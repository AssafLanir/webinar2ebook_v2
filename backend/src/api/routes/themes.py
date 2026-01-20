"""Theme proposal API endpoints.

Endpoints for theme proposal jobs in Ideas Edition.
"""

import logging

from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.api.response import error_response, success_response
from src.models.theme_job import ThemeJobStatus
from src.services.project_service import get_project, ProjectNotFoundError
from src.services.theme_job_store import get_theme_job_store
from src.services.theme_proposal_service import propose_themes

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai/themes", tags=["Themes"])


class ProposeThemesRequest(BaseModel):
    """Request to start theme proposal job."""
    project_id: str
    existing_themes: list[dict] = []


class ProposeThemesResponse(BaseModel):
    """Response from theme proposal endpoint."""
    job_id: str
    status: str


async def run_theme_proposal(job_id: str, project_id: str) -> None:
    """Background task to run theme proposal.

    Args:
        job_id: The job ID to update with results
        project_id: The project ID to analyze
    """
    store = get_theme_job_store()

    try:
        # Update status to processing
        await store.update_job(job_id, status=ThemeJobStatus.PROCESSING)

        # Get the project transcript
        logger.info("Getting project %s for theme proposal", project_id)
        project = await get_project(project_id)

        transcript = project.transcriptText
        if not transcript or not transcript.strip():
            raise ValueError("Project has no transcript text")

        logger.info(
            "Starting theme proposal for project %s (transcript length: %d)",
            project_id,
            len(transcript)
        )

        # Run theme proposal
        themes = await propose_themes(transcript)

        logger.info("Theme proposal completed with %d themes", len(themes))

        # Update job with results
        await store.update_job(
            job_id,
            status=ThemeJobStatus.COMPLETED,
            themes=themes
        )

    except ProjectNotFoundError:
        logger.error("Project %s not found for theme proposal", project_id)
        await store.update_job(
            job_id,
            status=ThemeJobStatus.FAILED,
            error=f"Project {project_id} not found"
        )

    except Exception as e:
        logger.exception("Theme proposal failed for job %s", job_id)
        await store.update_job(
            job_id,
            status=ThemeJobStatus.FAILED,
            error=str(e)
        )


@router.post("/propose")
async def start_theme_proposal(
    request: ProposeThemesRequest,
    background_tasks: BackgroundTasks
) -> dict:
    """Start async theme proposal job.

    Analyzes transcript and proposes thematic chapters.
    Returns job_id for polling status.
    """
    store = get_theme_job_store()
    job_id = await store.create_job(project_id=request.project_id)

    # Add background task for theme proposal
    background_tasks.add_task(run_theme_proposal, job_id, request.project_id)

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
