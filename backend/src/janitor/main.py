"""
Janitor — orphan recovery process.

Run as a completely standalone process:
    python -m src.janitor.main

Responsibility:
  Every JANITOR_INTERVAL seconds, scan the DB for jobs stuck in PROCESSING state
  whose Redis visibility-timeout key has expired (meaning the worker that held
  them has crashed or been killed). Re-enqueue those orphans so they get retried.

This is the Visibility Timeout recovery mechanism. Healthy workers keep their
processing key alive via HeartbeatThread. A dead worker stops heartbeating,
the key expires, and the janitor rescues the job on the next scan.
"""

import json
import logging
import signal
import sys
import time
from datetime import datetime, timezone

from src.core.config import settings
from src.core.database import create_tables, get_processing_jobs, update_job_status
from src.core.redis import get_redis

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.DEBUG),
    format="%(asctime)s [JANITOR] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

shutdown_requested = False


def _handle_signal(signum, frame):
    global shutdown_requested
    shutdown_requested = True
    logger.info("Signal %d received — janitor will stop after current scan.", signum)


signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGINT, _handle_signal)


def scan_once(redis) -> int:
    """
    Run a single orphan-recovery scan.
    Returns the number of jobs rescued.
    """
    jobs = get_processing_jobs()
    rescued = 0

    for job in jobs:
        job_id = str(job["id"])
        processing_key = f"vortex:processing:{job_id}"

        # Key still alive → worker is healthy, leave it alone
        if redis.exists(processing_key):
            continue

        # Key expired → worker is dead or timed out → rescue
        logger.warning("Rescued orphaned job %s (%s)", job_id, job["task_type"])

        queue_payload = json.dumps({
            "job_id": job_id,
            "task_type": job["task_type"],
            "payload": job["payload"],
            "enqueued_at": datetime.now(timezone.utc).isoformat(),
            "retry_count": job["retry_count"],
        })
        redis.lpush(settings.MAIN_QUEUE, queue_payload)
        update_job_status(job_id, "QUEUED")
        rescued += 1

    return rescued


def janitor_loop() -> None:
    create_tables()   # safe to call multiple times
    redis = get_redis()

    logger.info(
        "Janitor started — scanning every %ds for orphaned jobs.",
        settings.JANITOR_INTERVAL,
    )

    while not shutdown_requested:
        try:
            rescued = scan_once(redis)
            if rescued:
                logger.info("Scan complete — rescued %d orphaned job(s).", rescued)
            else:
                logger.debug("Scan complete — no orphans found.")
        except Exception as exc:
            logger.exception("Error during janitor scan: %s", exc)

        # Sleep in small increments so SIGTERM is noticed quickly
        for _ in range(settings.JANITOR_INTERVAL):
            if shutdown_requested:
                break
            time.sleep(1)

    logger.info("Janitor shut down cleanly.")
    sys.exit(0)


if __name__ == "__main__":
    janitor_loop()
