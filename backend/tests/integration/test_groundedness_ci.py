"""CI integration tests for groundedness harness.

Uses tiny deterministic synthetic fixtures (no copyrighted transcripts).
Runs as part of CI to catch regressions in groundedness checking.
"""

import pytest

from src.services.groundedness_service import (
    check_groundedness,
    check_and_repair_groundedness,
    is_groundedness_enabled,
)


# =============================================================================
# Deterministic Synthetic Fixtures
# =============================================================================

SYNTHETIC_TRANSCRIPT = """
Welcome everyone to today's session on voice technology.

Voice Hub is a tool we created to allow companies and developers to quickly
create projects and proof of concepts. We support multiple languages and add
more every day.

The technology can classify up to four hundred different sounds in real-time.
This enables new applications in security, healthcare, and smart home devices.

Thank you for joining us today.
"""

GROUNDED_DRAFT = """## Chapter 1: Voice Technology Overview

Voice technology enables new applications across industries.

### Key Excerpts

> "Voice Hub is a tool we created to allow companies and developers to quickly create projects and proof of concepts."
> — Speaker

> "We support multiple languages and add more every day."
> — Speaker

### Core Claims

- **Multi-language support**: "We support multiple languages and add more every day."
- **Sound classification capability**: "classify up to four hundred different sounds"
"""

UNGROUNDED_DRAFT_EXCERPT = """## Chapter 1: Voice Technology Overview

### Key Excerpts

> "This quote was completely invented and does not exist in the transcript."
> — Speaker

### Core Claims

- **Real claim**: "Voice Hub is a tool we created"
"""

UNGROUNDED_DRAFT_CLAIM = """## Chapter 1: Voice Technology Overview

### Key Excerpts

> "Voice Hub is a tool we created to allow companies and developers."
> — Speaker

### Core Claims

- **Invented claim**: "The AI can translate 500 languages in real-time."
"""


# =============================================================================
# CI Tests
# =============================================================================


class TestGroundednessCI:
    """CI integration tests for groundedness validation."""

    def test_feature_flag_exists(self):
        """Verify feature flag function is available."""
        # Just check it's callable and returns bool
        result = is_groundedness_enabled()
        assert isinstance(result, bool)

    def test_grounded_draft_passes(self):
        """Fully grounded draft should PASS."""
        report = check_groundedness(
            GROUNDED_DRAFT,
            SYNTHETIC_TRANSCRIPT,
            strict=True,
        )

        assert report.overall_verdict == "PASS"
        assert report.excerpt_provenance.verdict == "PASS"
        assert report.claim_support.verdict == "PASS"

    def test_ungrounded_excerpt_fails(self):
        """Draft with invented excerpt should FAIL."""
        report = check_groundedness(
            UNGROUNDED_DRAFT_EXCERPT,
            SYNTHETIC_TRANSCRIPT,
            strict=True,
        )

        assert report.overall_verdict == "FAIL"
        assert report.excerpt_provenance.verdict == "FAIL"
        assert report.excerpt_provenance.excerpts_not_found >= 1

    def test_ungrounded_claim_repaired_or_dropped(self):
        """Draft with invented claim evidence should be repaired/dropped."""
        report, repair_result, repaired_md = check_and_repair_groundedness(
            UNGROUNDED_DRAFT_CLAIM,
            SYNTHETIC_TRANSCRIPT,
        )

        # Excerpt should pass (it's real)
        assert report.excerpt_provenance.verdict == "PASS"

        # Invented claim evidence should be dropped
        assert repair_result.claims_dropped >= 1

    def test_repair_preserves_grounded_claims(self):
        """Repair should preserve claims with valid evidence."""
        draft_with_mixed = """### Core Claims

- **Real claim**: "Voice Hub is a tool we created"
- **Invented claim**: "This was never said in the transcript"
"""
        report, repair_result, repaired_md = check_and_repair_groundedness(
            draft_with_mixed,
            SYNTHETIC_TRANSCRIPT,
        )

        # One claim should be unchanged/repaired, one dropped
        assert repair_result.claims_unchanged + repair_result.claims_repaired >= 1
        assert repair_result.claims_dropped >= 1

    def test_deterministic_results(self):
        """Same input should produce same output (deterministic)."""
        report1 = check_groundedness(GROUNDED_DRAFT, SYNTHETIC_TRANSCRIPT)
        report2 = check_groundedness(GROUNDED_DRAFT, SYNTHETIC_TRANSCRIPT)

        assert report1.overall_verdict == report2.overall_verdict
        assert report1.excerpt_provenance.provenance_rate == report2.excerpt_provenance.provenance_rate
        assert report1.claim_support.evidence_provenance_rate == report2.claim_support.evidence_provenance_rate
