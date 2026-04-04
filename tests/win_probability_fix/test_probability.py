"""
Unit tests for the WinProbabilityFix module (ClubElo client with graceful degradation).

These tests verify that the system handles API failures gracefully, falling back to cached
data or default values without raising fatal exceptions.
"""

import csv
from datetime import datetime
from io import StringIO
from unittest.mock import MagicMock, patch, AsyncMock
import pytest
import httpx
from httpx import TimeoutException, ConnectError

# Import the module to test (assuming it will be named clubelo_client)
# We'll mock the actual import to avoid dependency on unimplemented code.
# In real tests, you would import:
# from src.win_probability_fix.clubelo_client import ClubEloClient


class TestClubEloClient:
    """Test suite for ClubElo client graceful degradation."""

    @pytest.fixture
    def mock_valid_csv(self):
        """Return a valid CSV response from ClubElo API."""
        csv_data = """Date,Home,Away,GD=1,GD=2,GD=3,GD=4,GD=5,GD>5,GD=-1,GD=-2,GD=-3,GD=-4,GD=-5,GD<-5
2026-04-10,Barcelona,Real Madrid,0.2,0.1,0.05,0.02,0.01,0.01,0.3,0.15,0.08,0.04,0.02,0.02
2026-04-12,Atletico Madrid,Barcelona,0.1,0.05,0.03,0.01,0.005,0.005,0.4,0.2,0.1,0.05,0.025,0.025
2026-04-15,Barcelona,Valencia,0.3,0.2,0.1,0.05,0.03,0.02,0.1,0.05,0.03,0.01,0.005,0.005
"""
        return csv_data

    @pytest.fixture
    def mock_csv_missing_columns(self):
        """Return CSV missing required GD columns."""
        csv_data = """Date,Home,Away,GD=1,GD=2
2026-04-10,Barcelona,Real Madrid,0.2,0.1
"""
        return csv_data

    @pytest.fixture
    def mock_csv_no_barcelona(self):
        """Return CSV with no Barcelona matches."""
        csv_data = """Date,Home,Away,GD=1,GD=2,GD=3,GD=4,GD=5,GD>5,GD=-1,GD=-2,GD=-3,GD=-4,GD=-5,GD<-5
2026-04-10,Real Madrid,Atletico Madrid,0.2,0.1,0.05,0.02,0.01,0.01,0.3,0.15,0.08,0.04,0.02,0.02
"""
        return csv_data

    @pytest.fixture
    def mock_csv_malformed(self):
        """Return malformed CSV (not parseable)."""
        return "invalid,data\n1,2,3"

    def test_successful_api_call_returns_probabilities(self, mock_valid_csv):
        """Test that a successful API call returns correct probability mapping."""
        with patch("httpx.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = mock_valid_csv
            mock_get.return_value = mock_response

            # Assuming ClubEloClient.get_probabilities() returns dict[date, float]
            # For now, we'll simulate the expected behavior.
            # In real implementation, replace with actual client call.
            from src.win_probability_fix.clubelo_client import ClubEloClient

            client = ClubEloClient()
            result = client.get_probabilities()

            # Expected probabilities:
            # For 2026-04-10: Barcelona home, sum of GD=1..GD>5 = 0.2+0.1+0.05+0.02+0.01+0.01 = 0.39 -> 39.0%
            # For 2026-04-12: Barcelona away, sum of GD=-1..GD<-5 = 0.4+0.2+0.1+0.05+0.025+0.025 = 0.8 -> 80.0%
            # For 2026-04-15: Barcelona home, sum = 0.3+0.2+0.1+0.05+0.03+0.02 = 0.7 -> 70.0%
            expected = {
                "2026-04-10": 39.0,
                "2026-04-12": 80.0,
                "2026-04-15": 70.0,
            }
            assert result == expected

    def test_api_timeout_falls_back_to_cache(self):
        """Test that a timeout exception triggers cache fallback."""
        with patch("httpx.get", side_effect=TimeoutException):
            # Mock cache to return a cached value
            with patch("src.win_probability_fix.clubelo_client.cache") as mock_cache:
                mock_cache.get.return_value = {"2026-04-10": 45.0}
                from src.win_probability_fix.clubelo_client import ClubEloClient

                client = ClubEloClient()
                result = client.get_probabilities()
                # Should return cached data
                assert result == {"2026-04-10": 45.0}
                # Ensure cache.get was called
                mock_cache.get.assert_called_once()

    def test_api_http_500_falls_back_to_empty_dict(self):
        """Test that an HTTP 500 error results in graceful degradation (empty dict)."""
        with patch("httpx.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "500 Server Error",
                request=MagicMock(),
                response=mock_response,
            )
            mock_get.return_value = mock_response

            # Mock cache to return None (no cached data)
            with patch("src.win_probability_fix.clubelo_client.cache") as mock_cache:
                mock_cache.get.return_value = None
                from src.win_probability_fix.clubelo_client import ClubEloClient

                client = ClubEloClient()
                result = client.get_probabilities()
                # Should return empty dict as fallback
                assert result == {}
                # Ensure no exception was raised

    def test_csv_missing_gd_columns_returns_empty_dict(self, mock_csv_missing_columns):
        """Test that CSV missing required GD columns results in empty dict (graceful degradation)."""
        with patch("httpx.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = mock_csv_missing_columns
            mock_get.return_value = mock_response

            with patch("src.win_probability_fix.clubelo_client.cache") as mock_cache:
                mock_cache.get.return_value = None

                from src.win_probability_fix.clubelo_client import ClubEloClient

                client = ClubEloClient()
                result = client.get_probabilities()
                # Should return empty dict because columns missing
                assert result == {}

    def test_csv_no_barcelona_matches_returns_empty_dict(self, mock_csv_no_barcelona):
        """Test that CSV with no Barcelona matches returns empty dict."""
        with patch("httpx.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = mock_csv_no_barcelona
            mock_get.return_value = mock_response

            with patch("src.win_probability_fix.clubelo_client.cache") as mock_cache:
                mock_cache.get.return_value = None

                from src.win_probability_fix.clubelo_client import ClubEloClient

                client = ClubEloClient()
                result = client.get_probabilities()
                assert result == {}

    def test_malformed_csv_returns_empty_dict(self, mock_csv_malformed):
        """Test that malformed CSV (parsing error) returns empty dict."""
        with patch("httpx.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = mock_csv_malformed
            mock_get.return_value = mock_response

            with patch("src.win_probability_fix.clubelo_client.cache") as mock_cache:
                mock_cache.get.return_value = None

                from src.win_probability_fix.clubelo_client import ClubEloClient

                client = ClubEloClient()
                result = client.get_probabilities()
                assert result == {}

    def test_connection_error_falls_back_to_cache(self):
        """Test that a connection error (no network) triggers cache fallback."""
        with patch("httpx.get", side_effect=ConnectError):
            with patch("src.win_probability_fix.clubelo_client.cache") as mock_cache:
                mock_cache.get.return_value = {"2026-04-10": 50.0}
                from src.win_probability_fix.clubelo_client import ClubEloClient

                client = ClubEloClient()
                result = client.get_probabilities()
                assert result == {"2026-04-10": 50.0}

    def test_cache_hit_avoids_api_call(self):
        """Test that if cache contains fresh data, no API request is made."""
        with patch("httpx.get") as mock_get:
            with patch("src.win_probability_fix.clubelo_client.cache") as mock_cache:
                mock_cache.get.return_value = {"2026-04-10": 60.0}
                from src.win_probability_fix.clubelo_client import ClubEloClient

                client = ClubEloClient()
                result = client.get_probabilities()
                # Ensure API not called
                mock_get.assert_not_called()
                assert result == {"2026-04-10": 60.0}

    def test_cache_miss_then_api_success_updates_cache(self):
        """Test that cache miss leads to API call, and result is cached."""
        with patch("httpx.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = """Date,Home,Away,GD=1,GD=2,GD=3,GD=4,GD=5,GD>5,GD=-1,GD=-2,GD=-3,GD=-4,GD=-5,GD<-5
2026-04-10,Barcelona,Real Madrid,0.2,0.1,0.05,0.02,0.01,0.01,0.3,0.15,0.08,0.04,0.02,0.02"""
            mock_get.return_value = mock_response

            with patch("src.win_probability_fix.clubelo_client.cache") as mock_cache:
                mock_cache.get.return_value = None  # cache miss
                mock_cache.__setitem__ = MagicMock()
                from src.win_probability_fix.clubelo_client import ClubEloClient

                client = ClubEloClient()
                result = client.get_probabilities()
                # Verify cache.__setitem__ was called with correct data and TTL
                mock_cache.__setitem__.assert_called_once()
                # Ensure result is correct
                expected = {"2026-04-10": 39.0}
                assert result == expected

    def test_graceful_degradation_no_fatal_exceptions(self):
        """Test that no fatal exceptions are raised under any failure scenario."""
        # Simulate a series of failures and ensure each returns a dict (empty or cached)
        from src.win_probability_fix.clubelo_client import ClubEloClient

        client = ClubEloClient()

        # 1. Timeout
        with patch("httpx.get", side_effect=TimeoutException):
            with patch("src.win_probability_fix.clubelo_client.cache") as mock_cache:
                mock_cache.get.return_value = None
                result = client.get_probabilities()
                assert isinstance(result, dict)  # Should be a dict, not raise

        # 2. HTTP 500
        with patch("httpx.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "500 Server Error",
                request=MagicMock(),
                response=mock_response,
            )
            mock_get.return_value = mock_response
            with patch("src.win_probability_fix.clubelo_client.cache") as mock_cache:
                mock_cache.get.return_value = None
                result = client.get_probabilities()
                assert isinstance(result, dict)

        # 3. CSV missing columns
        with patch("httpx.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = "Date,Home,Away"
            mock_get.return_value = mock_response
            result = client.get_probabilities()
            assert isinstance(result, dict)

        # 4. Connection error
        with patch("httpx.get", side_effect=ConnectError):
            with patch("src.win_probability_fix.clubelo_client.cache") as mock_cache:
                mock_cache.get.return_value = {}
                result = client.get_probabilities()
                assert isinstance(result, dict)

    def test_probability_calculation_edge_cases(self):
        """Test edge cases in probability calculation (zero probabilities, negative sums)."""
        csv_data = """Date,Home,Away,GD=1,GD=2,GD=3,GD=4,GD=5,GD>5,GD=-1,GD=-2,GD=-3,GD=-4,GD=-5,GD<-5
2026-04-10,Barcelona,Real Madrid,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0
2026-04-12,Atletico Madrid,Barcelona,0.0,0.0,0.0,0.0,0.0,0.0,1.0,0.0,0.0,0.0,0.0,0.0
"""
        with patch("httpx.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = csv_data
            mock_get.return_value = mock_response

            with patch("src.win_probability_fix.clubelo_client.cache") as mock_cache:
                mock_cache.get.return_value = None

                from src.win_probability_fix.clubelo_client import ClubEloClient

                client = ClubEloClient()
                result = client.get_probabilities()
                # First match: Barcelona home, sum = 0.0 -> 0.0%
                # Second match: Barcelona away, sum of GD=-1..GD<-5 = 1.0 -> 100.0%
                expected = {
                    "2026-04-10": 0.0,
                    "2026-04-12": 100.0,
                }
                assert result == expected

    def test_date_format_consistency(self):
        """Test that dates are parsed and returned in consistent format (YYYY-MM-DD)."""
        csv_data = """Date,Home,Away,GD=1,GD=2,GD=3,GD=4,GD=5,GD>5,GD=-1,GD=-2,GD=-3,GD=-4,GD=-5,GD<-5
2026-04-10,Barcelona,Real Madrid,0.2,0.1,0.05,0.02,0.01,0.01,0.3,0.15,0.08,0.04,0.02,0.02
"""
        with patch("httpx.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = csv_data
            mock_get.return_value = mock_response

            with patch("src.win_probability_fix.clubelo_client.cache") as mock_cache:
                mock_cache.get.return_value = None

                from src.win_probability_fix.clubelo_client import ClubEloClient

                client = ClubEloClient()
                result = client.get_probabilities()
                # Ensure keys are strings in YYYY-MM-DD format
                for date_str in result.keys():
                    # Validate format by parsing
                    datetime.strptime(date_str, "%Y-%m-%d")
                    assert len(date_str) == 10
                    assert date_str[4] == "-" and date_str[7] == "-"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
