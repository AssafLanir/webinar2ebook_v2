"""Pydantic models for Project and related entities."""

from datetime import datetime
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field


class WebinarType(str, Enum):
    """Type of webinar content."""

    STANDARD_PRESENTATION = "standard_presentation"
    TRAINING_TUTORIAL = "training_tutorial"


class OutlineItem(BaseModel):
    """A chapter or section in the ebook outline."""

    id: str
    title: Annotated[str, Field(min_length=1)]
    level: Annotated[int, Field(ge=1, le=3)]
    notes: str | None = None
    order: Annotated[int, Field(ge=0)]


class Resource(BaseModel):
    """A reference link or note attached to a project."""

    id: str
    label: Annotated[str, Field(min_length=1)]
    urlOrNote: str = ""
    order: Annotated[int, Field(ge=0)]


class Visual(BaseModel):
    """A visual element for the ebook (Stage 2)."""

    id: str
    title: str
    description: str = ""
    selected: bool = False


class StyleConfig(BaseModel):
    """Style configuration for draft generation (Stage 3)."""

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
    styleConfig: StyleConfig | None = None
    finalTitle: str = ""
    finalSubtitle: str = ""
    creditsText: str = ""


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
    styleConfig: StyleConfig | None = None
    finalTitle: str = ""
    finalSubtitle: str = ""
    creditsText: str = ""
