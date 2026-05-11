import json
import os

from dotenv import load_dotenv

load_dotenv()

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
QUEUE_NAME = os.getenv("REDIS_QUEUE_NAME", "vortex:queue:default")


def get_redis_connection():
    """
    Opens a connection to Redis.

    Redis is running separately from the FastAPI/Uvicorn server. Our app connects
    to it over TCP, usually localhost:6379 when Docker publishes the Redis port
    to Windows.
    """
    try:
        import redis
    except ImportError as exc:
        raise RuntimeError("Python package 'redis' is not installed. Run: pip install redis") from exc

    client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        decode_responses=True,
    )
    client.ping()
    return client


def push_job_to_queue(job_id, task_name, payload):
    """
    Converts a job into a JSON string and pushes it into the Redis list queue.
    """
    job_message = {
        "job_id": job_id,
        "task_name": task_name,
        "payload": payload,
    }

    redis_client = get_redis_connection()
    redis_client.lpush(QUEUE_NAME, json.dumps(job_message))
