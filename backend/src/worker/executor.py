"""
Executor: sits between the BRPOP loop and the actual task implementations.

Responsibilities:
  1. Idempotency check  — skip already-completed jobs (at-least-once delivery safety)
  2. Task dispatch      — call tasks.run(task_type, payload)
  3. Retry with backoff — re-enqueue with increasing delays on failure
  4. DLQ routing        — after MAX_RETRIES exhausted, write to dead_letter_queue
"""

import json
import logging
import time
from datetime import datetime, timezone

from src.core.config import settings
from src.core.redis import get_redis
from src.core.database import update_job_status, insert_dlq
from src.worker import tasks

logger = logging.getLogger(__name__)

# Exponential backoff delay ladder (seconds) — index = retry_count - 1
BACKOFF_DELAYS = [10, 30, 60, 120, 300]


def execute(job_id: str, task_type: str, payload: dict, retry_count: int) -> None:
    redis = get_redis()
    idempotency_key = f"vortex:idempotency:{job_id}"
    processing_key = f"vortex:processing:{job_id}"

    # ------------------------------------------------------------------
    # 1. Idempotency guard — prevents double-execution in at-least-once
    #    delivery (e.g. janitor re-queued a job the worker actually finished)
    # ------------------------------------------------------------------
    if redis.exists(idempotency_key):
        logger.info(
            "[Executor] job %s already completed (idempotency key found) — skipping",
            job_id,
        )
        update_job_status(job_id, "SUCCESS")
        return

    # ------------------------------------------------------------------
    # 2. Execute the task
    # ------------------------------------------------------------------
    try:
        logger.info("[Executor] running %s for job %s (attempt %d)", task_type, job_id, retry_count + 1)
        result = tasks.run(task_type, payload)
        logger.info("[Executor] job %s succeeded: %s", job_id, result)

        # Mark complete — idempotency key lives for 24h
        redis.set(idempotency_key, "done", ex=86400)
        redis.delete(processing_key)
        update_job_status(job_id, "SUCCESS")

    except Exception as exc:
        retry_count += 1
        logger.warning(
            "[Executor] job %s FAILED (attempt %d): %s",
            job_id, retry_count, exc,
        )

        # ------------------------------------------------------------------
        # 3. DLQ — retries exhausted
        # ------------------------------------------------------------------
        if retry_count >= settings.MAX_RETRIES:
            logger.error(
                "[Executor] job %s exhausted %d retries → DLQ",
                job_id, settings.MAX_RETRIES,
            )
            insert_dlq(job_id, task_type, payload, str(exc), retry_count)
            update_job_status(job_id, "FAILED", error_msg=str(exc))
            redis.delete(processing_key)
            return

        # ------------------------------------------------------------------
        # 4. Exponential backoff — re-enqueue after a delay
        #    We sleep here (blocking this worker) then push back to the queue.
        #    The heartbeat thread keeps the processing key alive during sleep.
        # ------------------------------------------------------------------
        delay = BACKOFF_DELAYS[min(retry_count - 1, len(BACKOFF_DELAYS) - 1)]
        logger.info(
            "[Executor] job %s will retry in %ds (retry_count=%d)",
            job_id, delay, retry_count,
        )

        # Set a short-lived key so the janitor knows this is a deliberate backoff
        redis.set(f"vortex:retry_delay:{job_id}", str(delay), ex=delay + 5)

        time.sleep(delay)

        updated_payload = json.dumps({
            "job_id": job_id,
            "task_type": task_type,
            "payload": payload,
            "enqueued_at": datetime.now(timezone.utc).isoformat(),
            "retry_count": retry_count,
        })
        redis.lpush(settings.MAIN_QUEUE, updated_payload)
        update_job_status(job_id, "QUEUED", retry_count=retry_count)

        redis.delete(processing_key)
        redis.delete(f"vortex:retry_delay:{job_id}")
