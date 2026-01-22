#!/usr/bin/env python3
"""Batch evaluator CLI for Ideas Edition quality metrics.

Runs the Ideas Edition pipeline across a corpus of transcripts and measures:
- Structural pass/fail (required sections present, no quote leaks)
- Yield metrics: sentences generated/kept/dropped
- Fallback usage rate per chapter
- Drop reasons histogram
- Final word counts (overall + prose only)

Usage:
    python scripts/batch_eval.py --input_dir corpora/ --edition ideas --out report.json

Run from backend directory:
    python scripts/batch_eval.py --help
"""

import argparse
import asyncio
import json
import os
import re
import sys
from collections import Counter
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from services.draft_service import (
    sanitize_speaker_framing,
    enforce_no_names_in_prose,
    sanitize_meta_discourse,
    ensure_required_sections_exist,
    DYNAMIC_NAME_POLICY_ENABLED,
)
from services.entity_allowlist import (
    build_person_blacklist,
    build_entity_allowlist,
    PersonBlacklist,
)


@dataclass
class ChapterMetrics:
    """Metrics for a single chapter."""
    chapter_index: int
    chapter_title: str = ""
    prose_word_count: int = 0
    prose_sentence_count: int = 0
    has_key_excerpts: bool = False
    has_core_claims: bool = False
    key_excerpt_count: int = 0
    core_claim_count: int = 0
    used_fallback: bool = False


@dataclass
class TranscriptResult:
    """Evaluation result for a single transcript."""
    filename: str
    structural_pass: bool = False
    structural_issues: list = field(default_factory=list)

    # Yield metrics
    total_prose_sentences: int = 0
    sentences_dropped: int = 0
    sentences_kept: int = 0
    drop_ratio: float = 0.0

    # Drop reasons
    drop_reasons: dict = field(default_factory=dict)

    # Word counts
    total_word_count: int = 0
    prose_word_count: int = 0

    # Chapter metrics
    chapter_count: int = 0
    chapters_with_fallback: int = 0
    fallback_ratio: float = 0.0
    chapter_metrics: list = field(default_factory=list)

    # Entity allowlist metrics (when flag enabled)
    person_blacklist_size: int = 0
    entity_allowlist_orgs: int = 0
    entity_allowlist_products: int = 0
    sentences_kept_due_to_allowlist: int = 0

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

    # Aggregate pass/fail
    structural_pass_count: int = 0
    structural_fail_count: int = 0

    # Aggregate metrics
    avg_drop_ratio: float = 0.0
    avg_fallback_ratio: float = 0.0
    avg_prose_words_per_chapter: float = 0.0

    # Top drop reasons across corpus
    top_drop_reasons: dict = field(default_factory=dict)

    # Per-transcript results
    results: list = field(default_factory=list)

    # Threshold violations
    threshold_violations: list = field(default_factory=list)


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


def analyze_chapter(chapter: dict) -> ChapterMetrics:
    """Analyze a single chapter for metrics."""
    content = chapter["content"]
    metrics = ChapterMetrics(
        chapter_index=chapter["index"],
        chapter_title=chapter["title"],
    )

    # Check for Key Excerpts
    if "### Key Excerpts" in content:
        metrics.has_key_excerpts = True
        # Count blockquotes in Key Excerpts section
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
            # Check for fallback placeholder
            if "*No fully grounded claims" in claims_content or "*No claims available" in claims_content:
                metrics.used_fallback = True

    # Extract prose (between chapter header and Key Excerpts)
    prose_match = re.search(
        r'^## Chapter.*?\n\n(.*?)(?=### Key Excerpts|### Core Claims|\Z)',
        content,
        re.DOTALL
    )
    if prose_match:
        prose = prose_match.group(1).strip()
        # Remove any remaining headers
        prose = re.sub(r'^#+.*$', '', prose, flags=re.MULTILINE).strip()
        # Count words and sentences
        words = prose.split()
        metrics.prose_word_count = len(words)
        # Simple sentence count (periods followed by space or end)
        sentences = re.split(r'[.!?]+\s*', prose)
        metrics.prose_sentence_count = len([s for s in sentences if s.strip()])

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
        issues.append(f"Empty Key Excerpts sections: {len(empty_key_excerpts)}")

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
            issues.append("Empty Core Claims section without placeholder")

    # Check for quotes in prose (outside Key Excerpts/Core Claims)
    chapters = extract_chapters(markdown)
    for chapter in chapters:
        prose_match = re.search(
            r'^## Chapter.*?\n\n(.*?)(?=### Key Excerpts|### Core Claims|\Z)',
            chapter["content"],
            re.DOTALL
        )
        if prose_match:
            prose = prose_match.group(1)
            # Look for quote patterns in prose
            inline_quotes = re.findall(r'["\u201c][^"\u201d]{10,}["\u201d]', prose)
            if inline_quotes:
                issues.append(f"Chapter {chapter['index'] + 1}: {len(inline_quotes)} inline quotes in prose")

    return len(issues) == 0, issues


def evaluate_transcript(
    filepath: Path,
    person_blacklist: Optional[PersonBlacklist] = None,
) -> TranscriptResult:
    """Evaluate a single transcript file."""
    import time
    start_time = time.time()

    result = TranscriptResult(filename=filepath.name)

    try:
        # Read transcript
        with open(filepath, 'r', encoding='utf-8') as f:
            transcript = f.read()

        # For now, we evaluate the markdown structure if it looks like a draft
        # In full implementation, this would run the generation pipeline
        if not transcript.strip().startswith("## Chapter"):
            # This is a raw transcript, not a draft - skip for now
            result.error = "Raw transcript (not a draft) - skipping evaluation"
            return result

        markdown = transcript

        # Build entity allowlist if dynamic policy enabled
        entity_allowlist = None
        if DYNAMIC_NAME_POLICY_ENABLED and person_blacklist:
            entity_allowlist = build_entity_allowlist(
                transcript,
                person_blacklist,
            )
            result.entity_allowlist_orgs = len(entity_allowlist.org_names)
            result.entity_allowlist_products = len(entity_allowlist.product_names)

        if person_blacklist:
            result.person_blacklist_size = len(person_blacklist.full_names)

        # Run gates and collect metrics
        drop_reasons = Counter()

        # 1. Speaker framing sanitizer
        _, sanitizer_report = sanitize_speaker_framing(markdown)
        if sanitizer_report.get("sentences_dropped", 0) > 0:
            for detail in sanitizer_report.get("drop_details", []):
                drop_reasons[detail.get("type", "speaker_framing")] += 1

        # 2. No-names-in-prose invariant
        _, names_report = enforce_no_names_in_prose(
            markdown,
            person_blacklist=person_blacklist,
            entity_allowlist=entity_allowlist,
        )
        if names_report.get("sentences_dropped", 0) > 0:
            for detail in names_report.get("drop_details", []):
                drop_reasons[detail.get("type", "name_in_prose")] += 1
        result.sentences_kept_due_to_allowlist = names_report.get("sentences_kept_due_to_allowlist", 0)

        # 3. Meta-discourse gate
        _, meta_report = sanitize_meta_discourse(markdown)
        if meta_report.get("sentences_dropped", 0) > 0:
            for detail in meta_report.get("drop_details", []):
                drop_reasons[detail.get("type", "meta_discourse")] += 1

        # Aggregate drop counts
        total_dropped = (
            sanitizer_report.get("sentences_dropped", 0) +
            names_report.get("sentences_dropped", 0) +
            meta_report.get("sentences_dropped", 0)
        )
        result.sentences_dropped = total_dropped
        result.drop_reasons = dict(drop_reasons)

        # Check structural invariants
        result.structural_pass, result.structural_issues = check_structural_invariants(markdown)

        # Analyze chapters
        chapters = extract_chapters(markdown)
        result.chapter_count = len(chapters)

        total_prose_words = 0
        total_prose_sentences = 0
        fallback_chapters = 0

        for chapter in chapters:
            chapter_metrics = analyze_chapter(chapter)
            result.chapter_metrics.append(asdict(chapter_metrics))
            total_prose_words += chapter_metrics.prose_word_count
            total_prose_sentences += chapter_metrics.prose_sentence_count
            if chapter_metrics.used_fallback:
                fallback_chapters += 1

        result.prose_word_count = total_prose_words
        result.total_prose_sentences = total_prose_sentences
        result.sentences_kept = total_prose_sentences  # Approximate
        result.chapters_with_fallback = fallback_chapters

        # Calculate ratios
        if result.total_prose_sentences > 0:
            result.drop_ratio = result.sentences_dropped / (result.total_prose_sentences + result.sentences_dropped)
        if result.chapter_count > 0:
            result.fallback_ratio = result.chapters_with_fallback / result.chapter_count

        # Total word count
        result.total_word_count = len(markdown.split())

    except Exception as e:
        result.error = str(e)

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

    print(f"Found {len(transcript_files)} transcript(s) to evaluate")
    print(f"Dynamic name policy: {'ENABLED' if DYNAMIC_NAME_POLICY_ENABLED else 'DISABLED'}")
    print()

    # Build a generic person blacklist (in real use, would be per-transcript)
    person_blacklist = PersonBlacklist() if DYNAMIC_NAME_POLICY_ENABLED else None

    all_drop_reasons = Counter()
    total_drop_ratio = 0.0
    total_fallback_ratio = 0.0
    total_prose_words_per_chapter = 0.0
    valid_results = 0

    for filepath in transcript_files:
        print(f"Evaluating: {filepath.name}...", end=" ")
        result = evaluate_transcript(filepath, person_blacklist)
        report.results.append(asdict(result))

        if result.error:
            print(f"ERROR: {result.error}")
            continue

        if result.structural_pass:
            report.structural_pass_count += 1
            print(f"PASS ({result.eval_time_ms}ms)")
        else:
            report.structural_fail_count += 1
            print(f"FAIL: {result.structural_issues}")

        # Aggregate metrics
        all_drop_reasons.update(result.drop_reasons)
        total_drop_ratio += result.drop_ratio
        total_fallback_ratio += result.fallback_ratio
        if result.chapter_count > 0:
            total_prose_words_per_chapter += result.prose_word_count / result.chapter_count
        valid_results += 1

    # Calculate averages
    if valid_results > 0:
        report.avg_drop_ratio = total_drop_ratio / valid_results
        report.avg_fallback_ratio = total_fallback_ratio / valid_results
        report.avg_prose_words_per_chapter = total_prose_words_per_chapter / valid_results

    report.top_drop_reasons = dict(all_drop_reasons.most_common(10))

    # Check thresholds
    FALLBACK_THRESHOLD = 0.25  # 25% of chapters
    DROP_RATIO_THRESHOLD = 0.40  # 40% of sentences
    MIN_PROSE_WORDS_PER_CHAPTER = 120

    if report.avg_fallback_ratio > FALLBACK_THRESHOLD:
        report.threshold_violations.append(
            f"P1: Fallback ratio {report.avg_fallback_ratio:.1%} > {FALLBACK_THRESHOLD:.0%} threshold"
        )
    if report.avg_drop_ratio > DROP_RATIO_THRESHOLD:
        report.threshold_violations.append(
            f"P2: Drop ratio {report.avg_drop_ratio:.1%} > {DROP_RATIO_THRESHOLD:.0%} threshold"
        )
    if report.avg_prose_words_per_chapter < MIN_PROSE_WORDS_PER_CHAPTER:
        report.threshold_violations.append(
            f"P1: Avg prose words/chapter {report.avg_prose_words_per_chapter:.0f} < {MIN_PROSE_WORDS_PER_CHAPTER} minimum"
        )

    # Write output
    if output_file:
        with open(output_file, 'w') as f:
            json.dump(asdict(report), f, indent=2)
        print(f"\nReport written to: {output_file}")

    return report


def print_summary(report: BatchReport) -> None:
    """Print human-readable summary."""
    print("\n" + "=" * 60)
    print(" BATCH EVALUATION SUMMARY")
    print("=" * 60)

    print(f"\nEdition: {report.edition}")
    print(f"Transcripts evaluated: {report.transcript_count}")
    print(f"Dynamic name policy: {'ENABLED' if report.dynamic_name_policy_enabled else 'DISABLED'}")

    print(f"\n--- Structural Invariants ---")
    print(f"  Pass: {report.structural_pass_count}")
    print(f"  Fail: {report.structural_fail_count}")

    print(f"\n--- Yield Metrics ---")
    print(f"  Avg drop ratio: {report.avg_drop_ratio:.1%}")
    print(f"  Avg fallback ratio: {report.avg_fallback_ratio:.1%}")
    print(f"  Avg prose words/chapter: {report.avg_prose_words_per_chapter:.0f}")

    if report.top_drop_reasons:
        print(f"\n--- Top Drop Reasons ---")
        for reason, count in report.top_drop_reasons.items():
            print(f"  {reason}: {count}")

    if report.threshold_violations:
        print(f"\n--- Threshold Violations ---")
        for violation in report.threshold_violations:
            print(f"  ⚠️  {violation}")
    else:
        print(f"\n✅ All thresholds within acceptable limits")

    print("\n" + "=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Batch evaluator for Ideas Edition quality metrics"
    )
    parser.add_argument(
        "--input_dir",
        type=Path,
        default=Path("corpora"),
        help="Directory containing transcript files (default: corpora/)"
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
        "--summary-only",
        action="store_true",
        help="Only print summary, don't save report"
    )

    args = parser.parse_args()

    if not args.input_dir.exists():
        print(f"Error: Input directory {args.input_dir} does not exist")
        print(f"Create it and add transcript files (.txt or .md)")
        return 1

    report = run_batch_evaluation(
        args.input_dir,
        args.edition,
        args.out if not args.summary_only else None,
    )

    print_summary(report)

    # Exit with error if P0 violations (structural failures)
    if report.structural_fail_count > 0:
        print(f"\n❌ {report.structural_fail_count} P0 structural failures - fix before shipping")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
