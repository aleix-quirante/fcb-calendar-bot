"""
Unit tests for the CalendarCleaner module.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from googleapiclient.errors import HttpError

from src.calendar_cleaner.cleaner import CalendarCleaner, create_cleaner
from src.calendar_cleaner.models import CalendarCleanerConfig, GoogleEvent


@pytest.fixture
def mock_service():
    """Mock Google Calendar API service."""
    service = MagicMock()
    events = MagicMock()
    service.events.return_value = events
    return service


@pytest.fixture
def cleaner(mock_service):
    """Create a CalendarCleaner instance with a mock service."""
    config = CalendarCleanerConfig(
        retention_days=7,
        batch_size=10,
        dry_run=False,
        filter_summary="Barça",
        filter_description="Barça Bot",
    )
    return CalendarCleaner(
        service=mock_service,
        calendar_id="primary",
        config=config,
    )


def test_default_config():
    """Test that default configuration is created correctly."""
    config = CalendarCleanerConfig()
    assert config.retention_days == 7
    assert config.batch_size == 50
    assert config.dry_run is False
    assert config.filter_summary is None
    assert config.filter_description is None


def test_retention_cutoff():
    """Test retention_cutoff property."""
    config = CalendarCleanerConfig(retention_days=3)
    cutoff = config.retention_cutoff
    now = datetime.now(timezone.utc)
    # Cutoff should be approximately now - 3 days (allow a few seconds of drift)
    diff = now - cutoff
    assert diff.days == 3
    assert diff.seconds < 10


def test_google_event_parsing():
    """Test GoogleEvent model parsing from Google API dict."""
    event_dict = {
        "id": "event123",
        "summary": "Test Event",
        "start": {"dateTime": "2026-04-01T10:00:00Z"},
        "end": {"dateTime": "2026-04-01T11:00:00Z"},
        "description": "A test event",
        "created": "2026-04-01T09:00:00Z",
        "updated": "2026-04-01T09:30:00Z",
        "iCalUID": "uid@example.com",
    }
    event = GoogleEvent.model_validate(event_dict)
    assert event.id == "event123"
    assert event.summary == "Test Event"
    assert event.start.year == 2026
    assert event.end.hour == 11
    assert event.description == "A test event"
    assert event.iCalUID == "uid@example.com"


def test_google_event_all_day():
    """Test parsing of all‑day events (date only)."""
    event_dict = {
        "id": "event456",
        "summary": "All Day",
        "start": {"date": "2026-04-01"},
        "end": {"date": "2026-04-02"},
        "description": "",
    }
    event = GoogleEvent.model_validate(event_dict)
    assert event.start.day == 1
    assert event.end.day == 2
    assert event.is_all_day is True


def test_should_delete_with_filters(cleaner):
    """Test _should_delete logic with summary/description filters."""
    event = GoogleEvent(
        id="test",
        summary="Barça vs Real Madrid",
        start=datetime(2026, 4, 1, 10, 0, tzinfo=timezone.utc),
        end=datetime(2026, 4, 1, 11, 0, tzinfo=timezone.utc),
        description="Barça Bot sync",
    )
    assert cleaner._should_delete(event) is True

    # Event without required summary filter
    event.summary = "Real Madrid vs Atlético"
    assert cleaner._should_delete(event) is False

    # Restore summary, remove description filter
    event.summary = "Barça vs Real Madrid"
    event.description = "Some other description"
    assert cleaner._should_delete(event) is False


def test_should_delete_future_event(cleaner):
    """Test that future events are not deleted."""
    future = datetime.now(timezone.utc).replace(year=2030)
    event = GoogleEvent(
        id="future",
        summary="Barça vs Future",
        start=future,
        end=future,
        description="Barça Bot",
    )
    # The event ends in the future, should be skipped
    assert cleaner._should_delete(event) is False


@patch("src.calendar_cleaner.cleaner.logger")
def test_list_events_page(mock_logger, cleaner, mock_service):
    """Test _list_events_page with mocked API response."""
    mock_events = [
        {
            "id": "1",
            "summary": "Event 1",
            "start": {"dateTime": "2026-03-01T10:00:00Z"},
            "end": {"dateTime": "2026-03-01T11:00:00Z"},
        },
        {
            "id": "2",
            "summary": "Event 2",
            "start": {"dateTime": "2026-03-02T10:00:00Z"},
            "end": {"dateTime": "2026-03-02T11:00:00Z"},
        },
    ]
    mock_execute = MagicMock(return_value={"items": mock_events})
    mock_service.events().list().execute = mock_execute

    cutoff = datetime(2026, 4, 1, tzinfo=timezone.utc)
    result = cleaner._list_events_page(cutoff)
    assert len(result) == 2
    assert result[0]["id"] == "1"
    # Verify API call parameters
    mock_service.events().list.assert_called_once_with(
        calendarId="primary",
        timeMax="2026-04-01T00:00:00Z",
        singleEvents=True,
        orderBy="startTime",
        maxResults=20,  # batch_size * 2 = 10 * 2 = 20, but capped at 250
        pageToken=None,
    )


@patch("src.calendar_cleaner.cleaner.logger")
def test_list_events_page_error(mock_logger, cleaner, mock_service):
    """Test _list_events_page when API raises an error."""
    mock_service.events().list().execute.side_effect = HttpError(
        resp=MagicMock(status=500), content=b"Internal Server Error"
    )
    cutoff = datetime(2026, 4, 1, tzinfo=timezone.utc)
    with pytest.raises(HttpError):
        cleaner._list_events_page(cutoff)
    mock_logger.error.assert_called()


def test_delete_event_success(cleaner, mock_service):
    """Test successful deletion of an event."""
    mock_service.events().delete().execute.return_value = None
    assert cleaner._delete_event("event123") is True
    mock_service.events().delete.assert_called_once_with(
        calendarId="primary", eventId="event123"
    )


def test_delete_event_failure(cleaner, mock_service):
    """Test deletion failure due to HTTP error."""
    mock_service.events().delete().execute.side_effect = HttpError(
        resp=MagicMock(status=404), content=b"Not Found"
    )
    assert cleaner._delete_event("event123") is False


@patch("src.calendar_cleaner.cleaner.logger")
def test_run_dry_run(mock_logger, mock_service):
    """Test run() in dry‑run mode (no deletions)."""
    config = CalendarCleanerConfig(dry_run=True, batch_size=5)
    cleaner = CalendarCleaner(
        service=mock_service,
        calendar_id="primary",
        config=config,
    )
    # Mock list_events_page to return a single event
    with patch.object(cleaner, "_list_events_page") as mock_list:
        mock_list.side_effect = [
            [
                {
                    "id": "1",
                    "summary": "Barça vs Team",
                    "start": {"dateTime": "2026-03-01T10:00:00Z"},
                    "end": {"dateTime": "2026-03-01T11:00:00Z"},
                    "description": "Barça Bot",
                }
            ],
            [],  # second page empty
        ]
        stats = cleaner.run()
        assert stats.total_scanned == 1
        assert stats.eligible_for_deletion == 1
        assert stats.deleted == 0  # dry‑run
        assert stats.skipped == 1
        assert stats.errors == 0
        # Ensure no delete calls were made
        mock_service.events().delete.assert_not_called()


def test_create_cleaner(mock_service):
    """Test factory function create_cleaner."""
    cleaner = create_cleaner(mock_service, calendar_id="test")
    assert cleaner.service == mock_service
    assert cleaner.calendar_id == "test"
    assert cleaner.config.retention_days == 7  # default


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
