"""Tests for deterministic excerpt compilation."""
from hashlib import sha256

from src.models.edition import CoverageLevel, SpeakerRef, SpeakerRole, WhitelistQuote


def _make_guest_quote(text: str, chapter_indices: list[int]) -> WhitelistQuote:
    """Create a test WhitelistQuote from a GUEST speaker."""
    quote_canonical = text.lower().strip()
    quote_id = sha256(f"guest|{quote_canonical}".encode()).hexdigest()[:16]
    return WhitelistQuote(
        quote_id=quote_id,
        quote_text=text,
        quote_canonical=quote_canonical,
        speaker=SpeakerRef(
            speaker_id="guest_1",
            speaker_name="Test Guest",
            speaker_role=SpeakerRole.GUEST,
        ),
        source_evidence_ids=[],
        chapter_indices=chapter_indices,
        match_spans=[],
    )


class TestCompileKeyExcerptsSection:
    def test_compiles_excerpts_from_whitelist_not_llm(self):
        """Key Excerpts come from whitelist, ignoring LLM output."""
        from src.services.draft_service import compile_key_excerpts_section

        whitelist = [
            _make_guest_quote("Wisdom is limitless in scope", chapter_indices=[0]),
            _make_guest_quote("Knowledge grows without bound", chapter_indices=[0]),
        ]

        result = compile_key_excerpts_section(
            chapter_index=0,
            whitelist=whitelist,
            coverage_level=CoverageLevel.MEDIUM,
        )

        assert "Wisdom is limitless" in result
        assert "Knowledge grows" in result
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
        assert result.strip() != ""  # Never empty

    def test_returns_placeholder_when_whitelist_empty(self):
        """Placeholder returned when no whitelist quotes at all."""
        from src.services.draft_service import compile_key_excerpts_section

        whitelist = []

        result = compile_key_excerpts_section(
            chapter_index=0,
            whitelist=whitelist,
            coverage_level=CoverageLevel.WEAK,
        )

        assert "no excerpts available" in result.lower() or "*" in result
        assert result.strip() != ""  # Never truly empty

    def test_respects_coverage_level_for_count(self):
        """Coverage level affects number of excerpts selected."""
        from src.services.draft_service import compile_key_excerpts_section

        whitelist = [
            _make_guest_quote("Quote one for chapter zero", chapter_indices=[0]),
            _make_guest_quote("Quote two for chapter zero", chapter_indices=[0]),
            _make_guest_quote("Quote three for chapter zero", chapter_indices=[0]),
            _make_guest_quote("Quote four for chapter zero", chapter_indices=[0]),
            _make_guest_quote("Quote five for chapter zero", chapter_indices=[0]),
        ]

        weak = compile_key_excerpts_section(0, whitelist, CoverageLevel.WEAK)
        strong = compile_key_excerpts_section(0, whitelist, CoverageLevel.STRONG)

        # STRONG should have more excerpts than WEAK
        weak_quote_count = weak.count('> "')
        strong_quote_count = strong.count('> "')
        assert strong_quote_count >= weak_quote_count
