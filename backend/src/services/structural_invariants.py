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


class PlaceholderGlueViolation(TypedDict):
    chapter: int
    text: str
    line_num: int


class VerbatimLeakViolation(TypedDict):
    chapter: int
    matched_text: str
    original_quote: str
    line_num: int


class ClaimsCoverageGap(TypedDict):
    chapter: int
    excerpt_count: int
    claim_count: int


class ShortSupportViolation(TypedDict):
    chapter: int
    claim_text: str
    support_text: str
    line_num: int


# Placeholder glue patterns that indicate removed quote artifacts
PLACEHOLDER_GLUE_PATTERNS = [
    r'\[as discussed in the excerpts? above\]',
    r'\[see excerpts? above\]',
    r'\[see key excerpts?\]',
    r'as noted in the (?:quotes?|excerpts?) above',
    r'see the key excerpts? for (?:more )?detail',
    r'as (?:the )?excerpts? (?:above )?(?:show|demonstrate|illustrate)',
    r'\[excerpt[^\]]*\]',  # Any bracketed excerpt reference
]

# Short support patterns (content-free acknowledgements)
SHORT_SUPPORT_PATTERNS = [
    r'^Yes\.?$',
    r'^No\.?$',
    r'^OK\.?$',
    r'^Okay\.?$',
    r'^Right\.?$',
    r'^Sure\.?$',
    r'^Exactly\.?$',
    r'^Absolutely\.?$',
    r'^Correct\.?$',
    r'^Yeah\.?$',
    r'^Mm-?hmm\.?$',
    r'^Uh-?huh\.?$',
]


def find_placeholder_glue(markdown: str) -> list[PlaceholderGlueViolation]:
    """Find placeholder glue strings that indicate removed quote artifacts.

    Args:
        markdown: Full document markdown.

    Returns:
        List of placeholder glue violations.
    """
    violations = []
    lines = markdown.split('\n')
    current_chapter = 0

    # Compile patterns
    patterns = [re.compile(p, re.IGNORECASE) for p in PLACEHOLDER_GLUE_PATTERNS]

    for line_num, line in enumerate(lines, 1):
        stripped = line.strip()

        # Track chapter
        if stripped.startswith('## Chapter'):
            match = re.match(r'## Chapter (\d+)', stripped)
            if match:
                current_chapter = int(match.group(1))

        # Skip headers and Key Excerpts/Core Claims sections
        if stripped.startswith('#'):
            continue

        # Check for placeholder patterns
        for pattern in patterns:
            match = pattern.search(line)
            if match:
                violations.append({
                    "chapter": current_chapter,
                    "text": match.group(0),
                    "line_num": line_num,
                })

    return violations


def find_verbatim_leaks(
    markdown: str,
    whitelist_quotes: list[str],
    min_substring_len: int = 30,
) -> list[VerbatimLeakViolation]:
    """Find whitelist quotes that appear verbatim in prose (even unquoted).

    Args:
        markdown: Full document markdown.
        whitelist_quotes: List of validated whitelist quote texts.
        min_substring_len: Minimum substring length to consider a match.

    Returns:
        List of verbatim leak violations.
    """
    violations = []
    lines = markdown.split('\n')

    in_key_excerpts = False
    in_core_claims = False
    current_chapter = 0

    # Normalize quotes for comparison
    def normalize(text: str) -> str:
        """Normalize text for fuzzy matching."""
        # Normalize quotes and apostrophes
        text = text.replace('"', '"').replace('"', '"')
        text = text.replace(''', "'").replace(''', "'")
        # Normalize whitespace
        text = ' '.join(text.split())
        return text.lower()

    normalized_quotes = [(normalize(q), q) for q in whitelist_quotes]

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

        # Skip headers and blockquotes
        if stripped.startswith('#') or stripped.startswith('>'):
            continue

        # Check for verbatim matches
        normalized_line = normalize(line)
        for norm_quote, original_quote in normalized_quotes:
            # Check full quote match
            if norm_quote in normalized_line:
                violations.append({
                    "chapter": current_chapter,
                    "matched_text": original_quote,
                    "original_quote": original_quote,
                    "line_num": line_num,
                })
                continue

            # Check significant substring match
            if len(norm_quote) >= min_substring_len:
                # Check overlapping windows of the quote
                for i in range(len(norm_quote) - min_substring_len + 1):
                    substring = norm_quote[i:i + min_substring_len]
                    if substring in normalized_line:
                        violations.append({
                            "chapter": current_chapter,
                            "matched_text": original_quote[i:i + min_substring_len],
                            "original_quote": original_quote,
                            "line_num": line_num,
                        })
                        break  # Only report once per quote per line

    return violations


def find_claims_coverage_gaps(
    markdown: str,
    min_excerpts_for_claims: int = 2,
) -> list[ClaimsCoverageGap]:
    """Find chapters that have excerpts but no claims.

    If a chapter has enough excerpts to support claims, it should have
    at least one valid claim (not just a placeholder).

    Args:
        markdown: Full document markdown.
        min_excerpts_for_claims: Minimum excerpts needed before claims required.

    Returns:
        List of chapters with claims coverage gaps.
    """
    gaps = []

    # Find all chapter boundaries
    chapter_pattern = re.compile(r'^## Chapter (\d+)', re.MULTILINE)
    chapters = list(chapter_pattern.finditer(markdown))

    for i, chapter_match in enumerate(chapters):
        chapter_num = int(chapter_match.group(1))
        chapter_start = chapter_match.start()
        chapter_end = chapters[i + 1].start() if i + 1 < len(chapters) else len(markdown)
        chapter_text = markdown[chapter_start:chapter_end]

        # Count excerpts (blockquotes in Key Excerpts section)
        key_excerpts_match = re.search(
            r'### Key Excerpts\s*\n(.*?)(?=### |## |\Z)',
            chapter_text,
            re.DOTALL
        )
        excerpt_count = 0
        if key_excerpts_match:
            excerpts_content = key_excerpts_match.group(1)
            # Count blockquote lines that start a new quote (not attribution lines)
            excerpt_count = len(re.findall(r'^> "[^"]*', excerpts_content, re.MULTILINE))

        # Count claims (bullet points in Core Claims section)
        core_claims_match = re.search(
            r'### Core Claims\s*\n(.*?)(?=### |## |\Z)',
            chapter_text,
            re.DOTALL
        )
        claim_count = 0
        if core_claims_match:
            claims_content = core_claims_match.group(1)
            # Check for placeholder
            has_placeholder = '*No fully grounded claims' in claims_content
            if not has_placeholder:
                # Count bullet points
                claim_count = len(re.findall(r'^- \*\*', claims_content, re.MULTILINE))

        # Check for gap: enough excerpts but no claims
        if excerpt_count >= min_excerpts_for_claims and claim_count == 0:
            gaps.append({
                "chapter": chapter_num,
                "excerpt_count": excerpt_count,
                "claim_count": claim_count,
            })

    return gaps


def find_short_support_claims(markdown: str) -> list[ShortSupportViolation]:
    """Find claims supported only by very short acknowledgements.

    Claims like 'The universe is infinite. "Yes."' are content-free
    and should be dropped or expanded.

    Args:
        markdown: Full document markdown.

    Returns:
        List of short support violations.
    """
    violations = []
    lines = markdown.split('\n')

    in_core_claims = False
    current_chapter = 0

    # Compile short support patterns
    short_patterns = [re.compile(p, re.IGNORECASE) for p in SHORT_SUPPORT_PATTERNS]

    for line_num, line in enumerate(lines, 1):
        stripped = line.strip()

        # Track sections
        if stripped.startswith('## Chapter'):
            match = re.match(r'## Chapter (\d+)', stripped)
            if match:
                current_chapter = int(match.group(1))
            in_core_claims = False
        elif stripped == '### Core Claims':
            in_core_claims = True
        elif stripped.startswith('### ') or stripped.startswith('## '):
            in_core_claims = False

        # Only check Core Claims section
        if not in_core_claims:
            continue

        # Check for claim lines with quotes
        if not stripped.startswith('- **'):
            continue

        # Extract quoted support text
        quote_match = re.search(r'"([^"]+)"', stripped)
        if not quote_match:
            continue

        support_text = quote_match.group(1).strip()

        # Check if support is too short
        for pattern in short_patterns:
            if pattern.match(support_text):
                # Extract claim text (between ** markers)
                claim_match = re.search(r'\*\*([^*]+)\*\*', stripped)
                claim_text = claim_match.group(1) if claim_match else stripped

                violations.append({
                    "chapter": current_chapter,
                    "claim_text": claim_text,
                    "support_text": support_text,
                    "line_num": line_num,
                })
                break

    return violations


def validate_structural_invariants(
    markdown: str,
    whitelist_quotes: list[str] | None = None,
) -> dict:
    """Validate all structural invariants.

    Args:
        markdown: Full document markdown.
        whitelist_quotes: Optional list of whitelist quote texts for verbatim leak detection.

    Returns:
        Dict with 'valid' bool and 'violations' dict.
    """
    empty_sections = find_empty_sections(markdown)
    inline_quotes = find_inline_quote_violations(markdown)
    placeholder_glue = find_placeholder_glue(markdown)
    claims_gaps = find_claims_coverage_gaps(markdown)
    short_supports = find_short_support_claims(markdown)

    # Verbatim leaks only checked if whitelist provided
    verbatim_leaks = []
    if whitelist_quotes:
        verbatim_leaks = find_verbatim_leaks(markdown, whitelist_quotes)

    all_valid = (
        len(empty_sections) == 0
        and len(inline_quotes) == 0
        and len(placeholder_glue) == 0
        and len(claims_gaps) == 0
        and len(short_supports) == 0
        and len(verbatim_leaks) == 0
    )

    return {
        "valid": all_valid,
        "empty_sections": empty_sections,
        "inline_quotes": inline_quotes,
        "placeholder_glue": placeholder_glue,
        "verbatim_leaks": verbatim_leaks,
        "claims_gaps": claims_gaps,
        "short_supports": short_supports,
    }
