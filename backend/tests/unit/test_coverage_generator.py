"""Tests for coverage report generation."""
from src.models.edition import CoverageReport, SpeakerRef, SpeakerRole, WhitelistQuote
from src.services.whitelist_service import generate_coverage_report


def _make_guest_quote(text: str, chapter_indices: list[int]) -> WhitelistQuote:
    """Create a test WhitelistQuote from a GUEST speaker."""
    from hashlib import sha256
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


def _make_host_quote(text: str, chapter_indices: list[int]) -> WhitelistQuote:
    """Create a test WhitelistQuote from a HOST speaker."""
    from hashlib import sha256
    quote_canonical = text.lower().strip()
    quote_id = sha256(f"host|{quote_canonical}".encode()).hexdigest()[:16]
    return WhitelistQuote(
        quote_id=quote_id,
        quote_text=text,
        quote_canonical=quote_canonical,
        speaker=SpeakerRef(
            speaker_id="host_1",
            speaker_name="Test Host",
            speaker_role=SpeakerRole.HOST,
        ),
        source_evidence_ids=[],
        chapter_indices=chapter_indices,
        match_spans=[],
    )


class TestGenerateCoverageReport:
    def test_generates_report_from_whitelist(self):
        """Test report is generated from whitelist."""
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
        assert any("insufficient" in note.lower() or "no valid" in note.lower()
                   for note in report.feasibility_notes)

    def test_counts_non_guest_as_invalid(self):
        """Non-GUEST quotes counted as invalid quotes for coverage."""
        whitelist = [
            _make_guest_quote("Guest quote", chapter_indices=[0]),
            _make_host_quote("Host quote", chapter_indices=[0]),
        ]

        report = generate_coverage_report(whitelist, 1, "hash")

        # Both are valid whitelist quotes, but only GUEST contributes to chapter coverage
        assert report.total_whitelist_quotes == 2
        assert report.chapters[0].valid_quotes == 1  # Only GUEST
        assert report.chapters[0].invalid_quotes == 1  # HOST counted here

    def test_predicts_word_range(self):
        """Report includes predicted word ranges."""
        whitelist = [
            _make_guest_quote("This is a quote with ten words in it here", chapter_indices=[0]),
        ]

        report = generate_coverage_report(whitelist, 1, "hash")

        min_words, max_words = report.chapters[0].predicted_word_range
        assert min_words > 0
        assert max_words >= min_words
        assert report.predicted_total_range[0] > 0
