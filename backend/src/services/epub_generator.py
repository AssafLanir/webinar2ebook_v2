"""EPUB generator service for ebook export.

Uses ebooklib to create EPUB 3.0 files with embedded images.
Integrates with export job store for async generation with progress tracking.

Temporary EPUB files are stored in /tmp/webinar2ebook/exports/{job_id}.epub
and cleaned up when jobs expire (via TTL).

Progress callbacks:
- 10%: Cover page generated
- 30-60%: Chapters generated (scaled by chapter count)
- 70%: TOC generated
- 80-90%: Images embedded (scaled by image count)
- 100%: EPUB written to disk
"""

from __future__ import annotations

import asyncio
import html
import logging
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Awaitable, Optional

import markdown
from ebooklib import epub

from src.models import ExportJob, ExportJobStatus, ExportFormat
from src.models.project import Project
from src.models.visuals import VisualAssignmentStatus
from src.services.epub_styles import EPUB_STYLESHEET
from src.services.export_job_store import (
    get_export_job,
    update_export_job,
    get_export_job_store,
)
from src.services.gridfs_service import get_file
from src.services.image_utils import (
    optimize_and_convert_for_epub,
    get_epub_image_extension,
)
from src.services.project_service import get_project

logger = logging.getLogger(__name__)

# Temporary storage directory for generated EPUBs
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
    """Generate the download filename for a project EPUB.

    Format: {safe_title}_{YYYY-MM-DD}.epub

    Args:
        project: The project being exported.

    Returns:
        Safe filename with date and .epub extension.
    """
    title = project.finalTitle or project.name or "ebook"
    safe_title = sanitize_filename(title)
    date_str = datetime.now().strftime("%Y-%m-%d")
    return f"{safe_title}_{date_str}.epub"


def get_epub_path(job_id: str) -> Path:
    """Get the file path for a job's EPUB output.

    Args:
        job_id: The export job ID.

    Returns:
        Path to the EPUB file (may not exist yet).
    """
    return EXPORTS_DIR / f"{job_id}.epub"


def ensure_exports_dir() -> None:
    """Ensure the exports directory exists."""
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)


class CancelledException(Exception):
    """Raised when EPUB generation is cancelled by user."""
    pass


class EpubGenerator:
    """Generates EPUB files from project data using ebooklib.

    Coordinates with export job store for progress updates and
    cancellation handling.
    """

    def __init__(self, project: Project, job_id: str):
        """Initialize EPUB generator.

        Args:
            project: The project to export.
            job_id: The export job ID for progress tracking.
        """
        self.project = project
        self.job_id = job_id
        self.book = epub.EpubBook()
        self.chapters: list[epub.EpubHtml] = []
        self.images: list[epub.EpubImage] = []

    async def generate(self) -> str:
        """Generate EPUB file and return the file path.

        Updates job progress and handles cancellation.

        Returns:
            Path to the generated EPUB file.

        Raises:
            CancelledException: If generation is cancelled.
            ValueError: If project has no draft content.
            RuntimeError: If generation fails.
        """
        if not self.project.draftText or not self.project.draftText.strip():
            raise ValueError("Project has no draft content to export")

        ensure_exports_dir()
        epub_path = get_epub_path(self.job_id)

        try:
            # Set up book metadata
            self._setup_book_metadata()

            # Update status to processing
            await update_export_job(
                self.job_id,
                status=ExportJobStatus.processing,
                progress=5,
            )

            # Check for cancellation
            await self._check_cancellation()

            # T010: Generate cover page - progress 10%
            await self._generate_cover_page()
            await update_export_job(self.job_id, progress=10)

            # Check for cancellation
            await self._check_cancellation()

            # T011: Generate chapters - progress 30-60%
            await self._generate_chapters()

            # Check for cancellation
            await self._check_cancellation()

            # T012: Generate TOC - progress 70%
            await self._generate_toc()
            await update_export_job(self.job_id, progress=70)

            # Check for cancellation
            await self._check_cancellation()

            # T013: Embed images - progress 80-90%
            await self._embed_images()

            # Check for cancellation
            await self._check_cancellation()

            # Add stylesheet
            self._add_stylesheet()

            # Set spine (reading order)
            self._set_spine()

            # Write EPUB file (sync operation, run in thread pool)
            await update_export_job(self.job_id, progress=95)
            await asyncio.to_thread(
                epub.write_epub, str(epub_path), self.book
            )

            await update_export_job(self.job_id, progress=100)
            logger.info(f"[{self.job_id}] EPUB generated: {epub_path}")

            return str(epub_path)

        except CancelledException:
            # Clean up partial file if it exists
            if epub_path.exists():
                epub_path.unlink()
            raise RuntimeError("Export cancelled by user")

        except Exception as e:
            logger.error(f"[{self.job_id}] EPUB generation failed: {e}")
            raise

    async def _check_cancellation(self) -> None:
        """Check if cancellation has been requested.

        Raises:
            CancelledException: If cancellation was requested.
        """
        job = await get_export_job(self.job_id)
        if job and job.cancel_requested:
            raise CancelledException("Export cancelled by user")

    def _setup_book_metadata(self) -> None:
        """Set up EPUB book metadata (title, identifier, language)."""
        title = self.project.finalTitle or self.project.name or "Ebook"

        self.book.set_identifier(f"webinar2ebook-{self.project.id}-{uuid.uuid4().hex[:8]}")
        self.book.set_title(title)
        self.book.set_language("en")

        # Add author/credits if available
        if self.project.creditsText:
            self.book.add_author(self.project.creditsText)

    async def _generate_cover_page(self) -> None:
        """Generate the cover page (T010).

        Creates a cover.xhtml with title, subtitle, and credits.
        """
        title = self.project.finalTitle or self.project.name or "Ebook"
        subtitle = self.project.finalSubtitle or ""
        credits = self.project.creditsText or ""

        # Escape HTML
        title = html.escape(title)
        subtitle = html.escape(subtitle)
        credits = html.escape(credits)

        subtitle_html = f'<p class="subtitle">{subtitle}</p>' if subtitle else ""
        credits_html = f'<p class="credits">{credits}</p>' if credits else ""

        cover_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" lang="en">
<head>
    <meta charset="UTF-8"/>
    <title>Cover</title>
    <link rel="stylesheet" type="text/css" href="styles.css"/>
</head>
<body>
    <div class="cover">
        <h1>{title}</h1>
        {subtitle_html}
        {credits_html}
    </div>
</body>
</html>"""

        cover = epub.EpubHtml(
            title="Cover",
            file_name="cover.xhtml",
            lang="en",
        )
        cover.content = cover_content
        self.book.add_item(cover)
        self.chapters.insert(0, cover)  # Cover is first

        logger.debug(f"[{self.job_id}] Cover page generated")

    async def _generate_chapters(self) -> None:
        """Generate chapter XHTML files from markdown (T011).

        Splits content by H1 headings, converts to XHTML.
        Progress: 30-60% (scaled by chapter count).
        """
        draft_text = self.project.draftText or ""

        # Split by H1 headings
        # Pattern matches "# Title" at start of line
        chapter_splits = re.split(r'^(?=# )', draft_text, flags=re.MULTILINE)

        # Filter out empty splits
        chapter_splits = [c.strip() for c in chapter_splits if c.strip()]

        if not chapter_splits:
            # No chapters found - create single chapter with all content
            chapter_splits = [draft_text]

        total_chapters = len(chapter_splits)
        progress_per_chapter = 30 / max(total_chapters, 1)  # 30% for 30-60 range

        for i, chapter_md in enumerate(chapter_splits):
            # Check for cancellation between chapters
            await self._check_cancellation()

            # Extract title from first line if it's an H1
            lines = chapter_md.split("\n", 1)
            first_line = lines[0].strip()

            if first_line.startswith("# "):
                chapter_title = first_line[2:].strip()
            else:
                chapter_title = f"Chapter {i + 1}"

            # Convert markdown to HTML
            md_converter = markdown.Markdown(
                extensions=["tables", "fenced_code"]
            )
            chapter_html = md_converter.convert(chapter_md)

            # Wrap in proper XHTML structure
            chapter_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" lang="en">
<head>
    <meta charset="UTF-8"/>
    <title>{html.escape(chapter_title)}</title>
    <link rel="stylesheet" type="text/css" href="styles.css"/>
</head>
<body>
    {chapter_html}
</body>
</html>"""

            # Create chapter item
            chapter = epub.EpubHtml(
                title=chapter_title,
                file_name=f"chapter_{i+1:02d}.xhtml",
                lang="en",
            )
            chapter.content = chapter_content
            self.book.add_item(chapter)
            self.chapters.append(chapter)

            # Update progress (30-60 range)
            progress = 30 + int((i + 1) * progress_per_chapter)
            await update_export_job(self.job_id, progress=min(progress, 60))

        logger.debug(f"[{self.job_id}] Generated {len(self.chapters) - 1} chapters")

    async def _generate_toc(self) -> None:
        """Generate table of contents (T012).

        Creates flat TOC from chapter titles (H1-based).
        """
        # Build TOC entries (skip cover, which is first)
        toc_entries = []
        for chapter in self.chapters[1:]:  # Skip cover
            toc_entries.append(
                epub.Link(chapter.file_name, chapter.title, chapter.get_id())
            )

        self.book.toc = tuple(toc_entries)

        # Add NCX (EPUB 2.0 compat) and Nav (EPUB 3.0)
        self.book.add_item(epub.EpubNcx())
        self.book.add_item(epub.EpubNav())

        logger.debug(f"[{self.job_id}] TOC generated with {len(toc_entries)} entries")

    async def _embed_images(self) -> None:
        """Embed images into EPUB (T013).

        Fetches images from GridFS, converts if needed, adds to book.
        Progress: 80-90% (scaled by image count).
        """
        if not self.project.visualPlan:
            await update_export_job(self.job_id, progress=90)
            return

        visual_plan = self.project.visualPlan

        # Build lookup maps
        asset_map = {asset.id: asset for asset in visual_plan.assets}

        # Get assigned images
        assigned_images = [
            a for a in visual_plan.assignments
            if a.status == VisualAssignmentStatus.assigned and a.asset_id
        ]

        if not assigned_images:
            await update_export_job(self.job_id, progress=90)
            return

        total_images = len(assigned_images)
        progress_per_image = 10 / max(total_images, 1)  # 10% for 80-90 range

        for i, assignment in enumerate(assigned_images):
            # Check for cancellation between images
            await self._check_cancellation()

            asset = asset_map.get(assignment.asset_id)
            if not asset or not asset.storage_key:
                logger.warning(
                    f"[{self.job_id}] Skipping image: asset not found "
                    f"(asset_id={assignment.asset_id})"
                )
                continue

            try:
                # Fetch image from GridFS
                file_result = await get_file(asset.storage_key)
                if not file_result:
                    logger.warning(
                        f"[{self.job_id}] Could not load image from GridFS: "
                        f"{asset.storage_key}"
                    )
                    continue

                content, content_type, _ = file_result

                # Convert to EPUB-compatible format if needed (WebP → JPEG/PNG)
                converted_content, final_mime = optimize_and_convert_for_epub(
                    content, content_type
                )

                # Determine file extension
                extension = get_epub_image_extension(final_mime)

                # Create EPUB image item
                image_item = epub.EpubImage()
                image_item.file_name = f"images/{asset.id}.{extension}"
                image_item.media_type = final_mime
                image_item.content = converted_content

                self.book.add_item(image_item)
                self.images.append(image_item)

                logger.debug(
                    f"[{self.job_id}] Embedded image: {image_item.file_name}"
                )

            except Exception as e:
                # Graceful degradation: skip failed images
                logger.warning(
                    f"[{self.job_id}] Failed to embed image {asset.id}: {e}"
                )
                continue

            # Update progress (80-90 range)
            progress = 80 + int((i + 1) * progress_per_image)
            await update_export_job(self.job_id, progress=min(progress, 90))

        logger.debug(f"[{self.job_id}] Embedded {len(self.images)} images")

    def _add_stylesheet(self) -> None:
        """Add CSS stylesheet to EPUB."""
        style = epub.EpubItem(
            uid="style",
            file_name="styles.css",
            media_type="text/css",
            content=EPUB_STYLESHEET.encode("utf-8"),
        )
        self.book.add_item(style)

        # Link stylesheet to all chapters
        for chapter in self.chapters:
            chapter.add_item(style)

    def _set_spine(self) -> None:
        """Set the reading order (spine) for the EPUB."""
        # Spine: nav, then all chapters (cover is already first in chapters)
        self.book.spine = ["nav"] + self.chapters


# ==============================================================================
# Public API
# ==============================================================================


async def start_epub_export(project_id: str) -> str:
    """Start EPUB export for a project.

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
    job_id = await store.create_job(project_id=project_id, format=ExportFormat.epub)

    # Generate download filename
    download_filename = generate_download_filename(project)

    # Update job with filename
    await update_export_job(job_id, download_filename=download_filename)

    logger.info(f"Starting EPUB export job {job_id} for project {project_id}")

    # Start background task
    asyncio.create_task(
        _epub_export_task(job_id, project),
        name=f"epub_export_{job_id}",
    )

    return job_id


async def _epub_export_task(job_id: str, project: Project) -> None:
    """Background task for EPUB generation.

    Updates job status on completion, failure, or cancellation.

    Args:
        job_id: The export job ID.
        project: The project to export.
    """
    try:
        generator = EpubGenerator(project, job_id)
        epub_path = await generator.generate()

        # Mark as completed
        await update_export_job(
            job_id,
            status=ExportJobStatus.completed,
            result_path=epub_path,
        )
        logger.info(f"EPUB export job {job_id} completed successfully")

    except RuntimeError as e:
        if "cancelled" in str(e).lower():
            # User-requested cancellation
            await update_export_job(
                job_id,
                status=ExportJobStatus.cancelled,
            )
            logger.info(f"EPUB export job {job_id} cancelled")
        else:
            # Other runtime error
            await update_export_job(
                job_id,
                status=ExportJobStatus.failed,
                error_message=str(e),
            )
            logger.error(f"EPUB export job {job_id} failed: {e}")

    except Exception as e:
        # Unexpected error
        await update_export_job(
            job_id,
            status=ExportJobStatus.failed,
            error_message=str(e),
        )
        logger.exception(f"EPUB export job {job_id} failed with unexpected error")


async def cancel_epub_export(job_id: str) -> bool:
    """Request cancellation of an EPUB export job.

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
    logger.info(f"Cancellation requested for EPUB export job {job_id}")
    return True


async def cleanup_epub_file(job_id: str) -> bool:
    """Clean up the EPUB file for a job.

    Called when a job is being deleted or has expired.

    Args:
        job_id: The job whose EPUB should be deleted.

    Returns:
        True if file was deleted, False if not found.
    """
    epub_path = get_epub_path(job_id)
    if epub_path.exists():
        try:
            epub_path.unlink()
            logger.info(f"Cleaned up EPUB file for job {job_id}")
            return True
        except Exception as e:
            logger.warning(f"Failed to clean up EPUB file for job {job_id}: {e}")
    return False
