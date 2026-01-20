# Ideas Edition Convergence Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Eliminate empty sections, stabilize word counts, and complete Ideas Edition by shifting from "generate → enforce → delete" to "plan → compile → validate".

**Architecture:** Pre-generation coverage planning determines feasibility. Key Excerpts and Core Claims are compiled (not generated) from whitelist. Fallback chains prevent empties. Assembly-time invariants catch violations before output.

**Tech Stack:** Python 3.11, FastAPI, Pydantic v2, pytest

---

## Context

ChatGPT analysis identified the root cause: LLM generates → enforcer deletes → headings stay empty. The fix is deterministic assembly:

1. **Preflight** - Coverage report predicts feasibility before generation
2. **Compile** - Key Excerpts/Core Claims built from whitelist (not LLM output)
3. **Validate** - Assembly-time invariants catch empties before output
4. **Fallback** - Deterministic chain prevents empties (merge chapters if needed)

## Recent Fixes (Already Committed)

- `select_deterministic_excerpts()` has 4-tier fallback (GUEST→any speaker→global GUEST→any global)
- `enforce_core_claims_text()` adds placeholder when all claims invalid
- Apostrophe preservation in prose
- Typed speaker attributions (GUEST/HOST/CALLER)

---

## Phase 1: Structural Invariants (Tests First)

### Task 1: Add structural invariant tests

**Files:**
- Create: `backend/tests/unit/test_structural_invariants.py`

**Step 1: Write the failing tests**

```python
"""Structural invariants for Ideas Edition output.

These tests assert properties that must NEVER be violated in final output.
"""
import re
import pytest


class TestKeyExcerptsInvariant:
    """Key Excerpts header must never be followed by empty content."""

    def test_no_empty_key_excerpts_section(self):
        """### Key Excerpts must have content or not appear at all."""
        # Pattern: ### Key Excerpts followed by only whitespace until next heading
        empty_pattern = re.compile(
            r'### Key Excerpts\s*\n\s*(?=### |## |\Z)',
            re.MULTILINE
        )

        sample_bad = '''## Chapter 1

Prose here.

### Key Excerpts

### Core Claims
'''
        sample_good = '''## Chapter 1

Prose here.

### Key Excerpts

> "Valid quote here"
> — Speaker (GUEST)

### Core Claims
'''

        assert empty_pattern.search(sample_bad) is not None, "Bad sample should match"
        assert empty_pattern.search(sample_good) is None, "Good sample should not match"

    def test_detect_empty_key_excerpts_in_multi_chapter(self):
        """Detect empties across multiple chapters."""
        from backend.src.services.structural_invariants import find_empty_sections

        doc = '''## Chapter 1

### Key Excerpts

> "Quote"
> — Speaker (GUEST)

## Chapter 2

### Key Excerpts

### Core Claims
'''
        empties = find_empty_sections(doc)
        assert len(empties) == 1
        assert empties[0]["chapter"] == 2
        assert empties[0]["section"] == "Key Excerpts"


class TestCoreClaimsInvariant:
    """Core Claims must have content or a placeholder."""

    def test_no_empty_core_claims_without_placeholder(self):
        """### Core Claims must have bullets or placeholder."""
        from backend.src.services.structural_invariants import find_empty_sections

        doc = '''## Chapter 1

### Core Claims

## Chapter 2
'''
        empties = find_empty_sections(doc)
        assert len(empties) == 1
        assert empties[0]["section"] == "Core Claims"

    def test_placeholder_is_acceptable(self):
        """Placeholder message is not considered 'empty'."""
        from backend.src.services.structural_invariants import find_empty_sections

        doc = '''## Chapter 1

### Core Claims

*No fully grounded claims available for this chapter.*

## Chapter 2
'''
        empties = find_empty_sections(doc)
        assert len(empties) == 0


class TestNoInlineQuotesInvariant:
    """Quotes only allowed in Key Excerpts and Core Claims."""

    def test_detects_inline_quotes_in_prose(self):
        """Quotes in narrative prose are violations."""
        from backend.src.services.structural_invariants import find_inline_quote_violations

        doc = '''## Chapter 1

David said "this is important" in the interview.

### Key Excerpts

> "Valid quote"
> — Speaker (GUEST)
'''
        violations = find_inline_quote_violations(doc)
        assert len(violations) == 1
        assert "this is important" in violations[0]["quote"]

    def test_allows_quotes_in_key_excerpts(self):
        """Quotes inside Key Excerpts are fine."""
        from backend.src.services.structural_invariants import find_inline_quote_violations

        doc = '''## Chapter 1

Prose without quotes.

### Key Excerpts

> "This quote is allowed"
> — Speaker (GUEST)

### Core Claims

- **Claim**: "This quote is also allowed"
'''
        violations = find_inline_quote_violations(doc)
        assert len(violations) == 0
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_structural_invariants.py -v`
Expected: FAIL with "No module named 'backend.src.services.structural_invariants'"

**Step 3: Create the structural_invariants module**

```python
"""Structural invariants for Ideas Edition output.

These functions detect violations of invariants that must NEVER
occur in final output:
1. No empty Key Excerpts sections
2. No empty Core Claims without placeholder
3. No inline quotes in narrative prose
"""
import re
from typing import TypedDict


class EmptySection(TypedDict):
    chapter: int
    section: str
    start_pos: int


class InlineQuoteViolation(TypedDict):
    chapter: int
    quote: str
    line: str
    line_num: int


def find_empty_sections(markdown: str) -> list[EmptySection]:
    """Find sections that are empty (no content between header and next section).

    Args:
        markdown: Full document markdown.

    Returns:
        List of empty section descriptors.
    """
    empties = []

    # Find all chapter boundaries
    chapter_pattern = re.compile(r'^## Chapter (\d+)', re.MULTILINE)
    chapters = list(chapter_pattern.finditer(markdown))

    for i, chapter_match in enumerate(chapters):
        chapter_num = int(chapter_match.group(1))
        chapter_start = chapter_match.start()
        chapter_end = chapters[i + 1].start() if i + 1 < len(chapters) else len(markdown)
        chapter_text = markdown[chapter_start:chapter_end]

        # Check Key Excerpts
        key_excerpts_empty = re.search(
            r'### Key Excerpts\s*\n\s*(?=### |## |\Z)',
            chapter_text
        )
        if key_excerpts_empty:
            empties.append({
                "chapter": chapter_num,
                "section": "Key Excerpts",
                "start_pos": chapter_start + key_excerpts_empty.start(),
            })

        # Check Core Claims (empty = no bullets AND no placeholder)
        core_claims_match = re.search(
            r'### Core Claims\s*\n(.*?)(?=### |## |\Z)',
            chapter_text,
            re.DOTALL
        )
        if core_claims_match:
            content = core_claims_match.group(1).strip()
            # Empty if no bullets (-) and no placeholder (*No fully grounded*)
            has_bullets = bool(re.search(r'^- \*\*', content, re.MULTILINE))
            has_placeholder = '*No fully grounded claims' in content
            if not has_bullets and not has_placeholder:
                empties.append({
                    "chapter": chapter_num,
                    "section": "Core Claims",
                    "start_pos": chapter_start + core_claims_match.start(),
                })

    return empties


def find_inline_quote_violations(markdown: str) -> list[InlineQuoteViolation]:
    """Find quotes that appear outside Key Excerpts and Core Claims.

    Args:
        markdown: Full document markdown.

    Returns:
        List of inline quote violations.
    """
    violations = []
    lines = markdown.split('\n')

    in_key_excerpts = False
    in_core_claims = False
    current_chapter = 0

    for line_num, line in enumerate(lines, 1):
        stripped = line.strip()

        # Track sections
        if stripped.startswith('## Chapter'):
            match = re.match(r'## Chapter (\d+)', stripped)
            if match:
                current_chapter = int(match.group(1))
            in_key_excerpts = False
            in_core_claims = False
        elif stripped == '### Key Excerpts':
            in_key_excerpts = True
            in_core_claims = False
        elif stripped == '### Core Claims':
            in_key_excerpts = False
            in_core_claims = True
        elif stripped.startswith('### ') or stripped.startswith('## '):
            in_key_excerpts = False
            in_core_claims = False

        # Skip allowed sections
        if in_key_excerpts or in_core_claims:
            continue

        # Skip blockquote lines (they're handled by Key Excerpts detection)
        if stripped.startswith('>'):
            continue

        # Find quotes in this line
        quote_pattern = re.compile(r'["\u201c]([^"\u201d]{5,})["\u201d]')
        for match in quote_pattern.finditer(line):
            violations.append({
                "chapter": current_chapter,
                "quote": match.group(1),
                "line": line.strip(),
                "line_num": line_num,
            })

    return violations


def validate_structural_invariants(markdown: str) -> dict:
    """Validate all structural invariants.

    Args:
        markdown: Full document markdown.

    Returns:
        Dict with 'valid' bool and 'violations' list.
    """
    empty_sections = find_empty_sections(markdown)
    inline_quotes = find_inline_quote_violations(markdown)

    return {
        "valid": len(empty_sections) == 0 and len(inline_quotes) == 0,
        "empty_sections": empty_sections,
        "inline_quotes": inline_quotes,
    }
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_structural_invariants.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/services/structural_invariants.py backend/tests/unit/test_structural_invariants.py
git commit -m "feat: add structural invariant validators for Ideas Edition

Adds functions to detect:
- Empty Key Excerpts sections
- Empty Core Claims without placeholder
- Inline quotes in narrative prose

These invariants must never be violated in final output."
```

---

### Task 2: Add CoverageReport model

**Files:**
- Modify: `backend/src/models/edition.py`
- Create: `backend/tests/unit/test_coverage_report.py`

**Step 1: Write the failing test**

```python
"""Tests for CoverageReport model."""
import pytest
from src.models.edition import CoverageReport, ChapterCoverageReport


class TestCoverageReport:
    def test_coverage_report_structure(self):
        """Test CoverageReport has required fields."""
        report = CoverageReport(
            transcript_hash="abc123",
            total_whitelist_quotes=10,
            chapters=[
                ChapterCoverageReport(
                    chapter_index=0,
                    valid_quotes=5,
                    invalid_quotes=2,
                    valid_claims=3,
                    invalid_claims=1,
                    predicted_word_range=(800, 1200),
                )
            ],
            predicted_total_range=(3200, 4800),
            is_feasible=True,
            feasibility_notes=[],
        )

        assert report.total_whitelist_quotes == 10
        assert len(report.chapters) == 1
        assert report.chapters[0].valid_quotes == 5
        assert report.is_feasible is True

    def test_coverage_report_detects_infeasible(self):
        """Test report marks as infeasible when quote count too low."""
        report = CoverageReport(
            transcript_hash="abc123",
            total_whitelist_quotes=2,
            chapters=[
                ChapterCoverageReport(
                    chapter_index=0,
                    valid_quotes=1,
                    invalid_quotes=5,
                    valid_claims=0,
                    invalid_claims=3,
                    predicted_word_range=(200, 400),
                )
            ],
            predicted_total_range=(200, 400),
            is_feasible=False,
            feasibility_notes=["Insufficient quotes for 4-chapter structure"],
        )

        assert report.is_feasible is False
        assert len(report.feasibility_notes) > 0
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_coverage_report.py -v`
Expected: FAIL with "cannot import name 'CoverageReport'"

**Step 3: Add models to edition.py**

```python
# Add to backend/src/models/edition.py

class ChapterCoverageReport(BaseModel):
    """Coverage report for a single chapter."""
    chapter_index: int
    valid_quotes: int
    invalid_quotes: int
    invalid_quote_reasons: list[str] = Field(default_factory=list)
    valid_claims: int
    invalid_claims: int
    invalid_claim_reasons: list[str] = Field(default_factory=list)
    predicted_word_range: tuple[int, int]  # (min, max)


class CoverageReport(BaseModel):
    """Pre-generation coverage analysis.

    Computed before generation to predict feasibility and word count.
    Deterministic for same transcript hash.
    """
    transcript_hash: str
    total_whitelist_quotes: int
    chapters: list[ChapterCoverageReport]
    predicted_total_range: tuple[int, int]  # (min, max) words
    is_feasible: bool
    feasibility_notes: list[str] = Field(default_factory=list)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_coverage_report.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/models/edition.py backend/tests/unit/test_coverage_report.py
git commit -m "feat: add CoverageReport model for pre-generation analysis"
```

---

### Task 3: Implement coverage report generator

**Files:**
- Modify: `backend/src/services/whitelist_service.py`
- Create: `backend/tests/unit/test_coverage_generator.py`

**Step 1: Write the failing test**

```python
"""Tests for coverage report generation."""
import pytest
from src.services.whitelist_service import generate_coverage_report
from src.models.edition import CoverageReport


class TestGenerateCoverageReport:
    def test_generates_report_from_whitelist(self):
        """Test report is generated from whitelist and evidence map."""
        # Setup: create whitelist with known quotes
        whitelist = [
            _make_guest_quote("Quote one with enough words here", chapter_indices=[0]),
            _make_guest_quote("Quote two with enough words here", chapter_indices=[0]),
            _make_guest_quote("Quote three for chapter two", chapter_indices=[1]),
        ]

        report = generate_coverage_report(
            whitelist=whitelist,
            chapter_count=2,
            transcript_hash="test123",
        )

        assert isinstance(report, CoverageReport)
        assert report.transcript_hash == "test123"
        assert report.total_whitelist_quotes == 3
        assert len(report.chapters) == 2
        assert report.chapters[0].valid_quotes == 2
        assert report.chapters[1].valid_quotes == 1

    def test_report_is_deterministic(self):
        """Same input always produces same report."""
        whitelist = [_make_guest_quote("Quote", chapter_indices=[0])]

        report1 = generate_coverage_report(whitelist, 1, "hash1")
        report2 = generate_coverage_report(whitelist, 1, "hash1")

        assert report1.model_dump() == report2.model_dump()

    def test_marks_infeasible_when_insufficient_quotes(self):
        """Report is infeasible when chapters lack minimum quotes."""
        whitelist = []  # No quotes

        report = generate_coverage_report(whitelist, 4, "hash")

        assert report.is_feasible is False
        assert any("insufficient" in note.lower() for note in report.feasibility_notes)
```

**Step 2: Implement generate_coverage_report**

```python
# Add to backend/src/services/whitelist_service.py

from src.models.edition import CoverageReport, ChapterCoverageReport

# Coverage constants
MIN_QUOTES_PER_CHAPTER = 2
WORDS_PER_QUOTE_MULTIPLIER = 2.5  # Each quote word supports ~2.5 prose words
BASE_CHAPTER_WORDS = 150  # Minimum overhead per chapter


def generate_coverage_report(
    whitelist: list[WhitelistQuote],
    chapter_count: int,
    transcript_hash: str,
) -> CoverageReport:
    """Generate pre-generation coverage report.

    Args:
        whitelist: Validated quote whitelist.
        chapter_count: Number of chapters planned.
        transcript_hash: Hash of canonical transcript.

    Returns:
        CoverageReport with feasibility analysis.
    """
    chapters = []
    feasibility_notes = []
    total_quote_words = 0

    for chapter_idx in range(chapter_count):
        # Count quotes for this chapter
        chapter_quotes = [
            q for q in whitelist
            if chapter_idx in q.chapter_indices
        ]
        guest_quotes = [
            q for q in chapter_quotes
            if q.speaker.speaker_role == SpeakerRole.GUEST
        ]

        valid_count = len(guest_quotes)
        invalid_count = len(chapter_quotes) - valid_count

        # Estimate word range
        quote_words = sum(len(q.quote_text.split()) for q in guest_quotes)
        total_quote_words += quote_words

        min_words = BASE_CHAPTER_WORDS + quote_words
        max_words = BASE_CHAPTER_WORDS + int(quote_words * WORDS_PER_QUOTE_MULTIPLIER)

        chapters.append(ChapterCoverageReport(
            chapter_index=chapter_idx,
            valid_quotes=valid_count,
            invalid_quotes=invalid_count,
            valid_claims=0,  # TODO: count from evidence map
            invalid_claims=0,
            predicted_word_range=(min_words, max_words),
        ))

        if valid_count < MIN_QUOTES_PER_CHAPTER:
            feasibility_notes.append(
                f"Chapter {chapter_idx + 1} has only {valid_count} GUEST quotes "
                f"(minimum {MIN_QUOTES_PER_CHAPTER})"
            )

    # Calculate totals
    min_total = sum(ch.predicted_word_range[0] for ch in chapters)
    max_total = sum(ch.predicted_word_range[1] for ch in chapters)

    is_feasible = len(feasibility_notes) == 0 and len(whitelist) >= MIN_QUOTES_PER_CHAPTER

    if not whitelist:
        feasibility_notes.append("No valid whitelist quotes found")
        is_feasible = False

    return CoverageReport(
        transcript_hash=transcript_hash,
        total_whitelist_quotes=len(whitelist),
        chapters=chapters,
        predicted_total_range=(min_total, max_total),
        is_feasible=is_feasible,
        feasibility_notes=feasibility_notes,
    )
```

**Step 3-5: Run tests, verify pass, commit**

```bash
pytest tests/unit/test_coverage_generator.py -v
git add backend/src/services/whitelist_service.py backend/tests/unit/test_coverage_generator.py
git commit -m "feat: add coverage report generator for pre-generation analysis"
```

---

## Phase 2: Deterministic Compilation

### Task 4: Move Key Excerpts to post-enforcement compilation

**Files:**
- Modify: `backend/src/services/draft_service.py`
- Create: `backend/tests/unit/test_excerpt_compilation.py`

**Goal:** Key Excerpts are compiled from whitelist AFTER enforcement, not generated by LLM.

**Step 1: Write failing test**

```python
"""Tests for deterministic excerpt compilation."""
import pytest


class TestExcerptCompilation:
    def test_compiles_excerpts_from_whitelist_not_llm(self):
        """Key Excerpts come from whitelist, ignoring LLM output."""
        from src.services.draft_service import compile_key_excerpts_section

        whitelist = [
            _make_guest_quote("Wisdom is limitless in scope", chapter_indices=[0]),
            _make_guest_quote("Knowledge grows without bound", chapter_indices=[0]),
        ]

        # Even if LLM output has garbage, we compile from whitelist
        llm_garbage = '''### Key Excerpts

> "Fabricated quote not in transcript"
> — Unknown
'''

        result = compile_key_excerpts_section(
            chapter_index=0,
            whitelist=whitelist,
            coverage_level=CoverageLevel.MEDIUM,
        )

        assert "Wisdom is limitless" in result
        assert "Knowledge grows" in result
        assert "Fabricated" not in result
        assert "(GUEST)" in result  # Typed attribution

    def test_uses_fallback_when_chapter_has_no_quotes(self):
        """Fallback chain provides excerpts when chapter pool empty."""
        from src.services.draft_service import compile_key_excerpts_section

        # Quotes only for chapter 1, not chapter 0
        whitelist = [
            _make_guest_quote("Quote for chapter one", chapter_indices=[1]),
        ]

        result = compile_key_excerpts_section(
            chapter_index=0,  # No quotes for this chapter
            whitelist=whitelist,
            coverage_level=CoverageLevel.WEAK,
        )

        # Should use global fallback
        assert "Quote for chapter one" in result
        assert result != ""  # Never empty
```

**Step 2: Implement compile_key_excerpts_section**

This function replaces LLM-generated Key Excerpts with deterministic compilation.

```python
# Add to backend/src/services/draft_service.py

def compile_key_excerpts_section(
    chapter_index: int,
    whitelist: list[WhitelistQuote],
    coverage_level: CoverageLevel,
) -> str:
    """Compile Key Excerpts section deterministically from whitelist.

    This replaces LLM-generated excerpts with whitelist-backed content.
    Uses fallback chain to ensure non-empty result.

    Args:
        chapter_index: 0-based chapter index.
        whitelist: Validated quote whitelist.
        coverage_level: Coverage level for excerpt count.

    Returns:
        Markdown string for Key Excerpts section (without header).
    """
    excerpts = select_deterministic_excerpts(whitelist, chapter_index, coverage_level)

    if not excerpts:
        # This should only happen if whitelist is completely empty
        return "*No excerpts available.*"

    return format_excerpts_markdown(excerpts)
```

**Step 3-5: Run tests, verify pass, commit**

---

### Task 5: Implement "Claims-first excerpts" fallback

**Files:**
- Modify: `backend/src/services/whitelist_service.py`

**Goal:** If chapter has valid Core Claims but no excerpts, use claim support quotes as excerpts.

**Step 1: Write failing test**

```python
def test_claims_first_fallback(self):
    """Use Core Claim support quotes as excerpts when pool empty."""
    from src.services.whitelist_service import select_deterministic_excerpts_with_claims

    # Whitelist quote only in claims context, not general pool
    whitelist = [
        _make_guest_quote(
            "This quote supports a claim",
            chapter_indices=[0],
            source_evidence_ids=["claim_1"],  # Tied to a claim
        ),
    ]

    claims = [
        {"id": "claim_1", "quote": "This quote supports a claim"},
    ]

    excerpts = select_deterministic_excerpts_with_claims(
        whitelist, chapter_index=0, coverage_level=CoverageLevel.WEAK, claims=claims
    )

    assert len(excerpts) >= 1
    assert "supports a claim" in excerpts[0].quote_text
```

---

### Task 6: Implement render guard (no empty headings)

**Files:**
- Modify: `backend/src/services/draft_service.py`

**Goal:** Section headers only rendered if content exists.

---

## Phase 3: Fallback Chain & Merging

### Task 7: Implement span-first chapter evidence scoping

**Files:**
- Modify: `backend/src/services/whitelist_service.py`

**Goal:** Chapters map to transcript intervals; evidence assigned by position, not just similarity.

---

### Task 8: Replace hard speaker filters with quotas

**Files:**
- Modify: `backend/src/services/whitelist_service.py`

**Goal:** Prefer GUEST but allow HOST if needed to meet excerpt minimum.

---

### Task 9: Implement quote re-anchoring (self-heal lite)

**Files:**
- Create: `backend/src/services/quote_anchoring.py`

**Goal:** Given proposed quote, find best match in raw transcript and extract exact substring.

---

### Task 10: Implement chapter merge logic

**Files:**
- Modify: `backend/src/services/draft_service.py`

**Goal:** When chapter evidence minimum fails, merge with neighbor instead of shipping empty.

---

## Phase 4: Word Budget & Coverage

### Task 11: Add word-budget allocator

**Files:**
- Create: `backend/src/services/word_budget.py`

**Goal:** Coverage-based budgeting instead of "force prose to 5k then delete".

---

### Task 12: Enforce "no inline quotes" at enforcer stage

**Files:**
- Modify: `backend/src/services/whitelist_service.py`

**Goal:** Inline quotes are removed and logged; never appear in final prose.

---

## Phase 5: Integration & Testing

### Task 13: Add end-to-end golden tests

**Files:**
- Create: `backend/tests/integration/test_ideas_edition_golden.py`

**Goal:** Test with evidence-rich, evidence-thin, and multi-speaker transcripts.

---

### Task 14: Wire Ideas Edition into draft generation

**Files:**
- Modify: `backend/src/services/draft_service.py`
- Modify: `backend/src/models/api_responses.py`

**Goal:** Selecting Ideas Edition in UI/backend runs the Ideas pipeline; themes no longer ignored.

---

### Task 15: Add preflight coverage endpoint

**Files:**
- Create: `backend/src/api/routes/coverage.py`

**Goal:** Surface predicted word count and feasibility before generation starts.

---

## Summary of Invariants

| Invariant | Enforcement Point |
|-----------|-------------------|
| Key Excerpts never empty | `compile_key_excerpts_section()` + fallback chain |
| Core Claims never empty | `enforce_core_claims_text()` + placeholder |
| No inline quotes in prose | `strip_prose_quote_chars()` + invariant validator |
| Preflight coverage report | `generate_coverage_report()` before generation |
| Chapters meet minimum evidence | Merge logic or abort |

---

## Execution

Tasks 1-6 are highest priority (eliminate empty sections).
Tasks 7-12 improve coverage and prevent the "generate → delete" oscillation.
Tasks 13-15 complete the Ideas Edition integration.
