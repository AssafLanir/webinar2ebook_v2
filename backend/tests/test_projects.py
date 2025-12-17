"""Tests for project CRUD endpoints."""

from typing import Any

import pytest
from httpx import AsyncClient


class TestCreateProject:
    """Tests for POST /projects endpoint."""

    @pytest.mark.asyncio
    async def test_create_project_success(
        self, client: AsyncClient, sample_project_data: dict[str, Any]
    ) -> None:
        """Test successful project creation."""
        response = await client.post("/projects", json=sample_project_data)

        assert response.status_code == 201
        json_data = response.json()

        # Check response envelope
        assert json_data["error"] is None
        assert json_data["data"] is not None

        # Check project data
        project = json_data["data"]
        assert project["name"] == sample_project_data["name"]
        assert project["webinarType"] == sample_project_data["webinarType"]
        assert "id" in project
        assert "createdAt" in project
        assert "updatedAt" in project

        # Check default values for empty fields
        assert project["transcriptText"] == ""
        assert project["outlineItems"] == []
        assert project["resources"] == []
        assert project["visuals"] == []
        assert project["draftText"] == ""
        assert project["styleConfig"] is None
        assert project["finalTitle"] == ""
        assert project["finalSubtitle"] == ""
        assert project["creditsText"] == ""

    @pytest.mark.asyncio
    async def test_create_project_invalid_empty_name(
        self, client: AsyncClient
    ) -> None:
        """Test validation error when name is empty."""
        response = await client.post(
            "/projects",
            json={"name": "", "webinarType": "standard_presentation"},
        )

        assert response.status_code == 400
        json_data = response.json()

        assert json_data["data"] is None
        assert json_data["error"] is not None
        assert json_data["error"]["code"] == "VALIDATION_ERROR"

    @pytest.mark.asyncio
    async def test_create_project_invalid_webinar_type(
        self, client: AsyncClient
    ) -> None:
        """Test validation error when webinarType is invalid."""
        response = await client.post(
            "/projects",
            json={"name": "Test Project", "webinarType": "invalid_type"},
        )

        assert response.status_code == 400
        json_data = response.json()

        assert json_data["data"] is None
        assert json_data["error"] is not None
        assert json_data["error"]["code"] == "VALIDATION_ERROR"

    @pytest.mark.asyncio
    async def test_create_project_missing_fields(
        self, client: AsyncClient
    ) -> None:
        """Test validation error when required fields are missing."""
        response = await client.post("/projects", json={})

        assert response.status_code == 400
        json_data = response.json()

        assert json_data["data"] is None
        assert json_data["error"] is not None
        assert json_data["error"]["code"] == "VALIDATION_ERROR"


class TestListProjects:
    """Tests for GET /projects endpoint."""

    @pytest.mark.asyncio
    async def test_list_projects_empty(self, client: AsyncClient) -> None:
        """Test listing projects when none exist."""
        response = await client.get("/projects")

        assert response.status_code == 200
        json_data = response.json()

        assert json_data["error"] is None
        assert json_data["data"] == []

    @pytest.mark.asyncio
    async def test_list_projects_with_data(
        self, client: AsyncClient, sample_project_data: dict[str, Any]
    ) -> None:
        """Test listing projects returns created projects."""
        # Create two projects
        await client.post("/projects", json=sample_project_data)
        await client.post(
            "/projects",
            json={"name": "Second Project", "webinarType": "training_tutorial"},
        )

        response = await client.get("/projects")

        assert response.status_code == 200
        json_data = response.json()

        assert json_data["error"] is None
        assert len(json_data["data"]) == 2

        # Check that summaries contain expected fields
        for project in json_data["data"]:
            assert "id" in project
            assert "name" in project
            assert "webinarType" in project
            assert "updatedAt" in project
            # Summaries should NOT contain full project data
            assert "transcriptText" not in project


class TestGetProject:
    """Tests for GET /projects/{id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_project_success(
        self, client: AsyncClient, sample_project_data: dict[str, Any]
    ) -> None:
        """Test getting a project by ID."""
        # Create a project first
        create_response = await client.post("/projects", json=sample_project_data)
        created_project = create_response.json()["data"]
        project_id = created_project["id"]

        # Get the project
        response = await client.get(f"/projects/{project_id}")

        assert response.status_code == 200
        json_data = response.json()

        assert json_data["error"] is None
        project = json_data["data"]
        assert project["id"] == project_id
        assert project["name"] == sample_project_data["name"]
        assert project["webinarType"] == sample_project_data["webinarType"]
        # Full project should include all fields
        assert "transcriptText" in project
        assert "outlineItems" in project

    @pytest.mark.asyncio
    async def test_get_project_not_found(self, client: AsyncClient) -> None:
        """Test getting a non-existent project."""
        response = await client.get("/projects/507f1f77bcf86cd799439011")

        assert response.status_code == 404
        json_data = response.json()

        assert json_data["data"] is None
        assert json_data["error"] is not None
        assert json_data["error"]["code"] == "PROJECT_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_get_project_invalid_id(self, client: AsyncClient) -> None:
        """Test getting a project with invalid ID format."""
        response = await client.get("/projects/invalid-id")

        assert response.status_code == 404
        json_data = response.json()

        assert json_data["data"] is None
        assert json_data["error"] is not None
        assert json_data["error"]["code"] == "PROJECT_NOT_FOUND"


class TestUpdateProject:
    """Tests for PUT /projects/{id} endpoint."""

    @pytest.mark.asyncio
    async def test_update_project_success(
        self, client: AsyncClient, sample_project_data: dict[str, Any]
    ) -> None:
        """Test successful project update."""
        # Create a project first
        create_response = await client.post("/projects", json=sample_project_data)
        created_project = create_response.json()["data"]
        project_id = created_project["id"]

        # Update the project with canonical StyleConfigEnvelope format
        update_data = {
            "name": "Updated Project Name",
            "webinarType": "training_tutorial",
            "transcriptText": "Updated transcript content",
            "outlineItems": [
                {"id": "item-1", "title": "Chapter 1", "level": 1, "order": 0}
            ],
            "resources": [
                {"id": "res-1", "label": "Resource 1", "urlOrNote": "https://example.com", "order": 0}
            ],
            "visuals": [
                {"id": "vis-1", "title": "Visual 1", "description": "A visual", "selected": True}
            ],
            "draftText": "Updated draft text",
            "styleConfig": {
                "version": 1,
                "preset_id": "test_preset",
                "style": {
                    "target_audience": "beginners",
                    "tone": "professional",
                }
            },
            "finalTitle": "Final Title",
            "finalSubtitle": "Final Subtitle",
            "creditsText": "Credits here",
        }

        response = await client.put(f"/projects/{project_id}", json=update_data)

        assert response.status_code == 200
        json_data = response.json()

        assert json_data["error"] is None
        project = json_data["data"]
        assert project["id"] == project_id
        assert project["name"] == "Updated Project Name"
        assert project["webinarType"] == "training_tutorial"
        assert project["transcriptText"] == "Updated transcript content"
        assert len(project["outlineItems"]) == 1
        assert project["outlineItems"][0]["title"] == "Chapter 1"
        assert len(project["resources"]) == 1
        assert len(project["visuals"]) == 1
        assert project["draftText"] == "Updated draft text"
        # StyleConfig is now a StyleConfigEnvelope
        assert project["styleConfig"]["version"] == 1
        assert project["styleConfig"]["preset_id"] == "test_preset"
        assert project["styleConfig"]["style"]["target_audience"] == "beginners"
        # VisualPlan should be initialized (even if empty)
        assert project["visualPlan"] is not None
        assert project["visualPlan"]["opportunities"] == []
        assert project["visualPlan"]["assets"] == []
        assert project["finalTitle"] == "Final Title"
        assert project["finalSubtitle"] == "Final Subtitle"
        assert project["creditsText"] == "Credits here"
        # createdAt should stay the same (compare up to seconds, ignore microseconds format)
        assert project["createdAt"][:19] == created_project["createdAt"][:19]
        # updatedAt should be different
        assert project["updatedAt"] != created_project["updatedAt"]

    @pytest.mark.asyncio
    async def test_update_project_not_found(self, client: AsyncClient) -> None:
        """Test updating a non-existent project."""
        update_data = {
            "name": "Updated Name",
            "webinarType": "standard_presentation",
        }
        response = await client.put(
            "/projects/507f1f77bcf86cd799439011", json=update_data
        )

        assert response.status_code == 404
        json_data = response.json()

        assert json_data["data"] is None
        assert json_data["error"] is not None
        assert json_data["error"]["code"] == "PROJECT_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_update_project_invalid_empty_name(
        self, client: AsyncClient, sample_project_data: dict[str, Any]
    ) -> None:
        """Test validation error when updating with empty name."""
        # Create a project first
        create_response = await client.post("/projects", json=sample_project_data)
        created_project = create_response.json()["data"]
        project_id = created_project["id"]

        # Try to update with empty name
        update_data = {
            "name": "",
            "webinarType": "standard_presentation",
        }
        response = await client.put(f"/projects/{project_id}", json=update_data)

        assert response.status_code == 400
        json_data = response.json()

        assert json_data["data"] is None
        assert json_data["error"] is not None
        assert json_data["error"]["code"] == "VALIDATION_ERROR"

    @pytest.mark.asyncio
    async def test_update_project_invalid_webinar_type(
        self, client: AsyncClient, sample_project_data: dict[str, Any]
    ) -> None:
        """Test validation error when updating with invalid webinar type."""
        # Create a project first
        create_response = await client.post("/projects", json=sample_project_data)
        created_project = create_response.json()["data"]
        project_id = created_project["id"]

        # Try to update with invalid webinar type
        update_data = {
            "name": "Valid Name",
            "webinarType": "invalid_type",
        }
        response = await client.put(f"/projects/{project_id}", json=update_data)

        assert response.status_code == 400
        json_data = response.json()

        assert json_data["data"] is None
        assert json_data["error"] is not None
        assert json_data["error"]["code"] == "VALIDATION_ERROR"


class TestDeleteProject:
    """Tests for DELETE /projects/{id} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_project_success(
        self, client: AsyncClient, sample_project_data: dict[str, Any]
    ) -> None:
        """Test successful project deletion."""
        # Create a project first
        create_response = await client.post("/projects", json=sample_project_data)
        created_project = create_response.json()["data"]
        project_id = created_project["id"]

        # Delete the project
        response = await client.delete(f"/projects/{project_id}")

        assert response.status_code == 200
        json_data = response.json()

        assert json_data["error"] is None
        assert json_data["data"]["deleted"] is True

        # Verify the project no longer exists
        get_response = await client.get(f"/projects/{project_id}")
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_project_not_found(self, client: AsyncClient) -> None:
        """Test deleting a non-existent project."""
        response = await client.delete("/projects/507f1f77bcf86cd799439011")

        assert response.status_code == 404
        json_data = response.json()

        assert json_data["data"] is None
        assert json_data["error"] is not None
        assert json_data["error"]["code"] == "PROJECT_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_delete_project_invalid_id(self, client: AsyncClient) -> None:
        """Test deleting with invalid ID format."""
        response = await client.delete("/projects/invalid-id")

        assert response.status_code == 404
        json_data = response.json()

        assert json_data["data"] is None
        assert json_data["error"] is not None
        assert json_data["error"]["code"] == "PROJECT_NOT_FOUND"
