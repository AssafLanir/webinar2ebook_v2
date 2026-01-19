"""Whitelist-based quote validation service.

Builds validated quote whitelist from Evidence Map, enforces quotes
against whitelist, and provides deterministic excerpt selection.
"""

from __future__ import annotations

from src.models.edition import SpeakerRef, SpeakerRole


def find_all_occurrences(text: str, substring: str) -> list[tuple[int, int]]:
    """Find all occurrences of substring in text.

    Args:
        text: Text to search in.
        substring: Substring to find.

    Returns:
        List of (start, end) tuples for each occurrence.
    """
    spans = []
    start = 0
    while True:
        pos = text.find(substring, start)
        if pos == -1:
            break
        spans.append((pos, pos + len(substring)))
        start = pos + 1
    return spans


def resolve_speaker(
    speaker_name: str,
    known_guests: list[str] | None = None,
    known_hosts: list[str] | None = None,
) -> SpeakerRef:
    """Resolve speaker name to typed SpeakerRef.

    Args:
        speaker_name: Name from transcript/evidence.
        known_guests: List of known guest names.
        known_hosts: List of known host names.

    Returns:
        SpeakerRef with stable ID and role.
    """
    known_guests = known_guests or []
    known_hosts = known_hosts or []

    # Generate stable ID from name
    speaker_id = speaker_name.lower().replace(" ", "_").replace(".", "")

    # Determine role
    if speaker_name.lower() in ("unknown", "unclear", ""):
        role = SpeakerRole.UNCLEAR
    elif speaker_name in known_guests:
        role = SpeakerRole.GUEST
    elif speaker_name in known_hosts:
        role = SpeakerRole.HOST
    else:
        # Default to GUEST if not explicitly known
        role = SpeakerRole.GUEST

    return SpeakerRef(
        speaker_id=speaker_id,
        speaker_name=speaker_name,
        speaker_role=role,
    )


def canonicalize_transcript(text: str) -> str:
    """Normalize transcript for matching.

    Handles:
    - Smart quotes -> straight quotes
    - Em-dash/en-dash -> hyphen
    - Collapsed whitespace

    Preserves case (for quote_text extraction).
    """
    result = text
    # Smart double quotes -> straight
    result = result.replace('\u201c', '"').replace('\u201d', '"')
    # Smart single quotes -> straight
    result = result.replace('\u2018', "'").replace('\u2019', "'")
    # Em-dash/en-dash -> hyphen
    result = result.replace('\u2014', '-').replace('\u2013', '-')
    # Collapse whitespace
    result = ' '.join(result.split())
    return result
