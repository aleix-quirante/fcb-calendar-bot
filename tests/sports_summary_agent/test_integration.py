"""
Integration and robustness tests for the SportsSummaryAgent.
"""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from src.sports_summary_agent.agent import SportsSummaryAgent
from src.sports_summary_agent.feed_client import FeedClientError
from src.sports_summary_agent.llm_client import LLMClientError
from src.sports_summary_agent.models import MatchResult, MatchSummary


@pytest.fixture
def mock_feed_client():
    """Create a mock FeedClient."""
    return MagicMock()


@pytest.fixture
def mock_llm_client():
    """Create a mock LLMClient."""
    return MagicMock()


@pytest.fixture
def agent(mock_feed_client, mock_llm_client):
    """Create a SportsSummaryAgent with mocked dependencies."""
    return SportsSummaryAgent(
        feed_client=mock_feed_client,
        llm_client=mock_llm_client,
        cache_enabled=False,
    )


def test_agent_initialization(agent, mock_feed_client, mock_llm_client):
    """Test that the agent is initialized with its dependencies."""
    assert agent.feed_client is mock_feed_client
    assert agent.llm_client is mock_llm_client


@patch("src.sports_summary_agent.agent.logger")
def test_run_success(mock_logger, agent, mock_feed_client, mock_llm_client):
    """Test a successful run with one match result."""
    match_result = MatchResult(
        home_team="FC Barcelona",
        away_team="Real Madrid",
        home_score=3,
        away_score=1,
        match_date=date(2026, 4, 5),
        competition="La Liga",
    )
    mock_feed_client.fetch_match_results.return_value = [match_result]

    summary = MatchSummary(
        match_id="fc-barcelona-real-madrid-2026-04-05",
        bullet_points=["Point 1", "Point 2", "Point 3"],
        championship_context="Context",
        generated_at="2026-04-05T22:00:00Z",
        model_used="llama3.2:3b",
        inference_source="local_ollama",
    )
    mock_llm_client.generate_summary.return_value = summary

    summaries = agent.run()

    assert len(summaries) == 1
    assert summaries[0] is summary
    mock_feed_client.fetch_match_results.assert_called_once()
    mock_llm_client.generate_summary.assert_called_once_with(match_result)
    mock_logger.info.assert_called()


@patch("src.sports_summary_agent.agent.logger")
def test_run_no_matches(mock_logger, agent, mock_feed_client):
    """Test run when there are no matches to summarize."""
    mock_feed_client.fetch_match_results.return_value = []

    summaries = agent.run()

    assert summaries == []
    mock_logger.info.assert_called_with("No matches found to summarize")


@patch("src.sports_summary_agent.agent.logger")
def test_run_feed_client_error(mock_logger, agent, mock_feed_client):
    """Test run when feed client raises an error."""
    mock_feed_client.fetch_match_results.side_effect = FeedClientError("Network error")

    summaries = agent.run()

    assert summaries == []
    mock_logger.error.assert_called_with("Failed to fetch match results", exc_info=True)


@patch("src.sports_summary_agent.agent.logger")
def test_run_llm_client_error(mock_logger, agent, mock_feed_client, mock_llm_client):
    """Test run when LLM client raises an error for a specific match."""
    match_result = MatchResult(
        home_team="FC Barcelona",
        away_team="Real Madrid",
        home_score=3,
        away_score=1,
        match_date=date(2026, 4, 5),
        competition="La Liga",
    )
    mock_feed_client.fetch_match_results.return_value = [match_result]
    mock_llm_client.generate_summary.side_effect = LLMClientError("API unreachable")

    summaries = agent.run()

    assert summaries == []
    mock_logger.error.assert_called_with(
        "Failed to generate summary for match", exc_info=True
    )


@patch("src.sports_summary_agent.agent.logger")
def test_run_partial_failure(mock_logger, agent, mock_feed_client, mock_llm_client):
    """Test run where one match succeeds and another fails."""
    match1 = MatchResult(
        home_team="FC Barcelona",
        away_team="Real Madrid",
        home_score=3,
        away_score=1,
        match_date=date(2026, 4, 5),
        competition="La Liga",
    )
    match2 = MatchResult(
        home_team="FC Barcelona",
        away_team="Atlético Madrid",
        home_score=2,
        away_score=2,
        match_date=date(2026, 4, 6),
        competition="La Liga",
    )
    mock_feed_client.fetch_match_results.return_value = [match1, match2]

    summary = MatchSummary(
        match_id="fc-barcelona-real-madrid-2026-04-05",
        bullet_points=["Point 1", "Point 2", "Point 3"],
        championship_context="Context",
        generated_at="2026-04-05T22:00:00Z",
        model_used="llama3.2:3b",
        inference_source="local_ollama",
    )
    # First call succeeds, second raises error
    mock_llm_client.generate_summary.side_effect = [
        summary,
        LLMClientError("API error"),
    ]

    summaries = agent.run()

    assert len(summaries) == 1
    assert summaries[0] is summary
    assert mock_llm_client.generate_summary.call_count == 2
    mock_logger.error.assert_called_once()


def test_cache_hit(agent, mock_feed_client, mock_llm_client):
    """Test that cache prevents duplicate LLM calls for the same match."""
    agent.cache_enabled = True
    match_result = MatchResult(
        home_team="FC Barcelona",
        away_team="Real Madrid",
        home_score=3,
        away_score=1,
        match_date=date(2026, 4, 5),
        competition="La Liga",
    )
    mock_feed_client.fetch_match_results.return_value = [match_result]

    summary = MatchSummary(
        match_id="fc-barcelona-real-madrid-2026-04-05",
        bullet_points=["Point 1", "Point 2", "Point 3"],
        championship_context="Context",
        generated_at="2026-04-05T22:00:00Z",
        model_used="llama3.2:3b",
        inference_source="local_ollama",
    )
    mock_llm_client.generate_summary.return_value = summary

    # First run
    summaries1 = agent.run()
    assert len(summaries1) == 1
    assert mock_llm_client.generate_summary.call_count == 1

    # Second run with same match result (cache hit)
    summaries2 = agent.run()
    assert len(summaries2) == 0  # cached, no new summary generated
    assert mock_llm_client.generate_summary.call_count == 1  # no extra call


def test_cache_disabled(agent, mock_feed_client, mock_llm_client):
    """Test that cache does not affect results when disabled."""
    agent.cache_enabled = False
    match_result = MatchResult(
        home_team="FC Barcelona",
        away_team="Real Madrid",
        home_score=3,
        away_score=1,
        match_date=date(2026, 4, 5),
        competition="La Liga",
    )
    mock_feed_client.fetch_match_results.return_value = [match_result]

    summary = MatchSummary(
        match_id="fc-barcelona-real-madrid-2026-04-05",
        bullet_points=["Point 1", "Point 2", "Point 3"],
        championship_context="Context",
        generated_at="2026-04-05T22:00:00Z",
        model_used="llama3.2:3b",
        inference_source="local_ollama",
    )
    mock_llm_client.generate_summary.return_value = summary

    # Two runs should generate two summaries
    agent.run()
    agent.run()
    assert mock_llm_client.generate_summary.call_count == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
