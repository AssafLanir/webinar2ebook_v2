"""OpenAI provider implementation.

Implements the LLMProvider interface for OpenAI's Chat Completions API.
Supports structured outputs via response_format.json_schema.
"""

import os
import time
from typing import Any

from openai import AsyncOpenAI, APIConnectionError, APIStatusError, APITimeoutError

from ..errors import (
    AuthenticationError,
    ContentFilterError,
    InvalidRequestError,
    LLMError,
    ModelNotFoundError,
    ProviderError,
    RateLimitError,
    TimeoutError,
)
from ..models import ChatMessage, LLMRequest, LLMResponse, Usage
from .base import LLMProvider


class OpenAIProvider(LLMProvider):
    """OpenAI Chat Completions API provider.

    Supports:
    - Structured outputs via response_format.json_schema
    - Function/tool calling
    - Vision (image inputs)
    - Streaming
    """

    # Supported capabilities
    SUPPORTED_FEATURES = {
        "json_schema",
        "json_object",
        "tools",
        "vision",
        "streaming",
        "system_message",
    }

    def __init__(
        self,
        api_key: str | None = None,
        timeout: float = 60.0,
        default_model: str = "gpt-4o",
    ):
        """Initialize OpenAI provider.

        Args:
            api_key: OpenAI API key. Defaults to OPENAI_API_KEY env var.
            timeout: Request timeout in seconds.
            default_model: Default model to use if not specified in request.
        """
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self._timeout = timeout
        self._default_model = default_model
        self._client: AsyncOpenAI | None = None

    @property
    def name(self) -> str:
        """Provider identifier."""
        return "openai"

    @property
    def client(self) -> AsyncOpenAI:
        """Lazy-initialized OpenAI client."""
        if self._client is None:
            if not self._api_key:
                raise AuthenticationError(
                    "OpenAI API key not configured. Set OPENAI_API_KEY environment variable.",
                    provider=self.name,
                )
            self._client = AsyncOpenAI(api_key=self._api_key, timeout=self._timeout)
        return self._client

    def supports(self, feature: str) -> bool:
        """Check if feature is supported."""
        return feature in self.SUPPORTED_FEATURES

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Send a completion request to OpenAI.

        Args:
            request: Vendor-neutral LLM request.

        Returns:
            Vendor-neutral LLM response.

        Raises:
            Various LLMError subclasses based on the error type.
        """
        start_time = time.perf_counter()

        # Build OpenAI-specific request
        openai_request = self._build_request(request)

        try:
            response = await self.client.chat.completions.create(**openai_request)
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            return self._parse_response(response, latency_ms)

        except APITimeoutError as e:
            raise TimeoutError(
                f"OpenAI request timed out after {self._timeout}s",
                provider=self.name,
            ) from e

        except APIConnectionError as e:
            raise ProviderError(
                f"Failed to connect to OpenAI: {e}",
                provider=self.name,
            ) from e

        except APIStatusError as e:
            self._handle_api_error(e)

    def _build_request(self, request: LLMRequest) -> dict[str, Any]:
        """Convert LLMRequest to OpenAI API format."""
        # Convert messages
        messages = []
        for msg in request.messages:
            openai_msg: dict[str, Any] = {
                "role": msg.role,
                "content": msg.content,
            }
            if msg.name:
                openai_msg["name"] = msg.name
            if msg.tool_call_id:
                openai_msg["tool_call_id"] = msg.tool_call_id
            if msg.tool_calls:
                openai_msg["tool_calls"] = msg.tool_calls
            messages.append(openai_msg)

        openai_request: dict[str, Any] = {
            "model": request.model or self._default_model,
            "messages": messages,
            "temperature": request.temperature,
        }

        # Optional parameters
        if request.max_tokens:
            openai_request["max_tokens"] = request.max_tokens

        if request.response_format:
            if request.response_format.type == "json_schema":
                openai_request["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "response",
                        "strict": True,
                        "schema": request.response_format.json_schema,
                    },
                }
            elif request.response_format.type == "json_object":
                openai_request["response_format"] = {"type": "json_object"}
            # "text" is the default, no need to set

        if request.tools:
            openai_request["tools"] = request.tools

        if request.tool_choice:
            openai_request["tool_choice"] = request.tool_choice

        if request.stop:
            openai_request["stop"] = request.stop

        return openai_request

    def _parse_response(self, response: Any, latency_ms: int) -> LLMResponse:
        """Convert OpenAI response to LLMResponse."""
        choice = response.choices[0]
        message = choice.message

        # Extract tool calls if present
        tool_calls = None
        if message.tool_calls:
            tool_calls = [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in message.tool_calls
            ]

        return LLMResponse(
            text=message.content,
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason or "stop",
            usage=Usage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
            ),
            model=response.model,
            provider=self.name,
            latency_ms=latency_ms,
            request_id=response.id,
            raw=response.model_dump() if hasattr(response, "model_dump") else None,
        )

    def _handle_api_error(self, error: APIStatusError) -> None:
        """Convert OpenAI API errors to LLMError types."""
        status_code = error.status_code
        message = str(error.message) if hasattr(error, "message") else str(error)
        request_id = getattr(error, "request_id", None)

        if status_code == 401:
            raise AuthenticationError(
                "Invalid OpenAI API key",
                provider=self.name,
                request_id=request_id,
            ) from error

        if status_code == 403:
            raise AuthenticationError(
                f"OpenAI access denied: {message}",
                provider=self.name,
                request_id=request_id,
            ) from error

        if status_code == 404:
            raise ModelNotFoundError(
                f"Model not found: {message}",
                provider=self.name,
                request_id=request_id,
            ) from error

        if status_code == 429:
            # Try to extract retry-after header
            retry_after = None
            if hasattr(error, "response") and error.response:
                retry_after_str = error.response.headers.get("retry-after")
                if retry_after_str:
                    try:
                        retry_after = float(retry_after_str)
                    except ValueError:
                        pass

            raise RateLimitError(
                f"OpenAI rate limit exceeded: {message}",
                retry_after=retry_after,
                provider=self.name,
                request_id=request_id,
            ) from error

        if status_code == 400:
            # Check for content filter in error message
            if "content_filter" in message.lower() or "safety" in message.lower():
                raise ContentFilterError(
                    f"Content blocked by OpenAI safety filters: {message}",
                    provider=self.name,
                    request_id=request_id,
                ) from error

            raise InvalidRequestError(
                f"Invalid request to OpenAI: {message}",
                provider=self.name,
                request_id=request_id,
            ) from error

        if status_code >= 500:
            raise ProviderError(
                f"OpenAI server error ({status_code}): {message}",
                provider=self.name,
                request_id=request_id,
            ) from error

        # Unknown error
        raise LLMError(
            f"OpenAI error ({status_code}): {message}",
            provider=self.name,
            request_id=request_id,
        ) from error
