"""Tests for span-first chapter evidence scoping."""
from hashlib import sha256

from src.models.edition import SpeakerRef, SpeakerRole, WhitelistQuote


def _make_quote_with_spans(
    text: str,
    match_spans: list[tuple[int, int]],
    chapter_indices: list[int] | None = None,
) -> WhitelistQuote:
    """Create a test WhitelistQuote with specific match spans."""
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
        chapter_indices=chapter_indices or [],
        match_spans=match_spans,
    )


class TestAssignQuotesToChaptersBySpan:
    def test_assigns_quote_to_chapter_by_position(self):
        """Quote assigned to chapter containing its span."""
        from src.services.whitelist_service import assign_quotes_to_chapters_by_span

        quotes = [
            _make_quote_with_spans("Quote in chapter 1", match_spans=[(100, 150)]),
            _make_quote_with_spans("Quote in chapter 2", match_spans=[(500, 550)]),
        ]
        chapter_spans = [
            (0, 300),    # Chapter 0: positions 0-300
            (300, 600),  # Chapter 1: positions 300-600
        ]

        result = assign_quotes_to_chapters_by_span(quotes, chapter_spans)

        assert 0 in result[0].chapter_indices  # First quote in chapter 0
        assert 1 in result[1].chapter_indices  # Second quote in chapter 1

    def test_quote_spanning_multiple_chapters(self):
        """Quote spanning chapter boundary assigned to both."""
        from src.services.whitelist_service import assign_quotes_to_chapters_by_span

        quotes = [
            _make_quote_with_spans("Quote spanning chapters", match_spans=[(250, 350)]),
        ]
        chapter_spans = [
            (0, 300),    # Chapter 0
            (300, 600),  # Chapter 1
        ]

        result = assign_quotes_to_chapters_by_span(quotes, chapter_spans)

        # Quote spans both chapters
        assert 0 in result[0].chapter_indices
        assert 1 in result[0].chapter_indices

    def test_quote_with_multiple_spans(self):
        """Quote with multiple match spans assigned to all relevant chapters."""
        from src.services.whitelist_service import assign_quotes_to_chapters_by_span

        quotes = [
            _make_quote_with_spans(
                "Repeated quote",
                match_spans=[(100, 150), (500, 550), (900, 950)],
            ),
        ]
        chapter_spans = [
            (0, 300),    # Chapter 0
            (300, 600),  # Chapter 1
            (600, 1000), # Chapter 2
        ]

        result = assign_quotes_to_chapters_by_span(quotes, chapter_spans)

        # Quote appears in all 3 chapters
        assert 0 in result[0].chapter_indices
        assert 1 in result[0].chapter_indices
        assert 2 in result[0].chapter_indices

    def test_preserves_existing_chapter_indices(self):
        """Existing chapter_indices are preserved and extended."""
        from src.services.whitelist_service import assign_quotes_to_chapters_by_span

        quotes = [
            _make_quote_with_spans(
                "Quote with existing assignment",
                match_spans=[(100, 150)],
                chapter_indices=[5],  # Pre-existing assignment
            ),
        ]
        chapter_spans = [
            (0, 300),  # Chapter 0
        ]

        result = assign_quotes_to_chapters_by_span(quotes, chapter_spans)

        # Both existing (5) and new (0) assignments present
        assert 5 in result[0].chapter_indices
        assert 0 in result[0].chapter_indices

    def test_quote_outside_all_chapters(self):
        """Quote outside all chapter spans keeps original assignment."""
        from src.services.whitelist_service import assign_quotes_to_chapters_by_span

        quotes = [
            _make_quote_with_spans("Quote outside chapters", match_spans=[(1000, 1050)]),
        ]
        chapter_spans = [
            (0, 300),    # Chapter 0
            (300, 600),  # Chapter 1
        ]

        result = assign_quotes_to_chapters_by_span(quotes, chapter_spans)

        # No chapters assigned (quote is at position 1000, chapters end at 600)
        assert result[0].chapter_indices == []

    def test_empty_match_spans_unchanged(self):
        """Quotes with no match spans are unchanged."""
        from src.services.whitelist_service import assign_quotes_to_chapters_by_span

        quotes = [
            _make_quote_with_spans("Quote without spans", match_spans=[], chapter_indices=[2]),
        ]
        chapter_spans = [(0, 300)]

        result = assign_quotes_to_chapters_by_span(quotes, chapter_spans)

        # Original assignment preserved
        assert result[0].chapter_indices == [2]
