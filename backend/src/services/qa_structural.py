"""Structural QA analysis using regex-based detection.

Fast, deterministic analysis for:
- T009: N-gram repetition detection
- T010: Heading hierarchy validation
- T011: Paragraph length analysis
- T012: Chapter balance analysis

No LLM calls - pure Python text processing.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Optional

from src.models.qa_report import QAIssue, IssueSeverity, IssueType


# ============================================================================
# Configuration
# ============================================================================

# Repetition detection
MIN_NGRAM_SIZE = 3  # Minimum words in a phrase
MAX_NGRAM_SIZE = 8  # Maximum words in a phrase
REPETITION_THRESHOLD = 3  # Minimum occurrences to flag

# Paragraph analysis
MAX_PARAGRAPH_WORDS = 300  # Warning threshold
CRITICAL_PARAGRAPH_WORDS = 500  # Critical threshold

# Chapter balance
MAX_CHAPTER_RATIO = 3.0  # Max allowed ratio between longest/shortest

# Heading hierarchy
HEADING_PATTERN = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)

# Passive voice detection (simple heuristic)
PASSIVE_PATTERNS = [
    r'\b(?:is|are|was|were|been|being)\s+\w+ed\b',
    r'\b(?:is|are|was|were|been|being)\s+\w+en\b',  # e.g., "was taken"
]
PASSIVE_RE = re.compile('|'.join(PASSIVE_PATTERNS), re.IGNORECASE)


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class Chapter:
    """Parsed chapter from markdown."""
    index: int
    heading: str
    level: int
    content: str
    word_count: int
    start_line: int


@dataclass
class StructuralAnalysisResult:
    """Results from structural analysis."""
    issues: list[QAIssue]
    structure_score: int  # 1-100
    repetition_score: int  # 1-100 (100 = no repetition)
    clarity_score: int  # 1-100


# ============================================================================
# Markdown Parsing
# ============================================================================

def parse_chapters(markdown: str) -> list[Chapter]:
    """Parse markdown into chapters based on h1/h2 headings."""
    chapters: list[Chapter] = []
    lines = markdown.split('\n')

    current_chapter: Optional[Chapter] = None
    current_content_lines: list[str] = []

    for line_num, line in enumerate(lines, start=1):
        heading_match = HEADING_PATTERN.match(line)

        if heading_match:
            level = len(heading_match.group(1))
            heading_text = heading_match.group(2).strip()

            # Only h1 and h2 start new chapters
            if level <= 2:
                # Save previous chapter
                if current_chapter is not None:
                    content = '\n'.join(current_content_lines)
                    current_chapter.content = content
                    current_chapter.word_count = len(content.split())
                    chapters.append(current_chapter)

                # Start new chapter
                current_chapter = Chapter(
                    index=len(chapters),
                    heading=heading_text,
                    level=level,
                    content="",
                    word_count=0,
                    start_line=line_num
                )
                current_content_lines = []
            else:
                # h3+ is part of current chapter content
                current_content_lines.append(line)
        else:
            current_content_lines.append(line)

    # Save last chapter
    if current_chapter is not None:
        content = '\n'.join(current_content_lines)
        current_chapter.content = content
        current_chapter.word_count = len(content.split())
        chapters.append(current_chapter)

    return chapters


def extract_paragraphs(text: str) -> list[str]:
    """Extract paragraphs from text (split by blank lines)."""
    # Split by one or more blank lines
    paragraphs = re.split(r'\n\s*\n', text)
    # Filter out empty paragraphs and headings
    return [
        p.strip() for p in paragraphs
        if p.strip() and not p.strip().startswith('#')
    ]


# ============================================================================
# T009: N-gram Repetition Detection
# ============================================================================

def detect_repetitions(
    markdown: str,
    min_ngram: int = MIN_NGRAM_SIZE,
    max_ngram: int = MAX_NGRAM_SIZE,
    threshold: int = REPETITION_THRESHOLD,
) -> tuple[list[QAIssue], int]:
    """Detect repeated phrases across the document.

    Returns:
        Tuple of (issues, repetition_score)
        repetition_score: 100 = no repetition, lower = more repetition
    """
    issues: list[QAIssue] = []

    # Normalize text: lowercase, remove punctuation for matching
    text = re.sub(r'[^\w\s]', ' ', markdown.lower())
    words = text.split()

    if len(words) < min_ngram:
        return issues, 100

    # Count n-grams of various sizes
    all_repeated: dict[str, int] = {}

    for n in range(min_ngram, min(max_ngram + 1, len(words))):
        ngrams = [' '.join(words[i:i+n]) for i in range(len(words) - n + 1)]
        counts = Counter(ngrams)

        for phrase, count in counts.items():
            if count >= threshold:
                # Avoid counting subphrases if superphrase is already counted
                if not any(phrase in existing for existing in all_repeated):
                    all_repeated[phrase] = count

    # Sort by count descending, take top issues
    sorted_repeated = sorted(all_repeated.items(), key=lambda x: -x[1])

    issue_num = 0
    for phrase, count in sorted_repeated[:20]:  # Limit to 20 repetition issues
        severity = IssueSeverity.critical if count >= 10 else (
            IssueSeverity.warning if count >= 5 else IssueSeverity.info
        )

        issues.append(QAIssue(
            id=f"rep-{issue_num}",
            severity=severity,
            issue_type=IssueType.repetition,
            message=f"Phrase '{phrase}' repeated {count} times",
            suggestion=f"Consider varying this phrase or combining repeated sections",
            metadata={"phrase": phrase, "count": count, "ngram_size": len(phrase.split())}
        ))
        issue_num += 1

    # Calculate score: 100 = no repetition, 0 = heavy repetition
    if not all_repeated:
        score = 100
    else:
        # Score based on worst repetition
        max_count = max(all_repeated.values())
        total_repeated_words = sum(
            len(phrase.split()) * count for phrase, count in all_repeated.items()
        )
        repetition_ratio = min(total_repeated_words / max(len(words), 1), 1.0)
        score = max(1, int(100 * (1 - repetition_ratio * 0.8)))  # Cap impact at 80%

    return issues, score


# ============================================================================
# T010: Heading Hierarchy Validation
# ============================================================================

def validate_heading_hierarchy(markdown: str) -> list[QAIssue]:
    """Check for heading level skip issues (e.g., h1 -> h3)."""
    issues: list[QAIssue] = []
    lines = markdown.split('\n')

    prev_level = 0
    issue_num = 0

    for line_num, line in enumerate(lines, start=1):
        match = HEADING_PATTERN.match(line)
        if match:
            level = len(match.group(1))
            heading_text = match.group(2).strip()

            # Check for skipped levels (e.g., h1 -> h3)
            if prev_level > 0 and level > prev_level + 1:
                issues.append(QAIssue(
                    id=f"struct-{issue_num}",
                    severity=IssueSeverity.warning,
                    issue_type=IssueType.structure,
                    heading=heading_text,
                    location=f"Line {line_num}",
                    message=f"Heading level skipped: h{prev_level} → h{level}",
                    suggestion=f"Use h{prev_level + 1} instead of h{level}",
                    metadata={"prev_level": prev_level, "current_level": level, "line": line_num}
                ))
                issue_num += 1

            prev_level = level

    return issues


# ============================================================================
# T011: Paragraph Length Analysis
# ============================================================================

def analyze_paragraph_lengths(markdown: str) -> tuple[list[QAIssue], int]:
    """Check for overly long paragraphs.

    Returns:
        Tuple of (issues, clarity_score)
    """
    issues: list[QAIssue] = []
    chapters = parse_chapters(markdown)

    long_paragraphs = 0
    total_paragraphs = 0
    issue_num = 0

    for chapter in chapters:
        paragraphs = extract_paragraphs(chapter.content)

        for para in paragraphs:
            total_paragraphs += 1
            word_count = len(para.split())

            if word_count > CRITICAL_PARAGRAPH_WORDS:
                long_paragraphs += 1
                issues.append(QAIssue(
                    id=f"clarity-{issue_num}",
                    severity=IssueSeverity.critical,
                    issue_type=IssueType.clarity,
                    chapter_index=chapter.index,
                    heading=chapter.heading,
                    location=para[:100] + "..." if len(para) > 100 else para,
                    message=f"Very long paragraph ({word_count} words)",
                    suggestion="Break into smaller paragraphs (aim for 100-150 words)",
                    metadata={"word_count": word_count}
                ))
                issue_num += 1
            elif word_count > MAX_PARAGRAPH_WORDS:
                long_paragraphs += 1
                issues.append(QAIssue(
                    id=f"clarity-{issue_num}",
                    severity=IssueSeverity.warning,
                    issue_type=IssueType.clarity,
                    chapter_index=chapter.index,
                    heading=chapter.heading,
                    location=para[:100] + "..." if len(para) > 100 else para,
                    message=f"Long paragraph ({word_count} words)",
                    suggestion="Consider breaking into smaller paragraphs",
                    metadata={"word_count": word_count}
                ))
                issue_num += 1

    # Calculate clarity score
    if total_paragraphs == 0:
        score = 100
    else:
        long_ratio = long_paragraphs / total_paragraphs
        score = max(1, int(100 * (1 - long_ratio)))

    return issues, score


def detect_passive_voice_heavy_sections(markdown: str) -> list[QAIssue]:
    """Flag sections with heavy passive voice usage."""
    issues: list[QAIssue] = []
    chapters = parse_chapters(markdown)
    issue_num = 0

    for chapter in chapters:
        paragraphs = extract_paragraphs(chapter.content)

        for para in paragraphs:
            sentences = re.split(r'[.!?]+', para)
            sentences = [s.strip() for s in sentences if s.strip()]

            if len(sentences) < 3:
                continue

            passive_count = sum(1 for s in sentences if PASSIVE_RE.search(s))
            passive_ratio = passive_count / len(sentences)

            # Flag if more than 40% of sentences appear passive
            if passive_ratio > 0.4 and passive_count >= 3:
                issues.append(QAIssue(
                    id=f"clarity-passive-{issue_num}",
                    severity=IssueSeverity.info,
                    issue_type=IssueType.clarity,
                    chapter_index=chapter.index,
                    heading=chapter.heading,
                    location=para[:100] + "..." if len(para) > 100 else para,
                    message=f"Section has heavy passive voice usage ({passive_count}/{len(sentences)} sentences)",
                    suggestion="Consider using more active voice for clarity",
                    metadata={"passive_count": passive_count, "total_sentences": len(sentences)}
                ))
                issue_num += 1

    return issues


# ============================================================================
# T012: Chapter Balance Analysis
# ============================================================================

def analyze_chapter_balance(markdown: str) -> list[QAIssue]:
    """Check for unbalanced chapter lengths."""
    issues: list[QAIssue] = []
    chapters = parse_chapters(markdown)

    if len(chapters) < 2:
        return issues

    word_counts = [c.word_count for c in chapters]
    avg_words = sum(word_counts) / len(word_counts)
    max_words = max(word_counts)
    min_words = max(min(word_counts), 1)  # Avoid division by zero

    ratio = max_words / min_words

    if ratio > MAX_CHAPTER_RATIO:
        # Find the extreme chapters
        longest = max(chapters, key=lambda c: c.word_count)
        shortest = min(chapters, key=lambda c: c.word_count)

        issues.append(QAIssue(
            id="struct-balance-0",
            severity=IssueSeverity.warning,
            issue_type=IssueType.structure,
            message=f"Unbalanced chapters: ratio {ratio:.1f}x between longest and shortest",
            suggestion="Consider splitting longer chapters or expanding shorter ones",
            metadata={
                "longest_chapter": longest.heading,
                "longest_words": longest.word_count,
                "shortest_chapter": shortest.heading,
                "shortest_words": shortest.word_count,
                "ratio": round(ratio, 2),
                "average_words": round(avg_words)
            }
        ))

        # Flag specifically short chapters
        for chapter in chapters:
            if chapter.word_count < avg_words * 0.3:  # Less than 30% of average
                issues.append(QAIssue(
                    id=f"struct-short-{chapter.index}",
                    severity=IssueSeverity.info,
                    issue_type=IssueType.structure,
                    chapter_index=chapter.index,
                    heading=chapter.heading,
                    message=f"Very short chapter ({chapter.word_count} words, average is {int(avg_words)})",
                    suggestion="Consider expanding this chapter or merging with another",
                    metadata={"word_count": chapter.word_count, "average": round(avg_words)}
                ))

    return issues


# ============================================================================
# Combined Structural Analysis
# ============================================================================

def analyze_structure(markdown: str) -> StructuralAnalysisResult:
    """Run all structural analysis checks.

    Returns:
        StructuralAnalysisResult with issues and scores
    """
    all_issues: list[QAIssue] = []

    # T009: Repetition
    rep_issues, repetition_score = detect_repetitions(markdown)
    all_issues.extend(rep_issues)

    # T010: Heading hierarchy
    heading_issues = validate_heading_hierarchy(markdown)
    all_issues.extend(heading_issues)

    # T011: Paragraph length
    para_issues, clarity_score = analyze_paragraph_lengths(markdown)
    all_issues.extend(para_issues)

    # Passive voice (part of clarity)
    passive_issues = detect_passive_voice_heavy_sections(markdown)
    all_issues.extend(passive_issues)

    # T012: Chapter balance
    balance_issues = analyze_chapter_balance(markdown)
    all_issues.extend(balance_issues)

    # Calculate structure score
    # Based on heading issues and balance issues
    structure_issues = [i for i in all_issues if i.issue_type == IssueType.structure]
    if not structure_issues:
        structure_score = 100
    else:
        # Penalize based on severity
        penalty = sum(
            20 if i.severity == IssueSeverity.critical else (
                10 if i.severity == IssueSeverity.warning else 5
            )
            for i in structure_issues
        )
        structure_score = max(1, 100 - penalty)

    # Adjust clarity score for passive voice issues
    passive_penalty = len(passive_issues) * 3
    clarity_score = max(1, clarity_score - passive_penalty)

    return StructuralAnalysisResult(
        issues=all_issues,
        structure_score=structure_score,
        repetition_score=repetition_score,
        clarity_score=clarity_score,
    )
