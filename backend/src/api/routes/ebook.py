"""Ebook preview and export API routes (Spec 006).

Endpoints:
- GET /api/projects/{project_id}/ebook/preview - Get HTML preview
- POST /api/projects/{project_id}/ebook/export - Start PDF export job
- GET /api/projects/{project_id}/ebook/export/status/{job_id} - Check export status
- GET /api/projects/{project_id}/ebook/export/download/{job_id} - Download PDF
- POST /api/projects/{project_id}/ebook/export/cancel/{job_id} - Cancel export job
"""

import logging
from pathlib import Path

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse

from src.api.response import error_response, success_response
from src.models import (
    ExportCancelData,
    ExportJobStatus,
    ExportStartData,
    ExportStatusData,
    PreviewData,
)
from src.services.ebook_renderer import EbookRenderer
from src.services.export_job_store import get_export_job
from src.services.pdf_generator import (
    cancel_pdf_export,
    get_pdf_path,
    start_pdf_export,
)
from src.services.project_service import get_project

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/projects/{project_id}/ebook",
    tags=["ebook"],
)


@router.get("/preview")
async def get_preview(
    project_id: str,
    include_images: bool = Query(default=True, description="Include assigned images in preview"),
):
    """Get HTML preview of the assembled ebook.

    Returns:
        PreviewResponse: { data: { html }, error: null } on success
    """
    # Get project
    project = await get_project(project_id)
    if not project:
        return error_response("PROJECT_NOT_FOUND", f"Project {project_id} not found")

    # Render the ebook preview
    renderer = EbookRenderer(project)
    html = await renderer.render_preview(include_images=include_images)

    preview_data = PreviewData(html=html)
    return success_response(preview_data.model_dump())


@router.post("/export")
async def start_export(project_id: str):
    """Start PDF export job.

    Returns:
        ExportStartResponse: { data: { job_id }, error: null } on success

    Errors:
        - PROJECT_NOT_FOUND: Project doesn't exist
        - NO_DRAFT_CONTENT: Project has no draft content to export
    """
    # Get project
    project = await get_project(project_id)
    if not project:
        return error_response("PROJECT_NOT_FOUND", f"Project {project_id} not found")

    # Check for draft content
    if not project.draftText or not project.draftText.strip():
        return error_response("NO_DRAFT_CONTENT", "Project has no draft content to export")

    try:
        # Start export job
        job_id = await start_pdf_export(project_id)
        logger.info(f"Started PDF export job {job_id} for project {project_id}")

        export_data = ExportStartData(job_id=job_id)
        return success_response(export_data.model_dump())

    except ValueError as e:
        logger.error(f"Failed to start export for project {project_id}: {e}")
        return error_response("EXPORT_START_FAILED", str(e))
    except Exception as e:
        logger.exception(f"Unexpected error starting export for project {project_id}")
        return error_response("EXPORT_START_FAILED", "Failed to start export. Please try again.")


@router.get("/export/status/{job_id}")
async def get_export_status(project_id: str, job_id: str):
    """Check export job status.

    Returns:
        ExportStatusResponse: { data: { job_id, status, progress, download_url }, error: null }

    Errors:
        - EXPORT_JOB_NOT_FOUND: Job doesn't exist
    """
    # Get job from store
    job = await get_export_job(job_id)
    if not job:
        return error_response("EXPORT_JOB_NOT_FOUND", f"Export job {job_id} not found")

    # Verify job belongs to the project
    if job.project_id != project_id:
        return error_response("EXPORT_JOB_NOT_FOUND", f"Export job {job_id} not found")

    # Build download URL if completed
    download_url = None
    if job.status == ExportJobStatus.completed:
        download_url = f"/api/projects/{project_id}/ebook/export/download/{job_id}"

    status_data = ExportStatusData(
        job_id=job.job_id,
        status=job.status,
        progress=job.progress,
        download_url=download_url,
        error_message=job.error_message,
    )
    return success_response(status_data.model_dump())


@router.get("/export/download/{job_id}")
async def download_export(project_id: str, job_id: str):
    """Download exported PDF file.

    Returns:
        Binary PDF stream with Content-Disposition header

    Errors:
        - EXPORT_JOB_NOT_FOUND: Job doesn't exist
        - EXPORT_NOT_READY: Job is not completed
        - EXPORT_FAILED: PDF file is missing
    """
    # Get job from store
    job = await get_export_job(job_id)
    if not job:
        return error_response("EXPORT_JOB_NOT_FOUND", f"Export job {job_id} not found")

    # Verify job belongs to the project
    if job.project_id != project_id:
        return error_response("EXPORT_JOB_NOT_FOUND", f"Export job {job_id} not found")

    # Check job is completed
    if job.status != ExportJobStatus.completed:
        return error_response(
            "EXPORT_NOT_READY",
            f"Export job is {job.status.value}, not ready for download"
        )

    # Get PDF file path
    pdf_path = get_pdf_path(job_id)
    if not pdf_path.exists():
        logger.error(f"PDF file missing for completed job {job_id}")
        return error_response(
            "EXPORT_FAILED",
            "PDF file not found. The export may have failed or been cleaned up."
        )

    # Get download filename
    filename = job.download_filename or "ebook.pdf"

    logger.info(f"Serving PDF download for job {job_id}: {filename}")

    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=filename,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.post("/export/cancel/{job_id}")
async def cancel_export(project_id: str, job_id: str):
    """Cancel an in-progress export job.

    Returns:
        ExportCancelResponse: { data: { cancelled: true }, error: null }

    Errors:
        - EXPORT_JOB_NOT_FOUND: Job doesn't exist
        - EXPORT_ALREADY_COMPLETE: Job is already in terminal state
    """
    # Get job from store
    job = await get_export_job(job_id)
    if not job:
        return error_response("EXPORT_JOB_NOT_FOUND", f"Export job {job_id} not found")

    # Verify job belongs to the project
    if job.project_id != project_id:
        return error_response("EXPORT_JOB_NOT_FOUND", f"Export job {job_id} not found")

    # Try to cancel
    cancelled = await cancel_pdf_export(job_id)

    if not cancelled:
        return error_response(
            "EXPORT_ALREADY_COMPLETE",
            f"Export job is already {job.status.value} and cannot be cancelled"
        )

    logger.info(f"Cancellation requested for export job {job_id}")
    cancel_data = ExportCancelData(cancelled=True)
    return success_response(cancel_data.model_dump())
