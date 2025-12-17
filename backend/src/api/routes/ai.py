"""AI-assisted feature endpoints.

Provides endpoints for:
- POST /ai/clean-transcript: Clean up a raw transcript
- POST /ai/suggest-outline: Suggest outline from transcript (future)
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
