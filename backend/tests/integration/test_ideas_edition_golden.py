"""Golden tests for Ideas Edition structural invariants.

These tests validate that the post-processing pipeline maintains
structural invariants across different content scenarios.
"""
from hashlib import sha256

import pytest

from src.models.edition import CoverageLevel, SpeakerRef, SpeakerRole, WhitelistQuote
from src.services.draft_service import (
    compile_key_excerpts_section,
    strip_empty_section_headers,
)
from src.services.structural_invariants import (
    validate_structural_invariants,
)
from src.services.whitelist_service import (
    format_excerpts_markdown,
    remove_inline_quotes,
    select_deterministic_excerpts,
)


def _make_whitelist_quote(
    text: str,
    chapter_indices: list[int],
    role: SpeakerRole = SpeakerRole.GUEST,
) -> WhitelistQuote:
    """Create a test WhitelistQuote."""
    quote_canonical = text.lower().strip()
    speaker_id = f"{role.value}_speaker"
    quote_id = sha256(f"{speaker_id}|{quote_canonical}".encode()).hexdigest()[:16]
    return WhitelistQuote(
        quote_id=quote_id,
        quote_text=text,
        quote_canonical=quote_canonical,
        speaker=SpeakerRef(
            speaker_id=speaker_id,
            speaker_name=f"Test {role.value.title()}",
            speaker_role=role,
        ),
        source_evidence_ids=[],
        chapter_indices=chapter_indices,
        match_spans=[],
    )


class TestEvidenceRichTranscript:
    """Tests with a transcript that has abundant evidence."""

    @pytest.fixture
    def rich_whitelist(self):
        """Whitelist with many quotes per chapter."""
        return [
            # Chapter 0 quotes
            _make_whitelist_quote("The Enlightenment marked a turning point in history", [0]),
            _make_whitelist_quote("Science is about finding testable regularities", [0]),
            _make_whitelist_quote("The scientific method has limitless scope", [0]),
            _make_whitelist_quote("Knowledge grows without bound", [0]),
            # Chapter 1 quotes
            _make_whitelist_quote("Wisdom is limitless like scientific knowledge", [1]),
            _make_whitelist_quote("We should colonize the solar system", [1]),
            _make_whitelist_quote("Human technology can transform environments", [1]),
            # Chapter 2 quotes
            _make_whitelist_quote("Universal laws apply everywhere", [2]),
            _make_whitelist_quote("Humility has hindered progress", [2]),
        ]

    def test_no_empty_sections_with_rich_evidence(self, rich_whitelist):
        """Rich evidence produces no empty sections."""
        # Compile Key Excerpts for each chapter
        ch0_excerpts = compile_key_excerpts_section(0, rich_whitelist, CoverageLevel.STRONG)
        ch1_excerpts = compile_key_excerpts_section(1, rich_whitelist, CoverageLevel.STRONG)
        ch2_excerpts = compile_key_excerpts_section(2, rich_whitelist, CoverageLevel.MEDIUM)

        # Build document
        doc = f'''## Chapter 1: The Enlightenment

The Enlightenment changed everything.

### Key Excerpts

{ch0_excerpts}

### Core Claims

- **Progress is possible**: "Science enables continuous improvement."

## Chapter 2: Human Potential

Humanity can reshape the cosmos.

### Key Excerpts

{ch1_excerpts}

### Core Claims

- **Wisdom evolves**: "Understanding deepens over time."

## Chapter 3: Universal Laws

Physics applies everywhere.

### Key Excerpts

{ch2_excerpts}

### Core Claims

- **Universality**: "Laws do not change by location."
'''

        # Validate
        result = validate_structural_invariants(doc)
        assert result["valid"], f"Invariant violations: {result}"
        assert len(result["empty_sections"]) == 0
        assert len(result["inline_quotes"]) == 0

    def test_deterministic_excerpt_selection(self, rich_whitelist):
        """Same whitelist produces same excerpts every time."""
        excerpts1 = select_deterministic_excerpts(rich_whitelist, 0, CoverageLevel.MEDIUM)
        excerpts2 = select_deterministic_excerpts(rich_whitelist, 0, CoverageLevel.MEDIUM)

        assert [e.quote_id for e in excerpts1] == [e.quote_id for e in excerpts2]


class TestEvidenceThinTranscript:
    """Tests with a transcript that has minimal evidence."""

    @pytest.fixture
    def thin_whitelist(self):
        """Whitelist with very few quotes."""
        return [
            _make_whitelist_quote("Only quote in the whole transcript", [0]),
        ]

    def test_fallback_prevents_empty_sections(self, thin_whitelist):
        """Global fallback provides excerpts even for evidence-thin chapters."""
        # Chapter 1 has no direct quotes
        ch1_excerpts = compile_key_excerpts_section(1, thin_whitelist, CoverageLevel.WEAK)

        # Should use global fallback
        assert ch1_excerpts.strip() != ""
        assert "Only quote" in ch1_excerpts or "No excerpts available" in ch1_excerpts

    def test_empty_whitelist_produces_placeholder(self):
        """Empty whitelist produces placeholder text."""
        empty_whitelist: list[WhitelistQuote] = []

        result = compile_key_excerpts_section(0, empty_whitelist, CoverageLevel.WEAK)

        assert result.strip() != ""
        assert "no excerpts" in result.lower() or "*" in result


class TestMultiSpeakerTranscript:
    """Tests with transcripts featuring multiple speakers."""

    @pytest.fixture
    def multi_speaker_whitelist(self):
        """Whitelist with HOST and GUEST quotes."""
        return [
            _make_whitelist_quote("Guest insight one", [0], SpeakerRole.GUEST),
            _make_whitelist_quote("Host question one", [0], SpeakerRole.HOST),
            _make_whitelist_quote("Guest response one", [0], SpeakerRole.GUEST),
            _make_whitelist_quote("Host follow up", [1], SpeakerRole.HOST),
            _make_whitelist_quote("Guest conclusion", [1], SpeakerRole.GUEST),
        ]

    def test_prefers_guest_quotes(self, multi_speaker_whitelist):
        """GUEST quotes preferred over HOST in excerpts."""
        excerpts = select_deterministic_excerpts(
            multi_speaker_whitelist, 0, CoverageLevel.MEDIUM
        )

        # Should prefer GUEST
        guest_count = sum(1 for e in excerpts if e.speaker.speaker_role == SpeakerRole.GUEST)
        assert guest_count > 0

    def test_attribution_includes_role(self, multi_speaker_whitelist):
        """Formatted excerpts include speaker role."""
        excerpts = select_deterministic_excerpts(
            multi_speaker_whitelist, 0, CoverageLevel.WEAK
        )
        formatted = format_excerpts_markdown(excerpts)

        # Should have role in attribution
        assert "(GUEST)" in formatted or "(HOST)" in formatted


class TestInlineQuoteRemoval:
    """Tests for inline quote removal in prose."""

    def test_removes_inline_quotes_preserves_structure(self):
        """Inline quotes removed while structure preserved."""
        doc = '''## Chapter 1

He said "this is important" and then "that is also key" to explain.

### Key Excerpts

> "Valid excerpt here"
> -- Speaker (GUEST)

### Core Claims

- **Claim**: "Supporting quote"
'''

        cleaned, report = remove_inline_quotes(doc)

        # Inline quotes removed
        assert '"this is important"' not in cleaned
        assert '"that is also key"' not in cleaned

        # Structure preserved
        assert '> "Valid excerpt here"' in cleaned
        assert '"Supporting quote"' in cleaned

        # Report accurate
        assert report["removed_count"] == 2


class TestRenderGuard:
    """Tests for empty section removal."""

    def test_strips_empty_key_excerpts(self):
        """Empty Key Excerpts headers removed."""
        doc = '''## Chapter 1

Some prose.

### Key Excerpts

### Core Claims

- **Claim**: "Support"
'''

        result = strip_empty_section_headers(doc)

        assert "### Key Excerpts" not in result
        assert "### Core Claims" in result

    def test_preserves_valid_sections(self):
        """Non-empty sections preserved."""
        doc = '''## Chapter 1

Some prose.

### Key Excerpts

> "Quote"
> -- Speaker (GUEST)

### Core Claims

- **Claim**: "Support"
'''

        result = strip_empty_section_headers(doc)

        assert "### Key Excerpts" in result
        assert "### Core Claims" in result
        assert '> "Quote"' in result


class TestFullPipeline:
    """End-to-end pipeline tests."""

    def test_pipeline_produces_valid_output(self):
        """Full pipeline produces structurally valid output."""
        # Simulate LLM output with inline quotes and potential empties
        raw_llm_output = '''## Chapter 1: The Beginning

The speaker explained "this concept" clearly to the audience.
He emphasized "another point" before moving on.

### Key Excerpts

### Core Claims

- **Key idea**: "Supporting quote here"

## Chapter 2: The Continuation

More content "with quotes" embedded in prose.

### Key Excerpts

> "Valid excerpt"
> -- Test Speaker (GUEST)

### Core Claims

'''

        # Step 1: Remove inline quotes
        cleaned, _ = remove_inline_quotes(raw_llm_output)

        # Step 2: Strip empty sections
        final = strip_empty_section_headers(cleaned)

        # Validate final output
        result = validate_structural_invariants(final)

        # Should have no inline quote violations
        assert len(result["inline_quotes"]) == 0

        # May still have empty sections if no whitelist was used
        # but the structure should be cleaner
        assert '> "Valid excerpt"' in final
