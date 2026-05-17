import json
from unittest.mock import Mock

from src.janitor import main as janitor


def test_scan_once_requeues_processing_jobs_without_lock(monkeypatch):
    redis_client = Mock()
    redis_client.exists.return_value = False
    update_status_mock = Mock()

    monkeypatch.setattr(
        janitor,
        "get_processing_jobs",
        Mock(
            return_value=[
                {
                    "id": "job-1",
                    "task_type": "web_scraping",
                    "payload": {"url": "https://example.com"},
                    "retry_count": 2,
                }
            ]
        ),
    )
    monkeypatch.setattr(janitor, "update_job_status", update_status_mock)

    rescued = janitor.scan_once(redis_client)

    assert rescued == 1
    redis_client.exists.assert_called_once_with("vortex:processing:job-1")
    redis_client.lpush.assert_called_once()
    queue_name, raw_payload = redis_client.lpush.call_args.args
    payload = json.loads(raw_payload)
    assert queue_name == janitor.settings.MAIN_QUEUE
    assert payload["job_id"] == "job-1"
    assert payload["retry_count"] == 2
    update_status_mock.assert_called_once_with("job-1", "QUEUED")


def test_scan_once_leaves_jobs_with_active_lock(monkeypatch):
    redis_client = Mock()
    redis_client.exists.return_value = True
    update_status_mock = Mock()

    monkeypatch.setattr(
        janitor,
        "get_processing_jobs",
        Mock(
            return_value=[
                {
                    "id": "job-1",
                    "task_type": "web_scraping",
                    "payload": {"url": "https://example.com"},
                    "retry_count": 0,
                }
            ]
        ),
    )
    monkeypatch.setattr(janitor, "update_job_status", update_status_mock)

    rescued = janitor.scan_once(redis_client)

    assert rescued == 0
    redis_client.exists.assert_called_once_with("vortex:processing:job-1")
    redis_client.lpush.assert_not_called()
    update_status_mock.assert_not_called()
