#!/usr/bin/env python3
"""Groundedness evaluator CLI for Ideas Edition quote provenance.

Validates that:
1. Key Excerpts quotes actually exist in the source transcript
2. Core Claims have supporting quotes that exist in the transcript

This catches "invented quotes" and ensures output is grounded in source material.

Usage:
    # Evaluate a single draft against its transcript
    python scripts/groundedness_eval.py --draft corpora/good_sensory.md --transcript /path/to/transcript.txt

    # Batch mode: evaluate all drafts in a directory against transcripts in another
    python scripts/groundedness_eval.py --draft_dir corpora/ --transcript_dir transcripts/ --out report.json

    # CI mode: exit non-zero on FAIL
    python scripts/groundedness_eval.py --draft draft.md --transcript transcript.txt --ci

Run from backend directory:
    python scripts/groundedness_eval.py --help
"""

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from services.groundedness_service import (
    check_groundedness,
    GroundednessReport,
)


@dataclass
class GroundednessResult:
    """Result for a single draft evaluation."""
    draft_file: str
    transcript_file: str
    overall_verdict: str = "PASS"

    # Key Excerpts provenance
    excerpts_total: int = 0
    excerpts_found: int = 0
    excerpts_not_found: int = 0
    excerpt_provenance_rate: float = 0.0
    excerpt_verdict: str = "PASS"
    missing_excerpts: list = field(default_factory=list)

    # Core Claims support
    claims_total: int = 0
    claims_with_evidence: int = 0
    claims_missing_evidence: int = 0
    evidence_found: int = 0
    evidence_not_found: int = 0
    evidence_provenance_rate: float = 0.0
    claim_verdict: str = "PASS"
    missing_evidence: list = field(default_factory=list)

    # Errors
    error: Optional[str] = None


@dataclass
class GroundednessBatchReport:
    """Batch groundedness evaluation report."""
    generated_at: str
    mode: str  # "strict" or "tolerant"
    files_evaluated: int = 0

    # Verdict counts
    pass_count: int = 0
    warn_count: int = 0
    fail_count: int = 0
    overall_verdict: str = "PASS"

    # Aggregate metrics
    avg_excerpt_provenance: float = 0.0
    avg_evidence_provenance: float = 0.0
    total_missing_excerpts: int = 0
    total_missing_evidence: int = 0

    # Per-file results
    results: list = field(default_factory=list)


def evaluate_groundedness(
    draft_path: Path,
    transcript_path: Path,
    strict: bool = True,
) -> GroundednessResult:
    """Evaluate groundedness of a single draft against transcript."""
    result = GroundednessResult(
        draft_file=draft_path.name,
        transcript_file=transcript_path.name,
    )

    try:
        draft = draft_path.read_text()
        transcript = transcript_path.read_text()

        report = check_groundedness(draft, transcript, strict=strict)

        # Populate result from report
        result.overall_verdict = report.overall_verdict

        # Excerpts
        ep = report.excerpt_provenance
        result.excerpts_total = ep.excerpts_total
        result.excerpts_found = ep.excerpts_found
        result.excerpts_not_found = ep.excerpts_not_found
        result.excerpt_provenance_rate = ep.provenance_rate
        result.excerpt_verdict = ep.verdict
        result.missing_excerpts = ep.missing_quotes

        # Claims
        cs = report.claim_support
        result.claims_total = cs.claims_total
        result.claims_with_evidence = cs.claims_with_evidence
        result.claims_missing_evidence = cs.claims_missing_evidence
        result.evidence_found = cs.evidence_quotes_found
        result.evidence_not_found = cs.evidence_quotes_not_found
        result.evidence_provenance_rate = cs.evidence_provenance_rate
        result.claim_verdict = cs.verdict
        result.missing_evidence = cs.missing_evidence_quotes

    except Exception as e:
        result.error = str(e)
        result.overall_verdict = "FAIL"

    return result


def print_result(result: GroundednessResult, verbose: bool = False) -> None:
    """Print a single result to console."""
    verdict_symbol = {"PASS": "✓", "WARN": "⚠", "FAIL": "✗"}.get(result.overall_verdict, "?")

    print(f"\n{verdict_symbol} {result.draft_file}")
    print(f"  Transcript: {result.transcript_file}")

    if result.error:
        print(f"  ERROR: {result.error}")
        return

    # Excerpts
    print(f"\n  Key Excerpts: {result.excerpt_verdict}")
    print(f"    Found: {result.excerpts_found}/{result.excerpts_total} ({result.excerpt_provenance_rate:.1%})")
    if result.missing_excerpts and (verbose or result.excerpt_verdict != "PASS"):
        print(f"    Missing quotes:")
        for q in result.missing_excerpts[:5]:
            print(f"      - {q}")

    # Claims
    print(f"\n  Core Claims: {result.claim_verdict}")
    print(f"    With evidence: {result.claims_with_evidence}/{result.claims_total}")
    print(f"    Evidence found: {result.evidence_found}/{result.claims_with_evidence} ({result.evidence_provenance_rate:.1%})")
    if result.missing_evidence and (verbose or result.claim_verdict != "PASS"):
        print(f"    Missing evidence quotes:")
        for q in result.missing_evidence[:5]:
            print(f"      - {q}")


def run_batch(
    draft_dir: Path,
    transcript_dir: Path,
    strict: bool = True,
    output_file: Optional[Path] = None,
) -> GroundednessBatchReport:
    """Run batch groundedness evaluation.

    Pairs drafts with transcripts by name pattern:
    - draft: good_sensory_default.md
    - transcript: good_sensory_default.txt (or .md)
    """
    report = GroundednessBatchReport(
        generated_at=datetime.now().isoformat(),
        mode="strict" if strict else "tolerant",
    )

    # Find all draft files
    draft_files = list(draft_dir.glob("*.md"))

    for draft_path in sorted(draft_files):
        # Try to find matching transcript
        base_name = draft_path.stem
        transcript_path = None

        for ext in [".txt", ".md"]:
            candidate = transcript_dir / f"{base_name}{ext}"
            if candidate.exists():
                transcript_path = candidate
                break

        if not transcript_path:
            # Skip files without matching transcript
            continue

        result = evaluate_groundedness(draft_path, transcript_path, strict=strict)
        report.results.append(asdict(result))
        report.files_evaluated += 1

        if result.overall_verdict == "PASS":
            report.pass_count += 1
        elif result.overall_verdict == "WARN":
            report.warn_count += 1
        else:
            report.fail_count += 1

        report.total_missing_excerpts += result.excerpts_not_found
        report.total_missing_evidence += result.evidence_not_found

    # Aggregate metrics
    if report.files_evaluated > 0:
        excerpt_rates = [r["excerpt_provenance_rate"] for r in report.results if r["excerpt_provenance_rate"] is not None]
        evidence_rates = [r["evidence_provenance_rate"] for r in report.results if r["evidence_provenance_rate"] is not None]

        if excerpt_rates:
            report.avg_excerpt_provenance = sum(excerpt_rates) / len(excerpt_rates)
        if evidence_rates:
            report.avg_evidence_provenance = sum(evidence_rates) / len(evidence_rates)

    # Overall verdict
    if report.fail_count > 0:
        report.overall_verdict = "FAIL"
    elif report.warn_count > 0:
        report.overall_verdict = "WARN"
    else:
        report.overall_verdict = "PASS"

    # Save report
    if output_file:
        with open(output_file, 'w') as f:
            json.dump(asdict(report), f, indent=2)

    return report


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate groundedness of Ideas Edition drafts against source transcripts"
    )

    # Single file mode
    parser.add_argument("--draft", type=Path, help="Path to draft markdown file")
    parser.add_argument("--transcript", type=Path, help="Path to transcript file")

    # Batch mode
    parser.add_argument("--draft_dir", type=Path, help="Directory containing draft files")
    parser.add_argument("--transcript_dir", type=Path, help="Directory containing transcript files")

    # Options
    parser.add_argument("--strict", action="store_true", default=True,
                        help="Use strict mode (FAIL on any missing quote)")
    parser.add_argument("--tolerant", action="store_true",
                        help="Use tolerant mode (WARN on ≤1 missing)")
    parser.add_argument("--out", type=Path, help="Output file for JSON report")
    parser.add_argument("--ci", action="store_true",
                        help="CI mode: exit non-zero on FAIL")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Show detailed output including all missing quotes")

    args = parser.parse_args()

    strict = not args.tolerant

    # Single file mode
    if args.draft and args.transcript:
        result = evaluate_groundedness(args.draft, args.transcript, strict=strict)
        print_result(result, verbose=args.verbose)

        if args.out:
            with open(args.out, 'w') as f:
                json.dump(asdict(result), f, indent=2)

        if args.ci and result.overall_verdict == "FAIL":
            sys.exit(1)

        return

    # Batch mode
    if args.draft_dir and args.transcript_dir:
        report = run_batch(args.draft_dir, args.transcript_dir, strict=strict, output_file=args.out)

        print("=" * 70)
        print("GROUNDEDNESS EVALUATION REPORT")
        print("=" * 70)
        print(f"\nMode: {'strict' if strict else 'tolerant'}")
        print(f"Files evaluated: {report.files_evaluated}")
        print(f"\nVerdicts:")
        print(f"  PASS: {report.pass_count}")
        print(f"  WARN: {report.warn_count}")
        print(f"  FAIL: {report.fail_count}")
        print(f"\nAggregate metrics:")
        print(f"  Avg excerpt provenance: {report.avg_excerpt_provenance:.1%}")
        print(f"  Avg evidence provenance: {report.avg_evidence_provenance:.1%}")
        print(f"  Total missing excerpts: {report.total_missing_excerpts}")
        print(f"  Total missing evidence: {report.total_missing_evidence}")

        if report.results:
            print(f"\nPer-file results:")
            for r in report.results:
                verdict = r["overall_verdict"]
                symbol = {"PASS": "✓", "WARN": "⚠", "FAIL": "✗"}.get(verdict, "?")
                print(f"  {symbol} {r['draft_file']}: {verdict}")

        print("=" * 70)
        print(f"Overall: {report.overall_verdict}")
        print("=" * 70)

        if args.ci and report.overall_verdict == "FAIL":
            sys.exit(1)

        return

    # No valid mode selected
    parser.print_help()
    print("\nError: Specify either (--draft + --transcript) or (--draft_dir + --transcript_dir)")
    sys.exit(1)


if __name__ == "__main__":
    main()
