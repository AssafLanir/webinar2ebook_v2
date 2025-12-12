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
            {"id": "res-1", "label": "Slide Deck", "urlOrNote": "https://example.com", "order": 0}
        ],
    }
