"""Draft generation service for ebook creation.

Orchestrates the async generation workflow:
1. Create job and start background task
2. Generate DraftPlan (structure + mappings)
3. Generate chapters sequentially with context
4. Assemble final draft

Uses in-memory job store for state management.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import uuid
from datetime import datetime
from typing import Optional

from src.llm import LLMClient, LLMRequest, ChatMessage, ResponseFormat, load_draft_plan_schema
from src.llm.schemas import load_visual_opportunities_schema
from src.models import (
    DraftPlan,
    ChapterPlan,
    VisualPlan,
    GenerationJob,
    JobStatus,
    DraftGenerateRequest,
    DraftStatusData,
    DraftCancelData,
    DraftRegenerateData,
    GenerationProgress,
)
from src.models.visuals import VisualOpportunity, VisualPlacement, VisualType, VisualSourcePolicy
from src.models.style_config import (
    compute_words_per_chapter,
    TotalLengthPreset,
    DetailLevel,
    ContentMode,
)
from src.models.evidence_map import EvidenceMap, ChapterEvidence
from src.models.edition import WhitelistQuote, TranscriptPair, CoverageLevel

from .job_store import get_job_store, get_job, update_job
from .whitelist_service import (
    build_quote_whitelist,
    canonicalize_transcript,
    strip_llm_blockquotes,
    enforce_quote_whitelist,
    enforce_core_claims_text,
    select_deterministic_excerpts,
    format_excerpts_markdown,
    compute_chapter_coverage,
    fix_quote_artifacts,
    strip_prose_quote_chars,
    detect_verbatim_leakage,
    detect_verbatim_leaks,
    remove_inline_quotes,
    generate_coverage_report,
    build_speaker_registry,
    normalize_speaker_names,
    clean_placeholder_glue,
)
from .prompts import (
    DRAFT_PLAN_SYSTEM_PROMPT,
    build_draft_plan_user_prompt,
    build_chapter_system_prompt,
    build_chapter_user_prompt,
    extract_transcript_segment,
    get_previous_chapter_ending,
    get_next_chapter_preview,
    parse_outline_to_chapters,
    VISUAL_OPPORTUNITY_SYSTEM_PROMPT,
    build_visual_opportunity_user_prompt,
    # Interview Q&A format
    build_interview_qa_system_prompt,
    build_interview_qa_chapter_prompt,
    # Evidence-grounded prompts (Spec 009)
    build_grounded_chapter_system_prompt,
    build_grounded_chapter_user_prompt,
    get_content_mode_prompt,
    # P0: Interview grounded single-pass generation
    build_interview_grounded_system_prompt,
    build_interview_grounded_user_prompt,
)
from .evidence_service import (
    generate_evidence_map,
    get_evidence_for_chapter,
    check_interview_constraints,
    detect_content_type,
    generate_mode_warning,
    evidence_map_to_summary,
    extract_definitional_candidates,
    check_key_ideas_coverage,
    format_candidates_for_prompt,
    verify_key_ideas_quotes,
    check_truncated_quotes,
)

logger = logging.getLogger(__name__)

# Default LLM models
PLANNING_MODEL = "gpt-4o-mini"  # Faster, cheaper for structured planning
CHAPTER_MODEL = "gpt-4o-mini"   # Could use gpt-4o for higher quality
POLISH_MODEL = "gpt-4o"         # Stronger model for prose polish pass

# Best-of-N candidate selection for interview mode
# When enabled, generates multiple candidates and picks the best based on scoring
# Env var sets the MAX allowed; request param sets actual count (capped by env var)
INTERVIEW_CANDIDATE_COUNT_MAX = int(os.environ.get("INTERVIEW_CANDIDATE_COUNT_MAX", "5"))  # Server-side cap

# Generic titles that should be replaced
GENERIC_TITLES = {
    "interview", "interview transcript", "untitled", "untitled ebook", "draft", ""
}

# ==============================================================================
# Post-Generation Enforcement (strip banned sections)
# ==============================================================================

# Regex patterns for banned sections (case-insensitive)
BANNED_SECTION_PATTERNS = [
    # Key Takeaways sections (with bullet or numbered lists)
    r'#{2,4}\s*(?:Key\s+)?Takeaways?\s*\n(?:(?:[-*•]\s*|\d+[.)]\s*).+\n?)+',
    # Action Steps/Items sections (with bullet or numbered lists)
    r'#{2,4}\s*(?:Action(?:able)?\s+)?(?:Steps?|Items?)\s*\n(?:(?:[-*•]\s*|\d+[.)]\s*).+\n?)+',
    # Conclusion sections with bullet summaries
    r'#{2,4}\s*(?:In\s+)?Conclusion\s*\n(?:(?:[-*•]\s*|\d+[.)]\s*).+\n?)+',
    # Summary sections with bullets
    r'#{2,4}\s*(?:Chapter\s+)?Summary\s*\n(?:(?:[-*•]\s*|\d+[.)]\s*).+\n?)+',
]

# Compile patterns for efficiency
BANNED_SECTION_REGEXES = [re.compile(p, re.IGNORECASE | re.MULTILINE) for p in BANNED_SECTION_PATTERNS]

# ==============================================================================
# Canonical Placeholder Constants (Ideas Edition)
# ==============================================================================
# These are the ONLY acceptable placeholders for empty sections.
# Any other "no claims/excerpts available" text is LLM-generated and must be rejected.

NO_CLAIMS_PLACEHOLDER = "*No claims available.*"
NO_EXCERPTS_PLACEHOLDER = "*No excerpts available.*"

# LLM-generated placeholder patterns to REJECT (these indicate ownership failure)
# The LLM sometimes generates its own "empty section" text instead of actual content.
# These patterns catch common LLM-generated placeholders that slip through.
LLM_PLACEHOLDER_PATTERNS = [
    # Italic markdown wrappers (our placeholders use * for italic, but LLM might vary)
    r'\*No (?:fully )?(?:grounded )?claims? (?:are )?available[^*]*\*',
    r'\*No (?:fully )?(?:grounded )?excerpts? (?:are )?available[^*]*\*',
    # Plain text variants
    r'No (?:fully )?(?:grounded )?claims? (?:are )?available for this chapter',
    r'No (?:fully )?(?:grounded )?excerpts? (?:are )?available for this chapter',
    # Bullet-formatted LLM placeholders
    r'- \*\*No (?:fully )?(?:grounded )?claims? (?:are )?available',
    # "Unable to" variants
    r'Unable to (?:extract|identify|find) (?:any )?(?:grounded )?claims?',
    r'Unable to (?:extract|identify|find) (?:any )?(?:relevant )?excerpts?',
    # "Could not" variants
    r'Could not (?:extract|identify|find) (?:any )?(?:grounded )?claims?',
    # Generic "none" statements
    r'(?:There are )?[Nn]o (?:specific |relevant )?claims? (?:were )?(?:identified|found|extracted)',
    r'(?:There are )?[Nn]o (?:specific |relevant )?excerpts? (?:were )?(?:identified|found|extracted)',
]

# Compile LLM placeholder patterns
LLM_PLACEHOLDER_REGEXES = [re.compile(p, re.IGNORECASE) for p in LLM_PLACEHOLDER_PATTERNS]

# Banned phrases to flag (for reporting, not auto-removal)
# These are AI-telltale phrases that should be avoided
BANNED_PHRASES = [
    # Conclusion markers
    "In conclusion",
    "To conclude",
    "In summary",
    # Hedging/noting phrases
    "It is important to note",
    "It should be noted",
    # Demonstrative patterns
    "This highlights",
    "This demonstrates",
    "This shows",
    # Back-references
    "As mentioned earlier",
    "As we discussed",
    # Conversational openers
    "Let's explore",
    "Let's dive into",
    "Let's take a look",
    # Sentence starter connectors (AI overuses these)
    "Moreover",
    "Furthermore",
    "Additionally",
    "However",
]

# Compile phrase patterns
BANNED_PHRASE_REGEXES = [re.compile(re.escape(p), re.IGNORECASE) for p in BANNED_PHRASES]


def strip_banned_sections(text: str, book_format: str = "essay") -> tuple[str, list[str]]:
    """Strip banned sections from generated text.

    Args:
        text: The generated chapter/draft text.
        book_format: The book format (enforcement is stricter for 'essay').

    Returns:
        Tuple of (cleaned_text, list of removed section types).
    """
    if book_format not in ("essay",):
        # Only enforce for essay format for now
        return text, []

    removed = []
    result = text

    for pattern in BANNED_SECTION_REGEXES:
        matches = pattern.findall(result)
        if matches:
            # Log what we're removing
            for match in matches:
                first_line = match.split('\n')[0].strip()
                removed.append(first_line)
            result = pattern.sub('', result)

    # Clean up multiple consecutive newlines
    result = re.sub(r'\n{3,}', '\n\n', result)

    return result.strip(), removed


def count_banned_phrases(text: str) -> dict[str, int]:
    """Count occurrences of banned phrases in text.

    Args:
        text: The text to check.

    Returns:
        Dict mapping phrase to count (only non-zero counts).
    """
    counts = {}
    for phrase, pattern in zip(BANNED_PHRASES, BANNED_PHRASE_REGEXES):
        count = len(pattern.findall(text))
        if count > 0:
            counts[phrase] = count
    return counts


def enforce_prose_quality(
    text: str,
    book_format: str = "essay",
    strip_sections: bool = True,
) -> tuple[str, dict]:
    """Apply all prose quality enforcement rules.

    Args:
        text: The generated text.
        book_format: The book format.
        strip_sections: Whether to strip banned sections.

    Returns:
        Tuple of (cleaned_text, enforcement_report).
    """
    report = {
        "sections_removed": [],
        "banned_phrase_counts": {},
        "total_banned_phrases": 0,
    }

    result = text

    # Strip banned sections
    if strip_sections:
        result, removed = strip_banned_sections(result, book_format)
        report["sections_removed"] = removed

    # Count banned phrases (for reporting)
    phrase_counts = count_banned_phrases(result)
    report["banned_phrase_counts"] = phrase_counts
    report["total_banned_phrases"] = sum(phrase_counts.values())

    if removed:
        logger.info(f"Enforcement: stripped {len(removed)} banned sections: {removed}")
    if phrase_counts:
        logger.warning(f"Enforcement: {report['total_banned_phrases']} banned phrases remain: {phrase_counts}")

    return result, report


# ==============================================================================
# Whitelist Excerpt Injection
# ==============================================================================

# Pattern to find chapters with empty Key Excerpts sections
# Matches "### Key Excerpts" followed by whitespace then another section header
KEY_EXCERPTS_EMPTY_PATTERN = re.compile(
    r'(### Key Excerpts\s*\n)(\s*(?:### Core Claims|## Chapter|\Z))',
    re.MULTILINE
)


def inject_excerpts_into_empty_sections(
    markdown: str,
    whitelist: list[WhitelistQuote],
    evidence_map: EvidenceMap,
) -> str:
    """Inject deterministic excerpts into empty Key Excerpts sections.

    When the LLM generates empty Key Excerpts sections (due to failed validation
    or other issues), this function injects valid excerpts from the whitelist
    to ensure each chapter has representative quotes.

    Args:
        markdown: The draft markdown text.
        whitelist: Validated quote whitelist.
        evidence_map: Evidence map with chapter data.

    Returns:
        Markdown with excerpts injected into empty Key Excerpts sections.
    """
    result = markdown

    # Find all chapter boundaries
    chapter_pattern = re.compile(r'^## Chapter (\d+)', re.MULTILINE)
    chapters = list(chapter_pattern.finditer(result))

    if not chapters:
        logger.info("inject_excerpts: No chapters found in markdown")
        return result

    logger.info(f"inject_excerpts: Found {len(chapters)} chapters, whitelist has {len(whitelist)} quotes")

    # Process chapters in reverse order to maintain string positions
    for i in range(len(chapters) - 1, -1, -1):
        chapter_match = chapters[i]
        chapter_num = int(chapter_match.group(1))
        chapter_idx = chapter_num - 1  # 0-based index

        # Find the bounds of this chapter
        chapter_start = chapter_match.start()
        chapter_end = chapters[i + 1].start() if i + 1 < len(chapters) else len(result)
        chapter_text = result[chapter_start:chapter_end]

        # Check if Key Excerpts section is empty
        # Pattern: "### Key Excerpts\n" followed by whitespace then "### Core Claims" or "## Chapter" or end
        key_excerpts_match = re.search(
            r'(### Key Excerpts\s*\n)(\s*)(?=### Core Claims|## Chapter |\Z)',
            chapter_text
        )

        if key_excerpts_match:
            # Check if the section only contains whitespace (empty)
            content_after_header = key_excerpts_match.group(2)
            if content_after_header.strip() == '':
                # This chapter has empty Key Excerpts - inject valid excerpts
                # Get chapter evidence to determine coverage
                chapter_evidence = None
                for ch in evidence_map.chapters:
                    if ch.chapter_index == chapter_num:
                        chapter_evidence = ch
                        break

                if chapter_evidence:
                    coverage = compute_chapter_coverage(chapter_evidence, whitelist, chapter_idx)
                    excerpts = select_deterministic_excerpts(whitelist, chapter_idx, coverage.level)

                    # Debug logging: count quotes available for this chapter
                    chapter_quotes = [q for q in whitelist if chapter_idx in q.chapter_indices]
                    guest_quotes = [q for q in chapter_quotes if q.speaker.speaker_role.value == "guest"]
                    logger.info(
                        f"Chapter {chapter_num}: {len(chapter_quotes)} whitelist quotes, "
                        f"{len(guest_quotes)} GUEST quotes, coverage={coverage.level.value}, "
                        f"selected {len(excerpts)} excerpts"
                    )

                    if excerpts:
                        formatted = format_excerpts_markdown(excerpts)
                        # Insert after "### Key Excerpts\n"
                        insert_pos = chapter_start + key_excerpts_match.end(1)
                        result = result[:insert_pos] + "\n" + formatted + "\n\n" + result[insert_pos:]
                        logger.info(
                            f"Injected {len(excerpts)} excerpts into Chapter {chapter_num} Key Excerpts section"
                        )
                    else:
                        logger.warning(
                            f"Chapter {chapter_num}: No excerpts to inject (empty Key Excerpts will remain)"
                        )

    return result


def compile_key_excerpts_section(
    chapter_index: int,
    whitelist: list[WhitelistQuote],
    coverage_level: CoverageLevel,
) -> str:
    """Compile Key Excerpts section deterministically from whitelist.

    This replaces LLM-generated excerpts with whitelist-backed content.
    Uses fallback chain from select_deterministic_excerpts to ensure
    non-empty result (unless whitelist is completely empty).

    Args:
        chapter_index: 0-based chapter index.
        whitelist: Validated quote whitelist.
        coverage_level: Coverage level for excerpt count.

    Returns:
        Markdown string for Key Excerpts content (without header).
        Returns placeholder if whitelist is empty.
    """
    if not whitelist:
        return NO_EXCERPTS_PLACEHOLDER

    excerpts = select_deterministic_excerpts(whitelist, chapter_index, coverage_level)

    if not excerpts:
        # Fallback chain failed (shouldn't happen with non-empty whitelist)
        logger.warning(
            f"compile_key_excerpts_section: No excerpts selected for chapter {chapter_index} "
            f"despite whitelist having {len(whitelist)} quotes"
        )
        return NO_EXCERPTS_PLACEHOLDER

    return format_excerpts_markdown(excerpts)


# ==============================================================================
# Render Guard: Strip Empty Section Headers
# ==============================================================================


def strip_empty_section_headers(markdown: str) -> tuple[str, list[dict]]:
    """Remove section headers that have no content.

    Section headers (### Key Excerpts, ### Core Claims) are removed
    if they have only whitespace before the next section or chapter header.

    This is the render guard that ensures empty sections don't appear
    in final output.

    IMPORTANT: This function logs warnings when sections are stripped.
    Empty sections indicate a failure in the upstream pipeline to provide
    content. While stripping prevents broken output, the warnings should
    be investigated.

    Args:
        markdown: The draft markdown text.

    Returns:
        Tuple of (cleaned_markdown, stripped_sections_report).
        stripped_sections_report is a list of dicts with:
        - chapter: chapter number
        - section: section type ("Key Excerpts" or "Core Claims")
        - reason: why it was stripped
    """
    result = markdown
    stripped_sections: list[dict] = []

    # Helper to find chapter number for a given position
    def get_chapter_at_position(text: str, pos: int) -> int:
        """Find which chapter number contains the given position."""
        chapter_pattern = re.compile(r'^## Chapter (\d+)', re.MULTILINE)
        chapter_num = 0
        for match in chapter_pattern.finditer(text):
            if match.start() > pos:
                break
            chapter_num = int(match.group(1))
        return chapter_num

    # Find and remove empty Key Excerpts, tracking what we remove
    key_excerpts_pattern = re.compile(
        r'### Key Excerpts\s*\n(?:\s*\n)*(?=### |## |\Z)'
    )

    for match in key_excerpts_pattern.finditer(result):
        chapter_num = get_chapter_at_position(result, match.start())
        stripped_sections.append({
            "chapter": chapter_num,
            "section": "Key Excerpts",
            "reason": "Section was empty (no blockquotes found)",
        })
        logger.warning(
            f"EMPTY SECTION STRIPPED: Chapter {chapter_num} Key Excerpts was empty. "
            f"This indicates the whitelist had no quotes for this chapter."
        )

    result = key_excerpts_pattern.sub('', result)

    # Find and remove empty Core Claims (but preserve placeholders)
    def remove_empty_core_claims_with_tracking(text: str) -> str:
        """Remove Core Claims sections that are truly empty (no bullets, no placeholder)."""
        pattern = re.compile(
            r'(### Core Claims\s*\n)(.*?)(?=### |## |\Z)',
            re.DOTALL
        )

        def replace_if_empty(match):
            content = match.group(2)
            stripped = content.strip()

            if not stripped:
                # Truly empty - remove
                chapter_num = get_chapter_at_position(text, match.start())
                stripped_sections.append({
                    "chapter": chapter_num,
                    "section": "Core Claims",
                    "reason": "Section was empty (no bullets or placeholder)",
                })
                logger.warning(
                    f"EMPTY SECTION STRIPPED: Chapter {chapter_num} Core Claims was empty. "
                    f"This indicates no grounded claims were available."
                )
                return ''

            # Check if it has actual content (bullets or placeholder)
            has_bullets = bool(re.search(r'^- \*\*', stripped, re.MULTILINE))
            has_placeholder = '*No fully grounded claims' in stripped

            if has_bullets or has_placeholder:
                return match.group(0)  # Keep as-is

            # Has some text but not valid content - keep it for now
            return match.group(0)

        return pattern.sub(replace_if_empty, text)

    result = remove_empty_core_claims_with_tracking(result)

    # Clean up any double blank lines created by removal
    result = re.sub(r'\n{3,}', '\n\n', result)

    # Summary log if any sections were stripped
    if stripped_sections:
        logger.warning(
            f"RENDER GUARD: Stripped {len(stripped_sections)} empty section(s). "
            f"Chapters affected: {sorted(set(s['chapter'] for s in stripped_sections))}"
        )

    return result, stripped_sections


# ==============================================================================
# Quote Substring Validation (Grounding Enforcement)
# ==============================================================================

# Pattern to extract quoted text (handles straight and smart quotes)
# Unicode: " (U+0022), " (U+201C left), " (U+201D right)
QUOTE_PATTERN = re.compile(r'["\u201c\u201d]([^"\u201c\u201d]+)["\u201c\u201d]')

# Ellipsis patterns to reject
ELLIPSIS_PATTERNS = ['...', '\u2026', '. . .']  # U+2026 is unicode ellipsis

# Truncation marker patterns to reject (indicate mid-sentence cutoff)
# These appear at the END of quotes and suggest incomplete/truncated content
TRUNCATION_END_PATTERNS = [
    '\u2014',  # em-dash —
    '\u2013',  # en-dash –
    '—',       # em-dash (duplicate for clarity)
    '–',       # en-dash (duplicate for clarity)
    '-',       # hyphen at end
]

# Anachronism keywords - contemporary terms that shouldn't appear in Ideas Edition
# unless they're actually in the transcript. These are filtered in non-quoted prose.
ANACHRONISM_KEYWORDS = [
    # Contemporary issues/framing
    'climate change', 'global warming', 'carbon footprint', 'sustainability',
    'social media', 'internet', 'online', 'digital age', 'smartphone',
    'artificial intelligence', ' ai ', ' a.i.', 'machine learning',
    'inequality', 'inequalities', 'social justice', 'systemic',
    'polarization', 'misinformation', 'disinformation', 'fake news',
    'pandemic', 'covid', 'coronavirus',
    # Modern buzzwords
    "today's world", "modern world", "modern challenges", "our time",
    "21st century", "contemporary", "current era",
    # Moralizing without evidence
    'crucial for survival', 'moral duty', 'moral imperative', 'ethical responsibility',
    'vigilant stewards', 'responsible stewardship',
]


def normalize_for_comparison(text: str) -> str:
    """Normalize text for substring comparison.

    Handles smart quotes, em-dashes, and other typography variations
    so that quotes can match even if the transcript uses different characters.

    Args:
        text: Text to normalize.

    Returns:
        Normalized text for comparison.
    """
    result = text
    # Smart quotes → straight quotes (using unicode escapes for reliability)
    result = result.replace('\u201c', '"').replace('\u201d', '"')  # " " → "
    result = result.replace('\u2018', "'").replace('\u2019', "'")  # ' ' → '
    # Em-dash/en-dash → hyphen
    result = result.replace('\u2014', '-').replace('\u2013', '-')  # — – → -
    # Normalize whitespace
    result = ' '.join(result.split())
    return result.lower()


def extract_quotes(text: str) -> list[dict]:
    """Extract all quoted spans from text.

    Args:
        text: The generated text to scan.

    Returns:
        List of dicts with 'quote', 'start', 'end' positions.
    """
    quotes = []
    for match in QUOTE_PATTERN.finditer(text):
        quotes.append({
            'quote': match.group(1),
            'start': match.start(),
            'end': match.end(),
            'full_match': match.group(0),
        })
    return quotes


def validate_quote_against_transcript(
    quote: str,
    transcript: str,
) -> dict:
    """Validate a single quote against the transcript.

    Args:
        quote: The quoted text to validate.
        transcript: The canonical transcript text.

    Returns:
        Dict with 'valid', 'reason', and details.
    """
    # Check for ellipsis
    for ellipsis in ELLIPSIS_PATTERNS:
        if ellipsis in quote:
            return {
                'valid': False,
                'reason': 'contains_ellipsis',
                'quote': quote,
                'ellipsis_found': ellipsis,
            }

    # Check for truncation markers at end of quote (indicates mid-sentence cutoff)
    quote_stripped = quote.rstrip(' .,;:!?')  # Strip trailing punctuation first
    for truncation in TRUNCATION_END_PATTERNS:
        if quote_stripped.endswith(truncation):
            return {
                'valid': False,
                'reason': 'truncated_quote',
                'quote': quote,
                'truncation_marker': truncation,
            }

    # Normalize both for comparison
    quote_normalized = normalize_for_comparison(quote)
    transcript_normalized = normalize_for_comparison(transcript)

    # Check if quote is a substring of transcript
    if quote_normalized in transcript_normalized:
        return {
            'valid': True,
            'reason': 'exact_match',
            'quote': quote,
        }

    # Not found - fabricated quote
    return {
        'valid': False,
        'reason': 'not_in_transcript',
        'quote': quote,
    }


def validate_quotes_in_text(
    text: str,
    transcript: str,
) -> dict:
    """Validate all quotes in generated text against transcript.

    Args:
        text: The generated text with quotes.
        transcript: The canonical transcript text.

    Returns:
        Dict with 'valid', 'invalid_quotes', 'valid_quotes', 'summary'.
    """
    quotes = extract_quotes(text)

    valid_quotes = []
    invalid_quotes = []

    for q in quotes:
        result = validate_quote_against_transcript(q['quote'], transcript)
        result['position'] = {'start': q['start'], 'end': q['end']}
        result['full_match'] = q['full_match']

        if result['valid']:
            valid_quotes.append(result)
        else:
            invalid_quotes.append(result)

    return {
        'valid': len(invalid_quotes) == 0,
        'total_quotes': len(quotes),
        'valid_quotes': valid_quotes,
        'invalid_quotes': invalid_quotes,
        'summary': {
            'total': len(quotes),
            'valid': len(valid_quotes),
            'invalid': len(invalid_quotes),
            'ellipsis_violations': sum(1 for q in invalid_quotes if q['reason'] == 'contains_ellipsis'),
            'truncation_violations': sum(1 for q in invalid_quotes if q['reason'] == 'truncated_quote'),
            'fabricated': sum(1 for q in invalid_quotes if q['reason'] == 'not_in_transcript'),
        }
    }


def remove_invalid_quotes(
    text: str,
    invalid_quotes: list[dict],
) -> tuple[str, list[str]]:
    """Convert invalid quotes to paraphrases by removing quotation marks.

    Instead of deleting sentences with invalid quotes (too destructive),
    we keep the text but remove the quotation marks - converting a false
    direct quote into a paraphrase.

    Args:
        text: The generated text.
        invalid_quotes: List of invalid quote dicts from validate_quotes_in_text.

    Returns:
        Tuple of (cleaned_text, list of converted quote texts).
    """
    if not invalid_quotes:
        return text, []

    converted_quotes = []
    result = text

    # Sort by position descending so we can replace from end first
    # (avoids position shifts)
    sorted_quotes = sorted(invalid_quotes, key=lambda q: q['position']['start'], reverse=True)

    for invalid in sorted_quotes:
        quote_text = invalid['full_match']  # includes surrounding quotes
        inner_text = invalid['quote']  # just the text inside quotes

        # Find the quoted text in the result
        pos = result.find(quote_text)
        if pos == -1:
            continue

        # Replace quoted text with unquoted version (convert to paraphrase)
        result = result[:pos] + inner_text + result[pos + len(quote_text):]
        converted_quotes.append(inner_text)

    return result, converted_quotes


def enforce_quote_grounding(
    text: str,
    transcript: str,
    convert_invalid: bool = True,
) -> tuple[str, dict]:
    """Enforce quote grounding: validate and optionally convert invalid quotes to paraphrases.

    Invalid quotes are converted to paraphrases by removing quotation marks
    (preserving the text content). This is less destructive than deleting
    entire sentences.

    Args:
        text: The generated text.
        transcript: The canonical transcript.
        convert_invalid: If True, convert invalid quotes to paraphrases.

    Returns:
        Tuple of (cleaned_text, validation_report).
    """
    validation = validate_quotes_in_text(text, transcript)

    result = text
    converted = []

    if convert_invalid and validation['invalid_quotes']:
        result, converted = remove_invalid_quotes(text, validation['invalid_quotes'])
        logger.info(
            f"Quote grounding: converted {len(converted)} invalid quotes to paraphrases "
            f"({validation['summary']['ellipsis_violations']} ellipsis, "
            f"{validation['summary']['fabricated']} fabricated)"
        )
    elif validation['invalid_quotes']:
        logger.warning(
            f"Quote grounding: {len(validation['invalid_quotes'])} invalid quotes found "
            f"(conversion disabled)"
        )

    report = {
        **validation,
        'converted_quotes': converted,
    }

    return result, report

def validate_core_claims_structure(text: str) -> tuple[str, dict]:
    """Validate Core Claims have proper quote structure.

    This is a STRUCTURAL safety net that catches malformed Core Claims
    that slipped through enforcement (e.g., due to exceptions).

    Drops any Core Claim bullet where:
    1. The quote is not properly closed (missing closing ")
    2. The quote contains known garbage suffixes (e.g., " choose.")

    Args:
        text: The draft markdown text.

    Returns:
        Tuple of (cleaned_text, report_dict).
    """
    # Known garbage patterns that indicate content corruption
    GARBAGE_SUFFIXES = [
        r'\s+choose\.$',
        r'\s+so\s+choose\.$',
    ]
    garbage_pattern = re.compile('|'.join(GARBAGE_SUFFIXES), re.IGNORECASE)

    lines = text.split('\n')
    result_lines = []
    dropped = []
    in_core_claims_section = False
    i = 0

    while i < len(lines):
        line = lines[i]

        # Detect Core Claims section start
        if line.strip() == '### Core Claims':
            in_core_claims_section = True
            result_lines.append(line)
            i += 1
            continue

        # Detect end of Core Claims section
        if in_core_claims_section and line.strip().startswith('#'):
            in_core_claims_section = False
            # Fall through to append

        # Process Core Claim bullets
        if in_core_claims_section and line.strip().startswith('- **'):
            # Check 1: Quote must be properly closed
            # Valid pattern: - **Claim**: "quote text"
            has_opening_quote = re.search(r'["\u201c]', line)
            has_closing_quote = re.search(r'["\u201d]\s*$', line) or re.search(r'["\u201d](?:\s*—|\s*$)', line)

            if has_opening_quote and not has_closing_quote:
                dropped.append({
                    "claim": line[:50],
                    "reason": "missing_closing_quote",
                })
                i += 1
                continue

            # Check 2: No garbage suffixes inside quote
            quote_match = re.search(r'["\u201c]([^"\u201d]+)["\u201d]', line)
            if quote_match:
                quote_text = quote_match.group(1)
                if garbage_pattern.search(quote_text):
                    dropped.append({
                        "claim": line[:50],
                        "reason": "garbage_suffix_in_quote",
                    })
                    i += 1
                    continue

        result_lines.append(line)
        i += 1

    result = '\n'.join(result_lines)

    if dropped:
        logger.info(
            f"Core Claims structure validation: dropped {len(dropped)} malformed claims"
        )

    return result, {
        "dropped_count": len(dropped),
        "dropped": dropped,
    }


def drop_claims_with_invalid_quotes(
    text: str,
    transcript: str,
) -> tuple[str, dict]:
    """Drop Core Claim bullets whose supporting quotes fail validation.

    This is a HARD GATE for Core Claims integrity. When a Core Claim's
    supporting quote cannot be validated against the transcript, the
    entire bullet is dropped (not just de-quoted). This maintains the
    integrity of "quote-backed claims."

    Only operates on ### Core Claims sections to avoid affecting narrative
    prose or Key Excerpts sections.

    Args:
        text: The generated text containing Core Claims sections.
        transcript: The canonical transcript for validation.

    Returns:
        Tuple of (cleaned_text, report_dict with dropped claims info).
    """
    lines = text.split('\n')
    result_lines = []
    dropped_claims = []
    in_core_claims_section = False
    i = 0

    while i < len(lines):
        line = lines[i]

        # Detect Core Claims section start
        if line.strip() == '### Core Claims':
            in_core_claims_section = True
            result_lines.append(line)
            i += 1
            continue

        # Detect end of Core Claims section (next section heading or chapter)
        if in_core_claims_section and line.strip().startswith('#'):
            in_core_claims_section = False
            # Fall through to append the line

        # Process Core Claim bullets
        if in_core_claims_section and line.strip().startswith('- **'):
            # Collect the full bullet (may span multiple lines)
            bullet_lines = [line]
            j = i + 1
            while j < len(lines):
                next_line = lines[j]
                # Next bullet, section heading, or blank line ends this bullet
                if (next_line.strip().startswith('- **') or
                    next_line.strip().startswith('#') or
                    next_line.strip() == ''):
                    break
                bullet_lines.append(next_line)
                j += 1

            bullet_text = '\n'.join(bullet_lines)

            # Extract the supporting quote from the bullet
            # Format: - **Claim text**: "supporting quote"
            quote_match = QUOTE_PATTERN.search(bullet_text)

            if quote_match:
                supporting_quote = quote_match.group(1)
                # Validate this quote against transcript
                validation = validate_quote_against_transcript(supporting_quote, transcript)

                if not validation['valid']:
                    # DROP the entire bullet - hard gate
                    dropped_claims.append({
                        'claim_preview': bullet_text[:100].replace('\n', ' '),
                        'quote': supporting_quote[:60],
                        'reason': validation['reason'],
                    })
                    # Skip to end of this bullet
                    i = j
                    continue

            # Quote is valid (or no quote found) - keep the bullet
            result_lines.extend(bullet_lines)
            i = j
            continue

        result_lines.append(line)
        i += 1

    result_text = '\n'.join(result_lines)

    # Handle empty Core Claims sections - add placeholder
    # Match: ### Core Claims followed by only whitespace until next heading or EOF
    result_text = re.sub(
        r'(### Core Claims)\n+(?=### |## |\Z)',
        r'\1\n*No fully grounded claims available for this chapter.*\n\n',
        result_text
    )

    return result_text, {
        "dropped_count": len(dropped_claims),
        "dropped_claims": dropped_claims[:10],  # Limit for logging
    }


def ensure_required_sections_exist(text: str) -> tuple[str, dict]:
    """Ensure every chapter has both Key Excerpts and Core Claims sections.

    If a section is completely missing (not just empty), this function inserts
    the section header with a placeholder. This handles cases where:
    - The LLM failed to generate the section
    - A transform accidentally removed the entire section

    This should run BEFORE strip_empty_section_headers to ensure headers exist.

    Args:
        text: The draft markdown text.

    Returns:
        Tuple of (updated_text, report_dict).
    """
    inserted_sections = []

    # Find all chapter boundaries
    chapter_pattern = re.compile(r'^## Chapter (\d+)[:\s]*(.*?)$', re.MULTILINE)
    chapters = list(chapter_pattern.finditer(text))

    if not chapters:
        return text, {"sections_inserted": 0, "inserted": []}

    result_parts = []
    last_end = 0

    for i, chapter_match in enumerate(chapters):
        chapter_num = int(chapter_match.group(1))
        chapter_start = chapter_match.start()
        chapter_end = chapters[i + 1].start() if i + 1 < len(chapters) else len(text)
        chapter_text = text[chapter_start:chapter_end]

        has_key_excerpts = '### Key Excerpts' in chapter_text
        has_core_claims = '### Core Claims' in chapter_text

        # Add text before this chapter
        result_parts.append(text[last_end:chapter_start])

        # Rebuild chapter with missing sections if needed
        if not has_key_excerpts or not has_core_claims:
            # Find where to insert missing sections
            # Structure should be: [prose] ### Key Excerpts [content] ### Core Claims [content]

            if not has_key_excerpts and not has_core_claims:
                # Both missing - add both at end of chapter
                chapter_text = chapter_text.rstrip() + f'\n\n### Key Excerpts\n\n{NO_EXCERPTS_PLACEHOLDER}\n\n### Core Claims\n\n{NO_CLAIMS_PLACEHOLDER}\n\n'
                inserted_sections.append({"chapter": chapter_num, "section": "Key Excerpts"})
                inserted_sections.append({"chapter": chapter_num, "section": "Core Claims"})

            elif has_key_excerpts and not has_core_claims:
                # Only Core Claims missing - add after Key Excerpts content
                # Find end of Key Excerpts section
                key_excerpts_pos = chapter_text.find('### Key Excerpts')
                after_key_excerpts = chapter_text[key_excerpts_pos:]

                # Add Core Claims at end of chapter
                chapter_text = chapter_text.rstrip() + f'\n\n### Core Claims\n\n{NO_CLAIMS_PLACEHOLDER}\n\n'
                inserted_sections.append({"chapter": chapter_num, "section": "Core Claims"})

            elif not has_key_excerpts and has_core_claims:
                # Only Key Excerpts missing - add before Core Claims
                core_claims_pos = chapter_text.find('### Core Claims')
                before_core_claims = chapter_text[:core_claims_pos].rstrip()
                from_core_claims = chapter_text[core_claims_pos:]

                chapter_text = before_core_claims + f'\n\n### Key Excerpts\n\n{NO_EXCERPTS_PLACEHOLDER}\n\n' + from_core_claims
                inserted_sections.append({"chapter": chapter_num, "section": "Key Excerpts"})

        result_parts.append(chapter_text)
        last_end = chapter_end

    # Add any remaining content
    if last_end < len(text):
        result_parts.append(text[last_end:])

    result = ''.join(result_parts)

    # Clean up extra blank lines
    result = re.sub(r'\n{3,}', '\n\n', result)

    if inserted_sections:
        logger.warning(
            f"STRUCTURAL FIX: Inserted {len(inserted_sections)} missing section(s): "
            f"{inserted_sections}"
        )

    return result, {
        "sections_inserted": len(inserted_sections),
        "inserted": inserted_sections,
    }


def drop_excerpts_with_invalid_quotes(
    text: str,
    transcript: str,
) -> tuple[str, dict]:
    """Drop Key Excerpt blocks whose quotes fail validation.

    This is a HARD GATE for Key Excerpts integrity. When a Key Excerpt's
    quote cannot be validated against the transcript, the entire block
    is dropped (quote line + attribution line). This maintains the
    integrity of "source truth" excerpts.

    Also drops excerpts with "Unknown" attribution - if the LLM isn't
    confident about the speaker, the excerpt shouldn't survive.

    Only operates on ### Key Excerpts sections to avoid affecting narrative
    prose or Core Claims sections.

    Args:
        text: The generated text containing Key Excerpts sections.
        transcript: The canonical transcript for validation.

    Returns:
        Tuple of (cleaned_text, report_dict with dropped excerpts info).
    """
    lines = text.split('\n')
    result_lines = []
    dropped_excerpts = []
    in_key_excerpts_section = False
    i = 0

    while i < len(lines):
        line = lines[i]

        # Detect Key Excerpts section start
        if line.strip() == '### Key Excerpts':
            in_key_excerpts_section = True
            result_lines.append(line)
            i += 1
            continue

        # Detect end of Key Excerpts section (next section heading or chapter)
        if in_key_excerpts_section and line.strip().startswith('#'):
            in_key_excerpts_section = False
            # Fall through to append the line

        # Process block quote lines in Key Excerpts
        if in_key_excerpts_section and line.strip().startswith('>'):
            # Collect the full excerpt block (quote line(s) + attribution line)
            block_lines = [line]
            j = i + 1

            # Collect continuation lines (more > lines, attribution, blank lines within block)
            while j < len(lines):
                next_line = lines[j]
                stripped = next_line.strip()

                # Continue if it's part of the block quote
                if stripped.startswith('>'):
                    block_lines.append(next_line)
                    j += 1
                    continue

                # Empty line after block - include it as separator
                if stripped == '':
                    block_lines.append(next_line)
                    j += 1
                    break

                # Section heading means end of excerpts
                if stripped.startswith('#'):
                    break

                # Any other content means end of this block
                break

            block_text = '\n'.join(block_lines)

            # Check for "Unknown" attribution - automatic fail
            if '— Unknown' in block_text or '- Unknown' in block_text:
                dropped_excerpts.append({
                    'excerpt_preview': block_text[:100].replace('\n', ' '),
                    'reason': 'unknown_attribution',
                })
                i = j
                continue

            # Extract the quote from the block (first > line with quoted content)
            quote_match = QUOTE_PATTERN.search(block_text)

            if quote_match:
                excerpt_quote = quote_match.group(1)
                # Validate this quote against transcript
                validation = validate_quote_against_transcript(excerpt_quote, transcript)

                if not validation['valid']:
                    # DROP the entire block - hard gate
                    dropped_excerpts.append({
                        'excerpt_preview': block_text[:100].replace('\n', ' '),
                        'quote': excerpt_quote[:60],
                        'reason': validation['reason'],
                    })
                    i = j
                    continue

            # Quote is valid (or no quote found) - keep the block
            result_lines.extend(block_lines)
            i = j
            continue

        result_lines.append(line)
        i += 1

    result_text = '\n'.join(result_lines)

    # Handle empty Key Excerpts sections - add placeholder
    result_text = re.sub(
        r'(### Key Excerpts)\n+(?=### |## |\Z)',
        r'\1\n*No fully grounded excerpts available for this chapter.*\n\n',
        result_text
    )

    return result_text, {
        "dropped_count": len(dropped_excerpts),
        "dropped_excerpts": dropped_excerpts[:10],  # Limit for logging
    }


# ==============================================================================
# Global Ellipsis Ban (Step B)
# ==============================================================================
# Ellipses anywhere in Ideas Edition output indicate truncation/approximation.
# They almost always mean "I'm hiding missing words" - unacceptable for grounded content.

# Pattern to find ellipsis in text (three dots, unicode ellipsis, or spaced dots)
GLOBAL_ELLIPSIS_PATTERN = re.compile(r'\.{3}|\u2026|\. \. \.')


def find_ellipses_in_text(text: str) -> list[dict]:
    """Find all ellipsis occurrences in text.

    Args:
        text: The generated text to scan.

    Returns:
        List of dicts with 'match', 'start', 'end', 'context' (surrounding sentence).
    """
    ellipses = []
    for match in GLOBAL_ELLIPSIS_PATTERN.finditer(text):
        # Get surrounding context (the sentence containing the ellipsis)
        start_pos = match.start()
        end_pos = match.end()

        # Find sentence boundaries
        sentence_start = 0
        for i in range(start_pos - 1, -1, -1):
            if text[i] in '.!?\n' and i < start_pos - 1:
                sentence_start = i + 1
                break

        sentence_end = len(text)
        for i in range(end_pos, len(text)):
            if text[i] in '.!?\n':
                sentence_end = i + 1
                break

        context = text[sentence_start:sentence_end].strip()

        ellipses.append({
            'match': match.group(0),
            'start': start_pos,
            'end': end_pos,
            'sentence_start': sentence_start,
            'sentence_end': sentence_end,
            'context': context,
        })

    return ellipses


def remove_ellipsis_sentences(text: str, ellipses: list[dict]) -> tuple[str, list[str]]:
    """Remove sentences containing ellipses from text.

    Args:
        text: The generated text.
        ellipses: List of ellipsis dicts from find_ellipses_in_text.

    Returns:
        Tuple of (cleaned_text, list of removed sentences).
    """
    if not ellipses:
        return text, []

    removed_sentences = []
    result = text

    # Sort by position descending to remove from end first (avoids position shifts)
    sorted_ellipses = sorted(ellipses, key=lambda e: e['sentence_start'], reverse=True)

    # Track which sentence ranges we've already removed to avoid duplicates
    removed_ranges = set()

    for ellipsis in sorted_ellipses:
        range_key = (ellipsis['sentence_start'], ellipsis['sentence_end'])
        if range_key in removed_ranges:
            continue

        sentence = ellipsis['context']
        if sentence:
            removed_sentences.append(sentence)
            # Remove the sentence
            result = result[:ellipsis['sentence_start']] + result[ellipsis['sentence_end']:]
            removed_ranges.add(range_key)

    # Clean up multiple consecutive newlines/spaces
    result = re.sub(r'\n{3,}', '\n\n', result)
    result = re.sub(r'  +', ' ', result)

    return result.strip(), removed_sentences


def enforce_ellipsis_ban(text: str, remove_sentences: bool = True) -> tuple[str, dict]:
    """Enforce global ellipsis ban: find and optionally remove ellipsis-containing sentences.

    Args:
        text: The generated text.
        remove_sentences: If True, remove sentences containing ellipses.

    Returns:
        Tuple of (cleaned_text, report_dict).
    """
    ellipses = find_ellipses_in_text(text)

    result = text
    removed = []

    if remove_sentences and ellipses:
        result, removed = remove_ellipsis_sentences(text, ellipses)
        logger.info(
            f"Ellipsis ban: removed {len(removed)} sentences containing ellipses"
        )
    elif ellipses:
        logger.warning(
            f"Ellipsis ban: {len(ellipses)} ellipses found (removal disabled)"
        )

    report = {
        'ellipses_found': len(ellipses),
        'ellipsis_locations': [
            {'match': e['match'], 'context': e['context'][:80] + '...' if len(e['context']) > 80 else e['context']}
            for e in ellipses
        ],
        'removed_sentences': removed,
    }

    return result, report


# ==============================================================================
# Attributed-Speech Enforcement (Step A) - HARD ENFORCEMENT
# ==============================================================================
# Detects patterns like "Deutsch argues, X" which bypass quote validation.
# Treats these as quote candidates - validates X against transcript.
# If valid: wraps X in quotes. If invalid: DELETES entire clause.

# Attribution verbs commonly used (includes base, -s, and -ing forms)
ATTRIBUTION_VERBS = r'(?:argu(?:es?|ing)|say(?:s|ing)?|not(?:es?|ing)|observ(?:es?|ing)|warn(?:s|ing)?|assert(?:s|ing)?|claim(?:s|ing)?|explain(?:s|ing)?|point(?:s|ing)?\s+out|suggest(?:s|ing)?|stat(?:es?|ing)|contend(?:s|ing)?|believ(?:es?|ing)|maintain(?:s|ing)?|emphasiz(?:es?|ing)|stress(?:es?|ing)|highlight(?:s|ing)?|insist(?:s|ing)?|remark(?:s|ing)?|caution(?:s|ing)?|envision(?:s|ing)?|tell(?:s|ing)?|add(?:s|ing)?|writ(?:es?|ing)|acknowledg(?:es?|ing)|reflect(?:s|ing)?|challeng(?:es?|ing)|see(?:s|ing)?|view(?:s|ing)?|think(?:s|ing)?|consider(?:s|ing)?|describ(?:es?|ing)|call(?:s|ing)?|put(?:s|ting)?)'

# Pattern 1: "Speaker verb, X" or "Speaker verb that X" or "Speaker verb: X"
# Matches: Deutsch argues, X / Deutsch says that X / Deutsch notes: X
# Also handles em-dash: Deutsch says—X
ATTRIBUTED_SPEECH_PATTERN_PREFIX = re.compile(
    r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?|He|She)\s+' +  # Speaker name or pronoun
    ATTRIBUTION_VERBS +
    r'(?:,|:|\s+that|\s*\u2014|\s*-)\s*(.+?)(?:\.(?:\s|$)|$)',  # Content after punctuation
    re.MULTILINE | re.DOTALL
)

# Pattern 2: "X, Speaker verb." (suffix attribution - sentence final)
ATTRIBUTED_SPEECH_PATTERN_SUFFIX = re.compile(
    r'([^.!?]+?),\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?|he|she)\s+' + ATTRIBUTION_VERBS + r'\.',
    re.MULTILINE | re.IGNORECASE
)

# Pattern 2b: "X, Speaker verb, Y" (mid-sentence attribution)
# Catches patterns like "The truth is X, he says, which means Y"
ATTRIBUTED_SPEECH_PATTERN_MID = re.compile(
    r'([^.!?,]{20,}?),\s+(he|she|[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+' + ATTRIBUTION_VERBS + r',\s+',
    re.MULTILINE | re.IGNORECASE
)

# Pattern 3: "Speaker: X" (colon form, narrative use)
ATTRIBUTED_SPEECH_PATTERN_COLON = re.compile(
    r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*:\s+([^.!?]+[.!?])',
    re.MULTILINE
)

# Pattern 4: "Speaker's [thoughts/views/etc] ... : X" (extended colon attribution)
# Catches: "Deutsch's thoughts on X illustrate this: Content"
# The content after colon is likely verbatim if it contains first-person language
ATTRIBUTED_SPEECH_PATTERN_COLON_EXTENDED = re.compile(
    r"([A-Z][a-z]+)'s\s+(?:thoughts?|views?|ideas?|words?|arguments?|observations?|insights?|comments?|reflections?|remarks?)"
    r"[^:]{0,60}:\s+([^.!?]{30,}[.!?])",
    re.MULTILINE
)

# Pattern 5: "Speaker [verb phrase], verb_ing Content" (participial -ing attribution)
# Catches: "Deutsch agrees with Hawking, saying we should hedge our bets."
# The -ing verb introduces reported speech
ATTRIBUTION_ING_VERBS = r'(?:saying|noting|arguing|observing|warning|explaining|claiming|asserting|adding|suggesting|stating|emphasizing|stressing|insisting|remarking|pointing\s+out)'
ATTRIBUTED_SPEECH_PATTERN_PARTICIPIAL = re.compile(
    r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?|He|She)[^,]{0,80},\s+' + ATTRIBUTION_ING_VERBS + r',?\s+([^.!?]{20,}[.!?])',
    re.MULTILINE | re.IGNORECASE
)

# Pattern 6: "As Speaker puts it, Content" (prefixed "As" construction)
# Catches: "As Deutsch puts it, we are a player in the universe."
ATTRIBUTED_SPEECH_PATTERN_AS_PREFIX = re.compile(
    r'[Aa]s\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+' + ATTRIBUTION_VERBS + r'(?:\s+it)?,\s*(.+?)(?:\.(?:\s|$)|$)',
    re.MULTILINE | re.DOTALL
)


def find_attributed_speech(text: str) -> list[dict]:
    """Find all attributed speech patterns in text.

    Detects patterns like:
    - Deutsch argues, X
    - He says that X
    - Deutsch notes: X
    - Deutsch says—X
    - X, Deutsch argues.

    Args:
        text: The generated text to scan.

    Returns:
        List of dicts with 'speaker', 'content', 'full_match', 'start', 'end', 'pattern_type'.
    """
    attributed = []

    # Find prefix patterns: "Deutsch argues, X" / "He says that X" / "Deutsch: X"
    for match in ATTRIBUTED_SPEECH_PATTERN_PREFIX.finditer(text):
        speaker = match.group(1)
        content = match.group(2).strip()
        # Remove trailing period if present (we'll add it back later)
        if content.endswith('.'):
            content = content[:-1].strip()
        # Skip if content is very short (likely not a real attribution)
        if len(content) < 10:
            continue
        # Skip if content is already in quotes (already handled by quote validator)
        if content.startswith('"') or content.startswith('\u201c'):
            continue
        attributed.append({
            'speaker': speaker,
            'content': content,
            'full_match': match.group(0),
            'start': match.start(),
            'end': match.end(),
            'pattern_type': 'prefix',
        })

    # Find suffix patterns: "X, Deutsch argues."
    for match in ATTRIBUTED_SPEECH_PATTERN_SUFFIX.finditer(text):
        content = match.group(1).strip()
        speaker = match.group(2)
        if len(content) < 10:
            continue
        if content.startswith('"') or content.startswith('\u201c'):
            continue
        attributed.append({
            'speaker': speaker,
            'content': content,
            'full_match': match.group(0),
            'start': match.start(),
            'end': match.end(),
            'pattern_type': 'suffix',
        })

    # Find mid-sentence patterns: "X, he says, Y"
    # These are verbatim leaks embedded mid-sentence
    for match in ATTRIBUTED_SPEECH_PATTERN_MID.finditer(text):
        content = match.group(1).strip()
        speaker = match.group(2)
        if len(content) < 20:  # Need substantial content
            continue
        if content.startswith('"') or content.startswith('\u201c'):
            continue
        attributed.append({
            'speaker': speaker,
            'content': content,
            'full_match': match.group(0),
            'start': match.start(),
            'end': match.end(),
            'pattern_type': 'mid',
        })

    # Find colon patterns: "Deutsch: X" (but not in dialogue context)
    for match in ATTRIBUTED_SPEECH_PATTERN_COLON.finditer(text):
        speaker = match.group(1)
        content = match.group(2).strip()
        # Skip common non-attribution uses
        if speaker.lower() in ('example', 'note', 'warning', 'tip', 'summary', 'chapter'):
            continue
        if len(content) < 10:
            continue
        if content.startswith('"') or content.startswith('\u201c'):
            continue
        attributed.append({
            'speaker': speaker,
            'content': content,
            'full_match': match.group(0),
            'start': match.start(),
            'end': match.end(),
            'pattern_type': 'colon',
        })

    # Find extended colon patterns: "Deutsch's thoughts illustrate this: X"
    for match in ATTRIBUTED_SPEECH_PATTERN_COLON_EXTENDED.finditer(text):
        speaker = match.group(1)  # Just the name (e.g., "Deutsch")
        content = match.group(2).strip()
        if content.startswith('"') or content.startswith('\u201c'):
            continue
        attributed.append({
            'speaker': speaker,
            'content': content,
            'full_match': match.group(0),
            'start': match.start(),
            'end': match.end(),
            'pattern_type': 'colon_extended',
        })

    # Find participial patterns: "Deutsch agrees with Hawking, saying X"
    for match in ATTRIBUTED_SPEECH_PATTERN_PARTICIPIAL.finditer(text):
        speaker = match.group(1)  # Just the name (e.g., "Deutsch")
        content = match.group(2).strip()
        if content.startswith('"') or content.startswith('\u201c'):
            continue
        attributed.append({
            'speaker': speaker,
            'content': content,
            'full_match': match.group(0),
            'start': match.start(),
            'end': match.end(),
            'pattern_type': 'participial',
        })

    # Find "As X puts it" patterns: "As Deutsch puts it, we are a player."
    for match in ATTRIBUTED_SPEECH_PATTERN_AS_PREFIX.finditer(text):
        speaker = match.group(1)
        content = match.group(2).strip()
        if content.endswith('.'):
            content = content[:-1].strip()
        if len(content) < 10:
            continue
        if content.startswith('"') or content.startswith('\u201c'):
            continue
        attributed.append({
            'speaker': speaker,
            'content': content,
            'full_match': match.group(0),
            'start': match.start(),
            'end': match.end(),
            'pattern_type': 'as_prefix',
        })

    # Sort by position and deduplicate overlapping matches
    attributed.sort(key=lambda x: x['start'])
    deduplicated = []
    last_end = -1
    for attr in attributed:
        if attr['start'] >= last_end:
            deduplicated.append(attr)
            last_end = attr['end']

    return deduplicated


def validate_attributed_content(
    content: str,
    transcript: str,
) -> dict:
    """Validate attributed content against transcript using exact substring matching.

    Uses same normalization as quote validator for consistency.

    Args:
        content: The attributed content (X in "Deutsch says, X").
        transcript: The canonical transcript.

    Returns:
        Dict with 'valid', 'reason', 'has_ellipsis'.
    """
    # Check for ellipsis in content (automatic rejection)
    has_ellipsis = any(p in content for p in ELLIPSIS_PATTERNS)
    if has_ellipsis:
        return {
            'valid': False,
            'reason': 'contains_ellipsis',
            'has_ellipsis': True,
        }

    # Normalize both for comparison
    content_normalized = normalize_for_comparison(content)
    transcript_normalized = normalize_for_comparison(transcript)

    # Exact substring match (same as quote validator)
    if content_normalized in transcript_normalized:
        return {
            'valid': True,
            'reason': 'exact_match',
            'has_ellipsis': False,
        }

    return {
        'valid': False,
        'reason': 'not_in_transcript',
        'has_ellipsis': False,
    }


def get_sentence_boundaries(text: str, pos: int) -> tuple[int, int]:
    """Find the start and end of the sentence containing position pos.

    Args:
        text: The full text.
        pos: Position within the text.

    Returns:
        Tuple of (sentence_start, sentence_end).
    """
    # Find sentence start (look backward for sentence end or start of text)
    sentence_start = 0
    for i in range(pos - 1, -1, -1):
        if text[i] in '.!?\n' and i < pos - 1:
            sentence_start = i + 1
            break

    # Find sentence end (look forward for sentence end or end of text)
    sentence_end = len(text)
    for i in range(pos, len(text)):
        if text[i] in '.!?\n':
            sentence_end = i + 1
            break

    return sentence_start, sentence_end


def enforce_attributed_speech_hard(
    text: str,
    transcript: str,
) -> tuple[str, dict]:
    """HARD enforcement of attributed speech validation.

    Rules:
    - Detect patterns like "Deutsch argues, X" / "He says, X" / "Deutsch: X"
    - Validate X against transcript (exact substring match)
    - If valid AND no ellipsis: wrap X in quotes → Deutsch argues, "X".
    - If invalid OR has ellipsis: DROP THE ENTIRE PARAGRAPH (not surgical edit)

    This uses paragraph-level dropping to avoid corruption from partial deletions.
    Paragraphs are atomic units - either they're valid or they're removed entirely.

    Args:
        text: The generated text.
        transcript: The canonical transcript.

    Returns:
        Tuple of (cleaned_text, report_dict).
    """
    attributed = find_attributed_speech(text)

    valid_converted = []  # Valid attributions that got quotes added
    invalid_deleted = []  # Invalid attributions - paragraphs dropped
    paragraphs_with_invalid = set()  # Track which paragraph indices have invalid content

    # Split text into paragraphs (double newline separated)
    # Preserve section headers as separate "paragraphs" that are never dropped
    paragraphs = text.split('\n\n')

    # First pass: identify which paragraphs contain invalid attributions
    for attr in attributed:
        content = attr['content']
        speaker = attr['speaker']
        full_match = attr['full_match']

        # Validate content against transcript
        validation = validate_attributed_content(content, transcript)

        if not validation['valid']:
            # Find which paragraph contains this invalid attribution
            char_pos = text.find(full_match)
            if char_pos == -1:
                continue

            # Determine paragraph index by counting \n\n before this position
            text_before = text[:char_pos]
            para_idx = text_before.count('\n\n')

            # Don't drop header paragraphs (## or ###)
            if para_idx < len(paragraphs):
                para_text = paragraphs[para_idx].strip()
                if not para_text.startswith('#'):
                    paragraphs_with_invalid.add(para_idx)
                    invalid_deleted.append({
                        'speaker': speaker,
                        'content': content[:50] + '...' if len(content) > 50 else content,
                        'reason': validation['reason'],
                        'paragraph_idx': para_idx,
                        'paragraph_preview': para_text[:80] + '...' if len(para_text) > 80 else para_text,
                    })

    # Second pass: process valid attributions (wrap in quotes)
    # Work on the original text, processing in reverse to maintain positions
    result = text
    for attr in reversed(attributed):
        content = attr['content']
        speaker = attr['speaker']
        full_match = attr['full_match']

        # Skip if this attribution's paragraph will be dropped
        char_pos = result.find(full_match)
        if char_pos == -1:
            continue

        text_before = result[:char_pos]
        para_idx = text_before.count('\n\n')
        if para_idx in paragraphs_with_invalid:
            continue  # This paragraph will be dropped, skip processing

        validation = validate_attributed_content(content, transcript)
        if not validation['valid']:
            continue  # Already tracked for paragraph drop

        # VALID: Wrap content in quotes
        pos = result.find(full_match)
        if pos == -1:
            continue

        # Build the quoted version based on pattern type
        if attr['pattern_type'] == 'suffix':
            attribution_clause = full_match[len(content):].strip()
            if attribution_clause.startswith(','):
                attribution_clause = attribution_clause[1:].strip()
            if not attribution_clause.endswith('.'):
                attribution_clause = attribution_clause + '.'
            quoted_version = f'"{content}," {attribution_clause}'
        elif attr['pattern_type'] == 'mid':
            verb = _extract_verb(full_match, speaker)
            quoted_version = f'"{content}," {speaker} {verb}, '
        elif attr['pattern_type'] == 'colon':
            quoted_version = f'{speaker}: "{content}"'
        elif attr['pattern_type'] == 'colon_extended':
            colon_pos = full_match.rfind(':')
            lead_in = full_match[:colon_pos + 1].strip()
            quoted_version = f'{lead_in} "{content}"'
        elif attr['pattern_type'] == 'participial':
            content_start = full_match.find(content)
            lead_in = full_match[:content_start].strip()
            quoted_version = f'{lead_in} "{content}."'
        elif attr['pattern_type'] == 'as_prefix':
            content_start = full_match.find(content)
            lead_in = full_match[:content_start].strip()
            quoted_version = f'{lead_in} "{content}."'
        else:
            verb = _extract_verb(full_match, speaker)
            quoted_version = f'{speaker} {verb}, "{content}."'

        result = result[:pos] + quoted_version + result[pos + len(full_match):]
        valid_converted.append({
            'speaker': speaker,
            'content': content[:50] + '...' if len(content) > 50 else content,
            'action': 'quoted',
        })

    # Third pass: drop paragraphs with invalid content
    # Re-split since we may have modified valid paragraphs
    if paragraphs_with_invalid:
        new_paragraphs = result.split('\n\n')
        kept_paragraphs = []
        for idx, para in enumerate(new_paragraphs):
            if idx in paragraphs_with_invalid:
                logger.info(f"Dropping paragraph {idx} with invalid attribution: {para[:60]}...")
            else:
                kept_paragraphs.append(para)
        result = '\n\n'.join(kept_paragraphs)

    # SAFE cleanup only - no aggressive fragment removal
    # Just normalize whitespace and fix obvious punctuation issues
    result = re.sub(r'\n{3,}', '\n\n', result)
    result = re.sub(r'  +', ' ', result)
    result = re.sub(r'[,.:;]\s*[,.:;]', '.', result)  # Fix double punctuation

    # NOTE: We deliberately DO NOT call repair_grammar_fragments here
    # That function causes token corruption by doing aggressive in-paragraph edits.
    # Paragraph-level dropping is cleaner - either keep the paragraph or drop it entirely.

    dangling_count = 0  # No longer doing dangling cleanup - paragraphs are dropped whole

    if valid_converted:
        logger.info(
            f"Attribution enforcement: converted {len(valid_converted)} valid attributions to quotes"
        )
    if invalid_deleted:
        logger.info(
            f"Attribution enforcement: deleted {len(invalid_deleted)} invalid attributions"
        )

    report = {
        'total_found': len(attributed),
        'valid_converted': len(valid_converted),
        'invalid_deleted': len(invalid_deleted),
        'valid_details': valid_converted,
        'invalid_details': invalid_deleted,
    }

    return result.strip(), report


def _split_into_sentences(text: str) -> list[str]:
    """Split text into sentences conservatively.

    Uses a simple approach that splits on sentence-ending punctuation followed
    by whitespace, while avoiding common abbreviations.

    Args:
        text: The text to split.

    Returns:
        List of sentences (preserving original punctuation).
    """
    # Conservative sentence splitter - split on .!? followed by space and capital
    # This avoids splitting on abbreviations like "Dr.", "Mr.", "etc."
    sentences = []
    current = []

    # Common abbreviations to avoid splitting on
    abbrevs = {'mr', 'mrs', 'ms', 'dr', 'prof', 'sr', 'jr', 'vs', 'etc', 'e.g', 'i.e'}

    words = text.split()
    for i, word in enumerate(words):
        current.append(word)

        # Check if this word ends a sentence
        if word and word[-1] in '.!?':
            # Check if it's an abbreviation
            word_lower = word.rstrip('.!?,;:').lower()
            is_abbrev = word_lower in abbrevs

            # Check if next word starts with capital (if exists)
            next_starts_capital = (
                i + 1 < len(words) and
                words[i + 1] and
                words[i + 1][0].isupper()
            )

            # Split if not abbreviation and (end of text or next word is capitalized)
            if not is_abbrev and (i + 1 >= len(words) or next_starts_capital):
                sentences.append(' '.join(current))
                current = []

    # Add any remaining words
    if current:
        sentences.append(' '.join(current))

    return sentences


def _check_sentence_for_leak(
    sentence: str,
    normalized_quotes: list[tuple[str, str]],
    min_match_len: int,
    normalize_fn,
) -> tuple[bool, dict | None]:
    """Check if a single sentence contains a verbatim leak.

    Args:
        sentence: The sentence to check.
        normalized_quotes: List of (normalized_quote, original_quote) tuples.
        min_match_len: Minimum substring length to consider a match.
        normalize_fn: Function to normalize text for comparison.

    Returns:
        Tuple of (has_leak, detail_dict_or_none).
    """
    normalized_sent = normalize_fn(sentence)

    for norm_quote, original_quote in normalized_quotes:
        # Check for full quote match
        if norm_quote in normalized_sent:
            return True, {
                "sentence": sentence[:60] + '...' if len(sentence) > 60 else sentence,
                "matched_quote": original_quote[:60] + '...' if len(original_quote) > 60 else original_quote,
                "match_type": "full",
            }

        # Check for significant substring match (sliding window)
        if len(norm_quote) >= min_match_len:
            for i in range(0, len(norm_quote) - min_match_len + 1, 5):  # Step by 5 for efficiency
                substring = norm_quote[i:i + min_match_len]
                if substring in normalized_sent:
                    return True, {
                        "sentence": sentence[:60] + '...' if len(sentence) > 60 else sentence,
                        "matched_quote": original_quote[:60] + '...' if len(original_quote) > 60 else original_quote,
                        "match_type": "substring",
                    }

    return False, None


def _stitch_sentences(sentences: list[str]) -> str:
    """Rejoin sentences with grammar cleanup.

    Handles:
    - Orphan connectives at start (However, Therefore, etc.)
    - Proper spacing
    - Capitalization of first letter

    Args:
        sentences: List of sentences to join.

    Returns:
        Cleaned, rejoined paragraph.
    """
    if not sentences:
        return ""

    # Orphan connectives that shouldn't start a paragraph after drops
    orphan_starters = [
        'however,', 'therefore,', 'thus,', 'hence,', 'moreover,',
        'furthermore,', 'nevertheless,', 'nonetheless,', 'consequently,',
        'accordingly,', 'similarly,', 'likewise,', 'instead,', 'meanwhile,',
        'otherwise,', 'still,', 'yet,', 'also,', 'besides,'
    ]

    result = []
    for i, sent in enumerate(sentences):
        sent = sent.strip()
        if not sent:
            continue

        # If first sentence starts with orphan connective, strip it
        if i == 0 or (result and not result[-1]):
            lower_sent = sent.lower()
            for orphan in orphan_starters:
                if lower_sent.startswith(orphan):
                    sent = sent[len(orphan):].strip()
                    # Capitalize first letter of remaining text
                    if sent:
                        sent = sent[0].upper() + sent[1:]
                    break

        if sent:
            result.append(sent)

    return ' '.join(result)


def enforce_verbatim_leak_gate(
    text: str,
    whitelist_quotes: list[str],
    min_match_len: int = 20,
) -> tuple[str, dict]:
    """Drop sentences (not whole paragraphs) containing verbatim whitelist quote text.

    This is the "Verbatim Leak Gate" - a deterministic post-processing pass
    that catches transcript quotes appearing unquoted in narrative prose.

    Policy: Whitelist quote text should ONLY appear in:
    - Key Excerpts (blockquotes)
    - Core Claims (bullet points with supporting quotes)

    If whitelist text appears in narrative prose, only the offending sentence
    is dropped (not the entire paragraph), preserving surrounding context.

    Args:
        text: The draft markdown text.
        whitelist_quotes: List of validated whitelist quote texts.
        min_match_len: Minimum substring length to consider a match.

    Returns:
        Tuple of (cleaned_text, report_dict).
    """
    if not whitelist_quotes:
        return text, {"sentences_dropped": 0, "paragraphs_dropped": 0, "dropped_details": []}

    # Normalize quotes for comparison
    def normalize(s: str) -> str:
        s = s.replace('"', '"').replace('"', '"')
        s = s.replace(''', "'").replace(''', "'")
        return ' '.join(s.split()).lower()

    normalized_quotes = [(normalize(q), q) for q in whitelist_quotes if len(q) >= min_match_len]

    # Split into paragraphs
    paragraphs = text.split('\n\n')
    kept_paragraphs = []
    dropped_details = []
    sentences_dropped = 0
    paragraphs_dropped = 0

    in_key_excerpts = False
    in_core_claims = False

    for para in paragraphs:
        stripped = para.strip()

        # Track section boundaries
        if '### Key Excerpts' in stripped:
            in_key_excerpts = True
            in_core_claims = False
            kept_paragraphs.append(para)
            continue
        elif '### Core Claims' in stripped:
            in_key_excerpts = False
            in_core_claims = True
            kept_paragraphs.append(para)
            continue
        elif stripped.startswith('## '):
            in_key_excerpts = False
            in_core_claims = False
            kept_paragraphs.append(para)
            continue
        elif stripped.startswith('### '):
            in_key_excerpts = False
            in_core_claims = False
            kept_paragraphs.append(para)
            continue

        # Allow Key Excerpts and Core Claims content
        if in_key_excerpts or in_core_claims:
            kept_paragraphs.append(para)
            continue

        # Skip blockquotes (they're Key Excerpts content)
        if stripped.startswith('>'):
            kept_paragraphs.append(para)
            continue

        # SENTENCE-LEVEL DROPPING: Split paragraph into sentences
        sentences = _split_into_sentences(stripped)
        kept_sentences = []
        para_had_leaks = False

        for sentence in sentences:
            has_leak, detail = _check_sentence_for_leak(
                sentence, normalized_quotes, min_match_len, normalize
            )

            if has_leak:
                para_had_leaks = True
                sentences_dropped += 1
                dropped_details.append(detail)
                logger.info(f"Verbatim leak gate: dropping sentence: {sentence[:60]}...")
            else:
                kept_sentences.append(sentence)

        # Rejoin remaining sentences with grammar cleanup
        if kept_sentences:
            cleaned_para = _stitch_sentences(kept_sentences)
            if cleaned_para.strip():
                kept_paragraphs.append(cleaned_para)
            else:
                # All sentences dropped or stitching produced empty result
                paragraphs_dropped += 1
        else:
            # All sentences had leaks
            paragraphs_dropped += 1

    result = '\n\n'.join(kept_paragraphs)

    return result, {
        "sentences_dropped": sentences_dropped,
        "paragraphs_dropped": paragraphs_dropped,
        "dropped_details": dropped_details,
    }


def enforce_dangling_attribution_gate(text: str) -> tuple[str, dict]:
    """Rewrite dangling attribution patterns to indirect speech, DROP unrewritable ones.

    Detects patterns like:
    - "He says, This idea..." → "He says that this idea..."
    - "Deutsch notes, For ages..." → "Deutsch notes that for ages..."
    - "He cautions, To try..." → "He cautions that to try..."

    These patterns indicate the LLM generated an attribution wrapper but
    the content wasn't properly quoted. Instead of dropping (which causes
    content collapse), we rewrite to indirect speech by inserting "that"
    and lowercasing the following word.

    SENTENCE DROP (P0 - Draft 20 regression):
    Some attribution patterns are unrewritable and indicate quote-introducer leaks.
    These should DROP the entire sentence rather than attempt rewriting:
    - "Deutsch mentions..., recalling, It's funny..." - double wrapper with recalled quote
    - "..., remembering, <Capital>" - recall verb introducing unquoted content

    Curated recall/memory verbs that trigger sentence drop:
    - recalling, remembering, recollecting
    - adding, continuing, joking, musing
    - quipping, reflecting, wondering

    These verbs typically introduce recalled speech that should have been quoted.
    Rewriting to indirect speech creates awkward prose; dropping is safer.

    Args:
        text: The draft markdown text.

    Returns:
        Tuple of (cleaned_text, report_dict).
    """
    # Pattern to match dangling attributions for rewriting
    # Captures: (optional leading comma)(subject + verb)(punctuation)(first word of payload)
    # We'll rewrite: "He says, This" → "He says that this"
    # BUT skip parenthetical: ", Deutsch points out, are" should NOT become "points out that are"
    # AND skip mid-sentence interpolations: ", as Deutsch notes, is" should NOT be rewritten
    # NOTE: Sentence-start "As Deutsch remarks, This" SHOULD be rewritten (no comma before "as")
    rewrite_pattern = re.compile(
        r'(,\s*)?'  # Group 1: Optional leading comma (indicates parenthetical)
        r'(?<!, as )'  # Negative lookbehind: skip ", as X notes" mid-sentence interpolations
        r'\b((?:Deutsch|David Deutsch|He|She|They|The\s+guest|The\s+host)\s+'
        r'(?:[a-z]+ly\s+)?'  # Optional adverb (e.g., "poignantly", "eloquently")
        r'(?:notes?|observes?|argues?|says?|said|states?|stated|explains?|explained|'
        r'suggests?|suggested|points?(?:\s+out)?|warns?|warned|cautions?|cautioned|'
        r'asserts?|asserted|claims?|claimed|contends?|contended|believes?|believed|'
        r'maintains?|maintained|emphasizes?|emphasized|stresses?|stressed|'
        r'highlights?|highlighted|remarks?|remarked|adds?|added|'
        r'insists?|insisted|predicts?|predicted|'
        r'captures?|captured|marks?|marked|underscores?|underscored))'
        r'(\s*[,:]\s*)'  # Group 3: Punctuation (comma or colon)
        r'([A-Za-z])',   # Group 4: First letter of payload
        re.IGNORECASE
    )

    # Participial pattern: "noting, This..." → "noting that this..."
    # Also captures optional leading comma for parenthetical detection
    # Also skips mid-sentence ", as X notes" interpolations via negative lookbehind
    participial_pattern = re.compile(
        r'(,\s*)?'  # Group 1: Optional leading comma (indicates parenthetical)
        r'(?<!, as )'  # Negative lookbehind: skip ", as X notes" mid-sentence interpolations
        r'\b((?:noting|observing|arguing|saying|stating|explaining|'
        r'suggesting|pointing\s+out|warning|cautioning|asserting|claiming|'
        r'emphasizing|stressing|adding|remarking|capturing|predicting))'
        r'(\s*[,:]\s*)'  # Group 3: Punctuation
        r'([A-Za-z])',   # Group 4: First letter
        re.IGNORECASE
    )

    # Extended colon-wrapper pattern: "Deutsch captures this shift: This..."
    # Catches speaker + verb + optional phrase + colon + Capital
    # These wrappers introduce pseudo-quotes and should be removed/rewritten
    colon_wrapper_pattern = re.compile(
        r'\b((?:Deutsch|David Deutsch|He|She|They|The\s+guest|The\s+host)\s+'
        r'(?:captures?|sums?\s+(?:it\s+)?up|puts?\s+it|describes?|'
        r'frames?|characterizes?|encapsulates?|expresses?|conveys?|'
        r'illustrates?|demonstrates?|shows?|reveals?|makes?\s+clear)'
        r'(?:\s+[^:]{1,40})?)'  # Optional short phrase (max 40 chars)
        r'(:\s*)'               # Colon + space
        r'([A-Z])',             # Capital letter starting the "quote"
        re.IGNORECASE
    )

    # Orphan wrapper pattern: "noting. This..." or "observing. The..."
    # Catches participial verbs followed by period + sentence start
    # These are orphaned wrappers where the quote was removed but the verb survived
    orphan_wrapper_pattern = re.compile(
        r'\b(noting|observing|arguing|saying|stating|explaining|'
        r'suggesting|pointing\s+out|warning|cautioning|asserting|claiming|'
        r'emphasizing|stressing|adding|remarking|capturing)'
        r'(\.\s+)'              # Period + whitespace
        r'([A-Z])',             # Capital letter starting next sentence
        re.IGNORECASE
    )

    # =========================================================================
    # SENTENCE DROP PATTERNS (P0 - Draft 20 regression)
    # =========================================================================
    # These patterns indicate quote-introducer leaks that cannot be cleanly
    # rewritten. The entire sentence should be DROPPED.
    #
    # Curated "recall" verbs - these typically introduce recalled speech that
    # should have been quoted. Attempting indirect speech creates awkward prose.
    RECALL_VERBS = {
        'recalling', 'remembering', 'recollecting',  # Memory verbs
        'joking', 'quipping', 'musing',              # Informal speech verbs
        'reflecting', 'wondering', 'pondering',      # Contemplation verbs
        'continuing', 'proceeding',                   # Continuation verbs
    }

    # Pattern: ", <recall_verb>, <Capital>" - double wrapper with recalled quote
    # Example: "Deutsch mentions the exchange, recalling, It's funny..."
    # This pattern catches quote introducers that leaked into prose.
    recall_verb_pattern = re.compile(
        r',\s*'                             # Leading comma
        r'(' + '|'.join(RECALL_VERBS) + ')' # One of the recall verbs (group 1)
        r'\s*,\s*'                          # Comma after verb
        r'([A-Z])',                         # Capital letter (group 2)
        re.IGNORECASE
    )

    # Pattern: "As <Name> <verb> that" - broken grammar, speaker framing leak
    # Example: "As Deutsch notes that what we call wisdom..."
    # This is grammatically broken. Valid forms:
    #   - "As Deutsch notes, what we call..." (interpolation with comma)
    #   - "Deutsch notes that what we call..." (indirect speech)
    # The "As X verb that" form is speaker framing that leaked through.
    # Action: DROP the entire sentence (no speaker framing in prose).
    as_verb_that_pattern = re.compile(
        r'\bAs\s+'                          # "As " (word boundary)
        r'(?:Deutsch|David\s+Deutsch|He|She|They|The\s+(?:guest|host|speaker))\s+'  # Subject
        r'(?:notes?|argues?|says?|observes?|suggests?|claims?|states?|explains?|'
        r'warns?|points?\s+out|remarks?|contends?|believes?|maintains?|asserts?)\s+'  # Verb
        r'that\b',                          # "that" (the broken part)
        re.IGNORECASE
    )

    rewrite_count = 0
    sentences_dropped = 0
    rewrite_details = []
    drop_details = []

    # Words that should be lowercased after "that" (pronouns/determiners)
    # These are never proper nouns, so always safe to lowercase
    LOWERCASE_AFTER_THAT = {
        'this', 'that', 'these', 'those', 'it', 'we', 'they', 'he', 'she',
        'the', 'a', 'an', 'our', 'their', 'his', 'her', 'its', 'my', 'your',
        'such', 'there', 'here', 'what', 'which', 'who', 'how', 'when', 'where',
    }

    def rewrite_to_indirect(match):
        """Convert direct attribution to indirect speech.

        IMPORTANT: Skip these patterns (return unchanged):
        1. Parenthetical: ", Deutsch points out, are..." (leading comma + lowercase payload)
        2. Interpolation: ", as Deutsch argues, is..." (preceded by ", as " or " as ")
        Only introducer patterns should get "that".
        """
        nonlocal rewrite_count
        leading_comma = match.group(1)  # Optional leading comma
        subject_verb = match.group(2)
        punctuation = match.group(3)
        first_letter = match.group(4)

        # SKIP parenthetical attributions: ", Deutsch points out, are..."
        # If there's a leading comma AND the payload starts with lowercase,
        # it's a parenthetical insert, not a clause introducer
        if leading_comma and first_letter.islower():
            # Return the original match unchanged
            return match.group(0)

        # SKIP interpolations: ", as Deutsch argues, is..." or "As Deutsch remarks, this..."
        # Check the left context for "as " pattern preceding the subject
        match_start = match.start()
        # Get text before the match (up to 20 chars for context)
        left_context = text[max(0, match_start - 20):match_start].lower()
        # Check if this is an "as X argues" interpolation
        # Pattern: ", as " or " as " immediately before the match
        if re.search(r',?\s+as\s*$', left_context):
            # This is an interpolation like ", as Deutsch argues, is"
            # Don't rewrite - return original
            return match.group(0)

        # Handle "points" → "points out" (grammatically required)
        # "He points, This" → "He points out that this"
        if re.search(r'\bpoints?\s*$', subject_verb, re.IGNORECASE):
            if not re.search(r'\bpoints?\s+out\s*$', subject_verb, re.IGNORECASE):
                subject_verb = re.sub(r'(\bpoints?)\s*$', r'\1 out', subject_verb, flags=re.IGNORECASE)

        # Build the replacement: "says," → "says that"
        # Lowercase the first letter of payload
        # Preserve leading comma if present
        prefix = leading_comma if leading_comma else ""
        replacement = f"{prefix}{subject_verb} that {first_letter.lower()}"

        rewrite_count += 1
        original = match.group(0)
        rewrite_details.append({
            "original": original,
            "replacement": replacement[:len(original) + 10],
        })

        return replacement

    def fix_that_capitalization(text_to_fix: str) -> str:
        """Fix 'that This/That/These...' patterns to lowercase.

        Catches cases where 'that' is followed by a capitalized
        pronoun/determiner that should be lowercase in indirect speech.
        E.g., 'suggests that This' → 'suggests that this'
        """
        def lowercase_after_that(m):
            word = m.group(1)
            if word.lower() in LOWERCASE_AFTER_THAT:
                return f"that {word.lower()}"
            return m.group(0)  # Keep original if it's a proper noun

        return re.sub(
            r'\bthat\s+([A-Z][a-z]+)\b',
            lowercase_after_that,
            text_to_fix
        )

    def remove_colon_wrapper(match):
        """Remove colon wrappers, keeping just the content.

        'Deutsch captures this shift: This revolution...' → 'This revolution...'

        We remove the wrapper entirely because converting to indirect speech
        would be awkward ('Deutsch captures this shift that this revolution...')
        """
        nonlocal rewrite_count
        wrapper = match.group(1)
        colon = match.group(2)
        first_letter = match.group(3)

        rewrite_count += 1
        rewrite_details.append({
            "original": match.group(0),
            "replacement": f"[wrapper removed] {first_letter}",
        })

        # Keep just the first letter (start of actual content)
        return first_letter

    def remove_orphan_wrapper(match):
        """Remove orphan wrappers, preserving sentence flow.

        'The shift occurred, noting. This led to...' → 'The shift occurred. This led to...'

        Orphan wrappers are participial verbs that were supposed to introduce
        a quote, but the quote was removed. We remove the orphan verb and
        keep the sentence boundary.
        """
        nonlocal rewrite_count
        verb = match.group(1)
        period_space = match.group(2)
        first_letter = match.group(3)

        rewrite_count += 1
        rewrite_details.append({
            "original": match.group(0),
            "replacement": f"[orphan '{verb}' removed]. {first_letter}",
        })

        # Replace orphan verb with just the sentence boundary
        # period_space already contains the period, so just use it directly
        return f"{period_space}{first_letter}"

    # Split into paragraphs to track sections
    paragraphs = text.split('\n\n')
    result_paragraphs = []

    in_key_excerpts = False
    in_core_claims = False

    for para in paragraphs:
        stripped = para.strip()

        # Track section boundaries
        if '### Key Excerpts' in stripped:
            in_key_excerpts = True
            in_core_claims = False
            result_paragraphs.append(para)
            continue
        elif '### Core Claims' in stripped:
            in_key_excerpts = False
            in_core_claims = True
            result_paragraphs.append(para)
            continue
        elif stripped.startswith('## '):
            in_key_excerpts = False
            in_core_claims = False
            result_paragraphs.append(para)
            continue
        elif stripped.startswith('### '):
            in_key_excerpts = False
            in_core_claims = False
            result_paragraphs.append(para)
            continue

        # Don't modify Key Excerpts or Core Claims content
        if in_key_excerpts or in_core_claims:
            result_paragraphs.append(para)
            continue

        # Skip blockquotes
        if stripped.startswith('>'):
            result_paragraphs.append(para)
            continue

        # STEP 1: Drop sentences containing problematic patterns (unrewritable leaks)
        # These are P0 drops - patterns that indicate quote-introducer or speaker framing leaks
        # Examples:
        #   - "Deutsch mentions the exchange, recalling, It's funny..." (recall verb leak)
        #   - "As Deutsch notes that what we call wisdom..." (broken "As X verb that" grammar)
        modified = para
        has_recall_verb = recall_verb_pattern.search(modified)
        has_as_verb_that = as_verb_that_pattern.search(modified)

        if has_recall_verb or has_as_verb_that:
            # Split into sentences and filter out bad ones
            # Use conservative sentence splitting
            sentence_pattern = re.compile(r'(?<=[.!?])\s+(?=[A-Z])')
            sentences = sentence_pattern.split(modified)
            kept_sentences = []

            for sentence in sentences:
                if recall_verb_pattern.search(sentence):
                    # Drop this sentence - recall verb leak
                    sentences_dropped += 1
                    drop_details.append({
                        "type": "recall_verb_leak",
                        "dropped_sentence": sentence[:100] + ("..." if len(sentence) > 100 else ""),
                    })
                elif as_verb_that_pattern.search(sentence):
                    # Drop this sentence - "As X verb that" broken grammar / speaker framing
                    sentences_dropped += 1
                    drop_details.append({
                        "type": "as_verb_that_leak",
                        "dropped_sentence": sentence[:100] + ("..." if len(sentence) > 100 else ""),
                    })
                else:
                    kept_sentences.append(sentence)

            # Rejoin remaining sentences
            if kept_sentences:
                modified = ' '.join(kept_sentences)
            else:
                # All sentences dropped - skip this paragraph entirely
                continue

        # STEP 2: Apply rewrites to narrative prose
        modified = rewrite_pattern.sub(rewrite_to_indirect, modified)
        modified = participial_pattern.sub(rewrite_to_indirect, modified)
        modified = colon_wrapper_pattern.sub(remove_colon_wrapper, modified)
        modified = orphan_wrapper_pattern.sub(remove_orphan_wrapper, modified)

        # Fix any "that This/That/These..." capitalization issues
        modified = fix_that_capitalization(modified)

        result_paragraphs.append(modified)

    result = '\n\n'.join(result_paragraphs)

    if rewrite_count > 0:
        logger.info(f"Dangling attribution gate: rewrote {rewrite_count} patterns to indirect speech")
    if sentences_dropped > 0:
        logger.info(f"Dangling attribution gate: dropped {sentences_dropped} sentences with recall verb leaks")

    return result, {
        "rewrites_applied": rewrite_count,
        "rewrite_details": rewrite_details,
        "sentences_dropped": sentences_dropped,
        "drop_details": drop_details,
    }


def sanitize_speaker_framing(text: str) -> tuple[str, dict]:
    """Drop sentences with attribution-wrapper patterns from narrative prose.

    VERB-AGNOSTIC approach: instead of matching specific verbs, match the
    structural pattern that indicates attributed speech leaked into prose.

    Drop patterns (sentence-level):
    1. (Name|He|She|They) <any words>, <Capital> - "He elaborates, In every..."
    2. Name's <noun> <verb> - "Deutsch's book suggests..."
    3. According to Name, ... - "According to Deutsch, ..."
    4. As Name <adverb?> verb that - "As Deutsch aptly suggests that..."
    5. Generic speaker attribution - "One scholar noted...", "An influential thinker remarked..."
    6. As/According to generic speaker - "As one scholar noted,", "According to some researchers,"
    7. Orphan pronouns with no antecedent - If no sentences kept yet and this starts with It/This/They/These

    This catches ALL attribution wrappers (named and generic) without needing a verb list.
    The final style invariant: no attribution framing at all in timeless prose.

    Args:
        text: The draft markdown text.

    Returns:
        Tuple of (sanitized_text, report_dict).
    """
    sentences_dropped = 0
    drop_details = []

    # Person names (not pronouns - those are handled separately)
    PERSON_NAMES = r'(?:Deutsch|David\s+Deutsch|Hawking|Stephen\s+Hawking)'

    # Pronouns that can introduce attributed speech
    PRONOUNS = r'(?:He|She|They)'

    # Pattern 1: (Name|Pronoun) <any words>, <Capital letter>
    # Catches: "He elaborates, In every...", "Deutsch acknowledges, We have..."
    # The comma followed by capital letter indicates quoted speech
    attribution_comma_capital = re.compile(
        r'\b(?:' + PERSON_NAMES + r'|' + PRONOUNS + r')\s+'  # Name or pronoun
        r'[^.!?]*'                                            # Any words (not sentence-ending)
        r',\s*'                                               # Comma
        r'[A-Z]',                                             # Capital letter (start of quote)
        re.IGNORECASE
    )

    # Pattern 2: Name's <word> <word> - possessive attribution
    # Catches: "Deutsch's book suggests...", "Hawking's view implies..."
    possessive_attribution = re.compile(
        r"\b(?:Deutsch|Hawking|David\s+Deutsch|Stephen\s+Hawking)'s\s+\w+",
        re.IGNORECASE
    )

    # Pattern 3: According to Name
    # Catches: "According to Deutsch, ..."
    according_to_pattern = re.compile(
        r'\bAccording\s+to\s+' + PERSON_NAMES + r'\b',
        re.IGNORECASE
    )

    # Pattern 4: As Name <adverb?> verb that - broken grammar leak
    # Catches: "As Deutsch aptly suggests that..."
    as_name_verb_that = re.compile(
        r'\bAs\s+' + PERSON_NAMES + r'\s+(?:\w+ly\s+)?(?:\w+)\s+that\b',
        re.IGNORECASE
    )

    # Pattern 5: Generic speaker attribution - "one scholar noted", "an influential thinker remarked"
    # Catches: "One scholar noted, The scientific...", "An influential thinker once remarked,"
    # This is the final style invariant - no attribution framing at all in timeless prose
    GENERIC_SPEAKERS = r'(?:scholar|thinker|philosopher|researcher|historian|figure|commentator|observer|writer|author)'
    ATTRIBUTION_VERBS = r'(?:noted|remarked|observed|argued|said|suggested|pointed\s+out|stated|claimed|wrote|explained)'
    generic_speaker_attribution = re.compile(
        r'\b(?:one|a|an|the|some)\s+'           # Article
        r'(?:\w+\s+)?'                           # Optional adjective: "influential", "noted"
        r'' + GENERIC_SPEAKERS + r'\s+'         # Generic speaker noun
        r'(?:once\s+)?'                          # Optional "once"
        r'' + ATTRIBUTION_VERBS + r'\b',        # Attribution verb
        re.IGNORECASE
    )

    # Pattern 6: "As/According to one scholar..." - generic framing
    # Catches: "As one scholar noted,", "According to some researchers,"
    as_generic_speaker = re.compile(
        r'\b(?:as|according\s+to)\s+'           # "As" or "According to"
        r'(?:one|some|a|an)\s+'                  # Article
        r'(?:\w+\s+)?'                           # Optional adjective
        r'' + GENERIC_SPEAKERS + r'\b',         # Generic speaker noun
        re.IGNORECASE
    )

    def is_attribution_sentence(sentence: str) -> tuple[bool, str]:
        """Check if sentence contains attribution wrapper. Returns (is_bad, pattern_type)."""
        if attribution_comma_capital.search(sentence):
            return True, "attribution_comma_capital"
        if possessive_attribution.search(sentence):
            return True, "possessive_attribution"
        if according_to_pattern.search(sentence):
            return True, "according_to"
        if as_name_verb_that.search(sentence):
            return True, "as_name_verb_that"
        if generic_speaker_attribution.search(sentence):
            return True, "generic_speaker_attribution"
        if as_generic_speaker.search(sentence):
            return True, "as_generic_speaker"
        return False, ""

    # Process paragraph by paragraph
    paragraphs = text.split('\n\n')
    result_paragraphs = []

    in_key_excerpts = False
    in_core_claims = False

    for para in paragraphs:
        stripped = para.strip()

        # Track section boundaries
        if '### Key Excerpts' in stripped:
            in_key_excerpts = True
            in_core_claims = False
            result_paragraphs.append(para)
            continue
        elif '### Core Claims' in stripped:
            in_key_excerpts = False
            in_core_claims = True
            result_paragraphs.append(para)
            continue
        elif stripped.startswith('## '):
            in_key_excerpts = False
            in_core_claims = False
            result_paragraphs.append(para)
            continue
        elif stripped.startswith('### '):
            in_key_excerpts = False
            in_core_claims = False
            result_paragraphs.append(para)
            continue

        # Don't modify Key Excerpts or Core Claims content
        if in_key_excerpts or in_core_claims:
            result_paragraphs.append(para)
            continue

        # Skip blockquotes
        if stripped.startswith('>'):
            result_paragraphs.append(para)
            continue

        # Split into sentences and filter out bad ones
        sentence_pattern = re.compile(r'(?<=[.!?])\s+(?=[A-Z])')
        sentences = sentence_pattern.split(para)
        kept_sentences = []

        # Orphan pronoun pattern - these need antecedent from previous sentence
        ORPHAN_PRONOUNS = re.compile(r'^(?:It|This|These|They|That|Those)\s+', re.IGNORECASE)

        for sentence in sentences:
            is_bad, pattern_type = is_attribution_sentence(sentence)

            # Mid-paragraph orphan-pronoun cleanup:
            # If NO sentences have been kept yet and this one starts with It/This/They/These,
            # the pronoun has no antecedent in this paragraph - drop it too
            if not is_bad and len(kept_sentences) == 0 and ORPHAN_PRONOUNS.match(sentence.strip()):
                is_bad = True
                pattern_type = "orphan_pronoun_no_antecedent"

            if is_bad:
                sentences_dropped += 1
                drop_details.append({
                    "type": pattern_type,
                    "dropped_sentence": sentence[:100] + ("..." if len(sentence) > 100 else ""),
                })
            else:
                kept_sentences.append(sentence)

        # Rejoin remaining sentences
        if kept_sentences:
            result_paragraphs.append(' '.join(kept_sentences))
        # If all sentences dropped, skip this paragraph entirely

    result = '\n\n'.join(result_paragraphs)

    if sentences_dropped > 0:
        logger.info(f"Speaker-framing sanitizer: dropped {sentences_dropped} sentences")

    return result, {
        "sentences_dropped": sentences_dropped,
        "drop_details": drop_details,
    }


def enforce_no_names_in_prose(
    text: str,
    person_blacklist: "PersonBlacklist | None" = None,
    entity_allowlist: "EntityAllowlist | None" = None,
) -> tuple[str, dict]:
    """Enforce 'no person names in narrative prose' as a hard invariant.

    Policy: Narrative prose must not contain PERSON names (speakers or third-party),
    but MAY contain org/product names if they appear in the transcript.

    When person_blacklist is provided (dynamic mode):
    - Uses speaker names from whitelist as the blacklist
    - Checks entity_allowlist before dropping (allows transcript-attested orgs)

    When person_blacklist is None (legacy mode):
    - Falls back to hardcoded physicist names for backwards compatibility

    Args:
        text: The draft markdown text.
        person_blacklist: Optional dynamic blacklist from speakers.
        entity_allowlist: Optional allowlist for org/product names.

    Returns:
        Tuple of (enforced_text, report_dict).
    """
    sentences_dropped = 0
    sentences_kept_due_to_allowlist = 0
    drop_details = []
    kept_details = []

    # Import here to avoid circular imports
    from .entity_allowlist import PersonBlacklist, EntityAllowlist

    # Legacy fallback: hardcoded names for backwards compatibility
    LEGACY_FORBIDDEN_NAMES = re.compile(
        r'\b(?:'
        r'Deutsch|David\s+Deutsch|'
        r'Hawking|Stephen\s+Hawking|'
        r'Einstein|Albert\s+Einstein|'
        r'Bohr|Niels\s+Bohr|'
        r'Popper|Karl\s+Popper'
        r')\b',
        re.IGNORECASE
    )

    # Pattern to extract potential name spans for checking
    # Matches: Capitalized words, multi-word Capitalized sequences
    NAME_SPAN_PATTERN = re.compile(
        r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b'
    )

    # Process paragraph by paragraph
    paragraphs = text.split('\n\n')
    result_paragraphs = []

    in_key_excerpts = False
    in_core_claims = False

    for para in paragraphs:
        stripped = para.strip()

        # Track section boundaries
        if '### Key Excerpts' in stripped:
            in_key_excerpts = True
            in_core_claims = False
            result_paragraphs.append(para)
            continue
        elif '### Core Claims' in stripped:
            in_key_excerpts = False
            in_core_claims = True
            result_paragraphs.append(para)
            continue
        elif stripped.startswith('## '):
            in_key_excerpts = False
            in_core_claims = False
            result_paragraphs.append(para)
            continue
        elif stripped.startswith('### '):
            in_key_excerpts = False
            in_core_claims = False
            result_paragraphs.append(para)
            continue

        # Don't modify Key Excerpts or Core Claims content
        if in_key_excerpts or in_core_claims:
            result_paragraphs.append(para)
            continue

        # Skip blockquotes
        if stripped.startswith('>'):
            result_paragraphs.append(para)
            continue

        # Helper function to check if sentence should be dropped
        def should_drop_sentence(sentence: str) -> tuple[bool, str, str | None]:
            """Check if sentence contains forbidden person name.

            Returns: (should_drop, reason, matched_name)
            """
            if person_blacklist is not None:
                # Dynamic mode: use provided blacklist + allowlist
                # Find all name-like spans in sentence
                name_spans = NAME_SPAN_PATTERN.findall(sentence)

                for span in name_spans:
                    # Check if it's a person name
                    if person_blacklist.matches(span):
                        # Check if it's allowlisted as org/product
                        if entity_allowlist and entity_allowlist.contains(span):
                            # It's an allowlisted entity, don't drop for this
                            continue
                        # It's a person name, drop
                        return True, "person_name_in_prose", span

                return False, "", None
            else:
                # Legacy mode: use hardcoded names
                if LEGACY_FORBIDDEN_NAMES.search(sentence):
                    match = LEGACY_FORBIDDEN_NAMES.search(sentence)
                    return True, "name_in_prose_legacy", match.group(0) if match else None
                return False, "", None

        # Check if paragraph might contain names (quick check)
        might_have_names = False
        if person_blacklist is not None:
            # Check against dynamic blacklist
            might_have_names = person_blacklist.matches(para)
        else:
            # Check against legacy pattern
            might_have_names = bool(LEGACY_FORBIDDEN_NAMES.search(para))

        if might_have_names:
            # Split into sentences and filter out bad ones
            sentence_pattern = re.compile(r'(?<=[.!?])\s+(?=[A-Z])')
            sentences = sentence_pattern.split(para)
            kept_sentences = []

            for sentence in sentences:
                should_drop, reason, matched_name = should_drop_sentence(sentence)

                if should_drop:
                    sentences_dropped += 1
                    drop_details.append({
                        "type": reason,
                        "matched_name": matched_name,
                        "dropped_sentence": sentence[:100] + ("..." if len(sentence) > 100 else ""),
                    })
                else:
                    kept_sentences.append(sentence)

            # Rejoin remaining sentences
            if kept_sentences:
                result_paragraphs.append(' '.join(kept_sentences))
            # If all sentences dropped, skip this paragraph entirely
        else:
            result_paragraphs.append(para)

    result = '\n\n'.join(result_paragraphs)

    if sentences_dropped > 0:
        logger.info(f"No-names-in-prose invariant: dropped {sentences_dropped} sentences")
    if sentences_kept_due_to_allowlist > 0:
        logger.info(f"No-names-in-prose: kept {sentences_kept_due_to_allowlist} sentences due to entity allowlist")

    return result, {
        "sentences_dropped": sentences_dropped,
        "sentences_kept_due_to_allowlist": sentences_kept_due_to_allowlist,
        "drop_details": drop_details,
        "kept_details": kept_details,
    }


# Keep old function name as alias for backward compatibility in pipeline
def enforce_speaker_framing_invariant(text: str) -> tuple[str, dict]:
    """Alias for enforce_no_names_in_prose for backward compatibility."""
    result, report = enforce_no_names_in_prose(text)
    # Remap report keys for compatibility
    return result, {
        "speaker_framing_sentences_dropped": report["sentences_dropped"],
        "drop_details": report["drop_details"],
    }


def sanitize_meta_discourse(text: str) -> tuple[str, dict]:
    """Drop sentences that describe the document itself from narrative prose.

    Meta-discourse is template/prompt text that leaked into the output.
    Instead of matching specific leaked phrases, we ban the structural pattern:
    sentences that reference document structure.

    Drop sentences containing:
    - "this chapter/section" - referencing the current document part
    - "the excerpts" / "the claims" - referencing document sections
    - "this edition/draft" - referencing the document
    - "in the following" / "as we'll see" - forward references
    - "below/above" - document navigation
    - "in summary" - meta-commentary

    Args:
        text: The draft markdown text.

    Returns:
        Tuple of (sanitized_text, report_dict).
    """
    sentences_dropped = 0
    drop_details = []

    # Meta-discourse patterns - references to document structure
    # These indicate template/prompt text that leaked through
    META_DISCOURSE_PATTERNS = re.compile(
        r'\b(?:'
        # Document part references
        r'this\s+(?:chapter|section|part|segment)|'
        r'(?:the\s+)?(?:chapter|section)\s+(?:develops?|explores?|examines?|discusses?|threads?)|'
        # Section references - "the excerpts preserve", "excerpts preserve"
        r'(?:the\s+)?excerpts?\s+(?:preserve|show|demonstrate|illustrate)|'
        r'(?:the\s+)?claims?\s+(?:synthesize|summarize|capture)|'
        r'key\s+excerpts?\s+(?:section|below)|'
        r'core\s+claims?\s+(?:section|below)|'
        # Document references
        r'this\s+(?:edition|draft|document)|'
        # Forward/backward references
        r'in\s+the\s+following|'
        r'as\s+we\'ll\s+see|'
        r'as\s+we\s+will\s+see|'
        r'see\s+below|'
        r'(?:above|below)\s+(?:we|you|the)|'
        r'mentioned\s+(?:above|below)|'
        r'discussed\s+(?:above|below)|'
        # Meta-commentary
        r'in\s+summary|'
        r'to\s+summarize|'
        r'in\s+conclusion'
        r')\b',
        re.IGNORECASE
    )

    # Process paragraph by paragraph
    paragraphs = text.split('\n\n')
    result_paragraphs = []

    in_key_excerpts = False
    in_core_claims = False

    for para in paragraphs:
        stripped = para.strip()

        # Track section boundaries
        if '### Key Excerpts' in stripped:
            in_key_excerpts = True
            in_core_claims = False
            result_paragraphs.append(para)
            continue
        elif '### Core Claims' in stripped:
            in_key_excerpts = False
            in_core_claims = True
            result_paragraphs.append(para)
            continue
        elif stripped.startswith('## '):
            in_key_excerpts = False
            in_core_claims = False
            result_paragraphs.append(para)
            continue
        elif stripped.startswith('### '):
            in_key_excerpts = False
            in_core_claims = False
            result_paragraphs.append(para)
            continue

        # Don't modify Key Excerpts or Core Claims content
        if in_key_excerpts or in_core_claims:
            result_paragraphs.append(para)
            continue

        # Skip blockquotes
        if stripped.startswith('>'):
            result_paragraphs.append(para)
            continue

        # Check if paragraph contains any meta-discourse patterns
        if META_DISCOURSE_PATTERNS.search(para):
            # Split into sentences and filter out bad ones
            sentence_pattern = re.compile(r'(?<=[.!?])\s+(?=[A-Z])')
            sentences = sentence_pattern.split(para)
            kept_sentences = []

            for sentence in sentences:
                if META_DISCOURSE_PATTERNS.search(sentence):
                    sentences_dropped += 1
                    drop_details.append({
                        "type": "meta_discourse",
                        "dropped_sentence": sentence[:100] + ("..." if len(sentence) > 100 else ""),
                    })
                else:
                    kept_sentences.append(sentence)

            # Rejoin remaining sentences
            if kept_sentences:
                result_paragraphs.append(' '.join(kept_sentences))
            # If all sentences dropped, skip this paragraph entirely
        else:
            result_paragraphs.append(para)

    result = '\n\n'.join(result_paragraphs)

    if sentences_dropped > 0:
        logger.info(f"Meta-discourse gate: dropped {sentences_dropped} sentences")

    return result, {
        "sentences_dropped": sentences_dropped,
        "drop_details": drop_details,
    }


def normalize_prose_punctuation(text: str) -> tuple[str, dict]:
    """Ensure narrative prose paragraphs end with proper terminal punctuation.

    For narrative prose only (not blockquotes, not headings, not inside quotes):
    If a paragraph ends with an alphanumeric character (no terminal punctuation),
    append a period.

    This is a final formatting pass that runs after all drops/repairs.

    Args:
        text: The draft markdown text.

    Returns:
        Tuple of (normalized_text, report_dict).
    """
    fixes_applied = 0
    fix_details = []

    # Process paragraph by paragraph
    paragraphs = text.split('\n\n')
    result_paragraphs = []

    in_key_excerpts = False
    in_core_claims = False

    for para in paragraphs:
        stripped = para.strip()

        # Track section boundaries
        if '### Key Excerpts' in stripped:
            in_key_excerpts = True
            in_core_claims = False
            result_paragraphs.append(para)
            continue
        elif '### Core Claims' in stripped:
            in_key_excerpts = False
            in_core_claims = True
            result_paragraphs.append(para)
            continue
        elif stripped.startswith('## '):
            in_key_excerpts = False
            in_core_claims = False
            result_paragraphs.append(para)
            continue
        elif stripped.startswith('### '):
            in_key_excerpts = False
            in_core_claims = False
            result_paragraphs.append(para)
            continue

        # Don't modify Key Excerpts or Core Claims content
        if in_key_excerpts or in_core_claims:
            result_paragraphs.append(para)
            continue

        # Skip blockquotes
        if stripped.startswith('>'):
            result_paragraphs.append(para)
            continue

        # Skip headings (any level)
        if stripped.startswith('#'):
            result_paragraphs.append(para)
            continue

        # Skip empty paragraphs
        if not stripped:
            result_paragraphs.append(para)
            continue

        # Check if paragraph ends without terminal punctuation
        # Terminal punctuation: . ? ! … — "
        # We check the last non-whitespace character
        last_char = stripped[-1] if stripped else ''

        if last_char.isalnum():
            # Missing terminal punctuation - append period
            # Preserve original whitespace by working with the original para
            fixed_para = para.rstrip() + '.'
            result_paragraphs.append(fixed_para)
            fixes_applied += 1
            fix_details.append({
                "original_ending": stripped[-20:] if len(stripped) > 20 else stripped,
                "fixed": True,
            })
        else:
            result_paragraphs.append(para)

    result = '\n\n'.join(result_paragraphs)

    if fixes_applied > 0:
        logger.info(f"Prose punctuation normalizer: fixed {fixes_applied} paragraphs")

    return result, {
        "fixes_applied": fixes_applied,
        "fix_details": fix_details,
    }


def cleanup_dangling_connectives(text: str) -> tuple[str, dict]:
    """Clean up dangling articles/connectives left when payload was dropped.

    When a gate drops a quote or clause but doesn't expand the deletion to
    include the grammatical "handle", we get broken patterns like:
        - "offers a . Traits that once helped..." (dangling article)
        - "suggesting that . This stark warning..." (dangling 'that' introducer)

    This function cleans up these orphaned connectives deterministically.

    Args:
        text: The draft markdown text.

    Returns:
        Tuple of (cleaned_text, report_dict).
    """
    cleanup_count = 0
    cleanup_details = []

    # Pattern A: Dangling determiners/articles before sentence boundary
    # "offers a . Traits" or "the . This" - delete the broken fragment
    # We delete from the start of the broken clause (after previous sentence end)
    dangling_article_pattern = re.compile(
        r'([.!?]\s+)'           # Previous sentence end (group 1)
        r'([^.!?]*?)'           # Any content before the article (group 2)
        r'\b(a|an|the)\s*'      # The dangling article (group 3)
        r'\.\s+'                # The orphan period + space
        r'([A-Z])',             # Start of next sentence (group 4)
        re.IGNORECASE
    )

    def fix_dangling_article(match):
        nonlocal cleanup_count
        prev_sentence_end = match.group(1)
        fragment_before = match.group(2).strip()
        article = match.group(3)
        next_sentence_start = match.group(4)

        cleanup_count += 1
        cleanup_details.append({
            "type": "dangling_article",
            "original": match.group(0)[:50] + "...",
            "article": article,
        })

        # If there's meaningful content before the dangling article, try to salvage
        # Otherwise just connect to next sentence
        if fragment_before and len(fragment_before) > 10:
            # There's a partial sentence - end it properly and start next
            return f"{prev_sentence_end}{fragment_before}. {next_sentence_start}"
        else:
            # Just the dangling article - skip to next sentence
            return f"{prev_sentence_end}{next_sentence_start}"

    # Pattern B: Dangling "that" introducers after attribution verbs
    # ", suggesting that . This" → ". This"
    dangling_that_pattern = re.compile(
        r',\s*'                 # Comma before the attribution
        r'(suggesting|stating|arguing|claiming|warning|noting|'
        r'observing|explaining|asserting|contending|maintaining|'
        r'emphasizing|stressing|adding|remarking)'
        r'\s+that\s*'          # The verb + "that"
        r'\.\s+'               # Orphan period + space
        r'([A-Z])',            # Start of next sentence
        re.IGNORECASE
    )

    def fix_dangling_that(match):
        nonlocal cleanup_count
        verb = match.group(1)
        next_sentence_start = match.group(2)

        cleanup_count += 1
        cleanup_details.append({
            "type": "dangling_that_introducer",
            "original": match.group(0),
            "verb": verb,
        })

        # Replace ", suggesting that ." with ". "
        return f". {next_sentence_start}"

    # Pattern C: Simple dangling article at start or after comma
    # "However, Stephen Hawking offers a . Traits" - the "However..." clause is broken
    # We need to delete from the clause start
    simple_dangling_pattern = re.compile(
        r'([A-Z][^.!?]*?)'      # Sentence fragment starting with capital (group 1)
        r'\b(a|an|the)\s*'      # Dangling article (group 2)
        r'\.\s+'                # Orphan period
        r'([A-Z])',             # Next sentence start (group 3)
    )

    def fix_simple_dangling(match):
        nonlocal cleanup_count
        fragment = match.group(1).strip()
        article = match.group(2)
        next_start = match.group(3)

        # Only fix if the fragment ends awkwardly (with a verb or preposition)
        # This avoids false positives on valid sentences
        awkward_endings = (
            'offers', 'offer', 'offered',
            'provides', 'provide', 'provided',
            'gives', 'give', 'gave',
            'presents', 'present', 'presented',
            'has', 'have', 'had',
            'is', 'are', 'was', 'were',
            'requires', 'require', 'required',
            'needs', 'need', 'needed',
            'describes', 'describe', 'described',
            'mentions', 'mention', 'mentioned',
        )

        words = fragment.split()
        if words and words[-1].lower() in awkward_endings:
            cleanup_count += 1
            cleanup_details.append({
                "type": "dangling_article_clause",
                "original": match.group(0)[:60] + "...",
                "fragment": fragment[-30:] if len(fragment) > 30 else fragment,
            })
            # Delete the broken clause entirely, keep next sentence
            return next_start
        else:
            # Not a clear case - leave it alone
            return match.group(0)

    # Split into paragraphs and process only narrative prose
    paragraphs = text.split('\n\n')
    result_paragraphs = []

    in_key_excerpts = False
    in_core_claims = False

    for para in paragraphs:
        stripped = para.strip()

        # Track section boundaries
        if '### Key Excerpts' in stripped:
            in_key_excerpts = True
            in_core_claims = False
            result_paragraphs.append(para)
            continue
        elif '### Core Claims' in stripped:
            in_key_excerpts = False
            in_core_claims = True
            result_paragraphs.append(para)
            continue
        elif stripped.startswith('## '):
            in_key_excerpts = False
            in_core_claims = False
            result_paragraphs.append(para)
            continue
        elif stripped.startswith('### '):
            in_key_excerpts = False
            in_core_claims = False
            result_paragraphs.append(para)
            continue

        # Don't modify Key Excerpts or Core Claims content
        if in_key_excerpts or in_core_claims:
            result_paragraphs.append(para)
            continue

        # Skip blockquotes
        if stripped.startswith('>'):
            result_paragraphs.append(para)
            continue

        # Apply cleanups to narrative prose
        modified = para
        modified = dangling_that_pattern.sub(fix_dangling_that, modified)
        modified = dangling_article_pattern.sub(fix_dangling_article, modified)
        modified = simple_dangling_pattern.sub(fix_simple_dangling, modified)

        result_paragraphs.append(modified)

    result = '\n\n'.join(result_paragraphs)

    if cleanup_count > 0:
        logger.info(f"Dangling connective cleanup: fixed {cleanup_count} orphaned articles/connectives")

    return result, {
        "cleanups_applied": cleanup_count,
        "cleanup_details": cleanup_details,
    }


def fix_truncated_attributions(text: str) -> tuple[str, dict]:
    """Fix attributions that got truncated at end of line/paragraph.

    Detects patterns like:
        "Deutsch notes,"

        "This transformation went beyond..."

    And joins them:
        "Deutsch notes that this transformation went beyond..."

    Args:
        text: The draft markdown text.

    Returns:
        Tuple of (fixed_text, report_dict).
    """
    # Pattern for attribution verb ending a paragraph (followed by paragraph break)
    # "Deutsch notes," or "He says," at end of line
    truncated_pattern = re.compile(
        r'((?:Deutsch|David Deutsch|He|She|They)\s+'
        r'(?:notes?|observes?|argues?|says?|states?|explains?|suggests?|'
        r'points?(?:\s+out)?|warns?|cautions?|asserts?|claims?|contends?|'
        r'remarks?|adds?|believes?|maintains?|emphasizes?))'
        r'\s*[,:]\s*$',  # Ends with comma/colon at end of line
        re.IGNORECASE | re.MULTILINE
    )

    fixes = []
    lines = text.split('\n')
    result_lines = []
    i = 0

    while i < len(lines):
        line = lines[i]
        match = truncated_pattern.search(line)

        if match:
            # Found truncated attribution - look for next non-empty line
            subject_verb = match.group(1)
            j = i + 1

            # Skip empty lines
            while j < len(lines) and not lines[j].strip():
                j += 1

            if j < len(lines):
                next_line = lines[j].strip()
                # Don't join with headers or special content
                if not next_line.startswith('#') and not next_line.startswith('>'):
                    # Handle "points" → "points out"
                    if re.search(r'\bpoints?\s*$', subject_verb, re.IGNORECASE):
                        if not re.search(r'\bpoints?\s+out\s*$', subject_verb, re.IGNORECASE):
                            subject_verb = re.sub(r'(\bpoints?)\s*$', r'\1 out', subject_verb, flags=re.IGNORECASE)

                    # Join with "that" and lowercase first letter
                    first_char = next_line[0].lower() if next_line else ''
                    rest = next_line[1:] if len(next_line) > 1 else ''
                    joined = f"{line[:match.start()]}{subject_verb} that {first_char}{rest}"

                    fixes.append({
                        "original_line": line.strip(),
                        "next_line": next_line[:40] + "..." if len(next_line) > 40 else next_line,
                        "joined": joined[:60] + "..." if len(joined) > 60 else joined,
                    })

                    result_lines.append(joined)
                    # Skip the lines we consumed (empty lines + content line)
                    i = j + 1
                    continue

        result_lines.append(line)
        i += 1

    result = '\n'.join(result_lines)

    if fixes:
        logger.info(f"Fixed {len(fixes)} truncated attributions by joining paragraphs")

    return result, {
        "fixes_applied": len(fixes),
        "fix_details": fixes,
    }


# Known valid short words that can follow "he " legitimately
VALID_HE_WORDS = {
    'is', 'was', 'has', 'had', 'can', 'may', 'did', 'does', 'will', 'would',
    'could', 'should', 'might', 'must', 'a', 'an', 'the', 'and', 'or', 'but',
    'in', 'on', 'at', 'to', 'of', 'for', 'by', 'as', 'if', 'so', 'no', 'up',
    'it', 'be', 'we', 'us', 'his', 'her', 'its', 'our', 'my', 'me', 'him',
}


def validate_token_integrity(text: str) -> tuple[bool, dict]:
    """Validate that no token truncation artifacts exist in the draft.

    This is a HARD GATE - if violations are found, the draft should be rejected.
    Token truncation indicates a buggy transform mutated text mid-word.

    Patterns detected:
    1. ", he [fragment]," where fragment is not a valid English word
       Examples: "he n,", "he p,", "he power," (power isn't a verb after "he")
    2. Orphan tail lines like "so choose." appearing standalone
    3. Mid-word truncation signatures in prose

    Args:
        text: The draft markdown text.

    Returns:
        Tuple of (is_valid, report) where:
        - is_valid: True if no violations found, False otherwise
        - report: Dict with violation details
    """
    violations = []

    # Split into lines for analysis
    lines = text.split('\n')

    in_key_excerpts = False
    in_core_claims = False

    for line_num, line in enumerate(lines, 1):
        stripped = line.strip()

        # Track section boundaries
        if '### Key Excerpts' in stripped:
            in_key_excerpts = True
            in_core_claims = False
            continue
        elif '### Core Claims' in stripped:
            in_key_excerpts = False
            in_core_claims = True
            continue
        elif stripped.startswith('## '):
            in_key_excerpts = False
            in_core_claims = False
            continue
        elif stripped.startswith('### '):
            in_key_excerpts = False
            in_core_claims = False
            continue

        # Pattern 2: Orphan tail lines (standalone fragments)
        # "so choose." or just "choose." appearing standalone
        # These are ALWAYS invalid, even in Key Excerpts or Core Claims sections
        # (they're structural corruption, not valid quote content)
        orphan_tail_pattern = re.compile(
            r'^(so\s+)?choose\.$',
            re.IGNORECASE
        )
        if orphan_tail_pattern.match(stripped):
            violations.append({
                'type': 'orphan_tail_line',
                'line_num': line_num,
                'matched': stripped,
                'context': stripped,
            })
            continue  # Don't process further patterns for this line

        # Skip protected sections for other checks
        if in_key_excerpts or in_core_claims:
            continue

        # Skip blockquotes and empty lines
        if stripped.startswith('>') or not stripped:
            continue

        # Pattern 1: ", he [fragment]," where fragment is suspicious
        # Matches: ", he n," or ", he power," (truncated attributions)
        he_fragment_pattern = re.compile(
            r',\s*he\s+([a-z]{1,10})\s*[,.]',
            re.IGNORECASE
        )
        for match in he_fragment_pattern.finditer(stripped):
            fragment = match.group(1).lower()
            # Check if this is a valid word
            if fragment not in VALID_HE_WORDS:
                # Additional check: is it a known verb?
                # Valid verbs: notes, says, argues, explains, etc.
                valid_verbs = {
                    'notes', 'says', 'argues', 'explains', 'states', 'claims',
                    'suggests', 'warns', 'adds', 'points', 'observes', 'believes',
                    'maintains', 'asserts', 'contends', 'remarks', 'emphasizes',
                }
                if fragment not in valid_verbs:
                    violations.append({
                        'type': 'truncated_he_fragment',
                        'line_num': line_num,
                        'matched': match.group(0),
                        'fragment': fragment,
                        'context': stripped[:80],
                    })

        # Pattern 3: Mid-word truncation signatures
        # Two consecutive short words glued by punctuation in unexpected places
        # e.g., "technology," followed by single letter fragments
        mid_truncation_pattern = re.compile(
            r',\s+([a-z])\s*,',  # ", n," or ", y," style artifacts
            re.IGNORECASE
        )
        for match in mid_truncation_pattern.finditer(stripped):
            violations.append({
                'type': 'mid_word_truncation',
                'line_num': line_num,
                'matched': match.group(0),
                'fragment': match.group(1),
                'context': stripped[:80],
            })

    is_valid = len(violations) == 0

    if violations:
        logger.warning(
            f"Token integrity check FAILED: {len(violations)} violations found"
        )
        for v in violations[:5]:
            logger.warning(f"  - {v['type']} at line {v['line_num']}: {v['matched']}")

    return is_valid, {
        'valid': is_valid,
        'violations': violations,
        'violation_count': len(violations),
    }


def validate_structural_integrity(text: str) -> tuple[bool, dict]:
    """Validate structural integrity of the draft - HARD GATE.

    This is a P0 invariant check. If violations are found, the draft should be REJECTED,
    not cleaned up. These patterns indicate fundamental corruption that cannot be safely
    patched.

    Patterns detected:
    1. Unclosed quotes in Core Claims bullets
       - Each Core Claim bullet should have exactly 2 double-quote chars (open + close)
       - OR 0 if the claim uses no quotes
    2. Headings (## or ###) inside quote spans
       - A quote that starts but doesn't close before a heading indicates structural corruption
    3. Multi-paragraph content absorbed into quotes
       - Paragraphs (double newline) inside a quote span indicate the LLM didn't close the quote

    Args:
        text: The draft markdown text.

    Returns:
        Tuple of (is_valid, report) where:
        - is_valid: True if no violations found, False otherwise
        - report: Dict with violation details
    """
    violations = []

    # Check 1: Core Claims bullets with unclosed quotes
    in_core_claims = False
    lines = text.split('\n')

    for line_num, line in enumerate(lines, 1):
        stripped = line.strip()

        # Track section boundaries
        if stripped.startswith('### Core Claims'):
            in_core_claims = True
            continue
        elif stripped.startswith('## ') or stripped.startswith('### '):
            in_core_claims = False
            continue

        # Check Core Claims bullets
        if in_core_claims and stripped.startswith('- **'):
            # Count double quote characters (straight and curly)
            quote_chars = sum(1 for c in stripped if c in '"\u201c\u201d')

            # Valid states: 0 quotes (no quote in claim) or 2 quotes (open + close)
            # Invalid: 1 quote (unclosed) or odd number
            if quote_chars % 2 != 0:
                violations.append({
                    'type': 'unclosed_quote_in_core_claim',
                    'line_num': line_num,
                    'quote_count': quote_chars,
                    'context': stripped[:100] + ('...' if len(stripped) > 100 else ''),
                })

            # Check for headings inside the bullet (structural corruption)
            # If the line contains ## or ### after the opening, it absorbed content
            if '## ' in stripped[4:] or '### ' in stripped[4:]:
                violations.append({
                    'type': 'heading_inside_core_claim',
                    'line_num': line_num,
                    'context': stripped[:100] + ('...' if len(stripped) > 100 else ''),
                })

    # Check 2: Quote spans that absorb multiple paragraphs
    # Find opening quotes in narrative that don't close before a paragraph break
    paragraphs = text.split('\n\n')
    for para_num, para in enumerate(paragraphs):
        stripped_para = para.strip()

        # Skip Key Excerpts and Core Claims sections (they have their own rules)
        if stripped_para.startswith('### Key Excerpts') or stripped_para.startswith('### Core Claims'):
            continue
        if stripped_para.startswith('>'):  # Blockquotes are OK
            continue
        if stripped_para.startswith('- **'):  # Core Claims bullets
            continue

        # Check for unclosed quotes in narrative paragraphs
        # Count quote characters
        open_quotes = stripped_para.count('"') + stripped_para.count('\u201c')
        close_quotes = stripped_para.count('"') + stripped_para.count('\u201d')

        # Simple heuristic: if paragraph has more opens than closes, it's suspicious
        # Note: This is imperfect but catches the "quote absorbs chapter" case
        if open_quotes > close_quotes + 1:  # Allow 1 imbalance for edge cases
            # Find line number
            para_start = text.find(stripped_para[:50]) if stripped_para else -1
            approx_line = text[:para_start].count('\n') + 1 if para_start > 0 else 0

            violations.append({
                'type': 'unclosed_quote_in_paragraph',
                'line_num': approx_line,
                'open_quotes': open_quotes,
                'close_quotes': close_quotes,
                'context': stripped_para[:100] + ('...' if len(stripped_para) > 100 else ''),
            })

    # Check 3: Specific pattern - Core Claims quote absorbing chapter
    # Look for patterns where ### appears after an opening " in Core Claims
    core_claims_sections = re.findall(
        r'### Core Claims\n\n(.*?)(?=\n## |\n### |\Z)',
        text,
        re.DOTALL
    )
    for section in core_claims_sections:
        # Find all bullets
        bullets = re.findall(r'- \*\*[^*]+\*\*[^\n]*(?:\n(?!- \*\*|\n)[^\n]*)*', section)
        for bullet in bullets:
            # Check if bullet contains a heading (absorbed content)
            if '\n## ' in bullet or '\n### ' in bullet:
                violations.append({
                    'type': 'core_claim_absorbed_chapter',
                    'context': bullet[:150] + ('...' if len(bullet) > 150 else ''),
                })

    # Check 4: Orphan fragment lines between sections
    # Detects short fragments like "ethos of inquiry." or "so choose." appearing
    # between Core Claims and next Chapter header (or between any sections).
    # These indicate truncation artifacts from a buggy transform.
    #
    # Criteria for orphan fragment:
    # - Not a heading (##, ###)
    # - Not a bullet (- **)
    # - Not a blockquote (>)
    # - Not an attribution (— Name)
    # - <= 8 words
    # - Ends with sentence punctuation (.!?)
    # - Appears between section end and next chapter
    chapter_pattern = re.compile(r'^## Chapter \d+', re.MULTILINE)
    chapters = list(chapter_pattern.finditer(text))

    for i, chapter_match in enumerate(chapters):
        chapter_start = chapter_match.start()
        chapter_end = chapters[i + 1].start() if i + 1 < len(chapters) else len(text)
        chapter_text = text[chapter_start:chapter_end]

        # Find the last section (Key Excerpts or Core Claims) in this chapter
        last_section_match = None
        for section_match in re.finditer(r'^### (Key Excerpts|Core Claims)', chapter_text, re.MULTILINE):
            last_section_match = section_match

        if last_section_match:
            # Get content after the last section's content ends
            # Find where Core Claims content ends (before next chapter or EOF)
            section_content_end = len(chapter_text)  # Default to chapter end

            # Check for orphan lines in the gap between sections
            # Look for lines that aren't part of proper structure
            after_section_pos = last_section_match.end()
            after_section_text = chapter_text[after_section_pos:]

            # Split into lines and check each
            for line in after_section_text.split('\n'):
                stripped = line.strip()
                if not stripped:
                    continue

                # Skip valid content
                if stripped.startswith('## '):  # Next chapter
                    break
                if stripped.startswith('### '):  # Section header
                    continue
                if stripped.startswith('- **'):  # Core Claims bullet
                    continue
                if stripped.startswith('>'):  # Blockquote
                    continue
                if stripped.startswith('— ') or stripped.startswith('- '):  # Attribution
                    continue

                # Check for orphan fragment criteria
                words = stripped.split()
                is_short = len(words) <= 8
                ends_with_punct = stripped and stripped[-1] in '.!?'
                starts_lowercase = stripped and stripped[0].islower()

                # Additional heuristic: no subject (doesn't start with capital or article)
                no_obvious_subject = not re.match(r'^(The|A|An|This|That|It|He|She|They|We|I)\b', stripped)

                if is_short and ends_with_punct and (starts_lowercase or no_obvious_subject):
                    # This is likely an orphan fragment
                    # Find approximate line number
                    line_pos = text.find(stripped)
                    approx_line = text[:line_pos].count('\n') + 1 if line_pos >= 0 else 0

                    violations.append({
                        'type': 'orphan_fragment_between_sections',
                        'line_num': approx_line,
                        'fragment': stripped,
                        'word_count': len(words),
                        'context': f"Found after {last_section_match.group()} in Chapter {i + 1}",
                    })

    # Check 5: Every chapter must have both Key Excerpts and Core Claims sections
    # Missing sections indicate compilation failure or incorrect stripping.
    for i, chapter_match in enumerate(chapters):
        chapter_num = i + 1
        chapter_start = chapter_match.start()
        chapter_end = chapters[i + 1].start() if i + 1 < len(chapters) else len(text)
        chapter_text = text[chapter_start:chapter_end]

        has_key_excerpts = '### Key Excerpts' in chapter_text
        has_core_claims = '### Core Claims' in chapter_text

        if not has_key_excerpts:
            violations.append({
                'type': 'missing_key_excerpts_section',
                'chapter': chapter_num,
                'context': f"Chapter {chapter_num} has no ### Key Excerpts section",
            })

        if not has_core_claims:
            violations.append({
                'type': 'missing_core_claims_section',
                'chapter': chapter_num,
                'context': f"Chapter {chapter_num} has no ### Core Claims section",
            })

    # Check 6: LLM-generated placeholder text in Core Claims (ownership violation)
    # Core Claims must be COMPILED, never LLM-authored. If the LLM generates its own
    # "no claims available" text, it indicates the compiler failed and the LLM is
    # filling in. This is a P0 violation - the section should have been populated
    # by the compiler, or left empty (which triggers our canonical placeholder).
    #
    # Valid Core Claims content:
    # - Bullet points: - **Claim**: "Supporting quote."
    # - Our canonical placeholder: *No claims available.*
    #
    # Invalid (LLM-generated):
    # - *No fully grounded claims available for this chapter.*
    # - Unable to extract claims from this section.
    # - No specific claims were identified.
    for i, chapter_match in enumerate(chapters):
        chapter_num = i + 1
        chapter_start = chapter_match.start()
        chapter_end = chapters[i + 1].start() if i + 1 < len(chapters) else len(text)
        chapter_text = text[chapter_start:chapter_end]

        # Extract Core Claims section content
        core_claims_match = re.search(
            r'### Core Claims\s*\n(.*?)(?=### |\Z)',
            chapter_text,
            re.DOTALL
        )
        if core_claims_match:
            core_claims_content = core_claims_match.group(1).strip()

            # Skip if it's our canonical placeholder (exactly)
            if core_claims_content == NO_CLAIMS_PLACEHOLDER:
                continue

            # Skip if it's valid bullet content (starts with - **)
            if core_claims_content.startswith('- **'):
                continue

            # Check for LLM-generated placeholder patterns
            for pattern in LLM_PLACEHOLDER_REGEXES:
                if pattern.search(core_claims_content):
                    violations.append({
                        'type': 'llm_generated_core_claims_placeholder',
                        'chapter': chapter_num,
                        'context': core_claims_content[:100] + ('...' if len(core_claims_content) > 100 else ''),
                        'detail': 'Core Claims must be compiled, not LLM-authored. '
                                  'This placeholder text was generated by the LLM instead of '
                                  'actual claims or the canonical placeholder.',
                    })
                    break  # One violation per chapter is enough

    is_valid = len(violations) == 0

    if violations:
        logger.error(
            f"Structural integrity check FAILED: {len(violations)} violations found"
        )
        for v in violations[:5]:
            logger.error(f"  - {v['type']}: {v.get('context', '')[:60]}...")

    return is_valid, {
        'valid': is_valid,
        'violations': violations,
        'violation_count': len(violations),
    }


def cleanup_orphan_fragments_between_sections(text: str) -> tuple[str, dict]:
    """Remove orphan content fragments appearing between sections and chapters.

    In the Ideas Edition structure, nothing should appear between:
    - Core Claims section content and the next Chapter header

    Orphan fragments like "ethos of inquiry." (Draft 19) can appear when:
    - A transform drops part of a sentence, leaving a tail
    - LLM generates malformed content after a section

    This cleanup removes non-structural content in these gaps.

    Args:
        text: The draft markdown text.

    Returns:
        Tuple of (cleaned_text, report_dict).
    """
    cleaned_fragments = []

    # Split into lines for processing
    lines = text.split('\n')
    result_lines = []

    in_core_claims = False
    last_was_bullet_or_attribution = False
    pending_gap_lines = []

    for line in lines:
        stripped = line.strip()

        # Track section boundaries
        if stripped.startswith('## Chapter'):
            # Flush any pending gap lines - these are orphans, discard them
            if pending_gap_lines:
                for gap_line in pending_gap_lines:
                    if gap_line.strip():
                        cleaned_fragments.append(gap_line.strip())
                pending_gap_lines = []
            in_core_claims = False
            last_was_bullet_or_attribution = False
            result_lines.append(line)
            continue

        if stripped.startswith('### Core Claims'):
            # Flush any pending gap lines before new section
            if pending_gap_lines:
                for gap_line in pending_gap_lines:
                    if gap_line.strip():
                        cleaned_fragments.append(gap_line.strip())
                pending_gap_lines = []
            in_core_claims = True
            last_was_bullet_or_attribution = False
            result_lines.append(line)
            continue

        if stripped.startswith('### '):
            # Any other ### section ends Core Claims
            if pending_gap_lines:
                for gap_line in pending_gap_lines:
                    if gap_line.strip():
                        cleaned_fragments.append(gap_line.strip())
                pending_gap_lines = []
            in_core_claims = False
            last_was_bullet_or_attribution = False
            result_lines.append(line)
            continue

        if in_core_claims:
            # Inside Core Claims section
            if stripped.startswith('- **'):
                # Valid bullet
                # First, flush any pending gaps - they were between bullets, keep them
                result_lines.extend(pending_gap_lines)
                pending_gap_lines = []
                result_lines.append(line)
                last_was_bullet_or_attribution = True
                continue

            if stripped.startswith('*'):
                # Placeholder text like "*No claims available*"
                result_lines.extend(pending_gap_lines)
                pending_gap_lines = []
                result_lines.append(line)
                last_was_bullet_or_attribution = True
                continue

            if not stripped:
                # Empty line - could be before or after content
                if last_was_bullet_or_attribution:
                    # After a bullet/attribution - accumulate as potential gap
                    pending_gap_lines.append(line)
                else:
                    result_lines.append(line)
                continue

            # Non-empty, non-structural line in Core Claims
            # This could be orphan content
            if last_was_bullet_or_attribution:
                # Orphan after bullet content - accumulate
                pending_gap_lines.append(line)
            else:
                # Before any bullets - keep it (might be legitimate)
                result_lines.append(line)
        else:
            # Not in Core Claims - keep everything
            result_lines.append(line)

    # Flush remaining pending gap lines (orphans at end)
    # These are discarded since we're at the end of text
    if pending_gap_lines:
        for gap_line in pending_gap_lines:
            if gap_line.strip():
                cleaned_fragments.append(gap_line.strip())

    result = '\n'.join(result_lines)

    # Clean up any triple+ blank lines
    result = re.sub(r'\n{3,}', '\n\n', result)

    if cleaned_fragments:
        logger.info(
            f"Removed {len(cleaned_fragments)} orphan fragment(s) between sections: "
            f"{cleaned_fragments[:3]}..."
        )

    return result, {
        "fragments_removed": len(cleaned_fragments),
        "removed_fragments": cleaned_fragments[:10],
    }


# Debug patterns for snapshot detection
_DEBUG_CORRUPTION_PATTERNS = [
    (re.compile(r',\s*he\s+n\s*,', re.IGNORECASE), 'he_n_truncation'),
    (re.compile(r',\s*he\s+power\s*,', re.IGNORECASE), 'he_power_truncation'),
    (re.compile(r'^so\s+choose\.$', re.IGNORECASE | re.MULTILINE), 'so_choose_orphan'),
    (re.compile(r',\s+[a-z]\s*,'), 'single_letter_truncation'),
    # Draft 19 orphan fragment pattern
    (re.compile(r'\nethos of inquiry\.\n', re.IGNORECASE), 'ethos_of_inquiry_orphan'),
    # Generic short orphan between sections (lowercase start, short, ends with .)
    (re.compile(r'\n\n([a-z][^.!?\n]{5,50}[.!?])\n\n## Chapter', re.MULTILINE), 'generic_orphan_fragment'),
]


def _check_for_corruption(text: str, step_name: str, job_id: str = "") -> bool:
    """Debug helper: check if known corruption patterns exist in text.

    Call this after each transform to identify which one introduces corruption.

    Args:
        text: The markdown text to check.
        step_name: Name of the transform that just completed.
        job_id: Optional job ID for logging.

    Returns:
        True if corruption detected, False otherwise.
    """
    found = []
    for pattern, name in _DEBUG_CORRUPTION_PATTERNS:
        matches = pattern.findall(text)
        if matches:
            found.append((name, matches[:3]))

    if found:
        logger.error(
            f"CORRUPTION DETECTED after '{step_name}' (job {job_id}):"
        )
        for name, matches in found:
            logger.error(f"  - {name}: {matches}")
        return True
    return False


def remove_discourse_markers(text: str) -> tuple[str, dict]:
    """Remove transcript discourse markers from prose.

    Discourse markers like "Okay,", "In fact,", "Yes." are verbal fillers
    that shouldn't appear in polished prose. This function removes them
    from the start of sentences.

    Args:
        text: The draft markdown text.

    Returns:
        Tuple of (cleaned_text, report_dict).
    """
    # Discourse markers that appear at start of sentences
    # These are verbal fillers from transcript that leaked into prose
    markers = [
        (r'\bOkay,\s*', 'Okay,'),
        (r'\bOK,\s*', 'OK,'),
        (r'\bYeah,\s*', 'Yeah,'),
        (r'\bYes\.\s+', 'Yes.'),
        (r'\bYes,\s*', 'Yes,'),
        (r'\bWell,\s*', 'Well,'),
        (r'\bSo,\s*', 'So,'),
        (r'\bNow,\s*', 'Now,'),
        (r'\bIn fact,\s*', 'In fact,'),
        (r'\bActually,\s*', 'Actually,'),
        (r'\bI mean,\s*', 'I mean,'),
        (r'\bYou know,\s*', 'You know,'),
        (r'\bLook,\s*', 'Look,'),
        (r'\bRight,\s*', 'Right,'),
    ]

    removals = []

    # Split into paragraphs to track sections
    paragraphs = text.split('\n\n')
    result_paragraphs = []

    in_key_excerpts = False
    in_core_claims = False

    for para in paragraphs:
        stripped = para.strip()

        # Track section boundaries
        if '### Key Excerpts' in stripped:
            in_key_excerpts = True
            in_core_claims = False
            result_paragraphs.append(para)
            continue
        elif '### Core Claims' in stripped:
            in_key_excerpts = False
            in_core_claims = True
            result_paragraphs.append(para)
            continue
        elif stripped.startswith('## '):
            in_key_excerpts = False
            in_core_claims = False
            result_paragraphs.append(para)
            continue

        # Don't modify Key Excerpts (quotes should be verbatim)
        if in_key_excerpts:
            result_paragraphs.append(para)
            continue

        # Don't modify Core Claims quotes
        if in_core_claims:
            result_paragraphs.append(para)
            continue

        # Skip blockquotes
        if stripped.startswith('>'):
            result_paragraphs.append(para)
            continue

        # Remove discourse markers from narrative prose
        modified = para
        for pattern, marker_name in markers:
            matches = list(re.finditer(pattern, modified, re.IGNORECASE))
            for match in reversed(matches):  # Reverse to preserve positions
                # Only remove if at start of sentence (after period, or start of paragraph)
                before = modified[:match.start()]
                if not before or before.rstrip().endswith(('.', '!', '?', '\n')):
                    # Capitalize the next word after removal
                    after = modified[match.end():]
                    if after and after[0].islower():
                        after = after[0].upper() + after[1:]
                    modified = before + after
                    removals.append({
                        "marker": marker_name,
                        "context": modified[max(0, match.start()-10):match.start()+30],
                    })

        result_paragraphs.append(modified)

    result = '\n\n'.join(result_paragraphs)

    if removals:
        logger.info(f"Removed {len(removals)} discourse markers from prose")

    return result, {
        "markers_removed": len(removals),
        "removal_details": removals[:10],  # Limit details
    }


def ensure_chapter_narrative_minimum(
    text: str,
    min_prose_paragraphs: int = 1,
) -> tuple[str, dict]:
    """Ensure each chapter has minimum narrative prose.

    If a chapter has zero prose paragraphs (only Key Excerpts + Core Claims),
    insert a minimal safe narrative. This prevents content collapse from
    overly aggressive gates while maintaining structural validity.

    The fallback narrative is purely rhetorical and never quotes or paraphrases
    transcript content, avoiding any grounding violations.

    Args:
        text: The draft markdown text.
        min_prose_paragraphs: Minimum required prose paragraphs per chapter.

    Returns:
        Tuple of (updated_text, report_dict).
    """
    # Find all chapter boundaries
    chapter_pattern = re.compile(r'^## Chapter (\d+)[:\s]*(.*?)$', re.MULTILINE)
    chapters = list(chapter_pattern.finditer(text))

    if not chapters:
        return text, {"chapters_fixed": 0, "fixed_details": []}

    fixed_details = []
    result_parts = []
    last_end = 0

    for i, chapter_match in enumerate(chapters):
        chapter_num = int(chapter_match.group(1))
        chapter_title = chapter_match.group(2).strip()
        chapter_start = chapter_match.start()
        chapter_end = chapters[i + 1].start() if i + 1 < len(chapters) else len(text)
        chapter_text = text[chapter_start:chapter_end]

        # Add text before this chapter
        result_parts.append(text[last_end:chapter_start])

        # Find Key Excerpts position (narrative should be before this)
        key_excerpts_match = re.search(r'^### Key Excerpts', chapter_text, re.MULTILINE)

        if key_excerpts_match:
            # Get the text between chapter header and Key Excerpts
            header_end = chapter_match.end() - chapter_start
            narrative_section = chapter_text[header_end:key_excerpts_match.start()]

            # Count prose paragraphs (non-empty, non-header paragraphs)
            paragraphs = [p.strip() for p in narrative_section.split('\n\n') if p.strip()]
            prose_paragraphs = [
                p for p in paragraphs
                if not p.startswith('#') and not p.startswith('>')
            ]

            if len(prose_paragraphs) < min_prose_paragraphs:
                # Insert fallback narrative
                fallback_narrative = _generate_fallback_narrative(chapter_num, chapter_title)

                # Reconstruct chapter: header + fallback + rest
                new_chapter = (
                    chapter_text[:header_end] +
                    '\n\n' + fallback_narrative + '\n' +
                    chapter_text[key_excerpts_match.start():]
                )
                result_parts.append(new_chapter)

                fixed_details.append({
                    "chapter": chapter_num,
                    "title": chapter_title,
                    "original_prose_count": len(prose_paragraphs),
                    "action": "inserted_fallback",
                })
                logger.info(
                    f"Chapter {chapter_num} had {len(prose_paragraphs)} prose paragraphs, "
                    f"inserted fallback narrative"
                )
            else:
                # Chapter has enough prose, keep as-is
                result_parts.append(chapter_text)
        else:
            # No Key Excerpts section found, keep chapter as-is
            result_parts.append(chapter_text)

        last_end = chapter_end

    # Add any remaining text after the last chapter
    result_parts.append(text[last_end:])

    return ''.join(result_parts), {
        "chapters_fixed": len(fixed_details),
        "fixed_details": fixed_details,
    }


def repair_orphan_chapter_openers(
    text: str,
    original_prose_by_chapter: dict[int, str] | None = None,
    whitelist_quotes: list[str] | None = None,
) -> tuple[str, dict]:
    """Repair chapters whose first narrative sentence has no antecedent.

    Post sentence-drop, chapters may start with pronouns/connectives like
    "It prompts us...", "Understanding these laws...", "However, the..." that
    lack antecedent because the anchoring sentence was dropped.

    Bad opener patterns:
    - Pronouns: It|This|That|These|Those (without clear antecedent)
    - "Understanding these/this..."
    - Discourse connectives: However|Therefore|Moreover|But|And

    Repair strategy (deterministic):
    1. Try salvage: if original_prose_by_chapter provided, find the closest
       earlier sentence that:
       - Does NOT match verbatim-leak detector
       - Does NOT match attribution-wrapper detector
       - Is >= 8 words
       Insert it at the beginning.

    2. If no salvage found: prepend the deterministic chapter fallback
       (don't replace remaining prose, just prepend).

    Args:
        text: The draft markdown text (post sentence-drop).
        original_prose_by_chapter: Optional dict mapping chapter_num to original
            pre-drop narrative prose for that chapter.
        whitelist_quotes: Optional whitelist for leak detection during salvage.

    Returns:
        Tuple of (repaired_text, report_dict).
    """
    # Bad opener patterns
    # At chapter start, these indicate missing antecedent/context
    BAD_OPENER_PATTERNS = [
        # Subject pronouns + any verb (Draft 22 fix: don't enumerate verb forms)
        # At chapter start, He/She/They/We/I always lack antecedent
        r'^He\s+[a-z]+',      # "He warned...", "He argues...", etc.
        r'^She\s+[a-z]+',     # "She noted...", "She believes...", etc.
        r'^They\s+[a-z]+',    # "They suggested...", etc.
        r'^We\s+[a-z]+',      # "We see...", etc. (rare but possible)
        r'^I\s+[a-z]+',       # "I think..." (rare in essay)
        # Object/demonstrative pronouns without antecedent
        r'^It\s+[a-z]+',      # "It moved us...", "It shows...", etc.
        r'^This\s+[a-z]+',    # "This challenges...", etc.
        r'^That\s+[a-z]+',    # "That shows...", etc.
        r'^These\s+[a-z]+',   # "These ideas...", etc.
        r'^Those\s+[a-z]+',   # "Those who...", etc.
        # "Understanding these/this..." - dangling participial
        r'^Understanding\s+(these?|this|the)\b',
        # Discourse connectives at start - indicate continuation without prior context
        r'^However[,\s]',
        r'^Therefore[,\s]',
        r'^Moreover[,\s]',
        r'^Furthermore[,\s]',
        r'^But\s+',
        r'^And\s+the\b',
    ]

    # Attribution wrapper patterns (for salvage filtering)
    ATTRIBUTION_PATTERNS = [
        r'\b(Deutsch|He|She|They)\s+(says?|notes?|argues?|observes?|warns?|claims?|states?|suggests?)\s*[,:]',
        r',\s*(recalling|remembering|noting|observing)\s*,',
    ]

    def is_bad_opener(sentence: str) -> bool:
        """Check if sentence is a bad opener."""
        stripped = sentence.strip()
        for pattern in BAD_OPENER_PATTERNS:
            if re.match(pattern, stripped, re.IGNORECASE):
                return True
        return False

    def has_attribution_wrapper(sentence: str) -> bool:
        """Check if sentence has attribution wrapper."""
        for pattern in ATTRIBUTION_PATTERNS:
            if re.search(pattern, sentence, re.IGNORECASE):
                return True
        return False

    def has_verbatim_leak(sentence: str, quotes: list[str], min_len: int = 20) -> bool:
        """Check if sentence contains verbatim quote text."""
        if not quotes:
            return False
        normalized_sentence = ' '.join(sentence.lower().split())
        for quote in quotes:
            if len(quote) >= min_len:
                normalized_quote = ' '.join(quote.lower().split())
                if normalized_quote in normalized_sentence:
                    return True
        return False

    def find_salvage_sentence(original_prose: str, quotes: list[str] | None) -> str | None:
        """Find a safe sentence from original prose to use as anchor.

        Returns the first valid sentence (>= 8 words, no leak, no attribution).
        """
        if not original_prose:
            return None

        # Split into sentences
        sentences = re.split(r'(?<=[.!?])\s+', original_prose.strip())

        for sentence in sentences:
            stripped = sentence.strip()
            if not stripped:
                continue

            words = stripped.split()
            if len(words) < 8:
                continue

            # Check for attribution wrappers
            if has_attribution_wrapper(stripped):
                continue

            # Check for verbatim leaks
            if has_verbatim_leak(stripped, quotes or []):
                continue

            # Check if it's itself a bad opener (useless for salvage)
            if is_bad_opener(stripped):
                continue

            # Valid salvage candidate
            return stripped

        return None

    # Parse chapters
    chapter_pattern = re.compile(r'^## Chapter (\d+)[:\s]*(.*?)$', re.MULTILINE)
    chapters = list(chapter_pattern.finditer(text))

    if not chapters:
        return text, {"chapters_repaired": 0, "repairs": []}

    repairs = []
    result_parts = []
    last_end = 0

    for i, chapter_match in enumerate(chapters):
        chapter_num = int(chapter_match.group(1))
        chapter_title = chapter_match.group(2).strip()
        chapter_start = chapter_match.start()
        chapter_end = chapters[i + 1].start() if i + 1 < len(chapters) else len(text)
        chapter_text = text[chapter_start:chapter_end]

        # Add content before this chapter
        result_parts.append(text[last_end:chapter_start])

        # Find narrative prose section (before Key Excerpts)
        key_excerpts_pos = chapter_text.find('### Key Excerpts')
        if key_excerpts_pos == -1:
            key_excerpts_pos = len(chapter_text)

        # Get just the header and narrative portion
        header_end = chapter_text.find('\n') + 1
        narrative_portion = chapter_text[header_end:key_excerpts_pos].strip()

        # Check if first narrative sentence is a bad opener
        if narrative_portion:
            first_sentence_match = re.match(r'^([^.!?]+[.!?])', narrative_portion)
            first_sentence = first_sentence_match.group(1) if first_sentence_match else narrative_portion.split('\n')[0]

            if is_bad_opener(first_sentence):
                # Try to salvage from original prose
                original_prose = original_prose_by_chapter.get(chapter_num) if original_prose_by_chapter else None
                salvage = find_salvage_sentence(original_prose, whitelist_quotes)

                if salvage:
                    # Prepend salvage sentence
                    repaired_narrative = salvage + ' ' + narrative_portion
                    repairs.append({
                        "chapter": chapter_num,
                        "action": "salvage_prepended",
                        "salvage_sentence": salvage[:50] + "...",
                        "bad_opener": first_sentence[:50] + "...",
                    })
                else:
                    # Prepend fallback
                    fallback = _generate_fallback_narrative(chapter_num, chapter_title)
                    repaired_narrative = fallback + '\n\n' + narrative_portion
                    repairs.append({
                        "chapter": chapter_num,
                        "action": "fallback_prepended",
                        "bad_opener": first_sentence[:50] + "...",
                    })

                # Rebuild chapter with repaired narrative
                chapter_text = (
                    chapter_text[:header_end] +
                    '\n' + repaired_narrative + '\n\n' +
                    chapter_text[key_excerpts_pos:]
                )

        result_parts.append(chapter_text)
        last_end = chapter_end

    # Add any remaining content
    if last_end < len(text):
        result_parts.append(text[last_end:])

    result = ''.join(result_parts)

    # Clean up extra blank lines
    result = re.sub(r'\n{3,}', '\n\n', result)

    if repairs:
        logger.info(f"Anchor-sentence policy: repaired {len(repairs)} chapter opener(s)")
        for r in repairs:
            logger.info(f"  - Chapter {r['chapter']}: {r['action']}")

    return result, {
        "chapters_repaired": len(repairs),
        "repairs": repairs,
    }


def repair_first_paragraph_pronouns(text: str) -> tuple[str, dict]:
    """Repair pronoun-start sentences within the first prose paragraph of each chapter.

    Within the first prose paragraph of a chapter, if a sentence starts with
    It/This/These/They, these pronouns lack antecedent and should be replaced
    with the chapter title noun (e.g., "The Enlightenment").

    This extends the anchor policy beyond just the chapter opener (first sentence)
    to cover all sentences in the first paragraph.

    Replacement strategy:
    1. Extract subject noun from chapter title (e.g., "The Impact of the Enlightenment" → "The Enlightenment")
    2. For each sentence in first paragraph starting with It/This/These/They:
       - Replace pronoun with chapter title noun
       - If no clear noun, drop the sentence

    Args:
        text: The draft markdown text.

    Returns:
        Tuple of (repaired_text, report_dict).
    """
    repairs = []
    sentences_dropped = 0

    # Pronouns that should be replaced with chapter title noun
    PRONOUN_STARTERS = ['It', 'This', 'These', 'They', 'That', 'Those']

    def extract_title_noun(chapter_title: str) -> str | None:
        """Extract the main noun phrase from chapter title for pronoun replacement.

        Examples:
        - "The Impact of the Enlightenment" → "The Enlightenment"
        - "Human Potential and the Universe" → "Human potential"
        - "The Role of Knowledge in Human Progress" → "Knowledge"
        - "The Boundaries of Scientific Inquiry" → "Scientific inquiry"
        """
        title = chapter_title.strip()
        if not title:
            return None

        # Pattern: "The Impact/Role/Boundaries of X" → extract X (including optional "the")
        # Group captures everything after "of " up to optional " in ..."
        match = re.match(r'^The\s+(?:Impact|Role|Boundaries|Nature|Power|Limits)\s+of\s+(.+?)(?:\s+in\s+.+)?$', title, re.IGNORECASE)
        if match:
            noun = match.group(1).strip()
            # Handle "the X" → "The X" (capitalize article)
            if noun.lower().startswith('the '):
                rest = noun[4:]  # After "the "
                return 'The ' + rest
            # Single word or phrase without article
            return noun[0].upper() + noun[1:] if noun else None

        # Pattern: "X and Y" → use X (lowercased except first letter)
        if ' and ' in title.lower():
            noun = title.split(' and ')[0].strip()
            return noun[0].upper() + noun[1:] if noun else None

        # Default: use the whole title
        return title[0].upper() + title[1:] if title else None

    def replace_pronoun_start(sentence: str, replacement_noun: str) -> str:
        """Replace pronoun at start of sentence with the replacement noun."""
        for pronoun in PRONOUN_STARTERS:
            if sentence.startswith(pronoun + ' '):
                # Replace pronoun, preserving the rest
                return replacement_noun + sentence[len(pronoun):]
            # Handle "It's" → "X is"
            if sentence.startswith(pronoun + "'s ") or sentence.startswith(pronoun + "'s "):
                return replacement_noun + ' is' + sentence[len(pronoun) + 2:]
        return sentence

    # Parse chapters
    chapter_pattern = re.compile(r'^## Chapter (\d+)[:\s]*(.*?)$', re.MULTILINE)
    chapters = list(chapter_pattern.finditer(text))

    if not chapters:
        return text, {"sentences_repaired": 0, "sentences_dropped": 0, "repairs": []}

    result_parts = []
    last_end = 0

    for i, chapter_match in enumerate(chapters):
        chapter_num = int(chapter_match.group(1))
        chapter_title = chapter_match.group(2).strip()
        chapter_start = chapter_match.start()
        chapter_end = chapters[i + 1].start() if i + 1 < len(chapters) else len(text)
        chapter_text = text[chapter_start:chapter_end]

        # Add content before this chapter
        result_parts.append(text[last_end:chapter_start])

        # Find narrative prose section (before Key Excerpts)
        key_excerpts_pos = chapter_text.find('### Key Excerpts')
        if key_excerpts_pos == -1:
            key_excerpts_pos = len(chapter_text)

        # Get just the header and narrative portion
        header_end = chapter_text.find('\n') + 1
        narrative_portion = chapter_text[header_end:key_excerpts_pos].strip()

        if narrative_portion:
            # Split narrative into paragraphs
            paragraphs = narrative_portion.split('\n\n')

            if paragraphs:
                # Only process the FIRST paragraph
                first_para = paragraphs[0].strip()

                # Split first paragraph into sentences
                sentences = re.split(r'(?<=[.!?])\s+', first_para)
                repaired_sentences = []
                title_noun = extract_title_noun(chapter_title)

                for sentence in sentences:
                    stripped = sentence.strip()
                    if not stripped:
                        continue

                    # Check if sentence starts with a pronoun
                    starts_with_pronoun = any(
                        stripped.startswith(p + ' ') or stripped.startswith(p + "'")
                        for p in PRONOUN_STARTERS
                    )

                    if starts_with_pronoun:
                        if title_noun:
                            # Replace pronoun with title noun
                            repaired = replace_pronoun_start(stripped, title_noun)
                            repaired_sentences.append(repaired)
                            repairs.append({
                                "chapter": chapter_num,
                                "action": "pronoun_replaced",
                                "original": stripped[:50] + ("..." if len(stripped) > 50 else ""),
                                "replacement_noun": title_noun,
                            })
                        else:
                            # No title noun available, drop the sentence
                            sentences_dropped += 1
                            repairs.append({
                                "chapter": chapter_num,
                                "action": "pronoun_sentence_dropped",
                                "original": stripped[:50] + ("..." if len(stripped) > 50 else ""),
                            })
                    else:
                        repaired_sentences.append(stripped)

                # Rebuild first paragraph
                if repaired_sentences:
                    paragraphs[0] = ' '.join(repaired_sentences)
                else:
                    # All sentences dropped - remove first paragraph
                    paragraphs = paragraphs[1:] if len(paragraphs) > 1 else []

                # Rebuild narrative
                narrative_portion = '\n\n'.join(paragraphs)

        # Rebuild chapter
        chapter_text = (
            chapter_text[:header_end] +
            '\n' + narrative_portion + '\n\n' +
            chapter_text[key_excerpts_pos:]
        )

        result_parts.append(chapter_text)
        last_end = chapter_end

    # Add any remaining content
    if last_end < len(text):
        result_parts.append(text[last_end:])

    result = ''.join(result_parts)

    # Clean up extra blank lines
    result = re.sub(r'\n{3,}', '\n\n', result)

    if repairs:
        logger.info(f"First-paragraph pronoun repair: {len(repairs)} repairs, {sentences_dropped} dropped")

    return result, {
        "sentences_repaired": len([r for r in repairs if r["action"] == "pronoun_replaced"]),
        "sentences_dropped": sentences_dropped,
        "repairs": repairs,
    }


def _generate_fallback_narrative(chapter_num: int, chapter_title: str) -> str:
    """Generate a minimal safe narrative for a chapter with no prose.

    The fallback is purely rhetorical and structural - it never quotes or
    paraphrases any content, only points to the excerpts below.

    Uses 3 distinct variants selected by stable hash to ensure:
    - Different chapters get different fallback text
    - Same chapter always gets same variant (deterministic)
    - No repetitive boilerplate across chapters

    Args:
        chapter_num: The chapter number.
        chapter_title: The chapter title (may be empty).

    Returns:
        A safe fallback narrative paragraph (2-3 sentences).
    """
    from hashlib import sha1

    # Clean up title for use in narrative
    title_text = chapter_title.strip() if chapter_title else ""
    theme_phrase = title_text.lower() if title_text else "the central ideas"

    # Create stable hash from chapter_num + title for variant selection
    hash_input = f"ch{chapter_num}:{chapter_title or 'untitled'}"
    variant = int(sha1(hash_input.encode()).hexdigest()[0], 16) % 3

    # Three distinct variants with different structure and vocabulary
    # All are purely structural - they never quote or paraphrase content
    if variant == 0:
        # Variant A: Theme + evidence structure
        return (
            f"This chapter develops the theme of {theme_phrase} by linking "
            f"concrete moments from the conversation to a set of grounded claims. "
            f"The excerpts preserve the original voice; the claims synthesize "
            f"the argument in compact form."
        )
    elif variant == 1:
        # Variant B: Tension + resolution framing
        return (
            f"The core tension in this chapter concerns {theme_phrase}. "
            f"The excerpts below provide the anchoring evidence, while the claims "
            f"distill how that tension resolves into a coherent position."
        )
    else:
        # Variant C: Threading + navigation
        return (
            f"This chapter threads from specific evidence to broader implications "
            f"regarding {theme_phrase}. "
            f"Read the excerpts first for context, then use the claims to see "
            f"how the argument assembles without direct quotation."
        )


def _extract_verb(full_match: str, speaker: str) -> str:
    """Extract the attribution verb from a full match.

    Handles both prefix patterns ("Deutsch argues, X") and suffix patterns
    ("X, Deutsch argues.") by finding the speaker position in the string.

    Args:
        full_match: The full matched string
        speaker: The speaker name (e.g., "Deutsch")

    Returns:
        The verb (e.g., "argues")
    """
    # Find speaker position in the string (case-insensitive)
    speaker_pos = full_match.lower().find(speaker.lower())
    if speaker_pos == -1:
        return 'says'  # Default fallback

    # Get text after the speaker
    after_speaker = full_match[speaker_pos + len(speaker):].strip()

    # Extract verb (first word)
    verb_match = re.match(r'(\w+)', after_speaker)
    if verb_match:
        return verb_match.group(1)
    return 'says'  # Default fallback


def repair_grammar_fragments(text: str) -> str:
    """Repair grammar fragments left after sentence deletions.

    Detects and removes:
    - Orphan sentence fragments (e.g., "Against the idea that...")
    - Sentences starting with lowercase (unless after colon)
    - Very short sentences that look incomplete
    - Pronoun orphans: paragraphs starting with It/This/That/These/They + verb
      where the antecedent was likely deleted

    Args:
        text: Text that may have fragments after deletions.

    Returns:
        Cleaned text with fragments removed.
    """
    # Split into paragraphs (double newline) for pronoun orphan detection
    paragraphs = text.split('\n\n')
    repaired_paragraphs = []

    for i, para in enumerate(paragraphs):
        stripped = para.strip()
        if not stripped:
            continue

        # Skip headings
        if stripped.startswith('#'):
            repaired_paragraphs.append(para)
            continue

        # Check for pronoun orphans at paragraph start
        # Pattern: starts with pronoun + verb, suggesting missing antecedent
        pronoun_orphan_patterns = [
            # "It grows and changes..." - orphaned "it" without clear referent
            r'^It\s+(is|was|grows|changes|reflects|represents|suggests|shows|demonstrates|illustrates|captures|marks|reveals|becomes|remains|continues|appears|seems)\b',
            # "This challenges..." - orphaned "this" without clear referent
            r'^This\s+(is|was|challenges|shows|suggests|indicates|demonstrates|reflects|captures|marks|reveals|means|implies|highlights|underscores|proves|confirms)\b',
            # "That is..." - orphaned "that"
            r'^That\s+(is|was|shows|means|suggests)\b',
            # "These ideas..." - may be orphaned if previous context deleted
            r'^These\s+(are|were|ideas?|concepts?|views?|notions?|principles?)\b',
            # "They believed..." - orphaned subject
            r'^They\s+(are|were|have|had|believed|thought|argued|suggested)\b',
            # "He/She envisions..." - orphaned third-person pronoun without named referent
            r'^He\s+(is|was|has|had|argues?|says?|notes?|observes?|warns?|asserts?|claims?|explains?|points?\s+out|suggests?|states?|contends?|believes?|maintains?|emphasizes?|stresses?|highlights?|insists?|remarks?|cautions?|envisions?|tells?|adds?|writes?|acknowledges?|reflects?|sees?|views?|challenges?|thinks?|considers?|describes?|calls?|puts?)\b',
            r'^She\s+(is|was|has|had|argues?|says?|notes?|observes?|warns?|asserts?|claims?|explains?|points?\s+out|suggests?|states?|contends?|believes?|maintains?|emphasizes?|stresses?|highlights?|insists?|remarks?|cautions?|envisions?|tells?|adds?|writes?|acknowledges?|reflects?|sees?|views?|challenges?|thinks?|considers?|describes?|calls?|puts?)\b',
        ]

        is_pronoun_orphan = False
        for pattern in pronoun_orphan_patterns:
            if re.match(pattern, stripped, re.IGNORECASE):
                # Check if previous paragraph provides a clear antecedent
                # Heuristic: if this is the first paragraph or prev ends without a noun phrase, it's orphaned
                if i == 0:
                    is_pronoun_orphan = True
                    break
                # Check if previous paragraph exists and ends with potential antecedent
                prev_para = paragraphs[i - 1].strip() if i > 0 else ""
                if not prev_para or prev_para.startswith('#'):
                    # No previous content or just a heading - definitely orphaned
                    is_pronoun_orphan = True
                    break
                # Check if previous paragraph ends with a clear noun that could be antecedent
                # This is a heuristic - if prev is very short, may be orphaned
                # Filter out empty strings from split (happens when sentence ends with punctuation)
                prev_sentences = [s for s in re.split(r'[.!?]\s*', prev_para) if s.strip()]
                last_sentence = prev_sentences[-1] if prev_sentences else ""
                # If the previous paragraph is very short overall, likely orphaned
                # (A long paragraph likely establishes context)
                if len(prev_para.strip()) < 50:
                    is_pronoun_orphan = True
                    break

        if is_pronoun_orphan:
            logger.info(f"Removing pronoun orphan: {stripped[:60]}...")
            continue

        # Also check for other fragment patterns within the paragraph
        lines = para.split('\n')
        repaired_lines = []

        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                repaired_lines.append(line)
                continue

            # Check for orphan fragments
            is_fragment = False

            # Lowercase start is always a fragment (proper sentences start with capitals)
            if re.match(r'^[a-z]', line_stripped) and not line_stripped.startswith('#'):
                is_fragment = True

            # Check other fragment patterns (need additional criteria)
            if not is_fragment:
                fragment_patterns = [
                    r'^Against\s+',  # Orphaned "Against..."
                    r'^Which\s+',  # Orphaned "Which..."
                    r'^And\s+the\s+',  # Orphaned "And the..."
                ]
                for pattern in fragment_patterns:
                    if re.match(pattern, line_stripped):
                        # Check if it's a complete sentence (has ending punctuation and reasonable length)
                        if len(line_stripped) < 30 or not line_stripped.endswith(('.', '!', '?')):
                            is_fragment = True
                            break

            if is_fragment:
                logger.debug(f"Removing fragment: {line_stripped[:50]}...")
                continue

            repaired_lines.append(line)

        repaired_para = '\n'.join(repaired_lines)

        # Remove mid-sentence orphan "He/She + verb" patterns
        # Pattern: sentence ending + "He/She" + attribution verb + content + sentence ending
        # Example: "...our future. He challenges the common belief..." → remove "He challenges..." sentence
        # Also handles: "He states, X" and "He states that X" and "He states: X"
        mid_sentence_orphan_pattern = re.compile(
            r'([.!?])\s+'  # Sentence ending + space
            r'(He|She)\s+'  # Orphan pronoun
            r'(?:is|was|has|had|argues?|says?|notes?|observes?|warns?|asserts?|claims?|explains?|'
            r'points?\s+out|suggests?|states?|contends?|believes?|maintains?|emphasizes?|stresses?|'
            r'highlights?|insists?|remarks?|cautions?|envisions?|tells?|adds?|writes?|acknowledges?|'
            r'reflects?|challenges?|sees?|views?|thinks?|considers?|describes?|calls?|puts?)'
            r'(?:,|:|\s+that)?\s+'  # Optional comma, colon, or "that" after verb
            r'[^.!?]+[.!?]',  # Rest of sentence until ending
            re.IGNORECASE
        )

        # Keep removing orphan sentences until none are found
        while True:
            match = mid_sentence_orphan_pattern.search(repaired_para)
            if not match:
                break
            # Remove the orphan sentence but keep the sentence ending from the previous sentence
            orphan_sentence = match.group(0)[1:].strip()  # Skip the sentence ending char
            logger.info(f"Removing mid-sentence orphan: {orphan_sentence[:50]}...")
            # Replace with just the sentence ending (keep the period/etc from previous sentence)
            repaired_para = repaired_para[:match.start() + 1] + repaired_para[match.end():]

        if repaired_para.strip():
            repaired_paragraphs.append(repaired_para)

    return '\n\n'.join(repaired_paragraphs)


def cleanup_dangling_attributions(text: str) -> tuple[str, int]:
    """Remove dangling attribution wrappers left after content deletion.

    These are patterns like:
    - "Deutsch argues," (trailing comma, no content)
    - "Deutsch notes." (period immediately after verb)
    - "saying." (orphan participial)
    - "Deutsch says:" (colon with no content)
    - "David Deutsch captures this idea, stating," (trailing comma)

    Args:
        text: Text that may have dangling attribution fragments.

    Returns:
        Tuple of (cleaned_text, count_of_removals).
    """
    result = text
    removal_count = 0

    # Patterns for dangling attributions (attribution verb followed by just punctuation)
    # These indicate the content was removed but the wrapper remained
    dangling_patterns = [
        # "Deutsch argues," or "Deutsch argues." at end of sentence/before newline
        (
            r'\b(?:Deutsch|David Deutsch|He|She)\s+'
            r'(?:argues?|says?|notes?|observes?|warns?|asserts?|claims?|explains?|'
            r'points?\s+out|suggests?|states?|contends?|believes?|maintains?|emphasizes?|'
            r'stresses?|highlights?|insists?|remarks?|cautions?|envisions?|tells?|adds?|'
            r'writes?|acknowledges?|reflects?|challenges?|sees?|views?|thinks?|considers?|'
            r'describes?|calls?|puts?|captures?\s+this\s+idea)'
            r'(?:\s+that)?'  # Optional "that"
            r'\s*[,.:;]\s*(?=\n|$|[A-Z])',  # Ends with punct, followed by newline/end/capital
            re.IGNORECASE
        ),
        # "saying." or "noting," as orphan participial
        (
            r'\b(?:saying|noting|arguing|observing|warning|explaining|claiming|asserting|'
            r'adding|suggesting|stating|emphasizing|stressing|insisting|remarking)'
            r'\s*[,.:;]\s*(?=\n|$|[A-Z])',
            re.IGNORECASE
        ),
        # Double punctuation artifacts: ", ." or ": ," or ", ,"
        (
            r'[,.:;]\s*[,.:;]',
            0  # No flags
        ),
        # Attribution with colon but no content: "Deutsch says: " followed by capital/newline
        (
            r'\b(?:Deutsch|David Deutsch|He|She)\s*:\s*(?=\n|$|[A-Z])',
            re.IGNORECASE
        ),
    ]

    for pattern, flags in dangling_patterns:
        compiled = re.compile(pattern, flags) if flags else re.compile(pattern)

        # Process from right to left to maintain positions
        matches = list(compiled.finditer(result))
        for match in reversed(matches):
            matched_text = match.group(0)
            start, end = match.start(), match.end()

            # Don't remove if it's part of a larger valid structure
            # (e.g., "Deutsch argues, " followed by a quote)
            after_text = result[end:end + 10] if end < len(result) else ""
            if after_text.lstrip().startswith('"') or after_text.lstrip().startswith('\u201c'):
                continue

            # Remove the dangling attribution
            before = result[:start].rstrip()
            after = result[end:].lstrip()

            # Add space if needed for sentence flow
            if before and after and before[-1] in '.!?' and after[0].isupper():
                result = before + ' ' + after
            elif before and after and before[-1] not in '.!?,;:' and after[0] not in '.!?,;:':
                result = before + ' ' + after
            else:
                result = before + after

            removal_count += 1
            logger.info(f"Removed dangling attribution: '{matched_text}'")

    # Clean up multiple spaces/newlines
    result = re.sub(r'  +', ' ', result)
    result = re.sub(r'\n{3,}', '\n\n', result)

    return result, removal_count


def compute_chapter_prose_metrics(
    final_text: str,
    original_text: str | None = None,
) -> dict:
    """Compute per-chapter prose metrics for Ideas Edition quality tracking.

    Calculates:
    - Per-chapter sentence counts (in prose sections)
    - Whether fallback was used (detects fallback variant phrases)
    - Optional: dropped sentence count if original_text provided

    Args:
        final_text: The final processed draft text.
        original_text: Optional original pre-processing text for drop counting.

    Returns:
        Dict with chapter-level metrics.
    """
    # Fallback variant indicators
    FALLBACK_INDICATORS = [
        "This chapter develops the theme",
        "The core tension in this chapter",
        "This chapter threads from specific evidence",
    ]

    def count_prose_sentences(chapter_text: str) -> int:
        """Count sentences in prose section (before Key Excerpts)."""
        # Find Key Excerpts section
        key_excerpts_pos = chapter_text.find('### Key Excerpts')
        if key_excerpts_pos == -1:
            key_excerpts_pos = len(chapter_text)

        # Get prose portion (after header, before Key Excerpts)
        header_end = chapter_text.find('\n')
        if header_end == -1:
            return 0

        prose = chapter_text[header_end:key_excerpts_pos].strip()
        if not prose:
            return 0

        # Count sentences (simple heuristic: split on .!? followed by space+capital)
        sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', prose)
        return len([s for s in sentences if s.strip()])

    def has_fallback(chapter_text: str) -> bool:
        """Check if chapter uses fallback narrative."""
        for indicator in FALLBACK_INDICATORS:
            if indicator in chapter_text:
                return True
        return False

    # Parse chapters
    chapter_pattern = re.compile(r'^## Chapter (\d+)', re.MULTILINE)
    chapters = list(chapter_pattern.finditer(final_text))

    if not chapters:
        return {"chapters": [], "total_sentences_kept": 0, "fallback_chapters": 0}

    chapter_metrics = []
    total_sentences = 0
    fallback_count = 0

    for i, chapter_match in enumerate(chapters):
        chapter_num = int(chapter_match.group(1))
        chapter_start = chapter_match.start()
        chapter_end = chapters[i + 1].start() if i + 1 < len(chapters) else len(final_text)
        chapter_text = final_text[chapter_start:chapter_end]

        sentence_count = count_prose_sentences(chapter_text)
        used_fallback = has_fallback(chapter_text)

        if used_fallback:
            fallback_count += 1

        total_sentences += sentence_count

        metrics = {
            "chapter": chapter_num,
            "sentences_kept": sentence_count,
            "fallback_used": used_fallback,
        }

        # If original text provided, calculate dropped count
        if original_text:
            orig_chapters = list(chapter_pattern.finditer(original_text))
            for j, orig_match in enumerate(orig_chapters):
                if int(orig_match.group(1)) == chapter_num:
                    orig_start = orig_match.start()
                    orig_end = orig_chapters[j + 1].start() if j + 1 < len(orig_chapters) else len(original_text)
                    orig_chapter_text = original_text[orig_start:orig_end]
                    orig_sentence_count = count_prose_sentences(orig_chapter_text)
                    metrics["sentences_dropped"] = max(0, orig_sentence_count - sentence_count)
                    break

        chapter_metrics.append(metrics)

    return {
        "chapters": chapter_metrics,
        "total_sentences_kept": total_sentences,
        "fallback_chapters": fallback_count,
        "total_chapters": len(chapters),
    }


def normalize_markdown_headers(text: str) -> tuple[str, dict]:
    """Ensure proper blank lines before markdown headers.

    Final render pass that fixes formatting issues:
    - Ensures a blank line before any line matching ^#{2,3} (Chapter/section headers)
    - Ensures a blank line after ## Chapter N if next line is prose or subheader

    This is a pure formatting pass - no content changes, only whitespace.

    Args:
        text: The draft markdown text.

    Returns:
        Tuple of (normalized_text, report_dict).
    """
    lines = text.split('\n')
    result_lines = []
    fixes_applied = 0

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Check if this line is a header (## or ###)
        is_header = stripped.startswith('## ') or stripped.startswith('### ')

        if is_header and i > 0:
            # Check if previous line is blank
            prev_line = lines[i - 1].strip() if i > 0 else ''

            if prev_line != '':
                # Need to insert a blank line before this header
                result_lines.append('')
                fixes_applied += 1

        result_lines.append(line)

        # If this is a chapter header, ensure blank line after
        if stripped.startswith('## Chapter') and i < len(lines) - 1:
            next_line = lines[i + 1].strip() if i + 1 < len(lines) else ''
            # If next line is not blank and not empty, we'll add blank line
            # (The next iteration will handle it naturally since we're building result_lines)

    result = '\n'.join(result_lines)

    # Clean up any triple+ newlines that might result
    result = re.sub(r'\n{3,}', '\n\n', result)

    if fixes_applied > 0:
        logger.debug(f"Markdown header normalizer: inserted {fixes_applied} blank lines")

    return result, {
        "blank_lines_inserted": fixes_applied,
    }


def repair_whitespace(text: str) -> str:
    """Repair whitespace issues left after sentence/paragraph deletions.

    Fixes:
    - Missing space after closing quote before next word: `."This` → `." This`
    - Leading spaces at start of paragraphs
    - Multiple consecutive blank lines
    - Multiple consecutive spaces

    Args:
        text: Text that may have whitespace issues after deletions.

    Returns:
        Text with repaired whitespace.
    """
    result = text

    # Fix missing space after closing quote + punctuation before capital letter
    # Pattern: closing punctuation + quote + capital letter (no space between)
    # e.g., `wrong."This` → `wrong." This`
    # Use negative lookahead to avoid adding space if one already exists
    result = re.sub(r'([.!?])(["\u201d])(?! )([A-Z])', r'\1\2 \3', result)

    # Fix leading spaces at start of paragraphs
    # Split by paragraph, strip leading whitespace from each, rejoin
    paragraphs = result.split('\n\n')
    cleaned_paragraphs = []
    for para in paragraphs:
        # Strip leading spaces from each line in the paragraph
        lines = para.split('\n')
        cleaned_lines = [line.lstrip() if not line.strip().startswith('#') else line for line in lines]
        cleaned_paragraphs.append('\n'.join(cleaned_lines))

    result = '\n\n'.join(cleaned_paragraphs)

    # Normalize multiple blank lines to double newline
    result = re.sub(r'\n{3,}', '\n\n', result)

    # Normalize multiple spaces to single space (but preserve indentation)
    result = re.sub(r'  +', ' ', result)

    return result.strip()


def fix_unquoted_excerpts(text: str) -> tuple[str, dict]:
    """Fix unquoted block quotes and Core Claims in Ideas Edition output.

    Detects and wraps:
    1. Block quotes (> lines) without quotation marks
    2. Core Claims bullets with unquoted supporting text after colon

    Args:
        text: The generated text.

    Returns:
        Tuple of (fixed_text, report_dict).
    """
    lines = text.split('\n')
    fixed_lines = []
    fixes_made = []

    for i, line in enumerate(lines):
        fixed_line = line

        # Fix block quotes without quotation marks
        # Pattern: > Some text without quotes
        # Should be: > "Some text"
        if line.strip().startswith('>'):
            content = line.strip()[1:].strip()  # Remove > and whitespace
            # Skip attribution lines (— Speaker)
            if content.startswith('—') or content.startswith('-'):
                fixed_lines.append(line)
                continue
            # Skip if already has quotes
            if content.startswith('"') or content.startswith('\u201c'):
                fixed_lines.append(line)
                continue
            # Skip empty lines
            if not content:
                fixed_lines.append(line)
                continue
            # Wrap in quotes
            # Preserve leading whitespace from original line
            leading_ws = len(line) - len(line.lstrip())
            fixed_line = ' ' * leading_ws + '> "' + content + '"'
            fixes_made.append({
                'type': 'block_quote',
                'line': i + 1,
                'original': line.strip()[:50] + '...' if len(line.strip()) > 50 else line.strip(),
            })

        # Fix Core Claims without quotation marks
        # Pattern: - **Claim**: some text without quotes
        # Should be: - **Claim**: "Some text"
        elif line.strip().startswith('- **') and '**: ' in line:
            # Split into claim part and quote part
            match = re.match(r'^(\s*-\s+\*\*[^*]+\*\*:\s*)(.+)$', line)
            if match:
                prefix = match.group(1)
                quote_part = match.group(2).strip()
                # Skip if already quoted
                if quote_part.startswith('"') or quote_part.startswith('\u201c'):
                    fixed_lines.append(line)
                    continue
                # Wrap in quotes, capitalize first letter
                if quote_part:
                    # Capitalize first letter if lowercase
                    if quote_part[0].islower():
                        quote_part = quote_part[0].upper() + quote_part[1:]
                    # Remove trailing period if present, we'll add it after the quote
                    if quote_part.endswith('.'):
                        quote_part = quote_part[:-1]
                    fixed_line = prefix + '"' + quote_part + '."'
                    fixes_made.append({
                        'type': 'core_claim',
                        'line': i + 1,
                        'original': line.strip()[:50] + '...' if len(line.strip()) > 50 else line.strip(),
                    })

        fixed_lines.append(fixed_line)

    report = {
        'fixes_made': len(fixes_made),
        'fix_details': fixes_made[:10],  # Limit to first 10 for brevity
    }

    if fixes_made:
        logger.info(f"Fixed {len(fixes_made)} unquoted excerpts/claims")

    return '\n'.join(fixed_lines), report


def filter_anachronism_paragraphs(text: str) -> tuple[str, dict]:
    """Filter paragraphs containing anachronism keywords without validated quotes.

    This is a safety net for Ideas Edition to catch contemporary framing
    that slipped past generation prompts. Only removes paragraphs that:
    1. Contain an anachronism keyword (case-insensitive)
    2. Do NOT contain a validated quote (text in quotation marks)

    Args:
        text: The generated text.

    Returns:
        Tuple of (cleaned_text, report_dict).
    """
    paragraphs = text.split('\n\n')
    filtered_paragraphs = []
    removed_paragraphs = []

    for para in paragraphs:
        stripped = para.strip()
        if not stripped:
            continue

        # Skip headings
        if stripped.startswith('#'):
            filtered_paragraphs.append(para)
            continue

        # Check if paragraph has a quote (any quoted text)
        has_quote = bool(QUOTE_PATTERN.search(stripped))

        # Check for anachronism keywords (case-insensitive)
        para_lower = stripped.lower()
        found_anachronism = None
        for keyword in ANACHRONISM_KEYWORDS:
            if keyword.lower() in para_lower:
                found_anachronism = keyword
                break

        # Remove if has anachronism AND no quote to anchor it
        if found_anachronism and not has_quote:
            logger.info(
                f"Anachronism filter: removing paragraph with '{found_anachronism}' "
                f"(no quote): {stripped[:60]}..."
            )
            removed_paragraphs.append({
                'keyword': found_anachronism,
                'paragraph': stripped[:100] + '...' if len(stripped) > 100 else stripped,
            })
            continue

        filtered_paragraphs.append(para)

    report = {
        'paragraphs_scanned': len(paragraphs),
        'paragraphs_removed': len(removed_paragraphs),
        'removed_details': removed_paragraphs,
    }

    return '\n\n'.join(filtered_paragraphs), report


# Keep old function name for backwards compatibility, but use hard enforcement
def enforce_attributed_speech(
    text: str,
    transcript: str,
    remediate_invalid: bool = True,  # Ignored, always hard enforcement now
) -> tuple[str, dict]:
    """Enforce attributed speech validation with HARD enforcement.

    This is now a wrapper around enforce_attributed_speech_hard.
    The remediate_invalid parameter is ignored - we always do hard enforcement.

    Args:
        text: The generated text.
        transcript: The canonical transcript.
        remediate_invalid: Ignored (kept for API compatibility).

    Returns:
        Tuple of (cleaned_text, report_dict).
    """
    return enforce_attributed_speech_hard(text, transcript)


# ==============================================================================
# Polish Pass - Prose Quality Enhancement
# ==============================================================================

POLISH_SYSTEM_PROMPT = """You are a ruthless editor who despises AI-generated prose. Your task: transform this text into writing that sounds unmistakably human.

CORE PRINCIPLE: If a sentence sounds like something ChatGPT would write, rewrite it completely.

BANNED PATTERNS - REWRITE ANY SENTENCE CONTAINING:

1. "This [noun]" sentence starters (the #1 AI tell):
   - "This observation..." → Rewrite to start differently
   - "This principle..." → Name the principle directly
   - "This capacity..." → Be specific about what capacity
   - "This reality..." → State the reality plainly
   - "These ideas..." → Name the ideas

2. Generic profundity (empty impressive-sounding phrases):
   - "profound implications" → What ARE the implications?
   - "far-reaching consequences" → Name them
   - "transformative power" → Show the transformation
   - "fundamental aspect" → Just state the aspect
   - "the very essence of" → Delete, state directly

3. Grandiose conclusions:
   - "The universe awaits..." → Delete entirely or be concrete
   - "...is boundless/limitless" → Give specific scope instead
   - "...the promise of transformation" → What transformation?
   - "...infinite potential" → Potential for what exactly?

4. Overused academic verbs (find synonyms or restructure):
   - "underscores" → emphasizes, reveals, shows (but vary!)
   - "highlights" → (often deletable - just state the point)
   - "articulates" → says, argues, writes
   - "emphasizes" → (don't overuse this either)

5. Hollow transitions:
   - "It is worth noting that" → Delete, just state it
   - "It is important to recognize" → Delete
   - "The implications of this are" → State implications directly
   - "This invites reflection on" → Just reflect

6. AI comfort phrases:
   - "In the face of" → During, amid, confronting
   - "At the heart of" → Central to, core of
   - "Paved the way for" → Enabled, led to, caused
   - "Serves as a reminder" → Delete or state the reminder

STRUCTURAL RULES:
- No two consecutive paragraphs should end with similar rhythms
- Vary sentence length dramatically (some 5 words, some 30)
- Start paragraphs with concrete nouns or actions, not abstractions
- End chapters with a specific thought, not a grand gesture

PRESERVE:
- All factual content and quotes
- Markdown formatting
- The author's actual arguments

OUTPUT: Return ONLY the polished text. No commentary."""


async def polish_chapter(
    chapter_text: str,
    client: Optional["LLMClient"] = None,
) -> str:
    """Polish chapter text through a stronger model for prose quality.

    Args:
        chapter_text: Raw chapter markdown text.
        client: Optional LLM client (created if not provided).

    Returns:
        Polished chapter text.
    """
    if client is None:
        from src.services.llm_client import get_llm_client
        client = await get_llm_client()

    request = LLMRequest(
        model=POLISH_MODEL,
        messages=[
            ChatMessage(role="system", content=POLISH_SYSTEM_PROMPT),
            ChatMessage(role="user", content=f"Polish this chapter:\n\n{chapter_text}"),
        ],
        temperature=0.3,  # Lower temperature for more consistent editing
        max_tokens=4000,
    )

    response = await client.generate(request)
    return response.text


def sanitize_interview_title(
    title: str,
    fallback: Optional[str] = None,
    transcript: Optional[str] = None,
) -> str:
    """Ensure interview mode doesn't use generic titles like 'Interview'.

    Args:
        title: The book title from draft plan.
        fallback: Optional fallback (e.g., project name, YouTube title).
        transcript: Optional transcript to extract title from.

    Returns:
        A proper book title, never a generic placeholder.
    """
    result = None

    if title and title.lower().strip() not in GENERIC_TITLES:
        result = title
    # Use fallback if provided and not generic
    elif fallback and fallback.lower().strip() not in GENERIC_TITLES:
        result = fallback
    # Try to extract book title from transcript
    elif transcript:
        extracted = _extract_book_title_from_transcript(transcript)
        if extracted:
            result = extracted

    if result:
        return _clean_title(result)

    # Last resort: generic placeholder (model should be told to improve it)
    return "Untitled Interview"


def _clean_title(title: str) -> str:
    """Clean up a title by removing trailing punctuation and extra whitespace.

    Args:
        title: Raw title string.

    Returns:
        Cleaned title without trailing commas, periods, etc.
    """
    # Strip whitespace
    title = title.strip()
    # Remove trailing punctuation (but keep ! and ? if intentional)
    while title and title[-1] in ".,;:":
        title = title[:-1].strip()
    return title


def _clean_markdown_title(markdown: str) -> str:
    """Clean up the H1 title in generated markdown.

    The model sometimes adds trailing punctuation to titles.
    This post-processes the markdown to clean it up.

    Args:
        markdown: Generated markdown content.

    Returns:
        Markdown with cleaned H1 title.
    """
    import re

    # Match H1 title at start of document: # Title,
    h1_pattern = r'^(#\s+)(.+?)([.,;:]+)?(\s*)$'

    lines = markdown.split('\n')
    for i, line in enumerate(lines):
        match = re.match(h1_pattern, line)
        if match:
            prefix = match.group(1)  # "# "
            title = match.group(2).strip()  # The title text
            # Clean trailing punctuation from title
            title = _clean_title(title)
            lines[i] = f"{prefix}{title}"
            break  # Only clean first H1

    return '\n'.join(lines)


def _extract_book_title_from_transcript(transcript: str) -> Optional[str]:
    """Try to extract a book title mentioned in the transcript.

    Looks for patterns like:
    - "The title of the book is X"
    - "my book X"
    - "The Beginning of Infinity" (quoted)

    Returns:
        Extracted title if found, None otherwise.
    """
    import re

    # Pattern 1: "title of the book is X" or "book is titled X"
    title_pattern = r'(?:title\s+of\s+(?:the\s+)?book\s+is|book\s+is\s+titled?)\s+["\']?([^"\'\.]+)["\']?'
    match = re.search(title_pattern, transcript, re.IGNORECASE)
    if match:
        return match.group(1).strip().strip('"\'')

    # Pattern 2: "my book X" or "the book X"
    book_pattern = r'(?:my|the)\s+book\s+["\']([^"\']+)["\']'
    match = re.search(book_pattern, transcript, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # Pattern 3: Look for "The Beginning of Infinity" specifically (common case)
    if "beginning of infinity" in transcript.lower():
        return "The Beginning of Infinity"

    return None


def _extract_speaker_name_from_transcript(transcript: str) -> Optional[str]:
    """Extract the main speaker/guest name from transcript.

    Looks for patterns like:
    - "Today we have [title] John Smith"
    - "our guest is John Smith"
    - "welcome John Smith"
    - Most frequent non-Host speaker in "Name:" attributions

    Returns:
        Speaker name if found, None otherwise.
    """
    import re
    from collections import Counter

    # Pattern 1: "Today we have [title] Name" or "Today we have Name"
    today_pattern = r'[Tt]oday\s+we\s+have\s+(?:\w+\s+)?([A-Z][a-z]+\s+[A-Z][a-z]+)'
    match = re.search(today_pattern, transcript)
    if match:
        return match.group(1).strip()

    # Pattern 2: "our guest is Name" or "guest today is Name"
    guest_pattern = r'(?:our\s+)?guest(?:\s+today)?\s+is\s+([A-Z][a-z]+\s+[A-Z][a-z]+)'
    match = re.search(guest_pattern, transcript, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # Pattern 3: "welcome Name" at start of sentence
    welcome_pattern = r'[Ww]elcome[,]?\s+([A-Z][a-z]+\s+[A-Z][a-z]+)'
    match = re.search(welcome_pattern, transcript)
    if match:
        return match.group(1).strip()

    # Pattern 4: Find most common speaker attribution (Name:)
    # Exclude common host labels
    host_labels = {'host', 'interviewer', 'moderator', 'q', 'question'}
    speaker_pattern = r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*:'
    speakers = re.findall(speaker_pattern, transcript, re.MULTILINE)
    if speakers:
        # Filter out host-like names and count
        non_host_speakers = [s for s in speakers if s.lower() not in host_labels]
        if non_host_speakers:
            counter = Counter(non_host_speakers)
            # Return most common (likely the main guest)
            most_common = counter.most_common(1)[0][0]
            return most_common

    return None


def _format_interview_title(speaker: Optional[str], book_title: Optional[str]) -> Optional[str]:
    """Format a proper interview ebook title.

    Creates titles like:
    - "David Deutsch on *The Beginning of Infinity*"
    - "David Deutsch Interview" (if no book title)
    - None (if no speaker name)

    Args:
        speaker: Speaker/guest name.
        book_title: Book or topic title.

    Returns:
        Formatted title or None if insufficient info.
    """
    if not speaker:
        return None

    if book_title:
        return f"{speaker} on *{book_title}*"
    else:
        return f"{speaker} Interview"


def _fix_interview_title(markdown: str, transcript: str) -> str:
    """Post-process markdown to fix the H1 title for interview mode.

    Replaces generic/chapter-like titles with proper interview format:
    "# The Enlightenment" -> "# David Deutsch on *The Beginning of Infinity*"

    The original title becomes the first H2 section heading.

    Args:
        markdown: Generated markdown content.
        transcript: Original transcript for extraction.

    Returns:
        Markdown with proper interview title format.
    """
    import re

    # Extract speaker and book title from transcript
    speaker = _extract_speaker_name_from_transcript(transcript)
    book_title = _extract_book_title_from_transcript(transcript)

    # Format the proper title
    proper_title = _format_interview_title(speaker, book_title)

    if not proper_title:
        # Can't improve, return as-is
        return markdown

    # Find the current H1 title
    h1_match = re.match(r'^#\s+(.+?)$', markdown, re.MULTILINE)
    if not h1_match:
        # No H1 found, prepend the proper title
        return f"# {proper_title}\n\n{markdown}"

    current_title = h1_match.group(1).strip()

    # Check if current title is already good (contains speaker name)
    if speaker and speaker.lower() in current_title.lower():
        return markdown  # Already has speaker name, don't change

    # Check if current title looks like a chapter heading (not a book title)
    # Chapter headings are typically short and topical
    chapter_indicators = [
        len(current_title.split()) <= 4,  # Short titles
        not any(word in current_title.lower() for word in ['interview', 'conversation', 'talk']),
        current_title.lower() not in ['introduction', 'conclusion'],
    ]

    if all(chapter_indicators):
        # Current title looks like a chapter/section heading
        # Replace H1 with proper title, demote current to H2
        lines = markdown.split('\n')

        # Find and replace the H1 line
        for i, line in enumerate(lines):
            if re.match(r'^#\s+', line) and not re.match(r'^##', line):
                # Insert proper title as H1, demote current to H2
                lines[i] = f"# {proper_title}\n\n## {current_title}"
                break

        return '\n'.join(lines)

    return markdown


def postprocess_interview_markdown(
    markdown: str,
    source_url: Optional[str] = None,
    include_metadata: bool = True,
) -> str:
    """Post-process interview markdown for proper structure and polish.

    Applies deterministic fixes that improve "book feel" without changing content:
    1. Fix heading hierarchy (## Key Ideas → ### Key Ideas, ## The Conversation → ###)
       This makes them subordinate to the topic heading.
    2. Add metadata block under H1 (source, format, date)
    3. Fix "Thank you" formatting (#### → *Interviewer:*)

    Args:
        markdown: Generated interview markdown.
        source_url: Optional source URL for metadata block.
        include_metadata: Whether to add metadata block (default True).

    Returns:
        Post-processed markdown with improved structure.
    """
    import re
    from datetime import date

    lines = markdown.split('\n')
    result_lines = []
    h1_index = None
    topic_heading = None
    inside_conversation = False
    seen_topic_in_conversation = False

    for i, line in enumerate(lines):
        # Track H1 position for metadata insertion
        if re.match(r'^#\s+[^#]', line) and h1_index is None:
            h1_index = len(result_lines)
            result_lines.append(line)
            continue

        # Fix #1: Ensure Key Ideas is ### (downgrade from ## to be subordinate to topic)
        if re.match(r'^#{2,3}\s+Key Ideas', line, re.IGNORECASE):
            line = re.sub(r'^#{2,3}\s+', '### ', line)
            result_lines.append(line)
            continue

        # Fix #1: Ensure The Conversation is ### (downgrade from ## to be subordinate to topic)
        if re.match(r'^#{2,3}\s+The Conversation', line, re.IGNORECASE):
            line = re.sub(r'^#{2,3}\s+', '### ', line)
            inside_conversation = True
            result_lines.append(line)
            continue

        # Track the topic heading (first ## after H1, after excluding structural sections)
        if re.match(r'^##\s+[^#]', line) and topic_heading is None:
            # This is the topic heading (e.g., "## The Enlightenment")
            topic_heading = re.sub(r'^##\s+', '', line).strip()
            result_lines.append(line)
            continue

        # Fix #1: Remove duplicate topic heading inside The Conversation
        if inside_conversation and topic_heading:
            if re.match(rf'^###\s+{re.escape(topic_heading)}\s*$', line, re.IGNORECASE):
                if not seen_topic_in_conversation:
                    seen_topic_in_conversation = True
                    # Skip this duplicate heading
                    continue

        # Fix #5: Convert "#### Thank you..." to "*Interviewer:* Thank you..."
        thank_you_match = re.match(r'^#{1,4}\s+(Thank\s+you.*)$', line, re.IGNORECASE)
        if thank_you_match:
            thank_text = thank_you_match.group(1)
            result_lines.append(f'*Interviewer:* {thank_text}')
            continue

        result_lines.append(line)

    # Fix #4: Insert metadata block after H1
    if include_metadata and h1_index is not None:
        # Compute actual word count from the content
        content_text = '\n'.join(result_lines)
        word_count = len(content_text.split())

        metadata_lines = []
        if source_url:
            metadata_lines.append(f'*Source:* {source_url}')
        metadata_lines.append('*Format:* Interview')
        metadata_lines.append(f'*Word count:* ~{word_count:,}')
        metadata_lines.append(f'*Generated:* {date.today().isoformat()}')

        # Insert after H1 (with blank line before and after)
        insert_pos = h1_index + 1
        metadata_block = [''] + metadata_lines + ['']
        result_lines = result_lines[:insert_pos] + metadata_block + result_lines[insert_pos:]

    # Apply speaker attribution fix
    result_text = '\n'.join(result_lines)
    result_text = fix_speaker_attribution(result_text)

    return result_text


# ==============================================================================
# Speaker Attribution (Heuristic Detection)
# ==============================================================================

# Caller intro patterns - high confidence
# These detect when a caller is being introduced
CALLER_INTRO_PATTERNS = [
    # "[Name] in [Location]...you're on the air"
    r'###\s+.*?([A-Z][a-z]+)\s+in\s+[A-Z][a-z]+.*?you\'?re\s+on\s+the\s+air',
    # "[Name], you're on the air"
    r'###\s+.*?([A-Z][a-z]+),?\s+you\'?re\s+on\s+the\s+air',
    # "Let's go to [Name] in [Location]"
    r'###\s+.*?[Ll]et\'?s\s+go\s+to\s+([A-Z][a-z]+)\s+in\s+[A-Z]',
    # "[Name] is calling from"
    r'###\s+.*?([A-Z][a-z]+)\s+is\s+calling\s+from',
    # "[Name] in [Location]. [Name], thank you" (e.g., "David in Boston. David, thank you")
    r'###\s+.*?([A-Z][a-z]+)\s+in\s+[A-Z][a-z]+.*?[Tt]hank(?:s|\s+you)',
]

# EXPLICIT Deutsch handoff patterns - these END caller mode
# Only patterns that clearly indicate the host is now asking Deutsch to respond
DEUTSCH_HANDOFF_PATTERNS = [
    # "David Deutsch, what do you say"
    r'###\s+.*?David\s+Deutsch.*?what\s+do\s+you\s+say',
    # "[Name], let us pick it up. David Deutsch, what do you say"
    r'###\s+.*?David\s+Deutsch.*?\?',
    # "Professor Deutsch, what do you say" / "Mr. Deutsch, what do you say"
    r'###\s+.*?(?:Professor|Mr\.?)\s+Deutsch.*?what\s+do\s+you',
    # Clear question to Deutsch ending with ?
    r'###\s+.*?(?:Professor|Mr\.?)\s+Deutsch.*?\?$',
]

# Host comment patterns - these do NOT end caller mode
# The caller may still respond after these
HOST_COMMENT_PATTERNS = [
    # "[Name], I'll put that to..." - host is commenting, caller may still respond
    r'###\s+[A-Z][a-z]+,\s+I\'ll\s+put\s+that\s+to',
    # "[Name], standby" - host is commenting
    r'###\s+[A-Z][a-z]+,\s+stand\s*by',
    # "You've got a specific question" - prompting caller to continue
    r'###\s+[Yy]ou\'?ve\s+got\s+a\s+specific\s+question',
]

# Patterns that indicate caller is speaking (in their response)
CALLER_SPEECH_PATTERNS = [
    r'^Hi,?\s+Tom',  # Greeting the host
    r'^Thanks?\s+for\s+(?:having|taking)',
    r'^I\s+have\s+a\s+question\s+for\s+(?:Mr\.|Professor)',
    r'^(?:Mr\.|Professor)\s+Deutsch,\s+(?:given|I)',
    r'^Yeah,?\s+thanks?\s+for\s+having',  # "Yeah, thanks for having me on"
    r'^I\s+think\s+that\s+Professor\s+Deutsch',
    r'^I\s+guess\s+for\s+me',
    r'^I\'m\s+(?:certainly|not)\s+',
]

# Clip patterns - external audio/video clips played during the show
CLIP_PATTERNS = [
    (r'Carl\s+Sagan', 'Carl Sagan'),
    (r'Stephen\s+Hawking', 'Stephen Hawking'),
    (r'Richard\s+Feynman', 'Richard Feynman'),
]


def fix_speaker_attribution(markdown: str) -> str:
    """Fix speaker attribution in interview markdown using heuristics.

    Applies deterministic fixes:
    1. Caller detection and persistence until explicit Deutsch handoff
    2. Header sanity: demote non-question headers to text
    3. CLIP detection for external audio/video clips
    4. HOST detection for short interjections mislabeled as GUEST

    Args:
        markdown: Interview markdown with potentially wrong speaker labels.

    Returns:
        Markdown with corrected speaker attribution.
    """
    import re

    # First pass: fix speaker labels (CALLER detection)
    markdown = _fix_speaker_labels(markdown)

    # Second pass: fix malformed headers (non-? headers that should be text)
    markdown = _fix_malformed_headers(markdown)

    # Third pass: detect and label clips
    markdown = _fix_clip_headers(markdown)

    # Fourth pass: detect HOST interjections mislabeled as GUEST
    markdown = _fix_host_interjections(markdown)

    return markdown


def _fix_speaker_labels(markdown: str) -> str:
    """Fix GUEST: labels to CALLER: where appropriate.

    In a caller segment, GUEST labels are converted to CALLER unless
    they sound like Deutsch responding (complex explanations, technical answers).
    """
    import re

    lines = markdown.split('\n')
    result_lines = []

    # State tracking
    current_caller: Optional[str] = None
    in_caller_segment = False
    # Track position: first GUEST after caller intro is always caller
    guest_count_in_segment = 0

    for i, line in enumerate(lines):
        # Check if this is a question header
        if line.startswith('### '):
            header_text = line

            # Check for caller intro patterns FIRST
            caller_name = None
            for pattern in CALLER_INTRO_PATTERNS:
                match = re.search(pattern, header_text, re.IGNORECASE)
                if match:
                    caller_name = match.group(1)
                    # Disambiguate: "David in Boston" is a caller, not "David Deutsch"
                    if caller_name.lower() == 'david' and 'deutsch' in header_text.lower():
                        caller_name = None  # This is about David Deutsch, not a caller
                    break

            if caller_name:
                # New caller intro - start caller segment
                current_caller = caller_name
                in_caller_segment = True
                guest_count_in_segment = 0
                result_lines.append(line)
                continue

            # Check for EXPLICIT Deutsch handoff (ends caller segment)
            is_deutsch_handoff = False
            for pattern in DEUTSCH_HANDOFF_PATTERNS:
                if re.search(pattern, header_text, re.IGNORECASE):
                    is_deutsch_handoff = True
                    break

            if is_deutsch_handoff:
                # Clear handoff to Deutsch - end caller segment
                in_caller_segment = False
                current_caller = None
                guest_count_in_segment = 0
                result_lines.append(line)
                continue

            # Check for host comments (do NOT end caller segment)
            is_host_comment = False
            for pattern in HOST_COMMENT_PATTERNS:
                if re.search(pattern, header_text, re.IGNORECASE):
                    is_host_comment = True
                    break

            # If it's a host comment and we're in a caller segment,
            # the caller segment continues (host is prompting caller to continue)
            if is_host_comment and in_caller_segment:
                # Caller segment persists - reset guest count for next caller response
                guest_count_in_segment = 0
                result_lines.append(line)
                continue

            result_lines.append(line)
            continue

        # Check if this is a speaker attribution line
        guest_match = re.match(r'^\*\*GUEST:\*\*\s*(.*)$', line)
        if guest_match:
            response_start = guest_match.group(1)
            guest_count_in_segment += 1

            # If in caller segment, this is likely the caller speaking
            if in_caller_segment and current_caller:
                # Default to CALLER for first response in segment
                # or if response has caller speech patterns
                is_caller_speech = False

                # First response after caller intro or host comment is always caller
                if guest_count_in_segment == 1:
                    is_caller_speech = True
                else:
                    # Check for explicit caller speech patterns
                    for pattern in CALLER_SPEECH_PATTERNS:
                        if re.match(pattern, response_start, re.IGNORECASE):
                            is_caller_speech = True
                            break

                    # If response mentions "Mr. Deutsch" or "Professor Deutsch" as addressee,
                    # it's likely a caller speaking TO Deutsch
                    if 'mr. deutsch' in response_start.lower() or 'professor deutsch' in response_start.lower():
                        is_caller_speech = True

                if is_caller_speech:
                    line = f'**CALLER ({current_caller}):** {response_start}'

            result_lines.append(line)
            continue

        result_lines.append(line)

    return '\n'.join(result_lines)


def _fix_malformed_headers(markdown: str) -> str:
    """Fix headers that should be text (non-? headers followed by GUEST continuation).

    Excludes host comments and clip intros from conversion.

    Also detects first-person continuation markers in the header itself:
    - "what I said", "I'm saying", "I said" → indicates Deutsch speaking, not a header
    """
    import re

    lines = markdown.split('\n')
    result_lines = []
    i = 0

    # First-person markers that indicate the header is actually Deutsch speaking
    # These should be converted to GUEST even without a following continuation
    FIRST_PERSON_PATTERNS = [
        r'\bwhat I said\b',
        r'\bwhat I\'m saying\b',
        r'\bwhat I am saying\b',
        r'\bI\'m saying\b',
        r'\bI am saying\b',
        r'\bI said\b',
        r'\bI think\b',
        r'\bI believe\b',
        r'\bI would say\b',
        r'\bI\'d say\b',
        r'\bI mean\b',
        r'\bI\'ve been\b',
        r'\bI have been\b',
        r'\bI was\b',
        r'\bI\'ve said\b',
        r'\bI have said\b',
        r'\bmy point\b',
        r'\bmy view\b',
        r'\bmy argument\b',
        r'\bmy position\b',
    ]

    while i < len(lines):
        line = lines[i]

        # Check for ### header that doesn't end with ?
        if line.startswith('### ') and not line.rstrip().endswith('?'):
            header_text = line[4:].strip()  # Remove "### "

            # Don't convert host comments - these are valid headers
            is_host_comment = False
            for pattern in HOST_COMMENT_PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    is_host_comment = True
                    break

            # Don't convert clip intros
            is_clip_intro = False
            for pattern, _ in CLIP_PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    is_clip_intro = True
                    break

            if is_host_comment or is_clip_intro:
                result_lines.append(line)
                i += 1
                continue

            # Check if the header ITSELF contains first-person markers
            # This indicates Deutsch speaking, not a host question/transition
            is_first_person = False
            for pattern in FIRST_PERSON_PATTERNS:
                if re.search(pattern, header_text, re.IGNORECASE):
                    is_first_person = True
                    break

            if is_first_person:
                # This header is actually Deutsch speaking
                result_lines.append(f'**GUEST:** {header_text}')
                i += 1
                continue

            # Look ahead: if next non-empty line starts with **GUEST:** and looks like
            # a continuation (starts with "Now," or similar), this header is misplaced
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1

            if j < len(lines):
                next_line = lines[j]
                # Check if this looks like Deutsch continuing an answer
                continuation_patterns = [
                    r'^\*\*GUEST:\*\*\s*Now,',
                    r'^\*\*GUEST:\*\*\s*Yes[,.]',
                    r'^\*\*GUEST:\*\*\s*Okay[,.]',
                    r'^\*\*GUEST:\*\*\s*Well[,.]',
                    r'^\*\*GUEST:\*\*\s*First[,.]',
                    r'^\*\*GUEST:\*\*\s*The\s+',
                ]

                is_continuation = False
                for pattern in continuation_patterns:
                    if re.match(pattern, next_line):
                        is_continuation = True
                        break

                if is_continuation:
                    # This header is actually part of Deutsch's response
                    # Convert to regular text and prepend to the GUEST block
                    # Skip this header - it will be absorbed into context
                    # Actually, let's just convert it to a GUEST line
                    result_lines.append(f'**GUEST:** {header_text}')
                    i += 1
                    continue

        result_lines.append(line)
        i += 1

    return '\n'.join(result_lines)


def _fix_clip_headers(markdown: str) -> str:
    """Convert clip content to CLIP labels.

    When a header introduces a clip (mentions Carl Sagan, Stephen Hawking, etc.),
    subsequent content becomes CLIP labels until a termination signal:
    - ### header (host question/transition)
    - **CALLER:** line
    - Mention of "Deutsch" (back to interview)

    Handles both ### headers AND **GUEST:** lines as potential clip content.
    This prevents clip quotes from being attributed to the guest (Deutsch).
    """
    import re

    lines = markdown.split('\n')
    result_lines = []
    clip_speaker = None  # Current clip context speaker

    # Phrases that indicate a clip intro (host ABOUT TO play a clip)
    INTRO_PHRASES = [
        "here's", "here is", "let's hear", "here he", "here she",
        "listen to", "we'll hear", "speaks at", "speaking at",
        "warning about", "in the cosmos", "in the series",
    ]

    # Backward references - host referring to a PAST clip, not introducing one
    BACKWARD_PHRASES = [
        "we played", "played the clip", "the clip from", "that clip",
    ]

    for i, line in enumerate(lines):
        # === Handle ### headers ===
        if line.startswith('### '):
            header_text = line[4:].strip()
            header_lower = header_text.lower()

            # Check if this header mentions a clip speaker
            mentioned_speaker = None
            for pattern, speaker_name in CLIP_PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    mentioned_speaker = speaker_name
                    break

            if mentioned_speaker:
                # Check for backward references first - these are NOT intros
                is_backward_ref = any(phrase in header_lower for phrase in BACKWARD_PHRASES)

                if is_backward_ref:
                    clip_speaker = None
                    result_lines.append(line)
                    continue

                # Check if this is a clip INTRO
                is_intro = any(phrase in header_lower for phrase in INTRO_PHRASES)

                if is_intro:
                    # Start clip context
                    clip_speaker = mentioned_speaker
                    result_lines.append(line)
                    continue
                else:
                    # Just mentions speaker, not an intro - ends any clip context
                    clip_speaker = None
                    result_lines.append(line)
                    continue

            # If we're in clip context and this is a non-intro header
            if clip_speaker:
                # Questions end clip context (host asking something)
                if header_text.endswith('?'):
                    clip_speaker = None
                    result_lines.append(line)
                    continue

                # Mention of Deutsch ends clip context
                if 'deutsch' in header_lower:
                    clip_speaker = None
                    result_lines.append(line)
                    continue

                # Non-question header in clip context = clip content
                result_lines.append(f'**CLIP ({clip_speaker}):** {header_text}')
                # Don't reset clip_speaker yet - there might be more clip lines
                continue

            result_lines.append(line)
            continue

        # === Handle **GUEST:** lines ===
        guest_match = re.match(r'^\*\*GUEST:\*\*\s*(.*)$', line)
        if guest_match and clip_speaker:
            content = guest_match.group(1)
            content_lower = content.lower()

            # Check for termination signals in the content
            if 'deutsch' in content_lower:
                # This is probably back to Deutsch - end clip context
                clip_speaker = None
                result_lines.append(line)
                continue

            # Convert GUEST to CLIP
            result_lines.append(f'**CLIP ({clip_speaker}):** {content}')
            # Don't reset - there might be multiple clip lines
            continue

        # === Handle **CALLER:** lines - ends clip context ===
        if line.startswith('**CALLER'):
            clip_speaker = None
            result_lines.append(line)
            continue

        # === Handle other lines ===
        # Empty lines don't affect clip context
        if not line.strip():
            result_lines.append(line)
            continue

        # Any other non-empty, non-speaker line could be clip continuation
        # But we're conservative - only convert explicitly labeled lines
        result_lines.append(line)

    return '\n'.join(result_lines)


def _fix_host_interjections(markdown: str) -> str:
    """Convert GUEST interjections that are actually HOST to ### headers.

    The LLM sometimes mislabels host comments as GUEST. We use three tiers:
    - HARD patterns: Apply regardless of length (unambiguous HOST phrases)
    - STRONG patterns: Apply up to 40 words (specific phrasings)
    - WEAK patterns: Apply up to 15 words (general patterns)

    Additionally, we use look-ahead confirmation:
    - If a GUEST line is followed by another GUEST starting with an affirmation
      ("Yes,", "Exactly,", "That's right,"), the first line is likely HOST.
    """
    import re

    lines = markdown.split('\n')

    # Thresholds for different pattern strengths
    MAX_STRONG_WORDS = 40  # Strong patterns can be longer
    MAX_WEAK_WORDS = 15    # Weak patterns need word count restriction

    # === HARD PATTERNS (no length limit) ===
    # These phrases are almost exclusively HOST, regardless of length
    HARD_HOST_PATTERNS = [
        r'^Maybe\s+I\s+misunderstood',           # Host seeking clarification
        r'^I\'m\s+trying\s+to\s+get\s+my\s+mind\s+around',  # Host processing
        r'^Let\s+me\s+push\s+back',              # Host challenge
        r'^Our\s+listeners',                      # Host referencing audience
        r'^Let\'s\s+go\s+to',                    # Host transitioning to callers
        r'^Let\s+me\s+bring',                    # Host bringing in callers
        r'^It\'s\s+hard\s+to\s+grapple\s+with',  # Host expressing difficulty
        r'^I\s+didn\'t\s+think\s+simply\s+of',   # Host clarifying understanding
    ]

    # === AFFIRMATION PATTERNS for look-ahead ===
    # If next GUEST line starts with these, previous GUEST is likely HOST
    AFFIRMATION_PATTERNS = [
        r'^Yes[,.\s]',
        r'^Exactly[,.\s]',
        r'^That\'s\s+right',
        r'^Right[,.\s]',
        r'^Correct[,.\s]',
        r'^Certainly[,.\s]',
        r'^Absolutely[,.\s]',
        r'^Indeed[,.\s]',
    ]

    # === HOST-LIKE PATTERNS for look-ahead confirmation ===
    # These patterns, when followed by affirmation, confirm HOST
    HOST_LIKE_PATTERNS = [
        r'\bwhat\s+you\'re\s+(?:saying|describing|suggesting)\b',
        r'\byou\'re\s+(?:saying|describing|suggesting|talking\s+about)\b',
        r'\byou\s+seem\s+to\s+be\s+(?:saying|describing|suggesting)\b',
        r'\bif\s+I\s+understand\s+(?:you|correctly)\b',
        r'\bso\s+you\'re\s+saying\b',
        r'\bwhat\s+you\s+mean\b',
        r'\bwhat\s+would\s+(?:that|it)\s+mean\b',
        r'\bis\s+that\s+really\s+what\b',
    ]

    def is_guest_line(line: str) -> tuple[bool, str]:
        """Check if line is GUEST and return (is_guest, content)."""
        match = re.match(r'^\*\*GUEST:\*\*\s*(.*)$', line)
        if match:
            return True, match.group(1)
        return False, ""

    def find_next_guest_content(lines: list, start_idx: int) -> str | None:
        """Find the content of the next GUEST line after start_idx."""
        for j in range(start_idx + 1, len(lines)):
            is_guest, content = is_guest_line(lines[j])
            if is_guest:
                return content
            # Stop at headers or other speaker labels
            if lines[j].startswith('###') or lines[j].startswith('**CALLER') or lines[j].startswith('**CLIP'):
                return None
        return None

    def matches_any_pattern(text: str, patterns: list) -> bool:
        """Check if text matches any pattern in the list."""
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    # First pass: identify which lines should be converted to HOST
    convert_to_host = set()

    for i, line in enumerate(lines):
        is_guest, content = is_guest_line(line)
        if not is_guest:
            continue

        word_count = len(content.split())
        is_likely_host = False

        # === HARD PATTERNS (no length limit) ===
        if matches_any_pattern(content, HARD_HOST_PATTERNS):
            is_likely_host = True

        # === STRONG PATTERNS (up to 40 words) ===
        if not is_likely_host and word_count <= MAX_STRONG_WORDS:

            # Host transition to guest: "[Name], let us pick it up"
            if re.search(r',\s*let\s+us\s+pick\s+it\s+up', content, re.IGNORECASE):
                is_likely_host = True

            # Host transition: "[Name], let me put that to"
            elif re.search(r',\s*let\s+me\s+put\s+that\s+to', content, re.IGNORECASE):
                is_likely_host = True

            # Host pushback: "Well, so you say, but"
            elif re.match(r'^Well,?\s+so\s+you\s+say', content, re.IGNORECASE):
                is_likely_host = True

            # Questions are almost always host (up to 40 words)
            elif content.rstrip().endswith('?'):
                is_likely_host = True

            # Addressing guest by name with question/transition
            elif re.match(r'^(?:Professor|Mr\.?|Dr\.?)\s+Deutsch', content, re.IGNORECASE):
                is_likely_host = True
            elif re.match(r'^David\s+Deutsch,', content, re.IGNORECASE):
                is_likely_host = True

            # Host addressing caller: "[Name], standby" or "[Name], let me"
            elif re.match(r'^[A-Z][a-z]+,\s+(?:standby|let\s+me|let\s+us)', content):
                is_likely_host = True

        # === WEAK PATTERNS (up to 15 words only) ===
        if not is_likely_host and word_count <= MAX_WEAK_WORDS:

            # Very short pushback starting with "But" (under 10 words)
            if word_count < 10 and re.match(r'^But\s+', content):
                is_likely_host = True

            # "But the environment" pushback (up to 15 words)
            elif re.match(r'^But\s+the\s+environment', content, re.IGNORECASE):
                is_likely_host = True

            # "You mean X" clarification
            elif re.match(r'^You\s+mean\s+', content, re.IGNORECASE) and word_count < 10:
                is_likely_host = True

            # "If I may" / "If I understand"
            elif re.match(r'^If\s+I\s+(?:may|understand)', content, re.IGNORECASE):
                is_likely_host = True

        # === LOOK-AHEAD CONFIRMATION ===
        # If next GUEST starts with affirmation AND current has host-like patterns
        if not is_likely_host:
            next_guest = find_next_guest_content(lines, i)
            if next_guest and matches_any_pattern(next_guest, AFFIRMATION_PATTERNS):
                # Next response is an affirmation - check if current has host-like patterns
                if matches_any_pattern(content, HOST_LIKE_PATTERNS):
                    is_likely_host = True

        if is_likely_host:
            convert_to_host.add(i)

    # Second pass: build result with conversions
    result_lines = []
    for i, line in enumerate(lines):
        if i in convert_to_host:
            is_guest, content = is_guest_line(line)
            result_lines.append(f'### {content}')
        else:
            result_lines.append(line)

    return '\n'.join(result_lines)


# ==============================================================================
# Interview Candidate Scoring (Best-of-N selection)
# ==============================================================================

def score_interview_draft(
    markdown: str,
    transcript: str,
) -> dict:
    """Score an interview draft for quality selection.

    Used by best-of-N candidate selection to pick the highest quality draft.
    Higher score = better draft.

    Scoring components:
    - Richness: Q&A block count, quote count
    - Quality: Fewer QA violations (invalid quotes, truncation)

    Args:
        markdown: Generated interview draft markdown.
        transcript: Original transcript for validation.

    Returns:
        Dict with total score and component breakdown.
    """
    score = 0.0
    breakdown = {}

    # 1. Count Q&A blocks (#### headers followed by speaker response)
    qa_blocks = len(re.findall(r'^####\s+.+$', markdown, re.MULTILINE))
    breakdown["qa_blocks"] = qa_blocks
    # Award points for richness (diminishing returns after 8)
    qa_score = min(qa_blocks, 8) * 10  # Max 80 points
    score += qa_score
    breakdown["qa_score"] = qa_score

    # 2. Count quote blocks (> "..." lines)
    quote_blocks = len(re.findall(r'^>\s*"[^"]+"\s*$', markdown, re.MULTILINE))
    breakdown["quote_blocks"] = quote_blocks
    # Award points for quotes (1-2 per section is good, diminishing after)
    quote_score = min(quote_blocks, 6) * 5  # Max 30 points
    score += quote_score
    breakdown["quote_score"] = quote_score

    # 3. Count Key Ideas bullets with inline quotes
    key_ideas_section = _extract_key_ideas_section(markdown)
    key_idea_bullets = len(re.findall(r'^-\s+\*\*[^*]+\*\*:\s*"[^"]+"', key_ideas_section, re.MULTILINE))
    breakdown["key_idea_bullets"] = key_idea_bullets
    key_ideas_score = min(key_idea_bullets, 8) * 8  # Max 64 points
    score += key_ideas_score
    breakdown["key_ideas_score"] = key_ideas_score

    # 4. Penalize invalid quotes (not in transcript)
    quote_validation = verify_key_ideas_quotes(key_ideas_section, transcript)
    invalid_quote_count = len(quote_validation.get("invalid_quotes", []))
    breakdown["invalid_quotes"] = invalid_quote_count
    invalid_penalty = invalid_quote_count * -20  # Heavy penalty
    score += invalid_penalty
    breakdown["invalid_penalty"] = invalid_penalty

    # 5. Penalize truncated quotes
    truncated = check_truncated_quotes(key_ideas_section)
    truncated_count = len(truncated)
    breakdown["truncated_quotes"] = truncated_count
    truncated_penalty = truncated_count * -10
    score += truncated_penalty
    breakdown["truncated_penalty"] = truncated_penalty

    # 6. Penalize interview constraint violations (pass transcript to avoid false positives)
    violations = check_interview_constraints(markdown, transcript=transcript)
    violation_count = len(violations)
    breakdown["constraint_violations"] = violation_count
    violation_penalty = violation_count * -15
    score += violation_penalty
    breakdown["violation_penalty"] = violation_penalty

    breakdown["total"] = score
    return breakdown


async def _generate_and_score_candidate(
    transcript: str,
    book_title: str,
    evidence_map: dict,
    forced_candidates: Optional[list] = None,
    candidate_num: int = 1,
) -> tuple[str, dict]:
    """Generate a single interview draft candidate and score it.

    Args:
        transcript: Interview transcript.
        book_title: Sanitized book title.
        evidence_map: Evidence mapping for grounding.
        forced_candidates: Optional definitional candidates to force into Key Ideas.
        candidate_num: Candidate number for logging.

    Returns:
        Tuple of (markdown, score_breakdown).
    """
    markdown = await generate_interview_single_pass(
        transcript=transcript,
        book_title=book_title,
        evidence_map=evidence_map,
        forced_candidates=forced_candidates,
    )
    markdown = _clean_markdown_title(markdown)

    score = score_interview_draft(markdown, transcript)
    logger.info(
        f"Candidate {candidate_num}: score={score['total']:.0f} "
        f"(qa={score['qa_blocks']}, quotes={score['key_idea_bullets']}, "
        f"invalid={score['invalid_quotes']}, violations={score['constraint_violations']})"
    )

    return markdown, score


# ==============================================================================
# Public API
# ==============================================================================

async def start_generation(
    request: DraftGenerateRequest,
    project_id: Optional[str] = None,
) -> str:
    """Start draft generation and return job ID.

    Creates a job and starts background generation task.
    Returns immediately for async polling.

    Args:
        request: Generation request with transcript, outline, style config.
        project_id: Optional associated project ID.

    Returns:
        Job ID for status polling.
    """
    store = get_job_store()
    job_id = await store.create_job(project_id=project_id)

    logger.info(f"Starting draft generation job {job_id}")

    # Start background task
    asyncio.create_task(
        _generate_draft_task(job_id, request),
        name=f"draft_generation_{job_id}",
    )

    return job_id


async def get_job_status(job_id: str) -> Optional[DraftStatusData]:
    """Get current status of a generation job.

    Args:
        job_id: The job identifier.

    Returns:
        Status data if job found, None otherwise.
    """
    job = await get_job(job_id)
    if not job:
        return None

    # Determine what to return based on status
    is_active = job.status in (JobStatus.queued, JobStatus.planning, JobStatus.evidence_map, JobStatus.generating)
    is_completed = job.status == JobStatus.completed
    is_failed = job.status == JobStatus.failed
    is_partial = job.status in (JobStatus.cancelled, JobStatus.failed)
    has_chapters = bool(job.chapters_completed)

    # Build partial draft for progress updates or partial results
    partial_draft = None
    if (is_active or is_partial) and has_chapters:
        partial_draft = _assemble_partial_draft(job)

    # Build progress info
    progress = None
    if is_active or is_failed:
        # Active/failed: show current progress
        progress = job.get_progress()
    elif is_completed:
        # Completed: show finalized 100% progress
        progress = GenerationProgress(
            current_chapter=job.total_chapters,
            total_chapters=job.total_chapters,
            current_chapter_title=None,
            chapters_completed=job.total_chapters,
            estimated_remaining_seconds=0,
        )

    # Build Evidence Map summary (Spec 009)
    evidence_summary = None
    if job.evidence_map:
        from src.models.evidence_map import EvidenceMap
        try:
            emap = EvidenceMap.model_validate(job.evidence_map)
            evidence_summary = evidence_map_to_summary(emap)
        except Exception:
            # If validation fails, use raw data
            evidence_summary = {
                "total_claims": len(job.evidence_map.get("chapters", [])),
                "content_mode": job.evidence_map.get("content_mode", "interview"),
            }

    return DraftStatusData(
        job_id=job.job_id,
        status=job.status,
        progress=progress,
        draft_markdown=job.draft_markdown if is_completed else None,
        draft_plan=job.draft_plan if is_completed else None,
        visual_plan=job.visual_plan if is_completed else None,
        generation_stats=job.get_stats() if is_completed else None,
        partial_draft_markdown=partial_draft,
        chapters_available=len(job.chapters_completed) if has_chapters else None,
        error_code=job.error_code if is_failed else None,
        error_message=job.error if is_failed else None,
        # Spec 009: Evidence Map info
        evidence_map_summary=evidence_summary,
        constraint_warnings=job.constraint_warnings if job.constraint_warnings else None,
    )


async def cancel_job(job_id: str) -> Optional[DraftCancelData]:
    """Request cancellation of a generation job.

    Cancellation happens after the current chapter completes.

    Args:
        job_id: The job identifier.

    Returns:
        Cancel data if job found, None otherwise.
    """
    job = await get_job(job_id)
    if not job:
        return None

    if job.is_terminal():
        return DraftCancelData(
            job_id=job.job_id,
            status=job.status,
            cancelled=False,
            message=f"Job already in terminal state: {job.status.value}",
            partial_draft_markdown=job.draft_markdown,
            chapters_available=len(job.chapters_completed) if job.chapters_completed else None,
        )

    # Request cancellation
    await update_job(job_id, cancel_requested=True)

    return DraftCancelData(
        job_id=job.job_id,
        status=job.status,
        cancelled=True,
        message="Cancellation requested. Job will stop after current chapter.",
        partial_draft_markdown=None,
        chapters_available=len(job.chapters_completed) if job.chapters_completed else None,
    )


async def regenerate_section(
    section_outline_item_id: str,
    draft_plan: DraftPlan,
    existing_draft: str,
    style_config: dict,
) -> Optional[DraftRegenerateData]:
    """Regenerate a single section/chapter.

    Args:
        section_outline_item_id: Outline item ID to regenerate.
        draft_plan: The original DraftPlan.
        existing_draft: Current full draft markdown.
        style_config: Style configuration dict.

    Returns:
        Regenerate data with new section content.
    """
    # Find the chapter to regenerate
    chapter_plan = None
    chapter_index = -1
    for i, ch in enumerate(draft_plan.chapters):
        if ch.outline_item_id == section_outline_item_id:
            chapter_plan = ch
            chapter_index = i
            break

    if not chapter_plan:
        logger.warning(f"Section not found: {section_outline_item_id}")
        return None

    # Find section boundaries in existing draft
    start_line, end_line = _find_section_boundaries(
        existing_draft,
        chapter_plan.chapter_number,
        chapter_plan.title,
    )

    # Generate new content
    # Note: This would need the transcript to work properly
    # For now, return placeholder - full implementation in Phase 5
    new_section = f"## Chapter {chapter_plan.chapter_number}: {chapter_plan.title}\n\n[Regenerated content placeholder]"

    return DraftRegenerateData(
        section_markdown=new_section,
        section_start_line=start_line,
        section_end_line=end_line,
        generation_stats=None,
    )


# ==============================================================================
# Background Generation Task
# ==============================================================================

async def _generate_draft_task(
    job_id: str,
    request: DraftGenerateRequest,
) -> None:
    """Background task that performs the actual generation.

    Args:
        job_id: The job identifier.
        request: Generation request.
    """
    try:
        # Phase 1: Generate DraftPlan
        await update_job(job_id, status=JobStatus.planning)
        logger.info(f"Job {job_id}: Starting planning phase")

        draft_plan = await generate_draft_plan(
            transcript=request.transcript,
            outline=request.outline,
            style_config=request.style_config,
            resources=request.resources,
        )

        job = await get_job(job_id)
        if not job:
            return

        await update_job(
            job_id,
            draft_plan=draft_plan,
            visual_plan=draft_plan.visual_plan,
            total_chapters=len(draft_plan.chapters),
        )

        # Check for cancellation
        if job.cancel_requested:
            await update_job(job_id, status=JobStatus.cancelled)
            logger.info(f"Job {job_id}: Cancelled during planning")
            return

        # Phase 2: Generate Evidence Map (Spec 009)
        await update_job(job_id, status=JobStatus.evidence_map)
        logger.info(f"Job {job_id}: Starting evidence map generation")

        # Extract content mode from style config
        style_dict = request.style_config.get("style", request.style_config) if isinstance(request.style_config, dict) else {}
        content_mode_str = style_dict.get("content_mode", "interview")
        try:
            content_mode = ContentMode(content_mode_str)
        except ValueError:
            content_mode = ContentMode.interview
        strict_grounded = style_dict.get("strict_grounded", True)

        # Detect content type and generate warning if mismatch
        constraint_warnings: list[str] = []
        detected_mode, confidence = detect_content_type(request.transcript)
        mode_warning = generate_mode_warning(detected_mode, content_mode, confidence)
        if mode_warning:
            constraint_warnings.append(mode_warning)
            logger.warning(f"Job {job_id}: {mode_warning}")

        # Generate Evidence Map
        evidence_map = await generate_evidence_map(
            project_id=job.project_id or job_id,
            transcript=request.transcript,
            chapters=draft_plan.chapters,
            content_mode=content_mode,
            strict_grounded=strict_grounded,
            style_config=style_dict,
        )

        await update_job(
            job_id,
            evidence_map=evidence_map.model_dump(mode="json"),
            content_mode=content_mode,
            constraint_warnings=constraint_warnings,
        )

        logger.info(
            f"Job {job_id}: Evidence Map complete - "
            f"{sum(len(ch.claims) for ch in evidence_map.chapters)} claims across {len(evidence_map.chapters)} chapters"
        )

        # Build quote whitelist for Ideas Edition
        whitelist: list[WhitelistQuote] = []
        if content_mode == ContentMode.essay and evidence_map:
            try:
                transcript_pair = TranscriptPair(
                    raw=request.transcript,
                    canonical=canonicalize_transcript(request.transcript),
                )
                whitelist = build_quote_whitelist(
                    evidence_map=evidence_map,
                    transcript=transcript_pair,
                    known_guests=[],  # TODO: Get from project settings
                    known_hosts=[],
                )
                logger.info(
                    f"Job {job_id}: Built whitelist with {len(whitelist)} validated quotes"
                )

                # Generate coverage report and check for weak chapters
                try:
                    from hashlib import sha256
                    transcript_hash = sha256(transcript_pair.canonical.encode()).hexdigest()[:32]
                    coverage_report = generate_coverage_report(
                        whitelist=whitelist,
                        chapter_count=len(evidence_map.chapters),
                        transcript_hash=transcript_hash,
                    )

                    # Log coverage summary
                    logger.info(
                        f"Job {job_id}: Coverage report - "
                        f"feasible={coverage_report.is_feasible}, "
                        f"predicted_words={coverage_report.predicted_total_range}"
                    )

                    # Check for chapters that need merging
                    merge_suggestions = suggest_chapter_merges(coverage_report.chapters)
                    if merge_suggestions:
                        for suggestion in merge_suggestions:
                            if suggestion.get("action") == "abort":
                                logger.warning(
                                    f"Job {job_id}: MERGE SUGGESTION - {suggestion['reason']}"
                                )
                            else:
                                logger.warning(
                                    f"Job {job_id}: MERGE SUGGESTION - Chapter {suggestion['weak_chapter'] + 1} "
                                    f"should merge into Chapter {suggestion['merge_into'] + 1}. "
                                    f"Reason: {suggestion['reason']}"
                                )
                        logger.warning(
                            f"Job {job_id}: {len(merge_suggestions)} chapter(s) have insufficient evidence. "
                            f"Consider reducing chapter count or adding more source material."
                        )

                    # PREFLIGHT GATE: If require_preflight_pass is True and coverage is not feasible, fail
                    if request.require_preflight_pass and not coverage_report.is_feasible:
                        error_msg = (
                            f"Preflight coverage check failed. "
                            f"Reasons: {'; '.join(coverage_report.feasibility_notes)}. "
                            f"Set require_preflight_pass=False to generate anyway with warnings."
                        )
                        logger.error(f"Job {job_id}: PREFLIGHT GATE BLOCKED - {error_msg}")
                        await update_job(
                            job_id,
                            status=JobStatus.failed,
                            error_message=error_msg,
                        )
                        return

                except Exception as e:
                    logger.warning(f"Job {job_id}: Coverage analysis failed (non-fatal): {e}")

            except Exception as e:
                logger.error(f"Job {job_id}: Whitelist build failed (non-fatal): {e}", exc_info=True)

        # Check for cancellation
        job = await get_job(job_id)
        if job and job.cancel_requested:
            await update_job(job_id, status=JobStatus.cancelled)
            logger.info(f"Job {job_id}: Cancelled during evidence map generation")
            return

        # Phase 3: Generate content
        await update_job(job_id, status=JobStatus.generating)

        # Compute words per chapter based on style config and chapter count
        style_dict = request.style_config.get("style", request.style_config) if isinstance(request.style_config, dict) else {}
        total_length_preset_str = style_dict.get("total_length_preset", "standard")
        try:
            total_length_preset = TotalLengthPreset(total_length_preset_str)
        except ValueError:
            total_length_preset = TotalLengthPreset.standard
        # Get custom word count if preset is 'custom'
        custom_total_words = style_dict.get("total_target_words")
        words_per_chapter = compute_words_per_chapter(
            total_length_preset,
            len(draft_plan.chapters),
            custom_total_words,
        )
        detail_level_str = style_dict.get("detail_level", "balanced")
        book_format = style_dict.get("book_format", "guide")

        # P0: Use single-pass generation for interview mode with evidence
        # Triggers when: content_mode=interview OR book_format=interview_qa
        # Both should produce Key Ideas + Conversation structure
        use_interview_single_pass = (
            (content_mode == ContentMode.interview or book_format == "interview_qa")
            and evidence_map
            and sum(len(ch.claims) for ch in evidence_map.chapters) > 0
        )

        if use_interview_single_pass:
            # Single-pass interview generation (P0: Key Ideas + Conversation)
            logger.info(f"Job {job_id}: Using single-pass interview generation")
            await update_job(job_id, current_chapter=1, total_chapters=1)

            # Title guardrail: prevent generic titles like "Interview"
            interview_book_title = sanitize_interview_title(
                draft_plan.book_title,
                fallback=request.project_name if hasattr(request, "project_name") else None,
                transcript=request.transcript,
            )

            # Extract definitional candidates BEFORE generation for coverage check
            definitional_candidates = extract_definitional_candidates(request.transcript)
            if definitional_candidates:
                logger.info(f"Job {job_id}: Found {len(definitional_candidates)} definitional candidates")

            # Determine forced candidates based on coverage requirements
            forced_candidates_for_generation = None

            # Best-of-N candidate selection
            # Use request param, capped by server-side max
            candidate_count = min(request.candidate_count, INTERVIEW_CANDIDATE_COUNT_MAX)
            runner_up_data = None  # Store runner-up for debugging

            if candidate_count > 1:
                logger.info(f"Job {job_id}: Generating {candidate_count} candidates for best-of-N selection")

                candidates = []
                for i in range(candidate_count):
                    markdown, score = await _generate_and_score_candidate(
                        transcript=request.transcript,
                        book_title=interview_book_title,
                        evidence_map=evidence_map,
                        forced_candidates=forced_candidates_for_generation,
                        candidate_num=i + 1,
                    )
                    candidates.append((markdown, score))

                # Sort by score (highest first)
                candidates.sort(key=lambda x: x[1]["total"], reverse=True)

                # Pick the best
                final_markdown, best_score = candidates[0]
                logger.info(
                    f"Job {job_id}: Selected candidate 1 with score {best_score['total']:.0f}"
                )

                # Store runner-up for debugging (if we have more than one)
                if len(candidates) > 1:
                    runner_up_markdown, runner_up_score = candidates[1]
                    runner_up_data = {
                        "score": runner_up_score,
                        "markdown_preview": runner_up_markdown[:500] + "..." if len(runner_up_markdown) > 500 else runner_up_markdown,
                    }
                    logger.info(
                        f"Job {job_id}: Runner-up score: {runner_up_score['total']:.0f} "
                        f"(diff: {best_score['total'] - runner_up_score['total']:.0f})"
                    )

            else:
                # Single candidate (default behavior)
                final_markdown = await generate_interview_single_pass(
                    transcript=request.transcript,
                    book_title=interview_book_title,
                    evidence_map=evidence_map,
                )
                # Clean up any trailing punctuation in H1 title
                final_markdown = _clean_markdown_title(final_markdown)

            # Key Ideas Coverage Guard: Check if core framework is surfaced
            if definitional_candidates:
                key_ideas_text = _extract_key_ideas_section(final_markdown)
                coverage = check_key_ideas_coverage(key_ideas_text, definitional_candidates)

                if not coverage["covered"]:
                    logger.warning(
                        f"Job {job_id}: Key Ideas missing definitional coverage, re-running with forced candidates"
                    )
                    # Re-run with forced candidates (single pass, not best-of-N)
                    final_markdown = await generate_interview_single_pass(
                        transcript=request.transcript,
                        book_title=interview_book_title,
                        evidence_map=evidence_map,
                        forced_candidates=coverage["missing_candidates"],
                    )
                    # Clean up any trailing punctuation in H1 title
                    final_markdown = _clean_markdown_title(final_markdown)
                    constraint_warnings.append(
                        "Key Ideas re-generated to include core framework definitions"
                    )
                else:
                    logger.info(
                        f"Job {job_id}: Key Ideas coverage check passed "
                        f"(matched: {coverage['matched_candidate']['keyword'] if coverage['matched_candidate'] else 'N/A'})"
                    )

            # Fix title format: "# The Enlightenment" -> "# David Deutsch on *The Beginning of Infinity*"
            final_markdown = _fix_interview_title(final_markdown, request.transcript)

            # Post-process for structure polish (heading hierarchy, metadata, Thank you)
            # Note: source_url could come from project metadata in future
            final_markdown = postprocess_interview_markdown(final_markdown, source_url=None)

            # Quote validation checks
            key_ideas_text = _extract_key_ideas_section(final_markdown)

            # Check for fabricated quotes (not in transcript)
            quote_validation = verify_key_ideas_quotes(key_ideas_text, request.transcript)
            if not quote_validation["valid"]:
                logger.warning(
                    f"Job {job_id}: {len(quote_validation['invalid_quotes'])} potentially invalid quotes in Key Ideas"
                )
                for invalid in quote_validation["invalid_quotes"][:3]:
                    constraint_warnings.append(
                        f"Quote issue: {invalid['reason'][:50]}"
                    )

            # Check for truncated quotes
            truncated = check_truncated_quotes(key_ideas_text)
            if truncated:
                logger.warning(f"Job {job_id}: {len(truncated)} truncated quotes in Key Ideas")
                for issue in truncated[:2]:
                    constraint_warnings.append(
                        f"Truncated quote: ...{issue['quote'][-30:]}"
                    )

            # Check for interview mode violations (pass transcript to avoid false positives)
            violations = check_interview_constraints(final_markdown, transcript=request.transcript)
            if violations:
                logger.warning(f"Job {job_id}: {len(violations)} interview mode violations in output")
                constraint_warnings.extend([
                    f"{v['matched_text'][:50]}..." for v in violations[:5]
                ])

            # Update job with any constraint warnings
            if constraint_warnings:
                await update_job(job_id, constraint_warnings=constraint_warnings)

            chapters_completed = [final_markdown]

        else:
            # Standard chapter-by-chapter generation
            logger.info(f"Job {job_id}: Starting chapter generation ({len(draft_plan.chapters)} chapters)")
            logger.info(f"Job {job_id}: Target ~{words_per_chapter} words/chapter, detail_level={detail_level_str}")

            chapters_completed: list[str] = []

            for i, chapter_plan in enumerate(draft_plan.chapters):
                # Check for cancellation between chapters
                job = await get_job(job_id)
                if job and job.cancel_requested:
                    await update_job(
                        job_id,
                        status=JobStatus.cancelled,
                        chapters_completed=chapters_completed,
                    )
                    logger.info(f"Job {job_id}: Cancelled after chapter {i}")
                    return

                await update_job(job_id, current_chapter=i + 1)
                logger.debug(f"Job {job_id}: Generating chapter {i + 1}/{len(draft_plan.chapters)}")

                # Get chapter evidence from Evidence Map
                chapter_evidence = get_evidence_for_chapter(evidence_map, chapter_plan.chapter_number)

                chapter_md = await generate_chapter(
                    chapter_plan=chapter_plan,
                    transcript=request.transcript,
                    book_title=draft_plan.book_title,
                    style_config=request.style_config,
                    chapters_completed=chapters_completed,
                    all_chapters=draft_plan.chapters,
                    words_per_chapter_target=words_per_chapter,
                    detail_level=detail_level_str,
                    # Spec 009: Evidence-grounded generation
                    chapter_evidence=chapter_evidence,
                    content_mode=content_mode,
                    strict_grounded=strict_grounded,
                )

                # Check for interview mode violations (Spec 009 US2)
                if content_mode == ContentMode.interview:
                    violations = check_interview_constraints(chapter_md, transcript=request.transcript)
                    if violations:
                        logger.warning(
                            f"Job {job_id}: Chapter {chapter_plan.chapter_number} has "
                            f"{len(violations)} interview mode violations"
                        )
                        # Add to warnings but don't fail
                        constraint_warnings.extend([
                            f"Ch{chapter_plan.chapter_number}: {v['matched_text'][:50]}..."
                            for v in violations[:3]
                        ])
                        await update_job(job_id, constraint_warnings=constraint_warnings)

                chapters_completed.append(chapter_md)
                await update_job(job_id, chapters_completed=chapters_completed)

            # Assemble final draft for chapter-by-chapter mode
            final_markdown = assemble_chapters(
                book_title=draft_plan.book_title,
                chapters=chapters_completed,
            )

            # Apply enforcement for essay format on final assembled draft
            if book_format == "essay":
                final_markdown, enforcement_report = enforce_prose_quality(final_markdown, book_format)
                if enforcement_report["sections_removed"]:
                    logger.info(
                        f"Job {job_id}: Final draft enforcement removed sections: "
                        f"{enforcement_report['sections_removed']}"
                    )
                if enforcement_report["banned_phrase_counts"]:
                    logger.info(
                        f"Job {job_id}: Final draft has {sum(enforcement_report['banned_phrase_counts'].values())} "
                        f"banned phrase instances"
                    )

        # Whitelist-based enforcement (Ideas Edition only)
        # When whitelist is available, use it for deterministic quote validation
        if content_mode == ContentMode.essay and whitelist:
            try:
                # Step 1: Strip LLM-generated blockquotes outside Key Excerpts section
                final_markdown = strip_llm_blockquotes(final_markdown)
                logger.debug(f"Job {job_id}: Stripped LLM blockquotes outside Key Excerpts")

                # Step 1.5: Inject excerpts into empty Key Excerpts sections
                # This ensures each chapter has valid excerpts even if LLM generation failed
                if evidence_map:
                    try:
                        logger.info(f"Job {job_id}: Calling inject_excerpts_into_empty_sections")
                        final_markdown = inject_excerpts_into_empty_sections(
                            final_markdown, whitelist, evidence_map
                        )
                        logger.info(f"Job {job_id}: Finished inject_excerpts_into_empty_sections")
                    except Exception as e:
                        logger.warning(f"Job {job_id}: Excerpt injection failed (non-fatal): {e}")

                # Step 2: Enforce whitelist on remaining quotes (Core Claims, inline)
                # Process each chapter separately to match quotes against the correct chapter's whitelist entries
                chapter_pattern = re.compile(r'^## Chapter (\d+)', re.MULTILINE)
                chapter_matches = list(chapter_pattern.finditer(final_markdown))

                total_dropped = []
                total_replaced = []

                if chapter_matches:
                    # Process chapters in reverse order to maintain string positions
                    for i in range(len(chapter_matches) - 1, -1, -1):
                        chapter_match = chapter_matches[i]
                        chapter_num = int(chapter_match.group(1))
                        chapter_idx = chapter_num - 1  # 0-based

                        chapter_start = chapter_match.start()
                        chapter_end = chapter_matches[i + 1].start() if i + 1 < len(chapter_matches) else len(final_markdown)
                        chapter_text = final_markdown[chapter_start:chapter_end]

                        # Enforce whitelist for this chapter
                        enforcement_result = enforce_quote_whitelist(
                            generated_text=chapter_text,
                            whitelist=whitelist,
                            chapter_index=chapter_idx,
                        )

                        # Replace chapter text with enforced version
                        final_markdown = final_markdown[:chapter_start] + enforcement_result.text + final_markdown[chapter_end:]

                        total_dropped.extend(enforcement_result.dropped)
                        total_replaced.extend(enforcement_result.replaced)
                else:
                    # Fallback: no chapter structure found, enforce globally with chapter_index=0
                    enforcement_result = enforce_quote_whitelist(
                        generated_text=final_markdown,
                        whitelist=whitelist,
                        chapter_index=0,
                    )
                    final_markdown = enforcement_result.text
                    total_dropped = enforcement_result.dropped
                    total_replaced = enforcement_result.replaced

                if total_dropped:
                    logger.info(
                        f"Job {job_id}: Whitelist enforcement - dropped {len(total_dropped)} invalid quotes"
                    )
                    for dropped in total_dropped[:3]:
                        constraint_warnings.append(f"Quote dropped: \"{dropped[:40]}...\"")

                if total_replaced:
                    logger.info(
                        f"Job {job_id}: Whitelist enforcement - replaced {len(total_replaced)} quotes with exact text"
                    )

                await update_job(job_id, constraint_warnings=constraint_warnings)

                # Step 2.5: Enforce Core Claims stricter rules (full-span match, min length)
                # Core Claims require GUEST-only quotes with exact whitelist match
                try:
                    total_claims_dropped = []
                    total_claims_kept = 0

                    if chapter_matches:
                        # Process per chapter
                        for i in range(len(chapter_matches) - 1, -1, -1):
                            chapter_match = chapter_matches[i]
                            chapter_num = int(chapter_match.group(1))
                            chapter_idx = chapter_num - 1

                            chapter_start = chapter_match.start()
                            chapter_end = chapter_matches[i + 1].start() if i + 1 < len(chapter_matches) else len(final_markdown)
                            chapter_text = final_markdown[chapter_start:chapter_end]

                            # Apply Core Claims enforcement
                            enforced_chapter, claims_report = enforce_core_claims_text(
                                chapter_text, whitelist, chapter_idx
                            )

                            final_markdown = final_markdown[:chapter_start] + enforced_chapter + final_markdown[chapter_end:]
                            total_claims_dropped.extend(claims_report.get("dropped", []))
                            total_claims_kept += claims_report.get("kept", 0)
                    else:
                        # Single chapter
                        final_markdown, claims_report = enforce_core_claims_text(
                            final_markdown, whitelist, 0
                        )
                        total_claims_dropped = claims_report.get("dropped", [])
                        total_claims_kept = claims_report.get("kept", 0)

                    if total_claims_dropped:
                        logger.info(
                            f"Job {job_id}: Core Claims enforcement - dropped {len(total_claims_dropped)}, kept {total_claims_kept}"
                        )
                        for claim in total_claims_dropped[:3]:
                            constraint_warnings.append(
                                f"Core Claim dropped ({claim['reason']}): \"{claim['claim'][:30]}...\""
                            )
                        await update_job(job_id, constraint_warnings=constraint_warnings)
                except Exception as e:
                    logger.warning(f"Job {job_id}: Core Claims enforcement failed (non-fatal): {e}")

                # Step 3: Detect and REMOVE verbatim leakage (unquoted whitelist text in prose)
                # Transcript-exact text in prose without quotation marks = leak
                try:
                    final_markdown, leak_report = detect_verbatim_leaks(
                        final_markdown, whitelist, min_leak_words=6
                    )
                    leak_count = leak_report.get("leaks_found", 0)
                    if leak_count > 0:
                        logger.warning(
                            f"Job {job_id}: Verbatim leakage removed - {leak_count} unquoted whitelist fragments from prose"
                        )
                        for leak in leak_report.get("leaks_removed", [])[:3]:
                            constraint_warnings.append(f"Verbatim leak removed: \"{leak['text'][:40]}...\"")
                        await update_job(job_id, constraint_warnings=constraint_warnings)
                except Exception as e:
                    logger.warning(f"Job {job_id}: Verbatim leakage removal failed (non-fatal): {e}")

                # Step 4: Remove inline quotes from prose (Ideas Edition)
                # Quotes are only allowed in Key Excerpts and Core Claims
                try:
                    final_markdown, inline_report = remove_inline_quotes(final_markdown)
                    if inline_report["removed_count"] > 0:
                        logger.info(
                            f"Job {job_id}: Removed {inline_report['removed_count']} inline quotes from prose"
                        )
                        for removed in inline_report["removed_quotes"][:3]:
                            constraint_warnings.append(f"Inline quote removed: \"{removed['text'][:40]}...\"")
                        await update_job(job_id, constraint_warnings=constraint_warnings)
                except Exception as e:
                    logger.warning(f"Job {job_id}: Inline quote removal failed (non-fatal): {e}")

                # Step 5: Normalize speaker attributions to canonical form
                # Ensures "David" becomes "David Deutsch (GUEST)", etc.
                try:
                    speaker_registry = build_speaker_registry(whitelist)
                    final_markdown, speaker_report = normalize_speaker_names(
                        final_markdown, speaker_registry
                    )
                    norm_count = speaker_report.get("normalized_count", 0)
                    if norm_count > 0:
                        logger.info(
                            f"Job {job_id}: Normalized {norm_count} speaker attributions to canonical form"
                        )
                        for norm in speaker_report.get("normalizations", [])[:3]:
                            constraint_warnings.append(
                                f"Speaker normalized: '{norm['original']}' → '{norm['canonical']}'"
                            )
                        await update_job(job_id, constraint_warnings=constraint_warnings)
                except Exception as e:
                    logger.warning(f"Job {job_id}: Speaker name normalization failed (non-fatal): {e}")

            except Exception as e:
                logger.error(f"Job {job_id}: Whitelist enforcement failed (non-fatal): {e}", exc_info=True)

        # Keep the old hard gates as fallback when whitelist is empty
        elif content_mode == ContentMode.essay:
            # Core Claims hard gate (Ideas Edition only)
            # Drop entire Core Claim bullets if their supporting quotes fail validation
            # This must run BEFORE general quote grounding so quotes are still in place
            try:
                final_markdown, claims_report = drop_claims_with_invalid_quotes(
                    final_markdown,
                    request.transcript,
                )
                if claims_report["dropped_count"] > 0:
                    logger.info(
                        f"Job {job_id}: Core Claims hard gate - dropped "
                        f"{claims_report['dropped_count']} claims with invalid quotes"
                    )
                    # Add to constraint warnings
                    for dropped in claims_report["dropped_claims"][:3]:
                        constraint_warnings.append(
                            f"Core Claim dropped ({dropped['reason']}): \"{dropped['quote'][:30]}...\""
                        )
                    await update_job(job_id, constraint_warnings=constraint_warnings)
            except Exception as e:
                logger.error(f"Job {job_id}: Core Claims hard gate failed (non-fatal): {e}", exc_info=True)

            # Key Excerpts hard gate (Ideas Edition only)
            # Drop entire excerpt blocks if their quotes fail validation or have Unknown attribution
            # This must run BEFORE general quote grounding so quotes are still in place
            try:
                final_markdown, excerpts_report = drop_excerpts_with_invalid_quotes(
                    final_markdown,
                    request.transcript,
                )
                if excerpts_report["dropped_count"] > 0:
                    logger.info(
                        f"Job {job_id}: Key Excerpts hard gate - dropped "
                        f"{excerpts_report['dropped_count']} excerpts with invalid quotes"
                    )
                    # Add to constraint warnings
                    for dropped in excerpts_report["dropped_excerpts"][:3]:
                        reason = dropped.get('reason', 'invalid')
                        preview = dropped.get('quote', dropped.get('excerpt_preview', ''))[:30]
                        constraint_warnings.append(
                            f"Key Excerpt dropped ({reason}): \"{preview}...\""
                        )
                    await update_job(job_id, constraint_warnings=constraint_warnings)
            except Exception as e:
                logger.error(f"Job {job_id}: Key Excerpts hard gate failed (non-fatal): {e}", exc_info=True)

        # Quote grounding enforcement (applies to all modes)
        # Validates quotes against transcript, converts invalid quotes to paraphrases
        try:
            final_markdown, quote_report = enforce_quote_grounding(
                final_markdown,
                request.transcript,
                convert_invalid=True,
            )
            if quote_report["invalid_quotes"]:
                logger.info(
                    f"Job {job_id}: Quote grounding - {quote_report['summary']['invalid']} invalid quotes "
                    f"({quote_report['summary']['ellipsis_violations']} ellipsis, "
                    f"{quote_report['summary']['fabricated']} fabricated)"
                )
                # Add to constraint warnings
                for invalid in quote_report["invalid_quotes"][:5]:
                    quote_preview = invalid.get('quote', '')[:40]
                    constraint_warnings.append(
                        f"Invalid quote ({invalid['reason']}): \"{quote_preview}...\""
                    )
                await update_job(job_id, constraint_warnings=constraint_warnings)
        except Exception as e:
            logger.error(f"Job {job_id}: Quote grounding failed (non-fatal): {e}", exc_info=True)
            # Continue without quote grounding - don't fail the whole generation

        # Fix unquoted excerpts (Ideas Edition) - wrap block quotes and Core Claims in quotation marks
        # This must run BEFORE validation so the newly-quoted content gets validated
        if content_mode == ContentMode.essay:
            try:
                final_markdown, excerpt_fix_report = fix_unquoted_excerpts(final_markdown)
                if excerpt_fix_report["fixes_made"] > 0:
                    logger.info(
                        f"Job {job_id}: Fixed {excerpt_fix_report['fixes_made']} unquoted excerpts/claims"
                    )
            except Exception as e:
                logger.error(f"Job {job_id}: Unquoted excerpt fix failed (non-fatal): {e}", exc_info=True)

        # Global ellipsis ban (Step B) - remove sentences containing ellipses
        # Ellipses indicate truncation/approximation which is unacceptable for grounded content
        try:
            final_markdown, ellipsis_report = enforce_ellipsis_ban(
                final_markdown,
                remove_sentences=True,
            )
            if ellipsis_report["ellipses_found"]:
                logger.info(
                    f"Job {job_id}: Ellipsis ban - removed {len(ellipsis_report['removed_sentences'])} "
                    f"sentences containing ellipses"
                )
                # Add to constraint warnings
                for location in ellipsis_report["ellipsis_locations"][:3]:
                    constraint_warnings.append(
                        f"Ellipsis removed: \"{location['context'][:50]}...\""
                    )
                await update_job(job_id, constraint_warnings=constraint_warnings)
        except Exception as e:
            logger.error(f"Job {job_id}: Ellipsis ban failed (non-fatal): {e}", exc_info=True)

        # Attributed-speech enforcement (Step A) - validate "Deutsch argues, X" patterns
        # These pseudo-quotes bypass quote validation and may contain fabricated content
        try:
            final_markdown, attribution_report = enforce_attributed_speech(
                final_markdown,
                request.transcript,
                remediate_invalid=True,  # Ignored - always hard enforcement now
            )
            if attribution_report.get("invalid_deleted", 0) > 0:
                logger.info(
                    f"Job {job_id}: Attribution enforcement (HARD) - deleted "
                    f"{attribution_report['invalid_deleted']} invalid attributions, "
                    f"wrapped {attribution_report.get('valid_converted', 0)} valid ones"
                )
                # Add to constraint warnings
                for detail in attribution_report.get("invalid_details", [])[:3]:
                    constraint_warnings.append(
                        f"Invalid attribution deleted ({detail['speaker']}): \"{detail['content'][:40]}...\""
                    )
                await update_job(job_id, constraint_warnings=constraint_warnings)
        except Exception as e:
            logger.error(f"Job {job_id}: Attribution enforcement failed (non-fatal): {e}", exc_info=True)

        # Fix Truncated Attributions (Ideas Edition only)
        # Fixes "Deutsch notes," at end of line followed by content in next paragraph
        if content_mode == ContentMode.essay:
            try:
                final_markdown, truncated_report = fix_truncated_attributions(final_markdown)
                if truncated_report["fixes_applied"] > 0:
                    logger.info(
                        f"Job {job_id}: Fixed {truncated_report['fixes_applied']} truncated attributions"
                    )
                    for detail in truncated_report.get("fix_details", [])[:3]:
                        constraint_warnings.append(
                            f"Truncated attribution fixed: \"{detail['original_line'][:30]}...\""
                        )
                    await update_job(job_id, constraint_warnings=constraint_warnings)
            except Exception as e:
                logger.error(f"Job {job_id}: Truncated attribution fix failed (non-fatal): {e}", exc_info=True)

        # Dangling Attribution Gate (Ideas Edition only)
        # Rewrites "Deutsch notes, For ages..." to "Deutsch notes that for ages..."
        if content_mode == ContentMode.essay:
            try:
                final_markdown, dangling_report = enforce_dangling_attribution_gate(final_markdown)
                if dangling_report["rewrites_applied"] > 0:
                    logger.info(
                        f"Job {job_id}: Dangling attribution gate - rewrote "
                        f"{dangling_report['rewrites_applied']} patterns to indirect speech"
                    )
                    for detail in dangling_report.get("rewrite_details", [])[:3]:
                        constraint_warnings.append(
                            f"Dangling attribution rewritten: \"{detail['original']}\" → indirect speech"
                        )
                    await update_job(job_id, constraint_warnings=constraint_warnings)
            except Exception as e:
                logger.error(f"Job {job_id}: Dangling attribution gate failed (non-fatal): {e}", exc_info=True)

        # Speaker-Framing Sanitizer (Ideas Edition only)
        # Rewrites "Deutsch argues that..." → clause content, strips attribution wrappers
        if content_mode == ContentMode.essay:
            try:
                final_markdown, sanitizer_report = sanitize_speaker_framing(final_markdown)
                if sanitizer_report["rewrites_applied"] > 0:
                    logger.info(
                        f"Job {job_id}: Speaker-framing sanitizer - rewrote "
                        f"{sanitizer_report['rewrites_applied']} patterns"
                    )
                    for detail in sanitizer_report.get("rewrite_details", [])[:3]:
                        constraint_warnings.append(
                            f"Speaker framing sanitized ({detail['type']}): starts with '{detail['replacement_start']}'"
                        )
                    await update_job(job_id, constraint_warnings=constraint_warnings)
            except Exception as e:
                logger.error(f"Job {job_id}: Speaker-framing sanitizer failed (non-fatal): {e}", exc_info=True)

        # Speaker-Framing Invariant (Ideas Edition only)
        # Hard invariant: any remaining speaker framing after sanitizer is dropped
        if content_mode == ContentMode.essay:
            try:
                final_markdown, invariant_report = enforce_speaker_framing_invariant(final_markdown)
                if invariant_report["speaker_framing_sentences_dropped"] > 0:
                    logger.info(
                        f"Job {job_id}: Speaker-framing invariant - dropped "
                        f"{invariant_report['speaker_framing_sentences_dropped']} sentences"
                    )
                    for detail in invariant_report.get("drop_details", [])[:3]:
                        constraint_warnings.append(
                            f"Speaker framing dropped: \"{detail['dropped_sentence'][:40]}...\""
                        )
                    await update_job(job_id, constraint_warnings=constraint_warnings)
            except Exception as e:
                logger.error(f"Job {job_id}: Speaker-framing invariant failed (non-fatal): {e}", exc_info=True)

        # Meta-Discourse Gate (Ideas Edition only)
        # Drops sentences that describe the document itself (template/prompt leakage)
        # E.g., "This chapter develops the theme...", "The excerpts preserve..."
        # Must run BEFORE orphan-pronoun repair so we can fix any new orphans created
        if content_mode == ContentMode.essay:
            try:
                final_markdown, meta_report = sanitize_meta_discourse(final_markdown)
                if meta_report["sentences_dropped"] > 0:
                    logger.info(
                        f"Job {job_id}: Meta-discourse gate - dropped "
                        f"{meta_report['sentences_dropped']} sentences"
                    )
                    for detail in meta_report.get("drop_details", [])[:3]:
                        constraint_warnings.append(
                            f"Meta-discourse dropped: \"{detail['dropped_sentence'][:40]}...\""
                        )
                    await update_job(job_id, constraint_warnings=constraint_warnings)
            except Exception as e:
                logger.error(f"Job {job_id}: Meta-discourse gate failed (non-fatal): {e}", exc_info=True)

        # Dangling Connective Cleanup (Ideas Edition only)
        # Fixes orphaned articles/connectives: "offers a ." → next sentence, ", suggesting that ." → "."
        if content_mode == ContentMode.essay:
            try:
                final_markdown, connective_report = cleanup_dangling_connectives(final_markdown)
                if connective_report["cleanups_applied"] > 0:
                    logger.info(
                        f"Job {job_id}: Dangling connective cleanup - fixed "
                        f"{connective_report['cleanups_applied']} orphaned connectives"
                    )
                    for detail in connective_report.get("cleanup_details", [])[:3]:
                        constraint_warnings.append(
                            f"Dangling connective cleaned: {detail['type']}"
                        )
                    await update_job(job_id, constraint_warnings=constraint_warnings)
            except Exception as e:
                logger.error(f"Job {job_id}: Dangling connective cleanup failed (non-fatal): {e}", exc_info=True)

        # Remove Discourse Markers (Ideas Edition only)
        # Removes "Okay,", "In fact,", "Yes." from prose
        if content_mode == ContentMode.essay:
            try:
                final_markdown, discourse_report = remove_discourse_markers(final_markdown)
                if discourse_report["markers_removed"] > 0:
                    logger.info(
                        f"Job {job_id}: Removed {discourse_report['markers_removed']} discourse markers"
                    )
                    for detail in discourse_report.get("removal_details", [])[:3]:
                        constraint_warnings.append(
                            f"Discourse marker removed: \"{detail['marker']}\""
                        )
                    await update_job(job_id, constraint_warnings=constraint_warnings)
            except Exception as e:
                logger.error(f"Job {job_id}: Discourse marker removal failed (non-fatal): {e}", exc_info=True)

        # Verbatim Leak Gate (Ideas Edition only)
        # Catches whitelist quote text appearing in narrative prose (outside Key Excerpts/Core Claims)
        if content_mode == ContentMode.essay and whitelist:
            try:
                # Extract quote texts from whitelist for comparison
                whitelist_quote_texts = [q.quote_text for q in whitelist]
                final_markdown, leak_report = enforce_verbatim_leak_gate(
                    final_markdown,
                    whitelist_quote_texts,
                    min_match_len=12,  # Tightened from 25 to catch shorter verbatim leaks
                )
                if leak_report["paragraphs_dropped"] > 0:
                    logger.info(
                        f"Job {job_id}: Verbatim leak gate - dropped "
                        f"{leak_report['paragraphs_dropped']} paragraphs with whitelist leaks"
                    )
                    for detail in leak_report.get("dropped_details", [])[:3]:
                        constraint_warnings.append(
                            f"Verbatim leak dropped ({detail['match_type']}): \"{detail['matched_quote'][:30]}...\""
                        )
                    await update_job(job_id, constraint_warnings=constraint_warnings)
            except Exception as e:
                logger.error(f"Job {job_id}: Verbatim leak gate failed (non-fatal): {e}", exc_info=True)

        # Anchor-sentence policy (Ideas Edition only)
        # Post sentence-drop, chapters may start with orphan pronouns/connectives
        # (It/This/These/However) that lack antecedent because anchoring sentence was dropped.
        # This repairs by prepending a safe salvage sentence or fallback.
        if content_mode == ContentMode.essay:
            try:
                # Note: original_prose_by_chapter is not available at this point in the pipeline
                # so salvage is not possible. We prepend fallback for bad openers.
                whitelist_quote_texts = [q.quote_text for q in whitelist] if whitelist else []
                final_markdown, opener_report = repair_orphan_chapter_openers(
                    final_markdown,
                    original_prose_by_chapter=None,  # TODO: wire up original prose for salvage
                    whitelist_quotes=whitelist_quote_texts,
                )
                if opener_report["chapters_repaired"] > 0:
                    logger.info(
                        f"Job {job_id}: Anchor-sentence policy - repaired "
                        f"{opener_report['chapters_repaired']} chapter opener(s)"
                    )
                    for r in opener_report.get("repairs", [])[:3]:
                        constraint_warnings.append(
                            f"Chapter {r['chapter']} bad opener repaired ({r['action']})"
                        )
                    await update_job(job_id, constraint_warnings=constraint_warnings)
            except Exception as e:
                logger.error(f"Job {job_id}: Anchor-sentence policy failed (non-fatal): {e}", exc_info=True)

        # First-Paragraph Pronoun Repair (Ideas Edition only)
        # Fixes pronoun-start sentences (It/This/These/They) in first paragraph
        # Replaces with chapter title noun (e.g., "It introduced..." → "The Enlightenment introduced...")
        if content_mode == ContentMode.essay:
            try:
                final_markdown, pronoun_report = repair_first_paragraph_pronouns(final_markdown)
                total_repairs = pronoun_report["sentences_repaired"] + pronoun_report["sentences_dropped"]
                if total_repairs > 0:
                    logger.info(
                        f"Job {job_id}: First-paragraph pronoun repair - "
                        f"{pronoun_report['sentences_repaired']} replaced, "
                        f"{pronoun_report['sentences_dropped']} dropped"
                    )
                    for r in pronoun_report.get("repairs", [])[:3]:
                        if r["action"] == "pronoun_replaced":
                            constraint_warnings.append(
                                f"Chapter {r['chapter']} pronoun replaced with '{r['replacement_noun']}'"
                            )
                        else:
                            constraint_warnings.append(
                                f"Chapter {r['chapter']} pronoun sentence dropped"
                            )
                    await update_job(job_id, constraint_warnings=constraint_warnings)
            except Exception as e:
                logger.error(f"Job {job_id}: First-paragraph pronoun repair failed (non-fatal): {e}", exc_info=True)

        # Anachronism filter (Ideas Edition safety net) - only for essay mode
        # Catches contemporary framing that slipped past generation prompts
        # NOTE: Must run BEFORE Chapter Narrative Minimum so fallback can fix any prose-zero created
        if content_mode == ContentMode.essay:
            try:
                final_markdown, anachronism_report = filter_anachronism_paragraphs(final_markdown)
                if anachronism_report["paragraphs_removed"] > 0:
                    logger.info(
                        f"Job {job_id}: Anachronism filter - removed "
                        f"{anachronism_report['paragraphs_removed']} paragraphs with contemporary framing"
                    )
                    # Add to constraint warnings
                    for detail in anachronism_report.get("removed_details", [])[:3]:
                        constraint_warnings.append(
                            f"Anachronism filtered ('{detail['keyword']}'): \"{detail['paragraph'][:40]}...\""
                        )
                    await update_job(job_id, constraint_warnings=constraint_warnings)
            except Exception as e:
                logger.error(f"Job {job_id}: Anachronism filter failed (non-fatal): {e}", exc_info=True)

        # Chapter Narrative Minimum (Ideas Edition only)
        # Ensures each chapter has at least one prose paragraph to prevent content collapse
        # If gates dropped all prose, insert a safe fallback narrative
        # NOTE: Must run AFTER all paragraph-dropping gates (anachronism, leak, etc.)
        if content_mode == ContentMode.essay:
            try:
                final_markdown, narrative_report = ensure_chapter_narrative_minimum(
                    final_markdown,
                    min_prose_paragraphs=1,
                )
                if narrative_report["chapters_fixed"] > 0:
                    logger.info(
                        f"Job {job_id}: Chapter narrative fallback - fixed "
                        f"{narrative_report['chapters_fixed']} chapters with no prose"
                    )
                    for detail in narrative_report.get("fixed_details", [])[:3]:
                        constraint_warnings.append(
                            f"Chapter {detail['chapter']} prose collapsed, inserted fallback"
                        )
                    await update_job(job_id, constraint_warnings=constraint_warnings)
            except Exception as e:
                logger.error(f"Job {job_id}: Chapter narrative fallback failed (non-fatal): {e}", exc_info=True)

        # Strip quote characters from prose (Ideas Edition only)
        # Policy: quotes only allowed in Key Excerpts blockquotes and Core Claims bullets
        # Everywhere else (narrative paragraphs), quote characters are stripped
        # This fixes unclosed inline quotes, orphan quotes, and half-quoted claims
        if content_mode == ContentMode.essay:
            try:
                final_markdown, prose_quote_report = strip_prose_quote_chars(final_markdown)
                if prose_quote_report.get("quotes_stripped", 0) > 0:
                    logger.info(
                        f"Job {job_id}: Prose quote cleanup - stripped {prose_quote_report['quotes_stripped']} quote chars"
                    )
            except Exception as e:
                logger.warning(f"Job {job_id}: Prose quote cleanup failed (non-fatal): {e}")

        # Second pass: Inject excerpts into sections that became empty after enforcement
        # This catches cases where LLM-generated excerpts were dropped by validation
        if content_mode == ContentMode.essay and evidence_map and whitelist:
            try:
                logger.info(
                    f"Job {job_id}: Second pass - inject_excerpts_into_empty_sections "
                    f"(whitelist has {len(whitelist)} quotes)"
                )
                final_markdown = inject_excerpts_into_empty_sections(
                    final_markdown, whitelist, evidence_map
                )
            except Exception as e:
                logger.warning(f"Job {job_id}: Second excerpt injection pass failed (non-fatal): {e}")

        # Final speaker normalization pass (Ideas Edition only)
        # Re-run after all content modifications to catch any non-canonical names
        # introduced by injection passes or other gates
        if content_mode == ContentMode.essay and whitelist:
            try:
                speaker_registry = build_speaker_registry(whitelist)
                final_markdown, final_speaker_report = normalize_speaker_names(
                    final_markdown, speaker_registry
                )
                final_norm_count = final_speaker_report.get("normalized_count", 0)
                if final_norm_count > 0:
                    logger.info(
                        f"Job {job_id}: Final speaker normalization - normalized {final_norm_count} attributions"
                    )
            except Exception as e:
                logger.warning(f"Job {job_id}: Final speaker normalization failed (non-fatal): {e}")

        # Final dangling attribution pass (Ideas Edition only)
        # Re-run after all content modifications to catch any patterns
        # introduced by injection passes, fallback narratives, or other gates
        if content_mode == ContentMode.essay:
            try:
                final_markdown, final_dangling_report = enforce_dangling_attribution_gate(final_markdown)
                if final_dangling_report["rewrites_applied"] > 0:
                    logger.info(
                        f"Job {job_id}: Final dangling attribution pass - rewrote "
                        f"{final_dangling_report['rewrites_applied']} patterns"
                    )
            except Exception as e:
                logger.warning(f"Job {job_id}: Final dangling attribution pass failed (non-fatal): {e}")

        # Final speaker-framing sanitizer pass (Ideas Edition only)
        # Re-run after all modifications to catch any patterns introduced by injection/fallback
        if content_mode == ContentMode.essay:
            try:
                final_markdown, final_sanitizer_report = sanitize_speaker_framing(final_markdown)
                if final_sanitizer_report["rewrites_applied"] > 0:
                    logger.info(
                        f"Job {job_id}: Final speaker-framing sanitizer - rewrote "
                        f"{final_sanitizer_report['rewrites_applied']} patterns"
                    )
            except Exception as e:
                logger.warning(f"Job {job_id}: Final speaker-framing sanitizer failed (non-fatal): {e}")

        # Final speaker-framing invariant pass (Ideas Edition only)
        # Re-run to enforce hard invariant after all modifications
        if content_mode == ContentMode.essay:
            try:
                final_markdown, final_invariant_report = enforce_speaker_framing_invariant(final_markdown)
                if final_invariant_report["speaker_framing_sentences_dropped"] > 0:
                    logger.info(
                        f"Job {job_id}: Final speaker-framing invariant - dropped "
                        f"{final_invariant_report['speaker_framing_sentences_dropped']} sentences"
                    )
            except Exception as e:
                logger.warning(f"Job {job_id}: Final speaker-framing invariant failed (non-fatal): {e}")

        # Final dangling connective cleanup (Ideas Edition only)
        # Re-run after all modifications to catch any orphaned articles/connectives
        if content_mode == ContentMode.essay:
            try:
                final_markdown, final_connective_report = cleanup_dangling_connectives(final_markdown)
                if final_connective_report["cleanups_applied"] > 0:
                    logger.info(
                        f"Job {job_id}: Final dangling connective pass - fixed "
                        f"{final_connective_report['cleanups_applied']} orphaned connectives"
                    )
            except Exception as e:
                logger.warning(f"Job {job_id}: Final dangling connective pass failed (non-fatal): {e}")

        # Core Claims structure validation (Ideas Edition safety net)
        # Catches malformed claims that slipped through enforcement (e.g., due to exceptions)
        # Drops claims with missing closing quotes or known garbage suffixes
        if content_mode == ContentMode.essay:
            try:
                final_markdown, structure_report = validate_core_claims_structure(final_markdown)
                if structure_report["dropped_count"] > 0:
                    logger.warning(
                        f"Job {job_id}: Core Claims structure validation - dropped "
                        f"{structure_report['dropped_count']} malformed claims"
                    )
                    for detail in structure_report.get("dropped", [])[:3]:
                        constraint_warnings.append(
                            f"Malformed Core Claim dropped ({detail['reason']})"
                        )
                    await update_job(job_id, constraint_warnings=constraint_warnings)
            except Exception as e:
                logger.warning(f"Job {job_id}: Core Claims structure validation failed (non-fatal): {e}")

        # Strip empty section headers (Ideas Edition render guard)
        # This is the render guard - empty Key Excerpts/Core Claims sections are removed
        if content_mode == ContentMode.essay:
            try:
                final_markdown, stripped_report = strip_empty_section_headers(final_markdown)
                if stripped_report:
                    logger.warning(
                        f"Job {job_id}: Render guard stripped {len(stripped_report)} empty section(s)"
                    )
                else:
                    logger.debug(f"Job {job_id}: Applied render guard - no empty sections found")
            except Exception as e:
                logger.warning(f"Job {job_id}: Render guard failed (non-fatal): {e}")

        # Clean up orphan fragments between sections (Ideas Edition structural cleanup)
        # Removes debris like "ethos of inquiry." that can appear after Core Claims
        # when a transform drops part of a sentence, leaving a tail
        if content_mode == ContentMode.essay:
            try:
                final_markdown, orphan_report = cleanup_orphan_fragments_between_sections(final_markdown)
                if orphan_report["fragments_removed"] > 0:
                    logger.warning(
                        f"Job {job_id}: Removed {orphan_report['fragments_removed']} orphan fragment(s): "
                        f"{orphan_report['removed_fragments'][:3]}"
                    )
            except Exception as e:
                logger.warning(f"Job {job_id}: Orphan fragment cleanup failed (non-fatal): {e}")

        # Quote artifact cleanup (final pass) - must run LAST after all other processing
        # Cleans up orphan quotes, stray punctuation, and mangled attributions
        # that may have been introduced by upstream enforcement steps
        try:
            final_markdown, artifact_report = fix_quote_artifacts(final_markdown)
            if artifact_report.get("fixes_applied", 0) > 0:
                logger.info(
                    f"Job {job_id}: Quote artifact cleanup - applied {artifact_report['fixes_applied']} fixes"
                )
        except Exception as e:
            logger.warning(f"Job {job_id}: Quote artifact cleanup failed (non-fatal): {e}")

        # Final whitespace repair pass - fix formatting issues from deletions
        try:
            final_markdown = repair_whitespace(final_markdown)
        except Exception as e:
            logger.error(f"Job {job_id}: Whitespace repair failed (non-fatal): {e}", exc_info=True)

        # Markdown header normalization (Ideas Edition) - ensure blank lines before headers
        # This is a pure formatting pass that fixes cosmetic issues
        if content_mode == ContentMode.essay:
            try:
                final_markdown, header_report = normalize_markdown_headers(final_markdown)
                if header_report.get("blank_lines_inserted", 0) > 0:
                    logger.debug(
                        f"Job {job_id}: Header normalizer inserted {header_report['blank_lines_inserted']} blank lines"
                    )
            except Exception as e:
                logger.warning(f"Job {job_id}: Header normalization failed (non-fatal): {e}")

        # Placeholder glue cleanup (Ideas Edition) - remove any leftover artifact strings
        # This catches "[as discussed in the excerpts above]" and similar markers
        if content_mode == ContentMode.essay:
            try:
                final_markdown, glue_report = clean_placeholder_glue(final_markdown)
                if glue_report.get("glue_removed", 0) > 0:
                    logger.info(
                        f"Job {job_id}: Cleaned {glue_report['glue_removed']} placeholder glue strings"
                    )
            except Exception as e:
                logger.warning(f"Job {job_id}: Placeholder glue cleanup failed (non-fatal): {e}")

        # Prose punctuation normalizer (Ideas Edition) - final formatting pass
        # Ensures narrative prose paragraphs end with proper terminal punctuation
        # Must run after all content-modifying passes, before validation
        if content_mode == ContentMode.essay:
            try:
                final_markdown, punct_report = normalize_prose_punctuation(final_markdown)
                if punct_report.get("fixes_applied", 0) > 0:
                    logger.info(
                        f"Job {job_id}: Prose punctuation normalizer - fixed {punct_report['fixes_applied']} paragraphs"
                    )
            except Exception as e:
                logger.warning(f"Job {job_id}: Prose punctuation normalizer failed (non-fatal): {e}")

        # TOKEN INTEGRITY HARD GATE (Ideas Edition)
        # This is the final structural invariant check - if violations are found,
        # the draft pipeline has a bug that corrupted text mid-word.
        # Currently logs warnings; will be elevated to hard-fail once source is identified.
        if content_mode == ContentMode.essay:
            try:
                is_valid, integrity_report = validate_token_integrity(final_markdown)
                if not is_valid:
                    logger.error(
                        f"Job {job_id}: TOKEN INTEGRITY VIOLATION - "
                        f"{integrity_report['violation_count']} token truncation artifacts detected"
                    )
                    for v in integrity_report.get("violations", [])[:5]:
                        logger.error(
                            f"  - {v['type']} at line {v['line_num']}: '{v['matched']}' "
                            f"in context: '{v['context'][:60]}...'"
                        )
                        constraint_warnings.append(
                            f"TOKEN CORRUPTION: {v['type']} - '{v['matched']}'"
                        )
                    await update_job(job_id, constraint_warnings=constraint_warnings)
                    # TODO: Once root cause is identified and fixed, elevate to hard-fail:
                    # raise ValueError(f"Token integrity check failed: {integrity_report['violation_count']} violations")
            except Exception as e:
                logger.error(f"Job {job_id}: Token integrity check failed: {e}", exc_info=True)

        # Per-chapter prose metrics (Ideas Edition quality tracking)
        if content_mode == ContentMode.essay:
            try:
                prose_metrics = compute_chapter_prose_metrics(final_markdown)
                logger.info(
                    f"Job {job_id}: Prose metrics - "
                    f"{prose_metrics['total_sentences_kept']} sentences kept across "
                    f"{prose_metrics['total_chapters']} chapters, "
                    f"{prose_metrics['fallback_chapters']} used fallback"
                )
                for ch_metrics in prose_metrics.get("chapters", []):
                    if ch_metrics.get("fallback_used"):
                        logger.info(
                            f"  - Chapter {ch_metrics['chapter']}: "
                            f"{ch_metrics['sentences_kept']} sentences (FALLBACK)"
                        )
                    elif ch_metrics["sentences_kept"] < 3:
                        logger.warning(
                            f"  - Chapter {ch_metrics['chapter']}: "
                            f"{ch_metrics['sentences_kept']} sentences (LOW)"
                        )
            except Exception as e:
                logger.warning(f"Job {job_id}: Prose metrics computation failed (non-fatal): {e}")

        # FINAL SECTION REPAIR (Ideas Edition) - runs AFTER all transforms/render guards
        # This ensures sections can never disappear. Must run AFTER strip_empty_section_headers
        # so any sections removed by render guards are re-inserted with placeholders.
        if content_mode == ContentMode.essay:
            try:
                final_markdown, sections_report = ensure_required_sections_exist(final_markdown)
                if sections_report["sections_inserted"] > 0:
                    logger.warning(
                        f"Job {job_id}: FINAL SECTION REPAIR - Inserted {sections_report['sections_inserted']} "
                        f"missing section(s): {sections_report['inserted']}"
                    )
            except Exception as e:
                logger.warning(f"Job {job_id}: Final section repair failed (non-fatal): {e}")

        # STRUCTURAL INTEGRITY HARD GATE (Ideas Edition)
        # P0 invariant: unclosed quotes, headings inside quotes, quote absorption
        # These indicate fundamental corruption that cannot be safely patched.
        # Runs immediately after section repair to validate the final structure.
        if content_mode == ContentMode.essay:
            try:
                is_valid, struct_report = validate_structural_integrity(final_markdown)
                if not is_valid:
                    logger.error(
                        f"Job {job_id}: STRUCTURAL INTEGRITY VIOLATION - "
                        f"{struct_report['violation_count']} structural corruption detected"
                    )
                    for v in struct_report.get("violations", [])[:5]:
                        logger.error(
                            f"  - {v['type']}: {v.get('context', '')[:60]}..."
                        )
                        constraint_warnings.append(
                            f"STRUCTURAL CORRUPTION: {v['type']}"
                        )
                    await update_job(job_id, constraint_warnings=constraint_warnings)
                    # TODO: Elevate to hard-fail once we're confident in the detection:
                    # raise ValueError(f"Structural integrity check failed: {struct_report['violation_count']} violations")
            except Exception as e:
                logger.error(f"Job {job_id}: Structural integrity check failed: {e}", exc_info=True)

        await update_job(
            job_id,
            status=JobStatus.completed,
            draft_markdown=final_markdown,
            chapters_completed=chapters_completed,
        )

        logger.info(f"Job {job_id}: Generation completed")

        # T019: Auto-trigger QA analysis after draft completion
        job = await get_job(job_id)
        if job and job.project_id:
            await _trigger_qa_analysis(job.project_id, final_markdown, request.transcript)

    except Exception as e:
        logger.error(f"Job {job_id}: Generation failed: {e}", exc_info=True)
        await update_job(
            job_id,
            status=JobStatus.failed,
            error=str(e),
            error_code="GENERATION_ERROR",
        )


# ==============================================================================
# Core Generation Functions (to be fully implemented in Phase 3)
# ==============================================================================

async def generate_draft_plan(
    transcript: str,
    outline: list[dict],
    style_config: dict,
    resources: Optional[list[dict]] = None,
) -> DraftPlan:
    """Generate a DraftPlan from outline structure with LLM enhancement.

    Chapters are derived from the outline (level=1 items = chapters).
    LLM is used only for visual plan generation, not chapter structure.

    Special case: For interview_qa format with no outline, creates a single
    flowing Q&A document with topics emerging naturally from the content.

    Args:
        transcript: Full transcript text.
        outline: List of outline items.
        style_config: StyleConfig or StyleConfigEnvelope dict.
        resources: Optional resources.

    Returns:
        Generated DraftPlan with outline-driven chapters.
    """
    # Extract style dict
    if "style" in style_config:
        style_dict = style_config.get("style", {})
    else:
        style_dict = style_config

    book_format = style_dict.get("book_format", "guide")

    # Step 1: Derive chapter structure from outline
    chapters = parse_outline_to_chapters(outline, transcript)

    if not chapters:
        from src.models import TranscriptSegment

        # Special handling for interview_qa without outline:
        # Create a single "document" that will generate flowing Q&A
        if book_format == "interview_qa":
            # Extract speaker name for title
            speaker_name = _extract_speaker_name(transcript)
            title = f"A Conversation with {speaker_name}" if speaker_name != "The speaker" else "Interview"

            chapters = [
                ChapterPlan(
                    chapter_number=1,
                    title=title,
                    outline_item_id="interview-qa-1",
                    goals=["Preserve the natural Q&A flow of the interview"],
                    key_points=["Questions and answers organized by topic"],
                    transcript_segments=[
                        TranscriptSegment(start_char=0, end_char=len(transcript), relevance="primary")
                    ],
                    estimated_words=max(500, len(transcript) // 5),
                )
            ]
            logger.info(f"Interview Q&A mode: creating single flowing document")
        else:
            # Standard fallback: create a single chapter
            chapters = [
                ChapterPlan(
                    chapter_number=1,
                    title="Content",
                    outline_item_id="fallback-1",
                    goals=["Cover the main content from the transcript"],
                    key_points=["Key points from the source material"],
                    transcript_segments=[
                        TranscriptSegment(start_char=0, end_char=len(transcript), relevance="primary")
                    ],
                    estimated_words=max(500, len(transcript) // 5),
                )
            ]

    logger.info(f"Derived {len(chapters)} chapters from outline")

    # Step 2: Generate visual plan using LLM (optional enhancement)
    # Skip visual generation for interview_qa (usually minimal visuals)
    if book_format == "interview_qa":
        from src.models.visuals import VisualPlan
        visual_plan = VisualPlan(opportunities=[], assets=[])
    else:
        visual_plan = await _generate_visual_plan(transcript, chapters, style_config)

    # Step 3: Calculate metadata
    total_words = sum(ch.estimated_words for ch in chapters)
    # Rough estimate: 30 seconds per 100 words
    estimated_time = (total_words // 100) * 30

    from src.models import GenerationMetadata
    metadata = GenerationMetadata(
        estimated_total_words=total_words,
        estimated_generation_time_seconds=estimated_time,
        transcript_utilization=0.9,  # Assume most transcript is used
    )

    # Step 4: Build book title from first outline item or default
    book_title = "Untitled Ebook"
    if outline:
        for item in outline:
            if item.get("level", 1) == 1:
                book_title = item.get("title", book_title)
                break
    elif book_format == "interview_qa":
        # For interview_qa without outline, use the chapter title
        book_title = chapters[0].title if chapters else "Interview"

    draft_plan = DraftPlan(
        version=1,
        book_title=book_title,
        chapters=chapters,
        visual_plan=visual_plan,
        generation_metadata=metadata,
    )

    logger.info(f"Generated DraftPlan with {len(draft_plan.chapters)} chapters (outline-driven)")
    return draft_plan


async def _generate_visual_plan(
    transcript: str,
    chapters: list[ChapterPlan],
    style_config: dict,
) -> VisualPlan:
    """Generate visual opportunities plan using LLM.

    Args:
        transcript: Full transcript text.
        chapters: List of chapter plans.
        style_config: Style configuration dict.

    Returns:
        VisualPlan with opportunities.
    """
    # Extract visual density setting
    if "style" in style_config:
        style_dict = style_config.get("style", {})
    else:
        style_dict = style_config

    visual_density = style_dict.get("visual_density", "medium")

    # For "none" density, return empty plan
    if visual_density == "none":
        logger.info("Visual density is 'none', skipping opportunity generation")
        return VisualPlan(opportunities=[], assets=[])

    # Skip if no chapters to analyze
    if not chapters:
        logger.info("No chapters to analyze for visual opportunities")
        return VisualPlan(opportunities=[], assets=[])

    try:
        client = LLMClient()

        # Build prompts
        user_prompt = build_visual_opportunity_user_prompt(chapters, visual_density)

        # Load schema for structured output
        schema = load_visual_opportunities_schema()

        request = LLMRequest(
            model=PLANNING_MODEL,
            messages=[
                ChatMessage(role="system", content=VISUAL_OPPORTUNITY_SYSTEM_PROMPT),
                ChatMessage(role="user", content=user_prompt),
            ],
            temperature=0.7,
            max_tokens=2000,
            response_format=ResponseFormat(
                type="json_schema",
                json_schema={
                    "name": "visual_opportunities",
                    "strict": True,
                    "schema": schema,
                },
            ),
        )

        response = await client.generate(request)

        # Parse response
        import json
        result = json.loads(response.text)
        raw_opportunities = result.get("opportunities", [])

        # Convert to VisualOpportunity objects with defaults
        opportunities: list[VisualOpportunity] = []
        for raw in raw_opportunities:
            try:
                # Map visual_type string to enum
                visual_type_str = raw.get("visual_type", "other")
                try:
                    visual_type = VisualType(visual_type_str)
                except ValueError:
                    visual_type = VisualType.other

                opportunity = VisualOpportunity(
                    id=str(uuid.uuid4()),
                    chapter_index=raw.get("chapter_index", 1),
                    section_path=None,  # Default
                    placement=VisualPlacement.after_heading,  # Default
                    visual_type=visual_type,
                    source_policy=VisualSourcePolicy.client_assets_only,  # Default
                    title=raw.get("title", "Untitled Visual"),
                    prompt=raw.get("prompt", ""),
                    caption=raw.get("caption", ""),
                    required=False,  # Default
                    candidate_asset_ids=[],  # Default
                    confidence=max(0.0, min(1.0, raw.get("confidence", 0.6))),
                    rationale=raw.get("rationale"),
                )
                opportunities.append(opportunity)
            except Exception as e:
                logger.warning(f"Failed to parse opportunity: {e}")
                continue

        # Sort by chapter_index ASC, then confidence DESC (deterministic ordering)
        opportunities.sort(key=lambda o: (o.chapter_index, -o.confidence))

        logger.info(f"Generated {len(opportunities)} visual opportunities (density={visual_density})")
        return VisualPlan(opportunities=opportunities, assets=[])

    except Exception as e:
        # On LLM failure, log and return empty opportunities (draft still succeeds)
        logger.error(f"Failed to generate visual opportunities: {e}")
        return VisualPlan(opportunities=[], assets=[])


async def generate_chapter(
    chapter_plan: ChapterPlan,
    transcript: str,
    book_title: str,
    style_config: dict,
    chapters_completed: list[str],
    all_chapters: list[ChapterPlan],
    words_per_chapter_target: int = 625,
    detail_level: str = "balanced",
    # Spec 009: Evidence-grounded generation
    chapter_evidence: Optional[ChapterEvidence] = None,
    content_mode: ContentMode = ContentMode.interview,
    strict_grounded: bool = True,
) -> str:
    """Generate a single chapter using LLM.

    Args:
        chapter_plan: The plan for this chapter.
        transcript: Full transcript text.
        book_title: Title of the ebook.
        style_config: StyleConfig dict.
        chapters_completed: Previously completed chapters (for context).
        all_chapters: All chapter plans (for next chapter preview).
        words_per_chapter_target: Target word count for this chapter.
        detail_level: Detail level (concise/balanced/detailed).
        chapter_evidence: Evidence Map data for this chapter (Spec 009).
        content_mode: Content mode (interview/essay/tutorial) (Spec 009).
        strict_grounded: Whether to enforce strict grounding (Spec 009).

    Returns:
        Generated chapter markdown.
    """
    client = LLMClient()

    # Extract style config if wrapped
    if "style" in style_config:
        style_dict = style_config.get("style", {})
    else:
        style_dict = style_config

    # Get transcript segment for this chapter
    transcript_segment = extract_transcript_segment(transcript, chapter_plan)

    # Check if using Interview Q&A format
    book_format = style_dict.get("book_format", "guide")

    # Get context from previous/next chapters
    previous_ending = get_previous_chapter_ending(chapters_completed)
    chapter_index = chapter_plan.chapter_number - 1
    next_preview = get_next_chapter_preview(all_chapters, chapter_index)

    if book_format == "interview_qa":
        # Use Q&A-specific prompts (Interview Q&A format from main)
        speaker_name = _extract_speaker_name(transcript)
        system_prompt = build_interview_qa_system_prompt(
            book_title=book_title,
            speaker_name=speaker_name,
        )
        user_prompt = build_interview_qa_chapter_prompt(
            chapter_plan=chapter_plan,
            transcript_segment=transcript_segment,
            speaker_name=speaker_name,
        )
    elif chapter_evidence and chapter_evidence.claims:
        # Use grounded chapter generation prompts (Spec 009)
        system_prompt = build_grounded_chapter_system_prompt(
            book_title=book_title,
            chapter_number=chapter_plan.chapter_number,
            style_config=style_dict,
            words_per_chapter_target=words_per_chapter_target,
            detail_level=detail_level,
            content_mode=content_mode.value,
            strict_grounded=strict_grounded,
        )
        user_prompt = build_grounded_chapter_user_prompt(
            chapter_plan=chapter_plan,
            evidence_claims=[claim.model_dump() for claim in chapter_evidence.claims],
            must_include=[item.model_dump() for item in chapter_evidence.must_include],
            transcript_segment=transcript_segment,
            previous_chapter_ending=previous_ending,
            next_chapter_preview=next_preview,
        )
        logger.debug(
            f"Using grounded prompts for chapter {chapter_plan.chapter_number} "
            f"({len(chapter_evidence.claims)} claims)"
        )
    else:
        # Fall back to standard prompts (no evidence available)
        system_prompt = build_chapter_system_prompt(
            book_title=book_title,
            chapter_number=chapter_plan.chapter_number,
            style_config=style_dict,
            words_per_chapter_target=words_per_chapter_target,
            detail_level=detail_level,
        )
        user_prompt = build_chapter_user_prompt(
            chapter_plan=chapter_plan,
            transcript_segment=transcript_segment,
            previous_chapter_ending=previous_ending,
            next_chapter_preview=next_preview,
        )
        logger.debug(
            f"Using standard prompts for chapter {chapter_plan.chapter_number} "
            "(no evidence available)"
        )

    request = LLMRequest(
        model=CHAPTER_MODEL,
        messages=[
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=user_prompt),
        ],
        temperature=0.7,
        max_tokens=4000,
    )

    response = await client.generate(request)

    logger.debug(f"Generated chapter {chapter_plan.chapter_number}: {len(response.text)} chars")

    # Apply enforcement for essay format
    chapter_text = response.text
    if book_format == "essay":
        chapter_text, enforcement_report = enforce_prose_quality(chapter_text, book_format)
        if enforcement_report["sections_removed"]:
            logger.info(
                f"Chapter {chapter_plan.chapter_number}: removed sections: "
                f"{enforcement_report['sections_removed']}"
            )

        # Polish pass for essay format - stronger model for prose quality
        try:
            logger.info(f"Chapter {chapter_plan.chapter_number}: running polish pass")
            polished_text = await polish_chapter(chapter_text, client)
            logger.info(f"Chapter {chapter_plan.chapter_number}: polish complete, {len(polished_text)} chars")
            chapter_text = polished_text
        except Exception as e:
            logger.error(f"Chapter {chapter_plan.chapter_number}: polish pass failed (using unpolished): {e}")
            # Continue with unpolished text rather than crashing

    return chapter_text


def _extract_speaker_name(transcript: str) -> str:
    """Extract the primary speaker name from transcript.

    Looks for patterns like "Name:" at the start of lines.
    Returns "The speaker" if no clear pattern found.

    Args:
        transcript: The transcript text.

    Returns:
        Extracted speaker name or default.
    """
    import re

    # Find speaker patterns like "Name:" at line starts (excluding "Host:")
    pattern = r'^([A-Z][a-zA-Z\s]+):'
    matches = re.findall(pattern, transcript, re.MULTILINE)

    # Filter out common host/interviewer labels
    host_labels = {"Host", "Interviewer", "Q", "Question", "Moderator"}
    speakers = [m.strip() for m in matches if m.strip() not in host_labels]

    if speakers:
        # Return most common non-host speaker
        from collections import Counter
        counter = Counter(speakers)
        most_common = counter.most_common(1)[0][0]
        return most_common

    return "The speaker"


# ==============================================================================
# P0: Single-Pass Interview Generation
# ==============================================================================

async def generate_interview_single_pass(
    transcript: str,
    book_title: str,
    evidence_map: EvidenceMap,
    forced_candidates: Optional[list[dict]] = None,
) -> str:
    """Generate interview ebook using single-pass approach (P0).

    Produces the new output structure:
    - ## Key Ideas (Grounded) - with inline supporting quotes
    - ## The Conversation - Q&A format

    Args:
        transcript: Full transcript text.
        book_title: Title of the ebook.
        evidence_map: Evidence Map with extracted claims.
        forced_candidates: Optional list of definitional candidates to force into Key Ideas.

    Returns:
        Generated markdown with Key Ideas + Conversation structure.
    """
    client = LLMClient()

    # Extract speaker name
    speaker_name = _extract_speaker_name(transcript)

    # Collect all claims from all chapters for the Key Ideas section
    all_claims: list[dict] = []
    for chapter in evidence_map.chapters:
        for claim in chapter.claims:
            all_claims.append(claim.model_dump())

    # Sort by confidence to prioritize strongest claims
    all_claims.sort(key=lambda c: c.get("confidence", 0), reverse=True)

    # Build prompts
    system_prompt = build_interview_grounded_system_prompt(
        book_title=book_title,
        speaker_name=speaker_name,
    )

    user_prompt = build_interview_grounded_user_prompt(
        transcript=transcript,
        speaker_name=speaker_name,
        evidence_claims=all_claims,
    )

    # If we have forced candidates (re-run), inject them into the prompt
    if forced_candidates:
        forced_text = format_candidates_for_prompt(forced_candidates)
        user_prompt = f"{forced_text}\n\n---\n\n{user_prompt}"
        logger.info(f"Re-running with {len(forced_candidates)} forced definitional candidates")

    request = LLMRequest(
        model=CHAPTER_MODEL,
        messages=[
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=user_prompt),
        ],
        temperature=0.7,
        max_tokens=8000,  # Larger for single-pass
    )

    response = await client.generate(request)

    # Strip any H1 heading the LLM might have generated (we add our own)
    content = response.text.strip()
    if content.startswith("# "):
        # Remove the first H1 line
        lines = content.split("\n")
        # Find first non-H1 line
        start_idx = 0
        for i, line in enumerate(lines):
            if line.strip() and not line.startswith("# "):
                start_idx = i
                break
            elif line.startswith("# "):
                start_idx = i + 1
        content = "\n".join(lines[start_idx:]).strip()

    # Assemble final output with proper book title
    final_markdown = f"# {book_title}\n\n{content}"

    logger.info(f"Generated interview single-pass: {len(content)} chars")
    return final_markdown


def _extract_key_ideas_section(markdown: str) -> str:
    """Extract just the Key Ideas section from the generated markdown.

    Args:
        markdown: Full generated markdown.

    Returns:
        Just the Key Ideas section content.
    """
    import re

    # Find Key Ideas section
    match = re.search(
        r'## Key Ideas.*?\n(.*?)(?=\n## |\Z)',
        markdown,
        re.DOTALL | re.IGNORECASE
    )

    if match:
        return match.group(1).strip()
    return ""


def assemble_chapters(
    book_title: str,
    chapters: list[str],
) -> str:
    """Assemble individual chapters into final draft.

    Args:
        book_title: Title of the ebook.
        chapters: List of chapter markdown strings.

    Returns:
        Complete draft markdown.
    """
    parts = []

    # Check if first chapter title duplicates the book title
    # Pattern: "## Chapter 1: {title}" or "## {title}"
    first_chapter_duplicates_title = False
    if chapters:
        first_chapter = chapters[0].strip()
        # Extract the title from first chapter header
        import re
        # Match "## Chapter 1: Title" or "## Title"
        match = re.match(r'^##\s*(?:Chapter\s*\d+[:\s]*)?(.+)', first_chapter, re.IGNORECASE)
        if match:
            first_chapter_title = match.group(1).strip()
            # Check if it matches book title (case-insensitive, ignoring punctuation)
            book_title_normalized = re.sub(r'[^\w\s]', '', book_title.lower())
            first_title_normalized = re.sub(r'[^\w\s]', '', first_chapter_title.lower())
            first_chapter_duplicates_title = book_title_normalized == first_title_normalized

    # Only add book title header if first chapter doesn't duplicate it
    if not first_chapter_duplicates_title:
        parts.append(f"# {book_title}")
        parts.append("")

    for chapter in chapters:
        parts.append(chapter)
        parts.append("")  # Blank line between chapters

    return "\n".join(parts)


def _assemble_partial_draft(job: GenerationJob) -> Optional[str]:
    """Assemble partial draft from completed chapters.

    Args:
        job: The generation job.

    Returns:
        Partial markdown if chapters available, None otherwise.
    """
    if not job.chapters_completed:
        return None

    title = job.draft_plan.book_title if job.draft_plan else "Untitled"
    markdown = assemble_chapters(title, job.chapters_completed)

    # Add note about incomplete generation
    markdown += "\n\n---\n\n"
    markdown += f"*Generation incomplete. {len(job.chapters_completed)} of {job.total_chapters} chapters available.*\n"

    return markdown


def _find_section_boundaries(
    draft_markdown: str,
    chapter_number: int,
    chapter_title: str,
) -> tuple[int, int]:
    """Find start and end lines of a chapter in the draft.

    Args:
        draft_markdown: Full draft markdown.
        chapter_number: Chapter number to find.
        chapter_title: Chapter title.

    Returns:
        Tuple of (start_line, end_line) (1-indexed).
    """
    lines = draft_markdown.split("\n")
    start_line = 1
    end_line = len(lines)

    # Find chapter heading pattern: ## Chapter N: Title
    chapter_pattern = f"## Chapter {chapter_number}:"

    for i, line in enumerate(lines):
        if line.startswith(chapter_pattern):
            start_line = i + 1  # 1-indexed

        # Find next chapter heading to get end
        elif line.startswith("## Chapter ") and start_line > 1:
            end_line = i  # Line before next chapter
            break

    return (start_line, end_line)


# ==============================================================================
# T019: QA Auto-Trigger
# ==============================================================================

async def _trigger_qa_analysis(
    project_id: str,
    draft: str,
    transcript: Optional[str] = None,
) -> None:
    """Trigger QA analysis after draft completion.

    Runs in background - does not block draft completion.
    Stores report in project.qaReport field.

    Args:
        project_id: The project ID.
        draft: The completed draft markdown.
        transcript: Optional transcript for faithfulness check.
    """
    try:
        from src.services.qa_evaluator import evaluate_draft
        from src.services.project_service import update_project

        logger.info(f"Auto-triggering QA analysis for project {project_id}")

        # Run QA evaluation
        report = await evaluate_draft(
            project_id=project_id,
            draft=draft,
            transcript=transcript,
        )

        # Store report in project
        await update_project(project_id, {"qaReport": report.model_dump(mode="json")})

        logger.info(
            f"QA analysis complete for project {project_id}: "
            f"score={report.overall_score}, issues={report.total_issue_count}"
        )

    except Exception as e:
        # Log error but don't fail the draft generation
        logger.error(f"QA auto-trigger failed for project {project_id}: {e}")


# ==============================================================================
# Chapter Merge Logic
# ==============================================================================

def suggest_chapter_merges(
    chapters: list,
    min_quotes: int = 2,
) -> list[dict]:
    """Suggest chapter merges for chapters below evidence minimum.

    When a chapter doesn't have enough quotes to produce meaningful
    content, this function suggests merging it with a neighbor chapter.

    Args:
        chapters: List of ChapterCoverageReport objects with `chapter_index`
                  and `valid_quotes` attributes.
        min_quotes: Minimum quotes required per chapter.

    Returns:
        List of merge suggestions, each with:
        - weak_chapter: Index of chapter to merge
        - merge_into: Index of chapter to merge into
        - reason: Why the merge is suggested
    """
    if len(chapters) <= 1:
        # Can't merge with only one chapter
        if chapters and chapters[0].valid_quotes < min_quotes:
            return [{"action": "abort", "reason": "Single chapter has insufficient evidence"}]
        return []

    merges = []

    for i, chapter in enumerate(chapters):
        if chapter.valid_quotes >= min_quotes:
            continue

        # This chapter is weak - find best neighbor to merge into
        prev_idx = i - 1 if i > 0 else None
        next_idx = i + 1 if i < len(chapters) - 1 else None

        prev_count = chapters[prev_idx].valid_quotes if prev_idx is not None else -1
        next_count = chapters[next_idx].valid_quotes if next_idx is not None else -1

        # Choose the stronger neighbor
        if prev_count >= next_count and prev_idx is not None:
            merge_into = prev_idx
        elif next_idx is not None:
            merge_into = next_idx
        else:
            # Edge case: shouldn't happen with len > 1
            continue

        merges.append({
            "weak_chapter": chapter.chapter_index,
            "merge_into": chapters[merge_into].chapter_index,
            "reason": f"Chapter {chapter.chapter_index + 1} has only {chapter.valid_quotes} quotes (minimum: {min_quotes})",
        })

    return merges
