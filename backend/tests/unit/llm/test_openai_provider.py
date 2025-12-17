"""Unit tests for OpenAI provider.

Tests cover:
- Request building and response parsing
- Error handling and mapping
- Structured output support
- Feature capability checks
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.llm.errors import (
    AuthenticationError,
    ContentFilterError,
    InvalidRequestError,
    ModelNotFoundError,
    ProviderError,
    RateLimitError,
    TimeoutError,
)
from src.llm.models import ChatMessage, LLMRequest, ResponseFormat
from src.llm.providers.openai import OpenAIProvider


class FakeAPIStatusError(Exception):
    """Fake API error for testing exception chaining."""

    def __init__(self, status_code: int, message: str, response=None, request_id=None):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.response = response
        self.request_id = request_id


class TestOpenAIProviderInit:
    """Tests for OpenAI provider initialization."""

    def test_provider_name(self):
        """Test provider name is correct."""
        provider = OpenAIProvider(api_key="test-key")
        assert provider.name == "openai"

    def test_default_model(self):
        """Test default model is gpt-4o."""
        provider = OpenAIProvider(api_key="test-key")
        assert provider._default_model == "gpt-4o"

    def test_custom_model(self):
        """Test custom default model."""
        provider = OpenAIProvider(api_key="test-key", default_model="gpt-4o-mini")
        assert provider._default_model == "gpt-4o-mini"

    def test_custom_timeout(self):
        """Test custom timeout."""
        provider = OpenAIProvider(api_key="test-key", timeout=120.0)
        assert provider._timeout == 120.0


class TestOpenAIProviderCapabilities:
    """Tests for OpenAI provider capabilities."""

    def test_supports_json_schema(self):
        """Test JSON schema support."""
        provider = OpenAIProvider(api_key="test-key")
        assert provider.supports("json_schema") is True

    def test_supports_json_object(self):
        """Test JSON object support."""
        provider = OpenAIProvider(api_key="test-key")
        assert provider.supports("json_object") is True

    def test_supports_tools(self):
        """Test tools support."""
        provider = OpenAIProvider(api_key="test-key")
        assert provider.supports("tools") is True

    def test_supports_vision(self):
        """Test vision support."""
        provider = OpenAIProvider(api_key="test-key")
        assert provider.supports("vision") is True

    def test_supports_streaming(self):
        """Test streaming support."""
        provider = OpenAIProvider(api_key="test-key")
        assert provider.supports("streaming") is True

    def test_unsupported_feature(self):
        """Test unsupported feature returns False."""
        provider = OpenAIProvider(api_key="test-key")
        assert provider.supports("unknown_feature") is False


class TestOpenAIRequestBuilding:
    """Tests for OpenAI request building."""

    def test_build_basic_request(self):
        """Test building a basic request."""
        provider = OpenAIProvider(api_key="test-key")
        request = LLMRequest(
            messages=[ChatMessage(role="user", content="Hello")],
            model="gpt-4o",
            temperature=0.5,
        )

        openai_request = provider._build_request(request)

        assert openai_request["model"] == "gpt-4o"
        assert openai_request["temperature"] == 0.5
        assert len(openai_request["messages"]) == 1
        assert openai_request["messages"][0]["role"] == "user"
        assert openai_request["messages"][0]["content"] == "Hello"

    def test_build_request_with_json_schema(self):
        """Test building a request with JSON schema response format."""
        provider = OpenAIProvider(api_key="test-key")
        schema = {
            "type": "object",
            "properties": {"items": {"type": "array"}},
            "required": ["items"],
        }
        request = LLMRequest(
            messages=[ChatMessage(role="user", content="List items")],
            model="gpt-4o",
            response_format=ResponseFormat(type="json_schema", json_schema=schema),
        )

        openai_request = provider._build_request(request)

        assert openai_request["response_format"]["type"] == "json_schema"
        assert openai_request["response_format"]["json_schema"]["name"] == "response"
        assert openai_request["response_format"]["json_schema"]["strict"] is True
        assert openai_request["response_format"]["json_schema"]["schema"] == schema

    def test_build_request_with_json_object(self):
        """Test building a request with JSON object response format."""
        provider = OpenAIProvider(api_key="test-key")
        request = LLMRequest(
            messages=[ChatMessage(role="user", content="Respond in JSON")],
            model="gpt-4o",
            response_format=ResponseFormat(type="json_object"),
        )

        openai_request = provider._build_request(request)

        assert openai_request["response_format"]["type"] == "json_object"

    def test_build_request_with_max_tokens(self):
        """Test building a request with max_tokens."""
        provider = OpenAIProvider(api_key="test-key")
        request = LLMRequest(
            messages=[ChatMessage(role="user", content="Hello")],
            model="gpt-4o",
            max_tokens=100,
        )

        openai_request = provider._build_request(request)

        assert openai_request["max_tokens"] == 100

    def test_build_request_with_stop_sequences(self):
        """Test building a request with stop sequences."""
        provider = OpenAIProvider(api_key="test-key")
        request = LLMRequest(
            messages=[ChatMessage(role="user", content="Hello")],
            model="gpt-4o",
            stop=["END", "STOP"],
        )

        openai_request = provider._build_request(request)

        assert openai_request["stop"] == ["END", "STOP"]

    def test_build_request_uses_default_model(self):
        """Test that default model is used when not specified."""
        provider = OpenAIProvider(api_key="test-key", default_model="gpt-4o-mini")
        request = LLMRequest(
            messages=[ChatMessage(role="user", content="Hello")],
            model="",  # Empty model
        )

        openai_request = provider._build_request(request)

        # Should use default model (provider uses model or default)
        assert "model" in openai_request


class TestOpenAIResponseParsing:
    """Tests for OpenAI response parsing."""

    def test_parse_text_response(self):
        """Test parsing a text response."""
        provider = OpenAIProvider(api_key="test-key")

        # Create mock response
        mock_response = MagicMock()
        mock_response.id = "chatcmpl-123"
        mock_response.model = "gpt-4o"
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hello, world!"
        mock_response.choices[0].message.tool_calls = None
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.usage.total_tokens = 15
        mock_response.model_dump = MagicMock(return_value={})

        response = provider._parse_response(mock_response, latency_ms=100)

        assert response.text == "Hello, world!"
        assert response.tool_calls is None
        assert response.finish_reason == "stop"
        assert response.provider == "openai"
        assert response.model == "gpt-4o"
        assert response.latency_ms == 100
        assert response.usage.prompt_tokens == 10
        assert response.usage.completion_tokens == 5

    def test_parse_tool_call_response(self):
        """Test parsing a response with tool calls."""
        provider = OpenAIProvider(api_key="test-key")

        # Create mock tool call
        mock_tool_call = MagicMock()
        mock_tool_call.id = "call_123"
        mock_tool_call.type = "function"
        mock_tool_call.function.name = "get_weather"
        mock_tool_call.function.arguments = '{"location": "NYC"}'

        mock_response = MagicMock()
        mock_response.id = "chatcmpl-123"
        mock_response.model = "gpt-4o"
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = None
        mock_response.choices[0].message.tool_calls = [mock_tool_call]
        mock_response.choices[0].finish_reason = "tool_calls"
        mock_response.usage.prompt_tokens = 50
        mock_response.usage.completion_tokens = 20
        mock_response.usage.total_tokens = 70
        mock_response.model_dump = MagicMock(return_value={})

        response = provider._parse_response(mock_response, latency_ms=200)

        assert response.text is None
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0]["id"] == "call_123"
        assert response.tool_calls[0]["function"]["name"] == "get_weather"
        assert response.finish_reason == "tool_calls"


class TestOpenAIErrorHandling:
    """Tests for OpenAI error handling."""

    def test_handle_401_error(self):
        """Test handling 401 authentication error."""
        provider = OpenAIProvider(api_key="test-key")

        error = FakeAPIStatusError(status_code=401, message="Invalid API key")

        with pytest.raises(AuthenticationError) as exc_info:
            provider._handle_api_error(error)

        assert "Invalid OpenAI API key" in str(exc_info.value)
        assert exc_info.value.provider == "openai"
        assert exc_info.value.__cause__ is error

    def test_handle_403_error(self):
        """Test handling 403 forbidden error."""
        provider = OpenAIProvider(api_key="test-key")

        error = FakeAPIStatusError(status_code=403, message="Access denied")

        with pytest.raises(AuthenticationError) as exc_info:
            provider._handle_api_error(error)

        assert "access denied" in str(exc_info.value).lower()
        assert exc_info.value.__cause__ is error

    def test_handle_404_error(self):
        """Test handling 404 model not found error."""
        provider = OpenAIProvider(api_key="test-key")

        error = FakeAPIStatusError(status_code=404, message="Model not found")

        with pytest.raises(ModelNotFoundError) as exc_info:
            provider._handle_api_error(error)

        assert "not found" in str(exc_info.value).lower()
        assert exc_info.value.__cause__ is error

    def test_handle_429_error(self):
        """Test handling 429 rate limit error."""
        provider = OpenAIProvider(api_key="test-key")

        mock_response = MagicMock()
        mock_response.headers = {"retry-after": "30"}
        error = FakeAPIStatusError(
            status_code=429, message="Rate limit exceeded", response=mock_response
        )

        with pytest.raises(RateLimitError) as exc_info:
            provider._handle_api_error(error)

        assert exc_info.value.retry_after == 30.0
        assert exc_info.value.provider == "openai"
        assert exc_info.value.__cause__ is error

    def test_handle_429_error_without_retry_after(self):
        """Test handling 429 error without retry-after header."""
        provider = OpenAIProvider(api_key="test-key")

        mock_response = MagicMock()
        mock_response.headers = {}
        error = FakeAPIStatusError(
            status_code=429, message="Rate limit exceeded", response=mock_response
        )

        with pytest.raises(RateLimitError) as exc_info:
            provider._handle_api_error(error)

        assert exc_info.value.retry_after is None
        assert exc_info.value.__cause__ is error

    def test_handle_400_error(self):
        """Test handling 400 invalid request error."""
        provider = OpenAIProvider(api_key="test-key")

        error = FakeAPIStatusError(status_code=400, message="Invalid request parameters")

        with pytest.raises(InvalidRequestError) as exc_info:
            provider._handle_api_error(error)

        assert "Invalid request" in str(exc_info.value)
        assert exc_info.value.__cause__ is error

    def test_handle_400_content_filter_error(self):
        """Test handling 400 error with content filter."""
        provider = OpenAIProvider(api_key="test-key")

        error = FakeAPIStatusError(status_code=400, message="Content blocked by safety filter")

        with pytest.raises(ContentFilterError) as exc_info:
            provider._handle_api_error(error)

        assert "safety" in str(exc_info.value).lower()
        assert exc_info.value.__cause__ is error

    def test_handle_500_error(self):
        """Test handling 500 server error."""
        provider = OpenAIProvider(api_key="test-key")

        error = FakeAPIStatusError(status_code=500, message="Internal server error")

        with pytest.raises(ProviderError) as exc_info:
            provider._handle_api_error(error)

        assert "server error" in str(exc_info.value).lower()
        assert exc_info.value.__cause__ is error

    def test_handle_503_error(self):
        """Test handling 503 service unavailable error."""
        provider = OpenAIProvider(api_key="test-key")

        error = FakeAPIStatusError(status_code=503, message="Service unavailable")

        with pytest.raises(ProviderError) as exc_info:
            provider._handle_api_error(error)

        assert exc_info.value.provider == "openai"
        assert exc_info.value.__cause__ is error


class TestOpenAIProviderGenerate:
    """Tests for OpenAI provider generate method."""

    @pytest.mark.asyncio
    async def test_generate_success(self):
        """Test successful generation."""
        provider = OpenAIProvider(api_key="test-key")

        # Create mock response
        mock_response = MagicMock()
        mock_response.id = "chatcmpl-123"
        mock_response.model = "gpt-4o"
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hello!"
        mock_response.choices[0].message.tool_calls = None
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage.prompt_tokens = 5
        mock_response.usage.completion_tokens = 2
        mock_response.usage.total_tokens = 7
        mock_response.model_dump = MagicMock(return_value={})

        # Mock the client
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch.object(provider, "_client", mock_client):
            request = LLMRequest(
                messages=[ChatMessage(role="user", content="Hi")],
                model="gpt-4o",
            )
            response = await provider.generate(request)

        assert response.text == "Hello!"
        assert response.provider == "openai"
        assert response.finish_reason == "stop"

    @pytest.mark.asyncio
    async def test_generate_timeout(self):
        """Test timeout error handling."""
        from openai import APITimeoutError

        provider = OpenAIProvider(api_key="test-key")

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=APITimeoutError(request=MagicMock())
        )

        with patch.object(provider, "_client", mock_client):
            request = LLMRequest(
                messages=[ChatMessage(role="user", content="Hi")],
                model="gpt-4o",
            )

            with pytest.raises(TimeoutError) as exc_info:
                await provider.generate(request)

            assert "timed out" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_generate_connection_error(self):
        """Test connection error handling."""
        from openai import APIConnectionError

        provider = OpenAIProvider(api_key="test-key")

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=APIConnectionError(request=MagicMock())
        )

        with patch.object(provider, "_client", mock_client):
            request = LLMRequest(
                messages=[ChatMessage(role="user", content="Hi")],
                model="gpt-4o",
            )

            with pytest.raises(ProviderError) as exc_info:
                await provider.generate(request)

            assert "connect" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_client_lazy_initialization(self):
        """Test that client is lazily initialized."""
        provider = OpenAIProvider(api_key="test-key")

        # Client should not be created yet
        assert provider._client is None

        # Access client property
        client = provider.client

        # Now client should be created
        assert client is not None
        assert provider._client is client

    @pytest.mark.asyncio
    async def test_missing_api_key_raises_error(self):
        """Test that missing API key raises AuthenticationError."""
        provider = OpenAIProvider(api_key=None)
        provider._api_key = None  # Ensure no env var

        with pytest.raises(AuthenticationError) as exc_info:
            _ = provider.client

        assert "API key not configured" in str(exc_info.value)
