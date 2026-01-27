"""Groundedness Harness v1: Quote provenance and claim support validation.

Validates that:
1. Key Excerpts quotes actually exist in the source transcript
2. Core Claims have supporting quotes that exist in the transcript

This catches "invented quotes" and ensures output is grounded in source material.

Feature Flag:
    GROUNDEDNESS_ENABLED: Set to "true" to enable groundedness checking in production.
                          Default: "false" (disabled in production, tests run regardless)
"""

import logging
import os
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Optional

logger = logging.getLogger(__name__)

# Feature flag: OFF by default in production
GROUNDEDNESS_ENABLED = os.environ.get("GROUNDEDNESS_ENABLED", "false").lower() == "true"


def is_groundedness_enabled() -> bool:
    """Check if groundedness checking is enabled.

    Returns True if GROUNDEDNESS_ENABLED env var is "true".
    Tests bypass this check and run regardless.
    """
    return GROUNDEDNESS_ENABLED


# =============================================================================
# Data Structures
# =============================================================================


@dataclass
class QuoteMatch:
    """Result of matching a quote against transcript."""
    quote_text: str
    quote_normalized: str
    found: bool
    match_type: Optional[str] = None  # "exact", "anchor", "fuzzy", None
    match_score: float = 0.0
    match_location: Optional[int] = None  # character offset in transcript


@dataclass
class ExcerptProvenanceResult:
    """Result of Key Excerpts provenance check."""
    excerpts_total: int = 0
    excerpts_found: int = 0
    excerpts_not_found: int = 0
    provenance_rate: float = 0.0
    missing_quotes: list[str] = field(default_factory=list)
    matches: list[QuoteMatch] = field(default_factory=list)
    verdict: str = "PASS"  # PASS, WARN, FAIL


@dataclass
class ClaimSupportResult:
    """Result of Core Claims support check."""
    claims_total: int = 0
    claims_with_evidence: int = 0
    claims_missing_evidence: int = 0
    evidence_quotes_found: int = 0
    evidence_quotes_not_found: int = 0
    evidence_provenance_rate: float = 0.0
    missing_evidence_claims: list[str] = field(default_factory=list)
    missing_evidence_quotes: list[str] = field(default_factory=list)
    verdict: str = "PASS"


@dataclass
class GroundednessReport:
    """Combined groundedness report."""
    excerpt_provenance: ExcerptProvenanceResult
    claim_support: ClaimSupportResult
    overall_verdict: str = "PASS"


# =============================================================================
# Text Normalization
# =============================================================================


def normalize_for_matching(text: str) -> str:
    """Normalize text for fuzzy matching.

    - Lowercase
    - Collapse whitespace
    - Remove most punctuation (keep apostrophes for contractions)
    - Normalize smart quotes to straight quotes
    """
    # Normalize smart quotes
    text = text.replace('"', '"').replace('"', '"')
    text = text.replace(''', "'").replace(''', "'")
    text = text.replace('—', '-').replace('–', '-')
    text = text.replace('…', '...')

    # Lowercase
    text = text.lower()

    # Remove punctuation except apostrophes
    text = re.sub(r'[^\w\s\']', ' ', text)

    # Collapse whitespace
    text = ' '.join(text.split())

    return text


def extract_anchor(text: str, num_words: int = 10) -> str:
    """Extract first N words as anchor for matching."""
    words = text.split()
    return ' '.join(words[:num_words])


# =============================================================================
# Quote Extraction
# =============================================================================


def extract_key_excerpts_quotes(markdown: str) -> list[str]:
    """Extract quotes from Key Excerpts sections.

    Key Excerpts format:
    > "Quote text here"
    > — Speaker Name

    or:
    > "Quote text here"
    > — Unknown
    """
    quotes = []

    # Find all Key Excerpts sections
    sections = re.split(r'(?m)^### ', markdown)

    for section in sections:
        if not section.startswith('Key Excerpts'):
            continue

        # Extract blockquote content
        # Pattern: > "quote" or > "quote"
        blockquote_pattern = r'>\s*["""](.+?)["""]'
        matches = re.findall(blockquote_pattern, section, re.DOTALL)

        for match in matches:
            # Clean up the quote
            quote = match.strip()
            # Remove any trailing attribution that got captured
            quote = re.sub(r'\n>\s*—.*$', '', quote, flags=re.MULTILINE)
            quote = ' '.join(quote.split())  # Normalize whitespace
            if quote:
                quotes.append(quote)

    return quotes


def extract_core_claims_with_evidence(markdown: str) -> list[tuple[str, Optional[str]]]:
    """Extract Core Claims with their supporting quote evidence.

    Core Claims format:
    - **Claim title**: "Supporting quote here"

    Returns list of (claim_text, evidence_quote) tuples.
    """
    claims = []

    # Find all Core Claims sections
    sections = re.split(r'(?m)^### ', markdown)

    for section in sections:
        if not section.startswith('Core Claims'):
            continue

        # Pattern: - **claim**: "quote"
        # Also handle claims without quotes
        claim_pattern = r'-\s*\*\*(.+?)\*\*:\s*(?:["""](.+?)["""])?'
        matches = re.findall(claim_pattern, section)

        for claim_title, evidence in matches:
            claim_title = claim_title.strip()
            evidence = evidence.strip() if evidence else None
            claims.append((claim_title, evidence))

    return claims


# =============================================================================
# Provenance Matching
# =============================================================================


def match_quote_in_transcript(
    quote: str,
    transcript: str,
    transcript_normalized: str,
    fuzzy_threshold: float = 0.85,
) -> QuoteMatch:
    """Check if a quote exists in the transcript.

    Matching strategy:
    1. Exact normalized substring match (fast path)
    2. Anchor search: match first ~10 words, allow rest to differ
    3. Fuzzy match with difflib (fallback)
    """
    quote_normalized = normalize_for_matching(quote)

    # Fast path: exact substring match
    if quote_normalized in transcript_normalized:
        location = transcript_normalized.find(quote_normalized)
        return QuoteMatch(
            quote_text=quote,
            quote_normalized=quote_normalized,
            found=True,
            match_type="exact",
            match_score=1.0,
            match_location=location,
        )

    # Anchor search: match first 10 words
    anchor = extract_anchor(quote_normalized, num_words=10)
    if len(anchor.split()) >= 8 and anchor in transcript_normalized:
        # Found anchor, check if reasonable match
        location = transcript_normalized.find(anchor)
        # Extract surrounding context from transcript
        context_start = max(0, location - 20)
        context_end = min(len(transcript_normalized), location + len(quote_normalized) + 50)
        context = transcript_normalized[context_start:context_end]

        # Calculate similarity with context
        ratio = SequenceMatcher(None, quote_normalized, context).ratio()
        if ratio >= fuzzy_threshold:
            return QuoteMatch(
                quote_text=quote,
                quote_normalized=quote_normalized,
                found=True,
                match_type="anchor",
                match_score=ratio,
                match_location=location,
            )

    # Fuzzy match: sliding window search
    # Only do this for shorter quotes to avoid performance issues
    if len(quote_normalized) <= 500:
        best_score = 0.0
        best_location = None
        window_size = len(quote_normalized) + 50  # Allow some slack

        # Sample positions to avoid O(n²)
        step = max(1, len(transcript_normalized) // 100)
        for i in range(0, len(transcript_normalized) - window_size, step):
            window = transcript_normalized[i:i + window_size]
            ratio = SequenceMatcher(None, quote_normalized, window).ratio()
            if ratio > best_score:
                best_score = ratio
                best_location = i

        if best_score >= fuzzy_threshold:
            return QuoteMatch(
                quote_text=quote,
                quote_normalized=quote_normalized,
                found=True,
                match_type="fuzzy",
                match_score=best_score,
                match_location=best_location,
            )

    # No match found
    return QuoteMatch(
        quote_text=quote,
        quote_normalized=quote_normalized,
        found=False,
        match_type=None,
        match_score=0.0,
    )


# =============================================================================
# Main Validation Functions
# =============================================================================


def check_excerpt_provenance(
    markdown: str,
    transcript: str,
    strict: bool = True,
) -> ExcerptProvenanceResult:
    """Check that all Key Excerpts quotes exist in the transcript.

    Args:
        markdown: Draft markdown with Key Excerpts sections
        transcript: Source transcript text
        strict: If True, FAIL on any missing quote. If False, WARN on ≤1 missing.

    Returns:
        ExcerptProvenanceResult with verdict and details
    """
    quotes = extract_key_excerpts_quotes(markdown)
    transcript_normalized = normalize_for_matching(transcript)

    result = ExcerptProvenanceResult(excerpts_total=len(quotes))

    for quote in quotes:
        match = match_quote_in_transcript(quote, transcript, transcript_normalized)
        result.matches.append(match)

        if match.found:
            result.excerpts_found += 1
        else:
            result.excerpts_not_found += 1
            # Truncate for debugging display
            preview = quote[:80] + "..." if len(quote) > 80 else quote
            result.missing_quotes.append(preview)

    # Calculate provenance rate
    if result.excerpts_total > 0:
        result.provenance_rate = result.excerpts_found / result.excerpts_total
    else:
        result.provenance_rate = 1.0  # No excerpts = vacuously true

    # Determine verdict
    if result.excerpts_not_found == 0:
        result.verdict = "PASS"
    elif not strict and result.excerpts_not_found <= 1:
        result.verdict = "WARN"
    else:
        result.verdict = "FAIL"

    return result


def check_claim_support(
    markdown: str,
    transcript: str,
    strict: bool = True,
) -> ClaimSupportResult:
    """Check that all Core Claims have grounded supporting evidence.

    Args:
        markdown: Draft markdown with Core Claims sections
        transcript: Source transcript text
        strict: If True, FAIL on any missing evidence. If False, WARN on ≤1 missing.

    Returns:
        ClaimSupportResult with verdict and details
    """
    claims = extract_core_claims_with_evidence(markdown)
    transcript_normalized = normalize_for_matching(transcript)

    result = ClaimSupportResult(claims_total=len(claims))

    for claim_title, evidence_quote in claims:
        if not evidence_quote:
            result.claims_missing_evidence += 1
            preview = claim_title[:80] + "..." if len(claim_title) > 80 else claim_title
            result.missing_evidence_claims.append(preview)
            continue

        result.claims_with_evidence += 1

        # Check if evidence quote exists in transcript
        match = match_quote_in_transcript(evidence_quote, transcript, transcript_normalized)

        if match.found:
            result.evidence_quotes_found += 1
        else:
            result.evidence_quotes_not_found += 1
            preview = evidence_quote[:80] + "..." if len(evidence_quote) > 80 else evidence_quote
            result.missing_evidence_quotes.append(preview)

    # Calculate evidence provenance rate
    if result.claims_with_evidence > 0:
        result.evidence_provenance_rate = result.evidence_quotes_found / result.claims_with_evidence
    else:
        result.evidence_provenance_rate = 0.0

    # Determine verdict
    total_issues = result.claims_missing_evidence + result.evidence_quotes_not_found
    if total_issues == 0:
        result.verdict = "PASS"
    elif not strict and total_issues <= 1:
        result.verdict = "WARN"
    else:
        result.verdict = "FAIL"

    return result


def check_groundedness(
    markdown: str,
    transcript: str,
    strict: bool = True,
) -> GroundednessReport:
    """Run full groundedness check on a draft.

    Args:
        markdown: Draft markdown
        transcript: Source transcript
        strict: If True, use strict verdicts

    Returns:
        GroundednessReport with excerpt provenance, claim support, and overall verdict
    """
    excerpt_result = check_excerpt_provenance(markdown, transcript, strict=strict)
    claim_result = check_claim_support(markdown, transcript, strict=strict)

    # Overall verdict: worst of the two
    if excerpt_result.verdict == "FAIL" or claim_result.verdict == "FAIL":
        overall = "FAIL"
    elif excerpt_result.verdict == "WARN" or claim_result.verdict == "WARN":
        overall = "WARN"
    else:
        overall = "PASS"

    return GroundednessReport(
        excerpt_provenance=excerpt_result,
        claim_support=claim_result,
        overall_verdict=overall,
    )


# =============================================================================
# Snap-to-Transcript Repair
# =============================================================================


@dataclass
class TranscriptSpan:
    """A span of text from the transcript."""
    text: str
    start: int
    end: int
    score: float


@dataclass
class ClaimRepairResult:
    """Result of repairing Core Claims evidence."""
    claims_total: int = 0
    claims_repaired: int = 0
    claims_dropped: int = 0
    claims_unchanged: int = 0
    repaired_markdown: str = ""
    repair_details: list = field(default_factory=list)
    drop_details: list = field(default_factory=list)


def find_best_transcript_span(
    evidence: str,
    transcript: str,
    fuzzy_threshold: float = 0.85,
    max_span_words: int = 40,
) -> Optional[TranscriptSpan]:
    """Find the best matching transcript span for an evidence quote.

    Uses sliding window search to find the transcript substring that
    best matches the evidence, then extracts it verbatim.

    Args:
        evidence: The evidence string to match
        transcript: Source transcript text
        fuzzy_threshold: Minimum similarity score to consider a match
        max_span_words: Maximum words to include in returned span

    Returns:
        TranscriptSpan with verbatim text, or None if no good match
    """
    evidence_normalized = normalize_for_matching(evidence)
    transcript_normalized = normalize_for_matching(transcript)

    # Fast path: exact match
    if evidence_normalized in transcript_normalized:
        start = transcript_normalized.find(evidence_normalized)
        # Map back to original transcript (approximate)
        # Find the corresponding position in original text
        original_start = _map_normalized_to_original(transcript, transcript_normalized, start)
        original_end = _map_normalized_to_original(
            transcript, transcript_normalized, start + len(evidence_normalized)
        )
        return TranscriptSpan(
            text=transcript[original_start:original_end].strip(),
            start=original_start,
            end=original_end,
            score=1.0,
        )

    # Sliding window fuzzy match
    window_size = len(evidence_normalized) + 50
    best_score = 0.0
    best_start = None
    best_end = None

    step = max(1, len(transcript_normalized) // 200)  # Finer granularity for repair

    for i in range(0, max(1, len(transcript_normalized) - window_size), step):
        window = transcript_normalized[i:i + window_size]
        ratio = SequenceMatcher(None, evidence_normalized, window).ratio()
        if ratio > best_score:
            best_score = ratio
            best_start = i
            best_end = i + window_size

    if best_score >= fuzzy_threshold and best_start is not None:
        # Map back to original and extract verbatim
        original_start = _map_normalized_to_original(transcript, transcript_normalized, best_start)
        original_end = _map_normalized_to_original(transcript, transcript_normalized, best_end)

        # Trim to sentence boundaries if possible
        span_text = transcript[original_start:original_end].strip()
        span_text = _trim_to_sentence_boundary(span_text, max_words=max_span_words)

        return TranscriptSpan(
            text=span_text,
            start=original_start,
            end=original_end,
            score=best_score,
        )

    return None


def _map_normalized_to_original(original: str, normalized: str, norm_pos: int) -> int:
    """Map a position in normalized text back to original text.

    Uses a simple word-counting approach: count words in normalized up to
    norm_pos, then find that many words in original.
    """
    # Count how many complete words are before norm_pos in normalized
    norm_before = normalized[:norm_pos]
    word_count = len(norm_before.split())

    # Find that many words in original
    words_found = 0
    for i, char in enumerate(original):
        if char.isspace() and i > 0 and not original[i-1].isspace():
            words_found += 1
            if words_found >= word_count:
                return i

    return len(original)


def _trim_to_sentence_boundary(text: str, max_words: int = 40) -> str:
    """Trim text to end at a sentence boundary, respecting max words."""
    words = text.split()
    if len(words) <= max_words:
        return text

    # Take first max_words and try to end at sentence boundary
    truncated = ' '.join(words[:max_words])

    # Find last sentence-ending punctuation
    for end_char in ['.', '!', '?']:
        last_end = truncated.rfind(end_char)
        if last_end > len(truncated) // 2:  # Must be past halfway
            return truncated[:last_end + 1]

    # No good boundary, just return truncated
    return truncated


def repair_core_claims_evidence(
    markdown: str,
    transcript: str,
    fuzzy_threshold: float = 0.85,
    min_claims_per_chapter: int = 2,
) -> ClaimRepairResult:
    """Repair Core Claims evidence by snapping to transcript.

    For each Core Claim with evidence:
    1. Find best transcript span matching the evidence
    2. If score >= threshold: replace evidence with exact transcript text
    3. If score < threshold: drop the claim

    Args:
        markdown: Draft markdown with Core Claims sections
        transcript: Source transcript
        fuzzy_threshold: Minimum score to repair (default 0.85)
        min_claims_per_chapter: Minimum claims to keep per chapter

    Returns:
        ClaimRepairResult with repaired markdown and details
    """
    result = ClaimRepairResult()
    repaired_md = markdown

    # Find all Core Claims sections and their claims
    sections = re.split(r'(^### Core Claims.*?)(?=^### |\Z)', markdown, flags=re.MULTILINE | re.DOTALL)

    claims_processed = []

    for i, section in enumerate(sections):
        if not section.strip().startswith('### Core Claims'):
            continue

        # Find all claims in this section
        claim_pattern = r'(-\s*\*\*(.+?)\*\*:\s*)(["""](.+?)[""])'
        matches = list(re.finditer(claim_pattern, section))

        result.claims_total += len(matches)

        for match in matches:
            full_match = match.group(0)
            claim_prefix = match.group(1)  # "- **Claim title**: "
            claim_title = match.group(2)
            quote_with_quotes = match.group(3)  # '"evidence"'
            evidence = match.group(4)  # 'evidence' (without quotes)

            # Find best transcript span
            span = find_best_transcript_span(evidence, transcript, fuzzy_threshold)

            if span:
                if span.score == 1.0:
                    # Exact match, no repair needed
                    result.claims_unchanged += 1
                else:
                    # Repair: replace evidence with transcript span
                    new_claim = f'{claim_prefix}"{span.text}"'
                    repaired_md = repaired_md.replace(full_match, new_claim, 1)
                    result.claims_repaired += 1
                    result.repair_details.append({
                        'claim': claim_title[:50],
                        'original': evidence[:60],
                        'repaired': span.text[:60],
                        'score': span.score,
                    })
            else:
                # No match found - drop the claim
                # Remove the entire bullet line
                repaired_md = repaired_md.replace(full_match + '\n', '', 1)
                if full_match in repaired_md:  # Fallback if no newline
                    repaired_md = repaired_md.replace(full_match, '', 1)
                result.claims_dropped += 1
                result.drop_details.append({
                    'claim': claim_title[:50],
                    'evidence': evidence[:60],
                    'reason': 'no_transcript_match',
                })

    result.repaired_markdown = repaired_md
    return result


def check_and_repair_groundedness(
    markdown: str,
    transcript: str,
    fuzzy_threshold: float = 0.85,
    min_claims_per_chapter: int = 2,
) -> tuple[GroundednessReport, ClaimRepairResult, str]:
    """Check groundedness and repair Core Claims evidence.

    Policy:
    - Key Excerpts: Hard FAIL if any missing (no repair)
    - Core Claims: Attempt repair via snap-to-transcript
      - If repaired: PASS
      - If dropped but enough claims remain: WARN
      - If too many dropped: FAIL

    Args:
        markdown: Draft markdown
        transcript: Source transcript
        fuzzy_threshold: Minimum score for repair
        min_claims_per_chapter: Minimum claims after repair

    Returns:
        Tuple of (GroundednessReport, ClaimRepairResult, repaired_markdown)
    """
    # First check excerpts (hard gate, no repair)
    excerpt_result = check_excerpt_provenance(markdown, transcript, strict=True)

    # Then repair claims
    repair_result = repair_core_claims_evidence(
        markdown, transcript, fuzzy_threshold, min_claims_per_chapter
    )

    # Re-check claims after repair
    claim_result = check_claim_support(
        repair_result.repaired_markdown, transcript, strict=True
    )

    # Determine verdict
    if excerpt_result.verdict == "FAIL":
        overall = "FAIL"
    elif repair_result.claims_dropped > 0 and claim_result.verdict == "FAIL":
        overall = "FAIL"
    elif repair_result.claims_dropped > 0:
        overall = "WARN"  # Some claims dropped but enough remain
    else:
        overall = "PASS"

    report = GroundednessReport(
        excerpt_provenance=excerpt_result,
        claim_support=claim_result,
        overall_verdict=overall,
    )

    # Emit metrics for observability
    _log_groundedness_metrics(report, repair_result)

    return report, repair_result, repair_result.repaired_markdown


def _log_groundedness_metrics(
    report: GroundednessReport,
    repair_result: ClaimRepairResult,
) -> None:
    """Log groundedness metrics for observability.

    Emits structured log entries for:
    - Excerpt provenance rate
    - Claim repair/drop counts
    - Overall verdict
    """
    ep = report.excerpt_provenance
    cs = report.claim_support

    # Log summary metrics
    logger.info(
        "groundedness_check_complete",
        extra={
            "verdict": report.overall_verdict,
            "excerpts_total": ep.excerpts_total,
            "excerpts_found": ep.excerpts_found,
            "excerpts_missing": ep.excerpts_not_found,
            "excerpt_provenance_rate": ep.provenance_rate,
            "claims_total": repair_result.claims_total,
            "claims_unchanged": repair_result.claims_unchanged,
            "claims_repaired": repair_result.claims_repaired,
            "claims_dropped": repair_result.claims_dropped,
            "claim_provenance_rate": cs.evidence_provenance_rate,
        }
    )

    # Log individual drops for debugging
    if repair_result.claims_dropped > 0:
        for drop in repair_result.drop_details:
            logger.warning(
                "groundedness_claim_dropped",
                extra={
                    "claim": drop.get("claim"),
                    "evidence_sample": drop.get("evidence", "")[:40],
                    "reason": drop.get("reason"),
                }
            )

    # Log repairs for debugging
    if repair_result.claims_repaired > 0:
        for repair in repair_result.repair_details:
            logger.info(
                "groundedness_claim_repaired",
                extra={
                    "claim": repair.get("claim"),
                    "score": repair.get("score"),
                }
            )
