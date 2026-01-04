# Data Model: Evidence-Grounded Drafting

**Feature**: 009-evidence-grounded
**Date**: 2026-01-04

## Overview

This document defines the data models for Evidence-Grounded Drafting. All models use Pydantic v2 with `extra="forbid"` to prevent drift.

---

## 1. ContentMode (Enum)

**Location**: `backend/src/models/style_config.py` (add to existing file)

```python
class ContentMode(str, Enum):
    """Content type that determines structure and constraints."""
    interview = "interview"  # Narrative, speaker insights, quotes
    essay = "essay"          # Argument/thesis structure
    tutorial = "tutorial"    # Step-by-step, action items allowed
```

### Usage
- Controls chapter generation prompts
- Determines forbidden patterns (interview mode)
- Affects default strict_grounded value

---

## 2. StyleConfig Updates

**Location**: `backend/src/models/style_config.py` (modify existing)

### New Fields

```python
class StyleConfig(BaseModel):
    # ... existing fields ...

    # NEW: Content mode and grounding (Spec 009)
    content_mode: ContentMode = Field(
        default=ContentMode.interview,
        description="Type of source content - affects structure and constraints"
    )
    strict_grounded: bool = Field(
        default=True,
        description="When true, only generate content supported by Evidence Map"
    )
```

### Validation

```python
@model_validator(mode="after")
def validate_content_mode_defaults(self) -> "StyleConfig":
    """Set sensible defaults based on content mode."""
    # Interview mode should disable action steps by default
    if self.content_mode == ContentMode.interview:
        # Note: Don't override if user explicitly set
        pass  # Default strict_grounded=True already handles this

    return self
```

---

## 3. EvidenceMap

**Location**: `backend/src/models/evidence_map.py` (new file)

### Main Model

```python
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict

class ClaimType(str, Enum):
    """Type of claim for appropriate handling."""
    factual = "factual"
    opinion = "opinion"
    recommendation = "recommendation"
    anecdote = "anecdote"
    definition = "definition"

class MustIncludePriority(str, Enum):
    """Priority level for must-include items."""
    critical = "critical"
    important = "important"
    optional = "optional"

class EvidenceMap(BaseModel):
    """Per-chapter grounding data for source-faithful generation."""

    model_config = ConfigDict(extra="forbid")

    version: int = Field(default=1, description="Schema version")
    project_id: str = Field(description="Associated project ID")
    content_mode: ContentMode = Field(description="Content mode used")
    strict_grounded: bool = Field(default=True)
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    transcript_hash: str = Field(description="Hash for cache invalidation")
    chapters: list["ChapterEvidence"] = Field(default_factory=list)
    global_context: Optional["GlobalContext"] = Field(default=None)
```

### ChapterEvidence

```python
class ChapterEvidence(BaseModel):
    """Evidence grounding for a single chapter."""

    model_config = ConfigDict(extra="forbid")

    chapter_index: int = Field(ge=1, description="1-based chapter index")
    chapter_title: str
    outline_item_id: Optional[str] = None
    claims: list["EvidenceEntry"] = Field(default_factory=list)
    must_include: list["MustIncludeItem"] = Field(default_factory=list)
    forbidden: list[str] = Field(
        default_factory=list,
        description="Content types forbidden in this chapter"
    )
    transcript_range: Optional["TranscriptRange"] = None
```

### EvidenceEntry

```python
class EvidenceEntry(BaseModel):
    """A single claim with its supporting transcript evidence."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(description="Unique identifier")
    claim: str = Field(description="The claim that can be made")
    support: list["SupportQuote"] = Field(min_length=1)
    confidence: float = Field(ge=0, le=1, default=0.8)
    claim_type: ClaimType = Field(default=ClaimType.factual)

class SupportQuote(BaseModel):
    """A quote from the transcript supporting a claim."""

    model_config = ConfigDict(extra="forbid")

    quote: str = Field(description="Exact quote from transcript")
    start_char: Optional[int] = Field(default=None, ge=0)
    end_char: Optional[int] = Field(default=None, ge=0)
    speaker: Optional[str] = None
```

### Supporting Types

```python
class MustIncludeItem(BaseModel):
    """Key point that must appear in chapter."""

    model_config = ConfigDict(extra="forbid")

    point: str
    priority: MustIncludePriority
    evidence_ids: list[str] = Field(default_factory=list)

class TranscriptRange(BaseModel):
    """Character range in transcript."""

    model_config = ConfigDict(extra="forbid")

    start_char: int = Field(ge=0)
    end_char: int = Field(ge=0)

class GlobalContext(BaseModel):
    """Cross-chapter context from transcript."""

    model_config = ConfigDict(extra="forbid")

    speakers: list["SpeakerInfo"] = Field(default_factory=list)
    main_topics: list[str] = Field(default_factory=list)
    key_terms: list[str] = Field(default_factory=list)

class SpeakerInfo(BaseModel):
    """Speaker identified in transcript."""

    model_config = ConfigDict(extra="forbid")

    name: str
    role: Optional[str] = None
    mentioned_credentials: Optional[str] = None
```

---

## 4. RewritePlan

**Location**: `backend/src/models/rewrite_plan.py` (new file)

### Main Model

```python
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict

class RewritePlan(BaseModel):
    """Plan for targeted rewrite of flagged sections."""

    model_config = ConfigDict(extra="forbid")

    version: int = Field(default=1)
    project_id: str
    qa_report_id: Optional[str] = None
    evidence_map_hash: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    pass_number: int = Field(ge=1, le=3, default=1)
    sections: list["RewriteSection"] = Field(default_factory=list)
    global_constraints: list[str] = Field(default_factory=lambda: [
        "Do not add claims not in evidence map",
        "Preserve all heading levels",
        "Maintain existing markdown formatting"
    ])
```

### RewriteSection

```python
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
    issues_addressed: list[IssueReference] = Field(default_factory=list)
    allowed_evidence_ids: list[str] = Field(default_factory=list)
    rewrite_instructions: Optional[str] = None
    preserve: list[str] = Field(default_factory=lambda: ["heading", "bullet_structure"])
```

---

## 5. Job Status Updates

**Location**: `backend/src/models/generation_job.py` (modify existing)

### New Fields for GenerationJob

```python
class JobStatus(str, Enum):
    queued = "queued"
    planning = "planning"
    evidence_map = "evidence_map"  # NEW
    generating = "generating"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"

class GenerationJob(BaseModel):
    # ... existing fields ...

    # NEW: Evidence Map storage
    evidence_map: Optional[EvidenceMap] = None
    content_mode: Optional[ContentMode] = None
    constraint_warnings: list[str] = Field(default_factory=list)
```

---

## 6. RewriteResult

**Location**: `backend/src/models/rewrite_plan.py`

```python
class RewriteResult(BaseModel):
    """Result of a targeted rewrite pass."""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    pass_number: int
    sections_rewritten: int
    issues_addressed: int
    before_draft_hash: str
    after_draft_hash: str
    diffs: list["SectionDiff"] = Field(default_factory=list)
    faithfulness_preserved: bool = True
    warnings: list[str] = Field(default_factory=list)

class SectionDiff(BaseModel):
    """Diff for a single rewritten section."""

    model_config = ConfigDict(extra="forbid")

    section_id: str
    heading: Optional[str] = None
    original: str
    rewritten: str
    changes_summary: str
```

---

## 7. Project Model Update

**Location**: `backend/src/models/project.py` (modify existing)

```python
class Project(BaseModel):
    # ... existing fields ...

    # NEW: Evidence Map persistence (Spec 009 FR-007a)
    evidenceMap: Optional[EvidenceMap] = Field(
        default=None,
        description="Evidence Map from last generation, persisted for debugging and rewrite"
    )
```

**Why persist?**
- Job store is TTL'd (1 hour) - Evidence Map would disappear
- Users need to see evidence grounding after generation
- Rewrite feature needs Evidence Map to enforce "no new claims"
- Debugging: trace any claim back to transcript

---

## Relationships

```
Project
├── styleConfig (with content_mode, strict_grounded)
├── draftText
├── qaReport (from Spec 008)
├── evidenceMap (NEW - persisted for rewrite and debugging)
└── [via generation job]
    └── evidence_map (also in job during generation)

GenerationJob
├── draft_plan
├── visual_plan
├── evidence_map (NEW - copied to Project on completion)
└── chapters_completed

QAReport + EvidenceMap → RewritePlan → RewriteResult
```

---

## Migration Notes

### Existing Projects
- Projects without `content_mode` default to `"interview"`
- Projects without `strict_grounded` default to `True`
- No data migration needed (additive fields with defaults)

### StyleConfig Version
- Increment `STYLE_CONFIG_VERSION` to 2
- Add migration in `style_config_migrations.py` if needed
