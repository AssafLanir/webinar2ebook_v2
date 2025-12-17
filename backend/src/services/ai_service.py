"""AI service for transcript processing and content suggestions.

Provides AI-powered features:
- Transcript cleanup (remove filler words, fix punctuation, organize paragraphs)
- Outline suggestion (extract structure from transcript)
- Resource suggestion (identify relevant resources)
"""

import json

from pydantic import BaseModel

from src.llm import ChatMessage, LLMClient, LLMRequest, ResponseFormat

# Maximum transcript length (enforced at API level too)
MAX_TRANSCRIPT_LENGTH = 50_000

# System prompts per research.md
CLEAN_TRANSCRIPT_PROMPT = """You are a transcript editor. Clean up the following raw transcript by:
- Removing filler words (um, uh, like, you know)
- Fixing punctuation and capitalization
- Organizing into logical paragraphs
- Preserving the speaker's meaning and tone
- Keeping technical terms and proper nouns intact

Return only the cleaned transcript text, no explanations."""

SUGGEST_OUTLINE_PROMPT = """You are a content strategist. Analyze the following transcript and suggest a structured outline for an ebook.
- Extract 5-15 main topics/sections
- Use levels 1-3 (1=chapter, 2=section, 3=subsection)
- Add brief notes where helpful
- Order logically for reader comprehension

Return as JSON matching the provided schema."""

SUGGEST_RESOURCES_PROMPT = """You are a research assistant. Based on the following transcript, suggest 3-5 relevant resources.
- Include URLs mentioned in the transcript
- Suggest related articles, tools, or references
- Each resource needs a short descriptive label
- Prioritize actionable, high-value resources

Return as JSON matching the provided schema."""

# JSON Schema for outline response (per research.md)
OUTLINE_SCHEMA = {
    "name": "outline_response",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "level": {"type": "integer"},
                        "notes": {"type": "string"},
                    },
                    "required": ["title", "level", "notes"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["items"],
        "additionalProperties": False,
    },
}

# JSON Schema for resources response (per research.md)
RESOURCES_SCHEMA = {
    "name": "resources_response",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "resources": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "label": {"type": "string"},
                        "url_or_note": {"type": "string"},
                    },
                    "required": ["label", "url_or_note"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["resources"],
        "additionalProperties": False,
    },
}


class SuggestedOutlineItem(BaseModel):
    """A suggested outline item from AI."""

    title: str
    level: int  # 1=chapter, 2=section, 3=subsection
    notes: str | None = None


class SuggestedResource(BaseModel):
    """A suggested resource from AI."""

    label: str
    url_or_note: str


async def clean_transcript(transcript: str) -> str:
    """Clean up a raw transcript using AI.

    Args:
        transcript: The raw transcript text to clean up.

    Returns:
        The cleaned transcript text.

    Raises:
        LLMError: If the AI request fails after retries and fallback.
    """
    client = LLMClient()

    request = LLMRequest(
        messages=[
            ChatMessage(role="system", content=CLEAN_TRANSCRIPT_PROMPT),
            ChatMessage(role="user", content=transcript),
        ],
        model="",  # Use provider default
        temperature=0.3,  # Lower temperature for more consistent cleanup
        max_tokens=16000,  # Allow long output for full transcript
    )

    response = await client.generate(request)

    # Return the cleaned text (or empty string if no text)
    return response.text or ""


async def suggest_outline(transcript: str) -> list[SuggestedOutlineItem]:
    """Generate outline suggestions from a transcript using AI.

    Args:
        transcript: The transcript text to analyze.

    Returns:
        A list of suggested outline items with title, level, and optional notes.

    Raises:
        LLMError: If the AI request fails after retries and fallback.
    """
    client = LLMClient()

    request = LLMRequest(
        messages=[
            ChatMessage(role="system", content=SUGGEST_OUTLINE_PROMPT),
            ChatMessage(role="user", content=transcript),
        ],
        model="",  # Use provider default
        temperature=0.7,  # Allow some creativity for outline structure
        max_tokens=4000,  # Outline output is structured and shorter
        response_format=ResponseFormat(
            type="json_schema",
            json_schema=OUTLINE_SCHEMA,
        ),
    )

    response = await client.generate(request)

    # Parse the JSON response
    if not response.text:
        return []

    data = json.loads(response.text)
    items = data.get("items", [])

    return [
        SuggestedOutlineItem(
            title=item["title"],
            level=item["level"],
            notes=item.get("notes"),
        )
        for item in items
    ]


async def suggest_resources(transcript: str) -> list[SuggestedResource]:
    """Generate resource suggestions from a transcript using AI.

    Args:
        transcript: The transcript text to analyze.

    Returns:
        A list of suggested resources with label and url_or_note.

    Raises:
        LLMError: If the AI request fails after retries and fallback.
    """
    client = LLMClient()

    request = LLMRequest(
        messages=[
            ChatMessage(role="system", content=SUGGEST_RESOURCES_PROMPT),
            ChatMessage(role="user", content=transcript),
        ],
        model="",  # Use provider default
        temperature=0.7,  # Allow some creativity for resource suggestions
        max_tokens=1000,  # Resources output is short
        response_format=ResponseFormat(
            type="json_schema",
            json_schema=RESOURCES_SCHEMA,
        ),
    )

    response = await client.generate(request)

    # Parse the JSON response
    if not response.text:
        return []

    data = json.loads(response.text)
    resources = data.get("resources", [])

    return [
        SuggestedResource(
            label=resource["label"],
            url_or_note=resource["url_or_note"],
        )
        for resource in resources
    ]
