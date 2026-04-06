"""
Unit tests for the RSS feed client (FeedClient) that fetches match results.
"""

from datetime import date
from unittest.mock import MagicMock, patch

import httpx
import pytest
from pydantic import ValidationError

from src.sports_summary_agent.feed_client import FeedClient, FeedClientError
from src.sports_summary_agent.models import MatchResult


@pytest.fixture
def feed_client():
    """Create a FeedClient instance with default settings."""
    return FeedClient(
        feed_url="https://example.com/feed.xml",
        timeout=10,
        max_retries=3,
    )


def test_feed_client_initialization(feed_client):
    """Test that FeedClient is initialized correctly."""
    assert feed_client.feed_url == "https://example.com/feed.xml"
    assert feed_client.timeout == 10
    assert feed_client.max_retries == 3


@patch("src.sports_summary_agent.feed_client.httpx")
def test_fetch_match_results_success(mock_httpx, feed_client):
    """Test successful parsing of a valid RSS feed."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = """
    <?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
        <channel>
            <item>
                <title>FC Barcelona 3 - 1 Real Madrid</title>
                <pubDate>2026-04-05T20:00:00Z</pubDate>
                <description>La Liga matchday 30</description>
            </item>
        </channel>
    </rss>
    """
    mock_httpx.get.return_value = mock_response

    results = feed_client.fetch_match_results()
    assert len(results) == 1
    result = results[0]
    assert result.home_team == "FC Barcelona"
    assert result.away_team == "Real Madrid"
    assert result.home_score == 3
    assert result.away_score == 1
    assert result.match_date == date(2026, 4, 5)
    assert result.competition == "La Liga"
    mock_httpx.get.assert_called_once_with(
        "https://example.com/feed.xml",
        timeout=10,
        follow_redirects=True,
    )


@patch("src.sports_summary_agent.feed_client.httpx")
def test_fetch_match_results_http_error(mock_httpx, feed_client):
    """Test handling of HTTP errors (404, 500, etc.)."""
    mock_httpx.get.side_effect = httpx.HTTPStatusError(
        "Not Found",
        request=MagicMock(),
        response=MagicMock(status_code=404),
    )
    with pytest.raises(FeedClientError, match="HTTP error"):
        feed_client.fetch_match_results()


@patch("src.sports_summary_agent.feed_client.httpx")
def test_fetch_match_results_timeout(mock_httpx, feed_client):
    """Test handling of request timeout."""
    mock_httpx.get.side_effect = httpx.TimeoutException("Request timed out")
    with pytest.raises(FeedClientError, match="Timeout"):
        feed_client.fetch_match_results()


@patch("src.sports_summary_agent.feed_client.httpx")
def test_fetch_match_results_retry_success(mock_httpx, feed_client):
    """Test that retries work after transient failures."""
    mock_httpx.get.side_effect = [
        httpx.TimeoutException("First attempt timed out"),
        MagicMock(status_code=200, text="<rss><channel></channel></rss>"),
    ]
    # Should not raise after retry
    results = feed_client.fetch_match_results()
    assert results == []  # empty feed
    assert mock_httpx.get.call_count == 2


@patch("src.sports_summary_agent.feed_client.httpx")
def test_fetch_match_results_malformed_xml(mock_httpx, feed_client):
    """Test handling of malformed XML that cannot be parsed."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "This is not XML"
    mock_httpx.get.return_value = mock_response

    with pytest.raises(FeedClientError, match="Failed to parse feed"):
        feed_client.fetch_match_results()


@patch("src.sports_summary_agent.feed_client.httpx")
def test_fetch_match_results_invalid_score_format(mock_httpx, feed_client):
    """Test handling of feed items with invalid score format."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = """
    <rss>
        <channel>
            <item>
                <title>Invalid Score Line</title>
                <pubDate>2026-04-05T20:00:00Z</pubDate>
            </item>
        </channel>
    </rss>
    """
    mock_httpx.get.return_value = mock_response

    # Should skip items that cannot be parsed
    results = feed_client.fetch_match_results()
    assert len(results) == 0


def test_match_result_validation():
    """Test that MatchResult model validates data correctly."""
    valid_data = {
        "home_team": "FC Barcelona",
        "away_team": "Real Madrid",
        "home_score": 2,
        "away_score": 0,
        "match_date": date(2026, 4, 5),
        "competition": "La Liga",
    }
    result = MatchResult(**valid_data)
    assert result.home_team == "FC Barcelona"

    # Negative scores should raise ValidationError
    invalid_data = valid_data.copy()
    invalid_data["home_score"] = -1
    with pytest.raises(ValidationError):
        MatchResult(**invalid_data)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
