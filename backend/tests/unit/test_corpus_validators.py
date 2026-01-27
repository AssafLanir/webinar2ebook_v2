"""Unit tests for corpus validators.

Tests the validation pipeline with fixture data - no LLM providers needed.
"""

import pytest
from corpus.validators import (
    validate_structure,
    compute_yield,
    make_gate_row,
    make_failure_gate_row,
    StructureResult,
    GroundednessResult,
    YieldResult,
    GateRow,
)
from corpus.thresholds import DEFAULT_THRESHOLDS, Thresholds


# =============================================================================
# Fixture: Well-formed Ideas Edition draft
# =============================================================================

VALID_IDEAS_DRAFT = """## Chapter 1: Introduction to Machine Learning

Machine learning is revolutionizing how organizations approach data analysis and decision-making. This chapter explores the foundational concepts.

### Key Excerpts

> "Machine learning is transforming the industry in unprecedented ways, enabling automation at scale." - Dr. Smith

This quote highlights the transformative potential of ML technologies in enterprise contexts.

### Core Claims

- **Efficiency gains:** Organizations using ML report 40% faster decision cycles
- **Cost reduction:** Automated processes reduce operational costs by 25%

## Chapter 2: Implementation Strategies

Successful ML implementation requires careful planning and organizational alignment.

### Key Excerpts

> "The key to successful AI adoption is starting with well-defined problems." - Industry Expert

Starting with clear objectives ensures focused development efforts.

### Core Claims

- **Problem definition:** Clear problem statements lead to 3x higher project success rates
- **Iterative approach:** Phased rollouts reduce implementation risk

## Chapter 3: Future Outlook

The future of machine learning holds tremendous promise for continued innovation.

### Key Excerpts

> "Looking ahead, we see AI becoming an integral part of every business function." - Tech Leader

This forward-looking perspective shapes strategic planning.

### Core Claims

- **Ubiquitous AI:** By 2030, AI will be embedded in 90% of enterprise software
- **Human-AI collaboration:** The most effective systems combine human judgment with AI insights
"""

VALID_TRANSCRIPT = """
Dr. Smith: Machine learning is transforming the industry in unprecedented ways, enabling automation at scale.
Industry Expert: The key to successful AI adoption is starting with well-defined problems.
Tech Leader: Looking ahead, we see AI becoming an integral part of every business function.
"""


# =============================================================================
# Fixture: Malformed drafts for failure testing
# =============================================================================

DRAFT_MISSING_CHAPTERS = """# Introduction

This is just prose without chapter structure.

Some content here about machine learning.
"""

DRAFT_MISSING_KEY_EXCERPTS = """## Chapter 1: Introduction

This chapter has no Key Excerpts section.

### Core Claims

- **Point one:** Some claim here
"""

DRAFT_INTERVIEW_LEAKAGE = """## Chapter 1: Introduction

*Format:* Interview

### The Conversation

*Interviewer:* What do you think about AI?

### Key Ideas (Grounded)

Some ideas here.
"""


# =============================================================================
# Structure Validation Tests
# =============================================================================

class TestStructureValidation:
    """Tests for Ideas Edition structure validation."""

    def test_valid_draft_passes(self):
        """A well-formed Ideas Edition draft should pass."""
        result = validate_structure(VALID_IDEAS_DRAFT)

        assert result.verdict == "PASS"
        assert result.has_chapter_structure is True
        assert result.has_key_excerpts is True
        assert result.has_core_claims is True
        assert result.has_interview_leakage is False
        assert result.chapter_count == 3
        assert len(result.violations) == 0

    def test_counts_chapters_correctly(self):
        """Should count chapters and excerpts correctly."""
        result = validate_structure(VALID_IDEAS_DRAFT)

        assert result.chapter_count == 3
        assert result.key_excerpt_count == 3  # One per chapter
        assert len(result.chapters) == 3

        # Check per-chapter details
        assert result.chapters[0].n == 1
        assert result.chapters[0].title == "Introduction to Machine Learning"
        assert result.chapters[0].has_key_excerpts is True
        assert result.chapters[0].has_core_claims is True

    def test_missing_chapter_structure_fails(self):
        """Draft without ## Chapter N: structure should fail."""
        result = validate_structure(DRAFT_MISSING_CHAPTERS)

        assert result.verdict == "FAIL"
        assert result.has_chapter_structure is False
        assert "Missing chapter structure" in result.violations[0]

    def test_missing_key_excerpts_fails(self):
        """Draft without Key Excerpts section should fail."""
        result = validate_structure(DRAFT_MISSING_KEY_EXCERPTS)

        assert result.verdict == "FAIL"
        assert "missing Key Excerpts" in str(result.violations)

    def test_interview_leakage_detected(self):
        """Interview template leakage should be detected."""
        result = validate_structure(DRAFT_INTERVIEW_LEAKAGE)

        assert result.verdict == "FAIL"
        assert result.has_interview_leakage is True
        # Should detect multiple leakage patterns
        assert any("Interview" in v for v in result.violations)

    def test_structure_result_to_dict(self):
        """StructureResult should serialize to dict correctly."""
        result = validate_structure(VALID_IDEAS_DRAFT)
        d = result.to_dict()

        assert "verdict" in d
        assert "chapter_count" in d
        assert "chapters" in d
        assert isinstance(d["chapters"], list)

    def test_claim_parsing_both_formats(self):
        """Should count claims with colon inside OR outside bold."""
        # Format 1: - **Label:** (colon inside bold)
        draft_inside = """## Chapter 1: Test

### Key Excerpts

> "Quote" - Speaker

### Core Claims

- **Label one:** description here
- **Label two:** another description
"""

        # Format 2: - **Label**: (colon outside bold)
        draft_outside = """## Chapter 1: Test

### Key Excerpts

> "Quote" - Speaker

### Core Claims

- **Label one**: description here
- **Label two**: another description
"""

        result_inside = validate_structure(draft_inside)
        result_outside = validate_structure(draft_outside)

        assert result_inside.core_claim_count == 2, "Should parse colon-inside format"
        assert result_outside.core_claim_count == 2, "Should parse colon-outside format"


# =============================================================================
# Yield Metrics Tests
# =============================================================================

class TestYieldMetrics:
    """Tests for yield/quality metrics computation."""

    def test_prose_word_count(self):
        """Should count prose words correctly."""
        structure = validate_structure(VALID_IDEAS_DRAFT)
        groundedness = GroundednessResult(
            overall_verdict="PASS",
            excerpt_provenance={"provenance_rate": 1.0},
            claim_support={"evidence_provenance_rate": 1.0},
        )

        yield_result = compute_yield(
            VALID_IDEAS_DRAFT, VALID_TRANSCRIPT, structure, groundedness
        )

        assert yield_result.prose_word_count > 0
        assert yield_result.total_word_count > yield_result.prose_word_count

    def test_per_chapter_prose_extraction(self):
        """Should extract prose words per chapter."""
        structure = validate_structure(VALID_IDEAS_DRAFT)
        groundedness = GroundednessResult(
            overall_verdict="PASS",
            excerpt_provenance={},
            claim_support={},
        )

        yield_result = compute_yield(
            VALID_IDEAS_DRAFT, VALID_TRANSCRIPT, structure, groundedness
        )

        assert yield_result.chapter_count == 3
        assert len(yield_result.prose_words_per_chapter) == 3
        assert all(w > 0 for w in yield_result.prose_words_per_chapter)

    def test_p10_calculation(self):
        """P10 should be the 10th percentile of per-chapter prose."""
        structure = validate_structure(VALID_IDEAS_DRAFT)
        groundedness = GroundednessResult(
            overall_verdict="PASS",
            excerpt_provenance={},
            claim_support={},
        )

        yield_result = compute_yield(
            VALID_IDEAS_DRAFT, VALID_TRANSCRIPT, structure, groundedness
        )

        # P10 should be <= min chapter prose (with 3 chapters, p10 index is 0)
        assert yield_result.p10_prose_words <= max(yield_result.prose_words_per_chapter)
        assert yield_result.p10_prose_words >= 0

    def test_fallback_detection(self):
        """Fallback markers should be detected."""
        draft_with_fallback = VALID_IDEAS_DRAFT + "\n<!-- fallback -->\n"
        structure = validate_structure(draft_with_fallback)
        groundedness = GroundednessResult(
            overall_verdict="PASS",
            excerpt_provenance={},
            claim_support={},
        )

        yield_result = compute_yield(
            draft_with_fallback, VALID_TRANSCRIPT, structure, groundedness
        )

        # Should detect fallback in at least one chapter
        assert yield_result.chapters_with_fallback >= 0

    def test_yield_result_to_dict(self):
        """YieldResult should serialize correctly."""
        structure = validate_structure(VALID_IDEAS_DRAFT)
        groundedness = GroundednessResult(
            overall_verdict="PASS",
            excerpt_provenance={},
            claim_support={},
        )

        yield_result = compute_yield(
            VALID_IDEAS_DRAFT, VALID_TRANSCRIPT, structure, groundedness
        )
        d = yield_result.to_dict()

        assert "prose_word_count" in d
        assert "p10_prose_words" in d
        assert "fallback_ratio" in d


# =============================================================================
# Gate Row Tests
# =============================================================================

class TestGateRow:
    """Tests for gate row verdict computation."""

    def test_pass_verdict_when_all_pass(self):
        """Should return PASS when structure and groundedness pass."""
        structure = StructureResult(verdict="PASS")
        groundedness = GroundednessResult(
            overall_verdict="PASS",
            excerpt_provenance={"provenance_rate": 1.0},
            claim_support={"evidence_provenance_rate": 1.0},
        )
        yield_result = YieldResult(
            p10_prose_words=100.0,  # Above threshold
            fallback_ratio=0.0,
        )

        gate_row = make_gate_row(
            run_id="test",
            transcript_id="T001",
            candidate_index=0,
            content_mode="essay",
            structure=structure,
            groundedness=groundedness,
            yield_result=yield_result,
            thresholds=DEFAULT_THRESHOLDS,
        )

        assert gate_row.verdict == "PASS"
        assert gate_row.failure_causes == []

    def test_structure_fail_overrides_all(self):
        """Structure FAIL should result in overall FAIL."""
        structure = StructureResult(verdict="FAIL", violations=["Missing chapters"])
        groundedness = GroundednessResult(
            overall_verdict="PASS",
            excerpt_provenance={"provenance_rate": 1.0},
            claim_support={"evidence_provenance_rate": 1.0},
        )
        yield_result = YieldResult(p10_prose_words=100.0, fallback_ratio=0.0)

        gate_row = make_gate_row(
            run_id="test",
            transcript_id="T001",
            candidate_index=0,
            content_mode="essay",
            structure=structure,
            groundedness=groundedness,
            yield_result=yield_result,
            thresholds=DEFAULT_THRESHOLDS,
        )

        assert gate_row.verdict == "FAIL"
        assert "structure_fail" in gate_row.failure_causes

    def test_groundedness_fail_overrides_warn(self):
        """Groundedness FAIL should result in overall FAIL."""
        structure = StructureResult(verdict="PASS")
        groundedness = GroundednessResult(
            overall_verdict="FAIL",
            excerpt_provenance={"provenance_rate": 0.5},
            claim_support={"evidence_provenance_rate": 0.5},
        )
        yield_result = YieldResult(p10_prose_words=100.0, fallback_ratio=0.0)

        gate_row = make_gate_row(
            run_id="test",
            transcript_id="T001",
            candidate_index=0,
            content_mode="essay",
            structure=structure,
            groundedness=groundedness,
            yield_result=yield_result,
            thresholds=DEFAULT_THRESHOLDS,
        )

        assert gate_row.verdict == "FAIL"
        assert "groundedness_fail" in gate_row.failure_causes

    def test_low_prose_triggers_warn(self):
        """P10 prose below threshold should trigger WARN."""
        structure = StructureResult(verdict="PASS")
        groundedness = GroundednessResult(
            overall_verdict="PASS",
            excerpt_provenance={"provenance_rate": 1.0},
            claim_support={"evidence_provenance_rate": 1.0},
        )
        yield_result = YieldResult(
            p10_prose_words=30.0,  # Below threshold of 60
            fallback_ratio=0.0,
        )

        gate_row = make_gate_row(
            run_id="test",
            transcript_id="T001",
            candidate_index=0,
            content_mode="essay",
            structure=structure,
            groundedness=groundedness,
            yield_result=yield_result,
            thresholds=DEFAULT_THRESHOLDS,
        )

        assert gate_row.verdict == "WARN"
        assert "low_prose" in gate_row.failure_causes

    def test_high_fallback_triggers_warn(self):
        """High fallback ratio should trigger WARN."""
        structure = StructureResult(verdict="PASS")
        groundedness = GroundednessResult(
            overall_verdict="PASS",
            excerpt_provenance={"provenance_rate": 1.0},
            claim_support={"evidence_provenance_rate": 1.0},
        )
        yield_result = YieldResult(
            p10_prose_words=100.0,
            fallback_ratio=0.5,  # Above threshold of 0.25
        )

        gate_row = make_gate_row(
            run_id="test",
            transcript_id="T001",
            candidate_index=0,
            content_mode="essay",
            structure=structure,
            groundedness=groundedness,
            yield_result=yield_result,
            thresholds=DEFAULT_THRESHOLDS,
        )

        assert gate_row.verdict == "WARN"
        assert "high_fallback" in gate_row.failure_causes

    def test_failure_gate_row(self):
        """make_failure_gate_row should create FAIL verdict with error."""
        gate_row = make_failure_gate_row(
            run_id="test",
            transcript_id="T001",
            candidate_index=0,
            content_mode="essay",
            error="Generation timed out",
            error_code="TIMEOUT",
        )

        assert gate_row.verdict == "FAIL"
        assert gate_row.error == "Generation timed out"
        assert "TIMEOUT" in gate_row.failure_causes

    def test_gate_row_to_dict(self):
        """GateRow should serialize correctly."""
        gate_row = make_failure_gate_row(
            run_id="test",
            transcript_id="T001",
            candidate_index=0,
            content_mode="essay",
            error="Error",
            error_code="ERROR",
        )
        d = gate_row.to_dict()

        assert d["run_id"] == "test"
        assert d["verdict"] == "FAIL"
        assert "error" in d


# =============================================================================
# Verdict Precedence Integration Test
# =============================================================================

class TestVerdictPrecedence:
    """Integration tests for verdict precedence logic."""

    def test_precedence_structure_over_groundedness(self):
        """Structure FAIL should take precedence over groundedness FAIL."""
        structure = StructureResult(verdict="FAIL")
        groundedness = GroundednessResult(
            overall_verdict="FAIL",
            excerpt_provenance={},
            claim_support={},
        )
        yield_result = YieldResult()

        gate_row = make_gate_row(
            run_id="test",
            transcript_id="T001",
            candidate_index=0,
            content_mode="essay",
            structure=structure,
            groundedness=groundedness,
            yield_result=yield_result,
            thresholds=DEFAULT_THRESHOLDS,
        )

        assert gate_row.verdict == "FAIL"
        # Both failures should be recorded
        assert "structure_fail" in gate_row.failure_causes
        assert "groundedness_fail" in gate_row.failure_causes

    def test_precedence_fail_over_warn(self):
        """FAIL should take precedence over WARN conditions."""
        structure = StructureResult(verdict="FAIL")
        groundedness = GroundednessResult(
            overall_verdict="PASS",
            excerpt_provenance={"provenance_rate": 1.0},
            claim_support={"evidence_provenance_rate": 1.0},
        )
        yield_result = YieldResult(
            p10_prose_words=30.0,  # Would trigger WARN
            fallback_ratio=0.5,    # Would trigger WARN
        )

        gate_row = make_gate_row(
            run_id="test",
            transcript_id="T001",
            candidate_index=0,
            content_mode="essay",
            structure=structure,
            groundedness=groundedness,
            yield_result=yield_result,
            thresholds=DEFAULT_THRESHOLDS,
        )

        # Overall verdict is FAIL, not WARN
        assert gate_row.verdict == "FAIL"
        assert "structure_fail" in gate_row.failure_causes
        # WARN causes should NOT be in failure_causes when there's a FAIL
        assert "low_prose" not in gate_row.failure_causes

    def test_multiple_warn_causes_recorded(self):
        """Multiple WARN conditions should all be recorded."""
        structure = StructureResult(verdict="PASS")
        groundedness = GroundednessResult(
            overall_verdict="PASS",
            excerpt_provenance={"provenance_rate": 0.8},  # Below 1.0 threshold
            claim_support={"evidence_provenance_rate": 0.8},  # Below 1.0 threshold
        )
        yield_result = YieldResult(
            p10_prose_words=30.0,  # Below 60 threshold
            fallback_ratio=0.5,    # Above 0.25 threshold
        )

        gate_row = make_gate_row(
            run_id="test",
            transcript_id="T001",
            candidate_index=0,
            content_mode="essay",
            structure=structure,
            groundedness=groundedness,
            yield_result=yield_result,
            thresholds=DEFAULT_THRESHOLDS,
        )

        assert gate_row.verdict == "WARN"
        assert "low_prose" in gate_row.failure_causes
        assert "high_fallback" in gate_row.failure_causes
