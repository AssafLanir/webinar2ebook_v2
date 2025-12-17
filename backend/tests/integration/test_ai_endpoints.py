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


class TestSuggestOutlineEndpoint:
    """Tests for POST /api/ai/suggest-outline endpoint."""

    def test_suggest_outline_success(self):
        """Test successful outline suggestion."""
        mock_json_response = '{"items": [{"title": "Introduction", "level": 1, "notes": "Overview of the topic"}, {"title": "Main Concepts", "level": 1, "notes": "Core ideas"}, {"title": "Key Details", "level": 2, "notes": "Supporting information"}]}'

        mock_response = LLMResponse(
            text=mock_json_response,
            tool_calls=None,
            finish_reason="stop",
            usage=Usage(prompt_tokens=200, completion_tokens=100, total_tokens=300),
            model="gpt-4o",
            provider="openai",
            latency_ms=1200,
        )

        with patch("src.services.ai_service.LLMClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.generate = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            response = client.post(
                "/api/ai/suggest-outline",
                json={"transcript": "This is a transcript about software development."},
            )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert len(data["items"]) == 3
        assert data["items"][0]["title"] == "Introduction"
        assert data["items"][0]["level"] == 1
        assert data["items"][0]["notes"] == "Overview of the topic"
        assert data["items"][1]["title"] == "Main Concepts"
        assert data["items"][2]["level"] == 2

    def test_suggest_outline_empty_transcript(self):
        """Test that empty transcript returns validation error."""
        response = client.post(
            "/api/ai/suggest-outline",
            json={"transcript": ""},
        )

        assert response.status_code == 422

    def test_suggest_outline_missing_transcript(self):
        """Test that missing transcript field returns validation error."""
        response = client.post(
            "/api/ai/suggest-outline",
            json={},
        )

        assert response.status_code == 422

    def test_suggest_outline_too_long(self):
        """Test that transcript exceeding max length returns validation error."""
        long_transcript = "a" * 50001

        response = client.post(
            "/api/ai/suggest-outline",
            json={"transcript": long_transcript},
        )

        assert response.status_code == 422

    def test_suggest_outline_llm_rate_limit_error(self):
        """Test that LLM rate limit error returns 503."""
        with patch("src.services.ai_service.LLMClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.generate = AsyncMock(
                side_effect=RateLimitError("Rate limit exceeded", provider="openai")
            )
            mock_client_class.return_value = mock_client

            response = client.post(
                "/api/ai/suggest-outline",
                json={"transcript": "Some transcript text"},
            )

        assert response.status_code == 503
        data = response.json()
        assert data["error"]["code"] == "AI_SERVICE_ERROR"

    def test_suggest_outline_returns_multiple_levels(self):
        """Test that outline with mixed levels is returned correctly."""
        mock_json_response = '{"items": [{"title": "Chapter 1", "level": 1, "notes": ""}, {"title": "Section 1.1", "level": 2, "notes": "Details"}, {"title": "Subsection 1.1.1", "level": 3, "notes": "More details"}, {"title": "Chapter 2", "level": 1, "notes": "Next chapter"}]}'

        mock_response = LLMResponse(
            text=mock_json_response,
            tool_calls=None,
            finish_reason="stop",
            usage=Usage(prompt_tokens=200, completion_tokens=120, total_tokens=320),
            model="gpt-4o",
            provider="openai",
            latency_ms=1500,
        )

        with patch("src.services.ai_service.LLMClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.generate = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            response = client.post(
                "/api/ai/suggest-outline",
                json={"transcript": "A detailed transcript with multiple topics."},
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 4
        levels = [item["level"] for item in data["items"]]
        assert levels == [1, 2, 3, 1]

    def test_suggest_outline_empty_response(self):
        """Test handling of empty outline response."""
        mock_json_response = '{"items": []}'

        mock_response = LLMResponse(
            text=mock_json_response,
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

            response = client.post(
                "/api/ai/suggest-outline",
                json={"transcript": "Very short text."},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []


class TestSuggestResourcesEndpoint:
    """Tests for POST /api/ai/suggest-resources endpoint."""

    def test_suggest_resources_success(self):
        """Test successful resource suggestion."""
        mock_json_response = '{"resources": [{"label": "Python Documentation", "url_or_note": "https://docs.python.org"}, {"label": "FastAPI Guide", "url_or_note": "https://fastapi.tiangolo.com"}, {"label": "Related Article", "url_or_note": "Check out this blog post about best practices"}]}'

        mock_response = LLMResponse(
            text=mock_json_response,
            tool_calls=None,
            finish_reason="stop",
            usage=Usage(prompt_tokens=150, completion_tokens=80, total_tokens=230),
            model="gpt-4o",
            provider="openai",
            latency_ms=800,
        )

        with patch("src.services.ai_service.LLMClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.generate = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            response = client.post(
                "/api/ai/suggest-resources",
                json={"transcript": "This is a transcript about Python and FastAPI development."},
            )

        assert response.status_code == 200
        data = response.json()
        assert "resources" in data
        assert len(data["resources"]) == 3
        assert data["resources"][0]["label"] == "Python Documentation"
        assert data["resources"][0]["url_or_note"] == "https://docs.python.org"
        assert data["resources"][1]["label"] == "FastAPI Guide"
        assert data["resources"][2]["url_or_note"] == "Check out this blog post about best practices"

    def test_suggest_resources_empty_transcript(self):
        """Test that empty transcript returns validation error."""
        response = client.post(
            "/api/ai/suggest-resources",
            json={"transcript": ""},
        )

        assert response.status_code == 422

    def test_suggest_resources_missing_transcript(self):
        """Test that missing transcript field returns validation error."""
        response = client.post(
            "/api/ai/suggest-resources",
            json={},
        )

        assert response.status_code == 422

    def test_suggest_resources_too_long(self):
        """Test that transcript exceeding max length returns validation error."""
        long_transcript = "a" * 50001

        response = client.post(
            "/api/ai/suggest-resources",
            json={"transcript": long_transcript},
        )

        assert response.status_code == 422

    def test_suggest_resources_llm_rate_limit_error(self):
        """Test that LLM rate limit error returns 503."""
        with patch("src.services.ai_service.LLMClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.generate = AsyncMock(
                side_effect=RateLimitError("Rate limit exceeded", provider="openai")
            )
            mock_client_class.return_value = mock_client

            response = client.post(
                "/api/ai/suggest-resources",
                json={"transcript": "Some transcript text"},
            )

        assert response.status_code == 503
        data = response.json()
        assert data["error"]["code"] == "AI_SERVICE_ERROR"

    def test_suggest_resources_with_urls_and_notes(self):
        """Test that resources with both URLs and notes are returned correctly."""
        mock_json_response = '{"resources": [{"label": "Official Docs", "url_or_note": "https://example.com/docs"}, {"label": "Key Takeaway", "url_or_note": "Remember to always validate user input"}, {"label": "Tool Mentioned", "url_or_note": "https://github.com/some/tool"}]}'

        mock_response = LLMResponse(
            text=mock_json_response,
            tool_calls=None,
            finish_reason="stop",
            usage=Usage(prompt_tokens=150, completion_tokens=70, total_tokens=220),
            model="gpt-4o",
            provider="openai",
            latency_ms=600,
        )

        with patch("src.services.ai_service.LLMClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.generate = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            response = client.post(
                "/api/ai/suggest-resources",
                json={"transcript": "A transcript mentioning various tools and best practices."},
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data["resources"]) == 3
        # First resource is a URL
        assert "https://" in data["resources"][0]["url_or_note"]
        # Second resource is a note
        assert "Remember" in data["resources"][1]["url_or_note"]

    def test_suggest_resources_empty_response(self):
        """Test handling of empty resources response."""
        mock_json_response = '{"resources": []}'

        mock_response = LLMResponse(
            text=mock_json_response,
            tool_calls=None,
            finish_reason="stop",
            usage=Usage(prompt_tokens=100, completion_tokens=10, total_tokens=110),
            model="gpt-4o",
            provider="openai",
            latency_ms=400,
        )

        with patch("src.services.ai_service.LLMClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.generate = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            response = client.post(
                "/api/ai/suggest-resources",
                json={"transcript": "Very generic text with no specific resources."},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["resources"] == []
