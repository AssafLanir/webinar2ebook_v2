"""Project service for business logic."""

from datetime import UTC, datetime

from bson import ObjectId

from src.api.exceptions import ProjectNotFoundError
from src.db.mongo import get_database
from src.models.edition import get_recommended_edition
from src.models.project import (
    CreateProjectRequest,
    Project,
    ProjectSummary,
    UpdateProjectRequest,
    WebinarType,
)
from src.services.normalization import normalize_project_data

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
    """Convert MongoDB document to Project model.

    Applies normalization to ensure backward-compatible fields
    are converted to canonical shapes.
    """
    # Normalize legacy/missing fields to canonical shapes
    normalized = normalize_project_data(doc)

    # Get default edition based on webinar type for backward compatibility
    webinar_type = doc.get("webinarType", "standard_presentation")
    default_edition = get_recommended_edition(webinar_type)

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
        styleConfig=normalized.get("styleConfig"),
        visualPlan=normalized.get("visualPlan"),
        finalTitle=doc.get("finalTitle", ""),
        finalSubtitle=doc.get("finalSubtitle", ""),
        creditsText=doc.get("creditsText", ""),
        qaReport=doc.get("qaReport"),
        # Edition fields with smart defaults for backward compatibility
        edition=doc.get("edition", default_edition.value),
        fidelity=doc.get("fidelity", "faithful"),
        themes=doc.get("themes", []),
        canonical_transcript=doc.get("canonical_transcript"),
        canonical_transcript_hash=doc.get("canonical_transcript_hash"),
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

    # Set default edition based on webinar type
    default_edition = get_recommended_edition(request.webinarType.value)

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
        "visualPlan": {"opportunities": [], "assets": [], "assignments": []},  # Canonical empty VisualPlan
        "finalTitle": "",
        "finalSubtitle": "",
        "creditsText": "",
        # Edition defaults based on webinar type
        "edition": default_edition.value,
        "fidelity": "faithful",
        "themes": [],
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

    # Build update document with canonical shapes
    # Normalize styleConfig if provided (ensures canonical format on save)
    style_config_data = None
    if request.styleConfig:
        if hasattr(request.styleConfig, "model_dump"):
            style_config_data = request.styleConfig.model_dump()
        elif isinstance(request.styleConfig, dict):
            style_config_data = request.styleConfig

    # Normalize visualPlan if provided
    visual_plan_data = {"opportunities": [], "assets": [], "assignments": []}  # Default empty
    if request.visualPlan:
        if hasattr(request.visualPlan, "model_dump"):
            visual_plan_data = request.visualPlan.model_dump()
        elif isinstance(request.visualPlan, dict):
            visual_plan_data = request.visualPlan

    # Serialize themes if provided
    themes_data = None
    if request.themes is not None:
        themes_data = [theme.model_dump() for theme in request.themes]

    update_doc = {
        "name": request.name,
        "webinarType": request.webinarType.value,
        "updatedAt": now,
        "transcriptText": request.transcriptText,
        "outlineItems": [item.model_dump() for item in request.outlineItems],
        "resources": [res.model_dump() for res in request.resources],
        "visuals": [vis.model_dump() for vis in request.visuals],
        "draftText": request.draftText,
        "styleConfig": style_config_data,
        "visualPlan": visual_plan_data,
        "finalTitle": request.finalTitle,
        "finalSubtitle": request.finalSubtitle,
        "creditsText": request.creditsText,
    }

    # Add edition fields if provided (partial update support)
    if request.edition is not None:
        update_doc["edition"] = request.edition.value
    if request.fidelity is not None:
        update_doc["fidelity"] = request.fidelity.value
    if themes_data is not None:
        update_doc["themes"] = themes_data

    await collection.update_one({"_id": object_id}, {"$set": update_doc})

    # Fetch updated document
    updated_doc = await collection.find_one({"_id": object_id})
    return _to_project(updated_doc)


async def patch_project(project_id: str, updates: dict) -> Project:
    """Partially update a project with specific fields.

    Unlike update_project which requires all fields, this allows
    updating only the specified fields.

    Args:
        project_id: The project ID to update.
        updates: Dictionary of fields to update.

    Returns:
        The updated Project.

    Raises:
        ProjectNotFoundError: If project doesn't exist.
    """
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

    # Add updatedAt timestamp
    updates["updatedAt"] = datetime.now(UTC)

    await collection.update_one({"_id": object_id}, {"$set": updates})

    # Fetch and return updated document
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
