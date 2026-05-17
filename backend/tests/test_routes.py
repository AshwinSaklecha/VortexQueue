import json
from datetime import datetime, timezone
from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api import routes


def make_client() -> TestClient:
    app = FastAPI()
    app.include_router(routes.router, prefix="/api")
    return TestClient(app)


def valid_job_payload() -> dict:
    return {
        "task_type": "web_scraping",
        "payload": {"url": "https://example.com", "selectors": ["h1"]},
    }


def test_create_job_happy_path(monkeypatch):
    redis_client = Mock()
    insert_job_mock = Mock()

    monkeypatch.setattr(routes, "insert_job", insert_job_mock)
    monkeypatch.setattr(routes, "get_redis", Mock(return_value=redis_client))

    response = make_client().post("/api/jobs", json=valid_job_payload())

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "QUEUED"
    assert body["message"] == "Job enqueued successfully"
    assert body["job_id"]
    insert_job_mock.assert_called_once_with(
        body["job_id"],
        "web_scraping",
        {"url": "https://example.com", "selectors": ["h1"]},
    )
    redis_client.lpush.assert_called_once()
    queued = json.loads(redis_client.lpush.call_args.args[1])
    assert queued["job_id"] == body["job_id"]
    assert queued["task_type"] == "web_scraping"


def test_create_job_redis_failure_compensates_with_delete(monkeypatch):
    redis_client = Mock()
    redis_client.lpush.side_effect = RuntimeError("redis down")
    delete_job_mock = Mock()

    monkeypatch.setattr(routes, "insert_job", Mock())
    monkeypatch.setattr(routes, "delete_job", delete_job_mock)
    monkeypatch.setattr(routes, "get_redis", Mock(return_value=redis_client))

    response = make_client().post("/api/jobs", json=valid_job_payload())

    assert response.status_code == 503
    assert response.json()["detail"] == "Queue unavailable, please retry"
    delete_job_mock.assert_called_once()


def test_get_job_status_existing_job(monkeypatch):
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    monkeypatch.setattr(
        routes,
        "get_job",
        Mock(
            return_value={
                "id": "11111111-1111-1111-1111-111111111111",
                "task_type": "web_scraping",
                "status": "SUCCESS",
                "retry_count": 0,
                "created_at": now,
                "updated_at": now,
                "worker_id": "worker-1",
                "error_msg": None,
                "result": {"url": "https://example.com", "scraped": {"h1": ["Example"]}},
            }
        ),
    )

    response = make_client().get("/api/jobs/11111111-1111-1111-1111-111111111111")

    assert response.status_code == 200
    body = response.json()
    assert body["job_id"] == "11111111-1111-1111-1111-111111111111"
    assert body["task_type"] == "web_scraping"
    assert body["status"] == "SUCCESS"
    assert body["worker_id"] == "worker-1"
    assert body["result"]["scraped"]["h1"] == ["Example"]


def test_get_job_status_missing_job(monkeypatch):
    monkeypatch.setattr(routes, "get_job", Mock(return_value=None))

    response = make_client().get("/api/jobs/missing-job")

    assert response.status_code == 404
    assert response.json()["detail"] == "Job missing-job not found"
