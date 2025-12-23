"""PDF generator service for ebook export.

Uses WeasyPrint to convert HTML to PDF with embedded images.
Integrates with export job store for async generation with progress tracking.

Temporary PDF files are stored in /tmp/webinar2ebook/exports/{job_id}.pdf
and cleaned up when jobs expire (via TTL).
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Optional

# Lazy import WeasyPrint to allow tests to run without system dependencies
# WeasyPrint requires cairo, pango, etc. which may not be available in CI
if TYPE_CHECKING:
    from weasyprint import HTML, CSS

from src.models import ExportJob, ExportJobStatus, ExportFormat
from src.models.project import Project
from src.services.ebook_renderer import EbookRenderer
from src.services.export_job_store import (
    get_export_job_store,
    get_export_job,
    update_export_job,
)
from src.services.project_service import get_project

logger = logging.getLogger(__name__)

# Temporary storage directory for generated PDFs
EXPORTS_DIR = Path(os.environ.get("EXPORTS_DIR", "/tmp/webinar2ebook/exports"))

# Maximum filename length (before extension)
MAX_FILENAME_LENGTH = 80


def sanitize_filename(title: str) -> str:
    """Sanitize a title for use as a filename.

    Rules:
    - Replace non-alphanumeric characters (except spaces and hyphens) with underscores
    - Replace whitespace sequences with single underscores
    - Strip leading/trailing underscores
    - Truncate to MAX_FILENAME_LENGTH characters
    - Fallback to 'ebook' if result is empty

    Args:
        title: The raw title string.

    Returns:
        Safe filename (without extension).

    Examples:
        >>> sanitize_filename("My Amazing E-Book!")
        'My_Amazing_E-Book'
        >>> sanitize_filename("Hello: World?")
        'Hello_World'
        >>> sanitize_filename("")
        'ebook'
    """
    if not title:
        return "ebook"

    # Replace non-alphanumeric chars (except spaces and hyphens) with underscores
    safe = re.sub(r"[^a-zA-Z0-9\s-]", "_", title)
    # Replace whitespace sequences with single underscores
    safe = re.sub(r"\s+", "_", safe)
    # Remove consecutive underscores
    safe = re.sub(r"_+", "_", safe)
    # Strip leading/trailing underscores
    safe = safe.strip("_")

    # Truncate if too long
    if len(safe) > MAX_FILENAME_LENGTH:
        safe = safe[:MAX_FILENAME_LENGTH].rstrip("_")

    return safe or "ebook"


def generate_download_filename(project: Project) -> str:
    """Generate the download filename for a project PDF.

    Format: {safe_title}_{YYYY-MM-DD}.pdf

    Priority for title:
    1. project.finalTitle
    2. project.name
    3. "ebook" (fallback)

    Args:
        project: The project being exported.

    Returns:
        Safe filename with date and .pdf extension.
    """
    title = project.finalTitle or project.name or "ebook"
    safe_title = sanitize_filename(title)
    date_str = datetime.now().strftime("%Y-%m-%d")
    return f"{safe_title}_{date_str}.pdf"


def get_pdf_path(job_id: str) -> Path:
    """Get the file path for a job's PDF output.

    Args:
        job_id: The export job ID.

    Returns:
        Path to the PDF file (may not exist yet).
    """
    return EXPORTS_DIR / f"{job_id}.pdf"


def ensure_exports_dir() -> None:
    """Ensure the exports directory exists."""
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)


class PdfGenerator:
    """Generates PDF files from project data using WeasyPrint.

    Coordinates with export job store for progress updates and
    cancellation handling.
    """

    def __init__(self, project: Project, job_id: str):
        """Initialize PDF generator.

        Args:
            project: The project to export.
            job_id: The export job ID for progress tracking.
        """
        self.project = project
        self.job_id = job_id
        self.renderer = EbookRenderer(project)

    async def generate(self) -> str:
        """Generate PDF file and return the file path.

        Updates job progress and handles cancellation.

        Returns:
            Path to the generated PDF file.

        Raises:
            RuntimeError: If generation fails or is cancelled.
        """
        ensure_exports_dir()
        pdf_path = get_pdf_path(self.job_id)

        try:
            # Update status to processing
            await update_export_job(
                self.job_id,
                status=ExportJobStatus.processing,
                progress=10,
            )

            # Check for cancellation
            job = await get_export_job(self.job_id)
            if job and job.cancel_requested:
                raise RuntimeError("Export cancelled by user")

            # Render HTML with embedded images
            await update_export_job(self.job_id, progress=20)
            logger.info(f"[{self.job_id}] Rendering HTML for PDF...")
            html_content = await self.renderer.render_for_pdf()

            # Check for cancellation
            job = await get_export_job(self.job_id)
            if job and job.cancel_requested:
                raise RuntimeError("Export cancelled by user")

            await update_export_job(self.job_id, progress=50)

            # Generate PDF using WeasyPrint (CPU-bound, run in thread pool)
            logger.info(f"[{self.job_id}] Generating PDF with WeasyPrint...")
            await asyncio.to_thread(self._generate_pdf_sync, html_content, str(pdf_path))

            # Check for cancellation
            job = await get_export_job(self.job_id)
            if job and job.cancel_requested:
                # Clean up partial file
                if pdf_path.exists():
                    pdf_path.unlink()
                raise RuntimeError("Export cancelled by user")

            await update_export_job(self.job_id, progress=100)
            logger.info(f"[{self.job_id}] PDF generated: {pdf_path}")

            return str(pdf_path)

        except Exception as e:
            logger.error(f"[{self.job_id}] PDF generation failed: {e}")
            raise

    def _generate_pdf_sync(self, html_content: str, output_path: str) -> None:
        """Synchronous PDF generation using WeasyPrint.

        This runs in a thread pool to avoid blocking the event loop.

        Args:
            html_content: The HTML to convert.
            output_path: Where to write the PDF.
        """
        # Import WeasyPrint at runtime to allow tests to run without system deps
        from weasyprint import HTML

        html_doc = HTML(string=html_content, base_url=".")
        html_doc.write_pdf(output_path)


# ==============================================================================
# Public API
# ==============================================================================


async def start_pdf_export(project_id: str) -> str:
    """Start PDF export for a project.

    Creates an export job and starts background generation.

    Args:
        project_id: The project to export.

    Returns:
        Job ID for status polling.

    Raises:
        ValueError: If project not found or has no draft content.
    """
    # Validate project exists and has content
    project = await get_project(project_id)
    if not project:
        raise ValueError(f"Project not found: {project_id}")

    if not project.draftText or not project.draftText.strip():
        raise ValueError("Project has no draft content to export")

    # Create export job
    store = get_export_job_store()
    job_id = await store.create_job(project_id=project_id, format=ExportFormat.pdf)

    # Generate download filename
    download_filename = generate_download_filename(project)

    # Update job with filename
    await update_export_job(job_id, download_filename=download_filename)

    logger.info(f"Starting PDF export job {job_id} for project {project_id}")

    # Start background task
    asyncio.create_task(
        _pdf_export_task(job_id, project),
        name=f"pdf_export_{job_id}",
    )

    return job_id


async def _pdf_export_task(job_id: str, project: Project) -> None:
    """Background task for PDF generation.

    Updates job status on completion, failure, or cancellation.

    Args:
        job_id: The export job ID.
        project: The project to export.
    """
    try:
        generator = PdfGenerator(project, job_id)
        pdf_path = await generator.generate()

        # Mark as completed
        await update_export_job(
            job_id,
            status=ExportJobStatus.completed,
            result_path=pdf_path,
        )
        logger.info(f"PDF export job {job_id} completed successfully")

    except RuntimeError as e:
        if "cancelled" in str(e).lower():
            # User-requested cancellation
            await update_export_job(
                job_id,
                status=ExportJobStatus.cancelled,
            )
            logger.info(f"PDF export job {job_id} cancelled")
        else:
            # Other runtime error
            await update_export_job(
                job_id,
                status=ExportJobStatus.failed,
                error_message=str(e),
            )
            logger.error(f"PDF export job {job_id} failed: {e}")

    except Exception as e:
        # Unexpected error
        await update_export_job(
            job_id,
            status=ExportJobStatus.failed,
            error_message=str(e),
        )
        logger.exception(f"PDF export job {job_id} failed with unexpected error")


async def cancel_pdf_export(job_id: str) -> bool:
    """Request cancellation of a PDF export job.

    The actual cancellation happens asynchronously - the job will
    check for the cancel flag at various checkpoints.

    Args:
        job_id: The job to cancel.

    Returns:
        True if cancellation was requested, False if job not found
        or already in terminal state.
    """
    job = await get_export_job(job_id)
    if not job:
        return False

    if job.is_terminal():
        # Already finished - nothing to cancel
        return False

    # Set cancel flag
    await update_export_job(job_id, cancel_requested=True)
    logger.info(f"Cancellation requested for PDF export job {job_id}")
    return True


async def cleanup_pdf_file(job_id: str) -> bool:
    """Clean up the PDF file for a job.

    Called when a job is being deleted or has expired.

    Args:
        job_id: The job whose PDF should be deleted.

    Returns:
        True if file was deleted, False if not found.
    """
    pdf_path = get_pdf_path(job_id)
    if pdf_path.exists():
        try:
            pdf_path.unlink()
            logger.info(f"Cleaned up PDF file for job {job_id}")
            return True
        except Exception as e:
            logger.warning(f"Failed to clean up PDF file for job {job_id}: {e}")
    return False
