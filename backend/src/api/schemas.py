from pydantic import BaseModel, field_validator
from typing import Literal, Optional
from datetime import datetime


VALID_TASK_TYPES = {"image_processing", "web_scraping", "bulk_invoice"}


class JobCreateRequest(BaseModel):
    task_type: Literal["image_processing", "web_scraping", "bulk_invoice"]
    payload: dict

    @field_validator("payload")
    @classmethod
    def payload_not_empty(cls, v: dict) -> dict:
        if not v:
            raise ValueError("payload must not be empty")
        return v


class JobResponse(BaseModel):
    job_id: str
    task_type: str
    status: str
    retry_count: int
    created_at: datetime
    updated_at: datetime
    worker_id: Optional[str] = None
    error_msg: Optional[str] = None
    result: Optional[dict] = None


class JobCreateResponse(BaseModel):
    job_id: str
    status: str
    message: str


class JobsByStatus(BaseModel):
    QUEUED: int = 0
    PROCESSING: int = 0
    SUCCESS: int = 0
    FAILED: int = 0


class DashboardStats(BaseModel):
    queue_depth: int
    jobs_by_status: JobsByStatus
    dlq_count: int
    avg_processing_time_ms: int
    jobs_last_hour: int
