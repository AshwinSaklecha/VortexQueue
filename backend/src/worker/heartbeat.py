import threading
import logging
from src.core.config import settings
from src.core.redis import get_redis

logger = logging.getLogger(__name__)


class HeartbeatThread(threading.Thread):
    """
    Daemon thread that keeps a job's visibility-timeout key alive in Redis.

    While a worker is actively processing a job it holds the key
    `vortex:processing:{job_id}` with a TTL of VISIBILITY_TIMEOUT seconds.
    Without a heartbeat, a long-running job would look like a crashed worker
    to the janitor. This thread refreshes the TTL every HEARTBEAT_INTERVAL
    seconds so the key never expires while real work is happening.

    Lifecycle:
        thread = HeartbeatThread(job_id)
        thread.start()
        ... do actual work ...
        thread.stop()   # sets the stop event; thread exits within one interval
    """

    def __init__(self, job_id: str):
        super().__init__(daemon=True, name=f"heartbeat-{job_id[:8]}")
        self.job_id = job_id
        self._stop_event = threading.Event()
        self._redis = get_redis()
        self._key = f"vortex:processing:{job_id}"

    def run(self) -> None:
        logger.debug("[Heartbeat] started for job %s", self.job_id)
        while not self._stop_event.wait(timeout=settings.HEARTBEAT_INTERVAL):
            refreshed = self._redis.expire(self._key, settings.VISIBILITY_TIMEOUT)
            if refreshed:
                logger.debug("[Heartbeat] refreshed TTL for job %s", self.job_id)
            else:
                # Key is gone — job was likely rescued by janitor or already finished
                logger.warning(
                    "[Heartbeat] key missing for job %s — stopping heartbeat",
                    self.job_id,
                )
                break
        logger.debug("[Heartbeat] stopped for job %s", self.job_id)

    def stop(self) -> None:
        """Signal the thread to exit after the current sleep interval."""
        self._stop_event.set()
