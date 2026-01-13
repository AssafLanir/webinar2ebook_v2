"""Pydantic models for Project and related entities."""

from datetime import datetime
from enum import Enum
from typing import Annotated, Any

from pydantic import BaseModel, Field

from .edition import Edition, Fidelity, Theme
from .evidence_map import EvidenceMap
from .qa_report import QAReport
from .style_config import StyleConfigEnvelope
from .visuals import VisualPlan


class WebinarType(str, Enum):
    """Type of webinar content."""

    STANDARD_PRESENTATION = "standard_presentation"
    TRAINING_TUTORIAL = "training_tutorial"
    INTERVIEW = "interview"


class ResourceType(str, Enum):
    """Type of resource content."""

    URL_OR_NOTE = "url_or_note"
    FILE = "file"


# File upload constants
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB in bytes

ALLOWED_MIME_TYPES: dict[str, list[str]] = {
    "application/pdf": [".pdf"],
    "application/vnd.ms-powerpoint": [".ppt"],
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": [".pptx"],
    "application/msword": [".doc"],
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
    "image/jpeg": [".jpg", ".jpeg"],
    "image/png": [".png"],
}

ALLOWED_EXTENSIONS = {ext for exts in ALLOWED_MIME_TYPES.values() for ext in exts}


class OutlineItem(BaseModel):
    """A chapter or section in the ebook outline."""

    id: str
    title: Annotated[str, Field(min_length=1)]
    level: Annotated[int, Field(ge=1, le=3)]
    notes: str | None = None
    order: Annotated[int, Field(ge=0)]


class Resource(BaseModel):
    """A reference link, note, or uploaded file attached to a project."""

    id: str
    label: Annotated[str, Field(min_length=1)]
    order: Annotated[int, Field(ge=0)]
    resourceType: ResourceType = ResourceType.URL_OR_NOTE

    # URL/Note fields (used when resourceType == URL_OR_NOTE)
    urlOrNote: str = ""

    # File fields (used when resourceType == FILE)
    fileId: str | None = None
    fileName: str | None = None
    fileSize: int | None = None  # bytes
    mimeType: str | None = None
    storagePath: str | None = None  # relative path in uploads directory


class Visual(BaseModel):
    """A visual element for the ebook (Stage 2)."""

    id: str
    title: str
    description: str = ""
    selected: bool = False


class LegacyStyleConfig(BaseModel):
    """Legacy style configuration (deprecated, for backward compat)."""

    audience: str | None = None
    tone: str | None = None
    depth: str | None = None
    targetPages: int | None = None


# Request schemas
class CreateProjectRequest(BaseModel):
    """Request body for creating a new project."""

    name: Annotated[str, Field(min_length=1)]
    webinarType: WebinarType


class UpdateProjectRequest(BaseModel):
    """Request body for updating a project."""

    name: Annotated[str, Field(min_length=1)]
    webinarType: WebinarType
    transcriptText: str = ""
    outlineItems: list[OutlineItem] = []
    resources: list[Resource] = []
    visuals: list[Visual] = []
    draftText: str = ""
    styleConfig: StyleConfigEnvelope | LegacyStyleConfig | dict[str, Any] | None = None
    visualPlan: VisualPlan | None = None
    finalTitle: str = ""
    finalSubtitle: str = ""
    creditsText: str = ""
    # Edition fields (Task 3) - all optional for partial updates
    edition: Edition | None = None
    fidelity: Fidelity | None = None
    themes: list[Theme] | None = None


# Response schemas
class ProjectSummary(BaseModel):
    """Summary of a project for list view."""

    id: str
    name: str
    webinarType: WebinarType
    updatedAt: datetime


class Project(BaseModel):
    """Full project representation."""

    id: str
    name: str
    webinarType: WebinarType
    createdAt: datetime
    updatedAt: datetime
    transcriptText: str = ""
    outlineItems: list[OutlineItem] = []
    resources: list[Resource] = []
    visuals: list[Visual] = []
    draftText: str = ""
    styleConfig: StyleConfigEnvelope | LegacyStyleConfig | dict[str, Any] | None = None
    visualPlan: VisualPlan | None = None
    qaReport: QAReport | None = None
    evidenceMap: EvidenceMap | None = None  # Spec 009: Evidence Map for grounded generation
    # Edition fields (Task 3)
    edition: Edition = Edition.QA  # Default to Q&A Edition
    fidelity: Fidelity = Fidelity.FAITHFUL  # Default to Faithful (Q&A only)
    themes: list[Theme] = []  # Empty by default (Ideas only)
    canonical_transcript: str | None = None  # Frozen transcript for offset validity
    canonical_transcript_hash: str | None = None  # SHA256 hash for verification
    finalTitle: str = ""
    finalSubtitle: str = ""
    creditsText: str = ""
