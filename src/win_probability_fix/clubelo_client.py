"""
ClubElo API client with graceful degradation.

Fetches CSV data from ClubElo's Fixtures endpoint, parses win probabilities for Barcelona matches,
and caches results using cachetools. Handles network errors and HTTP errors gracefully,
falling back to cached data or empty results.
"""

import csv
import logging
from io import StringIO

import httpx
from cachetools import TTLCache
from pydantic import ValidationError

from src.shared.config import settings
from src.win_probability_fix.models import ClubEloMatch

logger = logging.getLogger(__name__)

# Cache for ClubElo probabilities (singleton)
cache: TTLCache | None = None


def get_cache() -> TTLCache:
    """Return the singleton TTLCache instance."""
    global cache
    if cache is None:
        # Create cache with TTL from settings
        cache = TTLCache(maxsize=1, ttl=settings.clubelo_cache_ttl)
    return cache


class ClubEloClient:
    """Client for ClubElo API with graceful degradation."""

    BASE_URL = "http://api.clubelo.com/Fixtures"

    def __init__(self, timeout: int | None = None):
        """
        Initialize client.

        Args:
            timeout: HTTP timeout in seconds (defaults to settings.clubelo_timeout).
        """
        self.timeout = timeout or settings.clubelo_timeout
        self.cache = get_cache()

    def get_probabilities(self) -> dict[str, float]:
        """
        Fetch Barcelona win probabilities for upcoming matches.

        Returns:
            Dictionary mapping date strings (YYYY-MM-DD) to win probability percentages (float).
            Empty dict if no Barcelona matches found or on any error (graceful degradation).
        """
        # Try cache first
        cached = self.cache.get("probabilities")
        if cached is not None:
            logger.debug("Cache hit for ClubElo probabilities")
            return cached

        logger.debug("Cache miss, fetching from ClubElo API")
        try:
            probabilities = self._fetch_and_parse()
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            logger.warning("ClubElo API request failed: %s", e)
            # Graceful degradation: return empty dict
            probabilities = {}

        # Store in cache (even empty dict to avoid repeated failures)
        self.cache["probabilities"] = probabilities
        return probabilities

    def _fetch_and_parse(self) -> dict[str, float]:
        """
        Perform HTTP request, parse CSV, compute probabilities.

        Raises:
            httpx.RequestError: On network errors (timeout, connection, etc.)
            httpx.HTTPStatusError: On HTTP error status (4xx, 5xx)

        Returns:
            Dict mapping date to probability percentage.
        """
        response = httpx.get(self.BASE_URL, timeout=self.timeout)
        response.raise_for_status()  # Raises httpx.HTTPStatusError for error statuses
        csv_text = response.text

        # Parse CSV
        reader = csv.DictReader(StringIO(csv_text))
        if not reader.fieldnames:
            logger.warning("ClubElo CSV has no columns")
            return {}

        # Validate required columns
        required_columns = {
            "Date",
            "Home",
            "Away",
            "GD=1",
            "GD=2",
            "GD=3",
            "GD=4",
            "GD=5",
            "GD>5",
            "GD=-1",
            "GD=-2",
            "GD=-3",
            "GD=-4",
            "GD=-5",
            "GD<-5",
        }
        missing = required_columns - set(reader.fieldnames)
        if missing:
            logger.warning("ClubElo CSV missing required columns: %s", missing)
            return {}

        probabilities = {}
        for row in reader:
            try:
                match = ClubEloMatch(**row)
            except ValidationError as e:
                logger.debug("Skipping invalid CSV row: %s", e)
                continue

            prob = match.barcelona_win_probability()
            if prob is not None:
                # Convert from fraction to percentage
                probabilities[match.Date] = round(prob * 100, 2)

        return probabilities
