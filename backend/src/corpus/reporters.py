"""Report generation for corpus runner.

Produces:
- Per-transcript work unit files (7 files per transcript)
- Corpus-level aggregate report (corpus_report.json)
- Human-readable summary (corpus_summary.md)
"""

from __future__ import annotations

import json
import statistics
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from .draft_gen import DraftGenRequest, DraftGenResult, DraftGenMeta
from .validators import StructureResult, GroundednessResult, YieldResult, GateRow
from .thresholds import Thresholds, DEFAULT_THRESHOLDS


# =============================================================================
# Work Unit Writing
# =============================================================================


def write_work_unit(
    out_dir: Path,
    transcript_id: str,
    request: DraftGenRequest,
    result: DraftGenResult,
    structure: Optional[StructureResult],
    groundedness: Optional[GroundednessResult],
    yield_result: Optional[YieldResult],
    gate_row: GateRow,
) -> None:
    """Write all work unit files for a single transcript.

    Files written:
    - request.json
    - draft_meta.json
    - draft.md
    - structure.json
    - groundedness.json
    - yield.json
    - gate_row.json

    Always writes request.json and gate_row.json, even on failures.
    """
    transcript_dir = out_dir / transcript_id
    transcript_dir.mkdir(parents=True, exist_ok=True)

    # 1. request.json (always written)
    request_path = transcript_dir / "request.json"
    request_path.write_text(json.dumps(request.to_request_json(), indent=2))

    # 2. draft_meta.json
    if result.meta:
        # Update draft_path to actual location
        result.meta.draft_path = str(transcript_dir / "draft.md")
        meta_path = transcript_dir / "draft_meta.json"
        meta_path.write_text(json.dumps(result.meta.to_dict(), indent=2))

    # 3. draft.md
    if result.draft_markdown:
        draft_path = transcript_dir / "draft.md"
        draft_path.write_text(result.draft_markdown)

    # 4. structure.json
    if structure:
        structure_path = transcript_dir / "structure.json"
        structure_path.write_text(json.dumps(structure.to_dict(), indent=2))

    # 5. groundedness.json
    if groundedness:
        groundedness_path = transcript_dir / "groundedness.json"
        groundedness_path.write_text(json.dumps(groundedness.to_dict(), indent=2))

    # 6. yield.json
    if yield_result:
        yield_path = transcript_dir / "yield.json"
        yield_path.write_text(json.dumps(yield_result.to_dict(), indent=2))

    # 7. gate_row.json (always written)
    gate_row_path = transcript_dir / "gate_row.json"
    gate_row_path.write_text(json.dumps(gate_row.to_dict(), indent=2))


# =============================================================================
# Corpus Aggregation
# =============================================================================


def aggregate_corpus(
    gate_rows: list[GateRow],
    git_commit: str,
    config_hash: str,
    prompt_version: str,
    content_mode: str,
    require_preflight_pass: bool,
    thresholds: Thresholds = DEFAULT_THRESHOLDS,
) -> dict:
    """Aggregate gate rows into corpus report.

    Args:
        gate_rows: List of per-transcript gate rows
        git_commit: Git commit hash
        config_hash: Configuration hash
        prompt_version: Prompt version string
        content_mode: Content mode used
        require_preflight_pass: Whether preflight was required
        thresholds: Threshold configuration

    Returns:
        Corpus report dictionary
    """
    # Count verdicts
    pass_count = sum(1 for r in gate_rows if r.verdict == "PASS")
    warn_count = sum(1 for r in gate_rows if r.verdict == "WARN")
    fail_count = sum(1 for r in gate_rows if r.verdict == "FAIL")

    # Compute aggregates
    excerpt_rates = [r.excerpt_provenance_rate for r in gate_rows if r.excerpt_provenance_rate > 0]
    claim_rates = [r.claim_provenance_rate for r in gate_rows if r.claim_provenance_rate > 0]
    fallback_rates = [r.fallback_ratio for r in gate_rows]
    p10_values = [r.p10_prose_words for r in gate_rows if r.p10_prose_words > 0]

    aggregates = {
        "avg_excerpt_provenance": statistics.mean(excerpt_rates) if excerpt_rates else 0.0,
        "avg_claim_provenance": statistics.mean(claim_rates) if claim_rates else 0.0,
        "avg_fallback_ratio": statistics.mean(fallback_rates) if fallback_rates else 0.0,
        "p10_prose_words": statistics.mean(p10_values) if p10_values else 0.0,
        "median_prose_words": statistics.median(p10_values) if p10_values else 0.0,
    }

    # Check rollout gate
    violations = []
    if fail_count > thresholds.gate_max_fail:
        violations.append(f"fail_count={fail_count} exceeds gate_max_fail={thresholds.gate_max_fail}")
    if warn_count > thresholds.gate_max_warn:
        violations.append(f"warn_count={warn_count} exceeds gate_max_warn={thresholds.gate_max_warn}")
    if aggregates["avg_fallback_ratio"] > thresholds.gate_max_fallback_rate:
        violations.append(
            f"avg_fallback_ratio={aggregates['avg_fallback_ratio']:.2f} "
            f"exceeds gate_max_fallback_rate={thresholds.gate_max_fallback_rate}"
        )
    if aggregates["p10_prose_words"] < thresholds.gate_min_p10_prose:
        violations.append(
            f"p10_prose_words={aggregates['p10_prose_words']:.0f} "
            f"below gate_min_p10_prose={thresholds.gate_min_p10_prose}"
        )

    gate_passed = len(violations) == 0

    # Collect failure causes across corpus
    failure_cause_counts: dict[str, int] = {}
    for row in gate_rows:
        for cause in row.failure_causes:
            failure_cause_counts[cause] = failure_cause_counts.get(cause, 0) + 1

    return {
        "generated_at": datetime.now().isoformat(),
        "git_commit": git_commit,
        "config_hash": config_hash,
        "prompt_version": prompt_version,
        "content_mode": content_mode,
        "require_preflight_pass": require_preflight_pass,
        "transcript_count": len(gate_rows),
        "verdicts": {
            "PASS": pass_count,
            "WARN": warn_count,
            "FAIL": fail_count,
        },
        "aggregates": aggregates,
        "thresholds": thresholds.to_dict(),
        "rollout_gate": {
            "passed": gate_passed,
            "violations": violations,
        },
        "top_failure_causes": dict(sorted(
            failure_cause_counts.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:10]),
        "gate_rows": [r.to_dict() for r in gate_rows],
    }


def write_corpus_report(out_dir: Path, report: dict) -> Path:
    """Write corpus report to JSON file.

    Args:
        out_dir: Output directory
        report: Corpus report dictionary

    Returns:
        Path to written file
    """
    report_path = out_dir / "corpus_report.json"
    report_path.write_text(json.dumps(report, indent=2))
    return report_path


# =============================================================================
# Summary Markdown
# =============================================================================


def render_summary_md(report: dict) -> str:
    """Render human-readable summary markdown.

    Args:
        report: Corpus report dictionary

    Returns:
        Markdown string
    """
    lines = []

    # Header
    lines.append("# Corpus Runner Summary")
    lines.append("")
    lines.append(f"**Generated:** {report['generated_at']}")
    lines.append(f"**Git Commit:** `{report['git_commit']}`")
    lines.append(f"**Content Mode:** {report['content_mode']}")
    lines.append(f"**Transcripts:** {report['transcript_count']}")
    lines.append("")

    # Rollout Gate
    gate = report["rollout_gate"]
    gate_status = "PASSED" if gate["passed"] else "FAILED"
    lines.append(f"## Rollout Gate: {gate_status}")
    lines.append("")

    if gate["violations"]:
        lines.append("**Violations:**")
        for v in gate["violations"]:
            lines.append(f"- {v}")
        lines.append("")

    # Verdict Summary
    verdicts = report["verdicts"]
    lines.append("## Verdict Summary")
    lines.append("")
    lines.append("| Verdict | Count |")
    lines.append("|---------|-------|")
    lines.append(f"| PASS | {verdicts['PASS']} |")
    lines.append(f"| WARN | {verdicts['WARN']} |")
    lines.append(f"| FAIL | {verdicts['FAIL']} |")
    lines.append("")

    # Aggregates
    agg = report["aggregates"]
    lines.append("## Aggregate Metrics")
    lines.append("")
    lines.append(f"- **Avg Excerpt Provenance:** {agg['avg_excerpt_provenance']:.1%}")
    lines.append(f"- **Avg Claim Provenance:** {agg['avg_claim_provenance']:.1%}")
    lines.append(f"- **Avg Fallback Ratio:** {agg['avg_fallback_ratio']:.1%}")
    lines.append(f"- **P10 Prose Words:** {agg['p10_prose_words']:.0f}")
    lines.append("")

    # Top Failure Causes
    if report.get("top_failure_causes"):
        lines.append("## Top Failure Causes")
        lines.append("")
        for cause, count in report["top_failure_causes"].items():
            lines.append(f"- {cause}: {count}")
        lines.append("")

    # Per-Transcript Results
    lines.append("## Per-Transcript Results")
    lines.append("")
    lines.append("| Transcript | Verdict | Excerpt Prov | Claim Prov | Fallback | P10 Prose |")
    lines.append("|------------|---------|--------------|------------|----------|-----------|")

    for row in report["gate_rows"]:
        verdict_icon = {"PASS": "✓", "WARN": "⚠", "FAIL": "✗"}.get(row["verdict"], "?")
        lines.append(
            f"| {row['transcript_id']} | {verdict_icon} {row['verdict']} | "
            f"{row['excerpt_provenance_rate']:.0%} | {row['claim_provenance_rate']:.0%} | "
            f"{row['fallback_ratio']:.0%} | {row['p10_prose_words']:.0f} |"
        )

    lines.append("")

    # Top Offenders
    offenders = [r for r in report["gate_rows"] if r["verdict"] in ("FAIL", "WARN")]
    if offenders:
        lines.append("## Top Offenders")
        lines.append("")
        for row in offenders[:5]:
            lines.append(f"### {row['transcript_id']} ({row['verdict']})")
            if row.get("failure_causes"):
                lines.append(f"- Causes: {', '.join(row['failure_causes'])}")
            if row.get("error"):
                lines.append(f"- Error: {row['error']}")
            lines.append("")

    # Thresholds
    lines.append("## Thresholds Used")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps(report["thresholds"], indent=2))
    lines.append("```")
    lines.append("")

    return "\n".join(lines)


def write_corpus_summary(out_dir: Path, report: dict) -> Path:
    """Write corpus summary markdown.

    Args:
        out_dir: Output directory
        report: Corpus report dictionary

    Returns:
        Path to written file
    """
    summary_md = render_summary_md(report)
    summary_path = out_dir / "corpus_summary.md"
    summary_path.write_text(summary_md)
    return summary_path
