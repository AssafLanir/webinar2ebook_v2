"""AI-assisted feature endpoints.

Provides endpoints for:
- POST /ai/clean-transcript: Clean up a raw transcript
- POST /ai/suggest-outline: Suggest outline from transcript
- POST /ai/suggest-resources: Suggest resources from transcript (future)
"""

from typing import Annotated

from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.services import ai_service

router = APIRouter(prefix="/ai", tags=["AI"])


# Request/Response models per data-model.md and contracts/ai-endpoints.yaml


class CleanTranscriptRequest(BaseModel):
    """Request body for transcript cleanup."""

    transcript: Annotated[str, Field(min_length=1, max_length=50000)]


class CleanTranscriptResponse(BaseModel):
    """Response body for transcript cleanup."""

    cleaned_transcript: str


class SuggestOutlineRequest(BaseModel):
    """Request body for outline suggestion."""

    transcript: Annotated[str, Field(min_length=1, max_length=50000)]


class SuggestedOutlineItemResponse(BaseModel):
    """A single suggested outline item."""

    title: str
    level: int
    notes: str | None = None


class SuggestOutlineResponse(BaseModel):
    """Response body for outline suggestion."""

    items: list[SuggestedOutlineItemResponse]


@router.post("/clean-transcript", response_model=CleanTranscriptResponse)
async def clean_transcript(request: CleanTranscriptRequest) -> CleanTranscriptResponse:
    """Clean up a raw transcript using AI.

    Sends the transcript to an LLM for cleanup:
    - Removes filler words (um, uh, like, you know)
    - Fixes punctuation and capitalization
    - Organizes into logical paragraphs
    - Preserves speaker's meaning and tone
    """
    cleaned = await ai_service.clean_transcript(request.transcript)
    return CleanTranscriptResponse(cleaned_transcript=cleaned)


@router.post("/suggest-outline", response_model=SuggestOutlineResponse)
async def suggest_outline(request: SuggestOutlineRequest) -> SuggestOutlineResponse:
    """Suggest an outline structure from a transcript using AI.

    Analyzes the transcript and generates a structured outline:
    - Extracts 5-15 main topics/sections
    - Uses levels 1-3 (chapter, section, subsection)
    - Adds brief notes where helpful
    - Orders logically for reader comprehension
    """
    items = await ai_service.suggest_outline(request.transcript)
    return SuggestOutlineResponse(
        items=[
            SuggestedOutlineItemResponse(
                title=item.title,
                level=item.level,
                notes=item.notes,
            )
            for item in items
        ]
    )
