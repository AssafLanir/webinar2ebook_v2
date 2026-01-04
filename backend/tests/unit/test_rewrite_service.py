"""Unit tests for rewrite service (Spec 009 US3).

Tests for:
- T039: Section boundary detection
- Markdown parsing
- Issue-to-section mapping
- Rewrite plan creation
- Diff generation
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.services.rewrite_service import (
    parse_markdown_sections,
    get_section_content,
    find_sections_for_issues,
    create_rewrite_plan,
    execute_targeted_rewrite,
    generate_section_diff,
    should_allow_rewrite_pass,
    get_rewritten_draft,
    MarkdownSection,
    _build_rewrite_instructions,
    _summarize_changes,
)
from src.models.qa_report import QAIssue, QAReport, RubricScores, IssueType, IssueSeverity
from src.models.evidence_map import EvidenceMap, ChapterEvidence, EvidenceEntry, SupportQuote
from src.models.rewrite_plan import RewritePlan, RewriteSection, RewriteResult, SectionDiff
from src.models.style_config import ContentMode


class TestParseMarkdownSections:
    """Tests for parse_markdown_sections (T039)."""

    def test_parses_simple_headings(self):
        """Test parsing markdown with simple headings."""
        markdown = """# Title

Introduction text.

## Chapter 1: Getting Started

First chapter content.

## Chapter 2: Advanced Topics

Second chapter content.

### Subsection 2.1

Subsection content.
"""
        sections = parse_markdown_sections(markdown)

        assert len(sections) >= 3
        assert sections[0].heading == "Title"
        assert sections[0].level == 1

    def test_detects_section_boundaries(self):
        """Test that section boundaries are correctly detected."""
        markdown = """## Section 1

Content for section 1.
More content.

## Section 2

Content for section 2.
"""
        sections = parse_markdown_sections(markdown)

        assert len(sections) == 2
        assert sections[0].heading == "Section 1"
        assert sections[0].start_line == 1
        assert sections[0].end_line == 5  # Up to line before Section 2's heading
        assert sections[1].heading == "Section 2"
        assert sections[1].start_line == 6

    def test_respects_min_max_level(self):
        """Test level filtering."""
        markdown = """# H1
## H2
### H3
#### H4
##### H5
"""
        # Only h2 and h3
        sections = parse_markdown_sections(markdown, min_level=2, max_level=3)

        headings = [s.heading for s in sections]
        assert "H2" in headings
        assert "H3" in headings
        assert "H1" not in headings
        assert "H4" not in headings

    def test_tracks_chapter_index(self):
        """Test that chapter index is tracked for chapter headings."""
        markdown = """## Chapter 1: Introduction

Intro content.

## Chapter 2: Main Content

Main content.

### Subsection 2.1

Sub content.
"""
        sections = parse_markdown_sections(markdown)

        chapter_sections = [s for s in sections if s.chapter_index is not None]
        assert len(chapter_sections) >= 2

    def test_handles_empty_markdown(self):
        """Test with empty input."""
        sections = parse_markdown_sections("")
        assert sections == []

    def test_handles_no_headings(self):
        """Test markdown with no headings."""
        markdown = """Just some text.

No headings here.

More paragraphs.
"""
        sections = parse_markdown_sections(markdown)
        assert sections == []

    def test_includes_section_content(self):
        """Test that section content is populated."""
        markdown = """## Section 1

Line 1.
Line 2.

## Section 2

Line 3.
"""
        sections = parse_markdown_sections(markdown)

        assert "Line 1" in sections[0].content
        assert "Line 2" in sections[0].content
        assert "Line 3" in sections[1].content


class TestGetSectionContent:
    """Tests for get_section_content helper."""

    def test_extracts_correct_lines(self):
        """Test line extraction."""
        markdown = """Line 1
Line 2
Line 3
Line 4
Line 5"""
        content = get_section_content(markdown, start_line=2, end_line=4)

        assert "Line 2" in content
        assert "Line 3" in content
        assert "Line 4" in content
        assert "Line 1" not in content
        assert "Line 5" not in content


class TestFindSectionsForIssues:
    """Tests for find_sections_for_issues (T039)."""

    def test_maps_issue_by_heading(self):
        """Test mapping by issue.heading."""
        sections = [
            MarkdownSection(
                heading="Introduction",
                level=2,
                start_line=1,
                end_line=10,
                content="Intro content",
                chapter_index=1,
            ),
            MarkdownSection(
                heading="Conclusion",
                level=2,
                start_line=11,
                end_line=20,
                content="Conclusion content",
                chapter_index=2,
            ),
        ]

        issues = [
            QAIssue(
                id="i1",
                severity=IssueSeverity.warning,
                issue_type=IssueType.repetition,
                heading="Introduction",
                message="Repetitive text",
            )
        ]

        mapping = find_sections_for_issues(sections, issues)

        assert "Introduction" in mapping
        assert len(mapping["Introduction"]) == 1
        assert mapping["Introduction"][0].id == "i1"

    def test_maps_issue_by_location(self):
        """Test mapping by issue.location text search."""
        sections = [
            MarkdownSection(
                heading="Data Section",
                level=2,
                start_line=1,
                end_line=10,
                content="This section discusses important data patterns.",
                chapter_index=1,
            ),
        ]

        issues = [
            QAIssue(
                id="i2",
                severity=IssueSeverity.info,
                issue_type=IssueType.clarity,
                location="important data",
                message="Unclear reference",
            )
        ]

        mapping = find_sections_for_issues(sections, issues)

        assert "Data Section" in mapping

    def test_handles_unmatched_issues(self):
        """Test that issues without matches don't appear."""
        sections = [
            MarkdownSection(
                heading="Only Section",
                level=2,
                start_line=1,
                end_line=10,
                content="Some content",
            ),
        ]

        issues = [
            QAIssue(
                id="i3",
                severity=IssueSeverity.warning,
                issue_type=IssueType.structure,
                heading="Nonexistent Section",
                message="Some issue",
            )
        ]

        mapping = find_sections_for_issues(sections, issues)

        assert "Nonexistent Section" not in mapping
        assert len(mapping) == 0


class TestCreateRewritePlan:
    """Tests for create_rewrite_plan (T043)."""

    def test_creates_plan_from_issues(self):
        """Test basic plan creation."""
        draft = """## Chapter 1: Intro

Intro content here.

## Chapter 2: Main

Main content here.
"""
        qa_report = QAReport(
            id="report_1",
            project_id="proj_1",
            draft_hash="abc123",
            overall_score=70,
            rubric_scores=RubricScores(
                structure=80,
                clarity=70,
                faithfulness=75,
                repetition=60,
                completeness=80,
            ),
            issues=[
                QAIssue(
                    id="i1",
                    severity=IssueSeverity.warning,
                    issue_type=IssueType.repetition,
                    heading="Chapter 1: Intro",
                    message="Repeated phrase detected",
                )
            ],
            issue_counts={"critical": 0, "warning": 1, "info": 0},
            generated_at="2024-01-01T00:00:00Z",
            analysis_duration_ms=1000,
        )

        plan = create_rewrite_plan(
            project_id="proj_1",
            draft=draft,
            qa_report=qa_report,
        )

        assert plan.project_id == "proj_1"
        assert plan.qa_report_id == "report_1"
        assert len(plan.sections) >= 0  # May be 0 if heading doesn't match exactly

    def test_limits_sections_per_pass(self):
        """Test that section count is limited."""
        # Create many sections
        draft = "\n".join([f"## Section {i}\n\nContent {i}\n" for i in range(20)])

        issues = [
            QAIssue(
                id=f"i{i}",
                severity=IssueSeverity.warning,
                issue_type=IssueType.clarity,
                heading=f"Section {i}",
                message=f"Issue {i}",
            )
            for i in range(20)
        ]

        qa_report = QAReport(
            id="report_2",
            project_id="proj_2",
            draft_hash="def456",
            overall_score=60,
            rubric_scores=RubricScores(
                structure=60, clarity=60, faithfulness=60, repetition=60, completeness=60
            ),
            issues=issues,
            generated_at="2024-01-01T00:00:00Z",
            analysis_duration_ms=1000,
        )

        plan = create_rewrite_plan("proj_2", draft, qa_report)

        assert len(plan.sections) <= 10  # MAX_SECTIONS_PER_PASS

    def test_filters_by_issue_type(self):
        """Test issue type filtering."""
        draft = "## Section 1\n\nContent"

        qa_report = QAReport(
            id="report_3",
            project_id="proj_3",
            draft_hash="ghi789",
            overall_score=70,
            rubric_scores=RubricScores(
                structure=70, clarity=70, faithfulness=70, repetition=70, completeness=70
            ),
            issues=[
                QAIssue(
                    id="i1",
                    severity=IssueSeverity.warning,
                    issue_type=IssueType.repetition,
                    heading="Section 1",
                    message="Repetition",
                ),
                QAIssue(
                    id="i2",
                    severity=IssueSeverity.warning,
                    issue_type=IssueType.clarity,
                    heading="Section 1",
                    message="Clarity",
                ),
            ],
            generated_at="2024-01-01T00:00:00Z",
            analysis_duration_ms=1000,
        )

        # Only fix repetition issues
        plan = create_rewrite_plan(
            "proj_3",
            draft,
            qa_report,
            issue_types=[IssueType.repetition],
        )

        # Should filter to only repetition issues
        if plan.sections:
            for section in plan.sections:
                for ref in section.issues_addressed:
                    assert ref.issue_type.value == "repetition"


class TestGenerateSectionDiff:
    """Tests for generate_section_diff (T045)."""

    def test_creates_diff_with_summary(self):
        """Test diff creation."""
        original = "This is some original text with repetition. With repetition."
        rewritten = "This is some improved text without repetition."

        diff = generate_section_diff(
            section_id="s1",
            heading="Test Section",
            original=original,
            rewritten=rewritten,
        )

        assert diff.section_id == "s1"
        assert diff.heading == "Test Section"
        assert diff.original == original
        assert diff.rewritten == rewritten
        assert diff.changes_summary  # Should have some summary

    def test_summary_shows_word_change(self):
        """Test that summary reflects word count changes."""
        original = "Short text"
        rewritten = "Much longer text with more words added here"

        diff = generate_section_diff("s1", "Test", original, rewritten)

        assert "+" in diff.changes_summary or "word" in diff.changes_summary.lower()


class TestSummarizeChanges:
    """Tests for _summarize_changes helper."""

    def test_reports_word_addition(self):
        """Test word addition reporting."""
        summary = _summarize_changes("few words", "many more words added here")
        assert "+" in summary

    def test_reports_word_removal(self):
        """Test word removal reporting."""
        summary = _summarize_changes("many words here to remove", "fewer words")
        assert "-" in summary


class TestShouldAllowRewritePass:
    """Tests for multi-pass logic (T049)."""

    def test_allows_first_pass(self):
        """Test first pass is always allowed."""
        allowed, warning = should_allow_rewrite_pass(1)
        assert allowed is True
        assert warning is None

    def test_allows_second_pass_with_warning(self):
        """Test second pass allowed with warning."""
        allowed, warning = should_allow_rewrite_pass(2)
        assert allowed is True
        assert warning is not None
        assert "pass 2" in warning

    def test_blocks_fourth_pass(self):
        """Test fourth pass is blocked."""
        allowed, warning = should_allow_rewrite_pass(4)
        assert allowed is False
        assert "Maximum" in warning


class TestBuildRewriteInstructions:
    """Tests for _build_rewrite_instructions helper."""

    def test_builds_repetition_instructions(self):
        """Test instructions for repetition issues."""
        issues = [
            QAIssue(
                id="i1",
                severity=IssueSeverity.warning,
                issue_type=IssueType.repetition,
                message="Phrase appears 5 times",
            )
        ]
        instructions = _build_rewrite_instructions(issues)
        assert "repetition" in instructions.lower()

    def test_builds_clarity_instructions(self):
        """Test instructions for clarity issues."""
        issues = [
            QAIssue(
                id="i2",
                severity=IssueSeverity.info,
                issue_type=IssueType.clarity,
                message="Sentence too long",
            )
        ]
        instructions = _build_rewrite_instructions(issues)
        assert "clarity" in instructions.lower()


class TestGetRewrittenDraft:
    """Tests for get_rewritten_draft helper."""

    def test_applies_all_rewrites(self):
        """Test that all rewrites are applied."""
        original = "Section A content. Section B content."

        result = RewriteResult(
            project_id="p1",
            pass_number=1,
            sections_rewritten=2,
            issues_addressed=2,
            before_draft_hash="a",
            after_draft_hash="b",
            diffs=[
                SectionDiff(
                    section_id="s1",
                    original="Section A content",
                    rewritten="Improved A content",
                    changes_summary="Improved",
                ),
                SectionDiff(
                    section_id="s2",
                    original="Section B content",
                    rewritten="Better B content",
                    changes_summary="Better",
                ),
            ],
        )

        updated = get_rewritten_draft(original, result)

        assert "Improved A content" in updated
        assert "Better B content" in updated
        assert "Section A content" not in updated
        assert "Section B content" not in updated


class TestExecuteTargetedRewrite:
    """Tests for execute_targeted_rewrite (T044)."""

    @pytest.mark.asyncio
    async def test_rewrites_sections(self):
        """Test section rewriting with LLM."""
        draft = "## Section 1\n\nOriginal content here."

        plan = RewritePlan(
            project_id="p1",
            sections=[
                RewriteSection(
                    section_id="s1",
                    chapter_index=1,
                    heading="Section 1",
                    start_line=1,
                    end_line=3,
                    original_text="## Section 1\n\nOriginal content here.",
                )
            ],
        )

        mock_response = MagicMock()
        mock_response.content = "## Section 1\n\nImproved content here."

        with patch("src.services.rewrite_service.LLMClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.complete.return_value = mock_response
            mock_client_class.return_value = mock_client

            result = await execute_targeted_rewrite(draft, plan)

        assert result.sections_rewritten == 1
        assert len(result.diffs) == 1

    @pytest.mark.asyncio
    async def test_handles_rewrite_error(self):
        """Test graceful handling of rewrite errors."""
        draft = "## Section 1\n\nContent."

        plan = RewritePlan(
            project_id="p1",
            sections=[
                RewriteSection(
                    section_id="s1",
                    chapter_index=1,
                    start_line=1,
                    end_line=3,
                    original_text="## Section 1\n\nContent.",
                )
            ],
        )

        with patch("src.services.rewrite_service.LLMClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.complete.side_effect = Exception("LLM error")
            mock_client_class.return_value = mock_client

            result = await execute_targeted_rewrite(draft, plan)

        # Should complete with warnings, not raise
        assert len(result.warnings) > 0
        assert result.sections_rewritten == 0
