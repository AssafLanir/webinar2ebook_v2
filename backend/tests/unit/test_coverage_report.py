"""Tests for CoverageReport model."""
from src.models.edition import ChapterCoverageReport, CoverageReport


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

    def test_chapter_coverage_report_validation(self):
        """Test ChapterCoverageReport validates correctly."""
        chapter = ChapterCoverageReport(
            chapter_index=0,
            valid_quotes=3,
            invalid_quotes=1,
            valid_claims=2,
            invalid_claims=0,
            predicted_word_range=(500, 800),
        )

        assert chapter.chapter_index == 0
        assert chapter.valid_quotes == 3
        assert chapter.predicted_word_range == (500, 800)
