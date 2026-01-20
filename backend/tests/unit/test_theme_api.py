"""Tests for theme proposal API."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from src.api.main import app
    # Mock the background task runner to prevent actual execution
    with patch("src.api.routes.themes.run_theme_proposal", new_callable=AsyncMock):
        yield TestClient(app)


class TestProposeThemesEndpoint:
    def test_propose_themes_returns_job_id(self, client):
        response = client.post(
            "/api/ai/themes/propose",
            json={"project_id": "proj-123"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "job_id" in data["data"]
        assert data["data"]["status"] == "queued"

    def test_propose_themes_requires_project_id(self, client):
        response = client.post("/api/ai/themes/propose", json={})
        assert response.status_code == 422


class TestThemeStatusEndpoint:
    def test_status_not_found(self, client):
        response = client.get("/api/ai/themes/status/nonexistent")
        assert response.status_code == 404
        data = response.json()
        assert data["error"]["code"] == "JOB_NOT_FOUND"

    def test_status_returns_job_info(self, client):
        # Create a job first
        create_response = client.post(
            "/api/ai/themes/propose",
            json={"project_id": "proj-123"}
        )
        job_id = create_response.json()["data"]["job_id"]

        # Get status
        status_response = client.get(f"/api/ai/themes/status/{job_id}")
        assert status_response.status_code == 200
        data = status_response.json()["data"]
        assert data["job_id"] == job_id
        assert data["status"] == "queued"


class TestCancelThemeEndpoint:
    def test_cancel_not_found(self, client):
        response = client.post("/api/ai/themes/cancel/nonexistent")
        assert response.status_code == 404

    def test_cancel_queued_job(self, client):
        # Create a job
        create_response = client.post(
            "/api/ai/themes/propose",
            json={"project_id": "proj-123"}
        )
        job_id = create_response.json()["data"]["job_id"]

        # Cancel it
        cancel_response = client.post(f"/api/ai/themes/cancel/{job_id}")
        assert cancel_response.status_code == 200
        data = cancel_response.json()["data"]
        assert data["cancelled"] is True

        # Verify it's cancelled
        status_response = client.get(f"/api/ai/themes/status/{job_id}")
        assert status_response.json()["data"]["status"] == "cancelled"
