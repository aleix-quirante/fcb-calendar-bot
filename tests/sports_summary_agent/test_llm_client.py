"""
Unit tests for the LLM client (OpenAI‑compatible) that generates match summaries.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from openai import OpenAIError
from pydantic import ValidationError

from src.sports_summary_agent.llm_client import LLMClient, LLMClientError
from src.sports_summary_agent.models import MatchResult, MatchSummary


@pytest.fixture
def llm_client():
    """Create an LLMClient instance with default settings."""
    return LLMClient(
        base_url="http://localhost:11434/v1",
        api_key="ollama",
        model="llama3.2:3b",
        timeout=30,
        max_tokens=300,
        temperature=0.7,
    )


@pytest.fixture
def sample_match_result():
    """Provide a sample MatchResult for testing."""
    return MatchResult(
        home_team="FC Barcelona",
        away_team="Real Madrid",
        home_score=3,
        away_score=1,
        match_date="2026-04-05",
        competition="La Liga",
    )


def test_llm_client_initialization(llm_client):
    """Test that LLMClient is initialized correctly."""
    assert llm_client.base_url == "http://localhost:11434/v1"
    assert llm_client.model == "llama3.2:3b"
    assert llm_client.timeout == 30


@patch("src.sports_summary_agent.llm_client.OpenAI")
def test_generate_summary_success(mock_openai_class, llm_client, sample_match_result):
    """Test successful generation of a match summary."""
    mock_openai = MagicMock()
    mock_openai_class.return_value = mock_openai

    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(
            message=MagicMock(
                content="""{
                    "bullet_points": [
                        "El Barça dominó la posesión con un 65%.",
                        "Lewandowski anotó un doblete en el primer tiempo.",
                        "La victoria coloca al equipo a 5 puntos del líder."
                    ],
                    "championship_context": "El Barça se mantiene tercero en La Liga, a 5 puntos del Atlético de Madrid."
                }"""
            )
        )
    ]
    mock_openai.chat.completions.create.return_value = mock_response

    summary = llm_client.generate_summary(sample_match_result)

    assert isinstance(summary, MatchSummary)
    assert summary.match_id == "fc-barcelona-real-madrid-2026-04-05"
    assert len(summary.bullet_points) == 3
    assert "posesión" in summary.bullet_points[0].lower()
    assert summary.championship_context.startswith("El Barça")
    assert summary.inference_source == "local_ollama"
    assert summary.model_used == "llama3.2:3b"
    assert isinstance(summary.generated_at, datetime)

    # Verify the OpenAI client was called with correct parameters
    mock_openai_class.assert_called_once_with(
        base_url="http://localhost:11434/v1",
        api_key="ollama",
        timeout=30,
    )
    mock_openai.chat.completions.create.assert_called_once()
    call_kwargs = mock_openai.chat.completions.create.call_args.kwargs
    assert call_kwargs["model"] == "llama3.2:3b"
    assert call_kwargs["max_tokens"] == 300
    assert call_kwargs["temperature"] == 0.7
    assert "FC Barcelona 3 - 1 Real Madrid" in call_kwargs["messages"][0]["content"]


@patch("src.sports_summary_agent.llm_client.OpenAI")
def test_generate_summary_openai_error(
    mock_openai_class, llm_client, sample_match_result
):
    """Test handling of OpenAI API errors."""
    mock_openai = MagicMock()
    mock_openai_class.return_value = mock_openai
    mock_openai.chat.completions.create.side_effect = OpenAIError("API unreachable")

    with pytest.raises(LLMClientError, match="API unreachable"):
        llm_client.generate_summary(sample_match_result)


@patch("src.sports_summary_agent.llm_client.OpenAI")
def test_generate_summary_invalid_json_response(
    mock_openai_class, llm_client, sample_match_result
):
    """Test handling of invalid JSON response from LLM."""
    mock_openai = MagicMock()
    mock_openai_class.return_value = mock_openai

    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content="Not JSON at all"))]
    mock_openai.chat.completions.create.return_value = mock_response

    with pytest.raises(LLMClientError, match="Failed to parse LLM response"):
        llm_client.generate_summary(sample_match_result)


@patch("src.sports_summary_agent.llm_client.OpenAI")
def test_generate_summary_missing_fields(
    mock_openai_class, llm_client, sample_match_result
):
    """Test handling of LLM response missing required fields."""
    mock_openai = MagicMock()
    mock_openai_class.return_value = mock_openai

    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(
            message=MagicMock(
                content="""{
                    "bullet_points": ["Only one bullet point"],
                    "championship_context": "Some context"
                }"""
            )
        )
    ]
    mock_openai.chat.completions.create.return_value = mock_response

    with pytest.raises(ValidationError):
        llm_client.generate_summary(sample_match_result)


@patch("src.sports_summary_agent.llm_client.OpenAI")
def test_generate_summary_dry_run(llm_client, sample_match_result):
    """Test dry‑run mode where no actual API call is made."""
    llm_client.dry_run = True
    summary = llm_client.generate_summary(sample_match_result)

    assert summary.inference_source == "dry_run"
    assert summary.model_used == "llama3.2:3b"
    assert len(summary.bullet_points) == 3
    # In dry‑run, bullet points should be placeholders
    assert "dry‑run" in summary.bullet_points[0].lower()


def test_match_summary_validation():
    """Test that MatchSummary model validates data correctly."""
    valid_data = {
        "match_id": "test-match-123",
        "bullet_points": ["Point 1", "Point 2", "Point 3"],
        "championship_context": "Context here",
        "generated_at": datetime.now(),
        "model_used": "llama3.2:3b",
        "inference_source": "local_ollama",
    }
    summary = MatchSummary(**valid_data)
    assert summary.match_id == "test-match-123"

    # Too few bullet points should raise ValidationError
    invalid_data = valid_data.copy()
    invalid_data["bullet_points"] = ["Only one"]
    with pytest.raises(ValidationError):
        MatchSummary(**invalid_data)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
