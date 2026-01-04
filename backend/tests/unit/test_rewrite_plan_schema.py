"""Schema contract tests for Rewrite Plan models (Spec 009 US3).

These tests ensure the Rewrite Plan models serialize/deserialize correctly
and maintain schema compatibility.
"""

import pytest
from datetime import datetime, timezone

from src.models.rewrite_plan import (
    RewritePlan,
    RewriteSection,
    RewriteResult,
    SectionDiff,
    IssueReference,
    IssueTypeEnum,
)


class TestIssueReference:
    """Tests for IssueReference model."""

    def test_minimal_reference(self):
        """Test IssueReference with required fields only."""
        ref = IssueReference(
            issue_id="issue_001",
            issue_type=IssueTypeEnum.repetition
        )
        assert ref.issue_id == "issue_001"
        assert ref.issue_type == IssueTypeEnum.repetition
        assert ref.issue_message is None

    def test_full_reference(self):
        """Test IssueReference with all fields."""
        ref = IssueReference(
            issue_id="issue_002",
            issue_type=IssueTypeEnum.clarity,
            issue_message="Sentence is too complex"
        )
        assert ref.issue_id == "issue_002"
        assert ref.issue_type == IssueTypeEnum.clarity
        assert ref.issue_message == "Sentence is too complex"

    def test_extra_fields_forbidden(self):
        """Test that extra fields are rejected."""
        with pytest.raises(Exception):
            IssueReference(
                issue_id="test",
                issue_type=IssueTypeEnum.repetition,
                extra_field="not allowed"
            )


class TestRewriteSection:
    """Tests for RewriteSection model."""

    def test_minimal_section(self):
        """Test RewriteSection with required fields only."""
        section = RewriteSection(
            section_id="sec_001",
            chapter_index=1,
            start_line=10,
            end_line=20,
            original_text="Original paragraph text here."
        )
        assert section.section_id == "sec_001"
        assert section.chapter_index == 1
        assert section.heading is None
        assert section.start_line == 10
        assert section.end_line == 20
        assert section.original_text == "Original paragraph text here."
        assert section.issues_addressed == []
        assert section.allowed_evidence_ids == []
        assert "heading" in section.preserve
        assert "bullet_structure" in section.preserve

    def test_full_section(self):
        """Test RewriteSection with all fields."""
        section = RewriteSection(
            section_id="sec_002",
            chapter_index=3,
            heading="## Key Insights",
            start_line=50,
            end_line=75,
            original_text="The original content with issues...",
            issues_addressed=[
                IssueReference(
                    issue_id="issue_001",
                    issue_type=IssueTypeEnum.repetition,
                    issue_message="Repeated phrase 'very important'"
                ),
                IssueReference(
                    issue_id="issue_002",
                    issue_type=IssueTypeEnum.clarity,
                    issue_message="Sentence too long"
                ),
            ],
            allowed_evidence_ids=["claim_001", "claim_002", "claim_003"],
            rewrite_instructions="Simplify the prose and remove repeated phrases",
            preserve=["heading", "bullet_structure", "links"]
        )
        assert section.heading == "## Key Insights"
        assert len(section.issues_addressed) == 2
        assert len(section.allowed_evidence_ids) == 3
        assert section.rewrite_instructions is not None

    def test_chapter_index_positive(self):
        """Test chapter_index must be >= 1."""
        with pytest.raises(Exception):
            RewriteSection(
                section_id="bad",
                chapter_index=0,
                start_line=1,
                end_line=10,
                original_text="Test"
            )

    def test_line_numbers_positive(self):
        """Test line numbers must be >= 1."""
        with pytest.raises(Exception):
            RewriteSection(
                section_id="bad",
                chapter_index=1,
                start_line=0,  # Invalid
                end_line=10,
                original_text="Test"
            )


class TestRewritePlan:
    """Tests for RewritePlan model."""

    def test_minimal_plan(self):
        """Test RewritePlan with required fields only."""
        plan = RewritePlan(project_id="proj_123")
        assert plan.version == 1
        assert plan.project_id == "proj_123"
        assert plan.qa_report_id is None
        assert plan.evidence_map_hash is None
        assert plan.pass_number == 1
        assert plan.sections == []
        assert len(plan.global_constraints) == 3  # Default constraints

    def test_full_plan(self):
        """Test RewritePlan with all fields."""
        plan = RewritePlan(
            version=1,
            project_id="proj_456",
            qa_report_id="qa_789",
            evidence_map_hash="emap_hash_abc",
            created_at=datetime(2024, 1, 15, 12, 0, tzinfo=timezone.utc),
            pass_number=2,
            sections=[
                RewriteSection(
                    section_id="sec_001",
                    chapter_index=1,
                    start_line=1,
                    end_line=10,
                    original_text="Test section"
                )
            ],
            global_constraints=[
                "Do not add claims not in evidence map",
                "Preserve all heading levels",
                "Maintain existing markdown formatting",
                "Keep paragraph structure"
            ]
        )
        assert plan.qa_report_id == "qa_789"
        assert plan.pass_number == 2
        assert len(plan.sections) == 1
        assert len(plan.global_constraints) == 4

    def test_pass_number_bounds(self):
        """Test pass_number is bounded 1-3."""
        with pytest.raises(Exception):
            RewritePlan(project_id="test", pass_number=0)

        with pytest.raises(Exception):
            RewritePlan(project_id="test", pass_number=4)

    def test_serialization_roundtrip(self):
        """Test RewritePlan serializes and deserializes correctly."""
        original = RewritePlan(
            project_id="proj_roundtrip",
            qa_report_id="qa_test",
            pass_number=1,
            sections=[
                RewriteSection(
                    section_id="sec_001",
                    chapter_index=2,
                    heading="## Test Heading",
                    start_line=20,
                    end_line=30,
                    original_text="Original content here",
                    issues_addressed=[
                        IssueReference(
                            issue_id="i1",
                            issue_type=IssueTypeEnum.faithfulness
                        )
                    ]
                )
            ]
        )

        # Serialize to dict
        data = original.model_dump()

        # Deserialize back
        restored = RewritePlan.model_validate(data)

        assert restored.project_id == original.project_id
        assert len(restored.sections) == 1
        assert restored.sections[0].heading == "## Test Heading"


class TestSectionDiff:
    """Tests for SectionDiff model."""

    def test_minimal_diff(self):
        """Test SectionDiff with required fields."""
        diff = SectionDiff(
            section_id="sec_001",
            original="Original text",
            rewritten="Improved text",
            changes_summary="Simplified phrasing"
        )
        assert diff.section_id == "sec_001"
        assert diff.heading is None
        assert diff.original == "Original text"
        assert diff.rewritten == "Improved text"

    def test_full_diff(self):
        """Test SectionDiff with all fields."""
        diff = SectionDiff(
            section_id="sec_002",
            heading="## Results",
            original="The results were very very important and significant.",
            rewritten="The results were significant.",
            changes_summary="Removed redundant 'very very' and 'important'"
        )
        assert diff.heading == "## Results"


class TestRewriteResult:
    """Tests for RewriteResult model."""

    def test_minimal_result(self):
        """Test RewriteResult with required fields."""
        result = RewriteResult(
            project_id="proj_123",
            pass_number=1,
            sections_rewritten=3,
            issues_addressed=5,
            before_draft_hash="hash_before",
            after_draft_hash="hash_after"
        )
        assert result.project_id == "proj_123"
        assert result.sections_rewritten == 3
        assert result.issues_addressed == 5
        assert result.faithfulness_preserved is True  # default
        assert result.diffs == []
        assert result.warnings == []

    def test_full_result(self):
        """Test RewriteResult with all fields."""
        result = RewriteResult(
            project_id="proj_456",
            pass_number=2,
            sections_rewritten=2,
            issues_addressed=4,
            before_draft_hash="hash_v1",
            after_draft_hash="hash_v2",
            diffs=[
                SectionDiff(
                    section_id="sec_001",
                    heading="## Intro",
                    original="Old text",
                    rewritten="New text",
                    changes_summary="Clarified intro"
                )
            ],
            faithfulness_preserved=True,
            warnings=["One section had low confidence rewrite"]
        )
        assert len(result.diffs) == 1
        assert len(result.warnings) == 1


class TestIssueTypeEnum:
    """Tests for IssueTypeEnum."""

    def test_all_issue_types(self):
        """Test all issue types are valid."""
        assert IssueTypeEnum.repetition.value == "repetition"
        assert IssueTypeEnum.clarity.value == "clarity"
        assert IssueTypeEnum.faithfulness.value == "faithfulness"
        assert IssueTypeEnum.structure.value == "structure"
        assert IssueTypeEnum.completeness.value == "completeness"
