"""Whitelist-based quote validation service.

Builds validated quote whitelist from Evidence Map, enforces quotes
against whitelist, and provides deterministic excerpt selection.
"""

from __future__ import annotations

from hashlib import sha256

from src.models.edition import ChapterCoverage, CoverageLevel, SpeakerRef, SpeakerRole, TranscriptPair, WhitelistQuote
from src.models.evidence_map import ChapterEvidence, EvidenceMap


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


def build_quote_whitelist(
    evidence_map: EvidenceMap,
    transcript: TranscriptPair,
    known_guests: list[str] | None = None,
    known_hosts: list[str] | None = None,
) -> list[WhitelistQuote]:
    """Build whitelist of validated quotes from Evidence Map.

    Only includes quotes that:
    1. Have a speaker (None/Unknown attribution rejected)
    2. Match as substring in canonical transcript
    3. Have speaker resolved to non-UNCLEAR role

    Args:
        evidence_map: Evidence map with claims and support quotes.
        transcript: Raw and canonical transcript pair.
        known_guests: List of known guest names.
        known_hosts: List of known host names.

    Returns:
        List of validated WhitelistQuote entries.
    """
    known_guests = known_guests or []
    known_hosts = known_hosts or []

    canonical_lower = transcript.canonical.casefold()
    whitelist_map: dict[tuple[str, str], WhitelistQuote] = {}

    for chapter in evidence_map.chapters:
        # Convert 1-based chapter_index to 0-based
        chapter_idx = chapter.chapter_index - 1

        for claim in chapter.claims:
            for support in claim.support:
                # Reject None/Unknown attribution
                if not support.speaker:
                    continue

                speaker_ref = resolve_speaker(
                    support.speaker,
                    known_guests=known_guests,
                    known_hosts=known_hosts,
                )

                # Skip UNCLEAR speakers
                if speaker_ref.speaker_role == SpeakerRole.UNCLEAR:
                    continue

                # Canonicalize quote for matching
                quote_for_match = canonicalize_transcript(support.quote).casefold()

                # Find quote in canonical for validation
                spans_canonical = find_all_occurrences(canonical_lower, quote_for_match)
                if not spans_canonical:
                    continue  # Not in transcript

                # Find the ORIGINAL quote text in raw transcript for extraction
                # The support.quote should match the raw transcript verbatim or with minor variations
                raw_lower = transcript.raw.casefold()
                raw_quote_search = support.quote.casefold()
                spans_raw = find_all_occurrences(raw_lower, raw_quote_search)

                if spans_raw:
                    # Found exact quote in raw
                    start, end = spans_raw[0]
                    exact_quote = transcript.raw[start:end]
                    spans = spans_raw
                else:
                    # Fallback: use canonical match position on canonical transcript
                    start, end = spans_canonical[0]
                    exact_quote = transcript.canonical[start:end]
                    spans = spans_canonical

                key = (speaker_ref.speaker_id, quote_for_match)

                if key in whitelist_map:
                    # Merge: add chapter, evidence ID
                    existing = whitelist_map[key]
                    if chapter_idx not in existing.chapter_indices:
                        existing.chapter_indices.append(chapter_idx)
                    if claim.id not in existing.source_evidence_ids:
                        existing.source_evidence_ids.append(claim.id)
                else:
                    # Create new entry with stable ID
                    quote_id = sha256(
                        f"{speaker_ref.speaker_id}|{quote_for_match}".encode()
                    ).hexdigest()[:16]

                    whitelist_map[key] = WhitelistQuote(
                        quote_id=quote_id,
                        quote_text=exact_quote,
                        quote_canonical=quote_for_match,
                        speaker=speaker_ref,
                        source_evidence_ids=[claim.id],
                        chapter_indices=[chapter_idx],
                        match_spans=spans,
                    )

    return list(whitelist_map.values())


# Coverage thresholds
MIN_USABLE_QUOTE_LENGTH = 8  # words
STRONG_QUOTES = 5
STRONG_WORDS_PER_CLAIM = 50
MEDIUM_QUOTES = 3
MEDIUM_WORDS_PER_CLAIM = 30

# Excerpt counts per coverage level
EXCERPT_COUNTS = {
    CoverageLevel.STRONG: 4,
    CoverageLevel.MEDIUM: 3,
    CoverageLevel.WEAK: 2,
}


def compute_chapter_coverage(
    chapter_evidence: ChapterEvidence,
    whitelist: list[WhitelistQuote],
    chapter_index: int,
) -> ChapterCoverage:
    """Compute coverage metrics for a single chapter.

    Args:
        chapter_evidence: Evidence data for chapter.
        whitelist: Full whitelist of validated quotes.
        chapter_index: 0-based chapter index.

    Returns:
        ChapterCoverage with level and target_words.
    """
    # Filter whitelist to this chapter
    chapter_quotes = [
        q for q in whitelist
        if chapter_index in q.chapter_indices
    ]

    # Filter by minimum length
    usable_quotes = [
        q for q in chapter_quotes
        if len(q.quote_text.split()) >= MIN_USABLE_QUOTE_LENGTH
    ]

    claim_count = len(chapter_evidence.claims)
    total_quote_words = sum(len(q.quote_text.split()) for q in usable_quotes)

    # Compute metrics
    quotes_per_claim = len(usable_quotes) / max(claim_count, 1)
    quote_words_per_claim = total_quote_words / max(claim_count, 1)

    # Determine level
    if len(usable_quotes) >= STRONG_QUOTES and quote_words_per_claim >= STRONG_WORDS_PER_CLAIM:
        level = CoverageLevel.STRONG
        target_words = 800
        mode = "normal"
    elif len(usable_quotes) >= MEDIUM_QUOTES and quote_words_per_claim >= MEDIUM_WORDS_PER_CLAIM:
        level = CoverageLevel.MEDIUM
        target_words = 500
        mode = "thin"
    else:
        level = CoverageLevel.WEAK
        target_words = 250
        mode = "excerpt_only"

    return ChapterCoverage(
        chapter_index=chapter_index,
        level=level,
        usable_quotes=len(usable_quotes),
        quote_words_per_claim=quote_words_per_claim,
        quotes_per_claim=quotes_per_claim,
        target_words=target_words,
        generation_mode=mode,
    )


def select_deterministic_excerpts(
    whitelist: list[WhitelistQuote],
    chapter_index: int,
    coverage_level: CoverageLevel,
) -> list[WhitelistQuote]:
    """Select Key Excerpts deterministically from whitelist.

    Valid by construction: these quotes come from whitelist,
    so they're guaranteed to be transcript substrings with known speakers.

    Args:
        whitelist: Validated quote whitelist.
        chapter_index: 0-based chapter index.
        coverage_level: Coverage level for count selection.

    Returns:
        List of selected WhitelistQuote entries.
    """
    # Filter to this chapter, GUEST only
    candidates = [
        q for q in whitelist
        if chapter_index in q.chapter_indices
        and q.speaker.speaker_role == SpeakerRole.GUEST
    ]

    # Stable sort: longest first, then by quote_id for ties
    candidates.sort(key=lambda q: (-len(q.quote_text), q.quote_id))

    count = EXCERPT_COUNTS[coverage_level]
    return candidates[:count]
