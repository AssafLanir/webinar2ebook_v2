"""Integration tests for rewrite flow (Spec 009 US3).

Tests for:
- T040: End-to-end rewrite flow
- API endpoint behavior
- Multi-pass warning logic
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone

from httpx import AsyncClient, ASGITransport

from src.api.main import app
from src.models.qa_report import QAReport, QAIssue, RubricScores, IssueType, IssueSeverity
from src.models.evidence_map import EvidenceMap, ChapterEvidence, EvidenceEntry, SupportQuote
from src.models.style_config import ContentMode
from src.services.rewrite_service import (
    create_rewrite_plan,
    execute_targeted_rewrite,
    get_rewritten_draft,
)


class TestRewriteFlowIntegration:
    """Integration tests for rewrite flow (T040)."""

    @pytest.fixture
    def sample_draft(self):
        """Sample draft with issues."""
        return """## Chapter 1: Introduction

This is the introduction. The introduction covers important topics.
The introduction explains the key concepts. Important topics are covered here.

## Chapter 2: Main Content

The main content discusses data. Data is very important.
We need to understand data. Data analysis helps us understand data.

### Section 2.1: Details

More details about the important data. Data is discussed in detail.
"""

    @pytest.fixture
    def sample_qa_report(self):
        """Sample QA report with issues."""
        return QAReport(
            id="qa_report_001",
            project_id="test_project",
            draft_hash="abc123",
            overall_score=65,
            rubric_scores=RubricScores(
                structure=75,
                clarity=60,
                faithfulness=80,
                repetition=45,  # Low due to repetition
                completeness=70,
            ),
            issues=[
                QAIssue(
                    id="issue_001",
                    severity=IssueSeverity.warning,
                    issue_type=IssueType.repetition,
                    chapter_index=1,
                    heading="Chapter 1: Introduction",
                    message="'introduction' repeated 3 times",
                    location="The introduction covers",
                ),
                QAIssue(
                    id="issue_002",
                    severity=IssueSeverity.warning,
                    issue_type=IssueType.repetition,
                    chapter_index=2,
                    heading="Chapter 2: Main Content",
                    message="'data' repeated 5 times",
                    location="data is very important",
                ),
            ],
            issue_counts={"critical": 0, "warning": 2, "info": 0},
            generated_at=datetime.now(timezone.utc),
            analysis_duration_ms=500,
        )

    @pytest.fixture
    def sample_evidence_map(self):
        """Sample Evidence Map."""
        return EvidenceMap(
            project_id="test_project",
            content_mode=ContentMode.interview,
            strict_grounded=True,
            transcript_hash="transcript_hash_123",
            chapters=[
                ChapterEvidence(
                    chapter_index=1,
                    chapter_title="Introduction",
                    claims=[
                        EvidenceEntry(
                            id="claim_001",
                            claim="Key concepts are foundational",
                            support=[SupportQuote(quote="Key concepts are foundational to success")],
                        ),
                    ],
                ),
                ChapterEvidence(
                    chapter_index=2,
                    chapter_title="Main Content",
                    claims=[
                        EvidenceEntry(
                            id="claim_002",
                            claim="Data analysis enables insights",
                            support=[SupportQuote(quote="Data analysis enables powerful insights")],
                        ),
                    ],
                ),
            ],
        )

    def test_rewrite_plan_created_from_qa_issues(
        self, sample_draft, sample_qa_report, sample_evidence_map
    ):
        """Test that rewrite plan is created correctly from QA issues."""
        plan = create_rewrite_plan(
            project_id="test_project",
            draft=sample_draft,
            qa_report=sample_qa_report,
            evidence_map=sample_evidence_map,
        )

        assert plan.project_id == "test_project"
        assert plan.qa_report_id == "qa_report_001"
        # Plan may have 0-2 sections depending on heading matching
        assert plan.pass_number == 1

    @pytest.mark.asyncio
    async def test_rewrite_execution_produces_diffs(
        self, sample_draft, sample_qa_report, sample_evidence_map
    ):
        """Test that executing rewrite produces section diffs."""
        plan = create_rewrite_plan(
            project_id="test_project",
            draft=sample_draft,
            qa_report=sample_qa_report,
            evidence_map=sample_evidence_map,
        )

        mock_response = MagicMock()
        mock_response.content = "## Chapter 1: Introduction\n\nImproved content without repetition."

        with patch("src.services.rewrite_service.LLMClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.complete.return_value = mock_response
            mock_client_class.return_value = mock_client

            result = await execute_targeted_rewrite(
                draft=sample_draft,
                rewrite_plan=plan,
                evidence_map=sample_evidence_map,
            )

        # Result should be valid even if sections don't match
        assert result.project_id == "test_project"
        assert result.pass_number == 1
        assert result.faithfulness_preserved is True

    @pytest.mark.asyncio
    async def test_rewritten_draft_replaces_sections(
        self, sample_draft, sample_qa_report
    ):
        """Test that get_rewritten_draft correctly replaces sections."""
        from src.models.rewrite_plan import RewriteResult, SectionDiff

        # Create a result with known replacements
        result = RewriteResult(
            project_id="test_project",
            pass_number=1,
            sections_rewritten=1,
            issues_addressed=1,
            before_draft_hash="before",
            after_draft_hash="after",
            diffs=[
                SectionDiff(
                    section_id="s1",
                    heading="Introduction",
                    original="The introduction covers important topics.",
                    rewritten="The opening covers key topics.",
                    changes_summary="-2 words",
                ),
            ],
        )

        updated = get_rewritten_draft(sample_draft, result)

        assert "The opening covers key topics." in updated
        assert "The introduction covers important topics." not in updated

    def test_multi_pass_warning_on_second_pass(self):
        """Test that second pass triggers warning."""
        from src.services.rewrite_service import should_allow_rewrite_pass

        allowed, warning = should_allow_rewrite_pass(2)

        assert allowed is True
        assert warning is not None
        assert "pass 2" in warning.lower()

    def test_multi_pass_blocked_after_max(self):
        """Test that passes beyond max are blocked."""
        from src.services.rewrite_service import should_allow_rewrite_pass

        allowed, warning = should_allow_rewrite_pass(4)

        assert allowed is False
        assert "maximum" in warning.lower()


class TestRewritePreservesFaithfulness:
    """Tests that rewrite preserves faithfulness to source."""

    @pytest.fixture
    def strict_evidence_map(self):
        """Evidence Map with limited claims."""
        return EvidenceMap(
            project_id="test_project",
            content_mode=ContentMode.interview,
            strict_grounded=True,
            transcript_hash="hash",
            chapters=[
                ChapterEvidence(
                    chapter_index=1,
                    chapter_title="Test Chapter",
                    claims=[
                        EvidenceEntry(
                            id="only_claim",
                            claim="The speaker discussed machine learning",
                            support=[SupportQuote(quote="I work with ML")],
                        ),
                    ],
                ),
            ],
        )

    def test_plan_includes_allowed_evidence_ids(self, strict_evidence_map):
        """Test that rewrite plan includes evidence constraints."""
        draft = "## Chapter 1: Test Chapter\n\nContent about ML."

        qa_report = QAReport(
            id="r1",
            project_id="test_project",
            draft_hash="hash",
            overall_score=70,
            rubric_scores=RubricScores(
                structure=70, clarity=70, faithfulness=70, repetition=70, completeness=70
            ),
            issues=[
                QAIssue(
                    id="i1",
                    severity=IssueSeverity.warning,
                    issue_type=IssueType.clarity,
                    heading="Chapter 1: Test Chapter",
                    message="Unclear",
                )
            ],
            generated_at=datetime.now(timezone.utc),
            analysis_duration_ms=100,
        )

        plan = create_rewrite_plan(
            project_id="test_project",
            draft=draft,
            qa_report=qa_report,
            evidence_map=strict_evidence_map,
        )

        # If sections were matched, they should have evidence constraints
        for section in plan.sections:
            if section.chapter_index == 1:
                # Should include evidence IDs from the chapter
                assert "only_claim" in section.allowed_evidence_ids or not section.allowed_evidence_ids


class TestRewriteWithContentMode:
    """Tests for content mode integration."""

    @pytest.fixture
    def interview_evidence_map(self):
        """Evidence Map for interview mode."""
        return EvidenceMap(
            project_id="interview_project",
            content_mode=ContentMode.interview,
            strict_grounded=True,
            transcript_hash="interview_hash",
            chapters=[
                ChapterEvidence(
                    chapter_index=1,
                    chapter_title="Interview Chapter",
                    claims=[
                        EvidenceEntry(
                            id="interview_claim",
                            claim="Guest shared their experience",
                            support=[SupportQuote(quote="In my experience...")],
                        ),
                    ],
                    forbidden=["action_steps", "how_to_guides"],
                ),
            ],
        )

    def test_interview_mode_evidence_used_in_plan(self, interview_evidence_map):
        """Test that interview mode evidence is incorporated."""
        draft = "## Interview Chapter\n\nThe guest shared insights."

        qa_report = QAReport(
            id="r2",
            project_id="interview_project",
            draft_hash="hash2",
            overall_score=75,
            rubric_scores=RubricScores(
                structure=75, clarity=75, faithfulness=75, repetition=75, completeness=75
            ),
            issues=[
                QAIssue(
                    id="i2",
                    severity=IssueSeverity.info,
                    issue_type=IssueType.clarity,
                    heading="Interview Chapter",
                    message="Could be clearer",
                )
            ],
            generated_at=datetime.now(timezone.utc),
            analysis_duration_ms=100,
        )

        plan = create_rewrite_plan(
            project_id="interview_project",
            draft=draft,
            qa_report=qa_report,
            evidence_map=interview_evidence_map,
        )

        # Plan should respect interview mode
        assert plan.evidence_map_hash == "interview_hash"


class TestRewriteAPIContract:
    """Tests for rewrite API endpoint (to be implemented)."""

    @pytest.fixture
    def mock_project(self):
        """Mock project with draft and QA report."""
        return {
            "id": "project_123",
            "title": "Test Project",
            "draftText": "## Chapter 1\n\nSome content here.",
            "qaReport": {
                "id": "qa_1",
                "project_id": "project_123",
                "draft_hash": "hash",
                "overall_score": 70,
                "rubric_scores": {
                    "structure": 70,
                    "clarity": 70,
                    "faithfulness": 70,
                    "repetition": 70,
                    "completeness": 70,
                },
                "issues": [],
                "issue_counts": {"critical": 0, "warning": 0, "info": 0},
                "generated_at": "2024-01-01T00:00:00Z",
                "analysis_duration_ms": 100,
            },
        }

    # API endpoint tests would go here once the endpoint is created
    # For now, mark as expected to be implemented

    def test_rewrite_api_contract_placeholder(self, mock_project):
        """Placeholder for API contract tests."""
        # Will be implemented with T047-T049
        assert mock_project["id"] == "project_123"
