"""
CalendarCleaner module – purges old events from Google Calendar.

This module provides a high‑level interface to scan and delete events that are older
than a configurable retention period, with support for batch operations and dry‑run mode.
"""

import time
from datetime import UTC, datetime

from googleapiclient.discovery import Resource
from googleapiclient.errors import HttpError

from src.calendar_cleaner.models import (
    CalendarCleanerConfig,
    CleanupStats,
    GoogleEvent,
)
from src.shared.config import settings
from src.shared.logging_config import get_logger

logger = get_logger(__name__)


class CalendarCleaner:
    """
    Orchestrates the cleaning of old Google Calendar events.

    Attributes:
        service: Authenticated Google Calendar API service resource.
        calendar_id: ID of the calendar to clean (defaults to settings.google_calendar_id).
        config: Configuration for the cleaning process.
    """

    def __init__(
        self,
        service: Resource,
        calendar_id: str | None = None,
        config: CalendarCleanerConfig | None = None,
    ):
        """
        Initialize the cleaner.

        Args:
            service: Google Calendar API service (from googleapiclient.discovery.build).
            calendar_id: Calendar identifier (defaults to settings.google_calendar_id).
            config: Cleaner configuration (defaults to settings‑derived config).
        """
        self.service = service
        self.calendar_id = calendar_id or settings.google_calendar_id
        self.config = config or self._default_config()
        self.stats = CleanupStats()

        logger.debug(
            "CalendarCleaner initialized",
            extra={
                "calendar_id": self.calendar_id,
                "retention_days": self.config.retention_days,
                "batch_size": self.config.batch_size,
                "dry_run": self.config.dry_run,
            },
        )

    @staticmethod
    def _default_config() -> CalendarCleanerConfig:
        """Build a default configuration from global settings."""
        return CalendarCleanerConfig(
            retention_days=settings.retention_days,
            batch_size=settings.cleanup_batch_size,
            dry_run=settings.cleanup_dry_run,
        )

    def run(self) -> CleanupStats:
        """
        Execute the cleaning process.

        Returns:
            CleanupStats: Statistics about the performed cleanup.
        """
        logger.info(
            "Starting calendar cleanup",
            extra={
                "calendar_id": self.calendar_id,
                "retention_days": self.config.retention_days,
                "cutoff": self.config.retention_cutoff.isoformat(),
            },
        )

        try:
            self._scan_and_delete()
        except Exception as e:
            logger.error("Cleanup process failed", exc_info=e)
            raise

        logger.info(
            "Calendar cleanup completed",
            extra={
                "scanned": self.stats.total_scanned,
                "eligible": self.stats.eligible_for_deletion,
                "deleted": self.stats.deleted,
                "errors": self.stats.errors,
            },
        )
        return self.stats

    def _scan_and_delete(self) -> None:
        """Scan events older than the cutoff and delete them in batches."""
        cutoff = self.config.retention_cutoff
        page_token = None
        deleted_ids = []

        while True:
            events_page = self._list_events_page(cutoff, page_token)
            if not events_page:
                break

            for event_dict in events_page:
                self.stats.total_scanned += 1
                try:
                    event = GoogleEvent.model_validate(event_dict)
                except Exception as e:
                    logger.warning(
                        "Failed to parse event, skipping",
                        extra={"event_id": event_dict.get("id"), "error": str(e)},
                    )
                    continue

                if self._should_delete(event):
                    self.stats.eligible_for_deletion += 1
                    if self.config.dry_run:
                        logger.info(
                            "Would delete event (dry‑run)",
                            extra={
                                "event_id": event.id,
                                "summary": event.summary,
                                "end": event.end.isoformat(),
                            },
                        )
                        self.stats.skipped += 1
                    else:
                        if self._delete_event(event.id):
                            deleted_ids.append(event.id)
                            self.stats.deleted += 1
                        else:
                            self.stats.errors += 1

                    # If we have reached batch size, commit deletions (if not dry‑run)
                    if (
                        not self.config.dry_run
                        and len(deleted_ids) >= self.config.batch_size
                    ):
                        self._commit_batch(deleted_ids)
                        deleted_ids = []

            page_token = (
                events_page.next_page_token
                if hasattr(events_page, "next_page_token")
                else None
            )
            if not page_token:
                break

        # Delete any remaining events in the last batch
        if not self.config.dry_run and deleted_ids:
            self._commit_batch(deleted_ids)

    def _list_events_page(
        self, cutoff: datetime, page_token: str | None = None
    ) -> list[dict]:
        """
        Retrieve a single page of events that end before the cutoff.

        Args:
            cutoff: Maximum end datetime (exclusive).
            page_token: Token for pagination.

        Returns:
            List of raw event dictionaries from the Google Calendar API.
        """
        try:
            result = (
                self.service.events()
                .list(
                    calendarId=self.calendar_id,
                    timeMax=cutoff.strftime(
                        "%Y-%m-%dT%H:%M:%SZ"
                    ),  # Google expects RFC3339 with Z
                    singleEvents=True,
                    orderBy="startTime",
                    maxResults=min(self.config.batch_size * 2, 250),
                    pageToken=page_token,
                )
                .execute()
            )
            return result.get("items", [])
        except HttpError as e:
            logger.error("Failed to list events", exc_info=e)
            raise

    def _should_delete(self, event: GoogleEvent) -> bool:
        """
        Determine whether an event should be deleted based on configurable filters.

        Args:
            event: Parsed GoogleEvent.

        Returns:
            True if the event should be deleted.
        """
        # Filter by summary substring
        if (
            self.config.filter_summary
            and self.config.filter_summary not in event.summary
        ):
            return False

        # Filter by description substring
        if (
            self.config.filter_description
            and self.config.filter_description not in event.description
        ):
            return False

        # Additional business logic: never delete future events (safety check)
        if event.end > datetime.now(UTC):
            logger.warning(
                "Event ends in the future, skipping deletion",
                extra={"event_id": event.id, "end": event.end.isoformat()},
            )
            return False

        return True

    def _delete_event(self, event_id: str) -> bool:
        """
        Delete a single event.

        Args:
            event_id: Google Calendar event ID.

        Returns:
            True if deletion succeeded, False otherwise.
        """
        try:
            self.service.events().delete(
                calendarId=self.calendar_id, eventId=event_id
            ).execute()
            logger.info(
                "Event deleted",
                extra={"event_id": event_id},
            )
            return True
        except HttpError as e:
            logger.error(
                "Failed to delete event",
                extra={"event_id": event_id, "error": str(e)},
            )
            return False

    def _commit_batch(self, event_ids: list[str]) -> None:
        """
        Log batch deletion (actual batch deletion is not supported by Google Calendar API,
        so we just log that a batch would have been deleted).

        Since the Google Calendar API does not support batch deletion of events,
        we delete them one by one but group the log messages.

        Args:
            event_ids: List of event IDs that were deleted.
        """
        if not event_ids:
            return
        logger.info(
            "Batch deletion committed",
            extra={"count": len(event_ids), "event_ids": event_ids},
        )
        # Small delay to avoid rate limiting
        time.sleep(0.1)


def create_cleaner(service: Resource, **kwargs) -> CalendarCleaner:
    """
    Factory function to create a CalendarCleaner instance.

    This is the recommended entry point for using the module.

    Args:
        service: Authenticated Google Calendar API service.
        **kwargs: Additional arguments passed to CalendarCleaner constructor.

    Returns:
        CalendarCleaner instance.
    """
    return CalendarCleaner(service, **kwargs)
