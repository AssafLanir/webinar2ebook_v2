"""High-level LLM client with retry and fallback logic.

Provides automatic retry with exponential backoff and provider fallback
for resilient LLM operations.
"""

import asyncio
import logging
import os
import random
import uuid
from typing import Any

from .errors import (
    AuthenticationError,
    ContentFilterError,
    InvalidRequestError,
    LLMError,
    ModelNotFoundError,
    RateLimitError,
    RETRYABLE_ERRORS,
)
from .models import LLMRequest, LLMResponse
from .providers.anthropic import AnthropicProvider
from .providers.base import LLMProvider
from .providers.openai import OpenAIProvider

logger = logging.getLogger(__name__)


class LLMClient:
    """High-level LLM client with retry and fallback.

    Features:
    - Automatic retry with exponential backoff + jitter
    - Provider fallback (OpenAI → Anthropic)
    - Correlation ID tracking across attempts
    - Configurable via environment variables

    Configuration (env vars):
    - LLM_DEFAULT_PROVIDER: Default provider (default: "openai")
    - LLM_TIMEOUT_SECONDS: Request timeout (default: 60)
    - LLM_MAX_RETRIES: Max retries per provider (default: 2)
    """

    # Default configuration
    DEFAULT_PROVIDER = "openai"
    DEFAULT_TIMEOUT = 60.0
    DEFAULT_MAX_RETRIES = 2
    DEFAULT_BASE_DELAY = 1.0  # Base delay for exponential backoff
    DEFAULT_MAX_DELAY = 30.0  # Maximum delay between retries

    def __init__(
        self,
        default_provider: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
        openai_api_key: str | None = None,
        anthropic_api_key: str | None = None,
    ):
        """Initialize LLM client.

        Args:
            default_provider: Primary provider name. Defaults to LLM_DEFAULT_PROVIDER env var.
            timeout: Request timeout in seconds. Defaults to LLM_TIMEOUT_SECONDS env var.
            max_retries: Max retries per provider. Defaults to LLM_MAX_RETRIES env var.
            openai_api_key: OpenAI API key. Defaults to OPENAI_API_KEY env var.
            anthropic_api_key: Anthropic API key. Defaults to ANTHROPIC_API_KEY env var.
        """
        # Load configuration from environment or use provided values
        self._default_provider = (
            default_provider
            or os.environ.get("LLM_DEFAULT_PROVIDER", self.DEFAULT_PROVIDER)
        )
        self._timeout = (
            timeout
            if timeout is not None
            else float(os.environ.get("LLM_TIMEOUT_SECONDS", self.DEFAULT_TIMEOUT))
        )
        self._max_retries = (
            max_retries
            if max_retries is not None
            else int(os.environ.get("LLM_MAX_RETRIES", self.DEFAULT_MAX_RETRIES))
        )

        # Initialize providers
        self._providers: dict[str, LLMProvider] = {
            "openai": OpenAIProvider(api_key=openai_api_key, timeout=self._timeout),
            "anthropic": AnthropicProvider(api_key=anthropic_api_key, timeout=self._timeout),
        }

        # Provider fallback order
        self._fallback_order = ["openai", "anthropic"]

    def get_provider(self, name: str) -> LLMProvider:
        """Get a specific provider by name.

        Args:
            name: Provider name ("openai" or "anthropic").

        Returns:
            LLMProvider instance.

        Raises:
            ValueError: If provider name is not recognized.
        """
        if name not in self._providers:
            raise ValueError(f"Unknown provider: {name}. Available: {list(self._providers.keys())}")
        return self._providers[name]

    def get_default_provider(self) -> LLMProvider:
        """Get the default provider."""
        return self.get_provider(self._default_provider)

    def is_provider_available(self, name: str) -> bool:
        """Check if a provider is configured and available.

        Args:
            name: Provider name.

        Returns:
            True if the provider has valid configuration.
        """
        if name not in self._providers:
            return False

        # Check if API key is configured
        if name == "openai":
            return bool(os.environ.get("OPENAI_API_KEY"))
        if name == "anthropic":
            return bool(os.environ.get("ANTHROPIC_API_KEY"))

        return False

    async def generate(
        self,
        request: LLMRequest,
        provider: str | None = None,
        fallback: bool = True,
        correlation_id: str | None = None,
    ) -> LLMResponse:
        """Generate a completion with automatic retry and fallback.

        Args:
            request: LLM request to send.
            provider: Specific provider to use. Defaults to default provider.
            fallback: Whether to fallback to other providers on failure.
            correlation_id: Optional ID for tracking across retry attempts.

        Returns:
            LLM response from the successful provider.

        Raises:
            LLMError: If all providers fail after retries.
        """
        correlation_id = correlation_id or str(uuid.uuid4())

        # Determine provider order
        if provider:
            providers_to_try = [provider]
            if fallback:
                # Add other providers as fallbacks
                providers_to_try.extend(
                    p for p in self._fallback_order if p != provider
                )
        else:
            providers_to_try = self._fallback_order.copy()

        last_error: LLMError | None = None

        for provider_name in providers_to_try:
            if not self.is_provider_available(provider_name):
                logger.debug(
                    "Provider %s not available, skipping",
                    provider_name,
                    extra={"correlation_id": correlation_id},
                )
                continue

            try:
                response = await self._generate_with_retry(
                    request=request,
                    provider_name=provider_name,
                    correlation_id=correlation_id,
                )
                return response

            except RETRYABLE_ERRORS as e:
                # Retryable error - log and try next provider
                last_error = e
                logger.warning(
                    "Provider %s failed with retryable error: %s. Trying fallback.",
                    provider_name,
                    str(e),
                    extra={
                        "correlation_id": correlation_id,
                        "provider": provider_name,
                        "error_type": type(e).__name__,
                    },
                )
                if not fallback:
                    raise

            except (AuthenticationError, InvalidRequestError, ContentFilterError, ModelNotFoundError) as e:
                # Non-retryable error - don't try fallback for these
                logger.error(
                    "Provider %s failed with non-retryable error: %s",
                    provider_name,
                    str(e),
                    extra={
                        "correlation_id": correlation_id,
                        "provider": provider_name,
                        "error_type": type(e).__name__,
                    },
                )
                raise

        # All providers exhausted
        if last_error:
            raise last_error

        raise LLMError(
            "No providers available",
            correlation_id=correlation_id,
        )

    async def _generate_with_retry(
        self,
        request: LLMRequest,
        provider_name: str,
        correlation_id: str,
    ) -> LLMResponse:
        """Generate with retry logic for a single provider.

        Args:
            request: LLM request to send.
            provider_name: Provider to use.
            correlation_id: Tracking ID.

        Returns:
            LLM response.

        Raises:
            LLMError: After all retries exhausted.
        """
        provider = self.get_provider(provider_name)
        last_error: Exception | None = None

        for attempt in range(self._max_retries + 1):
            try:
                logger.debug(
                    "Attempting request to %s (attempt %d/%d)",
                    provider_name,
                    attempt + 1,
                    self._max_retries + 1,
                    extra={
                        "correlation_id": correlation_id,
                        "provider": provider_name,
                        "attempt": attempt + 1,
                    },
                )

                response = await provider.generate(request)

                # Log successful request
                logger.info(
                    "LLM request succeeded",
                    extra={
                        "correlation_id": correlation_id,
                        "provider": response.provider,
                        "model": response.model,
                        "latency_ms": response.latency_ms,
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "finish_reason": response.finish_reason,
                    },
                )

                return response

            except RETRYABLE_ERRORS as e:
                last_error = e
                e.correlation_id = correlation_id

                # Log retry attempt
                logger.warning(
                    "Retryable error on attempt %d/%d: %s",
                    attempt + 1,
                    self._max_retries + 1,
                    str(e),
                    extra={
                        "correlation_id": correlation_id,
                        "provider": provider_name,
                        "attempt": attempt + 1,
                        "error_type": type(e).__name__,
                    },
                )

                # If more retries left, wait with exponential backoff
                if attempt < self._max_retries:
                    delay = self._calculate_backoff(attempt, e)
                    logger.debug(
                        "Waiting %.2f seconds before retry",
                        delay,
                        extra={"correlation_id": correlation_id},
                    )
                    await asyncio.sleep(delay)

            except LLMError:
                # Non-retryable errors pass through immediately
                raise

        # All retries exhausted
        if last_error:
            raise last_error

        raise LLMError(
            f"Provider {provider_name} failed after {self._max_retries + 1} attempts",
            provider=provider_name,
            correlation_id=correlation_id,
        )

    def _calculate_backoff(self, attempt: int, error: Exception) -> float:
        """Calculate backoff delay with exponential growth and jitter.

        Args:
            attempt: Current attempt number (0-indexed).
            error: The error that triggered the retry.

        Returns:
            Delay in seconds.
        """
        # Check for retry-after header
        if isinstance(error, RateLimitError) and error.retry_after:
            return min(error.retry_after, self.DEFAULT_MAX_DELAY)

        # Exponential backoff: base * 2^attempt
        base_delay = self.DEFAULT_BASE_DELAY * (2 ** attempt)

        # Add jitter (±25%)
        jitter = base_delay * 0.25 * (2 * random.random() - 1)

        # Cap at max delay
        delay = min(base_delay + jitter, self.DEFAULT_MAX_DELAY)

        return delay


# Convenience functions for module-level access
_default_client: LLMClient | None = None


def get_client() -> LLMClient:
    """Get the default LLM client singleton."""
    global _default_client
    if _default_client is None:
        _default_client = LLMClient()
    return _default_client


def get_provider(name: str) -> LLMProvider:
    """Get a specific provider by name."""
    return get_client().get_provider(name)


def get_default_provider() -> LLMProvider:
    """Get the default provider."""
    return get_client().get_default_provider()


def is_provider_available(name: str) -> bool:
    """Check if a provider is available."""
    return get_client().is_provider_available(name)


async def generate(
    request: LLMRequest,
    provider: str | None = None,
    fallback: bool = True,
    correlation_id: str | None = None,
) -> LLMResponse:
    """Generate a completion using the default client."""
    return await get_client().generate(
        request=request,
        provider=provider,
        fallback=fallback,
        correlation_id=correlation_id,
    )
