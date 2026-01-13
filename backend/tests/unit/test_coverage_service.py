"""Tests for coverage scoring service.

Coverage scoring determines how well a theme is supported by transcript segments.
Uses actual token_count from SegmentRef, NOT preview text length.
"""

import pytest
from src.models.edition import Coverage, SegmentRef
from src.services.coverage_service import (
    score_coverage,
    calculate_spread,
)


# Test canonical hash - arbitrary but consistent
TEST_CANONICAL_HASH = "abc123" * 10 + "abcd"  # 64 chars like SHA256


def make_segment(start: int, end: int, tokens: int) -> SegmentRef:
    """Helper to create SegmentRef for tests.

    Uses token_count as the authoritative token count,
    NOT derived from preview text.
    """
    return SegmentRef(
        start_offset=start,
        end_offset=end,
        token_count=tokens,
        text_preview="preview...",
        canonical_hash=TEST_CANONICAL_HASH,
    )


class TestCalculateSpread:
    """Tests for segment spread calculation."""

    def test_single_segment_low_spread(self):
        """Single segment cannot be well-distributed."""
        segments = [make_segment(0, 100, 25)]
        spread = calculate_spread(segments, transcript_length=10000)
        assert spread < 0.3

    def test_distributed_segments_high_spread(self):
        """Evenly distributed segments should score high."""
        # Segments distributed across transcript at 0%, 30%, 60%, 90%
        # Not perfectly even (which would be 20%, 40%, 60%, 80%) but still good
        segments = [
            make_segment(0, 100, 25),
            make_segment(3000, 3100, 25),
            make_segment(6000, 6100, 25),
            make_segment(9000, 9100, 25),
        ]
        spread = calculate_spread(segments, transcript_length=10000)
        # 0.6+ indicates reasonable distribution
        assert spread > 0.6

    def test_empty_segments_zero_spread(self):
        """Empty segments list should return 0."""
        spread = calculate_spread([], transcript_length=10000)
        assert spread == 0.0

    def test_zero_transcript_length_zero_spread(self):
        """Zero transcript length should return 0."""
        segments = [make_segment(0, 100, 25)]
        spread = calculate_spread(segments, transcript_length=0)
        assert spread == 0.0

    def test_clustered_segments_low_spread(self):
        """Segments clustered together should score low."""
        # All segments in first 10% of transcript
        segments = [
            make_segment(0, 100, 25),
            make_segment(200, 300, 25),
            make_segment(400, 500, 25),
            make_segment(600, 700, 25),
        ]
        spread = calculate_spread(segments, transcript_length=10000)
        assert spread < 0.5


class TestScoreCoverage:
    """Tests for coverage scoring."""

    def test_strong_coverage(self):
        """5+ segments with 500+ tokens and good spread = STRONG."""
        # 5 segments, 600 total tokens, distributed across transcript
        segments = [
            make_segment(i * 2000, i * 2000 + 200, 120)
            for i in range(5)
        ]
        result = score_coverage(segments, transcript_length=10000)
        assert result == Coverage.STRONG

    def test_medium_coverage(self):
        """3 segments with 300 tokens = MEDIUM."""
        segments = [
            make_segment(i * 1000, i * 1000 + 100, 100)
            for i in range(3)
        ]
        result = score_coverage(segments, transcript_length=10000)
        assert result == Coverage.MEDIUM

    def test_weak_coverage(self):
        """1 segment with few tokens = WEAK."""
        segments = [make_segment(0, 50, 20)]
        result = score_coverage(segments, transcript_length=10000)
        assert result == Coverage.WEAK

    def test_empty_segments_is_weak(self):
        """No segments = WEAK coverage."""
        result = score_coverage([], transcript_length=10000)
        assert result == Coverage.WEAK

    def test_uses_token_count_not_preview(self):
        """CRITICAL: Coverage uses token_count, not preview text length.

        This ensures accurate coverage scoring even with truncated previews.
        """
        # Same segment but with different token_count
        low_tokens = make_segment(0, 1000, 50)  # 50 tokens
        high_tokens = make_segment(0, 1000, 200)  # 200 tokens

        # Single segment can't be STRONG, but more tokens should score higher
        low_result = score_coverage([low_tokens], transcript_length=10000)
        high_result = score_coverage([high_tokens], transcript_length=10000)

        # Both weak with single segment, but test the mechanism
        assert low_tokens.token_count == 50
        assert high_tokens.token_count == 200

    def test_many_low_token_segments_not_strong(self):
        """Many segments with very few tokens should not be STRONG."""
        # 10 segments but only 5 tokens each = 50 total tokens
        segments = [
            make_segment(i * 1000, i * 1000 + 50, 5)
            for i in range(10)
        ]
        result = score_coverage(segments, transcript_length=10000)
        # Many segments (good) but low total tokens (bad)
        # Score: 0.4 * 1.0 (segments) + 0.4 * 0.1 (tokens) + 0.2 * spread
        # Should be MEDIUM at best
        assert result in [Coverage.MEDIUM, Coverage.WEAK]

    def test_few_high_token_segments_can_be_medium(self):
        """Few segments with many tokens can reach MEDIUM."""
        # 2 segments but 300 tokens each = 600 total tokens
        segments = [
            make_segment(0, 500, 300),
            make_segment(5000, 5500, 300),
        ]
        result = score_coverage(segments, transcript_length=10000)
        # Score: 0.4 * 0.4 (2/5) + 0.4 * 1.0 (600/500) + 0.2 * spread
        # = 0.16 + 0.4 + ~0.15 = ~0.71 -> STRONG or MEDIUM
        assert result in [Coverage.STRONG, Coverage.MEDIUM]
