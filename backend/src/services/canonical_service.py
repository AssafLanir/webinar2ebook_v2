"""Canonical transcript service for offset-safe text normalization.

This service provides text canonicalization for consistent character offsets.
CRITICAL: Offsets in SegmentRef must reference the CANONICAL transcript,
not the raw transcript. All offset computation happens AFTER canonicalization.

The canonical transcript is the reference text for all SegmentRef offsets.
"""

import hashlib
import re
import unicodedata


def canonicalize(text: str) -> str:
    """Normalize text for consistent character offsets.

    Normalization steps (in order):
    1. Apply Unicode NFC normalization (ensures composed/decomposed equivalence)
    2. Collapse multiple whitespace (including newlines) to single space
    3. Normalize smart quotes (\u201c, \u201d) to straight quotes (")
    4. Normalize curly apostrophes (\u2018, \u2019) to straight apostrophes (')
    5. Normalize em/en dashes (\u2014, \u2013) to hyphens (-)
    6. Normalize non-breaking spaces (\u00a0) to regular spaces
    7. Strip leading/trailing whitespace

    Supported character scope:
    - Smart/curly double quotes: \u201c, \u201d -> "
    - Curly single quotes/apostrophes: \u2018, \u2019 -> '
    - Em dash (\u2014), en dash (\u2013) -> -
    - Non-breaking space (\u00a0) -> regular space

    Not normalized (out of scope for typical webinar transcripts):
    - Angle quotes/guillemets: << >> (U+00AB, U+00BB), < > (U+2039, U+203A)

    Returns canonicalized text suitable for offset references.

    IMPORTANT: This function must be idempotent.
    canonicalize(canonicalize(x)) == canonicalize(x)
    """
    if not text:
        return ""

    # Apply NFC normalization first to ensure composed/decomposed characters
    # produce the same result (e.g., 'cafe\u0301' -> 'cafe')
    result = unicodedata.normalize('NFC', text)

    # Normalize smart/curly double quotes to straight quotes
    # \u201c = left double quote, \u201d = right double quote
    result = result.replace('\u201c', '"')
    result = result.replace('\u201d', '"')

    # Normalize curly single quotes/apostrophes to straight apostrophes
    # \u2018 = left single quote, \u2019 = right single quote (curly apostrophe)
    result = result.replace('\u2018', "'")
    result = result.replace('\u2019', "'")

    # Normalize em and en dashes to hyphens
    # \u2014 = em dash, \u2013 = en dash
    result = result.replace('\u2014', '-')
    result = result.replace('\u2013', '-')

    # Normalize non-breaking spaces to regular spaces
    # \u00a0 = non-breaking space
    result = result.replace('\u00a0', ' ')

    # Normalize all whitespace (including \r\n, \n, \t, multiple spaces) to single space
    # This regex matches any sequence of whitespace characters
    result = re.sub(r'\s+', ' ', result)

    # Strip leading and trailing whitespace
    result = result.strip()

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
