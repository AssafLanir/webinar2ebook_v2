"""Canonical transcript service for offset-safe text normalization.

This service provides TWO canonicalization modes:

1. canonicalize() - FLAT canonical for offsets/hashing
   - All whitespace collapsed to single space
   - Used for: SegmentRef offsets, hash computation, quote validation
   - CRITICAL: All offsets must reference this flat canonical form

2. canonicalize_structured() - STRUCTURED canonical for display/parsing
   - Preserves paragraph breaks (double newlines)
   - Used for: Display, speaker turn parsing, UI rendering
   - Same character normalizations, but keeps document structure

Both apply the same character normalizations:
- Unicode NFC normalization
- Smart quotes → straight quotes
- Curly apostrophes → straight apostrophes
- Em/en dashes → hyphens
- Non-breaking spaces → regular spaces
"""

import hashlib
import re
import unicodedata


def _normalize_characters(text: str) -> str:
    """Apply character-level normalizations (shared by both modes).

    Steps:
    1. Unicode NFC normalization
    2. Smart quotes → straight quotes
    3. Curly apostrophes → straight apostrophes
    4. Em/en dashes → hyphens
    5. Non-breaking spaces → regular spaces

    Does NOT handle whitespace collapsing - that differs by mode.
    """
    if not text:
        return ""

    # Apply NFC normalization first
    result = unicodedata.normalize('NFC', text)

    # Normalize smart/curly double quotes to straight quotes
    result = result.replace('\u201c', '"')
    result = result.replace('\u201d', '"')

    # Normalize curly single quotes/apostrophes to straight apostrophes
    result = result.replace('\u2018', "'")
    result = result.replace('\u2019', "'")

    # Normalize em and en dashes to hyphens
    result = result.replace('\u2014', '-')
    result = result.replace('\u2013', '-')

    # Normalize non-breaking spaces to regular spaces
    result = result.replace('\u00a0', ' ')

    return result


def canonicalize(text: str) -> str:
    """FLAT canonical: Normalize text for consistent character offsets.

    Use this for: SegmentRef offsets, hash computation, quote validation.
    All whitespace (including newlines) collapses to single space.

    IMPORTANT: This function must be idempotent.
    canonicalize(canonicalize(x)) == canonicalize(x)

    Returns:
        Flat canonicalized text suitable for offset references.
    """
    if not text:
        return ""

    # Apply character normalizations
    result = _normalize_characters(text)

    # FLAT mode: Collapse ALL whitespace to single space
    result = re.sub(r'\s+', ' ', result)

    # Strip leading and trailing whitespace
    result = result.strip()

    return result


def canonicalize_structured(text: str) -> str:
    """STRUCTURED canonical: Normalize text while preserving paragraph structure.

    Use this for: Display, speaker turn parsing, UI rendering.
    Preserves paragraph breaks (double newlines) for structure.

    Normalization:
    - Same character normalizations as canonicalize()
    - Whitespace within paragraphs → single space
    - Paragraph breaks (2+ newlines) → double newline
    - Leading/trailing whitespace stripped

    IMPORTANT: This function must be idempotent.
    canonicalize_structured(canonicalize_structured(x)) == canonicalize_structured(x)

    Returns:
        Structured canonicalized text with preserved paragraph breaks.
    """
    if not text:
        return ""

    # Apply character normalizations
    result = _normalize_characters(text)

    # Normalize line endings: \r\n -> \n
    result = result.replace('\r\n', '\n')
    result = result.replace('\r', '\n')

    # Split into paragraphs (2+ newlines = paragraph break)
    # This regex splits on 2 or more newlines
    paragraphs = re.split(r'\n{2,}', result)

    # Process each paragraph: collapse internal whitespace
    normalized_paragraphs = []
    for para in paragraphs:
        # Collapse whitespace within paragraph (including single newlines)
        normalized = re.sub(r'\s+', ' ', para).strip()
        if normalized:  # Skip empty paragraphs
            normalized_paragraphs.append(normalized)

    # Join with double newline (canonical paragraph separator)
    result = '\n\n'.join(normalized_paragraphs)

    return result


def normalize_for_comparison(text: str) -> str:
    """Normalize text for fuzzy quote comparison.

    Applies canonicalization + lowercase.
    Use this when comparing quotes that may have case differences.

    Args:
        text: Text to normalize

    Returns:
        Canonicalized and lowercased text
    """
    return canonicalize(text).lower()


def compute_hash(text: str) -> str:
    """Compute SHA256 hash of text (should be canonicalized first).

    Args:
        text: Text to hash (typically already canonicalized)

    Returns:
        Hex-encoded SHA256 hash (64 chars)
    """
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def verify_canonical(transcript: str, stored_hash: str) -> bool:
    """Verify transcript matches stored canonical hash.

    This function canonicalizes the input transcript and compares
    its hash against the stored hash. Useful for detecting if
    the source transcript has changed.

    Args:
        transcript: Raw or canonical transcript text
        stored_hash: Previously computed hash from freeze_canonical_transcript

    Returns:
        True if canonicalize(transcript) has same hash as stored_hash
    """
    canonical = canonicalize(transcript)
    computed_hash = compute_hash(canonical)
    return computed_hash == stored_hash


def freeze_canonical_transcript(transcript: str) -> tuple[str, str]:
    """Freeze transcript for offset references.

    Use this when proposing themes to lock the canonical version.
    The returned canonical text is the reference for all SegmentRef offsets.
    The hash can be stored to verify the transcript hasn't changed.

    Args:
        transcript: Raw transcript text

    Returns:
        (canonical_text, hash) tuple where:
        - canonical_text: Normalized text for offset references
        - hash: SHA256 hash of the canonical text (64 chars)
    """
    canonical = canonicalize(transcript)
    hash_val = compute_hash(canonical)
    return (canonical, hash_val)
