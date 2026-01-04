"""Rewrite Plan models for Targeted Rewrite Pass (Spec 009 US3).

The Rewrite Plan identifies sections to fix based on QA issues,
constrained by the Evidence Map to prevent adding new claims.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, ConfigDict


class IssueTypeEnum(str, Enum):
    """Types of issues from QA system."""
    repetition = "repetition"
    clarity = "clarity"
    faithfulness = "faithfulness"
    structure = "structure"
    completeness = "completeness"


class IssueReference(BaseModel):
    """Reference to a QA issue being addressed."""

    model_config = ConfigDict(extra="forbid")

    issue_id: str
    issue_type: IssueTypeEnum
    issue_message: Optional[str] = None


class RewriteSection(BaseModel):
    """A single section to rewrite."""

    model_config = ConfigDict(extra="forbid")

    section_id: str
    chapter_index: int = Field(ge=1)
    heading: Optional[str] = None
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    original_text: str
    issues_addressed: List[IssueReference] = Field(default_factory=list)
    allowed_evidence_ids: List[str] = Field(default_factory=list)
    rewrite_instructions: Optional[str] = None
    preserve: List[str] = Field(default_factory=lambda: ["heading", "bullet_structure"])


class RewritePlan(BaseModel):
    """Plan for targeted rewrite of flagged sections."""

    model_config = ConfigDict(extra="forbid")

    version: int = Field(default=1)
    project_id: str
    qa_report_id: Optional[str] = None
    evidence_map_hash: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    pass_number: int = Field(ge=1, le=3, default=1)
    sections: List[RewriteSection] = Field(default_factory=list)
    global_constraints: List[str] = Field(default_factory=lambda: [
        "Do not add claims not in evidence map",
        "Preserve all heading levels",
        "Maintain existing markdown formatting"
    ])


class SectionDiff(BaseModel):
    """Diff for a single rewritten section."""

    model_config = ConfigDict(extra="forbid")

    section_id: str
    heading: Optional[str] = None
    original: str
    rewritten: str
    changes_summary: str


class RewriteResult(BaseModel):
    """Result of a targeted rewrite pass."""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    pass_number: int
    sections_rewritten: int
    issues_addressed: int
    before_draft_hash: str
    after_draft_hash: str
    diffs: List[SectionDiff] = Field(default_factory=list)
    faithfulness_preserved: bool = True
    warnings: List[str] = Field(default_factory=list)
