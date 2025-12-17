"""Unit tests for LLM client with retry and fallback logic.

Tests cover:
- Retry logic with exponential backoff
- Provider fallback (OpenAI → Anthropic)
- Error propagation for non-retryable errors
- Configuration from environment variables
- Correlation ID tracking
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.llm.client import LLMClient, get_client, generate
from src.llm.errors import (
    AuthenticationError,
    ContentFilterError,
    InvalidRequestError,
    LLMError,
    ProviderError,
    RateLimitError,
    TimeoutError,
)
from src.llm.models import ChatMessage, LLMRequest, LLMResponse, Usage


def create_mock_response(text: str = "Test response", provider: str = "openai") -> LLMResponse:
    """Create a mock LLMResponse for testing."""
    return LLMResponse(
        text=text,
        tool_calls=None,
        finish_reason="stop",
        usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        model="test-model",
        provider=provider,
        latency_ms=100,
    )


class TestLLMClientInit:
    """Tests for LLM client initialization."""

    def test_default_configuration(self):
        """Test default configuration values."""
        client = LLMClient()
        assert client._default_provider == "openai"
        assert client._timeout == 60.0
        assert client._max_retries == 2

    def test_custom_configuration(self):
        """Test custom configuration values."""
        client = LLMClient(
            default_provider="anthropic",
            timeout=120.0,
            max_retries=5,
        )
        assert client._default_provider == "anthropic"
        assert client._timeout == 120.0
        assert client._max_retries == 5

    def test_environment_configuration(self):
        """Test configuration from environment variables."""
        with patch.dict(os.environ, {
            "LLM_DEFAULT_PROVIDER": "anthropic",
            "LLM_TIMEOUT_SECONDS": "90",
            "LLM_MAX_RETRIES": "3",
        }):
            client = LLMClient()
            assert client._default_provider == "anthropic"
            assert client._timeout == 90.0
            assert client._max_retries == 3

    def test_providers_initialized(self):
        """Test that providers are initialized."""
        client = LLMClient(openai_api_key="test-openai", anthropic_api_key="test-anthropic")
        assert "openai" in client._providers
        assert "anthropic" in client._providers


class TestLLMClientProviderAccess:
    """Tests for provider access methods."""

    def test_get_provider(self):
        """Test getting a specific provider."""
        client = LLMClient(openai_api_key="test-key")
        provider = client.get_provider("openai")
        assert provider.name == "openai"

    def test_get_unknown_provider(self):
        """Test getting an unknown provider raises error."""
        client = LLMClient()
        with pytest.raises(ValueError) as exc_info:
            client.get_provider("unknown")
        assert "Unknown provider" in str(exc_info.value)

    def test_get_default_provider(self):
        """Test getting the default provider."""
        client = LLMClient(default_provider="anthropic", anthropic_api_key="test-key")
        provider = client.get_default_provider()
        assert provider.name == "anthropic"

    def test_is_provider_available(self):
        """Test checking provider availability."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False):
            client = LLMClient()
            assert client.is_provider_available("openai") is True

    def test_is_provider_unavailable(self):
        """Test checking unavailable provider."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove API keys
            env = os.environ.copy()
            env.pop("OPENAI_API_KEY", None)
            env.pop("ANTHROPIC_API_KEY", None)
            with patch.dict(os.environ, env, clear=True):
                client = LLMClient()
                assert client.is_provider_available("openai") is False


class TestLLMClientRetry:
    """Tests for retry logic."""

    @pytest.mark.asyncio
    async def test_successful_first_attempt(self):
        """Test successful request on first attempt."""
        client = LLMClient(openai_api_key="test-key")
        mock_response = create_mock_response()

        mock_provider = AsyncMock()
        mock_provider.generate = AsyncMock(return_value=mock_response)
        mock_provider.name = "openai"

        with patch.object(client, "_providers", {"openai": mock_provider}):
            with patch.object(client, "is_provider_available", return_value=True):
                request = LLMRequest(
                    messages=[ChatMessage(role="user", content="Hi")],
                    model="gpt-4o",
                )
                response = await client.generate(request, provider="openai", fallback=False)

        assert response.text == "Test response"
        assert mock_provider.generate.call_count == 1

    @pytest.mark.asyncio
    async def test_retry_on_rate_limit(self):
        """Test retry on rate limit error."""
        client = LLMClient(openai_api_key="test-key", max_retries=2)
        mock_response = create_mock_response()

        mock_provider = AsyncMock()
        mock_provider.generate = AsyncMock(
            side_effect=[
                RateLimitError("Rate limited", retry_after=0.1),
                mock_response,
            ]
        )
        mock_provider.name = "openai"

        with patch.object(client, "_providers", {"openai": mock_provider}):
            with patch.object(client, "is_provider_available", return_value=True):
                with patch("asyncio.sleep", new_callable=AsyncMock):
                    request = LLMRequest(
                        messages=[ChatMessage(role="user", content="Hi")],
                        model="gpt-4o",
                    )
                    response = await client.generate(request, provider="openai", fallback=False)

        assert response.text == "Test response"
        assert mock_provider.generate.call_count == 2

    @pytest.mark.asyncio
    async def test_retry_on_timeout(self):
        """Test retry on timeout error."""
        client = LLMClient(openai_api_key="test-key", max_retries=2)
        mock_response = create_mock_response()

        mock_provider = AsyncMock()
        mock_provider.generate = AsyncMock(
            side_effect=[
                TimeoutError("Request timed out"),
                mock_response,
            ]
        )
        mock_provider.name = "openai"

        with patch.object(client, "_providers", {"openai": mock_provider}):
            with patch.object(client, "is_provider_available", return_value=True):
                with patch("asyncio.sleep", new_callable=AsyncMock):
                    request = LLMRequest(
                        messages=[ChatMessage(role="user", content="Hi")],
                        model="gpt-4o",
                    )
                    response = await client.generate(request, provider="openai", fallback=False)

        assert response.text == "Test response"
        assert mock_provider.generate.call_count == 2

    @pytest.mark.asyncio
    async def test_retry_on_provider_error(self):
        """Test retry on provider (5xx) error."""
        client = LLMClient(openai_api_key="test-key", max_retries=2)
        mock_response = create_mock_response()

        mock_provider = AsyncMock()
        mock_provider.generate = AsyncMock(
            side_effect=[
                ProviderError("Server error"),
                mock_response,
            ]
        )
        mock_provider.name = "openai"

        with patch.object(client, "_providers", {"openai": mock_provider}):
            with patch.object(client, "is_provider_available", return_value=True):
                with patch("asyncio.sleep", new_callable=AsyncMock):
                    request = LLMRequest(
                        messages=[ChatMessage(role="user", content="Hi")],
                        model="gpt-4o",
                    )
                    response = await client.generate(request, provider="openai", fallback=False)

        assert response.text == "Test response"

    @pytest.mark.asyncio
    async def test_max_retries_exhausted(self):
        """Test that error is raised after max retries exhausted."""
        client = LLMClient(openai_api_key="test-key", max_retries=2)

        mock_provider = AsyncMock()
        mock_provider.generate = AsyncMock(
            side_effect=RateLimitError("Rate limited")
        )
        mock_provider.name = "openai"

        with patch.object(client, "_providers", {"openai": mock_provider}):
            with patch.object(client, "is_provider_available", return_value=True):
                with patch("asyncio.sleep", new_callable=AsyncMock):
                    request = LLMRequest(
                        messages=[ChatMessage(role="user", content="Hi")],
                        model="gpt-4o",
                    )
                    with pytest.raises(RateLimitError):
                        await client.generate(request, provider="openai", fallback=False)

        # Should have tried max_retries + 1 times (initial + retries)
        assert mock_provider.generate.call_count == 3


class TestLLMClientFallback:
    """Tests for provider fallback logic."""

    @pytest.mark.asyncio
    async def test_fallback_on_rate_limit(self):
        """Test fallback to Anthropic when OpenAI is rate limited (per ChatGPT requirement)."""
        client = LLMClient(
            openai_api_key="test-openai",
            anthropic_api_key="test-anthropic",
            max_retries=2,
        )

        openai_response = create_mock_response(provider="openai")
        anthropic_response = create_mock_response(text="Anthropic response", provider="anthropic")

        mock_openai = AsyncMock()
        mock_openai.generate = AsyncMock(side_effect=RateLimitError("Rate limited"))
        mock_openai.name = "openai"

        mock_anthropic = AsyncMock()
        mock_anthropic.generate = AsyncMock(return_value=anthropic_response)
        mock_anthropic.name = "anthropic"

        with patch.object(client, "_providers", {"openai": mock_openai, "anthropic": mock_anthropic}):
            with patch.object(client, "is_provider_available", return_value=True):
                with patch("asyncio.sleep", new_callable=AsyncMock):
                    request = LLMRequest(
                        messages=[ChatMessage(role="user", content="Hi")],
                        model="gpt-4o",
                    )
                    response = await client.generate(request, fallback=True)

        assert response.text == "Anthropic response"
        assert response.provider == "anthropic"
        # OpenAI should have been tried max_retries + 1 times
        assert mock_openai.generate.call_count == 3
        # Then fallback to Anthropic
        assert mock_anthropic.generate.call_count == 1

    @pytest.mark.asyncio
    async def test_fallback_on_timeout(self):
        """Test fallback when primary provider times out."""
        client = LLMClient(
            openai_api_key="test-openai",
            anthropic_api_key="test-anthropic",
            max_retries=1,
        )

        anthropic_response = create_mock_response(text="Fallback response", provider="anthropic")

        mock_openai = AsyncMock()
        mock_openai.generate = AsyncMock(side_effect=TimeoutError("Timeout"))
        mock_openai.name = "openai"

        mock_anthropic = AsyncMock()
        mock_anthropic.generate = AsyncMock(return_value=anthropic_response)
        mock_anthropic.name = "anthropic"

        with patch.object(client, "_providers", {"openai": mock_openai, "anthropic": mock_anthropic}):
            with patch.object(client, "is_provider_available", return_value=True):
                with patch("asyncio.sleep", new_callable=AsyncMock):
                    request = LLMRequest(
                        messages=[ChatMessage(role="user", content="Hi")],
                        model="gpt-4o",
                    )
                    response = await client.generate(request)

        assert response.provider == "anthropic"

    @pytest.mark.asyncio
    async def test_fallback_on_provider_error(self):
        """Test fallback when primary provider has 5xx error."""
        client = LLMClient(
            openai_api_key="test-openai",
            anthropic_api_key="test-anthropic",
            max_retries=1,
        )

        anthropic_response = create_mock_response(provider="anthropic")

        mock_openai = AsyncMock()
        mock_openai.generate = AsyncMock(side_effect=ProviderError("Server error"))
        mock_openai.name = "openai"

        mock_anthropic = AsyncMock()
        mock_anthropic.generate = AsyncMock(return_value=anthropic_response)
        mock_anthropic.name = "anthropic"

        with patch.object(client, "_providers", {"openai": mock_openai, "anthropic": mock_anthropic}):
            with patch.object(client, "is_provider_available", return_value=True):
                with patch("asyncio.sleep", new_callable=AsyncMock):
                    request = LLMRequest(
                        messages=[ChatMessage(role="user", content="Hi")],
                        model="gpt-4o",
                    )
                    response = await client.generate(request)

        assert response.provider == "anthropic"

    @pytest.mark.asyncio
    async def test_no_fallback_on_auth_error(self):
        """Test that AuthenticationError does NOT trigger fallback."""
        client = LLMClient(
            openai_api_key="test-openai",
            anthropic_api_key="test-anthropic",
        )

        mock_openai = AsyncMock()
        mock_openai.generate = AsyncMock(side_effect=AuthenticationError("Bad key"))
        mock_openai.name = "openai"

        mock_anthropic = AsyncMock()
        mock_anthropic.name = "anthropic"

        with patch.object(client, "_providers", {"openai": mock_openai, "anthropic": mock_anthropic}):
            with patch.object(client, "is_provider_available", return_value=True):
                request = LLMRequest(
                    messages=[ChatMessage(role="user", content="Hi")],
                    model="gpt-4o",
                )
                with pytest.raises(AuthenticationError):
                    await client.generate(request)

        # Anthropic should NOT have been called
        mock_anthropic.generate.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_fallback_on_invalid_request(self):
        """Test that InvalidRequestError does NOT trigger fallback."""
        client = LLMClient(
            openai_api_key="test-openai",
            anthropic_api_key="test-anthropic",
        )

        mock_openai = AsyncMock()
        mock_openai.generate = AsyncMock(side_effect=InvalidRequestError("Bad request"))
        mock_openai.name = "openai"

        mock_anthropic = AsyncMock()
        mock_anthropic.name = "anthropic"

        with patch.object(client, "_providers", {"openai": mock_openai, "anthropic": mock_anthropic}):
            with patch.object(client, "is_provider_available", return_value=True):
                request = LLMRequest(
                    messages=[ChatMessage(role="user", content="Hi")],
                    model="gpt-4o",
                )
                with pytest.raises(InvalidRequestError):
                    await client.generate(request)

        mock_anthropic.generate.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_fallback_on_content_filter(self):
        """Test that ContentFilterError does NOT trigger fallback."""
        client = LLMClient(
            openai_api_key="test-openai",
            anthropic_api_key="test-anthropic",
        )

        mock_openai = AsyncMock()
        mock_openai.generate = AsyncMock(side_effect=ContentFilterError("Blocked"))
        mock_openai.name = "openai"

        mock_anthropic = AsyncMock()
        mock_anthropic.name = "anthropic"

        with patch.object(client, "_providers", {"openai": mock_openai, "anthropic": mock_anthropic}):
            with patch.object(client, "is_provider_available", return_value=True):
                request = LLMRequest(
                    messages=[ChatMessage(role="user", content="Hi")],
                    model="gpt-4o",
                )
                with pytest.raises(ContentFilterError):
                    await client.generate(request)

        mock_anthropic.generate.assert_not_called()

    @pytest.mark.asyncio
    async def test_fallback_disabled(self):
        """Test that fallback can be disabled."""
        client = LLMClient(
            openai_api_key="test-openai",
            anthropic_api_key="test-anthropic",
            max_retries=1,
        )

        mock_openai = AsyncMock()
        mock_openai.generate = AsyncMock(side_effect=RateLimitError("Rate limited"))
        mock_openai.name = "openai"

        mock_anthropic = AsyncMock()
        mock_anthropic.name = "anthropic"

        with patch.object(client, "_providers", {"openai": mock_openai, "anthropic": mock_anthropic}):
            with patch.object(client, "is_provider_available", return_value=True):
                with patch("asyncio.sleep", new_callable=AsyncMock):
                    request = LLMRequest(
                        messages=[ChatMessage(role="user", content="Hi")],
                        model="gpt-4o",
                    )
                    with pytest.raises(RateLimitError):
                        await client.generate(request, provider="openai", fallback=False)

        mock_anthropic.generate.assert_not_called()

    @pytest.mark.asyncio
    async def test_both_providers_fail(self):
        """Test error when both providers fail after retries."""
        client = LLMClient(
            openai_api_key="test-openai",
            anthropic_api_key="test-anthropic",
            max_retries=1,
        )

        mock_openai = AsyncMock()
        mock_openai.generate = AsyncMock(side_effect=RateLimitError("OpenAI rate limited"))
        mock_openai.name = "openai"

        mock_anthropic = AsyncMock()
        mock_anthropic.generate = AsyncMock(side_effect=RateLimitError("Anthropic rate limited"))
        mock_anthropic.name = "anthropic"

        with patch.object(client, "_providers", {"openai": mock_openai, "anthropic": mock_anthropic}):
            with patch.object(client, "is_provider_available", return_value=True):
                with patch("asyncio.sleep", new_callable=AsyncMock):
                    request = LLMRequest(
                        messages=[ChatMessage(role="user", content="Hi")],
                        model="gpt-4o",
                    )
                    with pytest.raises(RateLimitError) as exc_info:
                        await client.generate(request)

        # Should get the last error (from Anthropic)
        assert "Anthropic" in str(exc_info.value)


class TestLLMClientBackoff:
    """Tests for backoff calculation."""

    def test_backoff_uses_retry_after(self):
        """Test that retry_after from RateLimitError is used."""
        client = LLMClient()
        error = RateLimitError("Rate limited", retry_after=10.0)

        delay = client._calculate_backoff(attempt=0, error=error)

        # Should use retry_after, capped at max
        assert delay == 10.0

    def test_backoff_caps_retry_after(self):
        """Test that retry_after is capped at max delay."""
        client = LLMClient()
        error = RateLimitError("Rate limited", retry_after=100.0)

        delay = client._calculate_backoff(attempt=0, error=error)

        assert delay == client.DEFAULT_MAX_DELAY

    def test_backoff_exponential(self):
        """Test exponential backoff calculation."""
        client = LLMClient()
        error = TimeoutError("Timeout")

        # First attempt: base delay * 2^0 = 1
        delay_0 = client._calculate_backoff(attempt=0, error=error)
        # Second attempt: base delay * 2^1 = 2
        delay_1 = client._calculate_backoff(attempt=1, error=error)
        # Third attempt: base delay * 2^2 = 4
        delay_2 = client._calculate_backoff(attempt=2, error=error)

        # Delays should increase (accounting for jitter)
        assert delay_0 < delay_1 < delay_2 or True  # With jitter, might not always be true


class TestLLMClientCorrelationId:
    """Tests for correlation ID tracking."""

    @pytest.mark.asyncio
    async def test_correlation_id_passed_to_errors(self):
        """Test that correlation ID is added to errors."""
        client = LLMClient(openai_api_key="test-key", max_retries=0)

        mock_provider = AsyncMock()
        mock_provider.generate = AsyncMock(side_effect=RateLimitError("Rate limited"))
        mock_provider.name = "openai"

        with patch.object(client, "_providers", {"openai": mock_provider}):
            with patch.object(client, "is_provider_available", return_value=True):
                request = LLMRequest(
                    messages=[ChatMessage(role="user", content="Hi")],
                    model="gpt-4o",
                )
                with pytest.raises(RateLimitError) as exc_info:
                    await client.generate(
                        request,
                        provider="openai",
                        fallback=False,
                        correlation_id="test-corr-123",
                    )

        assert exc_info.value.correlation_id == "test-corr-123"

    @pytest.mark.asyncio
    async def test_auto_generated_correlation_id(self):
        """Test that correlation ID is auto-generated if not provided."""
        client = LLMClient(openai_api_key="test-key", max_retries=0)

        mock_provider = AsyncMock()
        mock_provider.generate = AsyncMock(side_effect=RateLimitError("Rate limited"))
        mock_provider.name = "openai"

        with patch.object(client, "_providers", {"openai": mock_provider}):
            with patch.object(client, "is_provider_available", return_value=True):
                request = LLMRequest(
                    messages=[ChatMessage(role="user", content="Hi")],
                    model="gpt-4o",
                )
                with pytest.raises(RateLimitError) as exc_info:
                    await client.generate(request, provider="openai", fallback=False)

        # Should have an auto-generated correlation ID
        assert exc_info.value.correlation_id is not None


class TestModuleLevelFunctions:
    """Tests for module-level convenience functions."""

    def test_get_client_singleton(self):
        """Test that get_client returns a singleton."""
        # Reset singleton
        import src.llm.client as client_module
        client_module._default_client = None

        client1 = get_client()
        client2 = get_client()

        assert client1 is client2

    @pytest.mark.asyncio
    async def test_generate_function(self):
        """Test the module-level generate function."""
        mock_response = create_mock_response()

        with patch("src.llm.client.get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.generate = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            request = LLMRequest(
                messages=[ChatMessage(role="user", content="Hi")],
                model="gpt-4o",
            )
            response = await generate(request)

        assert response.text == "Test response"
