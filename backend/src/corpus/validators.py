"""Validators for corpus runner work units.

Produces the per-transcript output files:
- structure.json: Ideas Edition contract validation
- groundedness.json: Quote provenance validation
- yield.json: Quality metrics (diagnostic)
- gate_row.json: Rollout gate summary

All validators are deterministic and always re-run (not cached).
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field, asdict
from typing import Optional

from .thresholds import Thresholds, DEFAULT_THRESHOLDS


# =============================================================================
# Structure Validation (Ideas Edition Contract)
# =============================================================================


@dataclass
class ChapterStructure:
    """Structure info for a single chapter."""
    n: int
    title: str
    has_key_excerpts: bool
    has_core_claims: bool
    excerpt_count: int
    claim_count: int

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class StructureResult:
    """Result of Ideas Edition structure validation."""
    verdict: str = "PASS"
    violations: list[str] = field(default_factory=list)

    # Contract checks
    has_chapter_structure: bool = False
    has_key_excerpts: bool = False
    has_core_claims: bool = False
    has_interview_leakage: bool = False

    # Counts
    chapter_count: int = 0
    key_excerpt_count: int = 0
    core_claim_count: int = 0

    # Per-chapter detail
    chapters: list[ChapterStructure] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["chapters"] = [c.to_dict() if isinstance(c, ChapterStructure) else c for c in self.chapters]
        return d


def validate_structure(draft_md: str) -> StructureResult:
    """Validate Ideas Edition structure contract.

    Checks:
    1. Has ## Chapter N: structure
    2. Has ### Key Excerpts sections
    3. Has ### Core Claims sections
    4. No interview template leakage

    Returns:
        StructureResult with verdict and per-chapter details
    """
    result = StructureResult()

    # 1. Check chapter structure
    chapter_pattern = re.compile(r'^## Chapter (\d+):\s*(.*)$', re.MULTILINE)
    chapter_matches = list(chapter_pattern.finditer(draft_md))

    result.has_chapter_structure = len(chapter_matches) > 0
    result.chapter_count = len(chapter_matches)

    if not result.has_chapter_structure:
        result.violations.append("Missing chapter structure (## Chapter N:)")

    # 2. Extract per-chapter info
    for i, match in enumerate(chapter_matches):
        chapter_num = int(match.group(1))
        title = match.group(2).strip()
        start = match.start()
        end = chapter_matches[i + 1].start() if i + 1 < len(chapter_matches) else len(draft_md)
        chapter_content = draft_md[start:end]

        # Count Key Excerpts in this chapter
        has_excerpts = "### Key Excerpts" in chapter_content
        excerpt_count = len(re.findall(r'>\s*["""].+?["""]', chapter_content, re.DOTALL))

        # Count Core Claims in this chapter
        has_claims = "### Core Claims" in chapter_content
        # Pattern: - **Label:** or - **Label**: (colon inside or outside bold)
        claim_count = len(re.findall(r'-\s*\*\*[^*]+(?::\*\*|\*\*:)', chapter_content))

        result.chapters.append(ChapterStructure(
            n=chapter_num,
            title=title,
            has_key_excerpts=has_excerpts,
            has_core_claims=has_claims,
            excerpt_count=excerpt_count,
            claim_count=claim_count,
        ))

        if not has_excerpts:
            result.violations.append(f"Chapter {chapter_num} missing Key Excerpts")
        if not has_claims:
            result.violations.append(f"Chapter {chapter_num} missing Core Claims")

    # 3. Global counts
    result.has_key_excerpts = "### Key Excerpts" in draft_md
    result.has_core_claims = "### Core Claims" in draft_md
    result.key_excerpt_count = sum(c.excerpt_count for c in result.chapters)
    result.core_claim_count = sum(c.claim_count for c in result.chapters)

    if not result.has_key_excerpts:
        result.violations.append("No Key Excerpts sections found")
    if not result.has_core_claims:
        result.violations.append("No Core Claims sections found")

    # 4. Check for interview template leakage
    leakage_patterns = [
        (r'\*Format:\*\s*Interview', "Interview format marker (*Format:* Interview)"),
        (r'### The Conversation', "Interview conversation header (### The Conversation)"),
        (r'(?m)^\*Interviewer:\*', "Interview template leakage (*Interviewer:*)"),
        (r'### Key Ideas \(Grounded\)', "Interview Key Ideas section"),
    ]

    for pattern, description in leakage_patterns:
        if re.search(pattern, draft_md):
            result.has_interview_leakage = True
            result.violations.append(description)

    # Determine verdict
    if result.violations:
        result.verdict = "FAIL"
    else:
        result.verdict = "PASS"

    return result


# =============================================================================
# Groundedness Validation (Quote Provenance)
# =============================================================================


@dataclass
class GroundednessResult:
    """Result of groundedness validation."""
    overall_verdict: str = "PASS"

    # Excerpt provenance
    excerpt_provenance: dict = field(default_factory=dict)

    # Claim support
    claim_support: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def run_groundedness(draft_md: str, transcript: str, strict: bool = True) -> GroundednessResult:
    """Run groundedness validation using existing service.

    Wraps groundedness_service.check_groundedness() to produce groundedness.json.

    Args:
        draft_md: Draft markdown
        transcript: Source transcript text
        strict: If True, FAIL on any missing quote

    Returns:
        GroundednessResult with verdict and details
    """
    from services.groundedness_service import check_groundedness, GroundednessReport

    report = check_groundedness(draft_md, transcript, strict=strict)

    return GroundednessResult(
        overall_verdict=report.overall_verdict,
        excerpt_provenance={
            "excerpts_total": report.excerpt_provenance.excerpts_total,
            "excerpts_found": report.excerpt_provenance.excerpts_found,
            "excerpts_not_found": report.excerpt_provenance.excerpts_not_found,
            "provenance_rate": report.excerpt_provenance.provenance_rate,
            "missing_quotes": report.excerpt_provenance.missing_quotes,
            "verdict": report.excerpt_provenance.verdict,
        },
        claim_support={
            "claims_total": report.claim_support.claims_total,
            "claims_with_evidence": report.claim_support.claims_with_evidence,
            "claims_missing_evidence": report.claim_support.claims_missing_evidence,
            "evidence_quotes_found": report.claim_support.evidence_quotes_found,
            "evidence_quotes_not_found": report.claim_support.evidence_quotes_not_found,
            "evidence_provenance_rate": report.claim_support.evidence_provenance_rate,
            "missing_evidence_quotes": report.claim_support.missing_evidence_quotes,
            "verdict": report.claim_support.verdict,
        },
    )


# =============================================================================
# Yield Metrics (Quality / Diagnostic)
# =============================================================================


@dataclass
class YieldResult:
    """Quality metrics for a draft (diagnostic, not gating)."""
    # Word counts
    total_word_count: int = 0
    prose_word_count: int = 0
    chapter_count: int = 0
    avg_prose_words_per_chapter: float = 0.0
    prose_words_per_chapter: list[int] = field(default_factory=list)
    p10_prose_words: float = 0.0
    median_prose_words: float = 0.0

    # Fallback usage
    chapters_with_fallback: int = 0
    fallback_ratio: float = 0.0

    # Drop metrics
    drop_ratio: float = 0.0
    drop_reasons: dict = field(default_factory=dict)

    # Entity metrics
    entity_metrics: dict = field(default_factory=dict)

    # Preflight
    preflight_verdict: str = "PASS"

    def to_dict(self) -> dict:
        return asdict(self)


def _extract_prose_sections(draft_md: str) -> list[str]:
    """Extract prose sections (excluding blockquotes, claims, headers)."""
    lines = draft_md.split('\n')
    prose_lines = []

    for line in lines:
        stripped = line.strip()
        # Skip headers
        if stripped.startswith('#'):
            continue
        # Skip blockquotes
        if stripped.startswith('>'):
            continue
        # Skip claim bullets
        if re.match(r'^-\s*\*\*', stripped):
            continue
        # Skip empty lines
        if not stripped:
            continue
        prose_lines.append(stripped)

    return prose_lines


def _count_words(text: str) -> int:
    """Count words in text."""
    return len(text.split())


def _extract_chapter_prose_words(draft_md: str) -> list[int]:
    """Extract prose word count per chapter."""
    chapter_pattern = re.compile(r'^## Chapter \d+:', re.MULTILINE)
    chapter_starts = [m.start() for m in chapter_pattern.finditer(draft_md)]

    if not chapter_starts:
        return []

    prose_words = []
    for i, start in enumerate(chapter_starts):
        end = chapter_starts[i + 1] if i + 1 < len(chapter_starts) else len(draft_md)
        chapter_content = draft_md[start:end]
        prose_lines = _extract_prose_sections(chapter_content)
        prose_text = ' '.join(prose_lines)
        prose_words.append(_count_words(prose_text))

    return prose_words


def _detect_fallback_markers(draft_md: str) -> int:
    """Count chapters that used fallback generation.

    Fallback markers are internal indicators that the pipeline
    fell back to simpler generation due to insufficient evidence.
    """
    # Common fallback indicators (adjust based on actual pipeline markers)
    fallback_patterns = [
        r'\[FALLBACK\]',
        r'<!-- fallback -->',
        r'<!-- insufficient_evidence -->',
    ]

    chapter_pattern = re.compile(r'^## Chapter \d+:', re.MULTILINE)
    chapter_starts = [m.start() for m in chapter_pattern.finditer(draft_md)]

    if not chapter_starts:
        return 0

    fallback_count = 0
    for i, start in enumerate(chapter_starts):
        end = chapter_starts[i + 1] if i + 1 < len(chapter_starts) else len(draft_md)
        chapter_content = draft_md[start:end]

        for pattern in fallback_patterns:
            if re.search(pattern, chapter_content, re.IGNORECASE):
                fallback_count += 1
                break

    return fallback_count


def compute_yield(
    draft_md: str,
    transcript: str,
    structure: StructureResult,
    groundedness: GroundednessResult,
) -> YieldResult:
    """Compute yield/quality metrics for a draft.

    Args:
        draft_md: Draft markdown
        transcript: Source transcript text
        structure: Structure validation result
        groundedness: Groundedness validation result

    Returns:
        YieldResult with quality metrics
    """
    result = YieldResult()

    # Word counts
    result.total_word_count = _count_words(draft_md)
    prose_lines = _extract_prose_sections(draft_md)
    result.prose_word_count = _count_words(' '.join(prose_lines))

    # Per-chapter prose
    result.prose_words_per_chapter = _extract_chapter_prose_words(draft_md)
    result.chapter_count = len(result.prose_words_per_chapter)

    if result.chapter_count > 0:
        result.avg_prose_words_per_chapter = result.prose_word_count / result.chapter_count

        # p10 and median
        sorted_words = sorted(result.prose_words_per_chapter)
        p10_index = max(0, int(len(sorted_words) * 0.1))
        result.p10_prose_words = float(sorted_words[p10_index]) if sorted_words else 0.0
        result.median_prose_words = float(statistics.median(sorted_words)) if sorted_words else 0.0

    # Fallback usage
    result.chapters_with_fallback = _detect_fallback_markers(draft_md)
    if result.chapter_count > 0:
        result.fallback_ratio = result.chapters_with_fallback / result.chapter_count

    # Drop ratio (estimated from structure - claims without evidence)
    claims_total = groundedness.claim_support.get("claims_total", 0)
    claims_missing = groundedness.claim_support.get("claims_missing_evidence", 0)
    evidence_missing = groundedness.claim_support.get("evidence_quotes_not_found", 0)

    if claims_total > 0:
        result.drop_ratio = (claims_missing + evidence_missing) / claims_total
        result.drop_reasons = {
            "missing_evidence": claims_missing,
            "ungrounded_quotes": evidence_missing,
        }

    # Entity metrics (placeholder - would need entity service)
    result.entity_metrics = {
        "brand_mentions": 0,
        "acronym_mentions": 0,
        "person_mentions_blocked": 0,
    }

    return result


# =============================================================================
# Gate Row (Verdict + Metrics Summary)
# =============================================================================


@dataclass
class GateRow:
    """Rollout gate summary for a single transcript."""
    run_id: str
    transcript_id: str
    candidate_index: int
    content_mode: str

    # Verdicts
    verdict: str = "PASS"
    structure_verdict: str = "PASS"
    groundedness_verdict: str = "PASS"

    # Key metrics
    excerpt_provenance_rate: float = 0.0
    claim_provenance_rate: float = 0.0
    fallback_ratio: float = 0.0
    p10_prose_words: float = 0.0

    # Failure info
    failure_causes: list[str] = field(default_factory=list)

    # Error (if generation failed)
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


def make_gate_row(
    run_id: str,
    transcript_id: str,
    candidate_index: int,
    content_mode: str,
    structure: StructureResult,
    groundedness: GroundednessResult,
    yield_result: YieldResult,
    thresholds: Thresholds = DEFAULT_THRESHOLDS,
) -> GateRow:
    """Compute gate row with explicit verdict precedence.

    Verdict precedence:
    1. Structure FAIL → overall FAIL
    2. Groundedness FAIL → overall FAIL
    3. WARN thresholds hit → overall WARN
    4. Otherwise → PASS

    Args:
        run_id: Unique run identifier
        transcript_id: Transcript ID
        candidate_index: Candidate index (for multi-candidate runs)
        content_mode: Content mode used
        structure: Structure validation result
        groundedness: Groundedness validation result
        yield_result: Yield metrics result
        thresholds: Threshold configuration

    Returns:
        GateRow with verdict and metrics
    """
    row = GateRow(
        run_id=run_id,
        transcript_id=transcript_id,
        candidate_index=candidate_index,
        content_mode=content_mode,
        structure_verdict=structure.verdict,
        groundedness_verdict=groundedness.overall_verdict,
        excerpt_provenance_rate=groundedness.excerpt_provenance.get("provenance_rate", 0.0),
        claim_provenance_rate=groundedness.claim_support.get("evidence_provenance_rate", 0.0),
        fallback_ratio=yield_result.fallback_ratio,
        p10_prose_words=yield_result.p10_prose_words,
    )

    failure_causes = []

    # 1. Structure failures are fatal
    if structure.verdict == "FAIL":
        failure_causes.append("structure_fail")

    # 2. Groundedness failures are fatal
    if groundedness.overall_verdict == "FAIL":
        failure_causes.append("groundedness_fail")

    # 3. Check WARN thresholds
    warn_causes = []
    if yield_result.fallback_ratio > thresholds.warn_fallback_ratio:
        warn_causes.append("high_fallback")
    if yield_result.p10_prose_words < thresholds.warn_min_p10_prose:
        warn_causes.append("low_prose")
    if row.excerpt_provenance_rate < thresholds.warn_excerpt_provenance:
        warn_causes.append("missing_excerpts")
    if row.claim_provenance_rate < thresholds.warn_claim_provenance:
        warn_causes.append("missing_evidence")

    # Determine overall verdict
    if failure_causes:
        row.verdict = "FAIL"
        row.failure_causes = failure_causes
    elif warn_causes:
        row.verdict = "WARN"
        row.failure_causes = warn_causes
    else:
        row.verdict = "PASS"
        row.failure_causes = []

    return row


def make_failure_gate_row(
    run_id: str,
    transcript_id: str,
    candidate_index: int,
    content_mode: str,
    error: str,
    error_code: str,
) -> GateRow:
    """Create a FAIL gate row for generation failures.

    Args:
        run_id: Unique run identifier
        transcript_id: Transcript ID
        candidate_index: Candidate index
        content_mode: Content mode used
        error: Error message
        error_code: Error code

    Returns:
        GateRow with FAIL verdict
    """
    return GateRow(
        run_id=run_id,
        transcript_id=transcript_id,
        candidate_index=candidate_index,
        content_mode=content_mode,
        verdict="FAIL",
        structure_verdict="FAIL",
        groundedness_verdict="FAIL",
        failure_causes=[error_code],
        error=error,
    )
