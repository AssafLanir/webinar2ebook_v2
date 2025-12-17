"""LLM error hierarchy.

Custom exceptions for LLM operations with provider context.
Used for retry logic and user-friendly error messages.
"""


class LLMError(Exception):
    """Base exception for LLM operations."""

    def __init__(
        self,
        message: str,
        provider: str | None = None,
        request_id: str | None = None,
        correlation_id: str | None = None,
    ):
        super().__init__(message)
        self.provider = provider
        self.request_id = request_id
        self.correlation_id = correlation_id

    def __str__(self) -> str:
        parts = [super().__str__()]
        if self.provider:
            parts.append(f"provider={self.provider}")
        if self.request_id:
            parts.append(f"request_id={self.request_id}")
        return " ".join(parts)


class AuthenticationError(LLMError):
    """401/403 - Invalid or missing API key.

    Non-retryable. Check API key configuration.
    """

    pass


class RateLimitError(LLMError):
    """429 - Rate limit exceeded.

    Retryable with exponential backoff. Respect retry_after if provided.
    """

    def __init__(
        self,
        message: str,
        retry_after: float | None = None,
        provider: str | None = None,
        request_id: str | None = None,
        correlation_id: str | None = None,
    ):
        super().__init__(message, provider, request_id, correlation_id)
        self.retry_after = retry_after


class TimeoutError(LLMError):
    """Request exceeded timeout threshold.

    Retryable once with potentially increased timeout.
    """

    pass


class InvalidRequestError(LLMError):
    """400 - Malformed request.

    Non-retryable. Fix the request parameters.
    Examples: bad schema, too many tokens, invalid model.
    """

    pass


class ContentFilterError(LLMError):
    """Response blocked by safety filters.

    Non-retryable. Content was flagged by provider's safety system.
    """

    pass


class ProviderError(LLMError):
    """500/502/503 - Provider-side failure.

    Retryable. May be transient server issues.
    """

    pass


class ModelNotFoundError(LLMError):
    """Model identifier not recognized.

    Non-retryable. Check model name.
    """

    pass


# Error classification for retry logic
RETRYABLE_ERRORS = (RateLimitError, TimeoutError, ProviderError)
NON_RETRYABLE_ERRORS = (AuthenticationError, InvalidRequestError, ContentFilterError, ModelNotFoundError)
