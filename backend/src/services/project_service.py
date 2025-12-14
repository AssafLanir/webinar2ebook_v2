"""Project service for business logic."""

from datetime import UTC, datetime

from bson import ObjectId

from src.api.exceptions import ProjectNotFoundError
from src.db.mongo import get_database
from src.models.project import (
    CreateProjectRequest,
    Project,
    ProjectSummary,
    UpdateProjectRequest,
    WebinarType,
)

COLLECTION_NAME = "projects"


def _to_project_summary(doc: dict) -> ProjectSummary:
    """Convert MongoDB document to ProjectSummary model."""
    return ProjectSummary(
        id=str(doc["_id"]),
        name=doc["name"],
        webinarType=WebinarType(doc["webinarType"]),
        updatedAt=doc["updatedAt"],
    )


def _to_project(doc: dict) -> Project:
    """Convert MongoDB document to Project model."""
    return Project(
        id=str(doc["_id"]),
        name=doc["name"],
        webinarType=WebinarType(doc["webinarType"]),
        createdAt=doc["createdAt"],
        updatedAt=doc["updatedAt"],
        transcriptText=doc.get("transcriptText", ""),
        outlineItems=doc.get("outlineItems", []),
        resources=doc.get("resources", []),
        visuals=doc.get("visuals", []),
        draftText=doc.get("draftText", ""),
        styleConfig=doc.get("styleConfig"),
        finalTitle=doc.get("finalTitle", ""),
        finalSubtitle=doc.get("finalSubtitle", ""),
        creditsText=doc.get("creditsText", ""),
    )


async def list_projects() -> list[ProjectSummary]:
    """List all projects, sorted by updatedAt descending."""
    db = await get_database()
    collection = db[COLLECTION_NAME]

    cursor = collection.find().sort("updatedAt", -1)
    docs = await cursor.to_list(length=None)

    return [_to_project_summary(doc) for doc in docs]


async def create_project(request: CreateProjectRequest) -> Project:
    """Create a new project in the database."""
    db = await get_database()
    collection = db[COLLECTION_NAME]

    now = datetime.now(UTC)
    doc = {
        "name": request.name,
        "webinarType": request.webinarType.value,
        "createdAt": now,
        "updatedAt": now,
        "transcriptText": "",
        "outlineItems": [],
        "resources": [],
        "visuals": [],
        "draftText": "",
        "styleConfig": None,
        "finalTitle": "",
        "finalSubtitle": "",
        "creditsText": "",
    }

    result = await collection.insert_one(doc)
    doc["_id"] = result.inserted_id

    return _to_project(doc)


async def get_project(project_id: str) -> Project:
    """Get a project by ID."""
    db = await get_database()
    collection = db[COLLECTION_NAME]

    try:
        object_id = ObjectId(project_id)
    except Exception:
        raise ProjectNotFoundError(project_id) from None

    doc = await collection.find_one({"_id": object_id})
    if doc is None:
        raise ProjectNotFoundError(project_id)

    return _to_project(doc)


async def update_project(project_id: str, request: UpdateProjectRequest) -> Project:
    """Update a project by ID."""
    db = await get_database()
    collection = db[COLLECTION_NAME]

    try:
        object_id = ObjectId(project_id)
    except Exception:
        raise ProjectNotFoundError(project_id) from None

    # Check if project exists
    existing = await collection.find_one({"_id": object_id})
    if existing is None:
        raise ProjectNotFoundError(project_id)

    now = datetime.now(UTC)

    # Build update document
    update_doc = {
        "name": request.name,
        "webinarType": request.webinarType.value,
        "updatedAt": now,
        "transcriptText": request.transcriptText,
        "outlineItems": [item.model_dump() for item in request.outlineItems],
        "resources": [res.model_dump() for res in request.resources],
        "visuals": [vis.model_dump() for vis in request.visuals],
        "draftText": request.draftText,
        "styleConfig": request.styleConfig.model_dump() if request.styleConfig else None,
        "finalTitle": request.finalTitle,
        "finalSubtitle": request.finalSubtitle,
        "creditsText": request.creditsText,
    }

    await collection.update_one({"_id": object_id}, {"$set": update_doc})

    # Fetch updated document
    updated_doc = await collection.find_one({"_id": object_id})
    return _to_project(updated_doc)


async def delete_project(project_id: str) -> bool:
    """Delete a project by ID.

    Also cleans up any uploaded files associated with the project.
    """
    from src.services.file_service import file_service

    db = await get_database()
    collection = db[COLLECTION_NAME]

    try:
        object_id = ObjectId(project_id)
    except Exception:
        raise ProjectNotFoundError(project_id) from None

    # Check if project exists first
    existing = await collection.find_one({"_id": object_id})
    if existing is None:
        raise ProjectNotFoundError(project_id)

    # Delete all files associated with the project
    file_service.cleanup_project_files(project_id)

    await collection.delete_one({"_id": object_id})
    return True
