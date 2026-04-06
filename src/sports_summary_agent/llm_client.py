"""
LLM client for generating match summaries using an OpenAI‑compatible API.
"""

import json
import logging

from openai import OpenAI, OpenAIError
from pydantic import ValidationError

from src.sports_summary_agent.models import MatchResult, MatchSummary

logger = logging.getLogger(__name__)


class LLMClientError(Exception):
    """Base exception for LLM client errors."""

    pass


class LLMClient:
    """Client for interacting with an OpenAI‑compatible API (Ollama/LocalAI)."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout: int = 30,
        max_tokens: int = 300,
        temperature: float = 0.7,
        dry_run: bool = False,
    ):
        """
        Initialize the LLM client.

        Args:
            base_url: Base URL of the OpenAI‑compatible API (e.g., 'http://localhost:11434/v1').
            api_key: API key (can be a dummy for local inference).
            model: Model name to use (e.g., 'llama3.2:3b').
            timeout: Request timeout in seconds.
            max_tokens: Maximum tokens to generate.
            temperature: Sampling temperature (0.0–1.0).
            dry_run: If True, no actual API call is made; a dummy summary is returned.
        """
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.dry_run = dry_run
        self._client: OpenAI | None = None

    @property
    def client(self) -> OpenAI:
        """Lazy initialization of the OpenAI client."""
        if self._client is None:
            self._client = OpenAI(
                base_url=self.base_url,
                api_key=self.api_key,
                timeout=self.timeout,
            )
        return self._client

    def generate_summary(self, match_result: MatchResult) -> MatchSummary:
        """
        Generate a summary for a given match result.

        Args:
            match_result: The match result to summarize.

        Returns:
            A MatchSummary object.

        Raises:
            LLMClientError: If the API call fails or the response cannot be parsed.
        """
        if self.dry_run:
            logger.info("Dry‑run mode: generating dummy summary")
            return self._generate_dry_run_summary(match_result)

        prompt = self._build_prompt(match_result)
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                response_format={"type": "json_object"},
            )
        except OpenAIError as e:
            raise LLMClientError(f"OpenAI API error: {e}") from e

        content = response.choices[0].message.content
        if not content:
            raise LLMClientError("Empty response from LLM")

        return self._parse_response(content, match_result.match_id)

    def _build_prompt(self, match_result: MatchResult) -> str:
        """Build the prompt for the LLM."""
        return f"""
You are a football analyst. Generate a post‑match summary for the following game.

Match: {match_result.home_team} {match_result.home_score} - {match_result.away_score} {match_result.away_team}
Date: {match_result.match_date}
Competition: {match_result.competition}

Provide a JSON object with exactly the following structure:
{{
  "bullet_points": [
    "First bullet point (max 20 words, focus on tactical aspects)",
    "Second bullet point (max 20 words, highlight key players)",
    "Third bullet point (max 20 words, discuss championship implications)"
  ],
  "championship_context": "One‑sentence context about the team's position in the championship, points difference, etc."
}}

Ensure bullet_points are exactly three items, each a string.
"""

    def _parse_response(self, content: str, match_id: str) -> MatchSummary:
        """Parse the LLM response into a MatchSummary."""
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise LLMClientError(f"Failed to parse LLM response as JSON: {e}") from e

        # Ensure required fields are present
        bullet_points = data.get("bullet_points", [])
        championship_context = data.get("championship_context", "")

        try:
            return MatchSummary(
                match_id=match_id,
                bullet_points=bullet_points,
                championship_context=championship_context,
                model_used=self.model,
                inference_source=self._inference_source(),
            )
        except ValidationError as e:
            raise LLMClientError(f"LLM response validation failed: {e}") from e

    def _generate_dry_run_summary(self, match_result: MatchResult) -> MatchSummary:
        """Generate a dummy summary for dry‑run mode."""
        bullet_points = [
            f"[DRY‑RUN] {match_result.home_team} dominated possession.",
            "[DRY‑RUN] Key player scored a brace.",
            "[DRY‑RUN] Victory places team closer to top of the table.",
        ]
        return MatchSummary(
            match_id=match_result.match_id,
            bullet_points=bullet_points,
            championship_context="Dry‑run context: no real inference performed.",
            model_used=self.model,
            inference_source="dry_run",
        )

    def _inference_source(self) -> str:
        """Determine the inference source based on base URL."""
        if self.dry_run:
            return "dry_run"
        if "localhost" in self.base_url or "127.0.0.1" in self.base_url:
            return "local_ollama"
        return "cloudflare_tunnel"

    def close(self):
        """Close the underlying client."""
        if self._client is not None:
            self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
