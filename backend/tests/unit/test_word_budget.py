"""Tests for word budget allocation."""
from dataclasses import dataclass


@dataclass
class ChapterEvidence:
    """Simplified evidence metrics for testing."""
    chapter_index: int
    quote_count: int
    quote_words: int


class TestAllocateWordBudget:
    def test_distributes_proportionally_by_evidence(self):
        """Budget distributed proportionally to evidence."""
        from src.services.word_budget import allocate_word_budget

        chapters = [
            ChapterEvidence(0, quote_count=5, quote_words=200),  # 40%
            ChapterEvidence(1, quote_count=3, quote_words=100),  # 20%
            ChapterEvidence(2, quote_count=5, quote_words=200),  # 40%
        ]

        budget = allocate_word_budget(chapters, total_target=1000)

        # Chapter 0 and 2 should get more than chapter 1
        assert budget[0] > budget[1]
        assert budget[2] > budget[1]
        # Should sum to total (approximately)
        assert sum(budget) == 1000

    def test_ensures_minimum_per_chapter(self):
        """Each chapter gets at least minimum viable words."""
        from src.services.word_budget import allocate_word_budget

        chapters = [
            ChapterEvidence(0, quote_count=10, quote_words=500),  # Lots of evidence
            ChapterEvidence(1, quote_count=1, quote_words=20),    # Very little
            ChapterEvidence(2, quote_count=10, quote_words=500),  # Lots of evidence
        ]

        budget = allocate_word_budget(chapters, total_target=1000, min_words_per_chapter=200)

        # Chapter 1 still gets minimum
        assert budget[1] >= 200

    def test_single_chapter_gets_full_budget(self):
        """Single chapter gets entire word budget."""
        from src.services.word_budget import allocate_word_budget

        chapters = [
            ChapterEvidence(0, quote_count=5, quote_words=200),
        ]

        budget = allocate_word_budget(chapters, total_target=2000)

        assert len(budget) == 1
        assert budget[0] == 2000

    def test_equal_evidence_equal_budget(self):
        """Equal evidence across chapters means equal budget."""
        from src.services.word_budget import allocate_word_budget

        chapters = [
            ChapterEvidence(0, quote_count=3, quote_words=100),
            ChapterEvidence(1, quote_count=3, quote_words=100),
            ChapterEvidence(2, quote_count=3, quote_words=100),
        ]

        budget = allocate_word_budget(chapters, total_target=900)

        assert budget[0] == budget[1] == budget[2] == 300

    def test_zero_evidence_gets_minimum(self):
        """Chapter with zero evidence gets only minimum."""
        from src.services.word_budget import allocate_word_budget

        chapters = [
            ChapterEvidence(0, quote_count=5, quote_words=200),
            ChapterEvidence(1, quote_count=0, quote_words=0),   # No evidence
            ChapterEvidence(2, quote_count=5, quote_words=200),
        ]

        budget = allocate_word_budget(chapters, total_target=1000, min_words_per_chapter=100)

        # Chapter 1 gets minimum only
        assert budget[1] == 100
        # Others split the rest
        assert budget[0] > 100
        assert budget[2] > 100

    def test_budget_uses_quote_words_as_primary_metric(self):
        """Quote word count is primary metric for allocation."""
        from src.services.word_budget import allocate_word_budget

        # Chapter 0 has more quotes but less total words
        # Chapter 1 has fewer quotes but more total words
        chapters = [
            ChapterEvidence(0, quote_count=10, quote_words=100),
            ChapterEvidence(1, quote_count=2, quote_words=400),
        ]

        budget = allocate_word_budget(chapters, total_target=1000)

        # Chapter 1 should get more budget (more quote words)
        assert budget[1] > budget[0]

    def test_returns_list_matching_chapter_order(self):
        """Budget list matches input chapter order."""
        from src.services.word_budget import allocate_word_budget

        chapters = [
            ChapterEvidence(0, quote_count=3, quote_words=100),
            ChapterEvidence(1, quote_count=6, quote_words=200),
            ChapterEvidence(2, quote_count=9, quote_words=300),
        ]

        budget = allocate_word_budget(chapters, total_target=1200)

        assert len(budget) == 3
        # Budget should increase with chapter index
        assert budget[0] < budget[1] < budget[2]

    def test_handles_empty_chapters_list(self):
        """Empty chapters list returns empty budget."""
        from src.services.word_budget import allocate_word_budget

        budget = allocate_word_budget([], total_target=1000)

        assert budget == []
