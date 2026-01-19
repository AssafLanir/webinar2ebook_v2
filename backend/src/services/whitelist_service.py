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

import re
from dataclasses import dataclass
from hashlib import sha256
from typing import Protocol

from src.models.edition import ChapterCoverage, CoverageLevel, SpeakerRef, SpeakerRole, TranscriptPair, WhitelistQuote
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
            replacement = f'> "{validated.quote_text}"\n> — {validated.speaker.speaker_name}'
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
        block = f'> "{excerpt.quote_text}"\n> — {excerpt.speaker.speaker_name}'
        blocks.append(block)

    return '\n\n'.join(blocks)


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
    - Mismatched quote marks

    Args:
        text: Text to clean.

    Returns:
        Tuple of (cleaned text, report dict).
    """
    result = text
    fixes = []

    # Fix 1: Remove lines that are just quote marks (straight or smart)
    # Pattern: line with only whitespace and quote marks
    standalone_quote_pattern = re.compile(r'^[\s]*["\u201c\u201d\u2018\u2019\']+[\s]*$', re.MULTILINE)
    matches = list(standalone_quote_pattern.finditer(result))
    for match in reversed(matches):
        fixes.append({"type": "standalone_quote", "text": match.group().strip()})
        result = result[:match.start()] + result[match.end():]

    # Fix 2: Remove orphan closing quotes at word boundaries
    # Pattern: word followed by punctuation then quote (word." or word,") then space and capital
    # This catches: universe." This idea...
    orphan_close_pattern = re.compile(r'(\w+)([.!?,])["\u201d]\s+([A-Z])')
    result = orphan_close_pattern.sub(r'\1\2 \3', result)

    # Fix 3: Remove orphan opening quotes before periods
    # Pattern: ." or "word where quote seems misplaced
    orphan_open_pattern = re.compile(r'["\u201c]([.!?,])')
    result = orphan_open_pattern.sub(r'\1', result)

    # Fix 4: Collapse multiple consecutive blank lines
    result = re.sub(r'\n{3,}', '\n\n', result)

    # Fix 5: Remove trailing whitespace on lines
    result = re.sub(r'[ \t]+$', '', result, flags=re.MULTILINE)

    report = {
        "fixes_applied": len(fixes),
        "details": fixes[:10],  # First 10 fixes
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
