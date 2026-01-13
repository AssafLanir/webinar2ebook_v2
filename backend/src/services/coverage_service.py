"""Coverage scoring for theme supporting segments.

CRITICAL: Coverage scoring uses SegmentRef.token_count (actual token count),
NOT preview text length. This ensures accurate scoring even with truncated previews.

Deterministic scoring based on:
- Number of supporting segments (40% weight)
- Total token count (40% weight)
- Spread across transcript (20% weight)
"""

from src.models.edition import Coverage, SegmentRef


def calculate_spread(segments: list[SegmentRef], transcript_length: int) -> float:
    """Calculate how well-distributed segments are across transcript.

    Args:
        segments: List of segment references
        transcript_length: Total length of transcript in chars

    Returns:
        Spread score from 0.0 (clustered) to 1.0 (evenly distributed)
    """
    if not segments or transcript_length <= 0:
        return 0.0

    if len(segments) == 1:
        # Single segment can't be well-distributed
        return 0.1

    # Get midpoints of each segment
    midpoints = sorted([
        (s.start_offset + s.end_offset) / 2
        for s in segments
    ])

    # Calculate gaps between consecutive midpoints
    gaps = [
        midpoints[i + 1] - midpoints[i]
        for i in range(len(midpoints) - 1)
    ]

    # Ideal gap for even distribution
    ideal_gap = transcript_length / (len(segments) + 1)

    # Score based on how close gaps are to ideal
    if ideal_gap <= 0:
        return 0.0

    gap_scores = [
        min(gap / ideal_gap, ideal_gap / gap) if gap > 0 else 0.0
        for gap in gaps
    ]

    return sum(gap_scores) / len(gap_scores) if gap_scores else 0.0


def score_coverage(segments: list[SegmentRef], transcript_length: int) -> Coverage:
    """Score theme coverage based on supporting segments.

    CRITICAL: Uses SegmentRef.token_count for accurate scoring,
    NOT derived from preview text length.

    Scoring formula:
    - 40% weight: number of segments (up to 5)
    - 40% weight: total tokens (up to 500)
    - 20% weight: spread across transcript

    Args:
        segments: Supporting segment references
        transcript_length: Total transcript length in chars

    Returns:
        Coverage level (STRONG, MEDIUM, or WEAK)
    """
    if not segments:
        return Coverage.WEAK

    num_segments = len(segments)
    # CRITICAL: Use token_count from SegmentRef, NOT preview length
    total_tokens = sum(s.token_count for s in segments)
    spread = calculate_spread(segments, transcript_length)

    score = (
        min(num_segments / 5, 1.0) * 0.4 +
        min(total_tokens / 500, 1.0) * 0.4 +
        spread * 0.2
    )

    if score >= 0.7:
        return Coverage.STRONG
    elif score >= 0.4:
        return Coverage.MEDIUM
    else:
        return Coverage.WEAK
