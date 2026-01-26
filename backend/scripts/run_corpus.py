#!/usr/bin/env python3
"""Corpus runner CLI for end-to-end baseline testing.

Generates Ideas Edition drafts for corpus transcripts, runs quality + groundedness
validation, and enforces rollout gates.

Usage:
    # Full corpus run (Type1 only, essay mode, local backend)
    python scripts/run_corpus.py --corpus backend/corpora/index.jsonl --out corpus_output/

    # HTTP backend (requires running server)
    python scripts/run_corpus.py --corpus backend/corpora/index.jsonl --backend http

    # CI mode (exit non-zero if gate fails)
    python scripts/run_corpus.py --corpus backend/corpora/index.jsonl --ci

    # Filter transcripts
    python scripts/run_corpus.py --corpus backend/corpora/index.jsonl --only T0002,T0003

Run from backend directory:
    python scripts/run_corpus.py --help
"""

import argparse
import asyncio
import json
import logging
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from corpus.draft_gen import (
    DraftGenRequest,
    DraftGenResult,
    DraftGenBackend,
    create_backend,
)
from corpus.thresholds import DEFAULT_THRESHOLDS, DEFAULT_OUTLINE, DEFAULT_STYLE_CONFIG

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# =============================================================================
# Blocking Wrapper (CLI layer only)
# =============================================================================


def generate_blocking(
    request: DraftGenRequest,
    backend: DraftGenBackend,
    timeout_s: int = 600,
) -> DraftGenResult:
    """Blocking entrypoint that hides async polling.

    This wrapper is in the CLI layer (not the adapter module) to avoid
    event loop issues when called from tests or notebooks.

    Args:
        request: Generation request
        backend: Backend to use
        timeout_s: Timeout in seconds

    Returns:
        DraftGenResult with draft or error
    """
    # Check if we're already in an event loop
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is not None:
        # Already in an event loop - run in a thread pool
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                asyncio.run,
                backend.generate(request, timeout_s),
            )
            return future.result(timeout=timeout_s + 30)
    else:
        # No event loop - safe to use asyncio.run
        return asyncio.run(backend.generate(request, timeout_s))


# =============================================================================
# Corpus Loading
# =============================================================================


def load_corpus_manifest(manifest_path: Path) -> list[dict]:
    """Load corpus manifest from index.jsonl."""
    entries = []
    with open(manifest_path) as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def filter_entries(
    entries: list[dict],
    types: list[str],
    only: Optional[list[str]] = None,
    skip: Optional[list[str]] = None,
) -> list[dict]:
    """Filter corpus entries by type and ID."""
    filtered = []
    for entry in entries:
        # Type filter
        if entry.get("classification") not in types:
            continue

        # ID filters
        entry_id = entry.get("id", "")
        if only and entry_id not in only:
            continue
        if skip and entry_id in skip:
            continue

        filtered.append(entry)

    return filtered


def load_transcript(entry: dict, corpora_private_dir: Path) -> Optional[str]:
    """Load transcript text for a corpus entry."""
    entry_id = entry.get("id", "")

    # Try normalized.txt first, then extracted.txt
    for filename in ["normalized.txt", "extracted.txt"]:
        # Find matching directory (may have suffix)
        for subdir in corpora_private_dir.iterdir():
            if subdir.is_dir() and subdir.name.startswith(entry_id):
                transcript_path = subdir / filename
                if transcript_path.exists():
                    return transcript_path.read_text()

    return None


def get_transcript_path(entry: dict, corpora_private_dir: Path) -> Optional[str]:
    """Get transcript file path for a corpus entry."""
    entry_id = entry.get("id", "")

    for filename in ["normalized.txt", "extracted.txt"]:
        for subdir in corpora_private_dir.iterdir():
            if subdir.is_dir() and subdir.name.startswith(entry_id):
                transcript_path = subdir / filename
                if transcript_path.exists():
                    return str(transcript_path)

    return None


# =============================================================================
# Main Runner (Placeholder for PR B)
# =============================================================================


def run_single_transcript(
    entry: dict,
    backend: DraftGenBackend,
    corpora_private_dir: Path,
    output_dir: Path,
    content_mode: str,
    require_preflight: bool,
    timeout_s: int,
) -> dict:
    """Run generation + validation for a single transcript.

    Returns gate_row dict with verdict and metrics.
    """
    entry_id = entry.get("id", "")
    logger.info(f"Processing {entry_id}...")

    # Load transcript
    transcript = load_transcript(entry, corpora_private_dir)
    if not transcript:
        logger.error(f"Could not load transcript for {entry_id}")
        return {
            "transcript_id": entry_id,
            "verdict": "FAIL",
            "failure_causes": ["transcript_not_found"],
        }

    transcript_path = get_transcript_path(entry, corpora_private_dir) or ""

    # Build style config with content_mode
    style_config = DEFAULT_STYLE_CONFIG.copy()
    style_config["style"] = style_config.get("style", {}).copy()
    style_config["style"]["content_mode"] = content_mode

    # Build request
    request = DraftGenRequest(
        transcript_id=entry_id,
        transcript=transcript,
        transcript_path=transcript_path,
        outline=DEFAULT_OUTLINE.copy(),
        style_config=style_config,
        require_preflight_pass=require_preflight,
    )

    # Generate draft
    result = generate_blocking(request, backend, timeout_s)

    if not result.success:
        logger.error(f"Generation failed for {entry_id}: {result.error}")
        return {
            "transcript_id": entry_id,
            "verdict": "FAIL",
            "failure_causes": [result.error_code or "generation_failed"],
            "error": result.error,
        }

    # Create output directory
    transcript_output_dir = output_dir / entry_id
    transcript_output_dir.mkdir(parents=True, exist_ok=True)

    # Save draft
    draft_path = transcript_output_dir / "draft.md"
    draft_path.write_text(result.draft_markdown or "")

    # Save request.json
    request_path = transcript_output_dir / "request.json"
    request_path.write_text(json.dumps(request.to_request_json(), indent=2))

    # Update meta with draft path and save
    if result.meta:
        result.meta.draft_path = str(draft_path)
        meta_path = transcript_output_dir / "draft_meta.json"
        meta_path.write_text(json.dumps(result.meta.to_dict(), indent=2))

    logger.info(f"Generated draft for {entry_id} ({len(result.draft_markdown or '')} chars)")

    # TODO (PR B): Run structure validation
    # TODO (PR B): Run groundedness validation
    # TODO (PR B): Compute yield metrics
    # TODO (PR B): Compute gate_row verdict

    # Placeholder gate_row
    return {
        "transcript_id": entry_id,
        "verdict": "PASS",  # Placeholder until validators implemented
        "structure_verdict": "PASS",
        "groundedness_verdict": "PASS",
        "failure_causes": [],
    }


def main():
    parser = argparse.ArgumentParser(
        description="Corpus runner for end-to-end baseline testing"
    )

    # Required
    parser.add_argument(
        "--corpus",
        type=Path,
        required=True,
        help="Path to corpus index.jsonl",
    )

    # Output
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("corpus_output"),
        help="Output directory (default: corpus_output/)",
    )

    # Backend
    parser.add_argument(
        "--backend",
        choices=["local", "http"],
        default="local",
        help="Generation backend (default: local)",
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000/api",
        help="API base URL for http backend",
    )

    # Generation options
    parser.add_argument(
        "--content-mode",
        choices=["interview", "essay", "tutorial"],
        default="essay",
        help="Content mode (default: essay)",
    )
    parser.add_argument(
        "--require-preflight",
        action="store_true",
        default=True,
        help="Fail on preflight failures (default: True)",
    )
    parser.add_argument(
        "--no-require-preflight",
        action="store_false",
        dest="require_preflight",
        help="Don't fail on preflight failures",
    )

    # Filtering
    parser.add_argument(
        "--types",
        default="Type1",
        help="Transcript types to include (default: Type1)",
    )
    parser.add_argument(
        "--only",
        help="Comma-separated transcript IDs to include",
    )
    parser.add_argument(
        "--skip",
        help="Comma-separated transcript IDs to exclude",
    )

    # Execution
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Parallel workers (default: 1 = sequential)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=600,
        help="Per-transcript timeout in seconds (default: 600)",
    )

    # Caching
    parser.add_argument(
        "--cache",
        choices=["drafts", "off"],
        default="drafts",
        help="Cache mode (default: drafts)",
    )
    parser.add_argument(
        "--regen",
        action="store_true",
        help="Force regeneration (ignore cache)",
    )

    # CI mode
    parser.add_argument(
        "--ci",
        action="store_true",
        help="CI mode: exit non-zero if gate fails",
    )

    args = parser.parse_args()

    # Validate corpus path
    if not args.corpus.exists():
        print(f"Error: Corpus manifest not found: {args.corpus}")
        sys.exit(1)

    # Determine corpora_private directory
    corpora_private_dir = args.corpus.parent.parent / "corpora_private"
    if not corpora_private_dir.exists():
        print(f"Error: corpora_private directory not found: {corpora_private_dir}")
        sys.exit(1)

    # Load and filter corpus
    entries = load_corpus_manifest(args.corpus)
    types = [t.strip() for t in args.types.split(",")]
    only = [i.strip() for i in args.only.split(",")] if args.only else None
    skip = [i.strip() for i in args.skip.split(",")] if args.skip else None
    filtered = filter_entries(entries, types, only, skip)

    if not filtered:
        print("No transcripts match the filter criteria")
        sys.exit(0)

    print(f"Processing {len(filtered)} transcripts...")
    print(f"  Types: {types}")
    print(f"  Backend: {args.backend}")
    print(f"  Content mode: {args.content_mode}")
    print(f"  Output: {args.out}")

    # Create backend
    backend = create_backend(args.backend, args.base_url)

    # Create output directory
    args.out.mkdir(parents=True, exist_ok=True)

    # Run transcripts (sequential for v1)
    gate_rows = []
    for entry in filtered:
        gate_row = run_single_transcript(
            entry=entry,
            backend=backend,
            corpora_private_dir=corpora_private_dir,
            output_dir=args.out,
            content_mode=args.content_mode,
            require_preflight=args.require_preflight,
            timeout_s=args.timeout,
        )
        gate_rows.append(gate_row)

    # Compute corpus-level verdict
    fail_count = sum(1 for r in gate_rows if r["verdict"] == "FAIL")
    warn_count = sum(1 for r in gate_rows if r["verdict"] == "WARN")
    pass_count = sum(1 for r in gate_rows if r["verdict"] == "PASS")

    print("\n" + "=" * 60)
    print("CORPUS RUNNER RESULTS")
    print("=" * 60)
    print(f"  PASS: {pass_count}")
    print(f"  WARN: {warn_count}")
    print(f"  FAIL: {fail_count}")

    # Check rollout gate
    thresholds = DEFAULT_THRESHOLDS
    violations = []
    if fail_count > thresholds.gate_max_fail:
        violations.append(f"fail_count={fail_count} exceeds gate_max_fail={thresholds.gate_max_fail}")
    if warn_count > thresholds.gate_max_warn:
        violations.append(f"warn_count={warn_count} exceeds gate_max_warn={thresholds.gate_max_warn}")

    gate_passed = len(violations) == 0

    print(f"\nRollout Gate: {'PASSED' if gate_passed else 'FAILED'}")
    if violations:
        for v in violations:
            print(f"  - {v}")

    # Save corpus report
    corpus_report = {
        "generated_at": __import__("datetime").datetime.now().isoformat(),
        "content_mode": args.content_mode,
        "transcript_count": len(filtered),
        "verdicts": {"PASS": pass_count, "WARN": warn_count, "FAIL": fail_count},
        "thresholds": thresholds.to_dict(),
        "rollout_gate": {"passed": gate_passed, "violations": violations},
        "gate_rows": gate_rows,
    }
    report_path = args.out / "corpus_report.json"
    report_path.write_text(json.dumps(corpus_report, indent=2))
    print(f"\nReport saved to: {report_path}")

    # CI exit code
    if args.ci and not gate_passed:
        sys.exit(1)


if __name__ == "__main__":
    main()
