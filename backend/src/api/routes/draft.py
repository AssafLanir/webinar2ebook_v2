"""AI draft generation endpoints.

Provides async job-based API for ebook draft generation:
- POST /ai/draft/generate: Start draft generation (returns job_id)
- GET /ai/draft/status/{job_id}: Poll generation progress
- POST /ai/draft/cancel/{job_id}: Cancel ongoing generation
- POST /ai/draft/regenerate: Regenerate a single section

All responses use the { data, error } envelope pattern.

Endpoints will be fully implemented in Phase 3 (US1+US4).
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from src.api.response import success_response, error_response
from src.models import (
    DraftGenerateRequest,
    DraftRegenerateRequest,
    DraftGenerateResponse,
    DraftStatusResponse,
    DraftCancelResponse,
    DraftRegenerateResponse,
)
from src.services import draft_service

router = APIRouter(prefix="/ai/draft", tags=["Draft"])


@router.post("/generate", response_model=DraftGenerateResponse)
async def generate_draft(request: DraftGenerateRequest) -> dict:
    """Start async draft generation.

    Creates a background job and returns immediately with job_id.
    Poll /status/{job_id} for progress updates.

    Args:
        request: Generation request with transcript, outline, style config.

    Returns:
        Job ID and initial status for polling.
    """
    # Validate input
    if len(request.transcript) < 500:
        return JSONResponse(
            status_code=400,
            content=error_response(
                "TRANSCRIPT_TOO_SHORT",
                f"Transcript must be at least 500 characters (got {len(request.transcript)})",
            ),
        )

    # Check book_format for interview_qa (allows empty outline)
    style_dict = request.style_config.get("style", request.style_config) if isinstance(request.style_config, dict) else {}
    book_format = style_dict.get("book_format", "guide")
    is_interview_qa = book_format == "interview_qa"

    # Interview Q&A format allows empty outline (single flowing document)
    if len(request.outline) < 3 and not is_interview_qa:
        return JSONResponse(
            status_code=400,
            content=error_response(
                "OUTLINE_TOO_SMALL",
                f"Outline must have at least 3 items (got {len(request.outline)})",
            ),
        )

    job_id = await draft_service.start_generation(request)

    # Fetch initial status to include progress info
    status_data = await draft_service.get_job_status(job_id)
    if status_data:
        # Only include fields that DraftGenerateData supports
        # (exclude partial_draft_markdown and chapters_available)
        return success_response({
            "job_id": status_data.job_id,
            "status": status_data.status,
            "progress": status_data.progress.model_dump() if status_data.progress else None,
        })

    # Fallback if status not found (should not happen)
    return success_response({
        "job_id": job_id,
        "status": "queued",
        "progress": {
            "current_chapter": 0,
            "total_chapters": len(request.outline),
            "chapters_completed": 0,
        },
    })


@router.get("/status/{job_id}", response_model=DraftStatusResponse)
async def get_draft_status(job_id: str) -> dict:
    """Get generation job status.

    Poll this endpoint to track progress and get results.

    Args:
        job_id: The job identifier from /generate.

    Returns:
        Current status, progress info, and results when complete.
    """
    status_data = await draft_service.get_job_status(job_id)

    if not status_data:
        return JSONResponse(
            status_code=404,
            content=error_response("JOB_NOT_FOUND", f"Job {job_id} not found"),
        )

    return success_response(status_data.model_dump())


@router.post("/cancel/{job_id}", response_model=DraftCancelResponse)
async def cancel_draft(job_id: str) -> dict:
    """Cancel an ongoing generation.

    Cancellation is cooperative - the job will stop after the current
    chapter completes. Partial results are preserved.

    Args:
        job_id: The job identifier to cancel.

    Returns:
        Cancellation status and any partial results.
    """
    cancel_data = await draft_service.cancel_job(job_id)

    if not cancel_data:
        return JSONResponse(
            status_code=404,
            content=error_response("JOB_NOT_FOUND", f"Job {job_id} not found"),
        )

    return success_response(cancel_data.model_dump())


@router.post("/regenerate", response_model=DraftRegenerateResponse)
async def regenerate_section(request: DraftRegenerateRequest) -> dict:
    """Regenerate a single section/chapter.

    Synchronous operation - waits for regeneration to complete.
    Returns new section content with line numbers for replacement.

    Args:
        request: Regeneration request with section ID and context.

    Returns:
        New section markdown and position info.
    """
    from src.models import DraftPlan

    # Parse draft_plan dict to model
    try:
        draft_plan = DraftPlan.model_validate(request.draft_plan)
    except Exception as e:
        return JSONResponse(
            status_code=400,
            content=error_response("INVALID_DRAFT_PLAN", f"Invalid draft_plan: {e}"),
        )

    result = await draft_service.regenerate_section(
        section_outline_item_id=request.section_outline_item_id,
        draft_plan=draft_plan,
        existing_draft=request.existing_draft,
        style_config=request.style_config,
    )

    if not result:
        return JSONResponse(
            status_code=400,
            content=error_response(
                "SECTION_NOT_FOUND",
                f"Section {request.section_outline_item_id} not found in draft plan",
            ),
        )

    return success_response(result.model_dump())
