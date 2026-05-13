import json
import time

from engine.db import get_db_connection
from engine.redis_queue import QUEUE_NAME, get_redis_connection
# sleep time for simulation
SIMULATED_WORK_SECONDS = 5


def update_job_status(job_id, status):
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("Database connection failed")

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE jobs
                SET status = %s
                WHERE job_id = %s
                """,
                (status, job_id),
            )

            if cur.rowcount == 0:
                raise RuntimeError(f"No job found in database for job_id={job_id}")
    finally:
        conn.close()


def process_job(raw_job):
    job = json.loads(raw_job)

    job_id = job["job_id"]
    task_name = job["task_name"]

    print(f"Job received: {job_id} ({task_name})", flush=True)

    update_job_status(job_id, "RUNNING")
    print(f"Job {job_id} -> RUNNING", flush=True)

    time.sleep(SIMULATED_WORK_SECONDS)

    update_job_status(job_id, "SUCCESS")
    print(f"Job {job_id} -> SUCCESS", flush=True)


def worker_loop():
    redis_client = get_redis_connection()
    print(f"Worker started. Waiting for jobs on {QUEUE_NAME}...", flush=True)

    while True:
        _, raw_job = redis_client.brpop(QUEUE_NAME)
        process_job(raw_job)


if __name__ == "__main__":
    try:
        worker_loop()
    except KeyboardInterrupt:
        print("Worker stopped.", flush=True)
