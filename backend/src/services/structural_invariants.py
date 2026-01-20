"""Structural invariants for Ideas Edition output.

These functions detect violations of invariants that must NEVER
occur in final output:
1. No empty Key Excerpts sections
2. No empty Core Claims without placeholder
3. No inline quotes in narrative prose
"""
import re
from typing import TypedDict


class EmptySection(TypedDict):
    chapter: int
    section: str
    start_pos: int


class InlineQuoteViolation(TypedDict):
    chapter: int
    quote: str
    line: str
    line_num: int


def find_empty_sections(markdown: str) -> list[EmptySection]:
    """Find sections that are empty (no content between header and next section).

    Args:
        markdown: Full document markdown.

    Returns:
        List of empty section descriptors.
    """
    empties = []

    # Find all chapter boundaries
    chapter_pattern = re.compile(r'^## Chapter (\d+)', re.MULTILINE)
    chapters = list(chapter_pattern.finditer(markdown))

    for i, chapter_match in enumerate(chapters):
        chapter_num = int(chapter_match.group(1))
        chapter_start = chapter_match.start()
        chapter_end = chapters[i + 1].start() if i + 1 < len(chapters) else len(markdown)
        chapter_text = markdown[chapter_start:chapter_end]

        # Check Key Excerpts
        key_excerpts_empty = re.search(
            r'### Key Excerpts\s*\n\s*(?=### |## |\Z)',
            chapter_text
        )
        if key_excerpts_empty:
            empties.append({
                "chapter": chapter_num,
                "section": "Key Excerpts",
                "start_pos": chapter_start + key_excerpts_empty.start(),
            })

        # Check Core Claims (empty = no bullets AND no placeholder)
        core_claims_match = re.search(
            r'### Core Claims\s*\n(.*?)(?=### |## |\Z)',
            chapter_text,
            re.DOTALL
        )
        if core_claims_match:
            content = core_claims_match.group(1).strip()
            # Empty if no bullets (-) and no placeholder (*No fully grounded*)
            has_bullets = bool(re.search(r'^- \*\*', content, re.MULTILINE))
            has_placeholder = '*No fully grounded claims' in content
            if not has_bullets and not has_placeholder:
                empties.append({
                    "chapter": chapter_num,
                    "section": "Core Claims",
                    "start_pos": chapter_start + core_claims_match.start(),
                })

    return empties


def find_inline_quote_violations(markdown: str) -> list[InlineQuoteViolation]:
    """Find quotes that appear outside Key Excerpts and Core Claims.

    Args:
        markdown: Full document markdown.

    Returns:
        List of inline quote violations.
    """
    violations = []
    lines = markdown.split('\n')

    in_key_excerpts = False
    in_core_claims = False
    current_chapter = 0

    for line_num, line in enumerate(lines, 1):
        stripped = line.strip()

        # Track sections
        if stripped.startswith('## Chapter'):
            match = re.match(r'## Chapter (\d+)', stripped)
            if match:
                current_chapter = int(match.group(1))
            in_key_excerpts = False
            in_core_claims = False
        elif stripped == '### Key Excerpts':
            in_key_excerpts = True
            in_core_claims = False
        elif stripped == '### Core Claims':
            in_key_excerpts = False
            in_core_claims = True
        elif stripped.startswith('### ') or stripped.startswith('## '):
            in_key_excerpts = False
            in_core_claims = False

        # Skip allowed sections
        if in_key_excerpts or in_core_claims:
            continue

        # Skip blockquote lines (they're handled by Key Excerpts detection)
        if stripped.startswith('>'):
            continue

        # Find quotes in this line
        quote_pattern = re.compile(r'["\u201c]([^"\u201d]{5,})["\u201d]')
        for match in quote_pattern.finditer(line):
            violations.append({
                "chapter": current_chapter,
                "quote": match.group(1),
                "line": line.strip(),
                "line_num": line_num,
            })

    return violations


def validate_structural_invariants(markdown: str) -> dict:
    """Validate all structural invariants.

    Args:
        markdown: Full document markdown.

    Returns:
        Dict with 'valid' bool and 'violations' list.
    """
    empty_sections = find_empty_sections(markdown)
    inline_quotes = find_inline_quote_violations(markdown)

    return {
        "valid": len(empty_sections) == 0 and len(inline_quotes) == 0,
        "empty_sections": empty_sections,
        "inline_quotes": inline_quotes,
    }
