"""LLM provider abstraction layer.

This module provides a vendor-neutral interface for interacting with LLM providers
(OpenAI, Anthropic) with automatic fallback and retry logic.
"""

from .client import LLMClient
from .errors import (
    AuthenticationError,
    ContentFilterError,
    InvalidRequestError,
    LLMError,
    ProviderError,
    RateLimitError,
    TimeoutError,
)
from .models import ChatMessage, LLMRequest, LLMResponse, ResponseFormat, Usage
from .schemas import get_draft_plan_schema_path, load_draft_plan_schema

__all__ = [
    "LLMClient",
    "LLMRequest",
    "LLMResponse",
    "ChatMessage",
    "ResponseFormat",
    "Usage",
    "LLMError",
    "AuthenticationError",
    "RateLimitError",
    "TimeoutError",
    "InvalidRequestError",
    "ContentFilterError",
    "ProviderError",
    "load_draft_plan_schema",
    "get_draft_plan_schema_path",
]
