"""Theme proposal API endpoints.

Endpoints for theme proposal jobs in Ideas Edition.
"""

from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.api.response import success_response, error_response
from src.services.theme_job_store import get_theme_job_store
from src.models.theme_job import ThemeJobStatus


router = APIRouter(prefix="/ai/themes", tags=["Themes"])


class ProposeThemesRequest(BaseModel):
    """Request to start theme proposal job."""
    project_id: str
    existing_themes: list[dict] = []


class ProposeThemesResponse(BaseModel):
    """Response from theme proposal endpoint."""
    job_id: str
    status: str


@router.post("/propose")
async def propose_themes(
    request: ProposeThemesRequest,
    background_tasks: BackgroundTasks
) -> dict:
    """Start async theme proposal job.

    Analyzes transcript and proposes thematic chapters.
    Returns job_id for polling status.
    """
    store = get_theme_job_store()
    job_id = await store.create_job(project_id=request.project_id)

    # TODO: Add background task for actual theme proposal
    # background_tasks.add_task(run_theme_proposal, job_id, request)

    return success_response({
        "job_id": job_id,
        "status": "queued"
    })


@router.get("/status/{job_id}")
async def get_theme_status(job_id: str) -> dict:
    """Get theme proposal job status.

    Returns job status and themes if completed.
    """
    store = get_theme_job_store()
    job = await store.get_job(job_id)

    if not job:
        return JSONResponse(
            status_code=404,
            content=error_response("JOB_NOT_FOUND", f"Job {job_id} not found")
        )

    return success_response({
        "job_id": job.job_id,
        "status": job.status.value,
        "themes": [t.model_dump() for t in job.themes] if job.themes else [],
        "error": job.error
    })


@router.post("/cancel/{job_id}")
async def cancel_theme_job(job_id: str) -> dict:
    """Cancel a theme proposal job.

    Only works for jobs that are not yet completed.
    """
    store = get_theme_job_store()
    job = await store.get_job(job_id)

    if not job:
        return JSONResponse(
            status_code=404,
            content=error_response("JOB_NOT_FOUND", f"Job {job_id} not found")
        )

    if job.is_terminal():
        return success_response({
            "job_id": job_id,
            "cancelled": False,
            "message": "Job already completed"
        })

    await store.update_job(job_id, status=ThemeJobStatus.CANCELLED)

    return success_response({
        "job_id": job_id,
        "cancelled": True
    })
