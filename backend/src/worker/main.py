"""
Worker entry point.

Run with:
    python -m src.worker.main

Flow per job:
  BRPOP → distributed lock (SET NX EX) → DB → heartbeat → executor → cleanup
"""

import json
import logging
import signal
import sys

from src.core.config import settings
from src.core.redis import get_redis
from src.core.database import create_tables, update_job_status
from src.worker.heartbeat import HeartbeatThread
from src.worker.executor import execute

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.DEBUG),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

MAIN_QUEUE = "vortex:queue:main"

# ---------------------------------------------------------------------------
# Graceful shutdown — set by SIGTERM / SIGINT, checked between jobs
# ---------------------------------------------------------------------------
shutdown_requested = False


def _handle_signal(signum, frame):
    global shutdown_requested
    shutdown_requested = True
    logger.info("Signal %d received — finishing current job then shutting down...", signum)


signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGINT, _handle_signal)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def worker_loop() -> None:
    create_tables()   # idempotent — ensures tables exist even if API never ran

    redis = get_redis()
    logger.info("Worker %s started. Listening on %s ...", settings.WORKER_ID, MAIN_QUEUE)

    while not shutdown_requested:
        # BRPOP blocks up to 5s, then returns None — lets us re-check shutdown flag
        result = redis.brpop(MAIN_QUEUE, timeout=5)

        if result is None:
            continue   # timeout, loop again — checks shutdown_requested at top

        if shutdown_requested:
            # Put the job back before exiting so it isn't lost
            _, raw = result
            redis.lpush(MAIN_QUEUE, raw)
            logger.info("Shutdown requested — job returned to queue, exiting cleanly.")
            break

        _, raw = result

        # ------------------------------------------------------------------
        # Parse
        # ------------------------------------------------------------------
        try:
            job_data = json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.error("Malformed job payload, discarding: %s | error: %s", raw, exc)
            continue

        job_id = job_data["job_id"]
        task_type = job_data["task_type"]
        payload = job_data["payload"]
        retry_count = job_data.get("retry_count", 0)

        logger.info("Picked up job %s (%s) retry=%d", job_id, task_type, retry_count)

        # ------------------------------------------------------------------
        # Distributed lock — SET NX EX prevents two workers taking the same job
        # (rare but possible if janitor re-queues while worker still holds it)
        # ------------------------------------------------------------------
        processing_key = f"vortex:processing:{job_id}"
        acquired = redis.set(processing_key, settings.WORKER_ID, ex=settings.VISIBILITY_TIMEOUT, nx=True)
        if not acquired:
            logger.warning(
                "Job %s already locked by another worker — skipping", job_id
            )
            continue

        # ------------------------------------------------------------------
        # Update DB → PROCESSING
        # If this fails, return the job to the queue before re-raising so
        # it isn't silently lost (it's already been popped from Redis).
        # ------------------------------------------------------------------
        try:
            update_job_status(job_id, "PROCESSING", worker_id=settings.WORKER_ID)
        except Exception as exc:
            logger.error(
                "Failed to mark job %s as PROCESSING in DB — returning to queue: %s",
                job_id, exc,
            )
            redis.delete(processing_key)
            redis.lpush(MAIN_QUEUE, raw)
            continue

        # ------------------------------------------------------------------
        # Heartbeat thread — keeps processing key alive for long-running jobs
        # ------------------------------------------------------------------
        heartbeat = HeartbeatThread(job_id)
        heartbeat.start()

        try:
            execute(job_id, task_type, payload, retry_count)
        except Exception as exc:
            # Safety net — executor should handle all exceptions internally
            logger.exception("Unhandled error in executor for job %s: %s", job_id, exc)
            update_job_status(job_id, "FAILED", error_msg=str(exc))
            redis.delete(processing_key)
        finally:
            heartbeat.stop()

    logger.info("Worker %s shut down cleanly.", settings.WORKER_ID)
    sys.exit(0)


if __name__ == "__main__":
    worker_loop()
