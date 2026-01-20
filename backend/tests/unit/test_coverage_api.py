"""Tests for coverage API endpoints."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes.coverage import router


@pytest.fixture
def app():
    """Create a test app with the coverage router."""
    test_app = FastAPI()
    test_app.include_router(router)
    return test_app


@pytest.fixture
def client(app):
    """Create a test client."""
    return TestClient(app)


class TestPreflightEndpoint:
    """Tests for /coverage/preflight endpoint."""

    @pytest.fixture
    def sample_transcript(self):
        """Sample transcript for testing."""
        return """David Deutsch: The Enlightenment marked a turning point in history. We learned that progress is possible. Science gives us the tools to understand reality.

Host: That's fascinating. Can you elaborate on the scientific method?

David Deutsch: The scientific method is about finding testable regularities. Once we have this method, the scope of understanding is limitless. Knowledge grows without bound.

Host: What about wisdom?

David Deutsch: Wisdom, like scientific knowledge, is also limitless. What we call wisdom today will seem primitive in centuries to come."""

    def test_preflight_returns_coverage_report(self, client, sample_transcript):
        """Preflight endpoint returns a coverage report."""
        response = client.post(
            "/coverage/preflight",
            json={
                "transcript": sample_transcript,
                "chapter_count": 2,
                "known_guests": ["David Deutsch"],
                "known_hosts": ["Host"],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "report" in data
        assert "recommendations" in data
        assert data["report"]["total_whitelist_quotes"] >= 0

    def test_preflight_with_empty_transcript(self, client):
        """Empty transcript returns infeasible report."""
        response = client.post(
            "/coverage/preflight",
            json={
                "transcript": "",
                "chapter_count": 4,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["report"]["is_feasible"] is False

    def test_preflight_validates_chapter_count(self, client):
        """Invalid chapter count returns validation error."""
        response = client.post(
            "/coverage/preflight",
            json={
                "transcript": "Some text",
                "chapter_count": 100,  # Too many
            },
        )

        assert response.status_code == 422  # Validation error

    def test_preflight_includes_recommendations(self, client):
        """Preflight includes actionable recommendations."""
        response = client.post(
            "/coverage/preflight",
            json={
                "transcript": "Very short.",
                "chapter_count": 4,
            },
        )

        assert response.status_code == 200
        data = response.json()
        # Should have recommendations about insufficient content
        assert len(data["recommendations"]) > 0 or not data["report"]["is_feasible"]

    def test_preflight_with_defaults(self, client, sample_transcript):
        """Preflight works with default values for optional fields."""
        response = client.post(
            "/coverage/preflight",
            json={
                "transcript": sample_transcript,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "report" in data
        # Default chapter count is 4
        assert len(data["report"]["chapters"]) == 4

    def test_preflight_report_structure(self, client, sample_transcript):
        """Preflight report has expected structure."""
        response = client.post(
            "/coverage/preflight",
            json={
                "transcript": sample_transcript,
                "chapter_count": 2,
            },
        )

        assert response.status_code == 200
        data = response.json()

        report = data["report"]
        assert "transcript_hash" in report
        assert "total_whitelist_quotes" in report
        assert "chapters" in report
        assert "predicted_total_range" in report
        assert "is_feasible" in report
        assert "feasibility_notes" in report

        # Check chapter structure
        assert len(report["chapters"]) == 2
        for chapter in report["chapters"]:
            assert "chapter_index" in chapter
            assert "valid_quotes" in chapter
            assert "predicted_word_range" in chapter

    def test_preflight_chapter_count_min_boundary(self, client, sample_transcript):
        """Chapter count minimum boundary is 1."""
        response = client.post(
            "/coverage/preflight",
            json={
                "transcript": sample_transcript,
                "chapter_count": 1,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["report"]["chapters"]) == 1

    def test_preflight_chapter_count_max_boundary(self, client, sample_transcript):
        """Chapter count maximum boundary is 10."""
        response = client.post(
            "/coverage/preflight",
            json={
                "transcript": sample_transcript,
                "chapter_count": 10,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["report"]["chapters"]) == 10

    def test_preflight_chapter_count_below_min(self, client, sample_transcript):
        """Chapter count below minimum returns validation error."""
        response = client.post(
            "/coverage/preflight",
            json={
                "transcript": sample_transcript,
                "chapter_count": 0,
            },
        )

        assert response.status_code == 422  # Validation error
