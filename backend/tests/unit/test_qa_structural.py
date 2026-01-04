"""Unit tests for QA structural analysis.

T006: Tests for:
- T009: N-gram repetition detection
- T010: Heading hierarchy validation
- T011: Paragraph length analysis
- T012: Chapter balance analysis
"""

import pytest

from src.models.qa_report import IssueSeverity, IssueType
from src.services.qa_structural import (
    Chapter,
    StructuralAnalysisResult,
    analyze_chapter_balance,
    analyze_paragraph_lengths,
    analyze_structure,
    detect_passive_voice_heavy_sections,
    detect_repetitions,
    extract_paragraphs,
    parse_chapters,
    validate_heading_hierarchy,
)


# ============================================================================
# Markdown Parsing Tests
# ============================================================================

class TestParseChapters:
    """Tests for parse_chapters function."""

    def test_parse_empty_document(self):
        """Empty document returns no chapters."""
        chapters = parse_chapters("")
        assert chapters == []

    def test_parse_single_h1_chapter(self):
        """Single h1 heading creates one chapter."""
        markdown = """# Introduction

This is the introduction content.
"""
        chapters = parse_chapters(markdown)
        assert len(chapters) == 1
        assert chapters[0].heading == "Introduction"
        assert chapters[0].level == 1
        assert chapters[0].index == 0
        assert "introduction content" in chapters[0].content.lower()

    def test_parse_multiple_h1_chapters(self):
        """Multiple h1 headings create multiple chapters."""
        markdown = """# Chapter 1

Content for chapter 1.

# Chapter 2

Content for chapter 2.

# Chapter 3

Content for chapter 3.
"""
        chapters = parse_chapters(markdown)
        assert len(chapters) == 3
        assert [c.heading for c in chapters] == ["Chapter 1", "Chapter 2", "Chapter 3"]
        assert all(c.level == 1 for c in chapters)

    def test_parse_h2_chapters(self):
        """H2 headings also start new chapters."""
        markdown = """## Section 1

Content for section 1.

## Section 2

Content for section 2.
"""
        chapters = parse_chapters(markdown)
        assert len(chapters) == 2
        assert all(c.level == 2 for c in chapters)

    def test_h3_included_in_chapter_content(self):
        """H3+ headings are included in chapter content, not new chapters."""
        markdown = """# Main Chapter

Introduction.

### Subsection A

Subsection content.

### Subsection B

More content.
"""
        chapters = parse_chapters(markdown)
        assert len(chapters) == 1
        assert "### Subsection A" in chapters[0].content
        assert "### Subsection B" in chapters[0].content

    def test_word_count_calculated(self):
        """Word count is correctly calculated for each chapter."""
        markdown = """# Short Chapter

One two three.

# Longer Chapter

One two three four five six seven eight nine ten.
"""
        chapters = parse_chapters(markdown)
        assert chapters[0].word_count == 3
        assert chapters[1].word_count == 10

    def test_start_line_tracked(self):
        """Start line number is tracked for each chapter."""
        markdown = """# First Chapter

Content.

# Second Chapter

More content.
"""
        chapters = parse_chapters(markdown)
        assert chapters[0].start_line == 1
        assert chapters[1].start_line == 5


class TestExtractParagraphs:
    """Tests for extract_paragraphs function."""

    def test_extract_empty_text(self):
        """Empty text returns no paragraphs."""
        paragraphs = extract_paragraphs("")
        assert paragraphs == []

    def test_extract_single_paragraph(self):
        """Single paragraph is extracted."""
        text = "This is a single paragraph."
        paragraphs = extract_paragraphs(text)
        assert paragraphs == ["This is a single paragraph."]

    def test_extract_multiple_paragraphs(self):
        """Multiple paragraphs separated by blank lines."""
        text = """First paragraph.

Second paragraph.

Third paragraph."""
        paragraphs = extract_paragraphs(text)
        assert len(paragraphs) == 3
        assert paragraphs[0] == "First paragraph."
        assert paragraphs[1] == "Second paragraph."
        assert paragraphs[2] == "Third paragraph."

    def test_headings_excluded(self):
        """Headings are not included as paragraphs."""
        text = """# This is a heading

This is a paragraph.

## Another heading

Another paragraph."""
        paragraphs = extract_paragraphs(text)
        assert len(paragraphs) == 2
        assert all(not p.startswith("#") for p in paragraphs)

    def test_whitespace_trimmed(self):
        """Extra whitespace is trimmed from paragraphs."""
        text = """  First paragraph with spaces.

   Second paragraph.   """
        paragraphs = extract_paragraphs(text)
        assert paragraphs[0] == "First paragraph with spaces."
        assert paragraphs[1] == "Second paragraph."


# ============================================================================
# T009: Repetition Detection Tests
# ============================================================================

class TestDetectRepetitions:
    """Tests for T009: N-gram repetition detection."""

    def test_no_repetitions(self):
        """Document without repetitions returns empty list and score 100."""
        markdown = """# Chapter

Each sentence is unique. No phrases repeat here.
The content varies throughout the document.
"""
        issues, score = detect_repetitions(markdown)
        assert len(issues) == 0
        assert score == 100

    def test_detect_repeated_phrase(self):
        """Repeated phrase is detected and flagged."""
        markdown = """# Chapter

The quick brown fox jumps. The quick brown fox runs.
The quick brown fox sleeps. The quick brown fox eats.
"""
        issues, score = detect_repetitions(markdown, threshold=3)
        assert len(issues) > 0
        assert any("quick brown fox" in i.message.lower() for i in issues)
        assert all(i.issue_type == IssueType.repetition for i in issues)
        assert score < 100

    def test_severity_based_on_count(self):
        """Severity increases with repetition count."""
        # Create text with phrase repeated 10+ times for critical severity
        phrase = "the same phrase again"
        repeated = " ".join([phrase] * 12)
        markdown = f"# Chapter\n\n{repeated}"

        issues, score = detect_repetitions(markdown, threshold=3)
        critical_issues = [i for i in issues if i.severity == IssueSeverity.critical]
        assert len(critical_issues) > 0

    def test_short_document_no_issues(self):
        """Very short document doesn't produce false positives."""
        markdown = "# Title\n\nHello."
        issues, score = detect_repetitions(markdown)
        assert len(issues) == 0
        assert score == 100

    def test_metadata_included(self):
        """Issue metadata includes phrase and count."""
        markdown = """# Chapter

The same words appear. The same words here.
The same words again. The same words once more.
"""
        issues, _ = detect_repetitions(markdown, threshold=3)
        if issues:
            assert "phrase" in issues[0].metadata
            assert "count" in issues[0].metadata
            assert issues[0].metadata["count"] >= 3


# ============================================================================
# T010: Heading Hierarchy Tests
# ============================================================================

class TestValidateHeadingHierarchy:
    """Tests for T010: Heading hierarchy validation."""

    def test_valid_hierarchy(self):
        """Valid heading hierarchy produces no issues."""
        markdown = """# Main Title

## Section 1

### Subsection 1.1

## Section 2

### Subsection 2.1

#### Sub-subsection
"""
        issues = validate_heading_hierarchy(markdown)
        assert len(issues) == 0

    def test_skip_h1_to_h3(self):
        """Skipping from h1 to h3 is flagged."""
        markdown = """# Main Title

### Skipped h2

Content here.
"""
        issues = validate_heading_hierarchy(markdown)
        assert len(issues) == 1
        assert issues[0].severity == IssueSeverity.warning
        assert issues[0].issue_type == IssueType.structure
        assert "h1 → h3" in issues[0].message

    def test_skip_h2_to_h4(self):
        """Skipping from h2 to h4 is flagged."""
        markdown = """# Title

## Section

#### Skipped h3

Content.
"""
        issues = validate_heading_hierarchy(markdown)
        assert len(issues) == 1
        assert "h2 → h4" in issues[0].message

    def test_multiple_hierarchy_issues(self):
        """Multiple hierarchy issues are all detected."""
        markdown = """# Title

### Skip 1

##### Skip 2

Content.
"""
        issues = validate_heading_hierarchy(markdown)
        assert len(issues) == 2

    def test_line_number_in_location(self):
        """Line number is included in issue location."""
        markdown = """# Title

### Bad heading
"""
        issues = validate_heading_hierarchy(markdown)
        assert len(issues) == 1
        assert "Line" in issues[0].location


# ============================================================================
# T011: Paragraph Length Tests
# ============================================================================

class TestAnalyzeParagraphLengths:
    """Tests for T011: Paragraph length analysis."""

    def test_normal_paragraphs_no_issues(self):
        """Normal-length paragraphs produce no issues."""
        markdown = """# Chapter

This is a normal paragraph with a reasonable number of words.
It should not trigger any warnings.

Another normal paragraph here.
"""
        issues, score = analyze_paragraph_lengths(markdown)
        assert len(issues) == 0
        assert score == 100

    def test_long_paragraph_warning(self):
        """Paragraph over 300 words triggers warning."""
        # Create paragraph with ~350 words
        long_para = " ".join(["word"] * 350)
        markdown = f"# Chapter\n\n{long_para}"

        issues, score = analyze_paragraph_lengths(markdown)
        assert len(issues) == 1
        assert issues[0].severity == IssueSeverity.warning
        assert issues[0].issue_type == IssueType.clarity
        assert "Long paragraph" in issues[0].message
        assert score < 100

    def test_very_long_paragraph_critical(self):
        """Paragraph over 500 words triggers critical severity."""
        # Create paragraph with ~550 words
        very_long_para = " ".join(["word"] * 550)
        markdown = f"# Chapter\n\n{very_long_para}"

        issues, score = analyze_paragraph_lengths(markdown)
        assert len(issues) == 1
        assert issues[0].severity == IssueSeverity.critical
        assert "Very long paragraph" in issues[0].message

    def test_chapter_context_included(self):
        """Issue includes chapter heading for context."""
        long_para = " ".join(["word"] * 350)
        markdown = f"# My Chapter Title\n\n{long_para}"

        issues, _ = analyze_paragraph_lengths(markdown)
        assert issues[0].heading == "My Chapter Title"
        assert issues[0].chapter_index == 0


class TestDetectPassiveVoice:
    """Tests for passive voice detection."""

    def test_no_passive_voice(self):
        """Active voice text produces no issues."""
        markdown = """# Chapter

The team built the application. Users love the interface.
Developers write clean code. The system processes requests.
"""
        issues = detect_passive_voice_heavy_sections(markdown)
        assert len(issues) == 0

    def test_heavy_passive_voice_detected(self):
        """Heavy passive voice usage is detected."""
        markdown = """# Chapter

The application was built. The interface was designed.
The code was written. The tests were executed.
The results were analyzed. The report was generated.
"""
        issues = detect_passive_voice_heavy_sections(markdown)
        assert len(issues) > 0
        assert issues[0].issue_type == IssueType.clarity
        assert "passive voice" in issues[0].message.lower()

    def test_short_paragraphs_ignored(self):
        """Paragraphs with fewer than 3 sentences are skipped."""
        markdown = """# Chapter

It was done. That was it.
"""
        issues = detect_passive_voice_heavy_sections(markdown)
        assert len(issues) == 0


# ============================================================================
# T012: Chapter Balance Tests
# ============================================================================

class TestAnalyzeChapterBalance:
    """Tests for T012: Chapter balance analysis."""

    def test_balanced_chapters_no_issues(self):
        """Balanced chapters produce no issues."""
        # Create chapters with similar word counts
        content1 = " ".join(["word"] * 100)
        content2 = " ".join(["word"] * 120)
        content3 = " ".join(["word"] * 90)
        markdown = f"""# Chapter 1

{content1}

# Chapter 2

{content2}

# Chapter 3

{content3}
"""
        issues = analyze_chapter_balance(markdown)
        assert len(issues) == 0

    def test_unbalanced_chapters_detected(self):
        """Unbalanced chapters trigger warning."""
        # Create very unbalanced chapters (ratio > 3)
        short_content = " ".join(["word"] * 50)
        long_content = " ".join(["word"] * 500)
        markdown = f"""# Short Chapter

{short_content}

# Long Chapter

{long_content}
"""
        issues = analyze_chapter_balance(markdown)
        assert len(issues) > 0
        assert any("Unbalanced" in i.message for i in issues)
        assert any(i.severity == IssueSeverity.warning for i in issues)

    def test_very_short_chapter_flagged(self):
        """Chapters much shorter than average are flagged."""
        normal = " ".join(["word"] * 200)
        short = " ".join(["word"] * 20)  # Much less than average
        markdown = f"""# Normal 1

{normal}

# Normal 2

{normal}

# Tiny Chapter

{short}

# Normal 3

{normal}
"""
        issues = analyze_chapter_balance(markdown)
        short_issues = [i for i in issues if "Very short chapter" in i.message]
        assert len(short_issues) > 0

    def test_single_chapter_no_issues(self):
        """Single chapter document has no balance issues."""
        markdown = """# Only Chapter

This is the only chapter content.
"""
        issues = analyze_chapter_balance(markdown)
        assert len(issues) == 0

    def test_metadata_included(self):
        """Balance issue metadata includes chapter details."""
        short = " ".join(["word"] * 30)
        long = " ".join(["word"] * 500)
        markdown = f"""# Short

{short}

# Long

{long}
"""
        issues = analyze_chapter_balance(markdown)
        # Find the main balance issue
        balance_issues = [i for i in issues if "Unbalanced" in i.message]
        if balance_issues:
            meta = balance_issues[0].metadata
            assert "longest_chapter" in meta
            assert "shortest_chapter" in meta
            assert "ratio" in meta


# ============================================================================
# Combined Analysis Tests
# ============================================================================

class TestAnalyzeStructure:
    """Tests for combined structural analysis."""

    def test_clean_document(self):
        """Well-structured document gets high scores."""
        markdown = """# Introduction

This is a well-written introduction with varied content.

# Main Content

The main content covers different topics clearly.
Each paragraph is reasonably sized.

# Conclusion

A brief but complete conclusion.
"""
        result = analyze_structure(markdown)
        assert isinstance(result, StructuralAnalysisResult)
        assert result.structure_score >= 90
        assert result.repetition_score >= 90
        assert result.clarity_score >= 90
        assert len(result.issues) == 0

    def test_combines_all_analysis_types(self):
        """Combined analysis includes issues from all analyzers."""
        # Create document with multiple issues
        repeated = "the same phrase here " * 5
        long_para = " ".join(["word"] * 400)
        short_chapter = "tiny"
        long_chapter = " ".join(["word"] * 300)

        markdown = f"""# Chapter 1

{repeated}

### Skipped heading level

{long_para}

# Short One

{short_chapter}

# Long One

{long_chapter}
"""
        result = analyze_structure(markdown)

        # Should have issues from multiple types
        issue_types = {i.issue_type for i in result.issues}
        assert len(issue_types) >= 2  # At least 2 different issue types

    def test_scores_in_valid_range(self):
        """All scores are in valid 1-100 range."""
        # Create problematic document
        markdown = """# Title

### Bad heading

""" + " ".join(["same phrase"] * 50)

        result = analyze_structure(markdown)
        assert 1 <= result.structure_score <= 100
        assert 1 <= result.repetition_score <= 100
        assert 1 <= result.clarity_score <= 100

    def test_issues_have_required_fields(self):
        """All issues have required fields populated."""
        markdown = """# Title

### Skipped level

""" + " ".join(["repeated phrase"] * 10)

        result = analyze_structure(markdown)
        for issue in result.issues:
            assert issue.id is not None
            assert issue.severity is not None
            assert issue.issue_type is not None
            assert issue.message is not None
