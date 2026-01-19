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
from src.models.edition import WhitelistQuote, TranscriptPair

from .job_store import get_job_store, get_job, update_job
from .whitelist_service import (
    build_quote_whitelist,
    canonicalize_transcript,
    strip_llm_blockquotes,
    enforce_quote_whitelist,
    select_deterministic_excerpts,
    format_excerpts_markdown,
    compute_chapter_coverage,
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

# Attribution verbs commonly used
ATTRIBUTION_VERBS = r'(?:argues?|says?|notes?|observes?|warns?|asserts?|claims?|explains?|points?\s+out|suggests?|states?|contends?|believes?|maintains?|emphasizes?|stresses?|highlights?|insists?|remarks?|cautions?|envisions?|tells?|adds?|writes?|acknowledges?|reflects?|challenges?|sees?|views?|thinks?|considers?|describes?|calls?|puts?)'

# Pattern 1: "Speaker verb, X" or "Speaker verb that X" or "Speaker verb: X"
# Matches: Deutsch argues, X / Deutsch says that X / Deutsch notes: X
# Also handles em-dash: Deutsch says—X
ATTRIBUTED_SPEECH_PATTERN_PREFIX = re.compile(
    r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?|He|She)\s+' +  # Speaker name or pronoun
    ATTRIBUTION_VERBS +
    r'(?:,|:|\s+that|\s*\u2014|\s*-)\s*(.+?)(?:\.(?:\s|$)|$)',  # Content after punctuation
    re.MULTILINE | re.DOTALL
)

# Pattern 2: "X, Speaker verb." (suffix attribution)
ATTRIBUTED_SPEECH_PATTERN_SUFFIX = re.compile(
    r'([^.!?]+?),\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?|he|she)\s+' + ATTRIBUTION_VERBS + r'\.',
    re.MULTILINE | re.IGNORECASE
)

# Pattern 3: "Speaker: X" (colon form, narrative use)
ATTRIBUTED_SPEECH_PATTERN_COLON = re.compile(
    r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*:\s+([^.!?]+[.!?])',
    re.MULTILINE
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
    - If invalid OR has ellipsis: DELETE entire clause/sentence

    Args:
        text: The generated text.
        transcript: The canonical transcript.

    Returns:
        Tuple of (cleaned_text, report_dict).
    """
    attributed = find_attributed_speech(text)

    valid_converted = []  # Valid attributions that got quotes added
    invalid_deleted = []  # Invalid attributions that were deleted
    result = text

    # Process in reverse order to maintain positions
    for attr in reversed(attributed):
        content = attr['content']
        speaker = attr['speaker']
        full_match = attr['full_match']

        # Validate content against transcript
        validation = validate_attributed_content(content, transcript)

        if validation['valid']:
            # VALID: Wrap content in quotes
            # "Deutsch argues, X becomes Y." → "Deutsch argues, "X becomes Y.""
            pos = result.find(full_match)
            if pos == -1:
                continue

            # Build the quoted version
            if attr['pattern_type'] == 'suffix':
                # "X, Deutsch argues." → ""X," Deutsch argues."
                # Extract the full attribution clause (everything after content)
                # to preserve phrases like "Deutsch tells me" or "Deutsch points out here"
                attribution_clause = full_match[len(content):].strip()
                # Remove leading comma if present
                if attribution_clause.startswith(','):
                    attribution_clause = attribution_clause[1:].strip()
                # Ensure it ends with a period
                if not attribution_clause.endswith('.'):
                    attribution_clause = attribution_clause + '.'
                quoted_version = f'"{content}," {attribution_clause}'
            else:
                # "Deutsch argues, X." → "Deutsch argues, "X.""
                verb = _extract_verb(full_match, speaker)
                quoted_version = f'{speaker} {verb}, "{content}."'

            result = result[:pos] + quoted_version + result[pos + len(full_match):]
            valid_converted.append({
                'speaker': speaker,
                'content': content[:50] + '...' if len(content) > 50 else content,
                'action': 'quoted',
            })
        else:
            # INVALID: Delete entire sentence containing this attribution
            pos = result.find(full_match)
            if pos == -1:
                continue

            # Find and delete the entire sentence
            sent_start, sent_end = get_sentence_boundaries(result, pos)
            deleted_sentence = result[sent_start:sent_end].strip()

            result = result[:sent_start] + result[sent_end:]
            invalid_deleted.append({
                'speaker': speaker,
                'content': content[:50] + '...' if len(content) > 50 else content,
                'reason': validation['reason'],
                'deleted_sentence': deleted_sentence[:80] + '...' if len(deleted_sentence) > 80 else deleted_sentence,
            })

    # Clean up multiple consecutive newlines/spaces
    result = re.sub(r'\n{3,}', '\n\n', result)
    result = re.sub(r'  +', ' ', result)

    # Grammar repair pass: remove orphan fragments
    result = repair_grammar_fragments(result)

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

        # Anachronism filter (Ideas Edition safety net) - only for essay mode
        # Catches contemporary framing that slipped past generation prompts
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

        # Final whitespace repair pass - fix formatting issues from deletions
        try:
            final_markdown = repair_whitespace(final_markdown)
        except Exception as e:
            logger.error(f"Job {job_id}: Whitespace repair failed (non-fatal): {e}", exc_info=True)

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
