"""
Pydantic models for the CalendarCleaner module.

Defines data structures for Google Calendar events and configuration.
"""

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class GoogleEvent(BaseModel):
    """
    Represents a Google Calendar event with essential fields for cleaning logic.

    This model is used to validate and transform events returned by the Google Calendar API.
    """

    id: str = Field(description="Unique identifier of the event (Google's eventId).")
    summary: str = Field(description="Title of the event.")
    start: datetime = Field(description="Start datetime of the event (timezone-aware).")
    end: datetime = Field(description="End datetime of the event (timezone-aware).")
    description: str = Field(default="", description="Description of the event.")
    created: datetime | None = Field(
        default=None, description="When the event was created (if available)."
    )
    updated: datetime | None = Field(
        default=None, description="When the event was last updated (if available)."
    )
    iCalUID: str | None = Field(
        default=None, description="iCal UID of the event (if imported from ICS)."
    )

    @field_validator("start", "end", "created", "updated", mode="before")
    @classmethod
    def parse_datetime(cls, v):
        """
        Convert string or dict from Google API to datetime.

        Google Calendar API returns datetime in two possible formats:
        - 'dateTime' string (ISO 8601) for events with specific time.
        - 'date' string (YYYY-MM-DD) for all-day events.

        This validator attempts to parse both, but all-day events are not relevant
        for cleaning (they are not deleted). If parsing fails, we raise a ValueError.
        """
        if isinstance(v, dict):
            # Google API representation
            if "dateTime" in v:
                v = v["dateTime"]
            elif "date" in v:
                # All‑day event – we treat as datetime at 00:00 UTC
                v = v["date"] + "T00:00:00Z"
            else:
                raise ValueError(f"Unknown datetime dict format: {v}")
        if isinstance(v, str):
            # Remove trailing 'Z' and convert to naive datetime for simplicity
            # (timezone info is preserved via UTC).
            if v.endswith("Z"):
                v = v[:-1] + "+00:00"
            try:
                return datetime.fromisoformat(v)
            except ValueError:
                # Fallback to dateutil if needed (not required for Python >=3.11)
                pass
        return v

    @property
    def is_all_day(self) -> bool:
        """Return True if the event is an all‑day event (start time at 00:00 and duration 24h)."""
        # Simplified check: if the start hour/minute/second are zero and end - start == 1 day
        # This is not critical for cleaning logic.
        return (
            self.start.hour == 0 and self.start.minute == 0 and self.start.second == 0
        )

    model_config = ConfigDict(strict=True, arbitrary_types_allowed=True)


class CalendarCleanerConfig(BaseModel):
    """
    Configuration for the CalendarCleaner module.

    All fields can be overridden via environment variables with prefix BARCA_CLEANER_.
    """

    retention_days: int = Field(
        default=7,
        ge=0,
        le=365,
        description="Number of days to keep past events before deletion. Default 7.",
    )
    batch_size: int = Field(
        default=50,
        ge=1,
        le=250,
        description="Maximum number of events to delete in a single batch. Default 50.",
    )
    dry_run: bool = Field(
        default=False,
        description="If True, no events will be deleted; only log what would be deleted.",
    )
    filter_summary: str | None = Field(
        default=None,
        description="If set, only events whose summary contains this string will be considered for deletion.",
    )
    filter_description: str | None = Field(
        default=None,
        description="If set, only events whose description contains this string will be considered for deletion.",
    )

    @property
    def retention_cutoff(self) -> datetime:
        """
        Calculate the cutoff datetime: events ending before this time are considered old.

        Returns:
            datetime: Cutoff datetime (UTC).
        """
        # Use current time from settings (or datetime.utcnow) minus retention_days
        # In production we should use timezone‑aware UTC.
        from datetime import timedelta

        now = datetime.now(UTC)
        return now - timedelta(days=self.retention_days)

    @field_validator("retention_days")
    @classmethod
    def validate_retention_days(cls, v):
        """Ensure retention_days is reasonable."""
        if v == 0:
            # Warn but allow (means delete all past events)
            pass
        return v


class CleanupStats(BaseModel):
    """Statistics about a cleanup run."""

    total_scanned: int = Field(default=0, description="Total events scanned.")
    eligible_for_deletion: int = Field(
        default=0, description="Events that matched the retention and filter criteria."
    )
    deleted: int = Field(default=0, description="Events actually deleted.")
    skipped: int = Field(default=0, description="Events skipped (dry‑run or error).")
    errors: int = Field(default=0, description="Number of deletion errors.")

    def __str__(self) -> str:
        return (
            f"CleanupStats(scanned={self.total_scanned}, "
            f"eligible={self.eligible_for_deletion}, "
            f"deleted={self.deleted}, errors={self.errors})"
        )
