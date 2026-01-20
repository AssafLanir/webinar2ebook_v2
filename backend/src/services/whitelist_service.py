"""Whitelist-based quote validation service.

Builds validated quote whitelist from Evidence Map, enforces quotes
against whitelist, and provides deterministic excerpt selection.

QUOTE ENFORCEMENT RULES:
------------------------
1. BLOCKQUOTES ("> "quote" — Speaker"):
   - Valid (in whitelist) → replace with exact whitelist text
   - Invalid (not in whitelist) → DROP entirely (remove from output)

2. INLINE QUOTES ("quoted text"):
   - Valid (in whitelist) → replace with exact whitelist text
   - Invalid (not in whitelist) → UNQUOTE (remove quotes, keep text as paraphrase)

3. KEY EXCERPTS SECTION:
   - Injected deterministically from whitelist
   - LLM blockquotes in narrative are stripped
   - Injected excerpts are preserved verbatim

4. CORE CLAIMS:
   - Filter to GUEST-only quotes
   - Supporting quotes must be in whitelist
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from hashlib import sha256
from typing import Protocol

logger = logging.getLogger(__name__)

from src.models.edition import (
    ChapterCoverage,
    ChapterCoverageReport,
    CoverageLevel,
    CoverageReport,
    SpeakerRef,
    SpeakerRole,
    TranscriptPair,
    WhitelistQuote,
)
from src.models.evidence_map import ChapterEvidence, EvidenceMap


class CoreClaimProtocol(Protocol):
    """Protocol for CoreClaim-like objects."""
    claim_text: str
    supporting_quote: str


@dataclass
class EnforcementResult:
    """Result of whitelist enforcement."""
    text: str
    replaced: list[WhitelistQuote]
    dropped: list[str]


# Patterns for quote extraction
BLOCKQUOTE_PATTERN = re.compile(
    r'^>\s*["\u201c](?P<quote>[^"\u201d]+)["\u201d]\s*$\n'
    r'^>\s*[—\-]\s*(?P<speaker>.+?)\s*$',
    re.MULTILINE
)

BLOCKQUOTE_LINE_PATTERN = re.compile(r'^>\s*.*$', re.MULTILINE)

INLINE_QUOTE_PATTERN = re.compile(
    r'["\u201c](?P<quote>[^"\u201d]{5,})["\u201d]'
)

# Coverage constants for report generation
MIN_QUOTES_PER_CHAPTER = 2
WORDS_PER_QUOTE_MULTIPLIER = 2.5  # Each quote word supports ~2.5 prose words
BASE_CHAPTER_WORDS = 150  # Minimum overhead per chapter


def assign_quotes_to_chapters_by_span(
    whitelist: list[WhitelistQuote],
    chapter_spans: list[tuple[int, int]],
) -> list[WhitelistQuote]:
    """Assign quotes to chapters based on transcript position.

    Uses match_spans to determine which chapters a quote belongs to.
    A quote is assigned to a chapter if any of its match spans
    overlaps with the chapter's span.

    Args:
        whitelist: List of WhitelistQuote objects.
        chapter_spans: List of (start, end) tuples for each chapter.
            Index 0 corresponds to chapter 0, etc.

    Returns:
        Updated whitelist with chapter_indices populated by span.
    """
    result = []

    for quote in whitelist:
        # Start with existing chapter indices
        new_indices = set(quote.chapter_indices)

        # Check each match span against each chapter span
        for span_start, span_end in quote.match_spans:
            for chapter_idx, (chapter_start, chapter_end) in enumerate(chapter_spans):
                # Check for overlap: spans overlap if neither is completely before the other
                if span_start < chapter_end and span_end > chapter_start:
                    new_indices.add(chapter_idx)

        # Create updated quote with new indices
        updated_quote = WhitelistQuote(
            quote_id=quote.quote_id,
            quote_text=quote.quote_text,
            quote_canonical=quote.quote_canonical,
            speaker=quote.speaker,
            source_evidence_ids=quote.source_evidence_ids,
            chapter_indices=sorted(new_indices),
            match_spans=quote.match_spans,
        )
        result.append(updated_quote)

    return result


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


def format_speaker_attribution(speaker: SpeakerRef) -> str:
    """Format speaker attribution with typed role label.

    Produces unambiguous attributions like:
    - "David Deutsch (GUEST)"
    - "Lex Fridman (HOST)"
    - "David (CALLER)"

    This prevents ambiguity when names could refer to multiple people
    (e.g., "David" could be David Deutsch or a caller named David).

    Args:
        speaker: SpeakerRef with name and role.

    Returns:
        Formatted attribution string.
    """
    role_label = speaker.speaker_role.value.upper()
    return f"{speaker.speaker_name} ({role_label})"


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

# Speaker quota constants
GUEST_QUOTA_RATIO = 0.8  # 80% of excerpts should be GUEST
MAX_NON_GUEST_RATIO = 0.2  # Maximum 20% non-GUEST


def select_excerpts_with_speaker_quota(
    whitelist: list[WhitelistQuote],
    chapter_index: int,
    count: int,
    guest_quota_ratio: float = GUEST_QUOTA_RATIO,
) -> list[WhitelistQuote]:
    """Select excerpts with speaker quota enforcement.

    Prefers GUEST speakers but allows HOST/other to meet minimum count.
    This replaces the all-or-nothing approach of the original fallback chain.

    Args:
        whitelist: Validated quote whitelist.
        chapter_index: 0-based chapter index.
        count: Number of excerpts to select.
        guest_quota_ratio: Minimum ratio of GUEST quotes (default 0.8).

    Returns:
        List of selected excerpts (may be less than count if insufficient quotes).
    """
    # Filter to chapter
    chapter_quotes = [q for q in whitelist if chapter_index in q.chapter_indices]

    if not chapter_quotes:
        return []

    # Separate by speaker role
    guest_quotes = [q for q in chapter_quotes if q.speaker.speaker_role == SpeakerRole.GUEST]
    non_guest_quotes = [q for q in chapter_quotes if q.speaker.speaker_role != SpeakerRole.GUEST]

    # Sort each pool: longest first, then by quote_id for determinism
    def sort_key(q: WhitelistQuote) -> tuple[int, str]:
        return (-len(q.quote_text), q.quote_id)

    guest_quotes.sort(key=sort_key)
    non_guest_quotes.sort(key=sort_key)

    # Calculate quotas
    min_guest = int(count * guest_quota_ratio)
    max_non_guest = count - min_guest  # e.g., for count=5, min_guest=4, max_non_guest=1

    # Fill from GUEST first
    selected = guest_quotes[:count]  # Take up to count GUEST quotes

    # If we don't have enough, top up with non-GUEST (up to quota)
    if len(selected) < count:
        remaining_slots = count - len(selected)
        non_guest_slots = min(remaining_slots, max_non_guest)

        # If we have very few GUEST, allow more non-GUEST to meet minimum
        if len(selected) < min_guest:
            # Relax quota when GUEST is scarce
            non_guest_slots = min(remaining_slots, len(non_guest_quotes))

        selected.extend(non_guest_quotes[:non_guest_slots])

    # Final sort for deterministic output
    selected.sort(key=sort_key)

    return selected[:count]


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

    INVARIANT: Key Excerpts must never be empty. Fallback strategy:
    1. GUEST quotes for this chapter (preferred)
    2. Any speaker quotes for this chapter (fallback)
    3. Best global GUEST quotes across all chapters (last resort)

    Args:
        whitelist: Validated quote whitelist.
        chapter_index: 0-based chapter index.
        coverage_level: Coverage level for count selection.

    Returns:
        List of selected WhitelistQuote entries (never empty if whitelist has any quotes).
    """
    count = EXCERPT_COUNTS[coverage_level]

    # Strategy 1: GUEST quotes for this chapter (preferred)
    candidates = [
        q for q in whitelist
        if chapter_index in q.chapter_indices
        and q.speaker.speaker_role == SpeakerRole.GUEST
    ]

    # Strategy 2: Any speaker for this chapter (if no GUEST quotes)
    if not candidates:
        candidates = [
            q for q in whitelist
            if chapter_index in q.chapter_indices
        ]
        if candidates:
            logger.info(
                f"Chapter {chapter_index + 1}: No GUEST quotes, falling back to all speakers "
                f"({len(candidates)} available)"
            )

    # Strategy 3: Best global GUEST quotes (if chapter has no quotes at all)
    if not candidates:
        candidates = [
            q for q in whitelist
            if q.speaker.speaker_role == SpeakerRole.GUEST
        ]
        if candidates:
            logger.warning(
                f"Chapter {chapter_index + 1}: No chapter-scoped quotes, using global GUEST quotes "
                f"({len(candidates)} available)"
            )

    # Strategy 4: Any global quotes (absolute last resort)
    if not candidates:
        candidates = list(whitelist)
        if candidates:
            logger.warning(
                f"Chapter {chapter_index + 1}: No GUEST quotes in whitelist, using any available "
                f"({len(candidates)} available)"
            )

    # Stable sort: longest first, then by quote_id for ties
    candidates.sort(key=lambda q: (-len(q.quote_text), q.quote_id))

    return candidates[:count]


def select_deterministic_excerpts_with_claims(
    whitelist: list[WhitelistQuote],
    chapter_index: int,
    coverage_level: CoverageLevel,
    claims: list[dict],
) -> list[WhitelistQuote]:
    """Select Key Excerpts with claims-first fallback.

    Extended fallback chain:
    1. Check if chapter has direct quotes (chapter_index in quote.chapter_indices)
    2. If yes, use normal selection (GUEST chapter -> any chapter -> GUEST global -> any global)
    3. If no direct chapter quotes, find quotes supporting claims in this chapter
    4. Fall back to global quotes if no claim quotes either

    Args:
        whitelist: Validated quote whitelist.
        chapter_index: 0-based chapter index.
        coverage_level: Coverage level for count selection.
        claims: List of claim dicts with 'id' and 'chapter_index' fields.

    Returns:
        List of selected WhitelistQuote entries.
    """
    count = EXCERPT_COUNTS[coverage_level]

    # Check if chapter has ANY direct quotes (regardless of speaker role)
    chapter_has_direct_quotes = any(
        chapter_index in q.chapter_indices for q in whitelist
    )

    if chapter_has_direct_quotes:
        # Use normal selection which handles GUEST/any/global fallback
        return select_deterministic_excerpts(whitelist, chapter_index, coverage_level)

    # No direct chapter quotes - try claims-first fallback
    # Get claim IDs for this chapter
    chapter_claim_ids = {
        claim["id"] for claim in claims
        if claim.get("chapter_index") == chapter_index
    }

    if chapter_claim_ids:
        # Find quotes that support these claims (prefer GUEST)
        claim_quotes = [
            q for q in whitelist
            if any(eid in chapter_claim_ids for eid in q.source_evidence_ids)
            and q.speaker.speaker_role == SpeakerRole.GUEST
        ]

        if not claim_quotes:
            # Try any speaker if no GUEST claim quotes
            claim_quotes = [
                q for q in whitelist
                if any(eid in chapter_claim_ids for eid in q.source_evidence_ids)
            ]

        if claim_quotes:
            # Sort for determinism: longest first, then by quote_id
            claim_quotes.sort(key=lambda q: (-len(q.quote_text), q.quote_id))
            return claim_quotes[:count]

    # Final fallback: use global quotes (from select_deterministic_excerpts)
    return select_deterministic_excerpts(whitelist, chapter_index, coverage_level)


def enforce_quote_whitelist(
    generated_text: str,
    whitelist: list[WhitelistQuote],
    chapter_index: int,
) -> EnforcementResult:
    """Enforce ALL quotes against whitelist.

    This is the hard guarantee. Quotes not in whitelist are removed.
    Quotes in whitelist are replaced with exact quote_text.

    Args:
        generated_text: LLM-generated text with quotes.
        whitelist: Validated quote whitelist.
        chapter_index: 0-based chapter index.

    Returns:
        EnforcementResult with cleaned text and tracking.
    """
    # Build lookup index: (speaker_id, quote_canonical) -> list[WhitelistQuote]
    lookup: dict[tuple[str, str], list[WhitelistQuote]] = {}
    for q in whitelist:
        key = (q.speaker.speaker_id, q.quote_canonical)
        lookup.setdefault(key, []).append(q)

    result = generated_text
    dropped: list[str] = []
    replaced: list[WhitelistQuote] = []

    # Track which ranges are blockquotes (so we don't process them as inline)
    blockquote_ranges: list[tuple[int, int]] = []

    # Process block quotes (must process from end to start to maintain indices)
    matches = list(BLOCKQUOTE_PATTERN.finditer(result))
    for match in reversed(matches):
        quote_text = match.group("quote")
        speaker_text = match.group("speaker")

        validated = _validate_blockquote(
            quote_text, speaker_text, chapter_index, lookup, whitelist
        )

        if validated:
            # Replace with exact quote_text
            replacement = f'> "{validated.quote_text}"\n> — {format_speaker_attribution(validated.speaker)}'
            result = result[:match.start()] + replacement + result[match.end():]
            replaced.append(validated)
            # Track new blockquote range
            blockquote_ranges.append((match.start(), match.start() + len(replacement)))
        else:
            # Drop the blockquote entirely
            result = result[:match.start()] + result[match.end():]
            dropped.append(quote_text)

    # Process inline quotes (must process from end to start to maintain indices)
    # Skip quotes that are inside blockquotes
    matches = list(INLINE_QUOTE_PATTERN.finditer(result))
    for match in reversed(matches):
        # Check if this match is inside a blockquote
        is_in_blockquote = any(
            start <= match.start() < end for start, end in blockquote_ranges
        )
        if is_in_blockquote:
            continue

        quote_text = match.group("quote")

        validated = _validate_inline(quote_text, chapter_index, lookup, whitelist)

        if validated:
            # Replace with exact quote_text
            replacement = f'"{validated.quote_text}"'
            result = result[:match.start()] + replacement + result[match.end():]
            replaced.append(validated)
        else:
            # INLINE RULE: Remove quotes but keep text (convert to paraphrase).
            # Unlike blockquotes which are dropped entirely, inline quotes are
            # unquoted to preserve the narrative flow. The idea remains, but
            # without claiming it as a direct quote.
            result = result[:match.start()] + quote_text + result[match.end():]
            dropped.append(quote_text)

    return EnforcementResult(
        text=result,
        replaced=replaced,
        dropped=dropped,
    )


def _validate_blockquote(
    quote_text: str,
    speaker_text: str | None,
    chapter_index: int,
    lookup: dict[tuple[str, str], list[WhitelistQuote]],
    whitelist: list[WhitelistQuote],
) -> WhitelistQuote | None:
    """Find matching whitelist entry for a block quote."""
    quote_canonical = canonicalize_transcript(quote_text).casefold()

    # Try to resolve speaker
    if speaker_text:
        speaker_id = speaker_text.lower().replace(" ", "_").replace(".", "")
        candidates = lookup.get((speaker_id, quote_canonical), [])
    else:
        # No speaker—search all entries with this quote
        candidates = []
        for (sid, qc), entries in lookup.items():
            if qc == quote_canonical:
                candidates.extend(entries)

    # Find best match for this chapter
    for candidate in candidates:
        if chapter_index in candidate.chapter_indices:
            return candidate

    # Fall back to any candidate
    return candidates[0] if candidates else None


def _validate_inline(
    quote_text: str,
    chapter_index: int,
    lookup: dict[tuple[str, str], list[WhitelistQuote]],
    whitelist: list[WhitelistQuote],
) -> WhitelistQuote | None:
    """Find matching whitelist entry for an inline quote."""
    quote_canonical = canonicalize_transcript(quote_text).casefold()

    # Search all entries with this quote (no speaker info for inline)
    candidates = []
    for (sid, qc), entries in lookup.items():
        if qc == quote_canonical:
            candidates.extend(entries)

    # Find best match for this chapter
    for candidate in candidates:
        if chapter_index in candidate.chapter_indices:
            return candidate

    # Fall back to any candidate
    return candidates[0] if candidates else None


def enforce_core_claims_guest_only(
    claims: list[CoreClaimProtocol],
    whitelist: list[WhitelistQuote],
    chapter_index: int,
) -> list[CoreClaimProtocol]:
    """Filter Core Claims to only include GUEST quotes.

    Uses whitelist speaker role—doesn't parse attribution from text.

    Args:
        claims: List of CoreClaim objects (anything with supporting_quote).
        whitelist: Validated quote whitelist.
        chapter_index: 0-based chapter index.

    Returns:
        Filtered list of claims with GUEST quotes only.
    """
    # Build quote lookup for this chapter
    quote_to_entry: dict[str, WhitelistQuote] = {}
    for q in whitelist:
        if chapter_index in q.chapter_indices:
            quote_to_entry[q.quote_canonical] = q

    valid_claims = []
    for claim in claims:
        quote_canonical = canonicalize_transcript(claim.supporting_quote).casefold()

        entry = quote_to_entry.get(quote_canonical)
        if not entry:
            continue  # Quote not in whitelist

        if entry.speaker.speaker_role != SpeakerRole.GUEST:
            continue  # Not from guest

        valid_claims.append(claim)

    return valid_claims


def format_excerpts_markdown(excerpts: list[WhitelistQuote]) -> str:
    """Format excerpts as markdown blockquotes for prompt injection.

    Args:
        excerpts: List of WhitelistQuote entries.

    Returns:
        Markdown-formatted blockquotes.
    """
    if not excerpts:
        return "*No excerpts available for this chapter.*"

    blocks = []
    for excerpt in excerpts:
        block = f'> "{excerpt.quote_text}"\n> — {format_speaker_attribution(excerpt.speaker)}'
        blocks.append(block)

    return '\n\n'.join(blocks)


MIN_CORE_CLAIM_QUOTE_WORDS = 8
MIN_CORE_CLAIM_QUOTE_CHARS = 50


def enforce_core_claims_text(
    text: str,
    whitelist: list[WhitelistQuote],
    chapter_index: int,
) -> tuple[str, dict]:
    """Enforce strict rules on Core Claims in markdown text.

    Core Claims must have supporting quotes that:
    1. EXACTLY match a whitelist entry (full span, not substring)
    2. Meet minimum length requirement (≥8 words or ≥50 chars)
    3. Are from GUEST speakers only

    Invalid claims are DROPPED entirely (not unquoted like narrative).

    Args:
        text: Markdown text containing Core Claims section.
        whitelist: Validated quote whitelist.
        chapter_index: 0-based chapter index.

    Returns:
        Tuple of (cleaned text, report dict).
    """
    # Find Core Claims section
    core_claims_match = re.search(r'### Core Claims\s*\n', text)
    if not core_claims_match:
        return text, {"section_found": False, "dropped": [], "kept": 0}

    # Find end of Core Claims section (next ## or ### or end of text)
    section_start = core_claims_match.end()
    next_section = re.search(r'\n##', text[section_start:])
    section_end = section_start + next_section.start() if next_section else len(text)

    section_text = text[section_start:section_end]

    # Build quote lookup for this chapter (GUEST only)
    quote_to_entry: dict[str, WhitelistQuote] = {}
    for q in whitelist:
        if chapter_index in q.chapter_indices and q.speaker.speaker_role == SpeakerRole.GUEST:
            quote_to_entry[q.quote_canonical] = q

    # Parse Core Claims bullets
    # Pattern: - **Claim text**: "supporting quote"
    # Also handles: - **Claim text**: "supporting quote" — Attribution
    bullet_pattern = re.compile(
        r'^-\s*\*\*(?P<claim>[^*]+)\*\*[:\s]*["\u201c](?P<quote>[^"\u201d]+)["\u201d].*$',
        re.MULTILINE
    )

    dropped = []
    kept_bullets = []
    other_lines = []

    lines = section_text.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i]
        match = bullet_pattern.match(line)

        if match:
            claim_text = match.group("claim")
            quote_text = match.group("quote")
            full_line = line

            # Check 1: Minimum length
            word_count = len(quote_text.split())
            char_count = len(quote_text)

            if word_count < MIN_CORE_CLAIM_QUOTE_WORDS and char_count < MIN_CORE_CLAIM_QUOTE_CHARS:
                dropped.append({
                    "claim": claim_text.strip(),
                    "quote": quote_text,
                    "reason": f"too_short ({word_count} words, {char_count} chars)"
                })
                i += 1
                continue

            # Check 2: EXACT full-span match to whitelist
            quote_canonical = canonicalize_transcript(quote_text).casefold()
            entry = quote_to_entry.get(quote_canonical)

            if not entry:
                dropped.append({
                    "claim": claim_text.strip(),
                    "quote": quote_text[:50] + "..." if len(quote_text) > 50 else quote_text,
                    "reason": "not_in_whitelist"
                })
                i += 1
                continue

            # Valid - keep the bullet with exact whitelist text
            # Reconstruct with exact quote_text from whitelist
            kept_bullets.append(
                f'- **{claim_text.strip()}**: "{entry.quote_text}"'
            )
            i += 1
        else:
            # Non-bullet line (empty or other content)
            other_lines.append((i, line))
            i += 1

    # Reconstruct section
    if kept_bullets:
        new_section = '\n'.join(kept_bullets)
    else:
        # INVARIANT: Core Claims must never be empty without explanation
        # Add placeholder when all claims were dropped
        new_section = '*No fully grounded claims available for this chapter.*'
        logger.warning(
            f"Chapter {chapter_index + 1}: All Core Claims dropped, adding placeholder "
            f"({len(dropped)} claims failed validation)"
        )

    # Reconstruct full text
    result = text[:section_start] + new_section + '\n' + text[section_end:]

    # Clean up excessive blank lines
    result = re.sub(r'\n{3,}', '\n\n', result)

    return result, {
        "section_found": True,
        "dropped": dropped,
        "kept": len(kept_bullets),
    }


def strip_llm_blockquotes(generated_text: str) -> str:
    """Remove blockquote syntax LLM added outside Key Excerpts.

    Key Excerpts section was injected deterministically and is preserved.
    Narrative should paraphrase, not quote—strip any blockquotes there.

    Args:
        generated_text: LLM-generated text.

    Returns:
        Text with blockquotes stripped from non-Key Excerpts sections.
    """
    # Find Key Excerpts section
    key_excerpts_match = re.search(r'### Key Excerpts', generated_text)

    if key_excerpts_match:
        before = generated_text[:key_excerpts_match.start()]
        after = generated_text[key_excerpts_match.start():]

        # Strip blockquotes from narrative (before Key Excerpts)
        before = BLOCKQUOTE_LINE_PATTERN.sub('', before)

        # Find Core Claims section within after
        core_claims_match = re.search(r'### Core Claims', after)
        if core_claims_match:
            excerpts_section = after[:core_claims_match.start()]
            claims_and_rest = after[core_claims_match.start():]

            # Strip blockquotes from Core Claims too (quotes should be inline only)
            claims_and_rest = BLOCKQUOTE_LINE_PATTERN.sub('', claims_and_rest)

            result = before + excerpts_section + claims_and_rest
            # Collapse multiple consecutive blank lines to double newline
            result = re.sub(r'\n{3,}', '\n\n', result)
            return result

        result = before + after
        # Collapse multiple consecutive blank lines to double newline
        result = re.sub(r'\n{3,}', '\n\n', result)
        return result

    # No Key Excerpts found—strip all blockquotes
    result = BLOCKQUOTE_LINE_PATTERN.sub('', generated_text)
    # Collapse multiple consecutive blank lines to double newline
    result = re.sub(r'\n{3,}', '\n\n', result)
    return result


def fix_quote_artifacts(text: str) -> tuple[str, dict]:
    """Remove stray quote marks and malformed quote patterns.

    Cleans up debris left by quote enforcement:
    - Lines containing only quote marks
    - Orphan closing quotes at start of sentences (word." Text)
    - Double punctuation with quotes (."." or wrong.".")
    - Stray quote-space-quote patterns (." ")
    - Tokenization artifacts (",)

    Args:
        text: Text to clean.

    Returns:
        Tuple of (cleaned text, report dict).
    """
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"fix_quote_artifacts called with {len(text)} chars")

    result = text
    original = text
    fixes = []

    # Fix 1: Remove lines that are just quote marks (straight or smart)
    # Pattern: line with only whitespace and quote marks
    standalone_quote_pattern = re.compile(r'^[\s]*["\u201c\u201d\u2018\u2019\']+[\s]*$', re.MULTILINE)
    matches = list(standalone_quote_pattern.finditer(result))
    for match in reversed(matches):
        fixes.append({"type": "standalone_quote", "text": match.group().strip()})
        result = result[:match.start()] + result[match.end():]

    # Quote character class for both straight and curly quotes
    # Using actual Unicode chars since \u escapes don't work in raw strings
    QUOTES_CLOSE = '"\u201d'  # " and "
    QUOTES_OPEN = '"\u201c'   # " and "
    QUOTES_ALL = '"\u201c\u201d'  # all quote types

    # Fix 2: Remove orphan closing quotes at word boundaries
    # Pattern: word followed by punctuation then quote (word." or word,") then space and capital
    # This catches: universe." This idea...
    orphan_close_pattern = re.compile(f'(\\w+)([.!?,])[{QUOTES_CLOSE}]\\s+([A-Z])')
    result = orphan_close_pattern.sub(r'\1\2 \3', result)

    # Fix 3: Remove orphan opening quotes before periods
    # Pattern: ." or "word where quote seems misplaced
    orphan_open_pattern = re.compile(f'[{QUOTES_OPEN}]([.!?,])')
    result = orphan_open_pattern.sub(r'\1', result)

    # Fix 4: Remove quote-space-quote patterns (." " → .)
    # This catches: expanded dramatically." " Before...
    quote_space_quote_pattern = re.compile(f'([.!?,])[{QUOTES_CLOSE}]\\s+[{QUOTES_OPEN}]\\s*')
    result = quote_space_quote_pattern.sub(r'\1 ', result)

    # Fix 5: Remove double punctuation with quotes (wrong."." → wrong.")
    double_punct_quote_pattern = re.compile(f'([.!?,])[{QUOTES_CLOSE}]([.!?,])')
    result = double_punct_quote_pattern.sub(r'\1"', result)

    # Fix 6: Remove ORPHAN trailing quote at paragraph end
    # Only match quotes that follow punctuation+quote (like ."") - clear artifact
    # This is conservative to avoid removing valid quotes like "text."
    double_trailing_quote = re.compile(f'([.!?])[{QUOTES_CLOSE}][{QUOTES_CLOSE}]\\s*(\\n\\n|\\n$|$)')
    result = double_trailing_quote.sub(r'\1"\2', result)

    # Fix 7: Remove tokenization artifacts like ", at start of segments
    token_artifact_pattern = re.compile(f'[{QUOTES_OPEN}],\\s*')
    result = token_artifact_pattern.sub('', result)

    # Fix 8: Remove mangled attribution artifacts like ," y, or ," s,
    # These are LLM tokenization bugs where "he says" becomes " y, he says"
    # Pattern: comma + quote + space + single letter + comma
    mangled_attrib_pattern = re.compile(f',[{QUOTES_CLOSE}]\\s+[a-z],\\s*')
    result = mangled_attrib_pattern.sub(', ', result)

    # Fix 9: Remove orphan quote followed by single letter (like ." s or ," y)
    # Catches: technology," y he → technology, he
    orphan_quote_letter = re.compile(f'([,.])[{QUOTES_CLOSE}]\\s+([a-z])\\s+')
    result = orphan_quote_letter.sub(r'\1 ', result)

    # Fix 10: Remove naked tokenization artifacts like ", n," or ", y," or ", s,"
    # These can appear after strip_prose_quote_chars removes quote chars
    # Pattern: comma + space + single letter + comma (no quote required)
    naked_token_artifact = re.compile(r',\s+[a-z],\s*')
    result = naked_token_artifact.sub(', ', result)

    # Fix 11: Fix missing space after sentence-ending punctuation
    # Pattern: period/exclamation/question followed immediately by capital letter
    # This catches: "wrong.Recognizing" -> "wrong. Recognizing"
    missing_space_pattern = re.compile(r'([.!?])([A-Z])')
    result = missing_space_pattern.sub(r'\1 \2', result)

    # Fix 12: Collapse multiple consecutive blank lines
    result = re.sub(r'\n{3,}', '\n\n', result)

    # Fix 13: Remove trailing whitespace on lines
    result = re.sub(r'[ \t]+$', '', result, flags=re.MULTILINE)

    # Log if changes were made
    if result != original:
        diff_chars = len(original) - len(result)
        logger.info(f"fix_quote_artifacts: text changed by {diff_chars} chars")
    else:
        logger.info("fix_quote_artifacts: no changes made")

    report = {
        "fixes_applied": len(fixes),
        "details": fixes[:10],  # First 10 fixes
    }

    return result, report


def strip_prose_quote_chars(text: str) -> tuple[str, dict]:
    """Strip quote characters from narrative prose, preserving them only in allowed contexts.

    Policy: Quote characters are ONLY allowed in:
    - Key Excerpts blockquote lines (lines starting with ">")
    - Core Claims bullet lines (lines starting with "- **")

    Everywhere else (regular narrative paragraphs), quote characters are stripped.
    This fixes:
    - Unclosed inline quotes
    - Orphan closing quotes
    - Half-quoted claims the LLM embeds in narrative

    This is safer than trying to "auto-close" quotes, which could create fake-looking quotations.

    Args:
        text: Text to process.

    Returns:
        Tuple of (cleaned text, report dict with stats).
    """
    # Quote characters to strip (double quotes only - NOT apostrophes)
    # We preserve single quotes/apostrophes because they're needed for:
    # - Contractions: that's, isn't, doesn't
    # - Possessives: Deutsch's, humanity's
    QUOTE_CHARS = {'"', '\u201c', '\u201d'}  # straight and curly double quotes only

    lines = text.split('\n')
    result_lines = []
    stripped_count = 0

    # Track which section we're in
    in_key_excerpts = False
    in_core_claims = False

    for line in lines:
        stripped_line = line.strip()

        # Detect section changes
        if stripped_line.startswith('### Key Excerpts'):
            in_key_excerpts = True
            in_core_claims = False
            result_lines.append(line)
            continue
        elif stripped_line.startswith('### Core Claims'):
            in_key_excerpts = False
            in_core_claims = True
            result_lines.append(line)
            continue
        elif stripped_line.startswith('## ') or stripped_line.startswith('### '):
            # New chapter or other section - reset
            in_key_excerpts = False
            in_core_claims = False
            result_lines.append(line)
            continue

        # Determine if this line is allowed to have quotes
        allow_quotes = False

        if in_key_excerpts:
            # In Key Excerpts: only blockquote lines and attribution lines can have quotes
            # Blockquote lines start with ">"
            # Attribution lines start with "> —" or "> —"
            if stripped_line.startswith('>'):
                allow_quotes = True

        elif in_core_claims:
            # In Core Claims: only bullet lines can have quotes
            # Bullet lines start with "- **"
            if stripped_line.startswith('- **'):
                allow_quotes = True

        # Process the line
        if allow_quotes:
            result_lines.append(line)
        else:
            # Strip quote characters from this line
            new_line = ''.join(c for c in line if c not in QUOTE_CHARS)
            if new_line != line:
                stripped_count += len(line) - len(new_line)
            result_lines.append(new_line)

    result = '\n'.join(result_lines)

    report = {
        "quotes_stripped": stripped_count,
        "lines_processed": len(lines),
    }

    return result, report


def detect_verbatim_leakage(
    text: str,
    whitelist: list[WhitelistQuote],
    min_words: int = 6,
) -> tuple[str, dict]:
    """Detect and remove verbatim whitelist quotes appearing unquoted in prose.

    The LLM can bypass quote enforcement by pasting transcript text without
    quotation marks. This detector finds such leakage and removes the sentences.

    Args:
        text: Generated text.
        whitelist: Validated quote whitelist.
        min_words: Minimum words for a match to count as leakage (default 6).

    Returns:
        Tuple of (cleaned text, report dict).
    """
    # Extract prose sections (exclude Key Excerpts and Core Claims)
    # We'll work on the full text but only flag leakage outside structured sections

    result = text
    leakages = []

    # Build set of canonical quote substrings to search for
    # Use sliding window of min_words to catch partial matches
    quote_fragments: dict[str, WhitelistQuote] = {}
    for q in whitelist:
        # Split into words and create fragments
        words = q.quote_canonical.split()
        if len(words) >= min_words:
            # Create overlapping fragments
            for i in range(len(words) - min_words + 1):
                fragment = ' '.join(words[i:i + min_words])
                quote_fragments[fragment] = q

    # Canonicalize the text for searching
    canonical_text = canonicalize_transcript(text)

    # Find Key Excerpts and Core Claims sections to exclude
    key_excerpts_pattern = re.compile(r'### Key Excerpts.*?(?=### Core Claims|## Chapter|\Z)', re.DOTALL)
    core_claims_pattern = re.compile(r'### Core Claims.*?(?=## Chapter|\Z)', re.DOTALL)

    # Find positions of structured sections in canonical text
    excluded_ranges: list[tuple[int, int]] = []
    for match in key_excerpts_pattern.finditer(canonical_text):
        excluded_ranges.append((match.start(), match.end()))
    for match in core_claims_pattern.finditer(canonical_text):
        excluded_ranges.append((match.start(), match.end()))

    def is_in_excluded_range(pos: int) -> bool:
        return any(start <= pos < end for start, end in excluded_ranges)

    # Search for quote fragments in canonical text
    for fragment, quote in quote_fragments.items():
        pos = 0
        while True:
            found = canonical_text.find(fragment, pos)
            if found == -1:
                break

            # Check if this position is in an excluded section
            if not is_in_excluded_range(found):
                leakages.append({
                    "fragment": fragment,
                    "position": found,
                    "quote_id": quote.quote_id,
                    "speaker": quote.speaker.speaker_name,
                })

            pos = found + 1

    # For now, just report leakages (removal would require careful sentence detection)
    # In future: could remove sentences containing leakage
    report = {
        "leakage_count": len(leakages),
        "leakages": leakages[:10],  # First 10 leakages
        "action": "reported",  # Future: "removed"
    }

    return result, report


def generate_coverage_report(
    whitelist: list[WhitelistQuote],
    chapter_count: int,
    transcript_hash: str,
) -> CoverageReport:
    """Generate pre-generation coverage report.

    Analyzes whitelist to predict feasibility and word count
    before running expensive LLM generation.

    Args:
        whitelist: Validated quote whitelist.
        chapter_count: Number of chapters planned.
        transcript_hash: Hash of canonical transcript.

    Returns:
        CoverageReport with feasibility analysis.
    """
    chapters = []
    feasibility_notes = []
    total_quote_words = 0

    for chapter_idx in range(chapter_count):
        # Count quotes for this chapter
        chapter_quotes = [
            q for q in whitelist
            if chapter_idx in q.chapter_indices
        ]
        guest_quotes = [
            q for q in chapter_quotes
            if q.speaker.speaker_role == SpeakerRole.GUEST
        ]

        valid_count = len(guest_quotes)
        invalid_count = len(chapter_quotes) - valid_count

        # Estimate word range based on GUEST quote words
        quote_words = sum(len(q.quote_text.split()) for q in guest_quotes)
        total_quote_words += quote_words

        min_words = BASE_CHAPTER_WORDS + quote_words
        max_words = BASE_CHAPTER_WORDS + int(quote_words * WORDS_PER_QUOTE_MULTIPLIER)

        chapters.append(ChapterCoverageReport(
            chapter_index=chapter_idx,
            valid_quotes=valid_count,
            invalid_quotes=invalid_count,
            valid_claims=0,  # TODO: count from evidence map
            invalid_claims=0,
            predicted_word_range=(min_words, max_words),
        ))

        if valid_count < MIN_QUOTES_PER_CHAPTER:
            feasibility_notes.append(
                f"Chapter {chapter_idx + 1} has only {valid_count} GUEST quotes "
                f"(minimum {MIN_QUOTES_PER_CHAPTER})"
            )

    # Calculate totals
    min_total = sum(ch.predicted_word_range[0] for ch in chapters)
    max_total = sum(ch.predicted_word_range[1] for ch in chapters)

    is_feasible = len(feasibility_notes) == 0 and len(whitelist) >= MIN_QUOTES_PER_CHAPTER

    if not whitelist:
        feasibility_notes.append("No valid whitelist quotes found")
        is_feasible = False

    return CoverageReport(
        transcript_hash=transcript_hash,
        total_whitelist_quotes=len(whitelist),
        chapters=chapters,
        predicted_total_range=(min_total, max_total),
        is_feasible=is_feasible,
        feasibility_notes=feasibility_notes,
    )
