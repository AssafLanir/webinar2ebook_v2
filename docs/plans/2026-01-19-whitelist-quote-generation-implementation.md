# Whitelist-Based Quote Generation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement whitelist-based quote generation that eliminates fabricated quotes by construction.

**Architecture:** Pre-build validated quote whitelist from Evidence Map → inject deterministic excerpts → enforce all quotes against whitelist post-generation.

**Tech Stack:** Python 3.11, Pydantic v2, FastAPI, pytest

---

## Phase 1: Data Structures

### Task 1: Add SpeakerRole enum and SpeakerRef model

**Files:**
- Modify: `backend/src/models/edition.py`
- Test: `backend/tests/unit/test_edition_models.py`

**Step 1: Write failing test**

```python
# In backend/tests/unit/test_edition_models.py (create if needed)
import pytest
from src.models.edition import SpeakerRole, SpeakerRef

class TestSpeakerModels:
    def test_speaker_role_values(self):
        """Test SpeakerRole enum has expected values."""
        assert SpeakerRole.HOST == "host"
        assert SpeakerRole.GUEST == "guest"
        assert SpeakerRole.CALLER == "caller"
        assert SpeakerRole.CLIP == "clip"
        assert SpeakerRole.UNCLEAR == "unclear"

    def test_speaker_ref_creation(self):
        """Test SpeakerRef model creation."""
        ref = SpeakerRef(
            speaker_id="david_deutsch",
            speaker_name="David Deutsch",
            speaker_role=SpeakerRole.GUEST,
        )
        assert ref.speaker_id == "david_deutsch"
        assert ref.speaker_name == "David Deutsch"
        assert ref.speaker_role == SpeakerRole.GUEST
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_edition_models.py::TestSpeakerModels -v`
Expected: FAIL with ImportError

**Step 3: Write minimal implementation**

```python
# Add to backend/src/models/edition.py after existing imports

class SpeakerRole(str, Enum):
    """Role of speaker in transcript."""
    HOST = "host"
    GUEST = "guest"
    CALLER = "caller"
    CLIP = "clip"
    UNCLEAR = "unclear"


class SpeakerRef(BaseModel):
    """Reference to a speaker with typed role."""
    model_config = ConfigDict(extra="forbid")

    speaker_id: str = Field(description="Canonical stable ID (e.g., 'david_deutsch')")
    speaker_name: str = Field(description="Display name (e.g., 'David Deutsch')")
    speaker_role: SpeakerRole = Field(description="Role for filtering")
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/unit/test_edition_models.py::TestSpeakerModels -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/models/edition.py backend/tests/unit/test_edition_models.py
git commit -m "feat: add SpeakerRole enum and SpeakerRef model for whitelist"
```

---

### Task 2: Add TranscriptPair and WhitelistQuote models

**Files:**
- Modify: `backend/src/models/edition.py`
- Test: `backend/tests/unit/test_edition_models.py`

**Step 1: Write failing test**

```python
# Add to TestWhitelistModels class in test_edition_models.py
from src.models.edition import TranscriptPair, WhitelistQuote, SpeakerRef, SpeakerRole

class TestWhitelistModels:
    def test_transcript_pair_creation(self):
        """Test TranscriptPair holds raw and canonical."""
        pair = TranscriptPair(
            raw="He said "hello"—goodbye",
            canonical='he said "hello"-goodbye',
        )
        assert pair.raw == "He said "hello"—goodbye"
        assert pair.canonical == 'he said "hello"-goodbye'

    def test_whitelist_quote_creation(self):
        """Test WhitelistQuote model creation."""
        speaker = SpeakerRef(
            speaker_id="david_deutsch",
            speaker_name="David Deutsch",
            speaker_role=SpeakerRole.GUEST,
        )
        quote = WhitelistQuote(
            quote_id="abc123def456",
            quote_text="Wisdom is limitless",
            quote_canonical="wisdom is limitless",
            speaker=speaker,
            source_evidence_ids=["ev1", "ev2"],
            chapter_indices=[0, 1],
            match_spans=[(100, 120)],
        )
        assert quote.quote_id == "abc123def456"
        assert quote.speaker.speaker_role == SpeakerRole.GUEST
        assert 0 in quote.chapter_indices
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_edition_models.py::TestWhitelistModels -v`
Expected: FAIL with ImportError

**Step 3: Write minimal implementation**

```python
# Add to backend/src/models/edition.py

class TranscriptPair(BaseModel):
    """Both transcript forms needed for whitelist building."""
    model_config = ConfigDict(extra="forbid")

    raw: str = Field(description="Original transcript (for quote_text extraction)")
    canonical: str = Field(description="Normalized (for matching)")


class WhitelistQuote(BaseModel):
    """A validated quote that can be used in generation."""
    model_config = ConfigDict(extra="forbid")

    quote_id: str = Field(description="Stable ID: sha256(speaker_id|quote_canonical)[:16]")
    quote_text: str = Field(description="EXACT from raw transcript (for output)")
    quote_canonical: str = Field(description="Casefolded/normalized (for matching only)")
    speaker: SpeakerRef
    source_evidence_ids: list[str] = Field(default_factory=list)
    chapter_indices: list[int] = Field(default_factory=list)
    match_spans: list[tuple[int, int]] = Field(default_factory=list)
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/unit/test_edition_models.py::TestWhitelistModels -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/models/edition.py backend/tests/unit/test_edition_models.py
git commit -m "feat: add TranscriptPair and WhitelistQuote models"
```

---

### Task 3: Add CoverageLevel enum and ChapterCoverage model

**Files:**
- Modify: `backend/src/models/edition.py`
- Test: `backend/tests/unit/test_edition_models.py`

**Step 1: Write failing test**

```python
# Add to test_edition_models.py
from src.models.edition import CoverageLevel, ChapterCoverage

class TestCoverageModels:
    def test_coverage_level_values(self):
        """Test CoverageLevel enum values."""
        assert CoverageLevel.STRONG == "strong"
        assert CoverageLevel.MEDIUM == "medium"
        assert CoverageLevel.WEAK == "weak"

    def test_chapter_coverage_creation(self):
        """Test ChapterCoverage model creation."""
        coverage = ChapterCoverage(
            chapter_index=0,
            level=CoverageLevel.STRONG,
            usable_quotes=5,
            quote_words_per_claim=60.0,
            quotes_per_claim=2.5,
            target_words=800,
            generation_mode="normal",
        )
        assert coverage.level == CoverageLevel.STRONG
        assert coverage.target_words == 800
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_edition_models.py::TestCoverageModels -v`
Expected: FAIL with ImportError

**Step 3: Write minimal implementation**

```python
# Add to backend/src/models/edition.py

class CoverageLevel(str, Enum):
    """Coverage strength for quote availability."""
    STRONG = "strong"  # >= 5 usable quotes, >= 50 words/claim
    MEDIUM = "medium"  # >= 3 usable quotes, >= 30 words/claim
    WEAK = "weak"      # Below MEDIUM thresholds


class ChapterCoverage(BaseModel):
    """Coverage metrics for a chapter."""
    model_config = ConfigDict(extra="forbid")

    chapter_index: int = Field(ge=0)
    level: CoverageLevel
    usable_quotes: int = Field(ge=0)
    quote_words_per_claim: float = Field(ge=0)
    quotes_per_claim: float = Field(ge=0)
    target_words: int = Field(ge=0)
    generation_mode: str = Field(description="normal | thin | excerpt_only")
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/unit/test_edition_models.py::TestCoverageModels -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/models/edition.py backend/tests/unit/test_edition_models.py
git commit -m "feat: add CoverageLevel and ChapterCoverage models"
```

---

## Phase 2: Whitelist Builder (HARD GATE 1)

### Task 4: Add canonicalize_transcript function

**Files:**
- Create: `backend/src/services/whitelist_service.py`
- Test: `backend/tests/unit/test_whitelist_service.py`

**Step 1: Write failing tests**

```python
# Create backend/tests/unit/test_whitelist_service.py
import pytest
from src.services.whitelist_service import canonicalize_transcript

class TestCanonicalizeTranscript:
    def test_normalizes_smart_quotes(self):
        """Test smart quotes become straight quotes."""
        raw = 'He said "hello" and 'goodbye''
        result = canonicalize_transcript(raw)
        assert '"' not in result  # No curly double quotes
        assert ''' not in result  # No curly single quotes
        assert '"hello"' in result

    def test_normalizes_dashes(self):
        """Test em-dash and en-dash become hyphens."""
        raw = "word—another–third"
        result = canonicalize_transcript(raw)
        assert "—" not in result
        assert "–" not in result
        assert "word-another-third" in result

    def test_collapses_whitespace(self):
        """Test multiple spaces/newlines collapse to single space."""
        raw = "hello   world\n\ntest"
        result = canonicalize_transcript(raw)
        assert "hello world test" in result

    def test_preserves_case(self):
        """Test case is preserved (not lowercased)."""
        raw = "Hello World"
        result = canonicalize_transcript(raw)
        assert result == "Hello World"

    def test_stability(self):
        """Test same input always produces same output."""
        raw = 'Test "quote"—with dash'
        result1 = canonicalize_transcript(raw)
        result2 = canonicalize_transcript(raw)
        assert result1 == result2
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_whitelist_service.py::TestCanonicalizeTranscript -v`
Expected: FAIL with ModuleNotFoundError

**Step 3: Write minimal implementation**

```python
# Create backend/src/services/whitelist_service.py
"""Whitelist-based quote validation service.

Builds validated quote whitelist from Evidence Map, enforces quotes
against whitelist, and provides deterministic excerpt selection.
"""

from __future__ import annotations

import re
from hashlib import sha256


def canonicalize_transcript(text: str) -> str:
    """Normalize transcript for matching.

    Handles:
    - Smart quotes → straight quotes
    - Em-dash/en-dash → hyphen
    - Collapsed whitespace

    Preserves case (for quote_text extraction).
    """
    result = text
    # Smart double quotes → straight
    result = result.replace('\u201c', '"').replace('\u201d', '"')
    # Smart single quotes → straight
    result = result.replace('\u2018', "'").replace('\u2019', "'")
    # Em-dash/en-dash → hyphen
    result = result.replace('\u2014', '-').replace('\u2013', '-')
    # Collapse whitespace
    result = ' '.join(result.split())
    return result
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/unit/test_whitelist_service.py::TestCanonicalizeTranscript -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/services/whitelist_service.py backend/tests/unit/test_whitelist_service.py
git commit -m "feat: add canonicalize_transcript function for whitelist"
```

---

### Task 5: Add find_all_occurrences and resolve_speaker functions

**Files:**
- Modify: `backend/src/services/whitelist_service.py`
- Test: `backend/tests/unit/test_whitelist_service.py`

**Step 1: Write failing tests**

```python
# Add to test_whitelist_service.py
from src.services.whitelist_service import find_all_occurrences, resolve_speaker
from src.models.edition import SpeakerRole

class TestFindAllOccurrences:
    def test_finds_single_occurrence(self):
        """Test finding single occurrence."""
        text = "hello world hello"
        spans = find_all_occurrences(text, "world")
        assert spans == [(6, 11)]

    def test_finds_multiple_occurrences(self):
        """Test finding multiple occurrences."""
        text = "hello world hello world"
        spans = find_all_occurrences(text, "hello")
        assert len(spans) == 2
        assert spans[0] == (0, 5)
        assert spans[1] == (12, 17)

    def test_returns_empty_for_no_match(self):
        """Test returns empty list when not found."""
        text = "hello world"
        spans = find_all_occurrences(text, "xyz")
        assert spans == []

    def test_case_sensitive(self):
        """Test search is case-sensitive."""
        text = "Hello HELLO hello"
        spans = find_all_occurrences(text, "hello")
        assert len(spans) == 1
        assert spans[0] == (12, 17)


class TestResolveSpeaker:
    def test_resolves_known_guest(self):
        """Test resolving a known guest speaker."""
        ref = resolve_speaker("David Deutsch", known_guests=["David Deutsch"])
        assert ref.speaker_id == "david_deutsch"
        assert ref.speaker_name == "David Deutsch"
        assert ref.speaker_role == SpeakerRole.GUEST

    def test_resolves_host(self):
        """Test resolving host speaker."""
        ref = resolve_speaker("Naval Ravikant", known_hosts=["Naval Ravikant"])
        assert ref.speaker_role == SpeakerRole.HOST

    def test_resolves_unknown_as_unclear(self):
        """Test unknown speaker resolves as UNCLEAR."""
        ref = resolve_speaker("Unknown")
        assert ref.speaker_role == SpeakerRole.UNCLEAR

    def test_generates_stable_id(self):
        """Test speaker_id is stable."""
        ref1 = resolve_speaker("David Deutsch", known_guests=["David Deutsch"])
        ref2 = resolve_speaker("David Deutsch", known_guests=["David Deutsch"])
        assert ref1.speaker_id == ref2.speaker_id
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_whitelist_service.py::TestFindAllOccurrences tests/unit/test_whitelist_service.py::TestResolveSpeaker -v`
Expected: FAIL with ImportError

**Step 3: Write minimal implementation**

```python
# Add to backend/src/services/whitelist_service.py
from src.models.edition import SpeakerRole, SpeakerRef


def find_all_occurrences(text: str, substring: str) -> list[tuple[int, int]]:
    """Find all occurrences of substring in text.

    Args:
        text: Text to search in.
        substring: Substring to find.

    Returns:
        List of (start, end) tuples for each occurrence.
    """
    spans = []
    start = 0
    while True:
        pos = text.find(substring, start)
        if pos == -1:
            break
        spans.append((pos, pos + len(substring)))
        start = pos + 1
    return spans


def resolve_speaker(
    speaker_name: str,
    known_guests: list[str] | None = None,
    known_hosts: list[str] | None = None,
) -> SpeakerRef:
    """Resolve speaker name to typed SpeakerRef.

    Args:
        speaker_name: Name from transcript/evidence.
        known_guests: List of known guest names.
        known_hosts: List of known host names.

    Returns:
        SpeakerRef with stable ID and role.
    """
    known_guests = known_guests or []
    known_hosts = known_hosts or []

    # Generate stable ID from name
    speaker_id = speaker_name.lower().replace(" ", "_").replace(".", "")

    # Determine role
    if speaker_name.lower() in ("unknown", "unclear", ""):
        role = SpeakerRole.UNCLEAR
    elif speaker_name in known_guests:
        role = SpeakerRole.GUEST
    elif speaker_name in known_hosts:
        role = SpeakerRole.HOST
    else:
        # Default to GUEST if not explicitly known
        role = SpeakerRole.GUEST

    return SpeakerRef(
        speaker_id=speaker_id,
        speaker_name=speaker_name,
        speaker_role=role,
    )
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/unit/test_whitelist_service.py::TestFindAllOccurrences tests/unit/test_whitelist_service.py::TestResolveSpeaker -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/services/whitelist_service.py backend/tests/unit/test_whitelist_service.py
git commit -m "feat: add find_all_occurrences and resolve_speaker functions"
```

---

### Task 6: Add build_quote_whitelist function

**Files:**
- Modify: `backend/src/services/whitelist_service.py`
- Test: `backend/tests/unit/test_whitelist_service.py`

**Step 1: Write failing tests**

```python
# Add to test_whitelist_service.py
from src.services.whitelist_service import build_quote_whitelist
from src.models.edition import TranscriptPair, WhitelistQuote
from src.models.evidence_map import EvidenceMap, ChapterEvidence, EvidenceEntry, SupportQuote

class TestBuildQuoteWhitelist:
    @pytest.fixture
    def sample_transcript_pair(self):
        """Transcript with smart quotes in raw, straight in canonical."""
        raw = 'David said "Wisdom is limitless" and also "Knowledge grows"'
        canonical = 'David said "Wisdom is limitless" and also "Knowledge grows"'
        return TranscriptPair(raw=raw, canonical=canonical)

    @pytest.fixture
    def sample_evidence_map(self):
        """Evidence map with claims and quotes."""
        return EvidenceMap(
            version=1,
            project_id="test",
            content_mode="essay",
            transcript_hash="abc123",
            chapters=[
                ChapterEvidence(
                    chapter_index=1,
                    chapter_title="Chapter 1",
                    claims=[
                        EvidenceEntry(
                            id="ev1",
                            claim="Wisdom has no bounds",
                            support=[
                                SupportQuote(
                                    quote="Wisdom is limitless",
                                    speaker="David Deutsch",
                                )
                            ],
                        )
                    ],
                )
            ],
        )

    def test_builds_whitelist_from_evidence(self, sample_transcript_pair, sample_evidence_map):
        """Test whitelist is built from evidence map."""
        whitelist = build_quote_whitelist(
            sample_evidence_map,
            sample_transcript_pair,
            known_guests=["David Deutsch"],
        )
        assert len(whitelist) == 1
        assert whitelist[0].quote_text == "Wisdom is limitless"
        assert whitelist[0].speaker.speaker_role == SpeakerRole.GUEST

    def test_rejects_quote_not_in_transcript(self):
        """Test quotes not in transcript are excluded."""
        transcript = TranscriptPair(raw="Hello world", canonical="Hello world")
        evidence = EvidenceMap(
            version=1,
            project_id="test",
            content_mode="essay",
            transcript_hash="abc",
            chapters=[
                ChapterEvidence(
                    chapter_index=1,
                    chapter_title="Ch1",
                    claims=[
                        EvidenceEntry(
                            id="ev1",
                            claim="Test",
                            support=[SupportQuote(quote="Not in transcript", speaker="Someone")],
                        )
                    ],
                )
            ],
        )
        whitelist = build_quote_whitelist(evidence, transcript)
        assert len(whitelist) == 0

    def test_rejects_unknown_speaker(self):
        """Test Unknown attribution is excluded."""
        transcript = TranscriptPair(raw="Wisdom is limitless", canonical="Wisdom is limitless")
        evidence = EvidenceMap(
            version=1,
            project_id="test",
            content_mode="essay",
            transcript_hash="abc",
            chapters=[
                ChapterEvidence(
                    chapter_index=1,
                    chapter_title="Ch1",
                    claims=[
                        EvidenceEntry(
                            id="ev1",
                            claim="Test",
                            support=[SupportQuote(quote="Wisdom is limitless", speaker=None)],
                        )
                    ],
                )
            ],
        )
        whitelist = build_quote_whitelist(evidence, transcript)
        assert len(whitelist) == 0

    def test_extracts_quote_text_from_raw_transcript(self):
        """Test quote_text comes from raw transcript (preserves formatting)."""
        raw = 'He said "Wisdom is limitless"'  # smart quotes
        canonical = 'He said "Wisdom is limitless"'  # straight quotes
        transcript = TranscriptPair(raw=raw, canonical=canonical)

        evidence = EvidenceMap(
            version=1,
            project_id="test",
            content_mode="essay",
            transcript_hash="abc",
            chapters=[
                ChapterEvidence(
                    chapter_index=1,
                    chapter_title="Ch1",
                    claims=[
                        EvidenceEntry(
                            id="ev1",
                            claim="Test",
                            support=[SupportQuote(quote="Wisdom is limitless", speaker="David")],
                        )
                    ],
                )
            ],
        )
        whitelist = build_quote_whitelist(evidence, transcript, known_guests=["David"])
        assert len(whitelist) == 1
        # quote_text should be from raw transcript
        assert whitelist[0].quote_text == "Wisdom is limitless"

    def test_merges_duplicate_quotes(self):
        """Test same quote from same speaker merges chapter_indices."""
        transcript = TranscriptPair(
            raw="Wisdom is limitless",
            canonical="Wisdom is limitless",
        )
        evidence = EvidenceMap(
            version=1,
            project_id="test",
            content_mode="essay",
            transcript_hash="abc",
            chapters=[
                ChapterEvidence(
                    chapter_index=1,
                    chapter_title="Ch1",
                    claims=[
                        EvidenceEntry(
                            id="ev1",
                            claim="Claim 1",
                            support=[SupportQuote(quote="Wisdom is limitless", speaker="David")],
                        )
                    ],
                ),
                ChapterEvidence(
                    chapter_index=2,
                    chapter_title="Ch2",
                    claims=[
                        EvidenceEntry(
                            id="ev2",
                            claim="Claim 2",
                            support=[SupportQuote(quote="Wisdom is limitless", speaker="David")],
                        )
                    ],
                ),
            ],
        )
        whitelist = build_quote_whitelist(evidence, transcript, known_guests=["David"])
        assert len(whitelist) == 1
        assert 0 in whitelist[0].chapter_indices  # 0-indexed from 1-based
        assert 1 in whitelist[0].chapter_indices

    def test_generates_stable_quote_id(self):
        """Test quote_id is deterministic."""
        transcript = TranscriptPair(raw="Wisdom is limitless", canonical="Wisdom is limitless")
        evidence = EvidenceMap(
            version=1,
            project_id="test",
            content_mode="essay",
            transcript_hash="abc",
            chapters=[
                ChapterEvidence(
                    chapter_index=1,
                    chapter_title="Ch1",
                    claims=[
                        EvidenceEntry(
                            id="ev1",
                            claim="Test",
                            support=[SupportQuote(quote="Wisdom is limitless", speaker="David")],
                        )
                    ],
                )
            ],
        )
        whitelist1 = build_quote_whitelist(evidence, transcript, known_guests=["David"])
        whitelist2 = build_quote_whitelist(evidence, transcript, known_guests=["David"])
        assert whitelist1[0].quote_id == whitelist2[0].quote_id
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_whitelist_service.py::TestBuildQuoteWhitelist -v`
Expected: FAIL with ImportError

**Step 3: Write minimal implementation**

```python
# Add to backend/src/services/whitelist_service.py
from src.models.edition import TranscriptPair, WhitelistQuote
from src.models.evidence_map import EvidenceMap


def build_quote_whitelist(
    evidence_map: EvidenceMap,
    transcript: TranscriptPair,
    known_guests: list[str] | None = None,
    known_hosts: list[str] | None = None,
) -> list[WhitelistQuote]:
    """Build whitelist of validated quotes from Evidence Map.

    Only includes quotes that:
    1. Have a speaker (Unknown attribution rejected)
    2. Match as substring in canonical transcript
    3. Have speaker resolved to SpeakerRef

    Args:
        evidence_map: Evidence map with claims and support quotes.
        transcript: Raw and canonical transcript pair.
        known_guests: List of known guest names.
        known_hosts: List of known host names.

    Returns:
        List of validated WhitelistQuote entries.
    """
    known_guests = known_guests or []
    known_hosts = known_hosts or []

    canonical_lower = transcript.canonical.casefold()
    whitelist_map: dict[tuple[str, str], WhitelistQuote] = {}

    for chapter in evidence_map.chapters:
        # Convert 1-based chapter_index to 0-based
        chapter_idx = chapter.chapter_index - 1

        for claim in chapter.claims:
            for support in claim.support:
                # Reject Unknown attribution
                if not support.speaker:
                    continue

                speaker_ref = resolve_speaker(
                    support.speaker,
                    known_guests=known_guests,
                    known_hosts=known_hosts,
                )

                # Skip UNCLEAR speakers
                if speaker_ref.speaker_role == SpeakerRole.UNCLEAR:
                    continue

                # Canonicalize quote for matching
                quote_for_match = canonicalize_transcript(support.quote).casefold()

                # Find in canonical transcript
                spans = find_all_occurrences(canonical_lower, quote_for_match)
                if not spans:
                    continue  # Not in transcript

                # Extract exact text from raw transcript at same position
                start, end = spans[0]
                exact_quote = transcript.raw[start:end]

                key = (speaker_ref.speaker_id, quote_for_match)

                if key in whitelist_map:
                    # Merge: add chapter, evidence ID
                    existing = whitelist_map[key]
                    if chapter_idx not in existing.chapter_indices:
                        existing.chapter_indices.append(chapter_idx)
                    existing.source_evidence_ids.append(claim.id)
                else:
                    # Create new entry with stable ID
                    quote_id = sha256(
                        f"{speaker_ref.speaker_id}|{quote_for_match}".encode()
                    ).hexdigest()[:16]

                    whitelist_map[key] = WhitelistQuote(
                        quote_id=quote_id,
                        quote_text=exact_quote,
                        quote_canonical=quote_for_match,
                        speaker=speaker_ref,
                        source_evidence_ids=[claim.id],
                        chapter_indices=[chapter_idx],
                        match_spans=spans,
                    )

    return list(whitelist_map.values())
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/unit/test_whitelist_service.py::TestBuildQuoteWhitelist -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/services/whitelist_service.py backend/tests/unit/test_whitelist_service.py
git commit -m "feat: add build_quote_whitelist function"
```

---

### Task 7: HARD GATE 1 - Whitelist Builder Regression Tests

**Files:**
- Test: `backend/tests/unit/test_whitelist_service.py`

**Step 1: Write comprehensive regression tests**

```python
# Add to test_whitelist_service.py
class TestWhitelistBuilderHardGate:
    """HARD GATE 1: Whitelist builder correctness tests.

    These tests prove:
    - quote_text is exact raw substring
    - quote_canonical matches canonical transcript
    - Curly quotes/dashes/whitespace handled correctly
    - Duplicates merged properly
    """

    def test_curly_quotes_matched_correctly(self):
        """Test curly quotes in raw don't break matching."""
        raw = 'He said "Wisdom is limitless" today'  # curly quotes
        canonical = 'He said "Wisdom is limitless" today'  # straight quotes
        transcript = TranscriptPair(raw=raw, canonical=canonical)

        evidence = EvidenceMap(
            version=1, project_id="test", content_mode="essay", transcript_hash="abc",
            chapters=[ChapterEvidence(
                chapter_index=1, chapter_title="Ch1",
                claims=[EvidenceEntry(
                    id="ev1", claim="Test",
                    support=[SupportQuote(quote="Wisdom is limitless", speaker="David")],
                )],
            )],
        )
        whitelist = build_quote_whitelist(evidence, transcript, known_guests=["David"])
        assert len(whitelist) == 1
        # quote_text from raw should preserve curly quotes
        assert "Wisdom is limitless" in whitelist[0].quote_text

    def test_em_dash_matched_correctly(self):
        """Test em-dash in raw doesn't break matching."""
        raw = "Knowledge—the key—unlocks everything"  # em-dashes
        canonical = "Knowledge-the key-unlocks everything"  # hyphens
        transcript = TranscriptPair(raw=raw, canonical=canonical)

        evidence = EvidenceMap(
            version=1, project_id="test", content_mode="essay", transcript_hash="abc",
            chapters=[ChapterEvidence(
                chapter_index=1, chapter_title="Ch1",
                claims=[EvidenceEntry(
                    id="ev1", claim="Test",
                    support=[SupportQuote(quote="the key", speaker="David")],
                )],
            )],
        )
        whitelist = build_quote_whitelist(evidence, transcript, known_guests=["David"])
        assert len(whitelist) == 1

    def test_whitespace_variations_matched(self):
        """Test whitespace variations don't break matching."""
        raw = "Wisdom   is\nlimitless"  # extra spaces, newline
        canonical = "Wisdom is limitless"  # normalized
        transcript = TranscriptPair(raw=raw, canonical=canonical)

        evidence = EvidenceMap(
            version=1, project_id="test", content_mode="essay", transcript_hash="abc",
            chapters=[ChapterEvidence(
                chapter_index=1, chapter_title="Ch1",
                claims=[EvidenceEntry(
                    id="ev1", claim="Test",
                    support=[SupportQuote(quote="Wisdom is limitless", speaker="David")],
                )],
            )],
        )
        whitelist = build_quote_whitelist(evidence, transcript, known_guests=["David"])
        assert len(whitelist) == 1

    def test_quote_text_is_exact_raw_substring(self):
        """CRITICAL: quote_text must be exact substring from raw transcript."""
        raw = 'The "truth" is—complex'
        canonical = 'The "truth" is-complex'
        transcript = TranscriptPair(raw=raw, canonical=canonical)

        evidence = EvidenceMap(
            version=1, project_id="test", content_mode="essay", transcript_hash="abc",
            chapters=[ChapterEvidence(
                chapter_index=1, chapter_title="Ch1",
                claims=[EvidenceEntry(
                    id="ev1", claim="Test",
                    support=[SupportQuote(quote="truth", speaker="David")],
                )],
            )],
        )
        whitelist = build_quote_whitelist(evidence, transcript, known_guests=["David"])
        assert len(whitelist) == 1

        # Verify quote_text is extractable from raw
        quote_text = whitelist[0].quote_text
        assert quote_text in raw, f"quote_text '{quote_text}' not found in raw transcript"

    def test_quote_canonical_matches_canonical_transcript(self):
        """CRITICAL: quote_canonical must be findable in canonical transcript."""
        raw = 'He said "Wisdom is limitless"'
        canonical = 'He said "Wisdom is limitless"'
        transcript = TranscriptPair(raw=raw, canonical=canonical)

        evidence = EvidenceMap(
            version=1, project_id="test", content_mode="essay", transcript_hash="abc",
            chapters=[ChapterEvidence(
                chapter_index=1, chapter_title="Ch1",
                claims=[EvidenceEntry(
                    id="ev1", claim="Test",
                    support=[SupportQuote(quote="Wisdom is limitless", speaker="David")],
                )],
            )],
        )
        whitelist = build_quote_whitelist(evidence, transcript, known_guests=["David"])
        assert len(whitelist) == 1

        quote_canonical = whitelist[0].quote_canonical
        assert quote_canonical in canonical.casefold()

    def test_duplicate_quotes_different_chapters_merged(self):
        """Test same quote in different chapters creates single entry with both indices."""
        transcript = TranscriptPair(raw="Wisdom is limitless", canonical="Wisdom is limitless")
        evidence = EvidenceMap(
            version=1, project_id="test", content_mode="essay", transcript_hash="abc",
            chapters=[
                ChapterEvidence(
                    chapter_index=1, chapter_title="Ch1",
                    claims=[EvidenceEntry(
                        id="ev1", claim="Claim 1",
                        support=[SupportQuote(quote="Wisdom is limitless", speaker="David")],
                    )],
                ),
                ChapterEvidence(
                    chapter_index=2, chapter_title="Ch2",
                    claims=[EvidenceEntry(
                        id="ev2", claim="Claim 2",
                        support=[SupportQuote(quote="Wisdom is limitless", speaker="David")],
                    )],
                ),
                ChapterEvidence(
                    chapter_index=3, chapter_title="Ch3",
                    claims=[EvidenceEntry(
                        id="ev3", claim="Claim 3",
                        support=[SupportQuote(quote="Wisdom is limitless", speaker="David")],
                    )],
                ),
            ],
        )
        whitelist = build_quote_whitelist(evidence, transcript, known_guests=["David"])

        # Should be single entry
        assert len(whitelist) == 1
        # With all three chapter indices (0-indexed)
        assert set(whitelist[0].chapter_indices) == {0, 1, 2}
        # With all three evidence IDs
        assert set(whitelist[0].source_evidence_ids) == {"ev1", "ev2", "ev3"}

    def test_same_quote_different_speakers_separate_entries(self):
        """Test same quote from different speakers creates separate entries."""
        transcript = TranscriptPair(raw="The truth matters", canonical="The truth matters")
        evidence = EvidenceMap(
            version=1, project_id="test", content_mode="essay", transcript_hash="abc",
            chapters=[ChapterEvidence(
                chapter_index=1, chapter_title="Ch1",
                claims=[
                    EvidenceEntry(
                        id="ev1", claim="Claim 1",
                        support=[SupportQuote(quote="The truth matters", speaker="David")],
                    ),
                    EvidenceEntry(
                        id="ev2", claim="Claim 2",
                        support=[SupportQuote(quote="The truth matters", speaker="Naval")],
                    ),
                ],
            )],
        )
        whitelist = build_quote_whitelist(
            evidence, transcript,
            known_guests=["David", "Naval"],
        )

        # Should be two entries (one per speaker)
        assert len(whitelist) == 2
        speakers = {w.speaker.speaker_name for w in whitelist}
        assert speakers == {"David", "Naval"}
```

**Step 2: Run tests**

Run: `cd backend && python -m pytest tests/unit/test_whitelist_service.py::TestWhitelistBuilderHardGate -v`
Expected: PASS

**Step 3: Commit**

```bash
git add backend/tests/unit/test_whitelist_service.py
git commit -m "test: add HARD GATE 1 regression tests for whitelist builder"
```

---

## Phase 3: Coverage Scorer

### Task 8: Add compute_chapter_coverage function

**Files:**
- Modify: `backend/src/services/whitelist_service.py`
- Test: `backend/tests/unit/test_whitelist_service.py`

**Step 1: Write failing tests**

```python
# Add to test_whitelist_service.py
from src.services.whitelist_service import compute_chapter_coverage
from src.models.edition import CoverageLevel, ChapterCoverage

class TestComputeChapterCoverage:
    def test_strong_coverage(self):
        """Test STRONG coverage with >= 5 quotes and >= 50 words/claim."""
        whitelist = [
            _make_quote(f"Quote {i} " * 15, chapter_indices=[0])  # ~15 words each
            for i in range(6)
        ]
        chapter = _make_chapter_evidence(claim_count=2)

        coverage = compute_chapter_coverage(chapter, whitelist, chapter_index=0)

        assert coverage.level == CoverageLevel.STRONG
        assert coverage.usable_quotes >= 5
        assert coverage.target_words == 800
        assert coverage.generation_mode == "normal"

    def test_medium_coverage(self):
        """Test MEDIUM coverage with 3-4 quotes."""
        whitelist = [
            _make_quote(f"Quote {i} " * 10, chapter_indices=[0])
            for i in range(3)
        ]
        chapter = _make_chapter_evidence(claim_count=2)

        coverage = compute_chapter_coverage(chapter, whitelist, chapter_index=0)

        assert coverage.level == CoverageLevel.MEDIUM
        assert coverage.target_words == 500
        assert coverage.generation_mode == "thin"

    def test_weak_coverage(self):
        """Test WEAK coverage with < 3 quotes."""
        whitelist = [
            _make_quote("Short quote", chapter_indices=[0])
        ]
        chapter = _make_chapter_evidence(claim_count=2)

        coverage = compute_chapter_coverage(chapter, whitelist, chapter_index=0)

        assert coverage.level == CoverageLevel.WEAK
        assert coverage.target_words == 250
        assert coverage.generation_mode == "excerpt_only"

    def test_filters_short_quotes(self):
        """Test quotes < 8 words are not counted as usable."""
        whitelist = [
            _make_quote("Short", chapter_indices=[0]),  # 1 word - not usable
            _make_quote("This is a longer quote with enough words", chapter_indices=[0]),  # 8 words
        ]
        chapter = _make_chapter_evidence(claim_count=1)

        coverage = compute_chapter_coverage(chapter, whitelist, chapter_index=0)

        assert coverage.usable_quotes == 1  # Only the long one

    def test_filters_by_chapter_index(self):
        """Test only quotes for this chapter are counted."""
        whitelist = [
            _make_quote("Quote for chapter 0 with enough words here", chapter_indices=[0]),
            _make_quote("Quote for chapter 1 with enough words here", chapter_indices=[1]),
        ]
        chapter = _make_chapter_evidence(claim_count=1)

        coverage = compute_chapter_coverage(chapter, whitelist, chapter_index=0)

        assert coverage.usable_quotes == 1


# Helper functions for tests
def _make_quote(text: str, chapter_indices: list[int]) -> WhitelistQuote:
    """Create a WhitelistQuote for testing."""
    return WhitelistQuote(
        quote_id="test_id",
        quote_text=text,
        quote_canonical=text.lower(),
        speaker=SpeakerRef(
            speaker_id="test_speaker",
            speaker_name="Test Speaker",
            speaker_role=SpeakerRole.GUEST,
        ),
        source_evidence_ids=["ev1"],
        chapter_indices=chapter_indices,
        match_spans=[(0, len(text))],
    )


def _make_chapter_evidence(claim_count: int) -> ChapterEvidence:
    """Create ChapterEvidence for testing."""
    return ChapterEvidence(
        chapter_index=1,
        chapter_title="Test Chapter",
        claims=[
            EvidenceEntry(
                id=f"claim_{i}",
                claim=f"Claim {i}",
                support=[SupportQuote(quote="test", speaker="Test")],
            )
            for i in range(claim_count)
        ],
    )
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_whitelist_service.py::TestComputeChapterCoverage -v`
Expected: FAIL with ImportError

**Step 3: Write minimal implementation**

```python
# Add to backend/src/services/whitelist_service.py
from src.models.edition import CoverageLevel, ChapterCoverage
from src.models.evidence_map import ChapterEvidence

# Coverage thresholds
MIN_USABLE_QUOTE_LENGTH = 8  # words
STRONG_QUOTES = 5
STRONG_WORDS_PER_CLAIM = 50
MEDIUM_QUOTES = 3
MEDIUM_WORDS_PER_CLAIM = 30


def compute_chapter_coverage(
    chapter_evidence: ChapterEvidence,
    whitelist: list[WhitelistQuote],
    chapter_index: int,
) -> ChapterCoverage:
    """Compute coverage metrics for a single chapter.

    Args:
        chapter_evidence: Evidence data for chapter.
        whitelist: Full whitelist of validated quotes.
        chapter_index: 0-based chapter index.

    Returns:
        ChapterCoverage with level and target_words.
    """
    # Filter whitelist to this chapter
    chapter_quotes = [
        q for q in whitelist
        if chapter_index in q.chapter_indices
    ]

    # Filter by minimum length
    usable_quotes = [
        q for q in chapter_quotes
        if len(q.quote_text.split()) >= MIN_USABLE_QUOTE_LENGTH
    ]

    claim_count = len(chapter_evidence.claims)
    total_quote_words = sum(len(q.quote_text.split()) for q in usable_quotes)

    # Compute metrics
    quotes_per_claim = len(usable_quotes) / max(claim_count, 1)
    quote_words_per_claim = total_quote_words / max(claim_count, 1)

    # Determine level
    if len(usable_quotes) >= STRONG_QUOTES and quote_words_per_claim >= STRONG_WORDS_PER_CLAIM:
        level = CoverageLevel.STRONG
        target_words = 800
        mode = "normal"
    elif len(usable_quotes) >= MEDIUM_QUOTES and quote_words_per_claim >= MEDIUM_WORDS_PER_CLAIM:
        level = CoverageLevel.MEDIUM
        target_words = 500
        mode = "thin"
    else:
        level = CoverageLevel.WEAK
        target_words = 250
        mode = "excerpt_only"

    return ChapterCoverage(
        chapter_index=chapter_index,
        level=level,
        usable_quotes=len(usable_quotes),
        quote_words_per_claim=quote_words_per_claim,
        quotes_per_claim=quotes_per_claim,
        target_words=target_words,
        generation_mode=mode,
    )
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/unit/test_whitelist_service.py::TestComputeChapterCoverage -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/services/whitelist_service.py backend/tests/unit/test_whitelist_service.py
git commit -m "feat: add compute_chapter_coverage function"
```

---

## Phase 4: Deterministic Excerpt Selector

### Task 9: Add select_deterministic_excerpts function

**Files:**
- Modify: `backend/src/services/whitelist_service.py`
- Test: `backend/tests/unit/test_whitelist_service.py`

**Step 1: Write failing tests**

```python
# Add to test_whitelist_service.py
from src.services.whitelist_service import select_deterministic_excerpts

class TestSelectDeterministicExcerpts:
    def test_selects_correct_count_for_strong(self):
        """Test STRONG coverage gets 4 excerpts."""
        whitelist = [_make_guest_quote(f"Quote {i}") for i in range(10)]
        excerpts = select_deterministic_excerpts(whitelist, chapter_index=0, coverage_level=CoverageLevel.STRONG)
        assert len(excerpts) == 4

    def test_selects_correct_count_for_medium(self):
        """Test MEDIUM coverage gets 3 excerpts."""
        whitelist = [_make_guest_quote(f"Quote {i}") for i in range(10)]
        excerpts = select_deterministic_excerpts(whitelist, chapter_index=0, coverage_level=CoverageLevel.MEDIUM)
        assert len(excerpts) == 3

    def test_selects_correct_count_for_weak(self):
        """Test WEAK coverage gets 2 excerpts."""
        whitelist = [_make_guest_quote(f"Quote {i}") for i in range(10)]
        excerpts = select_deterministic_excerpts(whitelist, chapter_index=0, coverage_level=CoverageLevel.WEAK)
        assert len(excerpts) == 2

    def test_filters_to_guest_only(self):
        """Test only GUEST quotes are selected."""
        whitelist = [
            _make_guest_quote("Guest quote 1"),
            _make_host_quote("Host quote"),
            _make_guest_quote("Guest quote 2"),
        ]
        excerpts = select_deterministic_excerpts(whitelist, chapter_index=0, coverage_level=CoverageLevel.STRONG)
        for e in excerpts:
            assert e.speaker.speaker_role == SpeakerRole.GUEST

    def test_filters_to_chapter(self):
        """Test only quotes for this chapter are selected."""
        whitelist = [
            _make_guest_quote("Quote ch0", chapter_indices=[0]),
            _make_guest_quote("Quote ch1", chapter_indices=[1]),
        ]
        excerpts = select_deterministic_excerpts(whitelist, chapter_index=0, coverage_level=CoverageLevel.STRONG)
        for e in excerpts:
            assert 0 in e.chapter_indices

    def test_stable_ordering(self):
        """Test same input always produces same order."""
        whitelist = [_make_guest_quote(f"Quote {i}") for i in range(10)]
        excerpts1 = select_deterministic_excerpts(whitelist, chapter_index=0, coverage_level=CoverageLevel.STRONG)
        excerpts2 = select_deterministic_excerpts(whitelist, chapter_index=0, coverage_level=CoverageLevel.STRONG)
        assert [e.quote_id for e in excerpts1] == [e.quote_id for e in excerpts2]

    def test_prefers_longer_quotes(self):
        """Test longer quotes are selected first."""
        whitelist = [
            _make_guest_quote("Short"),
            _make_guest_quote("This is a much longer quote with many words"),
            _make_guest_quote("Medium length quote here"),
        ]
        excerpts = select_deterministic_excerpts(whitelist, chapter_index=0, coverage_level=CoverageLevel.WEAK)
        # First excerpt should be the longest
        assert "much longer" in excerpts[0].quote_text


def _make_guest_quote(text: str, chapter_indices: list[int] | None = None) -> WhitelistQuote:
    """Create a GUEST WhitelistQuote for testing."""
    if chapter_indices is None:
        chapter_indices = [0]
    quote_id = sha256(text.encode()).hexdigest()[:16]
    return WhitelistQuote(
        quote_id=quote_id,
        quote_text=text,
        quote_canonical=text.lower(),
        speaker=SpeakerRef(
            speaker_id="guest_speaker",
            speaker_name="Guest Speaker",
            speaker_role=SpeakerRole.GUEST,
        ),
        source_evidence_ids=["ev1"],
        chapter_indices=chapter_indices,
        match_spans=[(0, len(text))],
    )


def _make_host_quote(text: str, chapter_indices: list[int] | None = None) -> WhitelistQuote:
    """Create a HOST WhitelistQuote for testing."""
    if chapter_indices is None:
        chapter_indices = [0]
    quote_id = sha256(text.encode()).hexdigest()[:16]
    return WhitelistQuote(
        quote_id=quote_id,
        quote_text=text,
        quote_canonical=text.lower(),
        speaker=SpeakerRef(
            speaker_id="host_speaker",
            speaker_name="Host Speaker",
            speaker_role=SpeakerRole.HOST,
        ),
        source_evidence_ids=["ev1"],
        chapter_indices=chapter_indices,
        match_spans=[(0, len(text))],
    )
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_whitelist_service.py::TestSelectDeterministicExcerpts -v`
Expected: FAIL with ImportError

**Step 3: Write minimal implementation**

```python
# Add to backend/src/services/whitelist_service.py

EXCERPT_COUNTS = {
    CoverageLevel.STRONG: 4,
    CoverageLevel.MEDIUM: 3,
    CoverageLevel.WEAK: 2,
}


def select_deterministic_excerpts(
    whitelist: list[WhitelistQuote],
    chapter_index: int,
    coverage_level: CoverageLevel,
) -> list[WhitelistQuote]:
    """Select Key Excerpts deterministically from whitelist.

    Valid by construction: these quotes come from whitelist,
    so they're guaranteed to be transcript substrings with known speakers.

    Args:
        whitelist: Validated quote whitelist.
        chapter_index: 0-based chapter index.
        coverage_level: Coverage level for count selection.

    Returns:
        List of selected WhitelistQuote entries.
    """
    # Filter to this chapter, GUEST only
    candidates = [
        q for q in whitelist
        if chapter_index in q.chapter_indices
        and q.speaker.speaker_role == SpeakerRole.GUEST
    ]

    # Stable sort: longest first, then by quote_id for ties
    candidates.sort(key=lambda q: (-len(q.quote_text), q.quote_id))

    count = EXCERPT_COUNTS[coverage_level]
    return candidates[:count]
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/unit/test_whitelist_service.py::TestSelectDeterministicExcerpts -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/services/whitelist_service.py backend/tests/unit/test_whitelist_service.py
git commit -m "feat: add select_deterministic_excerpts function"
```

---

## Phase 5: Whitelist Enforcer (HARD GATE 2)

### Task 10: Add enforce_quote_whitelist function

**Files:**
- Modify: `backend/src/services/whitelist_service.py`
- Test: `backend/tests/unit/test_whitelist_service.py`

**Step 1: Write failing tests**

```python
# Add to test_whitelist_service.py
from src.services.whitelist_service import enforce_quote_whitelist, EnforcementResult

class TestEnforceQuoteWhitelist:
    def test_replaces_valid_blockquote_with_exact_text(self):
        """Test valid blockquotes are replaced with exact quote_text."""
        whitelist = [_make_guest_quote("Wisdom is limitless")]
        text = '> "wisdom is limitless"\n> — Guest Speaker'

        result = enforce_quote_whitelist(text, whitelist, chapter_index=0)

        assert "Wisdom is limitless" in result.text  # Exact from whitelist
        assert len(result.replaced) == 1
        assert len(result.dropped) == 0

    def test_drops_invalid_blockquote(self):
        """Test invalid blockquotes are dropped entirely."""
        whitelist = [_make_guest_quote("Wisdom is limitless")]
        text = '> "This quote is not in whitelist"\n> — Someone'

        result = enforce_quote_whitelist(text, whitelist, chapter_index=0)

        assert "not in whitelist" not in result.text
        assert len(result.dropped) == 1

    def test_replaces_valid_inline_quote(self):
        """Test valid inline quotes are replaced with exact text."""
        whitelist = [_make_guest_quote("Wisdom is limitless")]
        text = 'He said "wisdom is limitless" today.'

        result = enforce_quote_whitelist(text, whitelist, chapter_index=0)

        assert '"Wisdom is limitless"' in result.text

    def test_unquotes_invalid_inline_quote(self):
        """Test invalid inline quotes have quotes removed."""
        whitelist = [_make_guest_quote("Wisdom is limitless")]
        text = 'He said "fabricated quote" today.'

        result = enforce_quote_whitelist(text, whitelist, chapter_index=0)

        # Quote marks removed but text preserved
        assert '"fabricated quote"' not in result.text
        assert 'fabricated quote' in result.text

    def test_multi_candidate_lookup_same_quote_different_speakers(self):
        """Test multi-candidate lookup handles same quote from different speakers."""
        whitelist = [
            _make_guest_quote("The truth matters", speaker_name="David"),
            _make_guest_quote("The truth matters", speaker_name="Naval"),
        ]
        text = '> "The truth matters"\n> — David'

        result = enforce_quote_whitelist(text, whitelist, chapter_index=0)

        assert len(result.replaced) == 1
        # Should match David specifically

    def test_chapter_scoping(self):
        """Test quotes are scoped to chapter."""
        whitelist = [_make_guest_quote("Chapter 0 only", chapter_indices=[0])]
        text = '> "Chapter 0 only"\n> — Guest Speaker'

        # Chapter 0 - should match
        result0 = enforce_quote_whitelist(text, whitelist, chapter_index=0)
        assert len(result0.replaced) == 1

        # Chapter 1 - should not match (falls back to any)
        result1 = enforce_quote_whitelist(text, whitelist, chapter_index=1)
        # Still matches because fallback allows any chapter
        assert len(result1.replaced) == 1


class TestEnforcementResult:
    def test_enforcement_result_model(self):
        """Test EnforcementResult model structure."""
        result = EnforcementResult(
            text="cleaned text",
            replaced=[],
            dropped=["invalid quote"],
        )
        assert result.text == "cleaned text"
        assert len(result.dropped) == 1
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_whitelist_service.py::TestEnforceQuoteWhitelist -v`
Expected: FAIL with ImportError

**Step 3: Write minimal implementation**

```python
# Add to backend/src/services/whitelist_service.py
import re
from dataclasses import dataclass


@dataclass
class EnforcementResult:
    """Result of whitelist enforcement."""
    text: str
    replaced: list[WhitelistQuote]
    dropped: list[str]


# Patterns for quote extraction
BLOCKQUOTE_PATTERN = re.compile(
    r'^>\s*["\u201c](?P<quote>[^"\u201d]+)["\u201d]\s*$\n'
    r'^>\s*[—\-]\s*(?P<speaker>.+?)\s*$',
    re.MULTILINE
)

INLINE_QUOTE_PATTERN = re.compile(
    r'["\u201c](?P<quote>[^"\u201d]{5,})["\u201d]'
)


def enforce_quote_whitelist(
    generated_text: str,
    whitelist: list[WhitelistQuote],
    chapter_index: int,
) -> EnforcementResult:
    """Enforce ALL quotes against whitelist.

    This is the hard guarantee. Quotes not in whitelist are removed.
    Quotes in whitelist are replaced with exact quote_text.

    Args:
        generated_text: LLM-generated text with quotes.
        whitelist: Validated quote whitelist.
        chapter_index: 0-based chapter index.

    Returns:
        EnforcementResult with cleaned text and tracking.
    """
    # Build lookup index: (speaker_id, quote_canonical) -> list[WhitelistQuote]
    lookup: dict[tuple[str, str], list[WhitelistQuote]] = {}
    for q in whitelist:
        key = (q.speaker.speaker_id, q.quote_canonical)
        lookup.setdefault(key, []).append(q)

    result = generated_text
    dropped = []
    replaced = []

    # Process block quotes
    for match in list(BLOCKQUOTE_PATTERN.finditer(result)):
        quote_text = match.group("quote")
        speaker_text = match.group("speaker")

        validated = _validate_blockquote(
            quote_text, speaker_text, chapter_index, lookup, whitelist
        )

        if validated:
            # Replace with exact quote_text
            replacement = f'> "{validated.quote_text}"\n> — {validated.speaker.speaker_name}'
            result = result[:match.start()] + replacement + result[match.end():]
            replaced.append(validated)
        else:
            # Drop the blockquote entirely
            result = result[:match.start()] + result[match.end():]
            dropped.append(quote_text)

    # Process inline quotes
    for match in list(INLINE_QUOTE_PATTERN.finditer(result)):
        quote_text = match.group("quote")

        validated = _validate_inline(quote_text, chapter_index, lookup, whitelist)

        if validated:
            # Replace with exact quote_text
            replacement = f'"{validated.quote_text}"'
            result = result[:match.start()] + replacement + result[match.end():]
            replaced.append(validated)
        else:
            # Remove quotes but keep text (convert to paraphrase)
            result = result[:match.start()] + quote_text + result[match.end():]
            dropped.append(quote_text)

    return EnforcementResult(
        text=result,
        replaced=replaced,
        dropped=dropped,
    )


def _validate_blockquote(
    quote_text: str,
    speaker_text: str | None,
    chapter_index: int,
    lookup: dict[tuple[str, str], list[WhitelistQuote]],
    whitelist: list[WhitelistQuote],
) -> WhitelistQuote | None:
    """Find matching whitelist entry for a block quote."""
    quote_canonical = canonicalize_transcript(quote_text).casefold()

    # Try to resolve speaker
    if speaker_text:
        speaker_id = speaker_text.lower().replace(" ", "_").replace(".", "")
        candidates = lookup.get((speaker_id, quote_canonical), [])
    else:
        # No speaker—search all entries with this quote
        candidates = []
        for (sid, qc), entries in lookup.items():
            if qc == quote_canonical:
                candidates.extend(entries)

    # Find best match for this chapter
    for candidate in candidates:
        if chapter_index in candidate.chapter_indices:
            return candidate

    # Fall back to any candidate
    return candidates[0] if candidates else None


def _validate_inline(
    quote_text: str,
    chapter_index: int,
    lookup: dict[tuple[str, str], list[WhitelistQuote]],
    whitelist: list[WhitelistQuote],
) -> WhitelistQuote | None:
    """Find matching whitelist entry for an inline quote."""
    quote_canonical = canonicalize_transcript(quote_text).casefold()

    # Search all entries with this quote (no speaker info for inline)
    candidates = []
    for (sid, qc), entries in lookup.items():
        if qc == quote_canonical:
            candidates.extend(entries)

    # Find best match for this chapter
    for candidate in candidates:
        if chapter_index in candidate.chapter_indices:
            return candidate

    # Fall back to any candidate
    return candidates[0] if candidates else None
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/unit/test_whitelist_service.py::TestEnforceQuoteWhitelist -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/services/whitelist_service.py backend/tests/unit/test_whitelist_service.py
git commit -m "feat: add enforce_quote_whitelist function (HARD GATE 2)"
```

---

### Task 11: Add enforce_core_claims_guest_only function

**Files:**
- Modify: `backend/src/services/whitelist_service.py`
- Test: `backend/tests/unit/test_whitelist_service.py`

**Step 1: Write failing tests**

```python
# Add to test_whitelist_service.py
from src.services.whitelist_service import enforce_core_claims_guest_only
from dataclasses import dataclass

@dataclass
class CoreClaim:
    """Simple CoreClaim for testing."""
    claim_text: str
    supporting_quote: str


class TestEnforceCoreclaimsGuestOnly:
    def test_keeps_guest_claims(self):
        """Test claims with GUEST quotes are kept."""
        whitelist = [_make_guest_quote("Wisdom is limitless")]
        claims = [CoreClaim(claim_text="Wisdom has no bounds", supporting_quote="Wisdom is limitless")]

        result = enforce_core_claims_guest_only(claims, whitelist, chapter_index=0)

        assert len(result) == 1

    def test_drops_host_claims(self):
        """Test claims with HOST quotes are dropped."""
        whitelist = [_make_host_quote("Welcome everyone")]
        claims = [CoreClaim(claim_text="Greeting", supporting_quote="Welcome everyone")]

        result = enforce_core_claims_guest_only(claims, whitelist, chapter_index=0)

        assert len(result) == 0

    def test_drops_claims_not_in_whitelist(self):
        """Test claims with quotes not in whitelist are dropped."""
        whitelist = [_make_guest_quote("Wisdom is limitless")]
        claims = [CoreClaim(claim_text="Test", supporting_quote="Not in whitelist")]

        result = enforce_core_claims_guest_only(claims, whitelist, chapter_index=0)

        assert len(result) == 0

    def test_filters_by_chapter(self):
        """Test claims are filtered by chapter index."""
        whitelist = [_make_guest_quote("Chapter 0 quote", chapter_indices=[0])]
        claims = [CoreClaim(claim_text="Test", supporting_quote="Chapter 0 quote")]

        result0 = enforce_core_claims_guest_only(claims, whitelist, chapter_index=0)
        result1 = enforce_core_claims_guest_only(claims, whitelist, chapter_index=1)

        assert len(result0) == 1
        assert len(result1) == 0  # Not in chapter 1
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_whitelist_service.py::TestEnforceCoreclaimsGuestOnly -v`
Expected: FAIL with ImportError

**Step 3: Write minimal implementation**

```python
# Add to backend/src/services/whitelist_service.py
from typing import Protocol


class CoreClaimProtocol(Protocol):
    """Protocol for CoreClaim-like objects."""
    claim_text: str
    supporting_quote: str


def enforce_core_claims_guest_only(
    claims: list[CoreClaimProtocol],
    whitelist: list[WhitelistQuote],
    chapter_index: int,
) -> list[CoreClaimProtocol]:
    """Filter Core Claims to only include GUEST quotes.

    Uses whitelist speaker role—doesn't parse attribution from text.

    Args:
        claims: List of CoreClaim objects.
        whitelist: Validated quote whitelist.
        chapter_index: 0-based chapter index.

    Returns:
        Filtered list of claims with GUEST quotes only.
    """
    # Build quote lookup for this chapter
    quote_to_entry: dict[str, WhitelistQuote] = {}
    for q in whitelist:
        if chapter_index in q.chapter_indices:
            quote_to_entry[q.quote_canonical] = q

    valid_claims = []
    for claim in claims:
        quote_canonical = canonicalize_transcript(claim.supporting_quote).casefold()

        entry = quote_to_entry.get(quote_canonical)
        if not entry:
            continue  # Quote not in whitelist

        if entry.speaker.speaker_role != SpeakerRole.GUEST:
            continue  # Not from guest

        valid_claims.append(claim)

    return valid_claims
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/unit/test_whitelist_service.py::TestEnforceCoreclaimsGuestOnly -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/services/whitelist_service.py backend/tests/unit/test_whitelist_service.py
git commit -m "feat: add enforce_core_claims_guest_only function"
```

---

### Task 12: Add strip_llm_blockquotes function

**Files:**
- Modify: `backend/src/services/whitelist_service.py`
- Test: `backend/tests/unit/test_whitelist_service.py`

**Step 1: Write failing tests**

```python
# Add to test_whitelist_service.py
from src.services.whitelist_service import strip_llm_blockquotes

class TestStripLlmBlockquotes:
    def test_preserves_key_excerpts_section(self):
        """Test Key Excerpts blockquotes are preserved."""
        text = '''## Narrative

Some text here.

### Key Excerpts

> "Valid excerpt"
> — Speaker

### Core Claims

More text.'''

        result = strip_llm_blockquotes(text)

        assert '> "Valid excerpt"' in result
        assert "— Speaker" in result

    def test_strips_blockquotes_from_narrative(self):
        """Test blockquotes in narrative are stripped."""
        text = '''## Narrative

> "LLM added this quote"
> — Someone

Some legitimate text.

### Key Excerpts

> "Valid excerpt"
> — Speaker'''

        result = strip_llm_blockquotes(text)

        assert "LLM added this quote" not in result
        assert '> "Valid excerpt"' in result

    def test_strips_blockquotes_from_core_claims(self):
        """Test blockquotes in Core Claims section are stripped."""
        text = '''### Key Excerpts

> "Valid excerpt"
> — Speaker

### Core Claims

> "Should not be blockquote"
> — Someone

- **Claim**: "valid claim"'''

        result = strip_llm_blockquotes(text)

        assert '> "Valid excerpt"' in result
        assert '> "Should not be blockquote"' not in result

    def test_handles_no_key_excerpts(self):
        """Test handles text without Key Excerpts section."""
        text = '''## Chapter

> "Some blockquote"
> — Someone

Regular text.'''

        result = strip_llm_blockquotes(text)

        assert '> "Some blockquote"' not in result
        assert "Regular text" in result
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_whitelist_service.py::TestStripLlmBlockquotes -v`
Expected: FAIL with ImportError

**Step 3: Write minimal implementation**

```python
# Add to backend/src/services/whitelist_service.py

BLOCKQUOTE_LINE_PATTERN = re.compile(r'^>\s*.*$', re.MULTILINE)


def strip_llm_blockquotes(generated_text: str) -> str:
    """Remove blockquote syntax LLM added outside Key Excerpts.

    Key Excerpts section was injected deterministically and is preserved.
    Narrative should paraphrase, not quote—strip any blockquotes there.

    Args:
        generated_text: LLM-generated text.

    Returns:
        Text with blockquotes stripped from non-Key Excerpts sections.
    """
    # Find Key Excerpts section
    key_excerpts_match = re.search(r'### Key Excerpts', generated_text)

    if key_excerpts_match:
        before = generated_text[:key_excerpts_match.start()]
        after = generated_text[key_excerpts_match.start():]

        # Strip blockquotes from narrative (before Key Excerpts)
        before = BLOCKQUOTE_LINE_PATTERN.sub('', before)

        # Find Core Claims section within after
        core_claims_match = re.search(r'### Core Claims', after)
        if core_claims_match:
            excerpts_section = after[:core_claims_match.start()]
            claims_and_rest = after[core_claims_match.start():]

            # Strip blockquotes from Core Claims too (quotes should be inline only)
            claims_and_rest = BLOCKQUOTE_LINE_PATTERN.sub('', claims_and_rest)

            return before + excerpts_section + claims_and_rest

        return before + after

    # No Key Excerpts found—strip all blockquotes
    return BLOCKQUOTE_LINE_PATTERN.sub('', generated_text)
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/unit/test_whitelist_service.py::TestStripLlmBlockquotes -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/services/whitelist_service.py backend/tests/unit/test_whitelist_service.py
git commit -m "feat: add strip_llm_blockquotes function"
```

---

### Task 13: HARD GATE 2 - Enforcer Regression Tests

**Files:**
- Test: `backend/tests/unit/test_whitelist_service.py`

**Step 1: Write comprehensive regression tests**

```python
# Add to test_whitelist_service.py
class TestWhitelistEnforcerHardGate:
    """HARD GATE 2: Enforcer correctness tests.

    These tests prove:
    - Multi-candidate lookup works correctly
    - Chapter merge scoping (source_chapters) works
    - Core Claims = GUEST-only
    """

    def test_multi_candidate_same_quote_selects_correct_speaker(self):
        """Test same quote from different speakers picks correct one."""
        david_quote = WhitelistQuote(
            quote_id="david_q",
            quote_text="The truth matters",
            quote_canonical="the truth matters",
            speaker=SpeakerRef(
                speaker_id="david_deutsch",
                speaker_name="David Deutsch",
                speaker_role=SpeakerRole.GUEST,
            ),
            source_evidence_ids=["ev1"],
            chapter_indices=[0],
            match_spans=[(0, 17)],
        )
        naval_quote = WhitelistQuote(
            quote_id="naval_q",
            quote_text="The truth matters",
            quote_canonical="the truth matters",
            speaker=SpeakerRef(
                speaker_id="naval_ravikant",
                speaker_name="Naval Ravikant",
                speaker_role=SpeakerRole.HOST,
            ),
            source_evidence_ids=["ev2"],
            chapter_indices=[0],
            match_spans=[(0, 17)],
        )
        whitelist = [david_quote, naval_quote]

        # Text with David attribution
        text = '> "The truth matters"\n> — David Deutsch'
        result = enforce_quote_whitelist(text, whitelist, chapter_index=0)

        assert len(result.replaced) == 1
        assert result.replaced[0].speaker.speaker_name == "David Deutsch"

    def test_chapter_scoping_prefers_correct_chapter(self):
        """Test quotes scoped to multiple chapters prefer current chapter."""
        quote = WhitelistQuote(
            quote_id="q1",
            quote_text="Wisdom is limitless",
            quote_canonical="wisdom is limitless",
            speaker=SpeakerRef(
                speaker_id="david",
                speaker_name="David",
                speaker_role=SpeakerRole.GUEST,
            ),
            source_evidence_ids=["ev1", "ev2"],
            chapter_indices=[0, 2],  # Chapters 0 and 2
            match_spans=[(0, 19)],
        )
        whitelist = [quote]

        text = '> "Wisdom is limitless"\n> — David'

        # Chapter 0 - exact match
        result0 = enforce_quote_whitelist(text, whitelist, chapter_index=0)
        assert len(result0.replaced) == 1

        # Chapter 1 - no exact match, but falls back to any
        result1 = enforce_quote_whitelist(text, whitelist, chapter_index=1)
        assert len(result1.replaced) == 1

        # Chapter 2 - exact match
        result2 = enforce_quote_whitelist(text, whitelist, chapter_index=2)
        assert len(result2.replaced) == 1

    def test_core_claims_guest_only_strict(self):
        """Test Core Claims GUEST-only is strictly enforced."""
        guest_quote = _make_guest_quote("Guest wisdom")
        host_quote = _make_host_quote("Host welcome")

        whitelist = [guest_quote, host_quote]

        guest_claim = CoreClaim(claim_text="Guest insight", supporting_quote="Guest wisdom")
        host_claim = CoreClaim(claim_text="Host opening", supporting_quote="Host welcome")

        result = enforce_core_claims_guest_only(
            [guest_claim, host_claim],
            whitelist,
            chapter_index=0,
        )

        assert len(result) == 1
        assert result[0].claim_text == "Guest insight"

    def test_fabricated_quotes_always_dropped(self):
        """Test fabricated quotes (not in whitelist) are always dropped."""
        whitelist = [_make_guest_quote("Real quote")]

        # Blockquote - fabricated
        text1 = '> "Fabricated quote"\n> — Someone'
        result1 = enforce_quote_whitelist(text1, whitelist, chapter_index=0)
        assert len(result1.dropped) == 1
        assert "Fabricated quote" not in result1.text

        # Inline - fabricated
        text2 = 'He said "Fabricated inline" today.'
        result2 = enforce_quote_whitelist(text2, whitelist, chapter_index=0)
        assert len(result2.dropped) == 1
        # Text is kept but unquoted
        assert '"Fabricated inline"' not in result2.text

    def test_valid_quotes_use_exact_whitelist_text(self):
        """Test valid quotes are replaced with exact whitelist quote_text."""
        whitelist = [
            WhitelistQuote(
                quote_id="q1",
                quote_text="Wisdom IS Limitless",  # Exact case from transcript
                quote_canonical="wisdom is limitless",
                speaker=SpeakerRef(
                    speaker_id="david",
                    speaker_name="David",
                    speaker_role=SpeakerRole.GUEST,
                ),
                source_evidence_ids=["ev1"],
                chapter_indices=[0],
                match_spans=[(0, 19)],
            )
        ]

        # LLM used different case
        text = '> "wisdom is limitless"\n> — David'
        result = enforce_quote_whitelist(text, whitelist, chapter_index=0)

        # Should be replaced with exact whitelist text
        assert "Wisdom IS Limitless" in result.text
```

**Step 2: Run tests**

Run: `cd backend && python -m pytest tests/unit/test_whitelist_service.py::TestWhitelistEnforcerHardGate -v`
Expected: PASS

**Step 3: Commit**

```bash
git add backend/tests/unit/test_whitelist_service.py
git commit -m "test: add HARD GATE 2 regression tests for whitelist enforcer"
```

---

## Phase 6: Prompt Integration (HARD GATE 3)

### Task 14: Add format_excerpts_markdown function

**Files:**
- Modify: `backend/src/services/whitelist_service.py`
- Test: `backend/tests/unit/test_whitelist_service.py`

**Step 1: Write failing tests**

```python
# Add to test_whitelist_service.py
from src.services.whitelist_service import format_excerpts_markdown

class TestFormatExcerptsMarkdown:
    def test_formats_single_excerpt(self):
        """Test single excerpt is formatted correctly."""
        excerpts = [_make_guest_quote("Wisdom is limitless", speaker_name="David Deutsch")]
        result = format_excerpts_markdown(excerpts)

        assert '> "Wisdom is limitless"' in result
        assert "— David Deutsch" in result

    def test_formats_multiple_excerpts(self):
        """Test multiple excerpts are formatted with separation."""
        excerpts = [
            _make_guest_quote("Quote one", speaker_name="Speaker A"),
            _make_guest_quote("Quote two", speaker_name="Speaker B"),
        ]
        result = format_excerpts_markdown(excerpts)

        assert '> "Quote one"' in result
        assert '> "Quote two"' in result
        assert "— Speaker A" in result
        assert "— Speaker B" in result

    def test_empty_list_returns_placeholder(self):
        """Test empty excerpt list returns placeholder."""
        result = format_excerpts_markdown([])

        assert "No excerpts available" in result or result == ""

    def test_output_is_valid_markdown(self):
        """Test output is valid markdown blockquote format."""
        excerpts = [_make_guest_quote("Test quote", speaker_name="Test Speaker")]
        result = format_excerpts_markdown(excerpts)

        # Each line of the blockquote should start with >
        for line in result.strip().split('\n'):
            if line.strip():
                assert line.startswith('>') or line == ''
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_whitelist_service.py::TestFormatExcerptsMarkdown -v`
Expected: FAIL with ImportError

**Step 3: Write minimal implementation**

```python
# Add to backend/src/services/whitelist_service.py

def format_excerpts_markdown(excerpts: list[WhitelistQuote]) -> str:
    """Format excerpts as markdown blockquotes for prompt injection.

    Args:
        excerpts: List of WhitelistQuote entries.

    Returns:
        Markdown-formatted blockquotes.
    """
    if not excerpts:
        return "*No excerpts available for this chapter.*"

    blocks = []
    for excerpt in excerpts:
        block = f'> "{excerpt.quote_text}"\n> — {excerpt.speaker.speaker_name}'
        blocks.append(block)

    return '\n\n'.join(blocks)
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/unit/test_whitelist_service.py::TestFormatExcerptsMarkdown -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/services/whitelist_service.py backend/tests/unit/test_whitelist_service.py
git commit -m "feat: add format_excerpts_markdown function"
```

---

### Task 15: HARD GATE 3 - Excerpt Injection Tests

**Files:**
- Test: `backend/tests/unit/test_whitelist_service.py`

**Step 1: Write injection verification tests**

```python
# Add to test_whitelist_service.py
class TestExcerptInjectionHardGate:
    """HARD GATE 3: Excerpt injection correctness tests.

    These tests prove:
    - Injected excerpts appear exactly once
    - Injected excerpts appear in correct location
    - LLM blockquotes are stripped while injected ones preserved
    """

    def test_injected_excerpts_appear_once(self):
        """Test injected excerpts appear exactly once in output."""
        excerpts = [_make_guest_quote("Unique test quote 12345")]
        formatted = format_excerpts_markdown(excerpts)

        # Simulate pipeline: inject + strip + enforce
        template = '''## Chapter Title

Narrative text here.

### Key Excerpts

{{KEY_EXCERPTS_PLACEHOLDER}}

### Core Claims

- **Claim**: "supporting quote"'''

        injected = template.replace("{{KEY_EXCERPTS_PLACEHOLDER}}", formatted)

        # After strip_llm_blockquotes, Key Excerpts should be preserved
        result = strip_llm_blockquotes(injected)

        # Count occurrences
        count = result.count("Unique test quote 12345")
        assert count == 1, f"Expected 1 occurrence, found {count}"

    def test_injected_excerpts_in_correct_section(self):
        """Test injected excerpts appear between Key Excerpts and Core Claims."""
        excerpts = [_make_guest_quote("Injected quote here")]
        formatted = format_excerpts_markdown(excerpts)

        template = '''## Chapter

Narrative.

### Key Excerpts

{{KEY_EXCERPTS_PLACEHOLDER}}

### Core Claims

Claims here.'''

        injected = template.replace("{{KEY_EXCERPTS_PLACEHOLDER}}", formatted)

        # Find positions
        key_excerpts_pos = injected.find("### Key Excerpts")
        core_claims_pos = injected.find("### Core Claims")
        quote_pos = injected.find("Injected quote here")

        assert key_excerpts_pos < quote_pos < core_claims_pos

    def test_llm_blockquotes_stripped_injected_preserved(self):
        """Test LLM-added blockquotes stripped while injected ones preserved."""
        excerpts = [_make_guest_quote("Legitimate excerpt")]
        formatted = format_excerpts_markdown(excerpts)

        # Simulate LLM adding extra blockquotes
        llm_output = f'''## Chapter

> "LLM added this"
> — Fabricated

Narrative text.

### Key Excerpts

{formatted}

### Core Claims

> "LLM added in claims"
> — Also fabricated

- **Claim**: "quote"'''

        result = strip_llm_blockquotes(llm_output)

        # LLM blockquotes should be gone
        assert "LLM added this" not in result
        assert "LLM added in claims" not in result

        # Legitimate excerpt should remain
        assert "Legitimate excerpt" in result
```

**Step 2: Run tests**

Run: `cd backend && python -m pytest tests/unit/test_whitelist_service.py::TestExcerptInjectionHardGate -v`
Expected: PASS

**Step 3: Commit**

```bash
git add backend/tests/unit/test_whitelist_service.py
git commit -m "test: add HARD GATE 3 regression tests for excerpt injection"
```

---

## Phase 7: Integration

### Task 16: Update exports and integrate with draft_service

**Files:**
- Modify: `backend/src/services/__init__.py`
- Modify: `backend/src/services/draft_service.py`

**Step 1: Export whitelist service functions**

```python
# Add to backend/src/services/__init__.py
from .whitelist_service import (
    canonicalize_transcript,
    build_quote_whitelist,
    compute_chapter_coverage,
    select_deterministic_excerpts,
    enforce_quote_whitelist,
    enforce_core_claims_guest_only,
    strip_llm_blockquotes,
    format_excerpts_markdown,
    EnforcementResult,
)
```

**Step 2: Integration point in draft_service.py**

The integration with the full pipeline will be done in a separate task after testing confirms all components work individually.

**Step 3: Run full test suite**

Run: `cd backend && python -m pytest tests/unit/test_whitelist_service.py -v`
Expected: All tests PASS

**Step 4: Commit**

```bash
git add backend/src/services/__init__.py
git commit -m "feat: export whitelist service functions"
```

---

## Summary

This plan implements the whitelist-based quote generation system in 16 tasks across 7 phases:

1. **Phase 1 (Tasks 1-3):** Data structures - models for speaker typing, whitelist quotes, coverage
2. **Phase 2 (Tasks 4-7):** Whitelist builder with HARD GATE 1 tests
3. **Phase 3 (Task 8):** Coverage scorer
4. **Phase 4 (Task 9):** Deterministic excerpt selector
5. **Phase 5 (Tasks 10-13):** Whitelist enforcer with HARD GATE 2 tests
6. **Phase 6 (Tasks 14-15):** Prompt integration with HARD GATE 3 tests
7. **Phase 7 (Task 16):** Integration and exports

**Hard Gates:**
- HARD GATE 1 (Task 7): Whitelist builder correctness - raw/canonical alignment, curly quotes, duplicates
- HARD GATE 2 (Task 13): Enforcer correctness - multi-candidate lookup, chapter scoping, GUEST-only
- HARD GATE 3 (Task 15): Excerpt injection - appears once, correct location, LLM blockquotes stripped
