"""MongoDB connection setup using Motor async driver."""

import os
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

# Configuration from environment variables with defaults
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "webinar2ebook")

# Global client instance
_client: AsyncIOMotorClient | None = None


async def get_database() -> AsyncIOMotorDatabase:
    """Get the database instance, creating client if needed."""
    global _client
    if _client is None:
        # Add connection timeout to fail fast if MongoDB is unavailable
        _client = AsyncIOMotorClient(
            MONGODB_URL,
            serverSelectionTimeoutMS=5000,  # 5 second timeout
            connectTimeoutMS=5000,
        )
    return _client[DATABASE_NAME]


async def close_database() -> None:
    """Close the database connection."""
    global _client
    if _client is not None:
        _client.close()
        _client = None


def get_client() -> AsyncIOMotorClient | None:
    """Get the current client instance (for testing)."""
    return _client


def set_client(client: AsyncIOMotorClient | None) -> None:
    """Set the client instance (for testing)."""
    global _client
    _client = client
