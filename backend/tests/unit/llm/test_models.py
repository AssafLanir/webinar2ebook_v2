"""Unit tests for LLM data models and error classes.

Tests cover:
- Model instantiation and validation
- Error hierarchy and attributes
- Error classification (retryable vs non-retryable)
"""

import pytest

from src.llm.errors import (
    AuthenticationError,
    ContentFilterError,
    InvalidRequestError,
    LLMError,
    ModelNotFoundError,
    NON_RETRYABLE_ERRORS,
    ProviderError,
    RateLimitError,
    RETRYABLE_ERRORS,
    TimeoutError,
)
from src.llm.models import (
    ChatMessage,
    LLMRequest,
    LLMResponse,
    ResponseFormat,
    Usage,
)


class TestChatMessage:
    """Tests for ChatMessage model."""

    def test_basic_user_message(self):
        """Test creating a basic user message."""
        msg = ChatMessage(role="user", content="Hello, world!")
        assert msg.role == "user"
        assert msg.content == "Hello, world!"
        assert msg.name is None
        assert msg.tool_call_id is None
        assert msg.tool_calls is None

    def test_system_message(self):
        """Test creating a system message."""
        msg = ChatMessage(role="system", content="You are a helpful assistant.")
        assert msg.role == "system"
        assert msg.content == "You are a helpful assistant."

    def test_assistant_message_with_tool_calls(self):
        """Test assistant message with tool calls."""
        tool_calls = [
            {"id": "call_123", "type": "function", "function": {"name": "get_weather", "arguments": "{}"}}
        ]
        msg = ChatMessage(role="assistant", content="", tool_calls=tool_calls)
        assert msg.role == "assistant"
        assert msg.tool_calls == tool_calls

    def test_tool_message(self):
        """Test tool response message."""
        msg = ChatMessage(role="tool", content="72°F", tool_call_id="call_123")
        assert msg.role == "tool"
        assert msg.content == "72°F"
        assert msg.tool_call_id == "call_123"

    def test_multipart_content(self):
        """Test message with multipart content (for vision)."""
        content = [
            {"type": "text", "text": "What is in this image?"},
            {"type": "image_url", "image_url": {"url": "https://example.com/image.jpg"}},
        ]
        msg = ChatMessage(role="user", content=content)
        assert isinstance(msg.content, list)
        assert len(msg.content) == 2


class TestResponseFormat:
    """Tests for ResponseFormat model."""

    def test_text_format(self):
        """Test text response format."""
        fmt = ResponseFormat(type="text")
        assert fmt.type == "text"
        assert fmt.json_schema is None

    def test_json_object_format(self):
        """Test JSON object response format."""
        fmt = ResponseFormat(type="json_object")
        assert fmt.type == "json_object"

    def test_json_schema_format(self):
        """Test JSON schema response format."""
        schema = {
            "type": "object",
            "properties": {"items": {"type": "array"}},
            "required": ["items"],
        }
        fmt = ResponseFormat(type="json_schema", json_schema=schema)
        assert fmt.type == "json_schema"
        assert fmt.json_schema == schema


class TestLLMRequest:
    """Tests for LLMRequest model."""

    def test_minimal_request(self):
        """Test creating a minimal request."""
        messages = [ChatMessage(role="user", content="Hello")]
        request = LLMRequest(messages=messages, model="gpt-4o")
        assert len(request.messages) == 1
        assert request.model == "gpt-4o"
        assert request.temperature == 1.0  # default
        assert request.max_tokens is None
        assert request.response_format is None
        assert request.tools is None

    def test_full_request(self):
        """Test creating a request with all options."""
        messages = [
            ChatMessage(role="system", content="You are helpful."),
            ChatMessage(role="user", content="What is 2+2?"),
        ]
        request = LLMRequest(
            messages=messages,
            model="gpt-4o",
            temperature=0.5,
            max_tokens=1000,
            response_format=ResponseFormat(type="json_object"),
            stop=["END"],
            metadata={"user_id": "123"},
        )
        assert len(request.messages) == 2
        assert request.temperature == 0.5
        assert request.max_tokens == 1000
        assert request.response_format.type == "json_object"
        assert request.stop == ["END"]
        assert request.metadata == {"user_id": "123"}

    def test_temperature_bounds(self):
        """Test temperature validation bounds."""
        messages = [ChatMessage(role="user", content="Hi")]

        # Valid temperatures
        LLMRequest(messages=messages, model="gpt-4o", temperature=0.0)
        LLMRequest(messages=messages, model="gpt-4o", temperature=2.0)

        # Invalid temperatures
        with pytest.raises(ValueError):
            LLMRequest(messages=messages, model="gpt-4o", temperature=-0.1)
        with pytest.raises(ValueError):
            LLMRequest(messages=messages, model="gpt-4o", temperature=2.1)


class TestUsage:
    """Tests for Usage model."""

    def test_usage_creation(self):
        """Test creating usage statistics."""
        usage = Usage(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        assert usage.prompt_tokens == 100
        assert usage.completion_tokens == 50
        assert usage.total_tokens == 150


class TestLLMResponse:
    """Tests for LLMResponse model."""

    def test_text_response(self):
        """Test creating a text response."""
        response = LLMResponse(
            text="Hello! How can I help you?",
            tool_calls=None,
            finish_reason="stop",
            usage=Usage(prompt_tokens=10, completion_tokens=8, total_tokens=18),
            model="gpt-4o",
            provider="openai",
            latency_ms=500,
        )
        assert response.text == "Hello! How can I help you?"
        assert response.tool_calls is None
        assert response.finish_reason == "stop"
        assert response.provider == "openai"
        assert response.latency_ms == 500

    def test_tool_call_response(self):
        """Test creating a response with tool calls."""
        tool_calls = [
            {
                "id": "call_abc123",
                "type": "function",
                "function": {"name": "get_weather", "arguments": '{"location": "NYC"}'},
            }
        ]
        response = LLMResponse(
            text=None,
            tool_calls=tool_calls,
            finish_reason="tool_calls",
            usage=Usage(prompt_tokens=50, completion_tokens=20, total_tokens=70),
            model="gpt-4o",
            provider="openai",
            latency_ms=300,
            request_id="req_123",
        )
        assert response.text is None
        assert len(response.tool_calls) == 1
        assert response.finish_reason == "tool_calls"
        assert response.request_id == "req_123"


class TestLLMError:
    """Tests for LLMError base class."""

    def test_basic_error(self):
        """Test creating a basic LLM error."""
        error = LLMError("Something went wrong")
        assert str(error) == "Something went wrong"
        assert error.provider is None
        assert error.request_id is None

    def test_error_with_context(self):
        """Test creating an error with context."""
        error = LLMError(
            "API call failed",
            provider="openai",
            request_id="req_123",
            correlation_id="corr_456",
        )
        assert "API call failed" in str(error)
        assert "provider=openai" in str(error)
        assert "request_id=req_123" in str(error)
        assert error.correlation_id == "corr_456"


class TestRateLimitError:
    """Tests for RateLimitError."""

    def test_rate_limit_error(self):
        """Test creating a rate limit error."""
        error = RateLimitError(
            "Rate limit exceeded",
            retry_after=30.0,
            provider="openai",
        )
        assert error.retry_after == 30.0
        assert error.provider == "openai"

    def test_rate_limit_without_retry_after(self):
        """Test rate limit error without retry_after."""
        error = RateLimitError("Rate limit exceeded")
        assert error.retry_after is None


class TestErrorHierarchy:
    """Tests for error hierarchy and classification."""

    def test_authentication_error_is_llm_error(self):
        """Test AuthenticationError inheritance."""
        error = AuthenticationError("Invalid API key", provider="openai")
        assert isinstance(error, LLMError)

    def test_content_filter_error_is_llm_error(self):
        """Test ContentFilterError inheritance."""
        error = ContentFilterError("Content blocked", provider="openai")
        assert isinstance(error, LLMError)

    def test_retryable_errors(self):
        """Test that retryable errors are correctly classified."""
        assert RateLimitError in RETRYABLE_ERRORS
        assert TimeoutError in RETRYABLE_ERRORS
        assert ProviderError in RETRYABLE_ERRORS

    def test_non_retryable_errors(self):
        """Test that non-retryable errors are correctly classified."""
        assert AuthenticationError in NON_RETRYABLE_ERRORS
        assert InvalidRequestError in NON_RETRYABLE_ERRORS
        assert ContentFilterError in NON_RETRYABLE_ERRORS
        assert ModelNotFoundError in NON_RETRYABLE_ERRORS

    def test_retryable_error_instances(self):
        """Test that error instances can be checked against RETRYABLE_ERRORS."""
        rate_limit = RateLimitError("Rate limit")
        timeout = TimeoutError("Timeout")
        provider = ProviderError("Server error")

        assert isinstance(rate_limit, RETRYABLE_ERRORS)
        assert isinstance(timeout, RETRYABLE_ERRORS)
        assert isinstance(provider, RETRYABLE_ERRORS)

    def test_non_retryable_error_instances(self):
        """Test that error instances can be checked against NON_RETRYABLE_ERRORS."""
        auth = AuthenticationError("Bad key")
        invalid = InvalidRequestError("Bad request")
        content = ContentFilterError("Blocked")

        assert isinstance(auth, NON_RETRYABLE_ERRORS)
        assert isinstance(invalid, NON_RETRYABLE_ERRORS)
        assert isinstance(content, NON_RETRYABLE_ERRORS)
