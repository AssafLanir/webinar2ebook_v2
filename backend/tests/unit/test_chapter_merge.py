"""Tests for chapter merge logic."""
from dataclasses import dataclass


@dataclass
class ChapterMetrics:
    """Simplified metrics for testing."""
    chapter_index: int
    valid_quotes: int


class TestSuggestChapterMerges:
    def test_no_merge_when_all_chapters_sufficient(self):
        """No merges suggested when all chapters meet minimum."""
        from src.services.draft_service import suggest_chapter_merges

        chapters = [
            ChapterMetrics(0, valid_quotes=3),
            ChapterMetrics(1, valid_quotes=4),
            ChapterMetrics(2, valid_quotes=3),
        ]

        merges = suggest_chapter_merges(chapters, min_quotes=2)

        assert len(merges) == 0

    def test_merge_weak_chapter_with_neighbor(self):
        """Weak chapter merged with adjacent chapter."""
        from src.services.draft_service import suggest_chapter_merges

        chapters = [
            ChapterMetrics(0, valid_quotes=3),
            ChapterMetrics(1, valid_quotes=0),  # Below minimum
            ChapterMetrics(2, valid_quotes=4),
        ]

        merges = suggest_chapter_merges(chapters, min_quotes=2)

        assert len(merges) == 1
        # Chapter 1 should merge with neighbor (0 or 2)
        assert merges[0]["weak_chapter"] == 1
        assert merges[0]["merge_into"] in [0, 2]

    def test_prefers_stronger_neighbor(self):
        """Weak chapter merges into the stronger neighbor."""
        from src.services.draft_service import suggest_chapter_merges

        chapters = [
            ChapterMetrics(0, valid_quotes=2),  # Weaker
            ChapterMetrics(1, valid_quotes=1),  # Below minimum
            ChapterMetrics(2, valid_quotes=5),  # Stronger
        ]

        merges = suggest_chapter_merges(chapters, min_quotes=2)

        assert len(merges) == 1
        assert merges[0]["weak_chapter"] == 1
        assert merges[0]["merge_into"] == 2  # Stronger neighbor

    def test_first_chapter_merges_forward(self):
        """First chapter with no quotes merges into second."""
        from src.services.draft_service import suggest_chapter_merges

        chapters = [
            ChapterMetrics(0, valid_quotes=0),  # Below minimum, first
            ChapterMetrics(1, valid_quotes=3),
            ChapterMetrics(2, valid_quotes=4),
        ]

        merges = suggest_chapter_merges(chapters, min_quotes=2)

        assert len(merges) == 1
        assert merges[0]["weak_chapter"] == 0
        assert merges[0]["merge_into"] == 1  # Only option

    def test_last_chapter_merges_backward(self):
        """Last chapter with no quotes merges into previous."""
        from src.services.draft_service import suggest_chapter_merges

        chapters = [
            ChapterMetrics(0, valid_quotes=3),
            ChapterMetrics(1, valid_quotes=4),
            ChapterMetrics(2, valid_quotes=0),  # Below minimum, last
        ]

        merges = suggest_chapter_merges(chapters, min_quotes=2)

        assert len(merges) == 1
        assert merges[0]["weak_chapter"] == 2
        assert merges[0]["merge_into"] == 1  # Only option

    def test_multiple_weak_chapters(self):
        """Multiple weak chapters each get merge suggestions."""
        from src.services.draft_service import suggest_chapter_merges

        chapters = [
            ChapterMetrics(0, valid_quotes=0),  # Below
            ChapterMetrics(1, valid_quotes=4),  # Strong
            ChapterMetrics(2, valid_quotes=1),  # Below
            ChapterMetrics(3, valid_quotes=5),  # Strong
        ]

        merges = suggest_chapter_merges(chapters, min_quotes=2)

        assert len(merges) == 2
        weak_chapters = {m["weak_chapter"] for m in merges}
        assert weak_chapters == {0, 2}

    def test_adjacent_weak_chapters(self):
        """Adjacent weak chapters handled correctly."""
        from src.services.draft_service import suggest_chapter_merges

        chapters = [
            ChapterMetrics(0, valid_quotes=5),
            ChapterMetrics(1, valid_quotes=0),  # Weak
            ChapterMetrics(2, valid_quotes=0),  # Weak
            ChapterMetrics(3, valid_quotes=5),
        ]

        merges = suggest_chapter_merges(chapters, min_quotes=2)

        # Both weak chapters should get merge suggestions
        assert len(merges) >= 2

    def test_single_chapter_no_merge(self):
        """Single chapter document has no merge options."""
        from src.services.draft_service import suggest_chapter_merges

        chapters = [
            ChapterMetrics(0, valid_quotes=0),
        ]

        merges = suggest_chapter_merges(chapters, min_quotes=2)

        # Can't merge a single chapter
        assert len(merges) == 0 or merges[0].get("action") == "abort"
