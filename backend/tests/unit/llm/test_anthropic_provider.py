"""Unit tests for Anthropic provider.

Tests cover:
- Request building and response parsing
- Error handling and mapping
- Structured output via tool_use pattern
- Feature capability checks
"""

import json
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
from src.llm.providers.anthropic import AnthropicProvider


class FakeAPIStatusError(Exception):
    """Fake API error for testing exception chaining."""

    def __init__(self, status_code: int, message: str, response=None, request_id=None):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.response = response
        self.request_id = request_id


class TestAnthropicProviderInit:
    """Tests for Anthropic provider initialization."""

    def test_provider_name(self):
        """Test provider name is correct."""
        provider = AnthropicProvider(api_key="test-key")
        assert provider.name == "anthropic"

    def test_default_model(self):
        """Test default model is claude-sonnet-4-5-20250929."""
        provider = AnthropicProvider(api_key="test-key")
        assert provider._default_model == "claude-sonnet-4-5-20250929"

    def test_custom_model(self):
        """Test custom default model."""
        provider = AnthropicProvider(api_key="test-key", default_model="claude-3-opus-20240229")
        assert provider._default_model == "claude-3-opus-20240229"

    def test_custom_timeout(self):
        """Test custom timeout."""
        provider = AnthropicProvider(api_key="test-key", timeout=120.0)
        assert provider._timeout == 120.0


class TestAnthropicProviderCapabilities:
    """Tests for Anthropic provider capabilities."""

    def test_supports_json_schema(self):
        """Test JSON schema support (via tool_use)."""
        provider = AnthropicProvider(api_key="test-key")
        assert provider.supports("json_schema") is True

    def test_does_not_support_json_object(self):
        """Test JSON object is NOT supported."""
        provider = AnthropicProvider(api_key="test-key")
        assert provider.supports("json_object") is False

    def test_supports_tools(self):
        """Test tools support."""
        provider = AnthropicProvider(api_key="test-key")
        assert provider.supports("tools") is True

    def test_supports_vision(self):
        """Test vision support."""
        provider = AnthropicProvider(api_key="test-key")
        assert provider.supports("vision") is True

    def test_supports_streaming(self):
        """Test streaming support."""
        provider = AnthropicProvider(api_key="test-key")
        assert provider.supports("streaming") is True

    def test_unsupported_feature(self):
        """Test unsupported feature returns False."""
        provider = AnthropicProvider(api_key="test-key")
        assert provider.supports("unknown_feature") is False


class TestAnthropicRequestBuilding:
    """Tests for Anthropic request building."""

    def test_build_basic_request(self):
        """Test building a basic request."""
        provider = AnthropicProvider(api_key="test-key")
        request = LLMRequest(
            messages=[ChatMessage(role="user", content="Hello")],
            model="claude-sonnet-4-5-20250929",
            temperature=0.5,
        )

        anthropic_request = provider._build_request(request)

        assert anthropic_request["model"] == "claude-sonnet-4-5-20250929"
        assert anthropic_request["temperature"] == 0.5
        assert len(anthropic_request["messages"]) == 1
        assert anthropic_request["messages"][0]["role"] == "user"
        assert anthropic_request["messages"][0]["content"] == "Hello"

    def test_build_request_with_system_message(self):
        """Test building a request with system message."""
        provider = AnthropicProvider(api_key="test-key")
        request = LLMRequest(
            messages=[
                ChatMessage(role="system", content="You are helpful."),
                ChatMessage(role="user", content="Hello"),
            ],
            model="claude-sonnet-4-5-20250929",
        )

        anthropic_request = provider._build_request(request)

        # System message should be extracted to top-level parameter
        assert anthropic_request["system"] == "You are helpful."
        # Only user message should be in messages array
        assert len(anthropic_request["messages"]) == 1
        assert anthropic_request["messages"][0]["role"] == "user"

    def test_build_request_with_json_schema(self):
        """Test building a request with JSON schema response format (tool_use pattern)."""
        provider = AnthropicProvider(api_key="test-key")
        schema = {
            "type": "object",
            "properties": {"items": {"type": "array"}},
            "required": ["items"],
        }
        request = LLMRequest(
            messages=[ChatMessage(role="user", content="List items")],
            model="claude-sonnet-4-5-20250929",
            response_format=ResponseFormat(type="json_schema", json_schema=schema),
        )

        anthropic_request = provider._build_request(request)

        # Should create a tool for structured output
        assert "tools" in anthropic_request
        assert len(anthropic_request["tools"]) == 1
        assert anthropic_request["tools"][0]["name"] == "respond_with_json"
        assert anthropic_request["tools"][0]["input_schema"] == schema

        # Should force tool use
        assert anthropic_request["tool_choice"]["type"] == "tool"
        assert anthropic_request["tool_choice"]["name"] == "respond_with_json"

    def test_build_request_with_stop_sequences(self):
        """Test building a request with stop sequences."""
        provider = AnthropicProvider(api_key="test-key")
        request = LLMRequest(
            messages=[ChatMessage(role="user", content="Hello")],
            model="claude-sonnet-4-5-20250929",
            stop=["END", "STOP"],
        )

        anthropic_request = provider._build_request(request)

        assert anthropic_request["stop_sequences"] == ["END", "STOP"]

    def test_temperature_clamped(self):
        """Test that temperature > 1 is clamped to 1."""
        provider = AnthropicProvider(api_key="test-key")
        request = LLMRequest(
            messages=[ChatMessage(role="user", content="Hello")],
            model="claude-sonnet-4-5-20250929",
            temperature=1.5,  # Should be clamped to 1.0
        )

        anthropic_request = provider._build_request(request)

        assert anthropic_request["temperature"] == 1.0

    def test_default_max_tokens(self):
        """Test default max_tokens is set."""
        provider = AnthropicProvider(api_key="test-key")
        request = LLMRequest(
            messages=[ChatMessage(role="user", content="Hello")],
            model="claude-sonnet-4-5-20250929",
        )

        anthropic_request = provider._build_request(request)

        assert anthropic_request["max_tokens"] == 4096


class TestAnthropicResponseParsing:
    """Tests for Anthropic response parsing."""

    def test_parse_text_response(self):
        """Test parsing a text response."""
        provider = AnthropicProvider(api_key="test-key")
        request = LLMRequest(
            messages=[ChatMessage(role="user", content="Hello")],
            model="claude-sonnet-4-5-20250929",
        )

        # Create mock response with text block
        mock_text_block = MagicMock()
        mock_text_block.type = "text"
        mock_text_block.text = "Hello, world!"

        mock_response = MagicMock()
        mock_response.id = "msg_123"
        mock_response.model = "claude-sonnet-4-5-20250929"
        mock_response.content = [mock_text_block]
        mock_response.stop_reason = "end_turn"
        mock_response.usage.input_tokens = 10
        mock_response.usage.output_tokens = 5
        mock_response.model_dump = MagicMock(return_value={})

        response = provider._parse_response(mock_response, latency_ms=100, request=request)

        assert response.text == "Hello, world!"
        assert response.tool_calls is None
        assert response.finish_reason == "stop"  # mapped from end_turn
        assert response.provider == "anthropic"
        assert response.model == "claude-sonnet-4-5-20250929"
        assert response.latency_ms == 100

    def test_parse_tool_use_response(self):
        """Test parsing a response with tool use."""
        provider = AnthropicProvider(api_key="test-key")
        request = LLMRequest(
            messages=[ChatMessage(role="user", content="Get weather")],
            model="claude-sonnet-4-5-20250929",
            tools=[{
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "parameters": {"type": "object", "properties": {}},
                },
            }],
        )

        # Create mock tool use block
        mock_tool_block = MagicMock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.id = "call_123"
        mock_tool_block.name = "get_weather"
        mock_tool_block.input = {"location": "NYC"}

        mock_response = MagicMock()
        mock_response.id = "msg_123"
        mock_response.model = "claude-sonnet-4-5-20250929"
        mock_response.content = [mock_tool_block]
        mock_response.stop_reason = "tool_use"
        mock_response.usage.input_tokens = 50
        mock_response.usage.output_tokens = 20
        mock_response.model_dump = MagicMock(return_value={})

        response = provider._parse_response(mock_response, latency_ms=200, request=request)

        assert len(response.tool_calls) == 1
        assert response.tool_calls[0]["id"] == "call_123"
        assert response.tool_calls[0]["function"]["name"] == "get_weather"
        assert json.loads(response.tool_calls[0]["function"]["arguments"]) == {"location": "NYC"}
        assert response.finish_reason == "tool_calls"

    def test_parse_structured_output_response(self):
        """Test parsing a structured output response (via tool_use pattern)."""
        provider = AnthropicProvider(api_key="test-key")
        schema = {
            "type": "object",
            "properties": {"items": {"type": "array"}},
            "required": ["items"],
        }
        request = LLMRequest(
            messages=[ChatMessage(role="user", content="List items")],
            model="claude-sonnet-4-5-20250929",
            response_format=ResponseFormat(type="json_schema", json_schema=schema),
        )

        # Create mock tool use block for respond_with_json
        mock_tool_block = MagicMock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.id = "call_123"
        mock_tool_block.name = "respond_with_json"
        mock_tool_block.input = {"items": [{"title": "Item 1"}, {"title": "Item 2"}]}

        mock_response = MagicMock()
        mock_response.id = "msg_123"
        mock_response.model = "claude-sonnet-4-5-20250929"
        mock_response.content = [mock_tool_block]
        mock_response.stop_reason = "tool_use"
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50
        mock_response.model_dump = MagicMock(return_value={})

        response = provider._parse_response(mock_response, latency_ms=300, request=request)

        # For structured output, the tool input should become the text response
        assert response.text is not None
        parsed = json.loads(response.text)
        assert "items" in parsed
        assert len(parsed["items"]) == 2
        # Tool calls should be empty since this was structured output
        assert response.tool_calls is None

    def test_finish_reason_mapping(self):
        """Test that Anthropic finish reasons are mapped correctly."""
        provider = AnthropicProvider(api_key="test-key")
        request = LLMRequest(
            messages=[ChatMessage(role="user", content="Hello")],
            model="claude-sonnet-4-5-20250929",
        )

        test_cases = [
            ("end_turn", "stop"),
            ("max_tokens", "length"),
            ("stop_sequence", "stop"),
            ("tool_use", "tool_calls"),
        ]

        for anthropic_reason, expected_reason in test_cases:
            mock_text_block = MagicMock()
            mock_text_block.type = "text"
            mock_text_block.text = "Test"

            mock_response = MagicMock()
            mock_response.id = "msg_123"
            mock_response.model = "claude-sonnet-4-5-20250929"
            mock_response.content = [mock_text_block]
            mock_response.stop_reason = anthropic_reason
            mock_response.usage.input_tokens = 10
            mock_response.usage.output_tokens = 5
            mock_response.model_dump = MagicMock(return_value={})

            response = provider._parse_response(mock_response, latency_ms=100, request=request)
            assert response.finish_reason == expected_reason, f"Failed for {anthropic_reason}"


class TestAnthropicErrorHandling:
    """Tests for Anthropic error handling."""

    def test_handle_401_error(self):
        """Test handling 401 authentication error."""
        provider = AnthropicProvider(api_key="test-key")

        error = FakeAPIStatusError(status_code=401, message="Invalid API key")

        with pytest.raises(AuthenticationError) as exc_info:
            provider._handle_api_error(error)

        assert "Invalid Anthropic API key" in str(exc_info.value)
        assert exc_info.value.provider == "anthropic"
        assert exc_info.value.__cause__ is error

    def test_handle_403_error(self):
        """Test handling 403 forbidden error."""
        provider = AnthropicProvider(api_key="test-key")

        error = FakeAPIStatusError(status_code=403, message="Access denied")

        with pytest.raises(AuthenticationError) as exc_info:
            provider._handle_api_error(error)

        assert "access denied" in str(exc_info.value).lower()
        assert exc_info.value.__cause__ is error

    def test_handle_404_error(self):
        """Test handling 404 model not found error."""
        provider = AnthropicProvider(api_key="test-key")

        error = FakeAPIStatusError(status_code=404, message="Model not found")

        with pytest.raises(ModelNotFoundError) as exc_info:
            provider._handle_api_error(error)

        assert "not found" in str(exc_info.value).lower()
        assert exc_info.value.__cause__ is error

    def test_handle_429_error(self):
        """Test handling 429 rate limit error."""
        provider = AnthropicProvider(api_key="test-key")

        mock_response = MagicMock()
        mock_response.headers = {"retry-after": "60"}
        error = FakeAPIStatusError(
            status_code=429, message="Rate limit exceeded", response=mock_response
        )

        with pytest.raises(RateLimitError) as exc_info:
            provider._handle_api_error(error)

        assert exc_info.value.retry_after == 60.0
        assert exc_info.value.provider == "anthropic"
        assert exc_info.value.__cause__ is error

    def test_handle_400_error(self):
        """Test handling 400 invalid request error."""
        provider = AnthropicProvider(api_key="test-key")

        error = FakeAPIStatusError(status_code=400, message="Invalid request parameters")

        with pytest.raises(InvalidRequestError) as exc_info:
            provider._handle_api_error(error)

        assert "Invalid request" in str(exc_info.value)
        assert exc_info.value.__cause__ is error

    def test_handle_400_safety_error(self):
        """Test handling 400 error with safety filter."""
        provider = AnthropicProvider(api_key="test-key")

        error = FakeAPIStatusError(status_code=400, message="Content blocked due to safety concerns")

        with pytest.raises(ContentFilterError) as exc_info:
            provider._handle_api_error(error)

        assert "safety" in str(exc_info.value).lower()
        assert exc_info.value.__cause__ is error

    def test_handle_500_error(self):
        """Test handling 500 server error."""
        provider = AnthropicProvider(api_key="test-key")

        error = FakeAPIStatusError(status_code=500, message="Internal server error")

        with pytest.raises(ProviderError) as exc_info:
            provider._handle_api_error(error)

        assert "server error" in str(exc_info.value).lower()
        assert exc_info.value.__cause__ is error


class TestAnthropicProviderGenerate:
    """Tests for Anthropic provider generate method."""

    @pytest.mark.asyncio
    async def test_generate_success(self):
        """Test successful generation."""
        provider = AnthropicProvider(api_key="test-key")

        # Create mock response
        mock_text_block = MagicMock()
        mock_text_block.type = "text"
        mock_text_block.text = "Hello!"

        mock_response = MagicMock()
        mock_response.id = "msg_123"
        mock_response.model = "claude-sonnet-4-5-20250929"
        mock_response.content = [mock_text_block]
        mock_response.stop_reason = "end_turn"
        mock_response.usage.input_tokens = 5
        mock_response.usage.output_tokens = 2
        mock_response.model_dump = MagicMock(return_value={})

        # Mock the client
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        with patch.object(provider, "_client", mock_client):
            request = LLMRequest(
                messages=[ChatMessage(role="user", content="Hi")],
                model="claude-sonnet-4-5-20250929",
            )
            response = await provider.generate(request)

        assert response.text == "Hello!"
        assert response.provider == "anthropic"
        assert response.finish_reason == "stop"

    @pytest.mark.asyncio
    async def test_generate_timeout(self):
        """Test timeout error handling."""
        from anthropic import APITimeoutError

        provider = AnthropicProvider(api_key="test-key")

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(
            side_effect=APITimeoutError(request=MagicMock())
        )

        with patch.object(provider, "_client", mock_client):
            request = LLMRequest(
                messages=[ChatMessage(role="user", content="Hi")],
                model="claude-sonnet-4-5-20250929",
            )

            with pytest.raises(TimeoutError) as exc_info:
                await provider.generate(request)

            assert "timed out" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_generate_connection_error(self):
        """Test connection error handling."""
        from anthropic import APIConnectionError

        provider = AnthropicProvider(api_key="test-key")

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(
            side_effect=APIConnectionError(request=MagicMock())
        )

        with patch.object(provider, "_client", mock_client):
            request = LLMRequest(
                messages=[ChatMessage(role="user", content="Hi")],
                model="claude-sonnet-4-5-20250929",
            )

            with pytest.raises(ProviderError) as exc_info:
                await provider.generate(request)

            assert "connect" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_missing_api_key_raises_error(self):
        """Test that missing API key raises AuthenticationError."""
        provider = AnthropicProvider(api_key=None)
        provider._api_key = None  # Ensure no env var

        with pytest.raises(AuthenticationError) as exc_info:
            _ = provider.client

        assert "API key not configured" in str(exc_info.value)
