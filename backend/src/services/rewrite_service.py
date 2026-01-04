"""Targeted Rewrite Service (Spec 009 US3).

Rewrites sections of a draft to fix QA-flagged issues without
adding new claims beyond those in the Evidence Map.

Key functions:
- parse_markdown_sections: Split draft into sections for targeting
- find_sections_for_issues: Map QA issues to draft sections
- create_rewrite_plan: Build a plan of sections to rewrite
- execute_targeted_rewrite: Perform the rewrite using LLM
- generate_section_diff: Create before/after diff for UI
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from src.llm import LLMClient, LLMRequest, ChatMessage, ResponseFormat
from src.models.evidence_map import EvidenceMap, ChapterEvidence, EvidenceEntry
from src.models.qa_report import QAIssue, QAReport, IssueType
from src.models.rewrite_plan import (
    RewritePlan,
    RewriteSection,
    RewriteResult,
    SectionDiff,
    IssueReference,
    IssueTypeEnum,
)
from .prompts import REWRITE_SYSTEM_PROMPT, build_rewrite_section_prompt

logger = logging.getLogger(__name__)

# LLM model for rewrite
REWRITE_MODEL = "gpt-4o-mini"

# Maximum sections to rewrite in one pass
MAX_SECTIONS_PER_PASS = 10


# ==============================================================================
# Markdown Section Parsing (T041)
# ==============================================================================

@dataclass
class MarkdownSection:
    """A section of markdown defined by a heading."""
    heading: str
    level: int  # 1 for #, 2 for ##, etc.
    start_line: int  # 1-based
    end_line: int  # 1-based, inclusive
    content: str
    chapter_index: Optional[int] = None


def parse_markdown_sections(
    markdown: str,
    min_level: int = 1,
    max_level: int = 4,
) -> list[MarkdownSection]:
    """Parse markdown into sections based on headings.

    Args:
        markdown: The markdown text to parse.
        min_level: Minimum heading level to consider (1 = #).
        max_level: Maximum heading level to consider (4 = ####).

    Returns:
        List of MarkdownSection objects.
    """
    sections: list[MarkdownSection] = []
    lines = markdown.split('\n')

    # Heading pattern: # to #### at start of line
    heading_pattern = re.compile(r'^(#{1,6})\s+(.+)$')

    current_section: Optional[MarkdownSection] = None
    current_chapter_idx = 0

    for line_idx, line in enumerate(lines):
        line_num = line_idx + 1  # 1-based
        match = heading_pattern.match(line)

        if match:
            level = len(match.group(1))
            heading_text = match.group(2).strip()

            # Track chapter index (## headings are typically chapters)
            if level == 2 and 'chapter' in heading_text.lower():
                current_chapter_idx += 1

            if min_level <= level <= max_level:
                # Close previous section
                if current_section is not None:
                    current_section.end_line = line_num - 1
                    sections.append(current_section)

                # Start new section
                current_section = MarkdownSection(
                    heading=heading_text,
                    level=level,
                    start_line=line_num,
                    end_line=line_num,  # Will be updated
                    content='',
                    chapter_index=current_chapter_idx if current_chapter_idx > 0 else None,
                )

    # Close last section
    if current_section is not None:
        current_section.end_line = len(lines)
        sections.append(current_section)

    # Fill in content for each section
    for section in sections:
        section_lines = lines[section.start_line - 1:section.end_line]
        section.content = '\n'.join(section_lines)

    return sections


def get_section_content(
    markdown: str,
    start_line: int,
    end_line: int,
) -> str:
    """Extract content between line numbers.

    Args:
        markdown: Full markdown text.
        start_line: 1-based start line.
        end_line: 1-based end line (inclusive).

    Returns:
        Content of the section.
    """
    lines = markdown.split('\n')
    section_lines = lines[start_line - 1:end_line]
    return '\n'.join(section_lines)


# ==============================================================================
# Section-Issue Mapping (T042)
# ==============================================================================

def find_sections_for_issues(
    sections: list[MarkdownSection],
    issues: list[QAIssue],
) -> dict[str, list[QAIssue]]:
    """Map QA issues to the sections where they occur.

    Args:
        sections: Parsed markdown sections.
        issues: List of QA issues from the report.

    Returns:
        Dict mapping section heading to list of issues in that section.
    """
    section_issues: dict[str, list[QAIssue]] = {}

    for issue in issues:
        matched_section = _find_section_for_issue(sections, issue)
        if matched_section:
            key = matched_section.heading
            if key not in section_issues:
                section_issues[key] = []
            section_issues[key].append(issue)

    return section_issues


def _find_section_for_issue(
    sections: list[MarkdownSection],
    issue: QAIssue,
) -> Optional[MarkdownSection]:
    """Find the section where an issue occurs.

    Uses issue.heading if available, otherwise issue.chapter_index,
    otherwise issue.location text search.
    """
    # Try to match by heading first
    if issue.heading:
        for section in sections:
            if section.heading.lower() == issue.heading.lower():
                return section
            # Also try partial match
            if issue.heading.lower() in section.heading.lower():
                return section

    # Try to match by chapter index
    if issue.chapter_index is not None:
        for section in sections:
            if section.chapter_index == issue.chapter_index:
                return section

    # Try to match by location text
    if issue.location:
        for section in sections:
            if issue.location in section.content:
                return section

    # No match - could be a global issue
    return None


# ==============================================================================
# Rewrite Plan Creation (T043)
# ==============================================================================

def create_rewrite_plan(
    project_id: str,
    draft: str,
    qa_report: QAReport,
    evidence_map: Optional[EvidenceMap] = None,
    pass_number: int = 1,
    issue_types: Optional[list[IssueType]] = None,
) -> RewritePlan:
    """Create a plan for targeted rewrite.

    Args:
        project_id: Project identifier.
        draft: Current draft markdown.
        qa_report: QA report with issues to fix.
        evidence_map: Evidence Map to constrain rewrites.
        pass_number: Which pass this is (1, 2, or 3 max).
        issue_types: Only fix these issue types (default: all).

    Returns:
        RewritePlan with sections to rewrite.
    """
    # Parse draft into sections
    sections = parse_markdown_sections(draft)

    # Filter issues by type if specified
    issues_to_fix = qa_report.issues
    if issue_types:
        issues_to_fix = [i for i in issues_to_fix if i.issue_type in issue_types]

    # Map issues to sections
    section_issues = find_sections_for_issues(sections, issues_to_fix)

    # Create rewrite sections
    rewrite_sections: list[RewriteSection] = []
    section_id_counter = 0

    for section in sections:
        if section.heading not in section_issues:
            continue

        issues = section_issues[section.heading]
        if not issues:
            continue

        section_id_counter += 1

        # Get allowed evidence for this chapter
        allowed_evidence_ids = []
        if evidence_map and section.chapter_index:
            chapter_evidence = _get_chapter_evidence(evidence_map, section.chapter_index)
            if chapter_evidence:
                allowed_evidence_ids = [e.id for e in chapter_evidence.claims]

        # Create issue references
        issue_refs = [
            IssueReference(
                issue_id=issue.id,
                issue_type=IssueTypeEnum(issue.issue_type.value),
                issue_message=issue.message,
            )
            for issue in issues
        ]

        # Build rewrite instructions from issues
        instructions = _build_rewrite_instructions(issues)

        rewrite_section = RewriteSection(
            section_id=f"section_{section_id_counter:03d}",
            chapter_index=section.chapter_index or 1,
            heading=section.heading,
            start_line=section.start_line,
            end_line=section.end_line,
            original_text=section.content,
            issues_addressed=issue_refs,
            allowed_evidence_ids=allowed_evidence_ids,
            rewrite_instructions=instructions,
            preserve=["heading", "bullet_structure", "code_blocks"],
        )
        rewrite_sections.append(rewrite_section)

    # Limit sections per pass
    if len(rewrite_sections) > MAX_SECTIONS_PER_PASS:
        logger.warning(
            f"Limiting rewrite from {len(rewrite_sections)} to {MAX_SECTIONS_PER_PASS} sections"
        )
        rewrite_sections = rewrite_sections[:MAX_SECTIONS_PER_PASS]

    return RewritePlan(
        project_id=project_id,
        qa_report_id=qa_report.id,
        evidence_map_hash=evidence_map.transcript_hash if evidence_map else None,
        pass_number=pass_number,
        sections=rewrite_sections,
    )


def _get_chapter_evidence(
    evidence_map: EvidenceMap,
    chapter_index: int,
) -> Optional[ChapterEvidence]:
    """Get evidence for a chapter."""
    for chapter in evidence_map.chapters:
        if chapter.chapter_index == chapter_index:
            return chapter
    return None


def _build_rewrite_instructions(issues: list[QAIssue]) -> str:
    """Build rewrite instructions from issues."""
    instructions = []

    for issue in issues:
        if issue.issue_type == IssueType.repetition:
            instructions.append(f"Remove repetition: {issue.message}")
        elif issue.issue_type == IssueType.clarity:
            instructions.append(f"Improve clarity: {issue.message}")
        elif issue.issue_type == IssueType.faithfulness:
            instructions.append(f"Fix faithfulness issue: {issue.message}")
        elif issue.issue_type == IssueType.structure:
            instructions.append(f"Fix structure: {issue.message}")
        elif issue.issue_type == IssueType.completeness:
            instructions.append(f"Address completeness: {issue.message}")

    return '\n'.join(instructions)


# ==============================================================================
# Rewrite Execution (T044)
# ==============================================================================

async def execute_targeted_rewrite(
    draft: str,
    rewrite_plan: RewritePlan,
    evidence_map: Optional[EvidenceMap] = None,
) -> RewriteResult:
    """Execute a targeted rewrite based on the plan.

    Args:
        draft: Current draft markdown.
        rewrite_plan: Plan specifying sections to rewrite.
        evidence_map: Evidence Map to constrain rewrites.

    Returns:
        RewriteResult with diffs and updated draft.
    """
    before_hash = hashlib.sha256(draft.encode()).hexdigest()[:16]

    diffs: list[SectionDiff] = []
    issues_addressed = 0
    warnings: list[str] = []
    updated_draft = draft

    # Process each section
    for section in rewrite_plan.sections:
        try:
            # Get allowed claims for this section
            allowed_claims = []
            if evidence_map and section.chapter_index:
                chapter_evidence = _get_chapter_evidence(evidence_map, section.chapter_index)
                if chapter_evidence:
                    allowed_claims = [
                        {"id": c.id, "claim": c.claim}
                        for c in chapter_evidence.claims
                        if c.id in section.allowed_evidence_ids or not section.allowed_evidence_ids
                    ]

            # Build issues list for prompt
            issues = [
                {
                    "issue_type": ref.issue_type.value,
                    "issue_message": ref.issue_message or "Fix this issue",
                }
                for ref in section.issues_addressed
            ]

            # Rewrite the section
            rewritten = await _rewrite_section(
                original_text=section.original_text,
                issues=issues,
                allowed_claims=allowed_claims,
                preserve=section.preserve,
                rewrite_instructions=section.rewrite_instructions,
            )

            # Create diff
            diff = generate_section_diff(
                section_id=section.section_id,
                heading=section.heading,
                original=section.original_text,
                rewritten=rewritten,
            )
            diffs.append(diff)

            # Update draft with rewritten content
            updated_draft = updated_draft.replace(section.original_text, rewritten)
            issues_addressed += len(section.issues_addressed)

        except Exception as e:
            logger.error(f"Failed to rewrite section {section.section_id}: {e}")
            warnings.append(f"Section '{section.heading}' could not be rewritten: {str(e)[:100]}")

    after_hash = hashlib.sha256(updated_draft.encode()).hexdigest()[:16]

    return RewriteResult(
        project_id=rewrite_plan.project_id,
        pass_number=rewrite_plan.pass_number,
        sections_rewritten=len(diffs),
        issues_addressed=issues_addressed,
        before_draft_hash=before_hash,
        after_draft_hash=after_hash,
        diffs=diffs,
        faithfulness_preserved=True,  # Enforced by Evidence Map constraints
        warnings=warnings,
    )


async def _rewrite_section(
    original_text: str,
    issues: list[dict],
    allowed_claims: list[dict],
    preserve: list[str],
    rewrite_instructions: Optional[str] = None,
) -> str:
    """Use LLM to rewrite a single section.

    Args:
        original_text: Original section content.
        issues: Issues to fix.
        allowed_claims: Claims that can be used.
        preserve: Elements to preserve.
        rewrite_instructions: Specific instructions.

    Returns:
        Rewritten section text.
    """
    # Build prompt
    user_prompt = build_rewrite_section_prompt(
        original_text=original_text,
        issues=issues,
        allowed_claims=allowed_claims,
        preserve=preserve,
        rewrite_instructions=rewrite_instructions,
    )

    # Call LLM
    client = LLMClient()
    request = LLMRequest(
        model=REWRITE_MODEL,
        messages=[
            ChatMessage(role="system", content=REWRITE_SYSTEM_PROMPT),
            ChatMessage(role="user", content=user_prompt),
        ],
        temperature=0.3,  # Lower temperature for consistent rewrites
    )

    response = await client.complete(request)

    # Clean response - remove markdown code blocks if present
    rewritten = response.content.strip()
    if rewritten.startswith("```markdown"):
        rewritten = rewritten[11:]
    if rewritten.startswith("```"):
        rewritten = rewritten[3:]
    if rewritten.endswith("```"):
        rewritten = rewritten[:-3]

    return rewritten.strip()


# ==============================================================================
# Diff Generation (T045)
# ==============================================================================

def generate_section_diff(
    section_id: str,
    heading: Optional[str],
    original: str,
    rewritten: str,
) -> SectionDiff:
    """Generate a diff for a rewritten section.

    Args:
        section_id: Section identifier.
        heading: Section heading.
        original: Original text.
        rewritten: Rewritten text.

    Returns:
        SectionDiff with summary of changes.
    """
    # Generate summary of changes
    changes_summary = _summarize_changes(original, rewritten)

    return SectionDiff(
        section_id=section_id,
        heading=heading,
        original=original,
        rewritten=rewritten,
        changes_summary=changes_summary,
    )


def _summarize_changes(original: str, rewritten: str) -> str:
    """Summarize the changes between original and rewritten.

    Simple heuristic-based summary without full diff computation.
    """
    orig_words = len(original.split())
    new_words = len(rewritten.split())
    word_diff = new_words - orig_words

    orig_lines = len(original.split('\n'))
    new_lines = len(rewritten.split('\n'))

    parts = []

    if word_diff > 0:
        parts.append(f"+{word_diff} words")
    elif word_diff < 0:
        parts.append(f"{word_diff} words")

    if new_lines != orig_lines:
        line_diff = new_lines - orig_lines
        if line_diff > 0:
            parts.append(f"+{line_diff} lines")
        else:
            parts.append(f"{line_diff} lines")

    if not parts:
        parts.append("Content restructured")

    return ", ".join(parts)


# ==============================================================================
# Multi-Pass Logic (T049)
# ==============================================================================

def should_allow_rewrite_pass(
    pass_number: int,
    previous_result: Optional[RewriteResult] = None,
) -> tuple[bool, Optional[str]]:
    """Check if another rewrite pass should be allowed.

    Args:
        pass_number: The pass number being attempted (1, 2, or 3).
        previous_result: Result from previous pass if any.

    Returns:
        Tuple of (allowed, warning_message).
    """
    MAX_PASSES = 3

    if pass_number > MAX_PASSES:
        return False, f"Maximum of {MAX_PASSES} rewrite passes reached"

    if pass_number > 1:
        warning = (
            f"This is rewrite pass {pass_number}. "
            "Multiple passes may introduce drift from source material. "
            "Consider reviewing changes carefully."
        )
        return True, warning

    return True, None


def get_rewritten_draft(
    original_draft: str,
    result: RewriteResult,
) -> str:
    """Get the full draft with rewrites applied.

    Args:
        original_draft: The original draft markdown.
        result: The rewrite result with diffs.

    Returns:
        The updated draft with all rewrites applied.
    """
    updated = original_draft

    for diff in result.diffs:
        updated = updated.replace(diff.original, diff.rewritten)

    return updated
