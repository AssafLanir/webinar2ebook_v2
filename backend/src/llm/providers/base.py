"""Abstract base class for LLM providers.

Defines the interface that all LLM providers must implement.
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

from ..models import LLMRequest, LLMResponse


class LLMProvider(ABC):
    """Base interface for LLM providers.

    All providers (OpenAI, Anthropic, etc.) must implement this interface
    to ensure consistent behavior across the application.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier: 'openai', 'anthropic', etc."""
        ...

    @abstractmethod
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Send a completion request and return the response.

        Args:
            request: Vendor-neutral LLM request.

        Returns:
            Vendor-neutral LLM response.

        Raises:
            AuthenticationError: Invalid or missing API key.
            RateLimitError: Rate limit exceeded (retryable).
            TimeoutError: Request timed out (retryable).
            InvalidRequestError: Malformed request (non-retryable).
            ContentFilterError: Response blocked by safety filters.
            ProviderError: Provider-side failure (retryable).
        """
        ...

    @abstractmethod
    def supports(self, feature: str) -> bool:
        """Check if provider supports a capability.

        Args:
            feature: Feature name. Supported values:
                - 'json_schema': Structured outputs with JSON Schema
                - 'json_object': Basic JSON mode
                - 'tools': Function/tool calling
                - 'vision': Image inputs
                - 'streaming': Streaming responses
                - 'system_message': Dedicated system role

        Returns:
            True if the feature is supported.
        """
        ...

    async def stream(self, request: LLMRequest) -> AsyncIterator[dict[str, Any]]:
        """Stream response chunks.

        Args:
            request: Vendor-neutral LLM request.

        Yields:
            Response chunks as they arrive.

        Raises:
            NotImplementedError: If streaming is not supported.
        """
        raise NotImplementedError("Streaming not supported by this provider")
        # Make this an async generator
        yield {}  # pragma: no cover
