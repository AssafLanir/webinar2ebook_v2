"""Unit tests for EPUB generator service.

Tests:
- Image conversion utilities (WebP → JPEG/PNG, optimization)
- Filename sanitization
- Download filename generation
- Path utilities

Note: Full EPUB generation tests require complex mocking of MongoDB, GridFS,
and async contexts. Integration tests cover the full flow.
"""

import io
import re
from datetime import datetime
from pathlib import Path

import pytest
from PIL import Image

from src.models.project import Project
from src.services.epub_generator import (
    sanitize_filename,
    generate_download_filename,
    get_epub_path,
)
from src.services.image_utils import (
    convert_for_epub,
    optimize_epub_image_size,
    optimize_and_convert_for_epub,
    get_epub_image_extension,
    MAX_EPUB_DIMENSION,
)


def create_test_project(
    draft_text: str = "# Chapter 1\n\nSome content here.",
    final_title: str = "Test Book",
    final_subtitle: str = "",
    credits_text: str = "",
) -> Project:
    """Create a test project with the given content."""
    now = datetime.now()
    return Project(
        id="test-project-id",
        name="Test Project",
        webinarType="standard_presentation",
        createdAt=now,
        updatedAt=now,
        draftText=draft_text,
        finalTitle=final_title,
        finalSubtitle=final_subtitle,
        creditsText=credits_text,
    )


def create_test_image(width: int = 100, height: int = 100, mode: str = "RGB", format: str = "PNG") -> bytes:
    """Create a test image as bytes."""
    img = Image.new(mode, (width, height), color=(255, 0, 0))
    output = io.BytesIO()
    img.save(output, format=format)
    return output.getvalue()


def create_webp_image(width: int = 100, height: int = 100, has_alpha: bool = False) -> bytes:
    """Create a test WebP image."""
    mode = "RGBA" if has_alpha else "RGB"
    img = Image.new(mode, (width, height), color=(0, 255, 0, 128) if has_alpha else (0, 255, 0))
    output = io.BytesIO()
    img.save(output, format="WEBP")
    return output.getvalue()


class TestImageConversionUtils:
    """Tests for image conversion utilities (T008)."""

    def test_convert_webp_to_jpeg(self):
        """convert_for_epub() converts WebP to JPEG."""
        webp_bytes = create_webp_image(has_alpha=False)
        converted, mime = convert_for_epub(webp_bytes, "image/webp")

        assert mime == "image/jpeg"
        img = Image.open(io.BytesIO(converted))
        assert img.format == "JPEG"

    def test_convert_webp_with_alpha_to_png(self):
        """convert_for_epub() converts WebP with alpha to PNG."""
        webp_bytes = create_webp_image(has_alpha=True)
        converted, mime = convert_for_epub(webp_bytes, "image/webp")

        assert mime == "image/png"
        img = Image.open(io.BytesIO(converted))
        assert img.format == "PNG"

    def test_jpeg_passthrough(self):
        """convert_for_epub() passes through JPEG unchanged."""
        jpeg_bytes = create_test_image(format="JPEG")
        converted, mime = convert_for_epub(jpeg_bytes, "image/jpeg")

        assert mime == "image/jpeg"
        assert converted == jpeg_bytes

    def test_png_passthrough(self):
        """convert_for_epub() passes through PNG unchanged."""
        png_bytes = create_test_image(format="PNG")
        converted, mime = convert_for_epub(png_bytes, "image/png")

        assert mime == "image/png"
        assert converted == png_bytes

    def test_optimize_large_image(self):
        """optimize_and_convert_for_epub() downscales images > 1600px."""
        large_bytes = create_test_image(width=2400, height=1800, format="JPEG")
        converted, mime = optimize_and_convert_for_epub(large_bytes, "image/jpeg")

        img = Image.open(io.BytesIO(converted))
        assert max(img.size) <= MAX_EPUB_DIMENSION

    def test_optimize_preserves_aspect_ratio(self):
        """optimize_and_convert_for_epub() preserves aspect ratio."""
        # 4:3 aspect ratio at 2000x1500
        large_bytes = create_test_image(width=2000, height=1500, format="JPEG")
        converted, _ = optimize_and_convert_for_epub(large_bytes, "image/jpeg")

        img = Image.open(io.BytesIO(converted))
        width, height = img.size

        # Original ratio is 4:3 = 1.333
        original_ratio = 2000 / 1500
        new_ratio = width / height

        assert abs(original_ratio - new_ratio) < 0.01  # Allow small rounding error

    def test_gif_passthrough(self):
        """convert_for_epub() passes through GIF unchanged."""
        gif_bytes = create_test_image(format="GIF")
        converted, mime = convert_for_epub(gif_bytes, "image/gif")

        assert mime == "image/gif"
        assert converted == gif_bytes

    def test_small_image_not_resized(self):
        """Small images are not resized unnecessarily."""
        small_bytes = create_test_image(width=800, height=600, format="PNG")
        converted, _ = optimize_and_convert_for_epub(small_bytes, "image/png")

        img = Image.open(io.BytesIO(converted))
        assert img.size == (800, 600)


class TestGetEpubImageExtension:
    """Tests for get_epub_image_extension utility."""

    def test_jpeg_extension(self):
        """JPEG gets .jpg extension."""
        assert get_epub_image_extension("image/jpeg") == "jpg"

    def test_png_extension(self):
        """PNG gets .png extension."""
        assert get_epub_image_extension("image/png") == "png"

    def test_gif_extension(self):
        """GIF gets .gif extension."""
        assert get_epub_image_extension("image/gif") == "gif"

    def test_unknown_defaults_to_jpg(self):
        """Unknown MIME types default to jpg."""
        assert get_epub_image_extension("image/unknown") == "jpg"


class TestSanitizeFilename:
    """Tests for filename sanitization."""

    def test_sanitize_basic_title(self):
        """Basic title is sanitized correctly."""
        assert sanitize_filename("My Book Title") == "My_Book_Title"

    def test_sanitize_special_characters(self):
        """Special characters are replaced with underscores."""
        # : and ! get replaced with _, then consecutive _ collapsed, then trailing _ stripped
        assert sanitize_filename("Book: A Story!") == "Book_A_Story"

    def test_sanitize_empty_title(self):
        """Empty title returns 'ebook'."""
        assert sanitize_filename("") == "ebook"

    def test_sanitize_long_title(self):
        """Long titles are truncated."""
        long_title = "A" * 100
        result = sanitize_filename(long_title)
        assert len(result) <= 80

    def test_sanitize_preserves_hyphens(self):
        """Hyphens are preserved in the title."""
        assert sanitize_filename("My-Book-Title") == "My-Book-Title"

    def test_sanitize_leading_trailing_spaces(self):
        """Leading/trailing underscores are stripped."""
        result = sanitize_filename("  My Book  ")
        assert not result.startswith("_")
        assert not result.endswith("_")

    def test_sanitize_multiple_spaces(self):
        """Multiple spaces are collapsed to single underscore."""
        assert sanitize_filename("My    Book") == "My_Book"


class TestGetEpubPath:
    """Tests for get_epub_path utility."""

    def test_get_epub_path_format(self):
        """get_epub_path returns correct path format."""
        path = get_epub_path("test-job-id")
        assert str(path).endswith("test-job-id.epub")

    def test_get_epub_path_is_path_object(self):
        """get_epub_path returns a Path object."""
        path = get_epub_path("test-job")
        assert isinstance(path, Path)


class TestGenerateDownloadFilename:
    """Tests for generate_download_filename utility."""

    def test_generate_download_filename_format(self):
        """Download filename follows {safe_title}_{YYYY-MM-DD}.epub format."""
        project = create_test_project(final_title="Test Book")
        filename = generate_download_filename(project)

        assert filename.startswith("Test_Book_")
        assert filename.endswith(".epub")
        # Check date pattern
        assert re.match(r"Test_Book_\d{4}-\d{2}-\d{2}\.epub", filename)

    def test_generate_download_filename_uses_final_title(self):
        """Filename uses finalTitle when available."""
        project = create_test_project(final_title="My Final Title")
        filename = generate_download_filename(project)

        assert filename.startswith("My_Final_Title_")

    def test_generate_download_filename_fallback_to_name(self):
        """Filename falls back to project name if no finalTitle."""
        project = create_test_project(final_title="")
        filename = generate_download_filename(project)

        assert filename.startswith("Test_Project_")

    def test_generate_download_filename_includes_date(self):
        """Filename includes current date."""
        project = create_test_project(final_title="Book")
        filename = generate_download_filename(project)

        # Verify date format YYYY-MM-DD is present
        date_pattern = r"\d{4}-\d{2}-\d{2}"
        assert re.search(date_pattern, filename)


class TestImageEmbedding:
    """Tests for image embedding behavior."""

    async def test_webp_converted_to_jpeg(self):
        """WebP images without alpha are converted to JPEG."""
        webp_bytes = create_webp_image(has_alpha=False)
        converted, mime = convert_for_epub(webp_bytes, "image/webp")

        assert mime == "image/jpeg"
        img = Image.open(io.BytesIO(converted))
        assert img.format == "JPEG"

    async def test_webp_with_alpha_converted_to_png(self):
        """WebP images with alpha channel are converted to PNG."""
        webp_bytes = create_webp_image(has_alpha=True)
        converted, mime = convert_for_epub(webp_bytes, "image/webp")

        assert mime == "image/png"
        img = Image.open(io.BytesIO(converted))
        assert img.format == "PNG"

    async def test_large_images_downscaled(self):
        """Images larger than 1600px are downscaled."""
        large_img = create_test_image(width=2000, height=3000, format="PNG")
        converted, mime = optimize_and_convert_for_epub(large_img, "image/png")

        img = Image.open(io.BytesIO(converted))
        assert max(img.size) <= MAX_EPUB_DIMENSION
