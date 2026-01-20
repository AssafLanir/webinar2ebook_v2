"""Quote re-anchoring service (self-heal lite).

Finds the best match for a proposed quote in the raw transcript
and returns the exact transcript substring.
"""
import re
from difflib import SequenceMatcher

# Default thresholds
DEFAULT_SIMILARITY_THRESHOLD = 0.75  # 75% match required
DEFAULT_MIN_LENGTH = 10  # Minimum quote length to attempt anchoring


def normalize_for_matching(text: str) -> str:
    """Normalize text for fuzzy matching.

    Args:
        text: Text to normalize.

    Returns:
        Normalized text (lowercased, quotes normalized, extra whitespace removed).
    """
    # Convert smart quotes to straight
    text = text.replace('\u201c', '"').replace('\u201d', '"')
    text = text.replace('\u2018', "'").replace('\u2019', "'")

    # Lowercase
    text = text.lower()

    # Remove ellipsis
    text = text.replace('...', ' ').replace('\u2026', ' ')

    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()

    return text


def find_best_match_window(
    proposed: str,
    transcript: str,
) -> tuple[int, int, float] | None:
    """Find the best matching window in transcript for proposed quote.

    Uses sliding window with fuzzy matching to find best position.

    Args:
        proposed: The proposed quote text (normalized).
        transcript: The full transcript text (normalized).

    Returns:
        Tuple of (start, end, similarity) or None if no good match.
    """
    prop_len = len(proposed)
    if prop_len < 5:
        return None

    best_score = 0.0
    best_start = 0
    best_end = 0

    # Sliding window approach
    # Try windows of similar size to proposed quote (including exact size)
    window_sizes = [prop_len - 5, prop_len, prop_len + 5, prop_len + 10]
    window_sizes = [ws for ws in window_sizes if ws >= 5]

    for window_size in window_sizes:
        # Use finer step for better precision
        step = max(1, window_size // 8)

        for start in range(0, len(transcript) - window_size + 1, step):
            end = start + window_size
            window = transcript[start:end]

            # Calculate similarity
            similarity = SequenceMatcher(None, proposed, window).ratio()

            if similarity > best_score:
                best_score = similarity
                best_start = start
                best_end = end

    if best_score < 0.5:  # Minimum threshold to continue
        return None

    # Fine-tune: try small adjustments to find word boundaries
    # without expanding too much
    fine_start = best_start
    fine_end = best_end

    # Snap to word boundary at start (look backwards a few chars only)
    lookback = min(5, fine_start)
    for i in range(fine_start, fine_start - lookback - 1, -1):
        if i == 0 or not transcript[i - 1].isalnum():
            fine_start = i
            break

    # Snap to word boundary at end (look forward a few chars only)
    lookahead = min(5, len(transcript) - fine_end)
    for i in range(fine_end, fine_end + lookahead + 1):
        if i == len(transcript) or not transcript[i].isalnum():
            fine_end = i
            break

    return (fine_start, fine_end, best_score)


def reanchor_quote(
    proposed: str,
    transcript: str,
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    min_length: int = DEFAULT_MIN_LENGTH,
) -> str | None:
    """Re-anchor a proposed quote to the exact transcript text.

    Given a potentially mangled quote, find the best match in the
    transcript and return the exact substring.

    Args:
        proposed: The proposed quote (may have typos/changes).
        transcript: The raw transcript text.
        similarity_threshold: Minimum similarity ratio (0-1) required.
        min_length: Minimum length of quote to attempt anchoring.

    Returns:
        The exact transcript substring, or None if no good match found.
    """
    # Validate inputs
    if not proposed or not transcript:
        return None

    proposed_clean = proposed.strip()
    if len(proposed_clean) < min_length:
        # For very short quotes, require exact match
        if proposed_clean.lower() in transcript.lower():
            # Find exact position and extract with original case
            idx = transcript.lower().find(proposed_clean.lower())
            return transcript[idx:idx + len(proposed_clean)]
        return None

    # Normalize for matching
    proposed_norm = normalize_for_matching(proposed_clean)
    transcript_norm = normalize_for_matching(transcript)

    # Try exact match first (fast path)
    if proposed_norm in transcript_norm:
        idx = transcript_norm.find(proposed_norm)
        # Map back to original transcript position
        result = extract_original_substring(
            transcript, transcript_norm, idx, idx + len(proposed_norm)
        )
        if result:
            return result.strip()

    # Fuzzy matching
    match = find_best_match_window(proposed_norm, transcript_norm)
    if not match:
        return None

    start, end, similarity = match

    if similarity < similarity_threshold:
        return None

    # Extract from original transcript
    result = extract_original_substring(transcript, transcript_norm, start, end)
    if not result:
        return None

    # Verify the result is reasonable
    result_norm = normalize_for_matching(result)
    final_similarity = SequenceMatcher(None, proposed_norm, result_norm).ratio()

    if final_similarity < similarity_threshold:
        return None

    return result.strip()


def extract_original_substring(
    original: str,
    normalized: str,
    norm_start: int,
    norm_end: int,
) -> str | None:
    """Extract substring from original text given normalized positions.

    Maps positions in normalized text back to original text.

    Args:
        original: Original text with original formatting.
        normalized: Normalized version of text.
        norm_start: Start position in normalized text.
        norm_end: End position in normalized text.

    Returns:
        Corresponding substring from original text.
    """
    # Build a mapping from normalized positions to original positions
    # This is needed because normalization can change string length

    position_map: dict[int, int] = {}  # norm_pos -> orig_pos

    # Walk through both strings and map positions where they align
    i = 0
    j = 0

    while i < len(original) and j < len(normalized):
        # Skip whitespace differences
        while i < len(original) and original[i].isspace() and (j >= len(normalized) or not normalized[j].isspace()):
            i += 1
        while j < len(normalized) and normalized[j].isspace() and (i >= len(original) or not original[i].isspace()):
            j += 1

        if i >= len(original) or j >= len(normalized):
            break

        position_map[j] = i

        # Move both pointers
        orig_char = original[i].lower()
        norm_char = normalized[j]

        if orig_char == norm_char or (orig_char in '"\u201c\u201d' and norm_char == '"'):
            i += 1
            j += 1
        else:
            # Mismatch - try to recover
            i += 1
            j += 1

    # Also map the end position
    position_map[j] = i

    # Get original positions
    orig_start = position_map.get(norm_start)
    if orig_start is None:
        # Find closest
        for k in range(norm_start, -1, -1):
            if k in position_map:
                orig_start = position_map[k]
                break

    orig_end = position_map.get(norm_end)
    if orig_end is None:
        # Find closest
        for k in range(norm_end, len(normalized) + 1):
            if k in position_map:
                orig_end = position_map[k]
                break

    if orig_start is None:
        orig_start = 0
    if orig_end is None:
        orig_end = len(original)

    # Ensure valid range
    orig_start = max(0, min(orig_start, len(original)))
    orig_end = max(orig_start, min(orig_end, len(original)))

    return original[orig_start:orig_end]
