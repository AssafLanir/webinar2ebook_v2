"""Evidence Map generation service (Spec 009).

Generates Evidence Maps from transcript content to ground draft generation
in verifiable source material. Handles claim extraction, evidence validation,
and content mode detection.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime
from typing import Any, Optional

from src.llm import LLMClient, LLMRequest, ChatMessage, ResponseFormat
from src.models import (
    ChapterPlan,
    StyleConfig,
    StyleConfigEnvelope,
)
from src.models.evidence_map import (
    EvidenceMap,
    ChapterEvidence,
    EvidenceEntry,
    SupportQuote,
    MustIncludeItem,
    MustIncludePriority,
    ClaimType,
    GlobalContext,
    SpeakerInfo,
    TranscriptRange,
)
from src.models.style_config import ContentMode

from .prompts import (
    EVIDENCE_EXTRACTION_SYSTEM_PROMPT,
    build_claim_extraction_prompt,
    INTERVIEW_FORBIDDEN_PATTERNS,
    extract_transcript_segment,
)

logger = logging.getLogger(__name__)

# LLM model for evidence extraction
EVIDENCE_EXTRACTION_MODEL = "gpt-4o-mini"


# ==============================================================================
# Evidence Map Generation (T018)
# ==============================================================================

async def generate_evidence_map(
    project_id: str,
    transcript: str,
    chapters: list[ChapterPlan],
    content_mode: ContentMode = ContentMode.interview,
    strict_grounded: bool = True,
    style_config: Optional[dict] = None,
) -> EvidenceMap:
    """Generate an Evidence Map from transcript for all chapters.

    This is the main entry point for evidence extraction. Iterates through
    chapters, extracting claims and building the Evidence Map structure.

    Args:
        project_id: Associated project ID.
        transcript: Full transcript text.
        chapters: List of ChapterPlan objects defining structure.
        content_mode: Content mode (interview/essay/tutorial).
        strict_grounded: Whether to enforce strict grounding.
        style_config: Optional style config for additional context.

    Returns:
        Populated EvidenceMap with per-chapter evidence.
    """
    logger.info(f"Generating Evidence Map for project {project_id}, {len(chapters)} chapters")

    # Generate transcript hash for cache invalidation
    transcript_hash = hashlib.sha256(transcript.encode()).hexdigest()[:16]

    # Initialize Evidence Map
    evidence_map = EvidenceMap(
        project_id=project_id,
        content_mode=content_mode,
        strict_grounded=strict_grounded,
        transcript_hash=transcript_hash,
        generated_at=datetime.utcnow(),
    )

    # Extract global context first
    evidence_map.global_context = await _extract_global_context(transcript)

    # Process each chapter
    chapter_evidences: list[ChapterEvidence] = []
    for chapter in chapters:
        logger.debug(f"Extracting evidence for chapter {chapter.chapter_number}: {chapter.title}")

        # Get transcript segment for this chapter
        segment = extract_transcript_segment(transcript, chapter)

        # Extract claims for this chapter
        chapter_evidence = await extract_claims_for_chapter(
            chapter_index=chapter.chapter_number,
            chapter_title=chapter.title,
            transcript_segment=segment,
            content_mode=content_mode,
            outline_item_id=chapter.outline_item_id,
        )

        # Handle empty evidence (T021)
        chapter_evidence = handle_empty_evidence(
            chapter_evidence=chapter_evidence,
            chapter_title=chapter.title,
            content_mode=content_mode,
        )

        # Add forbidden patterns for interview mode
        if content_mode == ContentMode.interview:
            chapter_evidence.forbidden = [
                "action_steps",
                "how_to_guides",
                "biographical_details",
                "motivational_platitudes",
            ]

        chapter_evidences.append(chapter_evidence)

    evidence_map.chapters = chapter_evidences

    logger.info(
        f"Evidence Map complete: {sum(len(c.claims) for c in chapter_evidences)} claims across {len(chapters)} chapters"
    )

    return evidence_map


# ==============================================================================
# Claim Extraction (T019)
# ==============================================================================

async def extract_claims_for_chapter(
    chapter_index: int,
    chapter_title: str,
    transcript_segment: str,
    content_mode: str = "interview",
    outline_item_id: Optional[str] = None,
) -> ChapterEvidence:
    """Extract claims and evidence for a single chapter.

    Calls LLM to analyze transcript and extract verifiable claims
    with supporting quotes.

    Args:
        chapter_index: 1-based chapter number.
        chapter_title: Title of the chapter.
        transcript_segment: Transcript text for this chapter.
        content_mode: Content mode affecting extraction focus.
        outline_item_id: Optional outline item ID.

    Returns:
        ChapterEvidence with extracted claims.
    """
    # Build prompts
    user_prompt = build_claim_extraction_prompt(
        chapter_title=chapter_title,
        transcript_segment=transcript_segment,
        content_mode=content_mode,
    )

    # Call LLM
    client = LLMClient()
    request = LLMRequest(
        model=EVIDENCE_EXTRACTION_MODEL,
        messages=[
            ChatMessage(role="system", content=EVIDENCE_EXTRACTION_SYSTEM_PROMPT),
            ChatMessage(role="user", content=user_prompt),
        ],
        response_format=ResponseFormat(type="json_object"),
        temperature=0.3,  # Lower temperature for more consistent extraction
    )

    try:
        response = await client.generate(request)

        # Parse response
        result = json.loads(response.text)

        # Build claims from response
        claims = _parse_claims_response(result.get("claims", []), chapter_index)
        must_include = _parse_must_include_response(result.get("must_include", []))

        return ChapterEvidence(
            chapter_index=chapter_index,
            chapter_title=chapter_title,
            outline_item_id=outline_item_id,
            claims=claims,
            must_include=must_include,
            transcript_range=TranscriptRange(
                start_char=0,
                end_char=len(transcript_segment),
            ) if transcript_segment else None,
        )

    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse LLM response for chapter {chapter_index}: {e}")
        return ChapterEvidence(
            chapter_index=chapter_index,
            chapter_title=chapter_title,
            outline_item_id=outline_item_id,
        )
    except Exception as e:
        logger.error(f"Error extracting claims for chapter {chapter_index}: {e}")
        return ChapterEvidence(
            chapter_index=chapter_index,
            chapter_title=chapter_title,
            outline_item_id=outline_item_id,
        )


def _parse_claims_response(
    claims_data: list[dict],
    chapter_index: int,
) -> list[EvidenceEntry]:
    """Parse LLM claims response into EvidenceEntry objects.

    Args:
        claims_data: Raw claims from LLM response.
        chapter_index: Chapter number for ID prefixing.

    Returns:
        List of validated EvidenceEntry objects.
    """
    entries: list[EvidenceEntry] = []

    for i, claim_data in enumerate(claims_data):
        try:
            # Parse support quotes
            support_quotes: list[SupportQuote] = []
            for quote_data in claim_data.get("support", []):
                support_quotes.append(SupportQuote(
                    quote=quote_data.get("quote", ""),
                    start_char=quote_data.get("start_char"),
                    end_char=quote_data.get("end_char"),
                    speaker=quote_data.get("speaker"),
                ))

            if not support_quotes:
                # Skip claims without support
                logger.debug(f"Skipping claim without support: {claim_data.get('claim', '')[:50]}...")
                continue

            # Parse claim type
            claim_type_str = claim_data.get("claim_type", "factual")
            try:
                claim_type = ClaimType(claim_type_str)
            except ValueError:
                claim_type = ClaimType.factual

            # Create entry
            entry = EvidenceEntry(
                id=claim_data.get("id", f"ch{chapter_index}_claim_{i+1:03d}"),
                claim=claim_data.get("claim", ""),
                support=support_quotes,
                confidence=min(1.0, max(0.0, claim_data.get("confidence", 0.8))),
                claim_type=claim_type,
            )
            entries.append(entry)

        except Exception as e:
            logger.warning(f"Failed to parse claim {i}: {e}")
            continue

    return entries


def _parse_must_include_response(
    must_include_data: list[dict],
) -> list[MustIncludeItem]:
    """Parse must-include items from LLM response.

    Args:
        must_include_data: Raw must-include items.

    Returns:
        List of MustIncludeItem objects.
    """
    items: list[MustIncludeItem] = []

    for item_data in must_include_data:
        try:
            priority_str = item_data.get("priority", "important")
            try:
                priority = MustIncludePriority(priority_str)
            except ValueError:
                priority = MustIncludePriority.important

            items.append(MustIncludeItem(
                point=item_data.get("point", ""),
                priority=priority,
                evidence_ids=item_data.get("evidence_ids", []),
            ))
        except Exception as e:
            logger.warning(f"Failed to parse must-include item: {e}")
            continue

    return items


# ==============================================================================
# Supporting Quote Extraction (T020)
# ==============================================================================

def find_supporting_quotes(
    claim: str,
    transcript: str,
    max_quotes: int = 3,
) -> list[SupportQuote]:
    """Find quotes in transcript that support a claim.

    Uses fuzzy matching to find transcript segments that support the claim.
    This is a fallback when LLM doesn't provide character offsets.

    Args:
        claim: The claim to find support for.
        transcript: Full transcript text.
        max_quotes: Maximum quotes to return.

    Returns:
        List of SupportQuote objects with character positions.
    """
    quotes: list[SupportQuote] = []

    if not transcript:
        return quotes

    # Extract key words from claim, stripping punctuation
    claim_words = set(re.findall(r'\b\w+\b', claim.lower()))
    # Remove common words
    common_words = {"the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
                    "have", "has", "had", "do", "does", "did", "that", "this", "it", "and",
                    "or", "but", "in", "on", "at", "to", "for", "of", "with", "by"}
    key_words = claim_words - common_words

    if not key_words:
        return quotes

    # Split transcript into sentences
    sentences = re.split(r'(?<=[.!?])\s+', transcript)

    scored_sentences: list[tuple[float, str, int, int]] = []
    current_pos = 0

    for sentence in sentences:
        # Extract words from sentence, stripping punctuation
        sentence_words = set(re.findall(r'\b\w+\b', sentence.lower()))

        # Score by word overlap
        overlap = len(key_words & sentence_words)
        if overlap > 0:
            score = overlap / len(key_words)
            start_char = transcript.find(sentence, current_pos)
            if start_char != -1:
                scored_sentences.append((score, sentence, start_char, start_char + len(sentence)))

        current_pos += len(sentence) + 1

    # Sort by score and take top matches
    scored_sentences.sort(reverse=True, key=lambda x: x[0])

    for score, sentence, start, end in scored_sentences[:max_quotes]:
        if score >= 0.3:  # Minimum threshold
            quotes.append(SupportQuote(
                quote=sentence.strip(),
                start_char=start,
                end_char=end,
            ))

    return quotes


# ==============================================================================
# Empty Evidence Handling (T021)
# ==============================================================================

def handle_empty_evidence(
    chapter_evidence: ChapterEvidence,
    chapter_title: str,
    content_mode: ContentMode = ContentMode.interview,
    min_claims: int = 1,
) -> ChapterEvidence:
    """Handle chapters with no or insufficient evidence.

    Implements FR-009a: skip/merge chapter logic with warning emission.

    Args:
        chapter_evidence: The chapter evidence to check.
        chapter_title: Chapter title for logging.
        content_mode: Content mode for context.
        min_claims: Minimum claims required.

    Returns:
        Updated ChapterEvidence (may add warning must-include item).
    """
    if len(chapter_evidence.claims) >= min_claims:
        return chapter_evidence

    logger.warning(
        f"Chapter '{chapter_title}' has insufficient evidence "
        f"({len(chapter_evidence.claims)} claims, minimum {min_claims})"
    )

    # Add a warning must-include item
    warning_item = MustIncludeItem(
        point=f"[SPARSE EVIDENCE] This chapter has limited transcript coverage. "
              f"Consider merging with adjacent chapter or keeping brief.",
        priority=MustIncludePriority.important,
        evidence_ids=[],
    )

    chapter_evidence.must_include.append(warning_item)

    return chapter_evidence


# ==============================================================================
# Content Mode Detection (T022)
# ==============================================================================

def detect_content_type(transcript: str) -> tuple[ContentMode, float]:
    """Analyze transcript to detect most likely content mode.

    Uses heuristics to determine if content is interview-style,
    essay/article, or tutorial/instructional.

    Args:
        transcript: Full transcript text.

    Returns:
        Tuple of (detected mode, confidence score 0-1).
    """
    transcript_lower = transcript.lower()

    # Interview indicators
    interview_patterns = [
        r"\b(interviewer|host|guest|speaker)\s*:",
        r"thank you for (joining|being here|having me)",
        r"\b(q|a)\s*:",
        r"(tell us|share with us|explain to us)",
        r"(we're here with|joining us today)",
        r"(what do you think|how would you)",
    ]

    # Tutorial indicators
    tutorial_patterns = [
        r"(step \d|first,? |second,? |third,? |finally,? )",
        r"(how to|let's |now we |you should|you need to)",
        r"(click on|navigate to|enter the|type in)",
        r"(in this (tutorial|lesson|guide))",
        r"(make sure|don't forget|remember to)",
    ]

    # Essay indicators
    essay_patterns = [
        r"(in conclusion|to summarize|in summary)",
        r"(this paper|this article|this essay)",
        r"(we argue|we propose|we demonstrate)",
        r"(evidence suggests|research shows|studies indicate)",
        r"(furthermore|moreover|nevertheless|however)",
    ]

    def count_matches(patterns: list[str]) -> int:
        return sum(len(re.findall(p, transcript_lower)) for p in patterns)

    interview_score = count_matches(interview_patterns)
    tutorial_score = count_matches(tutorial_patterns)
    essay_score = count_matches(essay_patterns)

    total = interview_score + tutorial_score + essay_score + 1  # +1 to avoid division by zero

    if interview_score >= tutorial_score and interview_score >= essay_score:
        return ContentMode.interview, interview_score / total
    elif tutorial_score >= essay_score:
        return ContentMode.tutorial, tutorial_score / total
    else:
        return ContentMode.essay, essay_score / total


def generate_mode_warning(
    detected_mode: ContentMode,
    configured_mode: ContentMode,
    confidence: float,
) -> Optional[str]:
    """Generate warning if detected mode differs from configured mode.

    Args:
        detected_mode: Mode detected from content analysis.
        configured_mode: Mode configured by user.
        confidence: Confidence of detection.

    Returns:
        Warning message if modes differ, None otherwise.
    """
    if detected_mode == configured_mode:
        return None

    if confidence < 0.3:
        # Low confidence, don't warn
        return None

    return (
        f"Content appears to be {detected_mode.value}-style "
        f"(confidence: {confidence:.0%}), but {configured_mode.value} mode "
        f"is configured. Consider changing Content Mode for better results."
    )


# ==============================================================================
# Interview Mode Constraint Checking (T024)
# ==============================================================================

def check_interview_constraints(
    text: str,
    raise_on_violation: bool = False,
) -> list[dict]:
    """Check text for interview mode constraint violations.

    Scans text for patterns that shouldn't appear in interview-mode drafts:
    - Action steps / how-to instructions
    - Biographical details not from transcript
    - Motivational platitudes

    Args:
        text: Text to check (draft content).
        raise_on_violation: If True, raise on first violation.

    Returns:
        List of violation dicts with pattern, match, and location.
    """
    violations: list[dict] = []

    for pattern in INTERVIEW_FORBIDDEN_PATTERNS:
        try:
            for match in re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE):
                violation = {
                    "pattern": pattern,
                    "matched_text": match.group(),
                    "start": match.start(),
                    "end": match.end(),
                    "context": text[max(0, match.start()-50):match.end()+50],
                }
                violations.append(violation)

                if raise_on_violation:
                    raise InterviewConstraintViolation(
                        f"Interview mode violation: '{match.group()}' at position {match.start()}"
                    )
        except re.error as e:
            logger.warning(f"Invalid regex pattern '{pattern}': {e}")
            continue

    return violations


class InterviewConstraintViolation(Exception):
    """Raised when interview mode constraints are violated."""
    pass


# ==============================================================================
# Global Context Extraction
# ==============================================================================

async def _extract_global_context(transcript: str) -> GlobalContext:
    """Extract global context (speakers, topics) from transcript.

    This is a lightweight extraction for cross-chapter context.

    Args:
        transcript: Full transcript text.

    Returns:
        GlobalContext with speakers and topics.
    """
    # Simple heuristic extraction (could be enhanced with LLM)
    speakers: list[SpeakerInfo] = []

    # Look for speaker patterns like "Name:" or "[Name]"
    speaker_patterns = [
        r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*:',  # "John Smith:"
        r'\[([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\]',    # "[John Smith]"
    ]

    found_speakers: set[str] = set()
    for pattern in speaker_patterns:
        for match in re.finditer(pattern, transcript, re.MULTILINE):
            name = match.group(1)
            if name not in found_speakers and len(name) > 2:
                found_speakers.add(name)
                speakers.append(SpeakerInfo(name=name))

    # Extract main topics (simplified - look for repeated significant words)
    words = re.findall(r'\b[A-Za-z]{5,}\b', transcript.lower())
    word_freq = {}
    for word in words:
        if word not in {"about", "would", "could", "should", "their", "there", "where", "which", "being", "these", "those"}:
            word_freq[word] = word_freq.get(word, 0) + 1

    # Top topics by frequency
    sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
    main_topics = [word for word, _ in sorted_words[:10]]

    return GlobalContext(
        speakers=speakers[:5],  # Max 5 speakers
        main_topics=main_topics[:10],  # Max 10 topics
    )


# ==============================================================================
# Evidence Map Utilities
# ==============================================================================

def get_evidence_for_chapter(
    evidence_map: EvidenceMap,
    chapter_index: int,
) -> Optional[ChapterEvidence]:
    """Get evidence for a specific chapter.

    Args:
        evidence_map: The full Evidence Map.
        chapter_index: 1-based chapter index.

    Returns:
        ChapterEvidence or None if not found.
    """
    for chapter in evidence_map.chapters:
        if chapter.chapter_index == chapter_index:
            return chapter
    return None


def count_total_claims(evidence_map: EvidenceMap) -> int:
    """Count total claims across all chapters.

    Args:
        evidence_map: The Evidence Map.

    Returns:
        Total claim count.
    """
    return sum(len(chapter.claims) for chapter in evidence_map.chapters)


def evidence_map_to_summary(evidence_map: EvidenceMap) -> dict:
    """Convert Evidence Map to summary for API response.

    Args:
        evidence_map: Full Evidence Map.

    Returns:
        Summary dict suitable for status responses.
    """
    return {
        "total_claims": count_total_claims(evidence_map),
        "chapters": len(evidence_map.chapters),
        "content_mode": evidence_map.content_mode.value,
        "strict_grounded": evidence_map.strict_grounded,
        "transcript_hash": evidence_map.transcript_hash,
        "per_chapter_claims": [
            {
                "chapter": ch.chapter_index,
                "title": ch.chapter_title,
                "claims": len(ch.claims),
                "must_include": len(ch.must_include),
            }
            for ch in evidence_map.chapters
        ],
    }
