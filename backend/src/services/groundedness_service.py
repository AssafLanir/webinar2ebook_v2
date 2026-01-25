"""Groundedness Harness v1: Quote provenance and claim support validation.

Validates that:
1. Key Excerpts quotes actually exist in the source transcript
2. Core Claims have supporting quotes that exist in the transcript

This catches "invented quotes" and ensures output is grounded in source material.
"""

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Optional


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
