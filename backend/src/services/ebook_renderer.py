"""Ebook renderer service for assembling markdown into HTML.

Combines project draft, cover page, TOC, and visual assets into
a complete HTML document suitable for preview or PDF export.
"""

import base64
import logging
import re
from dataclasses import dataclass
from typing import Optional

import markdown
from markdown.extensions.toc import TocExtension

from src.models.project import Project
from src.models.visuals import (
    VisualAsset,
    VisualAssignment,
    VisualAssignmentStatus,
    VisualOpportunity,
    VisualPlan,
)
from src.services.ebook_styles import get_pdf_styles, get_preview_styles
from src.services.gridfs_service import get_file

logger = logging.getLogger(__name__)


@dataclass
class ImageData:
    """Resolved image data for insertion."""

    opportunity: VisualOpportunity
    asset: VisualAsset
    content: Optional[bytes] = None
    media_type: str = "image/png"


class EbookRenderer:
    """Renders ebook HTML from project data.

    Features:
    - Cover page with title, subtitle, and credits
    - Auto-generated table of contents from headings
    - Markdown to HTML conversion with tables and fenced code
    - Image insertion at chapter/section locations based on visual assignments
    """

    def __init__(self, project: Project):
        """Initialize renderer with project data.

        Args:
            project: The project containing draftText and visualPlan.
        """
        self.project = project
        self.visual_plan: Optional[VisualPlan] = project.visualPlan
        self._image_cache: dict[str, ImageData] = {}

    async def render_preview(self, include_images: bool = True) -> str:
        """Render HTML for browser preview.

        Uses HTTP URLs for images (faster than embedding).

        Args:
            include_images: Whether to include assigned images in preview.

        Returns:
            Complete HTML document with embedded CSS.
        """
        return await self._render(
            embed_images=False,
            include_images=include_images,
            styles=get_preview_styles(),
        )

    async def render_for_pdf(self) -> str:
        """Render HTML for PDF generation.

        Embeds images as base64 data URIs (required for WeasyPrint).

        Returns:
            Complete HTML document with embedded CSS and images.
        """
        return await self._render(
            embed_images=True,
            include_images=True,
            styles=get_pdf_styles(),
        )

    async def _render(
        self,
        embed_images: bool,
        include_images: bool,
        styles: str,
    ) -> str:
        """Core rendering logic.

        Args:
            embed_images: Whether to embed images as base64 data URIs.
            include_images: Whether to include images at all.
            styles: CSS styles to embed in the document.

        Returns:
            Complete HTML document.
        """
        # Get draft text (may be empty)
        draft_text = self.project.draftText or ""

        if not draft_text.strip():
            return self._empty_preview_html(styles)

        # Resolve image assignments
        images_by_chapter: dict[int, list[ImageData]] = {}
        images_by_section: dict[str, list[ImageData]] = {}

        if include_images and self.visual_plan:
            await self._resolve_images(embed_images)
            images_by_chapter, images_by_section = self._organize_images()

        # Convert markdown to HTML with TOC
        content_html, toc_html = self._convert_markdown(draft_text)

        # Insert images into content
        if include_images:
            content_html = self._insert_images(
                content_html,
                images_by_chapter,
                images_by_section,
                embed_images,
            )

        # Build cover page
        cover_html = self._build_cover_page()

        # Assemble full document
        return self._assemble_document(
            styles=styles,
            cover_html=cover_html,
            toc_html=toc_html,
            content_html=content_html,
        )

    def _empty_preview_html(self, styles: str) -> str:
        """Return placeholder HTML when no draft content exists."""
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ebook Preview</title>
    <style>{styles}</style>
</head>
<body>
    <div class="empty-state" style="text-align: center; padding: 4em; color: #666;">
        <h2>No Draft Content</h2>
        <p>Generate a draft in Tab 3 to see the ebook preview.</p>
    </div>
</body>
</html>"""

    async def _resolve_images(self, embed_images: bool) -> None:
        """Load and cache image data for assigned opportunities.

        Args:
            embed_images: Whether to load image bytes (for embedding).
        """
        if not self.visual_plan:
            return

        # Build lookup maps
        opp_map = {opp.id: opp for opp in self.visual_plan.opportunities}
        asset_map = {asset.id: asset for asset in self.visual_plan.assets}

        for assignment in self.visual_plan.assignments:
            if assignment.status != VisualAssignmentStatus.assigned:
                continue

            opp = opp_map.get(assignment.opportunity_id)
            asset = asset_map.get(assignment.asset_id) if assignment.asset_id else None

            if not opp or not asset:
                logger.warning(
                    f"Missing opportunity or asset for assignment: "
                    f"opp={assignment.opportunity_id}, asset={assignment.asset_id}"
                )
                continue

            image_data = ImageData(
                opportunity=opp,
                asset=asset,
                media_type=asset.media_type or "image/png",
            )

            # Load image bytes if embedding
            if embed_images and asset.storage_key:
                file_result = await get_file(asset.storage_key)
                if file_result:
                    content, content_type, _ = file_result
                    image_data.content = content
                    image_data.media_type = content_type
                else:
                    logger.warning(f"Could not load image: {asset.storage_key}")

            self._image_cache[opp.id] = image_data

    def _organize_images(
        self,
    ) -> tuple[dict[int, list[ImageData]], dict[str, list[ImageData]]]:
        """Organize cached images by chapter and section.

        Returns:
            Tuple of (images_by_chapter, images_by_section).
        """
        by_chapter: dict[int, list[ImageData]] = {}
        by_section: dict[str, list[ImageData]] = {}

        for image_data in self._image_cache.values():
            opp = image_data.opportunity
            chapter_idx = opp.chapter_index

            # Try section-specific placement first
            if opp.section_path:
                section_key = f"{chapter_idx}:{opp.section_path}"
                if section_key not in by_section:
                    by_section[section_key] = []
                by_section[section_key].append(image_data)
            else:
                # Fall back to chapter-level placement
                if chapter_idx not in by_chapter:
                    by_chapter[chapter_idx] = []
                by_chapter[chapter_idx].append(image_data)

        return by_chapter, by_section

    def _convert_markdown(self, markdown_text: str) -> tuple[str, str]:
        """Convert markdown to HTML with TOC extraction.

        Args:
            markdown_text: The markdown content.

        Returns:
            Tuple of (content_html, toc_html).
        """
        md = markdown.Markdown(
            extensions=[
                "tables",
                "fenced_code",
                TocExtension(
                    baselevel=1,
                    toc_depth=2,
                    title="",  # We'll add our own title
                    toc_class="toc-list",
                ),
            ]
        )

        content_html = md.convert(markdown_text)
        toc_html = getattr(md, "toc", "")

        return content_html, toc_html

    def _insert_images(
        self,
        html: str,
        by_chapter: dict[int, list[ImageData]],
        by_section: dict[str, list[ImageData]],
        embed_images: bool,
    ) -> str:
        """Insert image figures into the HTML content.

        MVP image insertion rules:
        1. Primary: Insert at start of matching chapter (after H1)
        2. If section_path exists and matches a heading anchor, insert after that heading
        3. Fallback: Chapter start if section not found

        Args:
            html: The converted HTML content.
            by_chapter: Images indexed by chapter number (1-based).
            by_section: Images indexed by "chapter:section_path" keys.
            embed_images: Whether to use data URIs or HTTP URLs.

        Returns:
            HTML with images inserted.
        """
        # Track which chapter we're in by counting H1 tags
        chapter_count = 0
        result_parts: list[str] = []
        last_end = 0

        # Track which section images were matched (for fallback)
        matched_section_keys: set[str] = set()

        # Build reverse lookup: section_key -> chapter_index
        section_to_chapter: dict[str, int] = {}
        for section_key in by_section:
            chapter_idx = int(section_key.split(":")[0])
            section_to_chapter[section_key] = chapter_idx

        # Find all H1 and H2 tags with their positions
        heading_pattern = re.compile(r'<h([12])[^>]*(?:id="([^"]*)")?[^>]*>(.*?)</h\1>', re.IGNORECASE)

        for match in heading_pattern.finditer(html):
            level = match.group(1)
            heading_id = match.group(2) or ""
            heading_text = match.group(3)

            # Add content before this heading
            result_parts.append(html[last_end : match.end()])
            last_end = match.end()

            if level == "1":
                chapter_count += 1

                # Insert chapter-level images after H1
                if chapter_count in by_chapter:
                    for img in by_chapter[chapter_count]:
                        result_parts.append(self._render_figure(img, embed_images))

                # Also insert any unmatched section images for this chapter (fallback)
                for section_key, images in by_section.items():
                    if section_to_chapter.get(section_key) == chapter_count:
                        if section_key not in matched_section_keys:
                            # This section wasn't matched yet - insert at chapter start
                            for img in images:
                                result_parts.append(self._render_figure(img, embed_images))
                            matched_section_keys.add(section_key)

            elif level == "2" and heading_id:
                # Check for section-level images
                section_key = f"{chapter_count}:{heading_id}"
                if section_key in by_section and section_key not in matched_section_keys:
                    for img in by_section[section_key]:
                        result_parts.append(self._render_figure(img, embed_images))
                    matched_section_keys.add(section_key)

                # Also try matching by slug of the heading text
                slug = self._slugify(heading_text)
                alt_section_key = f"{chapter_count}:{slug}"
                if alt_section_key in by_section and alt_section_key not in matched_section_keys:
                    for img in by_section[alt_section_key]:
                        result_parts.append(self._render_figure(img, embed_images))
                    matched_section_keys.add(alt_section_key)

        # Add remaining content
        result_parts.append(html[last_end:])

        return "".join(result_parts)

    def _render_figure(self, image_data: ImageData, embed: bool) -> str:
        """Render a figure HTML element for an image.

        Args:
            image_data: The resolved image data.
            embed: Whether to embed as base64 data URI.

        Returns:
            HTML figure element, or empty string if image can't be rendered.
        """
        asset = image_data.asset
        opp = image_data.opportunity

        # Determine image source
        if embed and image_data.content:
            # PDF mode with embedded image data
            b64 = base64.b64encode(image_data.content).decode("utf-8")
            src = f"data:{image_data.media_type};base64,{b64}"
        elif embed and not image_data.content:
            # PDF mode but no image data available - skip this image
            logger.warning(
                f"Skipping image in PDF: no content available for asset {asset.id} "
                f"(storage_key={asset.storage_key})"
            )
            return ""
        elif asset.source_url:
            # Preview mode with external URL
            src = asset.source_url
        elif asset.storage_key:
            # Preview mode with local storage - use absolute API endpoint URL
            # (relative URLs don't work in iframe with doc.write())
            src = f"http://localhost:8000/api/projects/{self.project.id}/visuals/assets/{asset.id}/content?size=full"
        else:
            # No image source available - skip
            logger.warning(f"Skipping image: no source available for asset {asset.id}")
            return ""

        # Alt text priority: asset.alt_text > asset.caption > opp.caption > filename
        alt_text = (
            asset.alt_text
            or asset.caption
            or opp.caption
            or asset.filename
            or "Image"
        )

        # Caption priority: asset.caption > opp.caption > filename
        caption = asset.caption or opp.caption or asset.filename or ""

        # Escape HTML in alt text and caption
        alt_text = self._escape_html(alt_text)
        caption = self._escape_html(caption)

        return f"""
<figure>
    <img src="{src}" alt="{alt_text}">
    <figcaption>{caption}</figcaption>
</figure>
"""

    def _build_cover_page(self) -> str:
        """Build the cover page HTML.

        Uses project.finalTitle, finalSubtitle, and creditsText.
        Falls back to project.name if finalTitle is empty.
        """
        title = self.project.finalTitle or self.project.name or "Ebook"
        subtitle = self.project.finalSubtitle or ""
        credits = self.project.creditsText or ""

        title = self._escape_html(title)
        subtitle = self._escape_html(subtitle)
        credits = self._escape_html(credits)

        subtitle_html = f"<h2>{subtitle}</h2>" if subtitle else ""
        credits_html = f'<div class="credits">{credits}</div>' if credits else ""

        return f"""
<div class="cover">
    <h1>{title}</h1>
    {subtitle_html}
    {credits_html}
</div>
"""

    def _assemble_document(
        self,
        styles: str,
        cover_html: str,
        toc_html: str,
        content_html: str,
    ) -> str:
        """Assemble the complete HTML document.

        Args:
            styles: CSS styles to embed.
            cover_html: Cover page HTML.
            toc_html: Table of contents HTML.
            content_html: Main content HTML.

        Returns:
            Complete HTML document.
        """
        title = self.project.finalTitle or self.project.name or "Ebook"
        title = self._escape_html(title)

        # Build TOC section if we have headings
        toc_section = ""
        if toc_html and toc_html.strip():
            toc_section = f"""
<nav class="toc">
    <h2>Table of Contents</h2>
    {toc_html}
</nav>
"""

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>{styles}</style>
</head>
<body>
    {cover_html}
    {toc_section}
    <main class="content">
        {content_html}
    </main>
</body>
</html>"""

    @staticmethod
    def _escape_html(text: str) -> str:
        """Escape HTML special characters."""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#x27;")
        )

    @staticmethod
    def _slugify(text: str) -> str:
        """Convert heading text to URL-friendly slug.

        Matches the markdown TOC extension's slug generation.
        """
        # Remove HTML tags
        text = re.sub(r"<[^>]+>", "", text)
        # Convert to lowercase
        text = text.lower()
        # Replace non-alphanumeric with hyphens
        text = re.sub(r"[^a-z0-9]+", "-", text)
        # Remove leading/trailing hyphens
        text = text.strip("-")
        return text
