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

from .job_store import get_job_store, get_job, update_job
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

# Best-of-N candidate selection for interview mode
# When enabled, generates multiple candidates and picks the best based on scoring
# Env var sets the MAX allowed; request param sets actual count (capped by env var)
INTERVIEW_CANDIDATE_COUNT_MAX = int(os.environ.get("INTERVIEW_CANDIDATE_COUNT_MAX", "5"))  # Server-side cap

# Generic titles that should be replaced
GENERIC_TITLES = {
    "interview", "interview transcript", "untitled", "untitled ebook", "draft", ""
}


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
    1. Fix heading hierarchy (### Key Ideas → ## Key Ideas, ### The Conversation → ##)
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

        # Fix #1: Ensure Key Ideas is ## (upgrade from ### if needed)
        if re.match(r'^#{2,3}\s+Key Ideas', line, re.IGNORECASE):
            line = re.sub(r'^#{2,3}\s+', '## ', line)
            result_lines.append(line)
            continue

        # Fix #1: Ensure The Conversation is ## (upgrade from ### if needed)
        if re.match(r'^#{2,3}\s+The Conversation', line, re.IGNORECASE):
            line = re.sub(r'^#{2,3}\s+', '## ', line)
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
CALLER_INTRO_PATTERNS = [
    # "[Name] in [Location]...you're on the air"
    r'###\s+.*?([A-Z][a-z]+)\s+in\s+[A-Z][a-z]+.*?you\'?re\s+on\s+the\s+air',
    # "[Name], you're on the air"
    r'###\s+.*?([A-Z][a-z]+),?\s+you\'?re\s+on\s+the\s+air',
    # "Let's go to [Name] in [Location]"
    r'###\s+.*?[Ll]et\'?s\s+go\s+to\s+([A-Z][a-z]+)\s+in\s+[A-Z]',
    # "[Name] is calling from"
    r'###\s+.*?([A-Z][a-z]+)\s+is\s+calling\s+from',
]

# Host transition patterns - signals end of caller segment
HOST_TRANSITION_PATTERNS = [
    # "[Name], I'll put that to..."
    r'###\s+[A-Z][a-z]+,\s+(?:I\'ll\s+put|let\s+(?:me|us)\s+pick)',
    # "David Deutsch, what do you say"
    r'###\s+.*?David\s+Deutsch.*?what\s+do\s+you\s+say',
    # "Professor Deutsch" or "Mr. Deutsch"
    r'###\s+.*?(?:Professor|Mr\.?)\s+Deutsch',
    # "Let me put that to" / "Let us pick it up"
    r'###\s+.*?[Ll]et\s+(?:me|us)\s+(?:put|pick)',
    # Questions directed at Deutsch
    r'###\s+.*?Deutsch.*?\?$',
]

# Patterns that indicate caller is speaking (in their response)
CALLER_SPEECH_PATTERNS = [
    r'^Hi,?\s+Tom',  # Greeting the host
    r'^Thanks?\s+for\s+(?:having|taking)',
    r'^I\s+have\s+a\s+question\s+for\s+(?:Mr\.|Professor)',
    r'^(?:Mr\.|Professor)\s+Deutsch,\s+(?:given|I)',
]


def fix_speaker_attribution(markdown: str) -> str:
    """Fix speaker attribution in interview markdown using heuristics.

    Detects caller segments and re-labels **GUEST:** blocks appropriately.
    Uses UNKNOWN: when attribution is uncertain (never misattribute).

    Detection strategy:
    1. Caller intro in header (e.g., "Dana in South Wellfleet...you're on the air")
       → Next **GUEST:** block becomes **CALLER (Dana):**
    2. Host transition (e.g., "Dana, I'll put that to David Deutsch")
       → End caller segment, next **GUEST:** is actually GUEST
    3. Caller speech patterns (e.g., "Hi, Tom. Mr. Deutsch...")
       → Confirms we're in a caller segment

    Args:
        markdown: Interview markdown with potentially wrong speaker labels.

    Returns:
        Markdown with corrected speaker attribution.
    """
    import re

    lines = markdown.split('\n')
    result_lines = []

    # State tracking
    current_caller: Optional[str] = None  # Name of active caller
    expecting_caller_speech = False  # Next GUEST: block is caller
    caller_blocks_remaining = 0  # How many more GUEST: blocks are caller

    for i, line in enumerate(lines):
        # Check if this is a question header
        if line.startswith('### '):
            header_text = line

            # Check for caller intro patterns
            caller_name = None
            for pattern in CALLER_INTRO_PATTERNS:
                match = re.search(pattern, header_text, re.IGNORECASE)
                if match:
                    caller_name = match.group(1)
                    break

            if caller_name:
                # Found caller intro - expect caller speech next
                current_caller = caller_name
                expecting_caller_speech = True
                # Callers typically get 1-2 speech blocks before host transitions
                caller_blocks_remaining = 2
                result_lines.append(line)
                continue

            # Check for host transition patterns (ends caller segment)
            for pattern in HOST_TRANSITION_PATTERNS:
                if re.search(pattern, header_text, re.IGNORECASE):
                    # Host is transitioning back to Deutsch
                    expecting_caller_speech = False
                    caller_blocks_remaining = 0
                    current_caller = None
                    break

            result_lines.append(line)
            continue

        # Check if this is a speaker attribution line
        guest_match = re.match(r'^\*\*GUEST:\*\*\s*(.*)$', line)
        if guest_match:
            response_start = guest_match.group(1)

            # Determine correct attribution
            if expecting_caller_speech and caller_blocks_remaining > 0:
                # Check if response matches caller speech patterns
                is_caller_speech = False
                for pattern in CALLER_SPEECH_PATTERNS:
                    if re.match(pattern, response_start, re.IGNORECASE):
                        is_caller_speech = True
                        break

                # Also check: short responses following caller intro are likely caller
                # Long responses (100+ words) after a question are likely Deutsch
                words_in_line = len(response_start.split())

                if is_caller_speech or (current_caller and caller_blocks_remaining == 2):
                    # This is caller speech
                    line = f'**CALLER ({current_caller}):** {response_start}'
                    caller_blocks_remaining -= 1
                    if caller_blocks_remaining == 0:
                        expecting_caller_speech = False
                else:
                    # Uncertain - but we're in a caller context
                    # Check next lines to see total response length
                    # For now, be conservative: if we expected caller, label as caller
                    if current_caller and caller_blocks_remaining > 0:
                        line = f'**CALLER ({current_caller}):** {response_start}'
                        caller_blocks_remaining -= 1

            # If not in caller context, keep as GUEST (it's Deutsch)
            result_lines.append(line)
            continue

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
    return response.text


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
    parts = [
        f"# {book_title}",
        "",
    ]

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
