"""Integration tests for ebook preview endpoint.

Tests GET /api/projects/{project_id}/ebook/preview
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient


@pytest_asyncio.fixture
async def project_with_draft(client: AsyncClient) -> str:
    """Create a project with draft content and return its ID."""
    # Create project
    create_resp = await client.post(
        "/projects",
        json={"name": "Test Ebook Project", "webinarType": "standard_presentation"},
    )
    assert create_resp.status_code == 201
    project_id = create_resp.json()["data"]["id"]

    # Update with draft content
    update_resp = await client.put(
        f"/projects/{project_id}",
        json={
            "name": "Test Ebook Project",
            "webinarType": "standard_presentation",
            "draftText": """# Chapter 1: Introduction

This is the introduction chapter with some content.

## Section 1.1: Getting Started

Here we explain how to get started.

# Chapter 2: Main Content

The main body of the ebook.
""",
            "finalTitle": "My Test Ebook",
            "finalSubtitle": "A Comprehensive Guide",
            "creditsText": "Written by Test Author",
        },
    )
    assert update_resp.status_code == 200
    return project_id


@pytest_asyncio.fixture
async def project_without_draft(client: AsyncClient) -> str:
    """Create a project without draft content and return its ID."""
    create_resp = await client.post(
        "/projects",
        json={"name": "Empty Project", "webinarType": "standard_presentation"},
    )
    assert create_resp.status_code == 201
    return create_resp.json()["data"]["id"]


class TestPreviewEndpoint:
    """Tests for GET /api/projects/{project_id}/ebook/preview."""

    async def test_preview_with_draft_returns_html(
        self, client: AsyncClient, project_with_draft: str
    ):
        """Preview returns HTML document when project has draft content."""
        preview_resp = await client.get(
            f"/api/projects/{project_with_draft}/ebook/preview"
        )
        assert preview_resp.status_code == 200

        data = preview_resp.json()
        assert data["error"] is None
        assert data["data"] is not None
        assert "html" in data["data"]

        html = data["data"]["html"]

        # Verify HTML structure
        assert "<!DOCTYPE html>" in html
        assert "<html" in html
        assert "</html>" in html

        # Verify cover page content
        assert "My Test Ebook" in html
        assert "A Comprehensive Guide" in html
        assert "Written by Test Author" in html

        # Verify chapter content
        assert "Chapter 1: Introduction" in html
        assert "Chapter 2: Main Content" in html

        # Verify TOC exists
        assert "Table of Contents" in html

    async def test_preview_without_draft_returns_empty_state(
        self, client: AsyncClient, project_without_draft: str
    ):
        """Preview returns empty state HTML when no draft content."""
        preview_resp = await client.get(
            f"/api/projects/{project_without_draft}/ebook/preview"
        )
        assert preview_resp.status_code == 200

        data = preview_resp.json()
        assert data["error"] is None
        assert data["data"] is not None

        html = data["data"]["html"]

        # Verify empty state message
        assert "No Draft Content" in html
        assert "Generate a draft in Tab 3" in html

    async def test_preview_nonexistent_project_returns_error(
        self, client: AsyncClient
    ):
        """Preview returns error for nonexistent project."""
        fake_id = "000000000000000000000000"
        preview_resp = await client.get(f"/api/projects/{fake_id}/ebook/preview")

        # Returns error envelope (with 404 status code)
        data = preview_resp.json()
        assert data["data"] is None
        assert data["error"] is not None
        assert data["error"]["code"] == "PROJECT_NOT_FOUND"

    async def test_preview_include_images_parameter(
        self, client: AsyncClient, project_with_draft: str
    ):
        """Preview respects include_images query parameter."""
        # Get preview with images (default)
        resp_with = await client.get(
            f"/api/projects/{project_with_draft}/ebook/preview",
            params={"include_images": "true"},
        )
        assert resp_with.status_code == 200

        # Get preview without images
        resp_without = await client.get(
            f"/api/projects/{project_with_draft}/ebook/preview",
            params={"include_images": "false"},
        )
        assert resp_without.status_code == 200

        # Both should return valid HTML
        assert resp_with.json()["data"]["html"]
        assert resp_without.json()["data"]["html"]

    async def test_preview_uses_project_name_as_fallback_title(
        self, client: AsyncClient
    ):
        """Preview uses project name when finalTitle is not set."""
        # Create project
        create_resp = await client.post(
            "/projects",
            json={"name": "Fallback Title Project", "webinarType": "standard_presentation"},
        )
        assert create_resp.status_code == 201
        project_id = create_resp.json()["data"]["id"]

        # Update with draft but no finalTitle
        await client.put(
            f"/projects/{project_id}",
            json={
                "name": "Fallback Title Project",
                "webinarType": "standard_presentation",
                "draftText": "# Chapter 1\n\nSome content here.",
                "finalTitle": "",
            },
        )

        preview_resp = await client.get(f"/api/projects/{project_id}/ebook/preview")
        assert preview_resp.status_code == 200

        html = preview_resp.json()["data"]["html"]
        assert "Fallback Title Project" in html

    async def test_preview_escapes_html_in_metadata(
        self, client: AsyncClient
    ):
        """Preview properly escapes HTML special characters in metadata."""
        # Create project
        create_resp = await client.post(
            "/projects",
            json={"name": "Test Project", "webinarType": "standard_presentation"},
        )
        assert create_resp.status_code == 201
        project_id = create_resp.json()["data"]["id"]

        # Update with XSS attempt in metadata
        await client.put(
            f"/projects/{project_id}",
            json={
                "name": "Test Project",
                "webinarType": "standard_presentation",
                "draftText": "# Chapter 1\n\nContent",
                "finalTitle": "<script>alert('xss')</script>",
                "finalSubtitle": "Test & Review <b>Guide</b>",
                "creditsText": 'Author "Special" <Name>',
            },
        )

        preview_resp = await client.get(f"/api/projects/{project_id}/ebook/preview")
        html = preview_resp.json()["data"]["html"]

        # Verify XSS is escaped
        assert "<script>" not in html
        assert "&lt;script&gt;" in html

        # Verify HTML entities are escaped
        assert "&amp;" in html
        assert "&lt;b&gt;" in html
        assert "&quot;" in html
