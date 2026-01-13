# Editions Feature Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add "Editions" feature with Q&A Edition (faithful interview) and Ideas Edition (thematic chapters with synthesized prose).

**Architecture:** Edition selector in Tab 1 controls output format. Q&A Edition uses existing generation flow with Fidelity toggle. Ideas Edition adds theme proposal workflow (AI proposes → user edits → per-theme generation with quote validation).

**Tech Stack:** Python 3.11, FastAPI, Pydantic v2, MongoDB, React 19, TypeScript, Tailwind CSS, OpenAI embeddings

---

## Phase 1: Backend Models & Enums

### Task 1: Add Edition and Fidelity Enums

**Files:**
- Create: `backend/src/models/edition.py`
- Modify: `backend/src/models/__init__.py`
- Test: `backend/tests/unit/test_edition_models.py`

**Step 1: Write the failing test**

```python
# backend/tests/unit/test_edition_models.py
"""Tests for Edition models."""

import pytest
from src.models.edition import Edition, Fidelity, Coverage


class TestEditionEnum:
    def test_edition_values(self):
        assert Edition.QA.value == "qa"
        assert Edition.IDEAS.value == "ideas"

    def test_edition_from_string(self):
        assert Edition("qa") == Edition.QA
        assert Edition("ideas") == Edition.IDEAS


class TestFidelityEnum:
    def test_fidelity_values(self):
        assert Fidelity.FAITHFUL.value == "faithful"
        assert Fidelity.VERBATIM.value == "verbatim"


class TestCoverageEnum:
    def test_coverage_values(self):
        assert Coverage.STRONG.value == "strong"
        assert Coverage.MEDIUM.value == "medium"
        assert Coverage.WEAK.value == "weak"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_edition_models.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'src.models.edition'"

**Step 3: Write minimal implementation**

```python
# backend/src/models/edition.py
"""Edition-related enums and models."""

from enum import Enum


class Edition(str, Enum):
    """Output edition type."""
    QA = "qa"
    IDEAS = "ideas"


class Fidelity(str, Enum):
    """Fidelity level for Q&A Edition."""
    FAITHFUL = "faithful"
    VERBATIM = "verbatim"


class Coverage(str, Enum):
    """Theme coverage strength."""
    STRONG = "strong"
    MEDIUM = "medium"
    WEAK = "weak"
```

**Step 4: Update models __init__.py**

```python
# Add to backend/src/models/__init__.py
from .edition import Edition, Fidelity, Coverage
```

**Step 5: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/unit/test_edition_models.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add backend/src/models/edition.py backend/src/models/__init__.py backend/tests/unit/test_edition_models.py
git commit -m "feat(editions): Add Edition, Fidelity, Coverage enums"
```

---

### Task 2: Add SegmentRef and Theme Models

**Files:**
- Modify: `backend/src/models/edition.py`
- Test: `backend/tests/unit/test_edition_models.py`

**Step 1: Add tests for SegmentRef and Theme**

```python
# Add to backend/tests/unit/test_edition_models.py
from src.models.edition import SegmentRef, Theme


class TestSegmentRef:
    def test_segment_ref_creation(self):
        seg = SegmentRef(
            start_offset=100,
            end_offset=200,
            token_count=25,
            text_preview="This is a preview..."
        )
        assert seg.start_offset == 100
        assert seg.end_offset == 200
        assert seg.token_count == 25
        assert seg.text_preview == "This is a preview..."

    def test_segment_ref_validation(self):
        with pytest.raises(ValueError):
            SegmentRef(
                start_offset=-1,  # Invalid
                end_offset=100,
                token_count=10,
                text_preview="test"
            )


class TestTheme:
    def test_theme_creation(self):
        theme = Theme(
            id="theme-1",
            title="The Nature of Knowledge",
            one_liner="How knowledge grows through conjecture",
            keywords=["epistemology", "Popper"],
            coverage=Coverage.STRONG,
            supporting_segments=[],
            include_in_generation=True
        )
        assert theme.id == "theme-1"
        assert theme.coverage == Coverage.STRONG
        assert theme.include_in_generation is True

    def test_theme_defaults(self):
        theme = Theme(
            id="theme-2",
            title="Test Theme",
            one_liner="A test",
            keywords=[],
            coverage=Coverage.WEAK,
            supporting_segments=[]
        )
        assert theme.include_in_generation is True  # Default
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_edition_models.py::TestSegmentRef -v`
Expected: FAIL with "cannot import name 'SegmentRef'"

**Step 3: Add SegmentRef and Theme models**

```python
# Add to backend/src/models/edition.py
from pydantic import BaseModel, Field
from typing import Annotated


class SegmentRef(BaseModel):
    """Reference to a transcript segment."""
    start_offset: Annotated[int, Field(ge=0)]
    end_offset: Annotated[int, Field(ge=0)]
    token_count: Annotated[int, Field(ge=0)]
    text_preview: str  # First ~100 chars for display


class Theme(BaseModel):
    """A theme/chapter for Ideas Edition."""
    id: str
    title: str
    one_liner: str
    keywords: list[str]
    coverage: Coverage
    supporting_segments: list[SegmentRef]
    include_in_generation: bool = True
```

**Step 4: Update __init__.py export**

```python
# Update backend/src/models/__init__.py
from .edition import Edition, Fidelity, Coverage, SegmentRef, Theme
```

**Step 5: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/unit/test_edition_models.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add backend/src/models/edition.py backend/src/models/__init__.py backend/tests/unit/test_edition_models.py
git commit -m "feat(editions): Add SegmentRef and Theme models"
```

---

### Task 3: Update Project Model with Edition Fields

**Files:**
- Modify: `backend/src/models/project.py`
- Test: `backend/tests/unit/test_edition_models.py`

**Step 1: Add tests for Project edition fields**

```python
# Add to backend/tests/unit/test_edition_models.py
from src.models.project import Project
from datetime import datetime


class TestProjectEditionFields:
    def test_project_has_edition_defaults(self):
        project = Project(
            id="proj-1",
            name="Test Project",
            webinarType="interview",
            createdAt=datetime.now(),
            updatedAt=datetime.now()
        )
        assert project.edition == Edition.QA
        assert project.fidelity == Fidelity.FAITHFUL
        assert project.themes == []
        assert project.canonical_transcript is None
        assert project.canonical_transcript_hash is None

    def test_project_with_ideas_edition(self):
        theme = Theme(
            id="t1",
            title="Test",
            one_liner="Test",
            keywords=[],
            coverage=Coverage.MEDIUM,
            supporting_segments=[]
        )
        project = Project(
            id="proj-2",
            name="Ideas Project",
            webinarType="interview",
            createdAt=datetime.now(),
            updatedAt=datetime.now(),
            edition=Edition.IDEAS,
            themes=[theme],
            canonical_transcript="The canonical text",
            canonical_transcript_hash="abc123"
        )
        assert project.edition == Edition.IDEAS
        assert len(project.themes) == 1
        assert project.canonical_transcript == "The canonical text"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_edition_models.py::TestProjectEditionFields -v`
Expected: FAIL (Project doesn't have edition field)

**Step 3: Update Project model**

Add to `backend/src/models/project.py`:

```python
# Add import at top
from .edition import Edition, Fidelity, Theme

# Add fields to Project class (after qaReport field, around line 144):
    edition: Edition = Edition.QA
    fidelity: Fidelity = Fidelity.FAITHFUL
    themes: list[Theme] = []
    canonical_transcript: str | None = None
    canonical_transcript_hash: str | None = None
```

Also update `UpdateProjectRequest` to include edition fields:

```python
# Add to UpdateProjectRequest class:
    edition: Edition | None = None
    fidelity: Fidelity | None = None
    themes: list[Theme] | None = None
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/unit/test_edition_models.py::TestProjectEditionFields -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/models/project.py backend/tests/unit/test_edition_models.py
git commit -m "feat(editions): Add edition fields to Project model"
```

---

## Phase 2: Canonical Transcript Service

### Task 4: Create Canonical Transcript Service

**Files:**
- Create: `backend/src/services/canonical_service.py`
- Modify: `backend/src/services/__init__.py`
- Test: `backend/tests/unit/test_canonical_service.py`

**Step 1: Write failing tests**

```python
# backend/tests/unit/test_canonical_service.py
"""Tests for canonical transcript service."""

import pytest
from src.services.canonical_service import (
    canonicalize,
    normalize_for_comparison,
    compute_hash,
    verify_canonical,
)


class TestCanonicalize:
    def test_collapses_whitespace(self):
        text = "Hello    world\n\ntest"
        result = canonicalize(text)
        assert result == "Hello world test"

    def test_normalizes_quotes(self):
        text = '"smart quotes" and "regular"'
        result = canonicalize(text)
        assert result == '"smart quotes" and "regular"'

    def test_normalizes_dashes(self):
        text = "em—dash and en–dash"
        result = canonicalize(text)
        assert result == "em-dash and en-dash"

    def test_strips_whitespace(self):
        text = "  padded text  "
        result = canonicalize(text)
        assert result == "padded text"


class TestNormalizeForComparison:
    def test_lowercase(self):
        text = "Hello World"
        result = normalize_for_comparison(text)
        assert result == "hello world"

    def test_combined_normalization(self):
        text = '  "HELLO"   World  '
        result = normalize_for_comparison(text)
        assert result == '"hello" world'


class TestComputeHash:
    def test_hash_is_sha256(self):
        text = "test"
        result = compute_hash(text)
        assert len(result) == 64  # SHA256 hex length

    def test_same_input_same_hash(self):
        text = "hello world"
        assert compute_hash(text) == compute_hash(text)

    def test_different_input_different_hash(self):
        assert compute_hash("hello") != compute_hash("world")


class TestVerifyCanonical:
    def test_matching_hash_returns_true(self):
        transcript = "Hello world"
        canonical = canonicalize(transcript)
        hash_val = compute_hash(canonical)
        assert verify_canonical(transcript, hash_val) is True

    def test_modified_transcript_returns_false(self):
        original = "Hello world"
        canonical = canonicalize(original)
        hash_val = compute_hash(canonical)
        modified = "Hello world MODIFIED"
        assert verify_canonical(modified, hash_val) is False
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_canonical_service.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Implement canonical service**

```python
# backend/src/services/canonical_service.py
"""Canonical transcript service for stable offsets.

Provides text normalization and hashing for Ideas Edition
to ensure SegmentRef offsets remain valid.
"""

import hashlib
import re


def canonicalize(text: str) -> str:
    """Normalize text for consistent character offsets.

    - Collapse multiple whitespace to single space
    - Normalize smart quotes to straight quotes
    - Normalize em/en dashes to hyphens
    - Strip leading/trailing whitespace

    Args:
        text: Raw transcript text

    Returns:
        Canonicalized text suitable for offset references
    """
    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text)

    # Normalize quotes
    text = text.replace('"', '"').replace('"', '"')
    text = text.replace(''', "'").replace(''', "'")

    # Normalize dashes
    text = text.replace('—', '-').replace('–', '-')

    return text.strip()


def normalize_for_comparison(text: str) -> str:
    """Normalize text for fuzzy comparison.

    Applies canonicalization plus lowercase for matching.

    Args:
        text: Text to normalize

    Returns:
        Normalized text for comparison
    """
    return canonicalize(text).lower()


def compute_hash(text: str) -> str:
    """Compute SHA256 hash of text.

    Args:
        text: Text to hash (should be canonicalized)

    Returns:
        Hex-encoded SHA256 hash
    """
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def verify_canonical(transcript: str, stored_hash: str) -> bool:
    """Verify transcript matches stored canonical hash.

    Args:
        transcript: Current transcript text
        stored_hash: Previously computed hash

    Returns:
        True if transcript (when canonicalized) matches hash
    """
    canonical = canonicalize(transcript)
    current_hash = compute_hash(canonical)
    return current_hash == stored_hash
```

**Step 4: Update services __init__.py**

```python
# Add to backend/src/services/__init__.py
from . import canonical_service
```

**Step 5: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/unit/test_canonical_service.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add backend/src/services/canonical_service.py backend/src/services/__init__.py backend/tests/unit/test_canonical_service.py
git commit -m "feat(editions): Add canonical transcript service"
```

---

## Phase 3: Coverage Scoring Service

### Task 5: Create Coverage Scoring Service

**Files:**
- Create: `backend/src/services/coverage_service.py`
- Test: `backend/tests/unit/test_coverage_service.py`

**Step 1: Write failing tests**

```python
# backend/tests/unit/test_coverage_service.py
"""Tests for coverage scoring service."""

import pytest
from src.models.edition import Coverage, SegmentRef
from src.services.coverage_service import (
    score_coverage,
    calculate_spread,
)


def make_segment(start: int, end: int, tokens: int) -> SegmentRef:
    """Helper to create SegmentRef."""
    return SegmentRef(
        start_offset=start,
        end_offset=end,
        token_count=tokens,
        text_preview="preview..."
    )


class TestCalculateSpread:
    def test_single_segment_low_spread(self):
        segments = [make_segment(0, 100, 25)]
        spread = calculate_spread(segments, transcript_length=10000)
        assert spread < 0.3

    def test_distributed_segments_high_spread(self):
        segments = [
            make_segment(0, 100, 25),
            make_segment(3000, 3100, 25),
            make_segment(6000, 6100, 25),
            make_segment(9000, 9100, 25),
        ]
        spread = calculate_spread(segments, transcript_length=10000)
        assert spread > 0.7


class TestScoreCoverage:
    def test_strong_coverage(self):
        # 5+ segments, 500+ tokens, good spread
        segments = [
            make_segment(i * 2000, i * 2000 + 200, 120)
            for i in range(5)
        ]
        result = score_coverage(segments, transcript_length=10000)
        assert result == Coverage.STRONG

    def test_medium_coverage(self):
        # 3 segments, 300 tokens
        segments = [
            make_segment(i * 1000, i * 1000 + 100, 100)
            for i in range(3)
        ]
        result = score_coverage(segments, transcript_length=10000)
        assert result == Coverage.MEDIUM

    def test_weak_coverage(self):
        # 1 segment, few tokens
        segments = [make_segment(0, 50, 20)]
        result = score_coverage(segments, transcript_length=10000)
        assert result == Coverage.WEAK

    def test_empty_segments_is_weak(self):
        result = score_coverage([], transcript_length=10000)
        assert result == Coverage.WEAK
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_coverage_service.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Implement coverage service**

```python
# backend/src/services/coverage_service.py
"""Coverage scoring for theme supporting segments.

Deterministic scoring based on:
- Number of supporting segments
- Total token count
- Spread across transcript (distribution)
"""

from src.models.edition import Coverage, SegmentRef


def calculate_spread(segments: list[SegmentRef], transcript_length: int) -> float:
    """Calculate how well-distributed segments are across transcript.

    Args:
        segments: List of segment references
        transcript_length: Total length of transcript in chars

    Returns:
        Spread score from 0.0 (clustered) to 1.0 (evenly distributed)
    """
    if not segments or transcript_length <= 0:
        return 0.0

    if len(segments) == 1:
        # Single segment can't be well-distributed
        return 0.1

    # Get midpoints of each segment
    midpoints = sorted([
        (s.start_offset + s.end_offset) / 2
        for s in segments
    ])

    # Calculate gaps between consecutive midpoints
    gaps = [
        midpoints[i + 1] - midpoints[i]
        for i in range(len(midpoints) - 1)
    ]

    # Ideal gap for even distribution
    ideal_gap = transcript_length / (len(segments) + 1)

    # Score based on how close gaps are to ideal
    if ideal_gap <= 0:
        return 0.0

    gap_scores = [
        min(gap / ideal_gap, ideal_gap / gap) if gap > 0 else 0.0
        for gap in gaps
    ]

    return sum(gap_scores) / len(gap_scores) if gap_scores else 0.0


def score_coverage(segments: list[SegmentRef], transcript_length: int) -> Coverage:
    """Score theme coverage based on supporting segments.

    Scoring formula:
    - 40% weight: number of segments (up to 5)
    - 40% weight: total tokens (up to 500)
    - 20% weight: spread across transcript

    Args:
        segments: Supporting segment references
        transcript_length: Total transcript length in chars

    Returns:
        Coverage level (STRONG, MEDIUM, or WEAK)
    """
    if not segments:
        return Coverage.WEAK

    num_segments = len(segments)
    total_tokens = sum(s.token_count for s in segments)
    spread = calculate_spread(segments, transcript_length)

    score = (
        min(num_segments / 5, 1.0) * 0.4 +
        min(total_tokens / 500, 1.0) * 0.4 +
        spread * 0.2
    )

    if score >= 0.7:
        return Coverage.STRONG
    elif score >= 0.4:
        return Coverage.MEDIUM
    else:
        return Coverage.WEAK
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/unit/test_coverage_service.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/services/coverage_service.py backend/tests/unit/test_coverage_service.py
git commit -m "feat(editions): Add coverage scoring service"
```

---

## Phase 4: Theme Proposal Service

### Task 6: Create Theme Job Store

**Files:**
- Create: `backend/src/models/theme_job.py`
- Create: `backend/src/services/theme_job_store.py`
- Modify: `backend/src/models/__init__.py`
- Test: `backend/tests/unit/test_theme_job_store.py`

**Step 1: Write failing tests**

```python
# backend/tests/unit/test_theme_job_store.py
"""Tests for theme job store."""

import pytest
from src.models.theme_job import ThemeJob, ThemeJobStatus
from src.services.theme_job_store import InMemoryThemeJobStore


@pytest.fixture
def store():
    return InMemoryThemeJobStore()


class TestThemeJobStore:
    @pytest.mark.asyncio
    async def test_create_job(self, store):
        job_id = await store.create_job(project_id="proj-1")
        assert job_id is not None

    @pytest.mark.asyncio
    async def test_get_job(self, store):
        job_id = await store.create_job(project_id="proj-1")
        job = await store.get_job(job_id)
        assert job is not None
        assert job.job_id == job_id
        assert job.status == ThemeJobStatus.QUEUED

    @pytest.mark.asyncio
    async def test_update_job(self, store):
        job_id = await store.create_job(project_id="proj-1")
        updated = await store.update_job(job_id, status=ThemeJobStatus.COMPLETED)
        assert updated.status == ThemeJobStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_get_nonexistent_job(self, store):
        job = await store.get_job("nonexistent")
        assert job is None
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_theme_job_store.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Create ThemeJob model**

```python
# backend/src/models/theme_job.py
"""Theme proposal job model."""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel

from .edition import Theme


class ThemeJobStatus(str, Enum):
    """Status of theme proposal job."""
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ThemeJob(BaseModel):
    """Theme proposal job."""
    job_id: str
    project_id: str
    status: ThemeJobStatus = ThemeJobStatus.QUEUED
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    themes: list[Theme] = []
    error: Optional[str] = None

    def is_terminal(self) -> bool:
        return self.status in (
            ThemeJobStatus.COMPLETED,
            ThemeJobStatus.FAILED,
            ThemeJobStatus.CANCELLED
        )
```

**Step 4: Create theme job store**

```python
# backend/src/services/theme_job_store.py
"""Theme job store for proposal jobs."""

import asyncio
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from src.models.theme_job import ThemeJob, ThemeJobStatus


class InMemoryThemeJobStore:
    """In-memory store for theme proposal jobs."""

    def __init__(self):
        self._jobs: dict[str, ThemeJob] = {}
        self._lock = asyncio.Lock()

    async def create_job(self, project_id: str) -> str:
        job_id = str(uuid4())
        job = ThemeJob(
            job_id=job_id,
            project_id=project_id,
            status=ThemeJobStatus.QUEUED,
            created_at=datetime.now(timezone.utc),
        )
        async with self._lock:
            self._jobs[job_id] = job
        return job_id

    async def get_job(self, job_id: str) -> Optional[ThemeJob]:
        async with self._lock:
            return self._jobs.get(job_id)

    async def update_job(self, job_id: str, **updates) -> Optional[ThemeJob]:
        async with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None

            for key, value in updates.items():
                if hasattr(job, key):
                    setattr(job, key, value)

            if updates.get("status") == ThemeJobStatus.PROCESSING:
                job.started_at = datetime.now(timezone.utc)
            if updates.get("status") in (
                ThemeJobStatus.COMPLETED,
                ThemeJobStatus.FAILED,
                ThemeJobStatus.CANCELLED,
            ):
                job.completed_at = datetime.now(timezone.utc)

            return job

    async def delete_job(self, job_id: str) -> bool:
        async with self._lock:
            if job_id in self._jobs:
                del self._jobs[job_id]
                return True
            return False


# Singleton instance
_store: Optional[InMemoryThemeJobStore] = None


def get_theme_job_store() -> InMemoryThemeJobStore:
    global _store
    if _store is None:
        _store = InMemoryThemeJobStore()
    return _store
```

**Step 5: Update __init__.py exports**

```python
# Add to backend/src/models/__init__.py
from .theme_job import ThemeJob, ThemeJobStatus
```

**Step 6: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/unit/test_theme_job_store.py -v`
Expected: PASS

**Step 7: Commit**

```bash
git add backend/src/models/theme_job.py backend/src/services/theme_job_store.py backend/src/models/__init__.py backend/tests/unit/test_theme_job_store.py
git commit -m "feat(editions): Add theme job store"
```

---

### Task 7: Create Theme Proposal API Route

**Files:**
- Create: `backend/src/api/routes/themes.py`
- Modify: `backend/src/api/main.py`
- Test: `backend/tests/unit/test_theme_api.py`

**Step 1: Write failing tests**

```python
# backend/tests/unit/test_theme_api.py
"""Tests for theme proposal API."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock


@pytest.fixture
def client():
    from src.api.main import app
    return TestClient(app)


class TestProposeThemesEndpoint:
    def test_propose_themes_returns_job_id(self, client):
        response = client.post(
            "/api/ai/themes/propose",
            json={"project_id": "proj-123"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "job_id" in data["data"]

    def test_propose_themes_requires_project_id(self, client):
        response = client.post("/api/ai/themes/propose", json={})
        assert response.status_code == 422


class TestThemeStatusEndpoint:
    def test_status_not_found(self, client):
        response = client.get("/api/ai/themes/status/nonexistent")
        assert response.status_code == 404
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_theme_api.py -v`
Expected: FAIL (route doesn't exist)

**Step 3: Create themes route**

```python
# backend/src/api/routes/themes.py
"""Theme proposal API endpoints."""

from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.api.response import success_response, error_response
from src.services.theme_job_store import get_theme_job_store
from src.models.theme_job import ThemeJobStatus


router = APIRouter(prefix="/ai/themes", tags=["Themes"])


class ProposeThemesRequest(BaseModel):
    project_id: str
    existing_themes: list[dict] = []


class ProposeThemesResponse(BaseModel):
    job_id: str
    status: str


@router.post("/propose")
async def propose_themes(
    request: ProposeThemesRequest,
    background_tasks: BackgroundTasks
) -> dict:
    """Start async theme proposal job.

    Analyzes transcript and proposes thematic chapters.
    """
    store = get_theme_job_store()
    job_id = await store.create_job(project_id=request.project_id)

    # TODO: Add background task for actual theme proposal
    # background_tasks.add_task(run_theme_proposal, job_id, request)

    return success_response({
        "job_id": job_id,
        "status": "queued"
    })


@router.get("/status/{job_id}")
async def get_theme_status(job_id: str) -> dict:
    """Get theme proposal job status."""
    store = get_theme_job_store()
    job = await store.get_job(job_id)

    if not job:
        return JSONResponse(
            status_code=404,
            content=error_response("JOB_NOT_FOUND", f"Job {job_id} not found")
        )

    return success_response({
        "job_id": job.job_id,
        "status": job.status.value,
        "themes": [t.model_dump() for t in job.themes] if job.themes else [],
        "error": job.error
    })


@router.post("/cancel/{job_id}")
async def cancel_theme_job(job_id: str) -> dict:
    """Cancel a theme proposal job."""
    store = get_theme_job_store()
    job = await store.get_job(job_id)

    if not job:
        return JSONResponse(
            status_code=404,
            content=error_response("JOB_NOT_FOUND", f"Job {job_id} not found")
        )

    if job.is_terminal():
        return success_response({
            "job_id": job_id,
            "cancelled": False,
            "message": "Job already completed"
        })

    await store.update_job(job_id, status=ThemeJobStatus.CANCELLED)

    return success_response({
        "job_id": job_id,
        "cancelled": True
    })
```

**Step 4: Register route in main.py**

```python
# Add to backend/src/api/main.py (with other route imports)
from src.api.routes.themes import router as themes_router

# Add to router registration section:
app.include_router(themes_router, prefix="/api")
```

**Step 5: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/unit/test_theme_api.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add backend/src/api/routes/themes.py backend/src/api/main.py backend/tests/unit/test_theme_api.py
git commit -m "feat(editions): Add theme proposal API endpoints"
```

---

## Phase 5: Frontend Types & Context

### Task 8: Add Edition Types to Frontend

**Files:**
- Modify: `frontend/src/types/project.ts`
- Create: `frontend/src/types/edition.ts`
- Test: `frontend/tests/unit/edition.test.ts`

**Step 1: Write failing test**

```typescript
// frontend/tests/unit/edition.test.ts
import { describe, it, expect } from 'vitest'
import type { Edition, Fidelity, Theme, Coverage } from '../../src/types/edition'

describe('Edition Types', () => {
  it('should have valid edition values', () => {
    const qa: Edition = 'qa'
    const ideas: Edition = 'ideas'
    expect(qa).toBe('qa')
    expect(ideas).toBe('ideas')
  })

  it('should have valid fidelity values', () => {
    const faithful: Fidelity = 'faithful'
    const verbatim: Fidelity = 'verbatim'
    expect(faithful).toBe('faithful')
    expect(verbatim).toBe('verbatim')
  })

  it('should have valid coverage values', () => {
    const coverage: Coverage = 'strong'
    expect(['strong', 'medium', 'weak']).toContain(coverage)
  })
})
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- tests/unit/edition.test.ts`
Expected: FAIL (module not found)

**Step 3: Create edition types**

```typescript
// frontend/src/types/edition.ts
/**
 * Edition types for output format selection.
 */

export type Edition = 'qa' | 'ideas'

export type Fidelity = 'faithful' | 'verbatim'

export type Coverage = 'strong' | 'medium' | 'weak'

export interface SegmentRef {
  start_offset: number
  end_offset: number
  token_count: number
  text_preview: string
}

export interface Theme {
  id: string
  title: string
  oneLiner: string
  keywords: string[]
  coverage: Coverage
  supportingSegments: SegmentRef[]
  includeInGeneration: boolean
}

export const EDITION_LABELS: Record<Edition, string> = {
  qa: 'Q&A Edition',
  ideas: 'Ideas Edition',
}

export const EDITION_DESCRIPTIONS: Record<Edition, string> = {
  qa: 'Faithful interview format with speaker labels',
  ideas: 'Thematic chapters with synthesized prose',
}

export const FIDELITY_LABELS: Record<Fidelity, string> = {
  faithful: 'Faithful (cleaned)',
  verbatim: 'Verbatim (strict)',
}

export const COVERAGE_COLORS: Record<Coverage, string> = {
  strong: 'text-green-600 bg-green-100',
  medium: 'text-yellow-600 bg-yellow-100',
  weak: 'text-red-600 bg-red-100',
}
```

**Step 4: Update project.ts to include edition fields**

```typescript
// Add to frontend/src/types/project.ts

// Add import at top:
import type { Edition, Fidelity, Theme } from './edition'

// Re-export edition types:
export type { Edition, Fidelity, Theme, Coverage, SegmentRef } from './edition'

// Update Project interface (add after creditsText):
export interface Project {
  // ... existing fields ...

  // Edition fields
  edition: Edition
  fidelity: Fidelity
  themes: Theme[]
  canonicalTranscript: string | null
  canonicalTranscriptHash: string | null
}

// Update INITIAL_STATE and DEFAULT values as needed
```

**Step 5: Run test to verify it passes**

Run: `cd frontend && npm test -- tests/unit/edition.test.ts`
Expected: PASS

**Step 6: Commit**

```bash
git add frontend/src/types/edition.ts frontend/src/types/project.ts frontend/tests/unit/edition.test.ts
git commit -m "feat(editions): Add Edition types to frontend"
```

---

### Task 9: Update ProjectContext for Edition State

**Files:**
- Modify: `frontend/src/context/ProjectContext.tsx`
- Test: `frontend/tests/unit/projectReducer.test.ts`

**Step 1: Write failing test**

```typescript
// Add to frontend/tests/unit/projectReducer.test.ts (or create new file)
import { describe, it, expect } from 'vitest'
import { projectReducer, INITIAL_STATE } from '../../src/context/ProjectContext'
import type { Edition, Fidelity } from '../../src/types/edition'

describe('Edition Actions', () => {
  it('should update edition', () => {
    const state = { ...INITIAL_STATE, project: { ...mockProject, edition: 'qa' as Edition } }
    const action = { type: 'SET_EDITION' as const, payload: 'ideas' as Edition }
    const result = projectReducer(state, action)
    expect(result.project?.edition).toBe('ideas')
  })

  it('should update fidelity', () => {
    const state = { ...INITIAL_STATE, project: { ...mockProject, fidelity: 'faithful' as Fidelity } }
    const action = { type: 'SET_FIDELITY' as const, payload: 'verbatim' as Fidelity }
    const result = projectReducer(state, action)
    expect(result.project?.fidelity).toBe('verbatim')
  })

  it('should set themes', () => {
    const themes = [{ id: 't1', title: 'Test', oneLiner: 'Test', keywords: [], coverage: 'strong' as const, supportingSegments: [], includeInGeneration: true }]
    const state = { ...INITIAL_STATE, project: mockProject }
    const action = { type: 'SET_THEMES' as const, payload: themes }
    const result = projectReducer(state, action)
    expect(result.project?.themes).toEqual(themes)
  })
})
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- tests/unit/projectReducer.test.ts`
Expected: FAIL (SET_EDITION action not handled)

**Step 3: Add edition actions to ProjectContext**

Add to `frontend/src/types/project.ts` (ProjectAction type):

```typescript
// Add to ProjectAction union type:
  | { type: 'SET_EDITION'; payload: Edition }
  | { type: 'SET_FIDELITY'; payload: Fidelity }
  | { type: 'SET_THEMES'; payload: Theme[] }
  | { type: 'UPDATE_THEME'; payload: { id: string; updates: Partial<Theme> } }
  | { type: 'REMOVE_THEME'; payload: string }
  | { type: 'REORDER_THEMES'; payload: string[] }
```

Add to `frontend/src/context/ProjectContext.tsx` (reducer):

```typescript
// Add cases to projectReducer:
case 'SET_EDITION':
  if (!state.project) return state
  return {
    ...state,
    project: { ...state.project, edition: action.payload }
  }

case 'SET_FIDELITY':
  if (!state.project) return state
  return {
    ...state,
    project: { ...state.project, fidelity: action.payload }
  }

case 'SET_THEMES':
  if (!state.project) return state
  return {
    ...state,
    project: { ...state.project, themes: action.payload }
  }

case 'UPDATE_THEME':
  if (!state.project) return state
  return {
    ...state,
    project: {
      ...state.project,
      themes: state.project.themes.map(t =>
        t.id === action.payload.id
          ? { ...t, ...action.payload.updates }
          : t
      )
    }
  }

case 'REMOVE_THEME':
  if (!state.project) return state
  return {
    ...state,
    project: {
      ...state.project,
      themes: state.project.themes.filter(t => t.id !== action.payload)
    }
  }

case 'REORDER_THEMES':
  if (!state.project) return state
  const themeMap = new Map(state.project.themes.map(t => [t.id, t]))
  return {
    ...state,
    project: {
      ...state.project,
      themes: action.payload.map(id => themeMap.get(id)!).filter(Boolean)
    }
  }
```

**Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- tests/unit/projectReducer.test.ts`
Expected: PASS

**Step 5: Commit**

```bash
git add frontend/src/types/project.ts frontend/src/context/ProjectContext.tsx frontend/tests/unit/projectReducer.test.ts
git commit -m "feat(editions): Add edition actions to ProjectContext"
```

---

## Phase 6: Frontend Components

### Task 10: Create EditionSelector Component

**Files:**
- Create: `frontend/src/components/tab1/EditionSelector.tsx`
- Test: `frontend/tests/component/EditionSelector.test.tsx`

**Step 1: Write failing test**

```typescript
// frontend/tests/component/EditionSelector.test.tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { EditionSelector } from '../../src/components/tab1/EditionSelector'

describe('EditionSelector', () => {
  it('renders both edition options', () => {
    const onChange = vi.fn()
    render(<EditionSelector value="qa" onChange={onChange} />)

    expect(screen.getByText('Q&A Edition')).toBeInTheDocument()
    expect(screen.getByText('Ideas Edition')).toBeInTheDocument()
  })

  it('shows selected edition', () => {
    const onChange = vi.fn()
    render(<EditionSelector value="qa" onChange={onChange} />)

    const qaRadio = screen.getByRole('radio', { name: /Q&A Edition/i })
    expect(qaRadio).toBeChecked()
  })

  it('calls onChange when selection changes', () => {
    const onChange = vi.fn()
    render(<EditionSelector value="qa" onChange={onChange} />)

    const ideasRadio = screen.getByRole('radio', { name: /Ideas Edition/i })
    fireEvent.click(ideasRadio)

    expect(onChange).toHaveBeenCalledWith('ideas')
  })

  it('shows recommendation hint when provided', () => {
    const onChange = vi.fn()
    render(
      <EditionSelector
        value="qa"
        onChange={onChange}
        recommendedEdition="qa"
      />
    )

    expect(screen.getByText(/recommended/i)).toBeInTheDocument()
  })
})
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- tests/component/EditionSelector.test.tsx`
Expected: FAIL (component doesn't exist)

**Step 3: Create EditionSelector component**

```typescript
// frontend/src/components/tab1/EditionSelector.tsx
import type { Edition } from '../../types/edition'
import { EDITION_LABELS, EDITION_DESCRIPTIONS } from '../../types/edition'

interface EditionSelectorProps {
  value: Edition
  onChange: (edition: Edition) => void
  recommendedEdition?: Edition
  disabled?: boolean
}

export function EditionSelector({
  value,
  onChange,
  recommendedEdition,
  disabled = false,
}: EditionSelectorProps) {
  const editions: Edition[] = ['qa', 'ideas']

  return (
    <div className="space-y-3">
      <label className="block text-sm font-medium text-gray-700">
        Output Edition
      </label>

      <div className="space-y-2">
        {editions.map((edition) => (
          <label
            key={edition}
            className={`
              relative flex items-start p-4 border rounded-lg cursor-pointer
              ${value === edition
                ? 'border-blue-500 bg-blue-50'
                : 'border-gray-200 hover:border-gray-300'
              }
              ${disabled ? 'opacity-50 cursor-not-allowed' : ''}
            `}
          >
            <input
              type="radio"
              name="edition"
              value={edition}
              checked={value === edition}
              onChange={() => onChange(edition)}
              disabled={disabled}
              className="h-4 w-4 mt-0.5 text-blue-600 border-gray-300 focus:ring-blue-500"
            />
            <div className="ml-3">
              <span className="block text-sm font-medium text-gray-900">
                {EDITION_LABELS[edition]}
              </span>
              <span className="block text-sm text-gray-500">
                {EDITION_DESCRIPTIONS[edition]}
              </span>
            </div>
          </label>
        ))}
      </div>

      {recommendedEdition && (
        <p className="text-sm text-gray-500">
          <span className="inline-flex items-center">
            <svg className="w-4 h-4 mr-1 text-blue-500" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
            </svg>
            Detected Q&A format — {EDITION_LABELS[recommendedEdition]} recommended.
          </span>
        </p>
      )}
    </div>
  )
}
```

**Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- tests/component/EditionSelector.test.tsx`
Expected: PASS

**Step 5: Commit**

```bash
git add frontend/src/components/tab1/EditionSelector.tsx frontend/tests/component/EditionSelector.test.tsx
git commit -m "feat(editions): Add EditionSelector component"
```

---

### Task 11: Create ThemesPanel Component

**Files:**
- Create: `frontend/src/components/tab1/ThemesPanel.tsx`
- Create: `frontend/src/components/tab1/ThemeRow.tsx`
- Test: `frontend/tests/component/ThemesPanel.test.tsx`

**Step 1: Write failing test**

```typescript
// frontend/tests/component/ThemesPanel.test.tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ThemesPanel } from '../../src/components/tab1/ThemesPanel'
import type { Theme } from '../../src/types/edition'

const mockThemes: Theme[] = [
  {
    id: 't1',
    title: 'The Nature of Knowledge',
    oneLiner: 'How knowledge grows',
    keywords: ['epistemology'],
    coverage: 'strong',
    supportingSegments: [],
    includeInGeneration: true,
  },
  {
    id: 't2',
    title: 'Progress Through Criticism',
    oneLiner: 'Error correction',
    keywords: ['criticism'],
    coverage: 'weak',
    supportingSegments: [],
    includeInGeneration: true,
  },
]

describe('ThemesPanel', () => {
  it('renders theme list', () => {
    render(
      <ThemesPanel
        themes={mockThemes}
        onProposeThemes={vi.fn()}
        onUpdateTheme={vi.fn()}
        onRemoveTheme={vi.fn()}
        onReorderThemes={vi.fn()}
      />
    )

    expect(screen.getByText('The Nature of Knowledge')).toBeInTheDocument()
    expect(screen.getByText('Progress Through Criticism')).toBeInTheDocument()
  })

  it('shows coverage badges', () => {
    render(
      <ThemesPanel
        themes={mockThemes}
        onProposeThemes={vi.fn()}
        onUpdateTheme={vi.fn()}
        onRemoveTheme={vi.fn()}
        onReorderThemes={vi.fn()}
      />
    )

    expect(screen.getByText('Strong')).toBeInTheDocument()
    expect(screen.getByText('Weak')).toBeInTheDocument()
  })

  it('shows weak coverage warning', () => {
    render(
      <ThemesPanel
        themes={mockThemes}
        onProposeThemes={vi.fn()}
        onUpdateTheme={vi.fn()}
        onRemoveTheme={vi.fn()}
        onReorderThemes={vi.fn()}
      />
    )

    expect(screen.getByText(/limited source material/i)).toBeInTheDocument()
  })

  it('calls onProposeThemes when button clicked', () => {
    const onProposeThemes = vi.fn()
    render(
      <ThemesPanel
        themes={[]}
        onProposeThemes={onProposeThemes}
        onUpdateTheme={vi.fn()}
        onRemoveTheme={vi.fn()}
        onReorderThemes={vi.fn()}
      />
    )

    fireEvent.click(screen.getByText('Propose Themes'))
    expect(onProposeThemes).toHaveBeenCalled()
  })
})
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- tests/component/ThemesPanel.test.tsx`
Expected: FAIL (component doesn't exist)

**Step 3: Create ThemeRow component**

```typescript
// frontend/src/components/tab1/ThemeRow.tsx
import type { Theme, Coverage } from '../../types/edition'
import { COVERAGE_COLORS } from '../../types/edition'

interface ThemeRowProps {
  theme: Theme
  onUpdate: (updates: Partial<Theme>) => void
  onRemove: () => void
}

const COVERAGE_LABELS: Record<Coverage, string> = {
  strong: 'Strong',
  medium: 'Medium',
  weak: 'Weak',
}

export function ThemeRow({ theme, onUpdate, onRemove }: ThemeRowProps) {
  return (
    <div className="flex items-start gap-3 p-3 bg-white border rounded-lg group">
      {/* Drag handle */}
      <div className="cursor-grab text-gray-400 hover:text-gray-600">
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8h16M4 16h16" />
        </svg>
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <h4 className="font-medium text-gray-900 truncate">{theme.title}</h4>
          <span className={`px-2 py-0.5 text-xs font-medium rounded ${COVERAGE_COLORS[theme.coverage]}`}>
            {COVERAGE_LABELS[theme.coverage]}
          </span>
        </div>
        <p className="text-sm text-gray-500 truncate">{theme.oneLiner}</p>
        {theme.coverage === 'weak' && (
          <p className="text-xs text-red-600 mt-1 flex items-center gap-1">
            <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
            </svg>
            Limited source material
          </p>
        )}
        <details className="mt-2">
          <summary className="text-xs text-gray-400 cursor-pointer hover:text-gray-600">
            {theme.supportingSegments.length} supporting segments
          </summary>
          <div className="mt-1 space-y-1">
            {theme.supportingSegments.slice(0, 3).map((seg, i) => (
              <p key={i} className="text-xs text-gray-500 truncate pl-2 border-l-2 border-gray-200">
                {seg.text_preview}
              </p>
            ))}
          </div>
        </details>
      </div>

      {/* Actions */}
      <button
        onClick={onRemove}
        className="opacity-0 group-hover:opacity-100 p-1 text-gray-400 hover:text-red-500"
        title="Remove theme"
      >
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  )
}
```

**Step 4: Create ThemesPanel component**

```typescript
// frontend/src/components/tab1/ThemesPanel.tsx
import { useState } from 'react'
import type { Theme } from '../../types/edition'
import { ThemeRow } from './ThemeRow'
import { Button } from '../common/Button'

interface ThemesPanelProps {
  themes: Theme[]
  onProposeThemes: () => void
  onAddSuggestions?: () => void
  onUpdateTheme: (id: string, updates: Partial<Theme>) => void
  onRemoveTheme: (id: string) => void
  onReorderThemes: (orderedIds: string[]) => void
  isProposing?: boolean
}

export function ThemesPanel({
  themes,
  onProposeThemes,
  onAddSuggestions,
  onUpdateTheme,
  onRemoveTheme,
  onReorderThemes,
  isProposing = false,
}: ThemesPanelProps) {
  const hasThemes = themes.length > 0

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-gray-700">
          Themes (chapter structure)
        </h3>
        <div className="flex gap-2">
          {hasThemes && onAddSuggestions && (
            <Button
              variant="secondary"
              size="sm"
              onClick={onAddSuggestions}
              disabled={isProposing}
            >
              Add Suggestions
            </Button>
          )}
          <Button
            variant={hasThemes ? 'secondary' : 'primary'}
            size="sm"
            onClick={onProposeThemes}
            disabled={isProposing}
          >
            {isProposing ? 'Proposing...' : hasThemes ? 'Repropose' : 'Propose Themes'}
          </Button>
        </div>
      </div>

      {!hasThemes && !isProposing && (
        <div className="text-center py-8 text-gray-500 border-2 border-dashed rounded-lg">
          <p>No themes yet.</p>
          <p className="text-sm">Click "Propose Themes" to analyze your transcript.</p>
        </div>
      )}

      {isProposing && (
        <div className="flex items-center justify-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
          <span className="ml-3 text-gray-600">Analyzing transcript...</span>
        </div>
      )}

      {hasThemes && (
        <div className="space-y-2">
          {themes.map((theme) => (
            <ThemeRow
              key={theme.id}
              theme={theme}
              onUpdate={(updates) => onUpdateTheme(theme.id, updates)}
              onRemove={() => onRemoveTheme(theme.id)}
            />
          ))}
        </div>
      )}
    </div>
  )
}
```

**Step 5: Run test to verify it passes**

Run: `cd frontend && npm test -- tests/component/ThemesPanel.test.tsx`
Expected: PASS

**Step 6: Commit**

```bash
git add frontend/src/components/tab1/ThemeRow.tsx frontend/src/components/tab1/ThemesPanel.tsx frontend/tests/component/ThemesPanel.test.tsx
git commit -m "feat(editions): Add ThemesPanel and ThemeRow components"
```

---

### Task 12: Update Tab1Content with Edition Selector

**Files:**
- Modify: `frontend/src/components/tab1/Tab1Content.tsx`
- Test: `frontend/tests/component/Tab1Content.test.tsx`

**Step 1: Write failing test**

```typescript
// Add to frontend/tests/component/Tab1Content.test.tsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Tab1Content } from '../../src/components/tab1/Tab1Content'
// Mock ProjectContext...

describe('Tab1Content Edition Integration', () => {
  it('shows edition selector', () => {
    // Render with mocked context where edition='qa'
    render(<Tab1Content />)
    expect(screen.getByText('Output Edition')).toBeInTheDocument()
  })

  it('shows outline for Q&A edition', () => {
    // Render with edition='qa'
    render(<Tab1Content />)
    expect(screen.getByText('Outline')).toBeInTheDocument()
  })

  it('shows themes panel for Ideas edition', () => {
    // Render with edition='ideas'
    render(<Tab1Content />)
    expect(screen.getByText(/Themes/)).toBeInTheDocument()
  })
})
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- tests/component/Tab1Content.test.tsx`
Expected: FAIL (edition selector not rendered)

**Step 3: Update Tab1Content**

```typescript
// frontend/src/components/tab1/Tab1Content.tsx
import { useProject } from '../../context/ProjectContext'
import { Card } from '../common/Card'
import { Button } from '../common/Button'
import { TranscriptEditor } from './TranscriptEditor'
import { OutlineEditor } from './OutlineEditor'
import { ResourceList } from './ResourceList'
import { AIAssistSection } from './AIAssistSection'
import { AIPreviewModal } from './AIPreviewModal'
import { EditionSelector } from './EditionSelector'
import { ThemesPanel } from './ThemesPanel'
import type { Edition } from '../../types/edition'

export function Tab1Content() {
  const { state, dispatch, uploadResourceFile, removeResourceFile } = useProject()
  const { project } = state

  if (!project) return null

  const handleEditionChange = (edition: Edition) => {
    dispatch({ type: 'SET_EDITION', payload: edition })
  }

  const handleTranscriptChange = (value: string) => {
    dispatch({ type: 'UPDATE_TRANSCRIPT', payload: value })
  }

  // ... existing handlers ...

  const handleProposeThemes = async () => {
    // TODO: Call theme proposal API
    console.log('Propose themes')
  }

  const handleUpdateTheme = (id: string, updates: Partial<import('../../types/edition').Theme>) => {
    dispatch({ type: 'UPDATE_THEME', payload: { id, updates } })
  }

  const handleRemoveTheme = (id: string) => {
    dispatch({ type: 'REMOVE_THEME', payload: id })
  }

  const handleReorderThemes = (orderedIds: string[]) => {
    dispatch({ type: 'REORDER_THEMES', payload: orderedIds })
  }

  const isIdeasEdition = project.edition === 'ideas'

  return (
    <div className="space-y-6">
      {/* Action buttons row */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <AIAssistSection />
        <Button variant="secondary" onClick={handleFillSampleData}>
          Fill with Sample Data
        </Button>
      </div>

      {/* AI Preview Modal */}
      <AIPreviewModal />

      {/* Edition Selector */}
      <Card title="Output Format">
        <EditionSelector
          value={project.edition}
          onChange={handleEditionChange}
          recommendedEdition="qa"  // TODO: Detect from transcript
        />
      </Card>

      {/* Transcript */}
      <Card title="Transcript">
        <TranscriptEditor value={project.transcriptText} onChange={handleTranscriptChange} />
      </Card>

      {/* Conditional: Outline (Q&A) or Themes (Ideas) */}
      {isIdeasEdition ? (
        <Card title="Themes">
          <ThemesPanel
            themes={project.themes}
            onProposeThemes={handleProposeThemes}
            onUpdateTheme={handleUpdateTheme}
            onRemoveTheme={handleRemoveTheme}
            onReorderThemes={handleReorderThemes}
          />
        </Card>
      ) : (
        <Card title="Outline">
          <p className="text-sm text-gray-500 mb-4">
            Optional: Used for topic grouping only. Won't change the interview content.
          </p>
          <OutlineEditor
            items={project.outlineItems}
            onAdd={handleAddOutlineItem}
            onUpdate={handleUpdateOutlineItem}
            onRemove={handleRemoveOutlineItem}
            onReorder={handleReorderOutlineItems}
          />
        </Card>
      )}

      {/* Resources */}
      <Card title="Resources">
        <ResourceList
          resources={project.resources}
          projectId={project.id}
          onAdd={handleAddResource}
          onUpdate={handleUpdateResource}
          onRemove={handleRemoveResource}
          onFileUpload={handleFileUpload}
          onFileRemove={handleFileRemove}
        />
      </Card>
    </div>
  )
}
```

**Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- tests/component/Tab1Content.test.tsx`
Expected: PASS

**Step 5: Commit**

```bash
git add frontend/src/components/tab1/Tab1Content.tsx frontend/tests/component/Tab1Content.test.tsx
git commit -m "feat(editions): Integrate EditionSelector into Tab1Content"
```

---

### Task 13: Add EditionMirror to Tab3Content

**Files:**
- Create: `frontend/src/components/tab3/EditionMirror.tsx`
- Modify: `frontend/src/components/tab3/Tab3Content.tsx`
- Test: `frontend/tests/component/EditionMirror.test.tsx`

**Step 1: Write failing test**

```typescript
// frontend/tests/component/EditionMirror.test.tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { EditionMirror } from '../../src/components/tab3/EditionMirror'

describe('EditionMirror', () => {
  it('shows edition name', () => {
    render(
      <EditionMirror
        edition="qa"
        fidelity="faithful"
        onChangeClick={vi.fn()}
      />
    )
    expect(screen.getByText(/Q&A Edition/)).toBeInTheDocument()
  })

  it('shows fidelity for Q&A edition', () => {
    render(
      <EditionMirror
        edition="qa"
        fidelity="faithful"
        onChangeClick={vi.fn()}
      />
    )
    expect(screen.getByText(/Faithful/i)).toBeInTheDocument()
  })

  it('hides fidelity for Ideas edition', () => {
    render(
      <EditionMirror
        edition="ideas"
        fidelity="faithful"
        onChangeClick={vi.fn()}
      />
    )
    expect(screen.queryByText(/Faithful/i)).not.toBeInTheDocument()
  })

  it('calls onChangeClick when link clicked', () => {
    const onChangeClick = vi.fn()
    render(
      <EditionMirror
        edition="qa"
        fidelity="faithful"
        onChangeClick={onChangeClick}
      />
    )
    fireEvent.click(screen.getByText('Change in Tab 1'))
    expect(onChangeClick).toHaveBeenCalled()
  })
})
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- tests/component/EditionMirror.test.tsx`
Expected: FAIL (component doesn't exist)

**Step 3: Create EditionMirror component**

```typescript
// frontend/src/components/tab3/EditionMirror.tsx
import type { Edition, Fidelity } from '../../types/edition'
import { EDITION_LABELS, FIDELITY_LABELS } from '../../types/edition'

interface EditionMirrorProps {
  edition: Edition
  fidelity: Fidelity
  onChangeClick: () => void
}

export function EditionMirror({ edition, fidelity, onChangeClick }: EditionMirrorProps) {
  return (
    <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg border">
      <div className="flex items-center gap-2">
        <span className="text-sm text-gray-600">Generating:</span>
        <span className="font-medium text-gray-900">{EDITION_LABELS[edition]}</span>
        {edition === 'qa' && (
          <>
            <span className="text-gray-400">·</span>
            <span className="text-sm text-gray-600">Fidelity: {FIDELITY_LABELS[fidelity]}</span>
          </>
        )}
      </div>
      <button
        onClick={onChangeClick}
        className="text-sm text-blue-600 hover:text-blue-800 hover:underline"
      >
        Change in Tab 1
      </button>
    </div>
  )
}
```

**Step 4: Update Tab3Content to include EditionMirror**

Add at the top of the Tab3Content component (after the component return statement begins):

```typescript
// Add import at top:
import { EditionMirror } from './EditionMirror'

// Add in render, near the top of the returned JSX:
<EditionMirror
  edition={project.edition}
  fidelity={project.fidelity}
  onChangeClick={() => dispatch({ type: 'SET_ACTIVE_TAB', payload: 1 })}
/>
```

**Step 5: Run test to verify it passes**

Run: `cd frontend && npm test -- tests/component/EditionMirror.test.tsx`
Expected: PASS

**Step 6: Commit**

```bash
git add frontend/src/components/tab3/EditionMirror.tsx frontend/src/components/tab3/Tab3Content.tsx frontend/tests/component/EditionMirror.test.tsx
git commit -m "feat(editions): Add EditionMirror to Tab3Content"
```

---

## Phase 7: Integration & Wiring

### Task 14: Wire Theme Proposal API to Frontend

**Files:**
- Create: `frontend/src/services/themeApi.ts`
- Modify: `frontend/src/components/tab1/Tab1Content.tsx`
- Test: `frontend/tests/integration/themeApi.test.ts`

**Step 1: Create theme API service**

```typescript
// frontend/src/services/themeApi.ts
import { API_BASE_URL } from './api'
import type { Theme } from '../types/edition'

interface ProposeThemesResponse {
  data: {
    job_id: string
    status: string
  }
  error: null | { code: string; message: string }
}

interface ThemeStatusResponse {
  data: {
    job_id: string
    status: 'queued' | 'processing' | 'completed' | 'failed' | 'cancelled'
    themes: Theme[]
    error: string | null
  }
  error: null | { code: string; message: string }
}

export async function proposeThemes(projectId: string): Promise<ProposeThemesResponse> {
  const response = await fetch(`${API_BASE_URL}/api/ai/themes/propose`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ project_id: projectId }),
  })
  return response.json()
}

export async function getThemeStatus(jobId: string): Promise<ThemeStatusResponse> {
  const response = await fetch(`${API_BASE_URL}/api/ai/themes/status/${jobId}`)
  return response.json()
}

export async function pollThemeProposal(
  projectId: string,
  onProgress?: (status: string) => void
): Promise<Theme[]> {
  const { data, error } = await proposeThemes(projectId)
  if (error) throw new Error(error.message)

  const jobId = data.job_id

  // Poll until complete
  while (true) {
    await new Promise((resolve) => setTimeout(resolve, 1000))

    const status = await getThemeStatus(jobId)
    if (status.error) throw new Error(status.error.message)

    onProgress?.(status.data.status)

    if (status.data.status === 'completed') {
      return status.data.themes
    }

    if (status.data.status === 'failed') {
      throw new Error(status.data.error || 'Theme proposal failed')
    }

    if (status.data.status === 'cancelled') {
      throw new Error('Theme proposal cancelled')
    }
  }
}
```

**Step 2: Update Tab1Content to use theme API**

```typescript
// In Tab1Content.tsx, update handleProposeThemes:
import { pollThemeProposal } from '../../services/themeApi'

const [isProposingThemes, setIsProposingThemes] = useState(false)

const handleProposeThemes = async () => {
  if (!project) return

  setIsProposingThemes(true)
  try {
    const themes = await pollThemeProposal(project.id)
    dispatch({ type: 'SET_THEMES', payload: themes })
  } catch (err) {
    console.error('Theme proposal failed:', err)
    // TODO: Show error to user
  } finally {
    setIsProposingThemes(false)
  }
}

// Update ThemesPanel usage:
<ThemesPanel
  themes={project.themes}
  onProposeThemes={handleProposeThemes}
  onUpdateTheme={handleUpdateTheme}
  onRemoveTheme={handleRemoveTheme}
  onReorderThemes={handleReorderThemes}
  isProposing={isProposingThemes}
/>
```

**Step 3: Commit**

```bash
git add frontend/src/services/themeApi.ts frontend/src/components/tab1/Tab1Content.tsx
git commit -m "feat(editions): Wire theme proposal API to frontend"
```

---

### Task 15: Run Full Test Suite & Fix Issues

**Step 1: Run backend tests**

Run: `cd backend && python -m pytest tests/ -v --tb=short`
Expected: All tests pass

**Step 2: Run frontend tests**

Run: `cd frontend && npm test`
Expected: All tests pass

**Step 3: Run linters**

Run: `cd backend && ruff check .`
Run: `cd frontend && npm run lint`
Expected: No errors

**Step 4: Manual smoke test**

1. Start backend: `cd backend && uvicorn src.api.main:app --reload`
2. Start frontend: `cd frontend && npm run dev`
3. Verify:
   - Edition selector appears in Tab 1
   - Switching editions shows Outline vs Themes panel
   - EditionMirror appears in Tab 3

**Step 5: Final commit**

```bash
git add -A
git commit -m "feat(editions): Complete Phase 1 - Edition selection UI"
```

---

## Summary

This plan covers the foundational work for the Editions feature:

**Completed in this plan:**
1. Backend models (Edition, Fidelity, Coverage, SegmentRef, Theme)
2. Canonical transcript service (normalization, hashing)
3. Coverage scoring service
4. Theme job store and API endpoints
5. Frontend types and context state
6. EditionSelector, ThemesPanel, ThemeRow, EditionMirror components
7. Tab1Content and Tab3Content integration

**Deferred to follow-up plan:**
- Theme proposal service (LLM integration for analyzing transcript)
- Segment retrieval with embeddings
- Ideas Edition generation pipeline
- Quote validation service
- Faithfulness cleanup
- Full end-to-end integration tests

---

**Plan complete and saved to `docs/plans/2026-01-13-editions-implementation.md`. Two execution options:**

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?**
