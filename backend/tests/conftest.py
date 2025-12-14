"""Pytest fixtures for testing."""

import asyncio
from collections.abc import AsyncGenerator, Generator
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from mongomock_motor import AsyncMongoMockClient

from src.api.main import app
from src.db import mongo


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def mock_db() -> AsyncGenerator[Any, None]:
    """Provide a mock MongoDB database for testing."""
    # Create mock client
    mock_client = AsyncMongoMockClient()
    mock_database = mock_client["test_webinar2ebook"]

    # Replace the real client with mock
    mongo.set_client(mock_client)

    yield mock_database

    # Cleanup
    mongo.set_client(None)


@pytest_asyncio.fixture
async def client(mock_db: Any) -> AsyncGenerator[AsyncClient, None]:
    """Provide an async HTTP client for testing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def sample_project_data() -> dict[str, Any]:
    """Sample project data for testing."""
    return {
        "name": "Test Project",
        "webinarType": "standard_presentation",
    }


@pytest.fixture
def sample_update_data() -> dict[str, Any]:
    """Sample update data for testing."""
    return {
        "name": "Updated Project",
        "webinarType": "training_tutorial",
        "transcriptText": "This is the transcript",
        "outlineItems": [
            {"id": "item-1", "title": "Introduction", "level": 1, "order": 0},
            {"id": "item-2", "title": "Main Content", "level": 1, "order": 1},
        ],
        "resources": [
            {
                "id": "res-1",
                "label": "Slide Deck",
                "urlOrNote": "https://example.com",
                "order": 0,
                "resourceType": "url_or_note",
            }
        ],
    }


# File upload fixtures


@pytest.fixture
def sample_pdf_file() -> tuple[str, bytes, str]:
    """Sample PDF file data for testing (filename, content, mime_type)."""
    return ("test_document.pdf", b"%PDF-1.4 sample pdf content", "application/pdf")


@pytest.fixture
def sample_image_file() -> tuple[str, bytes, str]:
    """Sample image file data for testing (filename, content, mime_type)."""
    # PNG header bytes
    png_header = b"\x89PNG\r\n\x1a\n"
    return ("test_image.png", png_header + b"fake png content", "image/png")


@pytest.fixture
def sample_pptx_file() -> tuple[str, bytes, str]:
    """Sample PowerPoint file data for testing (filename, content, mime_type)."""
    return (
        "test_presentation.pptx",
        b"PK\x03\x04 fake pptx content",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )


@pytest.fixture
def sample_docx_file() -> tuple[str, bytes, str]:
    """Sample Word document file data for testing (filename, content, mime_type)."""
    return (
        "test_document.docx",
        b"PK\x03\x04 fake docx content",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@pytest.fixture
def oversized_file() -> tuple[str, bytes, str]:
    """Oversized file data for testing size validation (filename, content, mime_type)."""
    from src.models.project import MAX_FILE_SIZE

    # Create content larger than MAX_FILE_SIZE
    return ("large_file.pdf", b"x" * (MAX_FILE_SIZE + 1), "application/pdf")


@pytest.fixture
def invalid_type_file() -> tuple[str, bytes, str]:
    """Invalid file type for testing type validation (filename, content, mime_type)."""
    return ("script.exe", b"MZ fake executable", "application/x-msdownload")
