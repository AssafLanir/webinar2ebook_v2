#!/usr/bin/env python3
"""Batch evaluator CLI for Ideas Edition quality metrics.

Runs the Ideas Edition pipeline across a corpus of transcripts and measures:
- Structural pass/fail (required sections present, no quote leaks)
- Yield metrics: sentences generated/kept/dropped
- Fallback usage rate per chapter
- Drop reasons histogram
- Entity retention (org/product names preserved vs person names blocked)
- Final word counts (overall + prose only)

Verdict logic:
- PASS: All invariants pass, metrics within thresholds
- WARN: Invariants pass but some metrics exceed soft thresholds
- FAIL: Structural invariants violated or hard thresholds exceeded

Usage:
    python scripts/batch_eval.py --input_dir corpora/ --edition ideas --out report.json
    python scripts/batch_eval.py --input_dir corpora/ --ci  # CI mode, exits non-zero on FAIL

Run from backend directory:
    python scripts/batch_eval.py --help
"""

import argparse
import json
import os
import re
import sys
from collections import Counter
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from services.draft_service import (
    sanitize_speaker_framing,
    enforce_no_names_in_prose,
    sanitize_meta_discourse,
    DYNAMIC_NAME_POLICY_ENABLED,
)
from services.entity_allowlist import (
    build_person_blacklist,
    build_entity_allowlist,
    PersonBlacklist,
    EntityAllowlist,
)


# =============================================================================
# Thresholds (tune based on calibration)
# =============================================================================

# Hard thresholds (FAIL if exceeded)
HARD_FALLBACK_THRESHOLD = 0.50  # 50% of chapters using fallback
HARD_DROP_RATIO_THRESHOLD = 0.60  # 60% of sentences dropped
HARD_MIN_PROSE_WORDS_PER_CHAPTER = 50  # Absolute minimum

# Soft thresholds (WARN if exceeded)
SOFT_FALLBACK_THRESHOLD = 0.25  # 25% of chapters
SOFT_DROP_RATIO_THRESHOLD = 0.40  # 40% of sentences
SOFT_MIN_PROSE_WORDS_PER_CHAPTER = 120  # Target minimum


class Verdict(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


@dataclass
class ChapterMetrics:
    """Metrics for a single chapter."""
    chapter_index: int
    chapter_title: str = ""
    prose_word_count: int = 0
    prose_sentence_count: int = 0
    sentences_dropped: int = 0
    drop_reasons: dict = field(default_factory=dict)
    has_key_excerpts: bool = False
    has_core_claims: bool = False
    key_excerpt_count: int = 0
    core_claim_count: int = 0
    used_fallback: bool = False
    verdict: str = "PASS"
    issues: list = field(default_factory=list)


@dataclass
class EntityMetrics:
    """Entity retention metrics."""
    # Brand entities (org_names + product_names) - what we care about preserving
    brand_mentions: int = 0
    brand_names_found: list = field(default_factory=list)

    # Acronym entities (ALLCAPS tokens like API, SDK, HIPAA) - diagnostic only
    acronym_mentions: int = 0
    acronym_names_found: list = field(default_factory=list)

    # Person names blocked
    person_mentions_blocked: int = 0
    person_names_blocked: list = field(default_factory=list)

    # Retention ratios (higher is better) - diagnostic, not gating
    brand_retention_ratio: float = 0.0
    total_retention_ratio: float = 0.0


@dataclass
class TranscriptResult:
    """Evaluation result for a single transcript."""
    filename: str
    verdict: str = "PASS"
    failure_causes: list = field(default_factory=list)

    # Structural
    structural_pass: bool = False
    structural_issues: list = field(default_factory=list)

    # Yield metrics
    total_prose_sentences: int = 0
    sentences_dropped: int = 0
    sentences_kept: int = 0
    drop_ratio: float = 0.0

    # Drop reasons histogram
    drop_reasons: dict = field(default_factory=dict)

    # Word counts
    total_word_count: int = 0
    prose_word_count: int = 0
    avg_prose_words_per_chapter: float = 0.0

    # Prose distribution (for future threshold tuning)
    prose_words_per_chapter: list = field(default_factory=list)
    p10_prose_words: float = 0.0
    median_prose_words: float = 0.0

    # Chapter metrics
    chapter_count: int = 0
    chapters_with_fallback: int = 0
    fallback_ratio: float = 0.0
    chapter_metrics: list = field(default_factory=list)

    # Entity metrics
    entity_metrics: dict = field(default_factory=dict)

    # Timing
    eval_time_ms: int = 0

    # Errors
    error: Optional[str] = None


@dataclass
class BatchReport:
    """Batch evaluation report."""
    generated_at: str
    edition: str
    transcript_count: int
    dynamic_name_policy_enabled: bool

    # Overall verdict
    overall_verdict: str = "PASS"

    # Counts by verdict
    pass_count: int = 0
    warn_count: int = 0
    fail_count: int = 0

    # Top failure causes across corpus
    top_failure_causes: dict = field(default_factory=dict)

    # Aggregate metrics
    avg_drop_ratio: float = 0.0
    avg_fallback_ratio: float = 0.0
    avg_prose_words_per_chapter: float = 0.0

    # Prose distribution aggregate (for threshold tuning)
    p10_prose_words: float = 0.0
    median_prose_words: float = 0.0

    # Entity retention aggregate (diagnostic, not gating)
    total_brand_mentions: int = 0
    total_acronym_mentions: int = 0
    total_person_blocked: int = 0

    # Top drop reasons across corpus
    top_drop_reasons: dict = field(default_factory=dict)

    # Per-transcript results (sorted by verdict)
    results: list = field(default_factory=list)


def extract_chapters(markdown: str) -> list[dict]:
    """Extract chapters from markdown draft."""
    chapters = []
    chapter_pattern = re.compile(r'^## Chapter (\d+):?\s*(.*)$', re.MULTILINE)

    matches = list(chapter_pattern.finditer(markdown))
    for i, match in enumerate(matches):
        chapter_num = int(match.group(1))
        title = match.group(2).strip()
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(markdown)
        content = markdown[start:end]

        chapters.append({
            "index": chapter_num - 1,
            "title": title,
            "content": content,
        })

    return chapters


def count_entity_mentions(
    prose: str,
    entity_allowlist: Optional[EntityAllowlist],
    person_blacklist: Optional[PersonBlacklist],
) -> EntityMetrics:
    """Count entity mentions in prose text.

    Splits entities into:
    - brand: org_names + product_names (what we care about preserving)
    - acronym: ALLCAPS tokens like API, SDK (diagnostic only)
    """
    metrics = EntityMetrics()

    if not entity_allowlist and not person_blacklist:
        return metrics

    # Find capitalized words/phrases that might be entities
    entity_pattern = re.compile(r'\b([A-Z][a-zA-Z]*(?:\s+[A-Z][a-zA-Z]*)*)\b')

    found_brands = set()
    found_acronyms = set()
    found_persons = set()

    for match in entity_pattern.finditer(prose):
        candidate = match.group(1)

        # Check if it's an allowlisted entity - split by type
        if entity_allowlist:
            # Check brand entities (org_names + product_names)
            is_org = candidate.lower() in {n.lower() for n in entity_allowlist.org_names}
            is_product = candidate.lower() in {n.lower() for n in entity_allowlist.product_names}
            is_acronym = candidate.upper() in entity_allowlist.acronyms or candidate in entity_allowlist.acronyms

            if is_org or is_product:
                metrics.brand_mentions += 1
                found_brands.add(candidate)
            elif is_acronym:
                metrics.acronym_mentions += 1
                found_acronyms.add(candidate)

        # Check if it would have been blocked as person
        if person_blacklist and person_blacklist.matches(candidate):
            metrics.person_mentions_blocked += 1
            found_persons.add(candidate)

    metrics.brand_names_found = list(found_brands)[:10]
    metrics.acronym_names_found = list(found_acronyms)[:10]
    metrics.person_names_blocked = list(found_persons)[:10]

    # Retention ratios (diagnostic, not gating)
    # Brand retention: brands / (brands + persons)
    brand_total = metrics.brand_mentions + metrics.person_mentions_blocked
    if brand_total > 0:
        metrics.brand_retention_ratio = metrics.brand_mentions / brand_total

    # Total retention: (brands + acronyms) / (brands + acronyms + persons)
    total = metrics.brand_mentions + metrics.acronym_mentions + metrics.person_mentions_blocked
    if total > 0:
        metrics.total_retention_ratio = (metrics.brand_mentions + metrics.acronym_mentions) / total

    return metrics


def analyze_chapter(
    chapter: dict,
    entity_allowlist: Optional[EntityAllowlist] = None,
    person_blacklist: Optional[PersonBlacklist] = None,
) -> ChapterMetrics:
    """Analyze a single chapter for metrics."""
    content = chapter["content"]
    metrics = ChapterMetrics(
        chapter_index=chapter["index"],
        chapter_title=chapter["title"],
    )

    # Check for Key Excerpts
    if "### Key Excerpts" in content:
        metrics.has_key_excerpts = True
        key_excerpts_match = re.search(
            r'### Key Excerpts\s*\n(.*?)(?=### |## |\Z)',
            content,
            re.DOTALL
        )
        if key_excerpts_match:
            excerpt_content = key_excerpts_match.group(1)
            metrics.key_excerpt_count = len(re.findall(r'^>', excerpt_content, re.MULTILINE))

    # Check for Core Claims
    if "### Core Claims" in content:
        metrics.has_core_claims = True
        core_claims_match = re.search(
            r'### Core Claims\s*\n(.*?)(?=### |## |\Z)',
            content,
            re.DOTALL
        )
        if core_claims_match:
            claims_content = core_claims_match.group(1)
            metrics.core_claim_count = len(re.findall(r'^- \*\*', claims_content, re.MULTILINE))
            if "*No fully grounded claims" in claims_content or "*No claims available" in claims_content:
                metrics.used_fallback = True
                metrics.issues.append("used_fallback")

    # Extract prose
    prose_match = re.search(
        r'^## Chapter.*?\n\n(.*?)(?=### Key Excerpts|### Core Claims|\Z)',
        content,
        re.DOTALL
    )
    prose = ""
    if prose_match:
        prose = prose_match.group(1).strip()
        prose = re.sub(r'^#+.*$', '', prose, flags=re.MULTILINE).strip()
        words = prose.split()
        metrics.prose_word_count = len(words)
        sentences = re.split(r'[.!?]+\s*', prose)
        metrics.prose_sentence_count = len([s for s in sentences if s.strip()])

    # Check chapter-level thresholds
    if metrics.prose_word_count < HARD_MIN_PROSE_WORDS_PER_CHAPTER:
        metrics.verdict = "FAIL"
        metrics.issues.append("prose_too_thin")
    elif metrics.prose_word_count < SOFT_MIN_PROSE_WORDS_PER_CHAPTER:
        if metrics.verdict != "FAIL":
            metrics.verdict = "WARN"
        metrics.issues.append("prose_below_target")

    if not metrics.has_key_excerpts:
        metrics.verdict = "FAIL"
        metrics.issues.append("missing_key_excerpts")

    if not metrics.has_core_claims:
        metrics.verdict = "FAIL"
        metrics.issues.append("missing_core_claims")

    return metrics


def check_structural_invariants(markdown: str) -> tuple[bool, list[str]]:
    """Check structural invariants on the draft."""
    issues = []

    # Check for empty Key Excerpts sections
    empty_key_excerpts = re.findall(
        r'### Key Excerpts\s*\n\s*(?=### |## |\Z)',
        markdown
    )
    if empty_key_excerpts:
        issues.append(f"empty_key_excerpts:{len(empty_key_excerpts)}")

    # Check for empty Core Claims sections (without placeholder)
    core_claims_matches = re.finditer(
        r'### Core Claims\s*\n(.*?)(?=### |## |\Z)',
        markdown,
        re.DOTALL
    )
    for match in core_claims_matches:
        content = match.group(1).strip()
        has_bullets = bool(re.search(r'^- \*\*', content, re.MULTILINE))
        has_placeholder = '*No fully grounded claims' in content or '*No claims available' in content
        if not has_bullets and not has_placeholder:
            issues.append("empty_core_claims_no_placeholder")

    # Check for quotes in prose
    chapters = extract_chapters(markdown)
    for chapter in chapters:
        prose_match = re.search(
            r'^## Chapter.*?\n\n(.*?)(?=### Key Excerpts|### Core Claims|\Z)',
            chapter["content"],
            re.DOTALL
        )
        if prose_match:
            prose = prose_match.group(1)
            inline_quotes = re.findall(r'["\u201c][^"\u201d]{10,}["\u201d]', prose)
            if inline_quotes:
                issues.append(f"inline_quotes_ch{chapter['index'] + 1}:{len(inline_quotes)}")

    return len(issues) == 0, issues


def compute_verdict(result: TranscriptResult) -> tuple[str, list[str]]:
    """Compute verdict and failure causes for a transcript result."""
    causes = []

    # P0: Structural invariants
    if not result.structural_pass:
        causes.append("structural_invariant_failed")

    # Hard thresholds → FAIL
    if result.fallback_ratio > HARD_FALLBACK_THRESHOLD:
        causes.append(f"fallback_overuse:{result.fallback_ratio:.0%}")

    if result.drop_ratio > HARD_DROP_RATIO_THRESHOLD:
        causes.append(f"drop_ratio_critical:{result.drop_ratio:.0%}")

    if result.chapter_count > 0:
        if result.avg_prose_words_per_chapter < HARD_MIN_PROSE_WORDS_PER_CHAPTER:
            causes.append(f"prose_critical:{result.avg_prose_words_per_chapter:.0f}w/ch")

    # Any hard failure → FAIL
    if causes:
        return Verdict.FAIL.value, causes

    # Soft thresholds → WARN
    warnings = []
    if result.fallback_ratio > SOFT_FALLBACK_THRESHOLD:
        warnings.append(f"fallback_high:{result.fallback_ratio:.0%}")

    if result.drop_ratio > SOFT_DROP_RATIO_THRESHOLD:
        warnings.append(f"drop_ratio_high:{result.drop_ratio:.0%}")

    if result.chapter_count > 0:
        if result.avg_prose_words_per_chapter < SOFT_MIN_PROSE_WORDS_PER_CHAPTER:
            warnings.append(f"prose_thin:{result.avg_prose_words_per_chapter:.0f}w/ch")

    if warnings:
        return Verdict.WARN.value, warnings

    return Verdict.PASS.value, []


def evaluate_transcript(
    filepath: Path,
    person_blacklist: Optional[PersonBlacklist] = None,
    entity_allowlist: Optional[EntityAllowlist] = None,
) -> TranscriptResult:
    """Evaluate a single transcript/draft file."""
    import time
    start_time = time.time()

    result = TranscriptResult(filename=filepath.name)

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check if it's a draft (has chapter structure)
        if not content.strip().startswith("## Chapter"):
            result.error = "not_a_draft"
            result.verdict = "SKIP"
            return result

        markdown = content

        # Store entity metrics
        if person_blacklist:
            result.entity_metrics["person_blacklist_size"] = len(person_blacklist.full_names)
        if entity_allowlist:
            result.entity_metrics["allowlist_orgs"] = len(entity_allowlist.org_names)
            result.entity_metrics["allowlist_products"] = len(entity_allowlist.product_names)
            result.entity_metrics["allowlist_acronyms"] = len(entity_allowlist.acronyms)

        # Run gates and collect drop metrics
        drop_reasons = Counter()

        # 1. Speaker framing sanitizer
        _, sanitizer_report = sanitize_speaker_framing(markdown)
        for detail in sanitizer_report.get("drop_details", []):
            drop_reasons[detail.get("type", "speaker_framing")] += 1

        # 2. No-names-in-prose invariant
        _, names_report = enforce_no_names_in_prose(
            markdown,
            person_blacklist=person_blacklist,
            entity_allowlist=entity_allowlist,
        )
        for detail in names_report.get("drop_details", []):
            drop_reasons[detail.get("type", "name_in_prose")] += 1

        # 3. Meta-discourse gate
        _, meta_report = sanitize_meta_discourse(markdown)
        for detail in meta_report.get("drop_details", []):
            drop_reasons[detail.get("type", "meta_discourse")] += 1

        # Aggregate drops
        total_dropped = (
            sanitizer_report.get("sentences_dropped", 0) +
            names_report.get("sentences_dropped", 0) +
            meta_report.get("sentences_dropped", 0)
        )
        result.sentences_dropped = total_dropped
        result.drop_reasons = dict(drop_reasons)

        # Structural invariants
        result.structural_pass, result.structural_issues = check_structural_invariants(markdown)

        # Analyze chapters
        chapters = extract_chapters(markdown)
        result.chapter_count = len(chapters)

        total_prose_words = 0
        total_prose_sentences = 0
        fallback_chapters = 0
        all_prose = []
        chapter_prose_counts = []

        for chapter in chapters:
            chapter_metrics = analyze_chapter(chapter, entity_allowlist, person_blacklist)
            result.chapter_metrics.append(asdict(chapter_metrics))
            total_prose_words += chapter_metrics.prose_word_count
            total_prose_sentences += chapter_metrics.prose_sentence_count
            chapter_prose_counts.append(chapter_metrics.prose_word_count)
            if chapter_metrics.used_fallback:
                fallback_chapters += 1

            # Collect prose for entity counting
            prose_match = re.search(
                r'^## Chapter.*?\n\n(.*?)(?=### Key Excerpts|### Core Claims|\Z)',
                chapter["content"],
                re.DOTALL
            )
            if prose_match:
                all_prose.append(prose_match.group(1))

        result.prose_word_count = total_prose_words
        result.total_prose_sentences = total_prose_sentences
        result.sentences_kept = total_prose_sentences
        result.chapters_with_fallback = fallback_chapters
        result.prose_words_per_chapter = chapter_prose_counts

        # Calculate ratios and percentiles
        if result.total_prose_sentences > 0:
            result.drop_ratio = result.sentences_dropped / (result.total_prose_sentences + result.sentences_dropped)
        if result.chapter_count > 0:
            result.fallback_ratio = result.chapters_with_fallback / result.chapter_count
            result.avg_prose_words_per_chapter = result.prose_word_count / result.chapter_count

            # Compute P10 and median for threshold tuning
            sorted_counts = sorted(chapter_prose_counts)
            n = len(sorted_counts)
            # P10: 10th percentile (the weak chapters)
            p10_idx = max(0, int(n * 0.1))
            result.p10_prose_words = float(sorted_counts[p10_idx])
            # Median
            if n % 2 == 0:
                result.median_prose_words = (sorted_counts[n//2 - 1] + sorted_counts[n//2]) / 2.0
            else:
                result.median_prose_words = float(sorted_counts[n//2])

        result.total_word_count = len(markdown.split())

        # Entity retention metrics
        if entity_allowlist or person_blacklist:
            combined_prose = "\n".join(all_prose)
            entity_metrics = count_entity_mentions(combined_prose, entity_allowlist, person_blacklist)
            result.entity_metrics.update(asdict(entity_metrics))

        # Compute verdict
        result.verdict, result.failure_causes = compute_verdict(result)

    except Exception as e:
        result.error = str(e)
        result.verdict = "FAIL"
        result.failure_causes = ["exception:" + str(e)[:50]]

    result.eval_time_ms = int((time.time() - start_time) * 1000)
    return result


def run_batch_evaluation(
    input_dir: Path,
    edition: str,
    output_file: Optional[Path] = None,
) -> BatchReport:
    """Run batch evaluation across all transcripts in directory."""
    report = BatchReport(
        generated_at=datetime.now().isoformat(),
        edition=edition,
        transcript_count=0,
        dynamic_name_policy_enabled=DYNAMIC_NAME_POLICY_ENABLED,
    )

    # Find all transcript files
    transcript_files = list(input_dir.glob("*.txt")) + list(input_dir.glob("*.md"))
    report.transcript_count = len(transcript_files)

    if not transcript_files:
        print(f"No transcript files found in {input_dir}")
        return report

    print(f"Found {len(transcript_files)} file(s) to evaluate")
    print(f"Dynamic name policy: {'ENABLED' if DYNAMIC_NAME_POLICY_ENABLED else 'DISABLED'}")
    print()

    # Build allowlists if dynamic policy enabled
    person_blacklist = PersonBlacklist() if DYNAMIC_NAME_POLICY_ENABLED else None
    entity_allowlist = None

    all_drop_reasons = Counter()
    all_failure_causes = Counter()
    results = []

    for filepath in transcript_files:
        # Build entity allowlist from this transcript if dynamic policy enabled
        if DYNAMIC_NAME_POLICY_ENABLED:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    transcript_text = f.read()
                entity_allowlist = build_entity_allowlist(transcript_text, person_blacklist)
            except Exception:
                entity_allowlist = None

        result = evaluate_transcript(filepath, person_blacklist, entity_allowlist)
        results.append(result)

        # Update counters
        if result.verdict == "PASS":
            report.pass_count += 1
        elif result.verdict == "WARN":
            report.warn_count += 1
        elif result.verdict == "FAIL":
            report.fail_count += 1

        all_drop_reasons.update(result.drop_reasons)
        for cause in result.failure_causes:
            all_failure_causes[cause.split(":")[0]] += 1

        # Aggregate entity metrics (split by type)
        if result.entity_metrics:
            report.total_brand_mentions += result.entity_metrics.get("brand_mentions", 0)
            report.total_acronym_mentions += result.entity_metrics.get("acronym_mentions", 0)
            report.total_person_blocked += result.entity_metrics.get("person_mentions_blocked", 0)

    # Sort results: FAIL first, then WARN, then PASS
    verdict_order = {"FAIL": 0, "WARN": 1, "PASS": 2, "SKIP": 3}
    results.sort(key=lambda r: (verdict_order.get(r.verdict, 4), -r.drop_ratio))
    report.results = [asdict(r) for r in results]

    # Aggregate metrics
    valid_results = [r for r in results if r.verdict != "SKIP" and not r.error]
    if valid_results:
        report.avg_drop_ratio = sum(r.drop_ratio for r in valid_results) / len(valid_results)
        report.avg_fallback_ratio = sum(r.fallback_ratio for r in valid_results) / len(valid_results)
        report.avg_prose_words_per_chapter = sum(
            r.avg_prose_words_per_chapter for r in valid_results
        ) / len(valid_results)

        # Aggregate prose percentiles across all chapters
        all_chapter_prose = []
        for r in valid_results:
            all_chapter_prose.extend(r.prose_words_per_chapter)
        if all_chapter_prose:
            sorted_prose = sorted(all_chapter_prose)
            n = len(sorted_prose)
            p10_idx = max(0, int(n * 0.1))
            report.p10_prose_words = float(sorted_prose[p10_idx])
            if n % 2 == 0:
                report.median_prose_words = (sorted_prose[n//2 - 1] + sorted_prose[n//2]) / 2.0
            else:
                report.median_prose_words = float(sorted_prose[n//2])

    report.top_drop_reasons = dict(all_drop_reasons.most_common(10))
    report.top_failure_causes = dict(all_failure_causes.most_common(5))

    # Overall verdict
    if report.fail_count > 0:
        report.overall_verdict = "FAIL"
    elif report.warn_count > 0:
        report.overall_verdict = "WARN"
    else:
        report.overall_verdict = "PASS"

    # Write output
    if output_file:
        with open(output_file, 'w') as f:
            json.dump(asdict(report), f, indent=2)
        print(f"Report written to: {output_file}")

    return report


def print_table(report: BatchReport) -> None:
    """Print compact results table sorted by worst offenders."""
    print("\n" + "=" * 80)
    print(" RESULTS TABLE (sorted by verdict, then drop ratio)")
    print("=" * 80)

    # Header
    print(f"{'FILE':<30} {'VERDICT':<6} {'DROP%':<7} {'FALLBACK%':<10} {'W/CH':<6} {'CAUSES'}")
    print("-" * 80)

    for result in report.results:
        if result.get("error") and result.get("verdict") == "SKIP":
            print(f"{result['filename']:<30} {'SKIP':<6} {'--':<7} {'--':<10} {'--':<6} {result.get('error', '')}")
            continue

        causes = ", ".join(result.get("failure_causes", [])[:2]) or "-"
        print(
            f"{result['filename']:<30} "
            f"{result['verdict']:<6} "
            f"{result['drop_ratio']*100:>5.1f}% "
            f"{result['fallback_ratio']*100:>8.1f}% "
            f"{result['avg_prose_words_per_chapter']:>5.0f} "
            f"{causes}"
        )

    print("-" * 80)


def print_summary(report: BatchReport) -> None:
    """Print human-readable summary."""
    print("\n" + "=" * 80)
    print(f" BATCH EVALUATION SUMMARY - {report.overall_verdict}")
    print("=" * 80)

    print(f"\nEdition: {report.edition}")
    print(f"Files evaluated: {report.transcript_count}")
    print(f"Dynamic name policy: {'ENABLED' if report.dynamic_name_policy_enabled else 'DISABLED'}")

    print(f"\n--- Verdicts ---")
    print(f"  PASS: {report.pass_count}")
    print(f"  WARN: {report.warn_count}")
    print(f"  FAIL: {report.fail_count}")

    print(f"\n--- Aggregate Metrics ---")
    print(f"  Avg drop ratio: {report.avg_drop_ratio:.1%}")
    print(f"  Avg fallback ratio: {report.avg_fallback_ratio:.1%}")
    print(f"  Avg prose words/chapter: {report.avg_prose_words_per_chapter:.0f}")

    print(f"\n--- Prose Distribution (for threshold tuning) ---")
    print(f"  P10 prose words/chapter: {report.p10_prose_words:.0f}")
    print(f"  Median prose words/chapter: {report.median_prose_words:.0f}")

    if report.dynamic_name_policy_enabled:
        print(f"\n--- Entity Retention (diagnostic, not gating) ---")
        print(f"  Brand mentions kept: {report.total_brand_mentions}")
        print(f"  Acronym mentions kept: {report.total_acronym_mentions}")
        print(f"  Person mentions blocked: {report.total_person_blocked}")
        total_kept = report.total_brand_mentions + report.total_acronym_mentions
        total = total_kept + report.total_person_blocked
        if total > 0:
            print(f"  Total retention: {total_kept / total:.1%}")

    if report.top_failure_causes:
        print(f"\n--- Top Failure Causes ---")
        for cause, count in report.top_failure_causes.items():
            print(f"  {cause}: {count}")

    if report.top_drop_reasons:
        print(f"\n--- Top Drop Reasons ---")
        for reason, count in list(report.top_drop_reasons.items())[:5]:
            print(f"  {reason}: {count}")

    print("\n" + "=" * 80)

    # Final verdict message
    if report.overall_verdict == "PASS":
        print("✅ All transcripts passed - safe to ship")
    elif report.overall_verdict == "WARN":
        print("⚠️  Some warnings - review before shipping")
    else:
        print("❌ Failures detected - do not ship until fixed")

    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(
        description="Batch evaluator for Ideas Edition quality metrics"
    )
    parser.add_argument(
        "--input_dir",
        type=Path,
        default=Path("corpora"),
        help="Directory containing transcript/draft files (default: corpora/)"
    )
    parser.add_argument(
        "--edition",
        choices=["ideas", "qa"],
        default="ideas",
        help="Edition type to evaluate (default: ideas)"
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output JSON report file (optional)"
    )
    parser.add_argument(
        "--ci",
        action="store_true",
        help="CI mode: exit non-zero on any FAIL verdict"
    )
    parser.add_argument(
        "--table-only",
        action="store_true",
        help="Only print results table, skip detailed summary"
    )

    args = parser.parse_args()

    if not args.input_dir.exists():
        print(f"Error: Input directory {args.input_dir} does not exist")
        return 1

    report = run_batch_evaluation(
        args.input_dir,
        args.edition,
        args.out,
    )

    print_table(report)

    if not args.table_only:
        print_summary(report)

    # CI mode: exit with error if any FAILs
    if args.ci and report.fail_count > 0:
        print(f"\n❌ CI check failed: {report.fail_count} transcript(s) failed")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
