import uuid
import json
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from src.api.schemas import (
    JobCreateRequest,
    JobCreateResponse,
    JobResponse,
    DashboardStats,
    JobsByStatus,
)
from src.core.database import insert_job, get_job, get_stats
from src.core.redis import get_redis

router = APIRouter()

MAIN_QUEUE = "vortex:queue:main"


@router.post("/jobs", response_model=JobCreateResponse, status_code=202)
def create_job(request: JobCreateRequest):
    job_id = str(uuid.uuid4())

    # 1. Persist to DB first (source of truth)
    insert_job(job_id, request.task_type, request.payload)

    # 2. Push onto Redis queue — atomic LPUSH, workers BRPOP from the right
    redis = get_redis()
    queue_payload = json.dumps({
        "job_id": job_id,
        "task_type": request.task_type,
        "payload": request.payload,
        "enqueued_at": datetime.now(timezone.utc).isoformat(),
        "retry_count": 0,
    })
    redis.lpush(MAIN_QUEUE, queue_payload)

    return JobCreateResponse(
        job_id=job_id,
        status="QUEUED",
        message="Job enqueued successfully",
    )


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job_status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    return JobResponse(
        job_id=str(job["id"]),
        task_type=job["task_type"],
        status=job["status"],
        retry_count=job["retry_count"],
        created_at=job["created_at"],
        updated_at=job["updated_at"],
        worker_id=job.get("worker_id"),
        error_msg=job.get("error_msg"),
    )


@router.get("/dashboard-stats", response_model=DashboardStats)
def dashboard_stats():
    redis = get_redis()
    queue_depth = redis.llen(MAIN_QUEUE)

    raw = get_stats()

    # Normalise status counts — DB may not have a row for every status
    status_counts = raw["jobs_by_status"]
    jobs_by_status = JobsByStatus(
        QUEUED=status_counts.get("QUEUED", 0),
        PROCESSING=status_counts.get("PROCESSING", 0),
        SUCCESS=status_counts.get("SUCCESS", 0),
        FAILED=status_counts.get("FAILED", 0),
    )

    return DashboardStats(
        queue_depth=queue_depth,
        jobs_by_status=jobs_by_status,
        dlq_count=raw["dlq_count"],
        avg_processing_time_ms=raw["avg_processing_time_ms"],
        jobs_last_hour=raw["jobs_last_hour"],
    )
