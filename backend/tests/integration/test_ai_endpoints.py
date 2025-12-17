"""Integration tests for AI endpoints.

Tests the /api/ai/* endpoints with mocked LLM responses.
These tests verify the full request/response flow through the API layer.
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.llm import LLMResponse, Usage
from src.llm.errors import RateLimitError, AuthenticationError


client = TestClient(app)


class TestCleanTranscriptEndpoint:
    """Tests for POST /api/ai/clean-transcript endpoint."""

    def test_clean_transcript_success(self):
        """Test successful transcript cleanup."""
        mock_response = LLMResponse(
            text="This is the cleaned transcript. It has proper punctuation and formatting.",
            tool_calls=None,
            finish_reason="stop",
            usage=Usage(prompt_tokens=100, completion_tokens=50, total_tokens=150),
            model="gpt-4o",
            provider="openai",
            latency_ms=500,
        )

        with patch("src.services.ai_service.LLMClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.generate = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            response = client.post(
                "/api/ai/clean-transcript",
                json={"transcript": "Um, so like, this is the, you know, raw transcript."},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["cleaned_transcript"] == "This is the cleaned transcript. It has proper punctuation and formatting."

    def test_clean_transcript_empty_transcript(self):
        """Test that empty transcript returns validation error."""
        response = client.post(
            "/api/ai/clean-transcript",
            json={"transcript": ""},
        )

        assert response.status_code == 422  # Pydantic validation error

    def test_clean_transcript_missing_transcript(self):
        """Test that missing transcript field returns validation error."""
        response = client.post(
            "/api/ai/clean-transcript",
            json={},
        )

        assert response.status_code == 422

    def test_clean_transcript_too_long(self):
        """Test that transcript exceeding max length returns validation error."""
        # Create a transcript that exceeds 50,000 characters
        long_transcript = "a" * 50001

        response = client.post(
            "/api/ai/clean-transcript",
            json={"transcript": long_transcript},
        )

        assert response.status_code == 422

    def test_clean_transcript_at_max_length(self):
        """Test that transcript at exactly max length is accepted."""
        mock_response = LLMResponse(
            text="Cleaned version",
            tool_calls=None,
            finish_reason="stop",
            usage=Usage(prompt_tokens=100, completion_tokens=10, total_tokens=110),
            model="gpt-4o",
            provider="openai",
            latency_ms=500,
        )

        with patch("src.services.ai_service.LLMClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.generate = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            # Create transcript at exactly 50,000 characters
            max_transcript = "a" * 50000

            response = client.post(
                "/api/ai/clean-transcript",
                json={"transcript": max_transcript},
            )

        assert response.status_code == 200

    def test_clean_transcript_llm_rate_limit_error(self):
        """Test that LLM rate limit error returns 503."""
        with patch("src.services.ai_service.LLMClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.generate = AsyncMock(
                side_effect=RateLimitError("Rate limit exceeded", provider="openai")
            )
            mock_client_class.return_value = mock_client

            response = client.post(
                "/api/ai/clean-transcript",
                json={"transcript": "Some transcript text"},
            )

        assert response.status_code == 503
        data = response.json()
        assert data["error"]["code"] == "AI_SERVICE_ERROR"

    def test_clean_transcript_llm_auth_error(self):
        """Test that LLM authentication error returns 503."""
        with patch("src.services.ai_service.LLMClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.generate = AsyncMock(
                side_effect=AuthenticationError("Invalid API key", provider="openai")
            )
            mock_client_class.return_value = mock_client

            response = client.post(
                "/api/ai/clean-transcript",
                json={"transcript": "Some transcript text"},
            )

        assert response.status_code == 503
        data = response.json()
        assert data["error"]["code"] == "AI_SERVICE_ERROR"

    def test_clean_transcript_preserves_content(self):
        """Test that the AI response text is returned correctly."""
        expected_text = """This is a properly formatted transcript.

It has multiple paragraphs with correct punctuation.

Technical terms like "API" and "JSON" are preserved."""

        mock_response = LLMResponse(
            text=expected_text,
            tool_calls=None,
            finish_reason="stop",
            usage=Usage(prompt_tokens=100, completion_tokens=80, total_tokens=180),
            model="gpt-4o",
            provider="openai",
            latency_ms=750,
        )

        with patch("src.services.ai_service.LLMClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.generate = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            response = client.post(
                "/api/ai/clean-transcript",
                json={"transcript": "um so this is uh the transcript you know"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["cleaned_transcript"] == expected_text
