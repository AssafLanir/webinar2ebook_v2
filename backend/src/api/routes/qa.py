"""QA (Quality Assessment) endpoints.

T017: Provides async job-based API for draft quality analysis:
- POST /qa/analyze: Start QA analysis (returns job_id)
- GET /qa/status/{job_id}: Poll analysis progress
- GET /qa/report/{project_id}: Get the latest QA report for a project

All responses use the { data, error } envelope pattern.
"""

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.api.response import success_response, error_response
from src.models import QAReport, QAJobStatus
from src.services.qa_job_store import (
    get_qa_job_store,
    create_qa_job,
    get_qa_job,
    update_qa_job,
    get_qa_job_for_project,
)
from src.services.qa_evaluator import evaluate_draft
from src.services.project_service import get_project, patch_project

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/qa", tags=["QA"])


# ============================================================================
# Request/Response Models
# ============================================================================

class QAAnalyzeRequest(BaseModel):
    """Request to start QA analysis."""
    project_id: str = Field(description="Project ID to analyze")
    force: bool = Field(
        default=False,
        description="Force reanalysis even if draft unchanged"
    )


class QAAnalyzeData(BaseModel):
    """Response data for analyze endpoint."""
    job_id: str = Field(description="Job ID for polling")
    status: str = Field(description="Initial job status")
    message: str = Field(description="Status message")


class QAStatusData(BaseModel):
    """Response data for status endpoint."""
    job_id: str = Field(description="Job identifier")
    status: str = Field(description="Current status")
    progress_pct: int = Field(ge=0, le=100, description="Progress percentage")
    current_stage: Optional[str] = Field(default=None, description="Current analysis stage")
    report: Optional[QAReport] = Field(default=None, description="QA report when complete")
    error: Optional[str] = Field(default=None, description="Error message if failed")


class QAReportData(BaseModel):
    """Response data for report endpoint."""
    report: Optional[QAReport] = Field(description="Latest QA report for project")


# ============================================================================
# Background Task
# ============================================================================

async def run_qa_analysis(job_id: str, project_id: str) -> None:
    """Background task to run QA analysis.

    Updates job status as analysis progresses.
    """
    try:
        # Mark job as running
        await update_qa_job(
            job_id,
            status=QAJobStatus.running,
            progress_pct=10,
            current_stage="loading_project",
        )

        # Fetch project
        project = await get_project(project_id)
        if not project:
            await update_qa_job(
                job_id,
                status=QAJobStatus.failed,
                error=f"Project {project_id} not found",
                error_code="PROJECT_NOT_FOUND",
            )
            return

        # Check for draft
        draft = project.draftText
        if not draft or len(draft.strip()) < 100:
            await update_qa_job(
                job_id,
                status=QAJobStatus.failed,
                error="No draft available for analysis",
                error_code="NO_DRAFT",
            )
            return

        # Get transcript if available (for faithfulness check)
        # The transcript is stored in project.transcriptText, not in resources
        transcript = project.transcriptText if project.transcriptText else None

        # Update progress
        await update_qa_job(
            job_id,
            progress_pct=30,
            current_stage="structural_analysis",
        )

        # Run evaluation
        logger.info(f"Starting QA evaluation for project {project_id}")
        report = await evaluate_draft(
            project_id=project_id,
            draft=draft,
            transcript=transcript,
        )

        # Update progress
        await update_qa_job(
            job_id,
            progress_pct=90,
            current_stage="saving_report",
        )

        # Save report to project
        await patch_project(project_id, {"qaReport": report.model_dump(mode="json")})

        # Mark job complete
        job = await get_qa_job(job_id)
        if job:
            job.mark_completed(report)
            await update_qa_job(
                job_id,
                status=job.status,
                completed_at=job.completed_at,
                progress_pct=100,
                report=report,
            )

        logger.info(
            f"QA analysis complete for project {project_id}: "
            f"score={report.overall_score}, issues={report.total_issue_count}"
        )

    except asyncio.CancelledError:
        logger.info(f"QA job {job_id} was cancelled")
        await update_qa_job(
            job_id,
            status=QAJobStatus.cancelled,
        )
    except Exception as e:
        logger.exception(f"QA analysis failed for job {job_id}: {e}")
        await update_qa_job(
            job_id,
            status=QAJobStatus.failed,
            error=str(e)[:500],
            error_code="ANALYSIS_ERROR",
        )


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/analyze")
async def analyze_draft(
    request: QAAnalyzeRequest,
    background_tasks: BackgroundTasks,
) -> dict:
    """Start async QA analysis.

    Creates a background job and returns immediately with job_id.
    Poll /status/{job_id} for progress updates.

    Args:
        request: Analysis request with project_id.
        background_tasks: FastAPI background tasks.

    Returns:
        Job ID and initial status for polling.
    """
    # Check if project exists
    project = await get_project(request.project_id)
    if not project:
        return JSONResponse(
            status_code=404,
            content=error_response(
                "PROJECT_NOT_FOUND",
                f"Project {request.project_id} not found",
            ),
        )

    # Check if draft exists
    if not project.draftText or len(project.draftText.strip()) < 100:
        return JSONResponse(
            status_code=400,
            content=error_response(
                "NO_DRAFT",
                "Project has no draft to analyze. Generate a draft first.",
            ),
        )

    # Check if we already have an up-to-date report (unless force=True)
    if not request.force and project.qaReport:
        from src.services.qa_evaluator import should_run_qa
        should_run = await should_run_qa(project.draftText, project.qaReport)
        if not should_run:
            return success_response({
                "job_id": None,
                "status": "already_current",
                "message": "QA report is already up-to-date for current draft",
            })

    # Create job
    job_id = await create_qa_job(request.project_id)

    # Start background analysis
    background_tasks.add_task(run_qa_analysis, job_id, request.project_id)

    return success_response({
        "job_id": job_id,
        "status": "queued",
        "message": "QA analysis started",
    })


@router.get("/status/{job_id}")
async def get_qa_status(job_id: str) -> dict:
    """Get QA job status.

    Poll this endpoint to track progress and get results.

    Args:
        job_id: The job identifier from /analyze.

    Returns:
        Current status, progress info, and report when complete.
    """
    job = await get_qa_job(job_id)

    if not job:
        return JSONResponse(
            status_code=404,
            content=error_response("JOB_NOT_FOUND", f"Job {job_id} not found"),
        )

    return success_response({
        "job_id": job.job_id,
        "status": job.status.value,
        "progress_pct": job.progress_pct,
        "current_stage": job.current_stage,
        "report": job.report.model_dump(mode="json") if job.report else None,
        "error": job.error,
    })


@router.get("/report/{project_id}")
async def get_qa_report(project_id: str) -> dict:
    """Get the latest QA report for a project.

    Returns the stored QA report without triggering new analysis.
    Use POST /analyze to trigger new analysis.

    Args:
        project_id: The project to get the report for.

    Returns:
        The latest QA report, or null if none exists.
    """
    project = await get_project(project_id)

    if not project:
        return JSONResponse(
            status_code=404,
            content=error_response(
                "PROJECT_NOT_FOUND",
                f"Project {project_id} not found",
            ),
        )

    return success_response({
        "report": project.qaReport.model_dump(mode="json") if project.qaReport else None,
    })


@router.post("/cancel/{job_id}")
async def cancel_qa_job(job_id: str) -> dict:
    """Cancel an ongoing QA analysis.

    Note: Cancellation is best-effort. The job may complete
    before cancellation takes effect.

    Args:
        job_id: The job identifier to cancel.

    Returns:
        Cancellation status.
    """
    job = await get_qa_job(job_id)

    if not job:
        return JSONResponse(
            status_code=404,
            content=error_response("JOB_NOT_FOUND", f"Job {job_id} not found"),
        )

    if job.is_terminal():
        return success_response({
            "job_id": job.job_id,
            "status": job.status.value,
            "message": f"Job already in terminal state: {job.status.value}",
            "cancelled": False,
        })

    # Request cancellation
    await update_qa_job(job_id, cancel_requested=True)

    return success_response({
        "job_id": job.job_id,
        "status": "cancelling",
        "message": "Cancellation requested",
        "cancelled": True,
    })
