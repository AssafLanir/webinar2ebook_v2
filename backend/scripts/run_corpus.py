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

    # Force regeneration (ignore cache)
    python scripts/run_corpus.py --corpus backend/corpora/index.jsonl --regen

Run from backend directory:
    python scripts/run_corpus.py --help
"""

import argparse
import logging
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from corpus.runner import run_corpus
from corpus.thresholds import DEFAULT_THRESHOLDS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


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

    # Debug
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )

    args = parser.parse_args()

    # Set log level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Validate corpus path
    if not args.corpus.exists():
        print(f"Error: Corpus manifest not found: {args.corpus}")
        sys.exit(1)

    # Determine corpora_private directory
    corpora_private_dir = args.corpus.parent.parent / "corpora_private"
    if not corpora_private_dir.exists():
        print(f"Error: corpora_private directory not found: {corpora_private_dir}")
        sys.exit(1)

    # Parse filter arguments
    types = [t.strip() for t in args.types.split(",")]
    only = [i.strip() for i in args.only.split(",")] if args.only else None
    skip = [i.strip() for i in args.skip.split(",")] if args.skip else None

    print(f"Corpus Runner")
    print(f"  Manifest: {args.corpus}")
    print(f"  Types: {types}")
    print(f"  Backend: {args.backend}")
    print(f"  Content mode: {args.content_mode}")
    print(f"  Output: {args.out}")
    print(f"  Cache: {args.cache}")
    if only:
        print(f"  Only: {only}")
    if skip:
        print(f"  Skip: {skip}")
    print()

    # Run corpus
    try:
        report = run_corpus(
            manifest_path=args.corpus,
            output_dir=args.out,
            corpora_private_dir=corpora_private_dir,
            types=types,
            only=only,
            skip=skip,
            workers=args.workers,
            backend_type=args.backend,
            base_url=args.base_url,
            content_mode=args.content_mode,
            require_preflight_pass=args.require_preflight,
            timeout_s=args.timeout,
            cache_enabled=args.cache == "drafts",
            force_regen=args.regen,
        )
    except Exception as e:
        logger.exception("Corpus run failed")
        print(f"\nError: {e}")
        sys.exit(1)

    # Print summary
    if "error" in report:
        print(f"\nError: {report['error']}")
        sys.exit(1)

    verdicts = report.get("verdicts", {})
    print("\n" + "=" * 60)
    print("CORPUS RUNNER RESULTS")
    print("=" * 60)
    print(f"  PASS: {verdicts.get('PASS', 0)}")
    print(f"  WARN: {verdicts.get('WARN', 0)}")
    print(f"  FAIL: {verdicts.get('FAIL', 0)}")

    gate = report.get("rollout_gate", {})
    gate_passed = gate.get("passed", False)

    print(f"\nRollout Gate: {'PASSED' if gate_passed else 'FAILED'}")
    if gate.get("violations"):
        for v in gate["violations"]:
            print(f"  - {v}")

    print(f"\nReports saved to: {args.out}")
    print(f"  - corpus_report.json")
    print(f"  - corpus_summary.md")

    # CI exit code
    if args.ci and not gate_passed:
        sys.exit(1)


if __name__ == "__main__":
    main()
