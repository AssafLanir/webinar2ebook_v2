"""Visual assets + visual opportunities.

Design goal:
- Tab 2 is where real images get uploaded/managed.
- Tab 3 draft generation can still output a *visual plan* so the editor knows where visuals should go.

So we keep two concepts:
1) VisualAsset: actual file (usually client-provided) or a link.
2) VisualOpportunity: a suggested placement in the ebook draft.

Pydantic v2. Extra fields are forbidden to prevent drift.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional, Literal

from pydantic import BaseModel, Field, ConfigDict, model_validator

from .style_config import VisualType, VisualSourcePolicy


class VisualAssetOrigin(str, Enum):
    client_provided = "client_provided"
    user_uploaded = "user_uploaded"
    client_upload = "client_upload"  # Alias for Spec 005 compatibility
    generated = "generated"
    ai_generated = "ai_generated"  # Alias for Spec 005 compatibility
    external_link = "external_link"
    external_url = "external_url"  # Alias for Spec 005 compatibility


class VisualAssignmentStatus(str, Enum):
    """Status of a visual assignment."""
    assigned = "assigned"
    skipped = "skipped"


class VisualAsset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(description="Stable id used for referencing this asset across the app")
    filename: str = Field(description="Original filename (or derived name)")
    media_type: str = Field(description="MIME type, e.g. image/png")
    origin: VisualAssetOrigin = Field(default=VisualAssetOrigin.client_provided)

    # Exactly one of these is typically present (depending on storage strategy)
    source_url: Optional[str] = Field(default=None, description="External link for the asset if applicable")
    storage_key: Optional[str] = Field(default=None, description="Internal storage key/path if stored by the app")

    width: Optional[int] = Field(default=None, ge=1)
    height: Optional[int] = Field(default=None, ge=1)

    alt_text: Optional[str] = Field(default=None, description="Accessibility / SEO alt text")
    tags: List[str] = Field(default_factory=list)

    # New fields for Spec 005 (Tab 2 Visuals)
    original_filename: Optional[str] = Field(default=None, description="Original upload filename before sanitization")
    size_bytes: Optional[int] = Field(default=None, ge=0, description="File size in bytes")
    caption: Optional[str] = Field(default=None, description="Display caption (defaults to filename stem)")
    sha256: Optional[str] = Field(default=None, description="SHA-256 hash of original bytes")
    created_at: Optional[str] = Field(default=None, description="ISO 8601 timestamp of upload")


class VisualPlacement(str, Enum):
    after_heading = "after_heading"
    inline = "inline"
    end_of_section = "end_of_section"
    end_of_chapter = "end_of_chapter"
    sidebar = "sidebar"


class VisualOpportunity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(description="Stable id for UI selection/acceptance")
    chapter_index: int = Field(ge=1, description="1-based chapter index")
    section_path: Optional[str] = Field(
        default=None, description='Optional fine-grained section identifier (e.g. "2.3" or heading slug)'
    )
    placement: VisualPlacement = Field(default=VisualPlacement.after_heading)

    visual_type: VisualType = Field(description="What kind of visual this should be")
    source_policy: VisualSourcePolicy = Field(default=VisualSourcePolicy.client_assets_only)

    title: str = Field(description="Short title for the visual (used as figure title or label)")
    prompt: str = Field(description="What the visual should show (LLM-generated description)")
    caption: str = Field(description="Caption text shown under the visual")

    required: bool = Field(default=False, description="If true, the draft should include a placeholder even if no asset")
    candidate_asset_ids: List[str] = Field(default_factory=list, description="If any known assets fit, list their ids")

    confidence: float = Field(default=0.6, ge=0.0, le=1.0)
    rationale: Optional[str] = Field(default=None, description="Why this visual helps the reader")


class VisualAssignment(BaseModel):
    """Links a VisualOpportunity to a VisualAsset (or marks it skipped).

    Lifecycle rules:
    - Unassigned: No VisualAssignment record exists
    - Assigned: Record with status="assigned" and asset_id populated
    - Skipped: Record with status="skipped" and asset_id=None
    """

    model_config = ConfigDict(extra="forbid")

    opportunity_id: str = Field(description="References VisualOpportunity.id")
    status: VisualAssignmentStatus = Field(description="assigned or skipped")
    asset_id: Optional[str] = Field(default=None, description="References VisualAsset.id (required when assigned)")
    user_notes: Optional[str] = Field(default=None, description="Optional user comment")
    updated_at: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat(),
        description="ISO 8601 timestamp",
    )

    @model_validator(mode="after")
    def validate_asset_id(self) -> "VisualAssignment":
        """Ensure asset_id is provided when status is 'assigned'."""
        if self.status == VisualAssignmentStatus.assigned and not self.asset_id:
            raise ValueError("asset_id required when status is 'assigned'")
        return self


class VisualPlan(BaseModel):
    """A draft-time plan that can be persisted and later resolved in Tab 2."""

    model_config = ConfigDict(extra="forbid")

    opportunities: List[VisualOpportunity] = Field(default_factory=list)
    assets: List[VisualAsset] = Field(default_factory=list)
    assignments: List[VisualAssignment] = Field(default_factory=list)
