"""Anthropic provider implementation.

Implements the LLMProvider interface for Anthropic's Messages API.
Supports structured outputs via tool_use pattern (since Anthropic doesn't have native json_schema).
"""

import json
import os
import time
from typing import Any

from anthropic import (
    AsyncAnthropic,
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
)

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
from ..models import LLMRequest, LLMResponse, Usage
from .base import LLMProvider


class AnthropicProvider(LLMProvider):
    """Anthropic Messages API provider.

    Supports:
    - Structured outputs via tool_use pattern
    - Function/tool calling
    - Vision (image inputs)
    - Streaming

    Note: Anthropic doesn't have native json_schema mode, but we achieve
    similar results using tool_use with a "respond" tool that has the schema.
    """

    # Supported capabilities
    SUPPORTED_FEATURES = {
        "json_schema",  # Via tool_use pattern
        "tools",
        "vision",
        "streaming",
        "system_message",
    }

    def __init__(
        self,
        api_key: str | None = None,
        timeout: float = 60.0,
        default_model: str = "claude-sonnet-4-5-20250929",
    ):
        """Initialize Anthropic provider.

        Args:
            api_key: Anthropic API key. Defaults to ANTHROPIC_API_KEY env var.
            timeout: Request timeout in seconds.
            default_model: Default model to use if not specified in request.
        """
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self._timeout = timeout
        self._default_model = default_model
        self._client: AsyncAnthropic | None = None

    @property
    def name(self) -> str:
        """Provider identifier."""
        return "anthropic"

    @property
    def client(self) -> AsyncAnthropic:
        """Lazy-initialized Anthropic client."""
        if self._client is None:
            if not self._api_key:
                raise AuthenticationError(
                    "Anthropic API key not configured. Set ANTHROPIC_API_KEY environment variable.",
                    provider=self.name,
                )
            self._client = AsyncAnthropic(api_key=self._api_key, timeout=self._timeout)
        return self._client

    def supports(self, feature: str) -> bool:
        """Check if feature is supported."""
        return feature in self.SUPPORTED_FEATURES

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Send a completion request to Anthropic.

        Args:
            request: Vendor-neutral LLM request.

        Returns:
            Vendor-neutral LLM response.

        Raises:
            Various LLMError subclasses based on the error type.
        """
        start_time = time.perf_counter()

        # Build Anthropic-specific request
        anthropic_request = self._build_request(request)

        try:
            response = await self.client.messages.create(**anthropic_request)
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            return self._parse_response(response, latency_ms, request)

        except APITimeoutError as e:
            raise TimeoutError(
                f"Anthropic request timed out after {self._timeout}s",
                provider=self.name,
            ) from e

        except APIConnectionError as e:
            raise ProviderError(
                f"Failed to connect to Anthropic: {e}",
                provider=self.name,
            ) from e

        except APIStatusError as e:
            self._handle_api_error(e)

    def _build_request(self, request: LLMRequest) -> dict[str, Any]:
        """Convert LLMRequest to Anthropic API format."""
        # Separate system message from conversation messages
        system_content = None
        messages = []

        for msg in request.messages:
            if msg.role == "system":
                # Anthropic takes system as a top-level parameter
                if isinstance(msg.content, str):
                    system_content = msg.content
                else:
                    # Handle list content (shouldn't happen for system, but be safe)
                    system_content = str(msg.content)
            elif msg.role == "tool":
                # Convert tool response to Anthropic format
                messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": msg.tool_call_id,
                        "content": msg.content if isinstance(msg.content, str) else json.dumps(msg.content),
                    }],
                })
            else:
                # user or assistant messages
                anthropic_msg: dict[str, Any] = {
                    "role": msg.role,
                    "content": msg.content,
                }
                messages.append(anthropic_msg)

        anthropic_request: dict[str, Any] = {
            "model": request.model or self._default_model,
            "messages": messages,
            "max_tokens": request.max_tokens or 4096,
        }

        if system_content:
            anthropic_request["system"] = system_content

        # Handle temperature (Anthropic uses 0-1 range, we use 0-2)
        # Scale down if > 1
        temp = request.temperature
        if temp > 1.0:
            temp = 1.0
        anthropic_request["temperature"] = temp

        # Handle structured output via tool_use pattern
        if request.response_format and request.response_format.type == "json_schema":
            schema = request.response_format.json_schema
            # Create a tool that forces structured output
            anthropic_request["tools"] = [{
                "name": "respond_with_json",
                "description": "Respond with structured JSON data matching the required schema.",
                "input_schema": schema,
            }]
            # Force the model to use this tool
            anthropic_request["tool_choice"] = {"type": "tool", "name": "respond_with_json"}

        elif request.tools:
            # Convert standard tools to Anthropic format
            anthropic_request["tools"] = [
                {
                    "name": tool["function"]["name"],
                    "description": tool["function"].get("description", ""),
                    "input_schema": tool["function"]["parameters"],
                }
                for tool in request.tools
                if tool.get("type") == "function"
            ]

            if request.tool_choice:
                if isinstance(request.tool_choice, str):
                    if request.tool_choice == "auto":
                        anthropic_request["tool_choice"] = {"type": "auto"}
                    elif request.tool_choice == "required":
                        anthropic_request["tool_choice"] = {"type": "any"}
                    elif request.tool_choice == "none":
                        # Don't set tool_choice, just don't pass tools
                        del anthropic_request["tools"]
                else:
                    # Specific tool choice
                    anthropic_request["tool_choice"] = {
                        "type": "tool",
                        "name": request.tool_choice.get("function", {}).get("name"),
                    }

        if request.stop:
            anthropic_request["stop_sequences"] = request.stop

        return anthropic_request

    def _parse_response(
        self, response: Any, latency_ms: int, request: LLMRequest
    ) -> LLMResponse:
        """Convert Anthropic response to LLMResponse."""
        # Extract text and tool calls from content blocks
        text_parts = []
        tool_calls = []

        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                # Check if this is our structured output tool
                if (
                    block.name == "respond_with_json"
                    and request.response_format
                    and request.response_format.type == "json_schema"
                ):
                    # Return the tool input as the text response
                    text_parts.append(json.dumps(block.input))
                else:
                    tool_calls.append({
                        "id": block.id,
                        "type": "function",
                        "function": {
                            "name": block.name,
                            "arguments": json.dumps(block.input),
                        },
                    })

        text = "\n".join(text_parts) if text_parts else None

        # Map Anthropic stop reasons to our format
        finish_reason_map = {
            "end_turn": "stop",
            "max_tokens": "length",
            "stop_sequence": "stop",
            "tool_use": "tool_calls",
        }
        finish_reason = finish_reason_map.get(response.stop_reason, response.stop_reason)

        return LLMResponse(
            text=text,
            tool_calls=tool_calls if tool_calls else None,
            finish_reason=finish_reason,
            usage=Usage(
                prompt_tokens=response.usage.input_tokens,
                completion_tokens=response.usage.output_tokens,
                total_tokens=response.usage.input_tokens + response.usage.output_tokens,
            ),
            model=response.model,
            provider=self.name,
            latency_ms=latency_ms,
            request_id=response.id,
            raw=response.model_dump() if hasattr(response, "model_dump") else None,
        )

    def _handle_api_error(self, error: APIStatusError) -> None:
        """Convert Anthropic API errors to LLMError types."""
        status_code = error.status_code
        message = str(error.message) if hasattr(error, "message") else str(error)
        request_id = getattr(error, "request_id", None)

        if status_code == 401:
            raise AuthenticationError(
                "Invalid Anthropic API key",
                provider=self.name,
                request_id=request_id,
            ) from error

        if status_code == 403:
            raise AuthenticationError(
                f"Anthropic access denied: {message}",
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
                f"Anthropic rate limit exceeded: {message}",
                retry_after=retry_after,
                provider=self.name,
                request_id=request_id,
            ) from error

        if status_code == 400:
            # Check for content filter in error message
            if "safety" in message.lower() or "harmful" in message.lower():
                raise ContentFilterError(
                    f"Content blocked by Anthropic safety filters: {message}",
                    provider=self.name,
                    request_id=request_id,
                ) from error

            raise InvalidRequestError(
                f"Invalid request to Anthropic: {message}",
                provider=self.name,
                request_id=request_id,
            ) from error

        if status_code >= 500:
            raise ProviderError(
                f"Anthropic server error ({status_code}): {message}",
                provider=self.name,
                request_id=request_id,
            ) from error

        # Unknown error
        raise LLMError(
            f"Anthropic error ({status_code}): {message}",
            provider=self.name,
            request_id=request_id,
        ) from error
