import json
from unittest.mock import Mock

from src.worker import executor


def test_execute_happy_path_stores_result(monkeypatch):
    redis_client = Mock()
    redis_client.exists.return_value = False
    result = {"ok": True}

    monkeypatch.setattr(executor, "get_redis", Mock(return_value=redis_client))
    run_mock = Mock(return_value=result)
    update_result_mock = Mock()
    monkeypatch.setattr(executor.tasks, "run", run_mock)
    monkeypatch.setattr(executor, "update_job_result", update_result_mock)

    executor.execute("job-1", "web_scraping", {"url": "https://example.com"}, 0)

    run_mock.assert_called_once_with("web_scraping", {"url": "https://example.com"})
    redis_client.set.assert_called_once_with("vortex:idempotency:job-1", "done", ex=86400)
    redis_client.delete.assert_called_once_with("vortex:processing:job-1")
    update_result_mock.assert_called_once_with("job-1", result)


def test_execute_retry_path_requeues_job(monkeypatch):
    redis_client = Mock()
    redis_client.exists.return_value = False

    update_status_mock = Mock()
    insert_dlq_mock = Mock()
    monkeypatch.setattr(executor, "get_redis", Mock(return_value=redis_client))
    monkeypatch.setattr(executor.tasks, "run", Mock(side_effect=RuntimeError("boom")))
    monkeypatch.setattr(executor, "update_job_status", update_status_mock)
    monkeypatch.setattr(executor, "insert_dlq", insert_dlq_mock)
    monkeypatch.setattr(executor.time, "sleep", Mock())
    monkeypatch.setattr(executor.settings, "MAX_RETRIES", 5)

    executor.execute("job-1", "web_scraping", {"url": "bad"}, 0)

    redis_client.set.assert_called_once_with("vortex:retry_delay:job-1", "10", ex=15)
    executor.time.sleep.assert_called_once_with(10)
    redis_client.lpush.assert_called_once()
    queue_name, raw_payload = redis_client.lpush.call_args.args
    payload = json.loads(raw_payload)

    assert queue_name == executor.settings.MAIN_QUEUE
    assert payload["job_id"] == "job-1"
    assert payload["task_type"] == "web_scraping"
    assert payload["retry_count"] == 1
    update_status_mock.assert_called_once_with("job-1", "QUEUED", retry_count=1)
    insert_dlq_mock.assert_not_called()
    redis_client.delete.assert_any_call("vortex:processing:job-1")
    redis_client.delete.assert_any_call("vortex:retry_delay:job-1")


def test_execute_dlq_path_after_max_retries(monkeypatch):
    redis_client = Mock()
    redis_client.exists.return_value = False

    update_status_mock = Mock()
    insert_dlq_mock = Mock()
    monkeypatch.setattr(executor, "get_redis", Mock(return_value=redis_client))
    monkeypatch.setattr(executor.tasks, "run", Mock(side_effect=ValueError("bad payload")))
    monkeypatch.setattr(executor, "update_job_status", update_status_mock)
    monkeypatch.setattr(executor, "insert_dlq", insert_dlq_mock)
    monkeypatch.setattr(executor.settings, "MAX_RETRIES", 5)

    executor.execute("job-1", "image_processing", {"image_url": "bad"}, 4)

    insert_dlq_mock.assert_called_once_with(
        "job-1",
        "image_processing",
        {"image_url": "bad"},
        "bad payload",
        5,
    )
    update_status_mock.assert_called_once_with("job-1", "FAILED", error_msg="bad payload")
    redis_client.lpush.assert_not_called()
    redis_client.delete.assert_called_once_with("vortex:processing:job-1")


def test_execute_idempotency_skips_completed_job(monkeypatch):
    redis_client = Mock()
    redis_client.exists.return_value = True

    run_mock = Mock()
    update_status_mock = Mock()
    monkeypatch.setattr(executor, "get_redis", Mock(return_value=redis_client))
    monkeypatch.setattr(executor.tasks, "run", run_mock)
    monkeypatch.setattr(executor, "update_job_status", update_status_mock)

    executor.execute("job-1", "bulk_invoice", {"customer_id": "DEMO-001"}, 0)

    run_mock.assert_not_called()
    update_status_mock.assert_called_once_with("job-1", "SUCCESS")
    redis_client.set.assert_not_called()
