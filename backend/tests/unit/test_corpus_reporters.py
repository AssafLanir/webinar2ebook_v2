"""Unit tests for corpus reporters.

Tests report aggregation and rendering - no LLM providers needed.
"""

import json
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory

from corpus.reporters import (
    aggregate_corpus,
    render_summary_md,
    write_corpus_report,
    write_corpus_summary,
    write_work_unit,
)
from corpus.validators import (
    GateRow,
    StructureResult,
    GroundednessResult,
    YieldResult,
)
from corpus.draft_gen import DraftGenRequest, DraftGenResult, DraftGenMeta
from corpus.thresholds import DEFAULT_THRESHOLDS


# =============================================================================
# Test Fixtures
# =============================================================================

def make_pass_gate_row(transcript_id: str) -> GateRow:
    """Create a PASS gate row for testing."""
    return GateRow(
        run_id=f"{transcript_id}__essay__c0__abc123",
        transcript_id=transcript_id,
        candidate_index=0,
        content_mode="essay",
        verdict="PASS",
        structure_verdict="PASS",
        groundedness_verdict="PASS",
        excerpt_provenance_rate=1.0,
        claim_provenance_rate=0.9,
        fallback_ratio=0.0,
        p10_prose_words=100.0,
        failure_causes=[],
    )


def make_warn_gate_row(transcript_id: str) -> GateRow:
    """Create a WARN gate row for testing."""
    return GateRow(
        run_id=f"{transcript_id}__essay__c0__abc123",
        transcript_id=transcript_id,
        candidate_index=0,
        content_mode="essay",
        verdict="WARN",
        structure_verdict="PASS",
        groundedness_verdict="PASS",
        excerpt_provenance_rate=0.8,
        claim_provenance_rate=0.7,
        fallback_ratio=0.1,
        p10_prose_words=50.0,
        failure_causes=["low_prose"],
    )


def make_fail_gate_row(transcript_id: str) -> GateRow:
    """Create a FAIL gate row for testing."""
    return GateRow(
        run_id=f"{transcript_id}__essay__c0__abc123",
        transcript_id=transcript_id,
        candidate_index=0,
        content_mode="essay",
        verdict="FAIL",
        structure_verdict="FAIL",
        groundedness_verdict="FAIL",
        excerpt_provenance_rate=0.0,
        claim_provenance_rate=0.0,
        fallback_ratio=0.0,
        p10_prose_words=0.0,
        failure_causes=["structure_fail"],
        error="Missing chapter structure",
    )


# =============================================================================
# Corpus Aggregation Tests
# =============================================================================

class TestCorpusAggregation:
    """Tests for corpus-level report aggregation."""

    def test_aggregates_verdicts(self):
        """Should count verdicts correctly."""
        gate_rows = [
            make_pass_gate_row("T001"),
            make_pass_gate_row("T002"),
            make_warn_gate_row("T003"),
            make_fail_gate_row("T004"),
        ]

        report = aggregate_corpus(
            gate_rows=gate_rows,
            git_commit="abc1234",
            config_hash="cfg123",
            prompt_version="ideas_v3",
            content_mode="essay",
            require_preflight_pass=True,
        )

        assert report["verdicts"]["PASS"] == 2
        assert report["verdicts"]["WARN"] == 1
        assert report["verdicts"]["FAIL"] == 1
        assert report["transcript_count"] == 4

    def test_computes_averages(self):
        """Should compute aggregate metrics correctly."""
        gate_rows = [
            make_pass_gate_row("T001"),  # excerpt=1.0, claim=0.9, p10=100
            make_warn_gate_row("T002"),  # excerpt=0.8, claim=0.7, p10=50
        ]

        report = aggregate_corpus(
            gate_rows=gate_rows,
            git_commit="abc1234",
            config_hash="cfg123",
            prompt_version="ideas_v3",
            content_mode="essay",
            require_preflight_pass=True,
        )

        agg = report["aggregates"]
        assert agg["avg_excerpt_provenance"] == pytest.approx(0.9, abs=0.01)
        assert agg["avg_claim_provenance"] == pytest.approx(0.8, abs=0.01)
        assert agg["p10_prose_words"] == pytest.approx(75.0, abs=0.01)

    def test_rollout_gate_passes(self):
        """Gate should pass when within thresholds."""
        gate_rows = [
            make_pass_gate_row("T001"),
            make_pass_gate_row("T002"),
            make_warn_gate_row("T003"),  # 1 WARN is within threshold
        ]

        report = aggregate_corpus(
            gate_rows=gate_rows,
            git_commit="abc1234",
            config_hash="cfg123",
            prompt_version="ideas_v3",
            content_mode="essay",
            require_preflight_pass=True,
        )

        assert report["rollout_gate"]["passed"] is True
        assert len(report["rollout_gate"]["violations"]) == 0

    def test_rollout_gate_fails_on_fail_count(self):
        """Gate should fail when FAIL count exceeds threshold."""
        gate_rows = [
            make_pass_gate_row("T001"),
            make_fail_gate_row("T002"),  # 1 FAIL > gate_max_fail=0
        ]

        report = aggregate_corpus(
            gate_rows=gate_rows,
            git_commit="abc1234",
            config_hash="cfg123",
            prompt_version="ideas_v3",
            content_mode="essay",
            require_preflight_pass=True,
        )

        assert report["rollout_gate"]["passed"] is False
        assert any("fail_count" in v for v in report["rollout_gate"]["violations"])

    def test_rollout_gate_fails_on_warn_count(self):
        """Gate should fail when WARN count exceeds threshold."""
        gate_rows = [
            make_warn_gate_row("T001"),
            make_warn_gate_row("T002"),
            make_warn_gate_row("T003"),  # 3 WARN > gate_max_warn=2
        ]

        report = aggregate_corpus(
            gate_rows=gate_rows,
            git_commit="abc1234",
            config_hash="cfg123",
            prompt_version="ideas_v3",
            content_mode="essay",
            require_preflight_pass=True,
        )

        assert report["rollout_gate"]["passed"] is False
        assert any("warn_count" in v for v in report["rollout_gate"]["violations"])

    def test_tracks_failure_causes(self):
        """Should track and count failure causes."""
        gate_rows = [
            GateRow(
                run_id="T001__essay__c0__abc",
                transcript_id="T001",
                candidate_index=0,
                content_mode="essay",
                verdict="WARN",
                failure_causes=["low_prose", "high_fallback"],
            ),
            GateRow(
                run_id="T002__essay__c0__abc",
                transcript_id="T002",
                candidate_index=0,
                content_mode="essay",
                verdict="WARN",
                failure_causes=["low_prose"],
            ),
        ]

        report = aggregate_corpus(
            gate_rows=gate_rows,
            git_commit="abc1234",
            config_hash="cfg123",
            prompt_version="ideas_v3",
            content_mode="essay",
            require_preflight_pass=True,
        )

        assert report["top_failure_causes"]["low_prose"] == 2
        assert report["top_failure_causes"]["high_fallback"] == 1

    def test_includes_metadata(self):
        """Report should include run metadata."""
        gate_rows = [make_pass_gate_row("T001")]

        report = aggregate_corpus(
            gate_rows=gate_rows,
            git_commit="abc1234",
            config_hash="cfg123",
            prompt_version="ideas_v3",
            content_mode="essay",
            require_preflight_pass=True,
        )

        assert report["git_commit"] == "abc1234"
        assert report["config_hash"] == "cfg123"
        assert report["prompt_version"] == "ideas_v3"
        assert report["content_mode"] == "essay"
        assert "generated_at" in report


# =============================================================================
# Summary Markdown Tests
# =============================================================================

class TestSummaryMarkdown:
    """Tests for human-readable summary rendering."""

    def test_renders_header(self):
        """Summary should include header with metadata."""
        gate_rows = [make_pass_gate_row("T001")]
        report = aggregate_corpus(
            gate_rows=gate_rows,
            git_commit="abc1234",
            config_hash="cfg123",
            prompt_version="ideas_v3",
            content_mode="essay",
            require_preflight_pass=True,
        )

        md = render_summary_md(report)

        assert "# Corpus Runner Summary" in md
        assert "abc1234" in md
        assert "essay" in md

    def test_renders_gate_status(self):
        """Summary should show rollout gate status."""
        gate_rows = [make_pass_gate_row("T001")]
        report = aggregate_corpus(
            gate_rows=gate_rows,
            git_commit="abc1234",
            config_hash="cfg123",
            prompt_version="ideas_v3",
            content_mode="essay",
            require_preflight_pass=True,
        )

        md = render_summary_md(report)

        assert "## Rollout Gate: PASSED" in md

    def test_renders_verdict_table(self):
        """Summary should include verdict summary table."""
        gate_rows = [
            make_pass_gate_row("T001"),
            make_warn_gate_row("T002"),
        ]
        report = aggregate_corpus(
            gate_rows=gate_rows,
            git_commit="abc1234",
            config_hash="cfg123",
            prompt_version="ideas_v3",
            content_mode="essay",
            require_preflight_pass=True,
        )

        md = render_summary_md(report)

        assert "## Verdict Summary" in md
        assert "| PASS | 1 |" in md
        assert "| WARN | 1 |" in md

    def test_renders_per_transcript_results(self):
        """Summary should include per-transcript table."""
        gate_rows = [make_pass_gate_row("T001")]
        report = aggregate_corpus(
            gate_rows=gate_rows,
            git_commit="abc1234",
            config_hash="cfg123",
            prompt_version="ideas_v3",
            content_mode="essay",
            require_preflight_pass=True,
        )

        md = render_summary_md(report)

        assert "## Per-Transcript Results" in md
        assert "T001" in md


# =============================================================================
# File Writing Tests
# =============================================================================

class TestFileWriting:
    """Tests for writing reports to disk."""

    def test_write_corpus_report(self):
        """Should write corpus_report.json correctly."""
        gate_rows = [make_pass_gate_row("T001")]
        report = aggregate_corpus(
            gate_rows=gate_rows,
            git_commit="abc1234",
            config_hash="cfg123",
            prompt_version="ideas_v3",
            content_mode="essay",
            require_preflight_pass=True,
        )

        with TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir)
            path = write_corpus_report(out_dir, report)

            assert path.exists()
            assert path.name == "corpus_report.json"

            # Verify it's valid JSON
            with open(path) as f:
                loaded = json.load(f)
            assert loaded["transcript_count"] == 1

    def test_write_corpus_summary(self):
        """Should write corpus_summary.md correctly."""
        gate_rows = [make_pass_gate_row("T001")]
        report = aggregate_corpus(
            gate_rows=gate_rows,
            git_commit="abc1234",
            config_hash="cfg123",
            prompt_version="ideas_v3",
            content_mode="essay",
            require_preflight_pass=True,
        )

        with TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir)
            path = write_corpus_summary(out_dir, report)

            assert path.exists()
            assert path.name == "corpus_summary.md"

            content = path.read_text()
            assert "# Corpus Runner Summary" in content

    def test_write_work_unit_success(self):
        """Should write all work unit files for successful generation."""
        with TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir)

            request = DraftGenRequest(
                transcript_id="T001",
                transcript="Test transcript",
                transcript_path="/path/to/transcript.txt",
                outline=[{"id": "1", "title": "Intro"}],
                style_config={"edition": "ideas"},
            )

            result = DraftGenResult(
                success=True,
                draft_markdown="# Test Draft",
                meta=DraftGenMeta(
                    run_id="T001__essay__c0__abc",
                    transcript_id="T001",
                    candidate_index=0,
                    transcript_path="/path/to/transcript.txt",
                    draft_path="",
                    git_commit="abc123",
                    config_hash="cfg123",
                    prompt_version="ideas_v3",
                    model="gpt-4o-mini",
                    temperature=0.7,
                    routing_version="2026-01-26",
                    backend="local",
                    content_mode="essay",
                    seed=None,
                    normalized_sha256="sha256",
                    generation_time_s=1.5,
                ),
            )

            structure = StructureResult(verdict="PASS")
            groundedness = GroundednessResult(overall_verdict="PASS")
            yield_result = YieldResult(prose_word_count=100)
            gate_row = make_pass_gate_row("T001")

            write_work_unit(
                out_dir=out_dir,
                transcript_id="T001",
                request=request,
                result=result,
                structure=structure,
                groundedness=groundedness,
                yield_result=yield_result,
                gate_row=gate_row,
            )

            work_dir = out_dir / "T001"
            assert work_dir.exists()
            assert (work_dir / "request.json").exists()
            assert (work_dir / "draft_meta.json").exists()
            assert (work_dir / "draft.md").exists()
            assert (work_dir / "structure.json").exists()
            assert (work_dir / "groundedness.json").exists()
            assert (work_dir / "yield.json").exists()
            assert (work_dir / "gate_row.json").exists()

    def test_write_work_unit_failure(self):
        """Should write minimal files for failed generation."""
        with TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir)

            request = DraftGenRequest(
                transcript_id="T001",
                transcript="Test transcript",
                transcript_path="/path/to/transcript.txt",
                outline=[{"id": "1", "title": "Intro"}],
                style_config={"edition": "ideas"},
            )

            result = DraftGenResult(
                success=False,
                error="Generation failed",
                error_code="GENERATION_FAILED",
            )

            gate_row = make_fail_gate_row("T001")

            write_work_unit(
                out_dir=out_dir,
                transcript_id="T001",
                request=request,
                result=result,
                structure=None,
                groundedness=None,
                yield_result=None,
                gate_row=gate_row,
            )

            work_dir = out_dir / "T001"
            assert work_dir.exists()
            assert (work_dir / "request.json").exists()
            assert (work_dir / "gate_row.json").exists()
            # These should NOT exist for failed generation
            assert not (work_dir / "draft.md").exists()
            assert not (work_dir / "structure.json").exists()
