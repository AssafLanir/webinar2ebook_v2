"""QA Report models for draft quality assessment.

Design goal:
- QAReport provides structured quality metrics after draft generation
- Enables measurement-driven improvement via scores and issues
- Hybrid approach: regex for structural (fast), LLM for semantic (accurate)
- Issue list capped at 300 to prevent MongoDB document bloat

Pydantic v2. Extra fields are forbidden to prevent drift.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, ConfigDict


class IssueSeverity(str, Enum):
    """Severity level for QA issues."""
    critical = "critical"  # Likely hallucination, factual error, broken structure
    warning = "warning"    # Repetition, long paragraphs, clarity issues
    info = "info"          # Minor suggestions, style improvements


class IssueType(str, Enum):
    """Category of QA issue."""
    repetition = "repetition"
    structure = "structure"
    clarity = "clarity"
    faithfulness = "faithfulness"
    completeness = "completeness"


class IssueCounts(BaseModel):
    """Aggregated issue counts by severity (always accurate, even when truncated)."""
    model_config = ConfigDict(extra="forbid")

    critical: int = Field(default=0, ge=0, description="Count of critical issues")
    warning: int = Field(default=0, ge=0, description="Count of warning issues")
    info: int = Field(default=0, ge=0, description="Count of info issues")

    @property
    def total(self) -> int:
        """Total number of issues."""
        return self.critical + self.warning + self.info


class RubricScores(BaseModel):
    """Breakdown of quality scores by category."""
    model_config = ConfigDict(extra="forbid")

    structure: int = Field(
        ge=1, le=100,
        description="Heading hierarchy and chapter balance score"
    )
    clarity: int = Field(
        ge=1, le=100,
        description="Sentence length, passive voice, jargon score"
    )
    faithfulness: int = Field(
        ge=1, le=100,
        description="Alignment with source material score"
    )
    repetition: int = Field(
        ge=1, le=100,
        description="Inverse of repetition (100 = no repetition)"
    )
    completeness: int = Field(
        ge=1, le=100,
        description="Coverage of source topics score"
    )

    def average(self) -> float:
        """Compute average score across all rubrics."""
        scores = [self.structure, self.clarity, self.faithfulness, self.repetition, self.completeness]
        return sum(scores) / len(scores)


class QAIssue(BaseModel):
    """A single detected quality issue."""
    model_config = ConfigDict(extra="forbid")

    id: str = Field(description="Unique issue identifier")
    severity: IssueSeverity = Field(description="Issue severity level")
    issue_type: IssueType = Field(description="Category of the issue")
    chapter_index: Optional[int] = Field(
        default=None, ge=0,
        description="Chapter index (0-based), null if global"
    )
    heading: Optional[str] = Field(
        default=None,
        description="Heading where issue occurs"
    )
    location: Optional[str] = Field(
        default=None,
        description="Text excerpt showing location"
    )
    message: str = Field(
        min_length=1, max_length=500,
        description="Human-readable issue description"
    )
    suggestion: Optional[str] = Field(
        default=None, max_length=500,
        description="Actionable fix suggestion"
    )
    metadata: Optional[dict[str, Any]] = Field(
        default=None,
        description="Additional issue-specific data (e.g., repeated phrase, count)"
    )


# Maximum number of issues stored in report (prevents MongoDB document bloat)
MAX_ISSUES = 300

# Current schema version
QA_REPORT_VERSION = "1.0"


class QAReport(BaseModel):
    """Quality assessment report for an ebook draft.

    Generated automatically after draft completion or manually triggered.
    Stored in project.qaReport field (no new collection).
    """
    model_config = ConfigDict(extra="forbid")

    id: str = Field(description="Unique report identifier (UUID)")
    project_id: str = Field(description="Reference to the project")
    draft_hash: str = Field(min_length=1, description="Hash of draft text for cache invalidation")
    overall_score: int = Field(ge=1, le=100, description="Overall quality score")
    rubric_scores: RubricScores = Field(description="Breakdown by category")
    issues: list[QAIssue] = Field(
        default_factory=list,
        description=f"List of detected issues (max {MAX_ISSUES})"
    )
    issue_counts: IssueCounts = Field(
        default_factory=IssueCounts,
        description="Counts by severity (always accurate, even if truncated)"
    )
    truncated: bool = Field(
        default=False,
        description="True if issues list was capped at max"
    )
    total_issue_count: int = Field(
        default=0, ge=0,
        description="Actual total count (may exceed issues array length)"
    )
    generated_at: datetime = Field(description="When the report was generated")
    analysis_duration_ms: int = Field(ge=0, description="Analysis duration in milliseconds")
    version: str = Field(default=QA_REPORT_VERSION, description="Schema version for migrations")

    @classmethod
    def from_issues(
        cls,
        id: str,
        project_id: str,
        draft_hash: str,
        overall_score: int,
        rubric_scores: RubricScores,
        all_issues: list[QAIssue],
        analysis_duration_ms: int,
    ) -> "QAReport":
        """Create a QAReport, handling issue truncation automatically.

        Args:
            id: Unique report identifier
            project_id: Reference to the project
            draft_hash: Hash of draft text
            overall_score: Overall quality score (1-100)
            rubric_scores: Breakdown by category
            all_issues: All detected issues (will be truncated if > MAX_ISSUES)
            analysis_duration_ms: How long analysis took

        Returns:
            QAReport with proper truncation and counts
        """
        # Compute counts from all issues (before truncation)
        counts = IssueCounts(
            critical=sum(1 for i in all_issues if i.severity == IssueSeverity.critical),
            warning=sum(1 for i in all_issues if i.severity == IssueSeverity.warning),
            info=sum(1 for i in all_issues if i.severity == IssueSeverity.info),
        )

        # Truncate issues if needed (keep most severe first)
        total_count = len(all_issues)
        truncated = total_count > MAX_ISSUES

        if truncated:
            # Sort by severity (critical first) then keep first MAX_ISSUES
            severity_order = {IssueSeverity.critical: 0, IssueSeverity.warning: 1, IssueSeverity.info: 2}
            sorted_issues = sorted(all_issues, key=lambda i: severity_order[i.severity])
            stored_issues = sorted_issues[:MAX_ISSUES]
        else:
            stored_issues = all_issues

        return cls(
            id=id,
            project_id=project_id,
            draft_hash=draft_hash,
            overall_score=overall_score,
            rubric_scores=rubric_scores,
            issues=stored_issues,
            issue_counts=counts,
            truncated=truncated,
            total_issue_count=total_count,
            generated_at=datetime.now(timezone.utc),
            analysis_duration_ms=analysis_duration_ms,
        )


def qa_report_json_schema() -> dict:
    """Return JSON schema for QAReport (for OpenAPI docs)."""
    return QAReport.model_json_schema()
