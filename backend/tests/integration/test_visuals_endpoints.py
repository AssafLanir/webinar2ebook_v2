"""Integration tests for visuals API endpoints.

Tests:
- Upload validation (rejects wrong type/size/count with proper error envelope)
- Upload sets default caption (filename without extension)
- Project-scoped serving (404 if asset not in project's visualPlan.assets)
- Delete removes GridFS files and returns success envelope
"""

import io
from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import AsyncClient
from PIL import Image


def create_test_image(
    width: int = 100,
    height: int = 100,
    format: str = "PNG",
) -> bytes:
    """Create a test image in memory."""
    img = Image.new("RGB", (width, height), color="red")
    buffer = io.BytesIO()
    img.save(buffer, format=format)
    buffer.seek(0)
    return buffer.getvalue()


@pytest.fixture
def test_image_png() -> bytes:
    """Create a test PNG image."""
    return create_test_image(format="PNG")


@pytest.fixture
def test_image_jpeg() -> bytes:
    """Create a test JPEG image."""
    return create_test_image(format="JPEG")


@pytest_asyncio.fixture
async def test_project_id(client: AsyncClient) -> str:
    """Create a test project and return its ID."""
    response = await client.post(
        "/projects",
        json={"name": "Visuals Test Project", "webinarType": "standard_presentation"},
    )
    assert response.status_code == 201
    return response.json()["data"]["id"]


class TestUploadValidation:
    """Test upload validation errors."""

    @pytest.mark.asyncio
    async def test_upload_rejects_unsupported_type(
        self,
        client: AsyncClient,
        test_project_id: str,
    ):
        """Upload should reject non-image files with UNSUPPORTED_MEDIA_TYPE."""
        # Create a fake PDF file
        files = [
            ("files", ("document.pdf", b"fake pdf content", "application/pdf")),
        ]

        response = await client.post(
            f"/api/projects/{test_project_id}/visuals/assets/upload",
            files=files,
        )

        assert response.status_code == 400
        data = response.json()
        assert data["data"] is None
        assert data["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"
        assert "document.pdf" in data["error"]["message"]

    @pytest.mark.asyncio
    async def test_upload_rejects_oversized_file(
        self,
        client: AsyncClient,
        test_project_id: str,
    ):
        """Upload should reject files over 10MB with UPLOAD_TOO_LARGE."""
        # Create a file that's "too large" by mocking the size check
        test_image = create_test_image()

        with patch(
            "src.services.visual_asset_service.MAX_FILE_SIZE", 100
        ):  # Set limit to 100 bytes
            files = [
                ("files", ("large.png", test_image, "image/png")),
            ]

            response = await client.post(
                f"/api/projects/{test_project_id}/visuals/assets/upload",
                files=files,
            )

            assert response.status_code == 400
            data = response.json()
            assert data["data"] is None
            assert data["error"]["code"] == "UPLOAD_TOO_LARGE"

    @pytest.mark.asyncio
    async def test_upload_rejects_too_many_files(
        self,
        client: AsyncClient,
        test_project_id: str,
        test_image_png: bytes,
    ):
        """Upload should reject more than 10 files in single request."""
        files = [
            ("files", (f"image{i}.png", test_image_png, "image/png"))
            for i in range(11)
        ]

        response = await client.post(
            f"/api/projects/{test_project_id}/visuals/assets/upload",
            files=files,
        )

        assert response.status_code == 400
        data = response.json()
        assert data["data"] is None
        assert data["error"]["code"] == "TOO_MANY_FILES"

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="GridFS not supported in mongomock_motor - test manually")
    async def test_upload_rejects_when_project_at_limit(
        self,
        client: AsyncClient,
        test_project_id: str,
        test_image_png: bytes,
    ):
        """Upload should reject when project already has max assets."""
        # First, upload images to reach the limit
        with patch(
            "src.services.visual_asset_service.MAX_ASSETS_PER_PROJECT", 2
        ):
            # Upload first batch
            files = [
                ("files", ("image1.png", test_image_png, "image/png")),
                ("files", ("image2.png", test_image_png, "image/png")),
            ]
            response = await client.post(
                f"/api/projects/{test_project_id}/visuals/assets/upload",
                files=files,
            )
            assert response.status_code == 200

            # Update project with the assets so they're tracked
            upload_data = response.json()["data"]
            assets = upload_data["assets"]

            # Save the assets to the project
            await client.put(
                f"/projects/{test_project_id}",
                json={
                    "name": "Test Project",
                    "webinarType": "standard_presentation",
                    "transcriptText": "",
                    "outlineItems": [],
                    "resources": [],
                    "visuals": [],
                    "draftText": "",
                    "visualPlan": {
                        "opportunities": [],
                        "assets": assets,
                        "assignments": [],
                    },
                    "finalTitle": "",
                    "finalSubtitle": "",
                    "creditsText": "",
                },
            )

            # Now try to upload one more
            files = [
                ("files", ("image3.png", test_image_png, "image/png")),
            ]
            response = await client.post(
                f"/api/projects/{test_project_id}/visuals/assets/upload",
                files=files,
            )

            assert response.status_code == 400
            data = response.json()
            assert data["error"]["code"] == "TOO_MANY_ASSETS"


class TestUploadSuccess:
    """Test successful upload scenarios.

    NOTE: These tests require real GridFS support. mongomock_motor doesn't
    support AsyncIOMotorGridFSBucket, so we skip these in the mock environment
    and rely on manual testing or a real MongoDB instance.
    """

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="GridFS not supported in mongomock_motor - test manually")
    async def test_upload_sets_default_caption(
        self,
        client: AsyncClient,
        test_project_id: str,
        test_image_png: bytes,
    ):
        """Upload should set caption to filename without extension."""
        files = [
            ("files", ("my_photo.png", test_image_png, "image/png")),
        ]

        response = await client.post(
            f"/api/projects/{test_project_id}/visuals/assets/upload",
            files=files,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["error"] is None
        assert len(data["data"]["assets"]) == 1

        asset = data["data"]["assets"][0]
        assert asset["caption"] == "my_photo"  # Without .png extension
        assert asset["filename"] == "my_photo.png"

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="GridFS not supported in mongomock_motor - test manually")
    async def test_upload_returns_complete_asset_metadata(
        self,
        client: AsyncClient,
        test_project_id: str,
        test_image_png: bytes,
    ):
        """Upload should return all VisualAsset fields."""
        files = [
            ("files", ("test.png", test_image_png, "image/png")),
        ]

        response = await client.post(
            f"/api/projects/{test_project_id}/visuals/assets/upload",
            files=files,
        )

        assert response.status_code == 200
        asset = response.json()["data"]["assets"][0]

        # Check required fields
        assert "id" in asset
        assert asset["filename"] == "test.png"
        assert asset["media_type"] == "image/png"
        assert asset["origin"] == "client_provided"

        # Check new Spec 005 fields
        assert asset["original_filename"] == "test.png"
        assert asset["size_bytes"] > 0
        assert asset["caption"] == "test"
        assert asset["sha256"] is not None
        assert len(asset["sha256"]) == 64  # SHA-256 hex length
        assert asset["created_at"] is not None

        # Check dimensions
        assert asset["width"] == 100
        assert asset["height"] == 100

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="GridFS not supported in mongomock_motor - test manually")
    async def test_upload_multiple_files(
        self,
        client: AsyncClient,
        test_project_id: str,
        test_image_png: bytes,
        test_image_jpeg: bytes,
    ):
        """Upload should handle multiple files in one request."""
        files = [
            ("files", ("image1.png", test_image_png, "image/png")),
            ("files", ("image2.jpg", test_image_jpeg, "image/jpeg")),
        ]

        response = await client.post(
            f"/api/projects/{test_project_id}/visuals/assets/upload",
            files=files,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]["assets"]) == 2


class TestServeContent:
    """Test asset content serving."""

    @pytest.mark.asyncio
    async def test_serve_returns_404_for_unowned_asset(
        self,
        client: AsyncClient,
        test_project_id: str,
    ):
        """Serve should return 404 if asset not in project's visualPlan."""
        response = await client.get(
            f"/api/projects/{test_project_id}/visuals/assets/nonexistent-id/content",
        )

        assert response.status_code == 404
        data = response.json()
        assert data["error"]["code"] == "ASSET_NOT_FOUND"

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="GridFS not supported in mongomock_motor - test manually")
    async def test_serve_returns_thumbnail_by_default(
        self,
        client: AsyncClient,
        test_project_id: str,
        test_image_png: bytes,
    ):
        """Serve should return thumbnail variant by default."""
        # Upload an image
        files = [("files", ("test.png", test_image_png, "image/png"))]
        upload_response = await client.post(
            f"/api/projects/{test_project_id}/visuals/assets/upload",
            files=files,
        )
        asset = upload_response.json()["data"]["assets"][0]

        # Save asset to project
        await client.put(
            f"/projects/{test_project_id}",
            json={
                "name": "Test Project",
                "webinarType": "standard_presentation",
                "transcriptText": "",
                "outlineItems": [],
                "resources": [],
                "visuals": [],
                "draftText": "",
                "visualPlan": {
                    "opportunities": [],
                    "assets": [asset],
                    "assignments": [],
                },
                "finalTitle": "",
                "finalSubtitle": "",
                "creditsText": "",
            },
        )

        # Serve the asset
        response = await client.get(
            f"/api/projects/{test_project_id}/visuals/assets/{asset['id']}/content",
        )

        assert response.status_code == 200
        assert response.headers["content-type"] in ["image/png", "image/jpeg"]
        assert len(response.content) > 0


class TestDeleteAsset:
    """Test asset deletion."""

    @pytest.mark.asyncio
    async def test_delete_returns_404_for_unowned_asset(
        self,
        client: AsyncClient,
        test_project_id: str,
    ):
        """Delete should return 404 if asset not in project."""
        response = await client.delete(
            f"/api/projects/{test_project_id}/visuals/assets/nonexistent-id",
        )

        assert response.status_code == 404
        data = response.json()
        assert data["error"]["code"] == "ASSET_NOT_FOUND"

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="GridFS not supported in mongomock_motor - test manually")
    async def test_delete_removes_gridfs_files(
        self,
        client: AsyncClient,
        test_project_id: str,
        test_image_png: bytes,
    ):
        """Delete should remove GridFS files and return success."""
        # Upload an image
        files = [("files", ("test.png", test_image_png, "image/png"))]
        upload_response = await client.post(
            f"/api/projects/{test_project_id}/visuals/assets/upload",
            files=files,
        )
        asset = upload_response.json()["data"]["assets"][0]

        # Save asset to project
        await client.put(
            f"/projects/{test_project_id}",
            json={
                "name": "Test Project",
                "webinarType": "standard_presentation",
                "transcriptText": "",
                "outlineItems": [],
                "resources": [],
                "visuals": [],
                "draftText": "",
                "visualPlan": {
                    "opportunities": [],
                    "assets": [asset],
                    "assignments": [],
                },
                "finalTitle": "",
                "finalSubtitle": "",
                "creditsText": "",
            },
        )

        # Delete the asset
        response = await client.delete(
            f"/api/projects/{test_project_id}/visuals/assets/{asset['id']}",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["error"] is None
        assert data["data"]["deleted"] is True
        assert data["data"]["files_removed"] == 2  # original + thumb
