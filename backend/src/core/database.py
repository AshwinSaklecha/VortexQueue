import json
import logging

import psycopg2
import psycopg2.pool
from psycopg2.extras import RealDictCursor
from typing import Optional
from src.core.config import settings

logger = logging.getLogger(__name__)

# Module-level connection pool — initialised once, shared across all imports
_pool: Optional[psycopg2.pool.ThreadedConnectionPool] = None


def get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    global _pool
    if _pool is None:
        _pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=settings.DATABASE_URL,
        )
    return _pool


def get_conn():
    """Borrow a connection from the pool. Caller must call put_conn() when done."""
    return get_pool().getconn()


def put_conn(conn):
    """Return a connection to the pool."""
    get_pool().putconn(conn)


# ---------------------------------------------------------------------------
# Table bootstrap — called once at API / worker startup
# ---------------------------------------------------------------------------

CREATE_JOBS_TABLE = """
CREATE TABLE IF NOT EXISTS jobs (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_type    VARCHAR(50)  NOT NULL,
    payload      JSONB        NOT NULL,
    status       VARCHAR(20)  NOT NULL DEFAULT 'QUEUED',
    retry_count  INTEGER      NOT NULL DEFAULT 0,
    created_at   TIMESTAMPTZ  DEFAULT NOW(),
    updated_at   TIMESTAMPTZ  DEFAULT NOW(),
    worker_id    VARCHAR(100),
    error_msg    TEXT,
    result       JSONB
);
"""

# Adds result column to tables created before this column existed
ALTER_JOBS_ADD_RESULT = """
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS result JSONB;
"""

CREATE_DLQ_TABLE = """
CREATE TABLE IF NOT EXISTS dead_letter_queue (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id         UUID        NOT NULL,
    task_type      VARCHAR(50) NOT NULL,
    payload        JSONB       NOT NULL,
    failure_reason TEXT,
    failed_at      TIMESTAMPTZ DEFAULT NOW(),
    retry_count    INTEGER     NOT NULL
);
"""


def create_tables() -> None:
    """Idempotent — safe to call on every startup."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(CREATE_JOBS_TABLE)
            cur.execute(CREATE_DLQ_TABLE)
            cur.execute(ALTER_JOBS_ADD_RESULT)
        conn.commit()
        logger.info("[DB] Tables verified / created.")
    finally:
        put_conn(conn)


# ---------------------------------------------------------------------------
# Job helpers
# ---------------------------------------------------------------------------

def insert_job(job_id: str, task_type: str, payload: dict) -> dict:
    """Insert a new job in QUEUED state and return the full row."""
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO jobs (id, task_type, payload, status)
                VALUES (%s, %s, %s, 'QUEUED')
                RETURNING *
                """,
                (job_id, task_type, json.dumps(payload)),
            )
            row = dict(cur.fetchone())
        conn.commit()
        return row
    except Exception:
        conn.rollback()
        raise
    finally:
        put_conn(conn)


def delete_job(job_id: str) -> None:
    """Hard-delete a job row — used only for rollback compensation in the API."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM jobs WHERE id = %s", (job_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        put_conn(conn)


def update_job_status(
    job_id: str,
    status: str,
    worker_id: Optional[str] = None,
    retry_count: Optional[int] = None,
    error_msg: Optional[str] = None,
) -> None:
    """Partial update — only overwrites fields that are explicitly passed."""
    fields = ["status = %s", "updated_at = NOW()"]
    values = [status]

    if worker_id is not None:
        fields.append("worker_id = %s")
        values.append(worker_id)
    if retry_count is not None:
        fields.append("retry_count = %s")
        values.append(retry_count)
    if error_msg is not None:
        fields.append("error_msg = %s")
        values.append(error_msg)

    values.append(job_id)

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE jobs SET {', '.join(fields)} WHERE id = %s",
                values,
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        put_conn(conn)


def update_job_result(job_id: str, result: dict) -> None:
    """Store the task result and mark the job SUCCESS atomically."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE jobs SET result = %s, status = 'SUCCESS', updated_at = NOW() WHERE id = %s",
                (json.dumps(result), job_id),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        put_conn(conn)


def get_job(job_id: str) -> Optional[dict]:
    """Return a single job row as a dict, or None if not found."""
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM jobs WHERE id = %s", (job_id,))
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        put_conn(conn)


def get_processing_jobs() -> list[dict]:
    """Return all jobs currently in PROCESSING state — used by the janitor."""
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, task_type, payload, retry_count FROM jobs WHERE status = 'PROCESSING'"
            )
            return [dict(r) for r in cur.fetchall()]
    finally:
        put_conn(conn)


def insert_dlq(
    job_id: str,
    task_type: str,
    payload: dict,
    failure_reason: str,
    retry_count: int,
) -> None:
    """Move an exhausted job into the dead-letter queue table."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO dead_letter_queue
                    (job_id, task_type, payload, failure_reason, retry_count)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (job_id, task_type, json.dumps(payload), failure_reason, retry_count),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        put_conn(conn)


def get_stats() -> dict:
    """Aggregate query for the dashboard-stats endpoint."""
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Status breakdown
            cur.execute(
                """
                SELECT status, COUNT(*) AS count
                FROM jobs
                GROUP BY status
                """
            )
            status_rows = cur.fetchall()

            # DLQ count
            cur.execute("SELECT COUNT(*) AS count FROM dead_letter_queue")
            dlq_count = cur.fetchone()["count"]

            # Average processing time (updated_at - created_at for SUCCESS jobs in ms)
            cur.execute(
                """
                SELECT AVG(EXTRACT(EPOCH FROM (updated_at - created_at)) * 1000)::BIGINT
                    AS avg_ms
                FROM jobs
                WHERE status = 'SUCCESS'
                """
            )
            avg_row = cur.fetchone()
            avg_ms = avg_row["avg_ms"] if avg_row["avg_ms"] is not None else 0

            # Jobs submitted in the last hour
            cur.execute(
                """
                SELECT COUNT(*) AS count
                FROM jobs
                WHERE created_at >= NOW() - INTERVAL '1 hour'
                """
            )
            jobs_last_hour = cur.fetchone()["count"]

        jobs_by_status = {r["status"]: r["count"] for r in status_rows}
        return {
            "jobs_by_status": jobs_by_status,
            "dlq_count": dlq_count,
            "avg_processing_time_ms": avg_ms,
            "jobs_last_hour": jobs_last_hour,
        }
    finally:
        put_conn(conn)
