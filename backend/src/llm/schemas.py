"""Schema loading utilities for LLM structured output.

Provides utilities for loading JSON schemas for LLM calls:
- Internal schema for tests/docs/Anthropic
- OpenAI strict schema for production OpenAI calls
"""

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

logger = logging.getLogger(__name__)

# Schema directory relative to repo root
SCHEMAS_DIR = (
    Path(__file__).parent.parent.parent.parent
    / "specs"
    / "004-tab3-ai-draft"
    / "schemas"
)

# Schema filenames
DRAFT_PLAN_INTERNAL_SCHEMA = "draft_plan.internal.schema.json"
DRAFT_PLAN_OPENAI_STRICT_SCHEMA = "draft_plan.openai.strict.schema.json"


@lru_cache(maxsize=4)
def _load_schema_from_file(filepath: Path) -> dict[str, Any]:
    """Load a JSON schema from file (cached).

    Args:
        filepath: Path to the JSON schema file.

    Returns:
        The parsed JSON schema as a dict.

    Raises:
        FileNotFoundError: If schema file doesn't exist.
        json.JSONDecodeError: If schema is invalid JSON.
    """
    with open(filepath) as f:
        return json.load(f)


def load_draft_plan_schema(
    provider: Literal["openai", "anthropic", "internal"] = "openai",
) -> dict[str, Any]:
    """Load the DraftPlan schema for the specified provider.

    Args:
        provider: Which provider schema to load:
            - "openai": OpenAI strict mode compatible schema (production)
            - "anthropic": Uses internal schema (allOf allowed)
            - "internal": Uses internal schema (for tests/docs)

    Returns:
        The JSON schema dict ready to pass to LLM request.

    Raises:
        FileNotFoundError: If schema file doesn't exist.
    """
    if provider == "openai":
        schema_file = DRAFT_PLAN_OPENAI_STRICT_SCHEMA
    else:
        schema_file = DRAFT_PLAN_INTERNAL_SCHEMA

    schema_path = SCHEMAS_DIR / schema_file
    schema = _load_schema_from_file(schema_path)

    logger.info(f"Using DraftPlan {provider} schema: {schema_path}")

    return schema


def get_draft_plan_schema_path(
    provider: Literal["openai", "anthropic", "internal"] = "openai",
) -> Path:
    """Get the path to the DraftPlan schema for the specified provider.

    Args:
        provider: Which provider schema to get path for.

    Returns:
        Path to the schema file.
    """
    if provider == "openai":
        return SCHEMAS_DIR / DRAFT_PLAN_OPENAI_STRICT_SCHEMA
    return SCHEMAS_DIR / DRAFT_PLAN_INTERNAL_SCHEMA
