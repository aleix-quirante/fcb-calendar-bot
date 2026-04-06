"""
SportsSummaryAgent orchestrates the generation of match summaries.
"""

import logging

from src.sports_summary_agent.feed_client import FeedClient, FeedClientError
from src.sports_summary_agent.llm_client import LLMClient, LLMClientError
from src.sports_summary_agent.models import MatchSummary

logger = logging.getLogger(__name__)


class SportsSummaryAgent:
    """
    Agent that fetches match results and generates summaries using an LLM.

    Attributes:
        feed_client: Client for fetching match results.
        llm_client: Client for generating summaries.
        cache_enabled: Whether to cache summaries to avoid duplicate generation.
        _cache: In‑memory cache of generated summaries (match_id → MatchSummary).
    """

    def __init__(
        self,
        feed_client: FeedClient,
        llm_client: LLMClient,
        cache_enabled: bool = True,
    ):
        """
        Initialize the agent.

        Args:
            feed_client: FeedClient instance.
            llm_client: LLMClient instance.
            cache_enabled: Enable caching of summaries.
        """
        self.feed_client = feed_client
        self.llm_client = llm_client
        self.cache_enabled = cache_enabled
        self._cache: dict[str, MatchSummary] = {}

    def run(self) -> list[MatchSummary]:
        """
        Run the agent: fetch matches, generate summaries, return results.

        Returns:
            List of MatchSummary objects (only newly generated ones).
        """
        try:
            match_results = self.feed_client.fetch_match_results()
        except FeedClientError:
            logger.error("Failed to fetch match results", exc_info=True)
            return []

        if not match_results:
            logger.info("No matches found to summarize")
            return []

        summaries = []
        for match_result in match_results:
            match_id = match_result.match_id

            # Check cache
            if self.cache_enabled and match_id in self._cache:
                logger.debug("Summary for match %s already cached, skipping", match_id)
                continue

            try:
                summary = self.llm_client.generate_summary(match_result)
            except LLMClientError:
                logger.error("Failed to generate summary for match", exc_info=True)
                continue

            summaries.append(summary)
            if self.cache_enabled:
                self._cache[match_id] = summary

        logger.info(
            "Generated %d new summaries (cache contains %d entries)",
            len(summaries),
            len(self._cache),
        )
        return summaries

    def clear_cache(self):
        """Clear the internal cache."""
        self._cache.clear()

    def get_cache_size(self) -> int:
        """Return the number of cached summaries."""
        return len(self._cache)
