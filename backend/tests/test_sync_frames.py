from unittest.mock import MagicMock, patch

import pytest
from app.tasks import frames as frames_tasks
from app.tasks.frames import sync_s3_frames


@pytest.fixture
def mock_settings(monkeypatch):
    mock = MagicMock()
    mock.storage_frames_bucket = "frames"
    monkeypatch.setattr(frames_tasks, "get_settings", lambda: mock)
    return mock


@pytest.fixture
def mock_list_bucket_keys():
    with patch("app.tasks.frames.list_bucket_keys") as mock:
        yield mock


@pytest.fixture
def mock_import_frame():
    with patch("app.tasks.frames.import_frame") as mock:
        yield mock


def test_sync_s3_frames_triggers_import(mock_settings, mock_list_bucket_keys, mock_import_frame):
    # Setup S3 keys
    mock_list_bucket_keys.return_value = ["existing.jpg", "new.jpg"]

    # Setup DB session
    mock_session = MagicMock()
    # Mock existing URIs query result
    # The code queries: session.query(Frame.storage_uri)...
    mock_session.query.return_value.filter.return_value.all.return_value = [
        ("s3://frames/existing.jpg",)
    ]

    # Run the task
    with patch("app.tasks.frames._session_scope") as mock_scope:
        mock_scope.return_value.__enter__.return_value = mock_session
        result = sync_s3_frames()

    # Verify results
    assert result["status"] == "completed"
    assert result["s3_total"] == 2
    assert result["triggered_imports"] == 1
    
    # Verify import was called for the new file
    mock_import_frame.delay.assert_called_once_with(
        file_path="new.jpg",
        storage_uri="s3://frames/new.jpg"
    )


def test_sync_s3_frames_no_bucket(mock_settings, mock_list_bucket_keys):
    mock_settings.storage_frames_bucket = None
    
    result = sync_s3_frames()
    
    assert result["status"] == "skipped"
    mock_list_bucket_keys.assert_not_called()


def test_sync_s3_frames_handles_list_error(mock_settings, mock_list_bucket_keys):
    mock_list_bucket_keys.side_effect = Exception("S3 error")
    
    result = sync_s3_frames()
    
    assert result["status"] == "error"
    assert "S3 listing failed" in result["reason"]
