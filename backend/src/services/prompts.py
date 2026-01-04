"""Prompt templates for AI draft generation.

Contains system and user prompts for:
1. DraftPlan generation - creating the chapter structure and mappings
2. Chapter generation - writing individual chapters
"""

from __future__ import annotations

import json
from typing import Any, Optional

from typing import List
from src.models import ChapterPlan, StyleConfig, StyleConfigEnvelope, TranscriptSegment


# ==============================================================================
# DraftPlan Prompts
# ==============================================================================

DRAFT_PLAN_SYSTEM_PROMPT = """You are an expert ebook architect. Given a webinar transcript and outline, create a detailed generation plan.

Your task:
1. Analyze the transcript content and map it to the provided outline
2. For each chapter, identify the relevant transcript segments (character ranges)
3. Define 2-4 learning goals and 3-6 key points per chapter
4. Suggest visual opportunities where images would enhance understanding
5. Estimate word counts based on source material density

Rules:
- Map ALL substantial transcript content to chapters
- transcript_segments use character indices (start_char, end_char)
- Visual opportunities are suggestions only - no placeholders in content
- Respect the style configuration for tone and structure
- Be precise with transcript mappings - no hallucinated quotes
- chapter_index for visuals is 1-based
- Generate visual opportunities based on visual_density setting:
  - "none": Generate 0 opportunities
  - "light": 1-2 per 3 chapters
  - "medium": 1-2 per chapter
  - "heavy": 2-4 per chapter"""


def build_draft_plan_user_prompt(
    transcript: str,
    outline: list[dict],
    style_config: dict,
    assets: Optional[list[dict]] = None,
) -> str:
    """Build user prompt for DraftPlan generation.

    Args:
        transcript: Full transcript text.
        outline: List of outline items.
        style_config: StyleConfig or StyleConfigEnvelope dict.
        assets: Optional list of available visual assets.

    Returns:
        Formatted user prompt string.
    """
    # Extract style config if wrapped in envelope
    if "style" in style_config:
        style_dict = style_config.get("style", {})
    else:
        style_dict = style_config

    parts = [
        "## Transcript",
        f"```\n{transcript}\n```",
        "",
        "## Outline",
        f"```json\n{json.dumps(outline, indent=2)}\n```",
        "",
        "## Style Configuration",
        f"```json\n{json.dumps(style_dict, indent=2)}\n```",
    ]

    if assets:
        parts.extend([
            "",
            "## Available Visual Assets",
            f"```json\n{json.dumps(assets, indent=2)}\n```",
            "",
            "Match visual opportunities to available assets when possible by populating candidate_asset_ids.",
        ])

    parts.extend([
        "",
        "Generate a DraftPlan following the provided schema.",
        "Ensure all transcript content is mapped to chapters via transcript_segments.",
    ])

    return "\n".join(parts)


# ==============================================================================
# Visual Opportunity Prompts
# ==============================================================================

VISUAL_OPPORTUNITY_SYSTEM_PROMPT = """You are an expert at identifying where visual elements would enhance an ebook.

Your task is to analyze chapter content and suggest visual opportunities - places where diagrams, charts, screenshots, or other visuals would help readers understand the material better.

For each opportunity, provide:
- chapter_index: Which chapter (1-based)
- visual_type: One of: screenshot, diagram, chart, table, icon, photo, other
- title: Short title for the visual (2-6 words)
- prompt: What the visual should show
- caption: Caption text to display under the visual
- rationale: Why this visual helps the reader
- confidence: How confident you are this visual would help (0.0-1.0)

Focus on:
- Complex concepts that benefit from visualization
- Processes or workflows that could be shown as diagrams
- Data or comparisons that work well as charts/tables
- UI elements or tools mentioned that could use screenshots
- Key frameworks or models that benefit from visual representation

Do NOT suggest visuals for:
- Simple concepts easily understood from text
- Generic decorative images
- Content where a visual adds no educational value"""


# Density guidelines for opportunity count
VISUAL_DENSITY_GUIDANCE = {
    "light": "Generate 1-2 visual opportunities total across all chapters. Only suggest visuals for the most impactful moments.",
    "medium": "Generate approximately 1-2 visual opportunities per chapter. Focus on key concepts and processes.",
    "heavy": "Generate 2-4 visual opportunities per chapter. Be thorough in identifying visualization opportunities.",
}


def build_visual_opportunity_user_prompt(
    chapters: list[ChapterPlan],
    visual_density: str,
) -> str:
    """Build user prompt for visual opportunity generation.

    Args:
        chapters: List of chapter plans with titles and key points.
        visual_density: One of 'light', 'medium', 'heavy'.

    Returns:
        Formatted user prompt string.
    """
    density_guidance = VISUAL_DENSITY_GUIDANCE.get(
        visual_density,
        VISUAL_DENSITY_GUIDANCE["medium"]
    )

    parts = [
        "## Density Guidance",
        density_guidance,
        "",
        "## Chapters to Analyze",
        "",
    ]

    for chapter in chapters:
        parts.append(f"### Chapter {chapter.chapter_number}: {chapter.title}")
        if chapter.key_points:
            parts.append("Key points:")
            for point in chapter.key_points:
                parts.append(f"- {point}")
        parts.append("")

    parts.extend([
        "## Instructions",
        "Analyze the chapters above and generate visual opportunities.",
        "Return a JSON object with an 'opportunities' array.",
        f"Remember: {density_guidance}",
    ])

    return "\n".join(parts)


# ==============================================================================
# Chapter Generation Prompts
# ==============================================================================

def build_chapter_system_prompt(
    book_title: str,
    chapter_number: int,
    style_config: dict,
    words_per_chapter_target: int = 625,
    detail_level: str = "balanced",
) -> str:
    """Build system prompt for chapter generation.

    Args:
        book_title: Title of the ebook.
        chapter_number: 1-based chapter number.
        style_config: StyleConfig dict (unwrapped from envelope).
        words_per_chapter_target: Target word count for this chapter.
        detail_level: Detail level (concise/balanced/detailed).

    Returns:
        Formatted system prompt string.
    """
    # Extract style values with defaults
    target_audience = style_config.get("target_audience", "general_professional")
    tone = style_config.get("tone", "conversational")
    formality = style_config.get("formality", "conversational")
    reading_level = style_config.get("reading_level", "college")
    faithfulness = style_config.get("faithfulness_level", "faithful_with_polish")
    avoid_hallucinations = style_config.get("avoid_hallucinations", True)
    citation_style = style_config.get("citation_style", "none")
    include_summary = style_config.get("include_summary_per_chapter", False)
    include_takeaways = style_config.get("include_key_takeaways", False)
    include_actions = style_config.get("include_action_steps", False)

    # Detail level guidance
    detail_guidance = {
        "concise": "Be concise: fewer examples, tighter bullet points, avoid tangents. Focus on key points only.",
        "balanced": "Use a balanced approach: normal explanatory tone with clear examples where helpful.",
        "detailed": "Be detailed: include more examples, step-by-step explanations, frameworks, and checklists where relevant.",
    }
    detail_instruction = detail_guidance.get(detail_level, detail_guidance["balanced"])

    lines = [
        f'You are writing chapter {chapter_number} of an ebook titled "{book_title}".',
        "",
        "Length and detail:",
        f"- Target length: approximately {words_per_chapter_target} words for this chapter",
        f"- Detail level: {detail_level}",
        f"- {detail_instruction}",
        "",
        "Writing style:",
        f"- Target audience: {target_audience}",
        f"- Tone: {tone}",
        f"- Formality: {formality}",
        f"- Reading level: {reading_level}",
        "",
        "Structure guidelines:",
        f"- Chapter heading: ## Chapter {chapter_number}: [Title]",
        "- Use ### for sections, #### for subsections (no deeper)",
    ]

    if include_summary:
        lines.append("- Include a brief summary at chapter start")
    if include_takeaways:
        lines.append("- End with key takeaways in a bulleted list")
    if include_actions:
        lines.append("- Include actionable steps readers can follow")

    lines.extend([
        "",
        "Source fidelity:",
        f"- Faithfulness: {faithfulness}",
    ])

    if avoid_hallucinations:
        lines.append("- Only include information from the provided transcript")
    if citation_style != "none":
        lines.append(f"- Cite sources: {citation_style}")

    lines.extend([
        "",
        "IMPORTANT: DO NOT include visual placeholders like [IMAGE], VISUAL_SLOT, or similar markers.",
        "Write flowing prose - visuals will be added separately.",
    ])

    return "\n".join(lines)


def build_chapter_user_prompt(
    chapter_plan: ChapterPlan,
    transcript_segment: str,
    previous_chapter_ending: Optional[str] = None,
    next_chapter_preview: Optional[tuple[str, list[str]]] = None,
) -> str:
    """Build user prompt for chapter generation.

    Args:
        chapter_plan: The ChapterPlan for this chapter.
        transcript_segment: The mapped transcript text for this chapter.
        previous_chapter_ending: Last 2 paragraphs of previous chapter (for continuity).
        next_chapter_preview: Tuple of (title, first_points) for next chapter (for setup).

    Returns:
        Formatted user prompt string.
    """
    parts = [
        "## Your Goals for This Chapter",
    ]

    if chapter_plan.goals:
        for goal in chapter_plan.goals:
            parts.append(f"- {goal}")
    else:
        parts.append("- Cover the key content from the transcript segment")

    parts.extend([
        "",
        "## Key Points to Cover",
    ])

    if chapter_plan.key_points:
        for point in chapter_plan.key_points:
            parts.append(f"- {point}")
    else:
        parts.append("- Extract and organize the main ideas from the transcript")

    parts.extend([
        "",
        "## Source Material (Transcript Segment)",
        f"```\n{transcript_segment}\n```",
    ])

    if previous_chapter_ending:
        parts.extend([
            "",
            "## Context: Previous Chapter Ending",
            "Ensure continuity with how the previous chapter concluded:",
            f"```\n{previous_chapter_ending}\n```",
        ])

    if next_chapter_preview:
        next_title, next_points = next_chapter_preview
        parts.extend([
            "",
            "## Context: Next Chapter Preview",
            f'Next chapter: "{next_title}"',
        ])
        if next_points:
            parts.append(f"Topics: {', '.join(next_points[:3])}")

    parts.extend([
        "",
        f"Write Chapter {chapter_plan.chapter_number}: {chapter_plan.title}",
    ])

    return "\n".join(parts)


def extract_transcript_segment(
    transcript: str,
    chapter_plan: ChapterPlan,
) -> str:
    """Extract the transcript segment for a chapter.

    Args:
        transcript: Full transcript text.
        chapter_plan: The chapter plan with transcript_segments.

    Returns:
        The concatenated transcript text for this chapter.
    """
    if not chapter_plan.transcript_segments:
        # Fallback: use entire transcript (not ideal)
        return transcript

    segments = []
    for seg in chapter_plan.transcript_segments:
        start = max(0, seg.start_char)
        end = min(len(transcript), seg.end_char)
        if start < end:
            segments.append(transcript[start:end])

    return "\n\n---\n\n".join(segments) if segments else transcript


def get_previous_chapter_ending(
    chapters_completed: list[str],
    num_paragraphs: int = 2,
) -> Optional[str]:
    """Get the last paragraphs of the previous chapter for continuity.

    Args:
        chapters_completed: List of completed chapter markdown strings.
        num_paragraphs: Number of paragraphs to include.

    Returns:
        The last paragraphs, or None if no previous chapter.
    """
    if not chapters_completed:
        return None

    last_chapter = chapters_completed[-1]
    paragraphs = [p.strip() for p in last_chapter.split("\n\n") if p.strip()]

    if not paragraphs:
        return None

    # Get last N paragraphs, excluding headings
    content_paragraphs = [
        p for p in paragraphs
        if not p.startswith("#")
    ]

    if not content_paragraphs:
        return None

    return "\n\n".join(content_paragraphs[-num_paragraphs:])


def get_next_chapter_preview(
    chapters: list[ChapterPlan],
    current_index: int,
) -> Optional[tuple[str, list[str]]]:
    """Get preview of the next chapter for setup.

    Args:
        chapters: All chapter plans.
        current_index: 0-based index of current chapter.

    Returns:
        Tuple of (title, first_key_points), or None if no next chapter.
    """
    next_index = current_index + 1
    if next_index >= len(chapters):
        return None

    next_chapter = chapters[next_index]
    return (next_chapter.title, next_chapter.key_points[:3])


# ==============================================================================
# Outline-Driven Chapter Structure
# ==============================================================================

def parse_outline_to_chapters(
    outline: list[dict],
    transcript: str,
) -> list[ChapterPlan]:
    """Parse outline into chapters based on structure.

    Top-level items (level=1) become chapters.
    Nested items (level>1) become section hints within chapters.
    Transcript is split proportionally among chapters.

    Args:
        outline: List of outline item dicts with id, title, level, order.
        transcript: Full transcript text for proportional mapping.

    Returns:
        List of ChapterPlan objects with basic structure.
    """
    if not outline:
        return []

    # Sort outline by order
    sorted_outline = sorted(outline, key=lambda x: x.get("order", 0))

    # Find top-level items (chapters) and group sub-items
    chapters: list[ChapterPlan] = []
    current_sections: list[dict] = []
    chapter_number = 0

    for item in sorted_outline:
        level = item.get("level", 1)

        if level == 1:
            # This is a chapter
            chapter_number += 1

            # Create chapter plan with sections from previous accumulation
            chapter = ChapterPlan(
                chapter_number=chapter_number,
                title=item.get("title", f"Chapter {chapter_number}"),
                outline_item_id=item.get("id", f"ch-{chapter_number}"),
                goals=[],  # Will be populated later
                key_points=[],  # Populated from sections
                transcript_segments=[],  # Will be mapped below
                estimated_words=1500,
            )
            chapters.append(chapter)
            current_sections = []

        else:
            # This is a sub-section - add to current chapter's key points
            if chapters:
                section_title = item.get("title", "")
                notes = item.get("notes", "")
                if section_title:
                    key_point = section_title
                    if notes:
                        key_point = f"{section_title}: {notes}"
                    chapters[-1].key_points.append(key_point)

    # Map transcript proportionally to chapters
    if chapters and transcript:
        _map_transcript_to_chapters(chapters, transcript)

    return chapters


def _map_transcript_to_chapters(
    chapters: list[ChapterPlan],
    transcript: str,
) -> None:
    """Distribute transcript content proportionally among chapters.

    Simple proportional split based on number of chapters.
    Could be enhanced with keyword matching in the future.

    Args:
        chapters: List of ChapterPlan objects to update in place.
        transcript: Full transcript text.
    """
    if not chapters or not transcript:
        return

    total_len = len(transcript)
    segment_size = total_len // len(chapters)

    for i, chapter in enumerate(chapters):
        start = i * segment_size
        # Last chapter gets all remaining content
        end = total_len if i == len(chapters) - 1 else (i + 1) * segment_size

        chapter.transcript_segments = [
            TranscriptSegment(
                start_char=start,
                end_char=end,
                relevance="primary",
            )
        ]
        # Estimate words based on transcript segment length (rough: 5 chars per word)
        chapter.estimated_words = max(500, (end - start) // 5)


def build_chapter_enhancement_prompt(
    chapter: ChapterPlan,
    transcript_segment: str,
) -> str:
    """Build prompt to enhance a chapter with goals and additional key points.

    Args:
        chapter: Basic ChapterPlan from outline.
        transcript_segment: The mapped transcript text.

    Returns:
        Prompt for LLM to generate goals and key points.
    """
    return f"""Based on this chapter outline and transcript segment, generate:
1. 2-4 learning goals for the reader
2. Additional key points beyond those already listed

Chapter: {chapter.title}
Existing key points: {json.dumps(chapter.key_points)}

Transcript segment:
```
{transcript_segment[:3000]}...
```

Respond with JSON: {{"goals": ["goal1", ...], "additional_key_points": ["point1", ...]}}"""


# ==============================================================================
# Interview Q&A Prompts (book_format: interview_qa)
# ==============================================================================

INTERVIEW_QA_SYSTEM_PROMPT = """You are formatting an interview transcript into a readable Q&A ebook.

Your task is to preserve the interview's natural question-and-answer structure while making it
readable and engaging. The speaker's voice, insights, and personality should shine through.

## Output Structure

Organize content using this hierarchy:
- ## Topic headers (h2) - Group related questions by theme
- ### Question headers (h3) - Each question from the host becomes a section header
- Body text - The speaker's response, edited for readability but preserving their voice
- > Blockquotes - Use for particularly notable or quotable statements

## Formatting Guidelines

1. **Question headers**: Rephrase host questions as engaging section headers at ### level
   - Original: "Host: So how did you get started in physics?"
   - Header: "### How did you get started in physics?"

2. **Speaker voice**: Preserve the speaker's actual words and phrasing
   - Clean up verbal tics (um, uh, you know) for readability
   - Keep distinctive phrases and expressions
   - Maintain the conversational, authentic feel

3. **Blockquotes**: Use for memorable, quotable statements
   - Select 1-3 standout quotes per topic section
   - Choose statements that capture key insights or the speaker's character

4. **Topic grouping**: Group related Q&A exchanges under ## topic headers
   - Use natural themes that emerge from the conversation
   - 2-5 questions per topic section is typical

## Forbidden Patterns

Do NOT include:
- "Key Takeaways" sections - this is not a how-to guide
- "Action Steps" or "Action Items" - this is a conversation, not a tutorial
- "Summary" sections - let the conversation speak for itself
- Bullet lists of "lessons learned" - avoid reducing insights to listicles
- Invented biographical information - only use what the speaker actually says
- Generic platitudes or filler text

The goal is to preserve the authentic interview experience while making it readable as an ebook."""


def build_interview_qa_system_prompt(
    book_title: str,
    speaker_name: str,
) -> str:
    """Build system prompt for Interview Q&A format generation.

    Args:
        book_title: Title of the ebook.
        speaker_name: Name of the interview subject/speaker.

    Returns:
        Formatted system prompt string.
    """
    return f"""{INTERVIEW_QA_SYSTEM_PROMPT}

## Book Context

- Book title: "{book_title}"
- Primary speaker: {speaker_name}

Attribute insights and quotes to {speaker_name}. Use their name naturally in the text
where attribution adds clarity."""


def build_interview_qa_chapter_prompt(
    chapter_plan: ChapterPlan,
    transcript_segment: str,
    speaker_name: str,
) -> str:
    """Build user prompt for Interview Q&A chapter generation.

    This prompt instructs the LLM to:
    - Extract questions from the transcript as section headers
    - Group questions by topic/theme
    - Preserve the speaker's voice with selective blockquotes

    Args:
        chapter_plan: The ChapterPlan for this chapter.
        transcript_segment: The mapped transcript text for this chapter.
        speaker_name: Name of the speaker for attribution.

    Returns:
        Formatted user prompt string.
    """
    parts = [
        f"## Chapter: {chapter_plan.title}",
        "",
        "## Instructions",
        "",
        "Transform this transcript segment into Q&A format:",
        "",
        "1. **Identify questions**: Find each question posed by the host",
        "2. **Create ### headers**: Convert questions into engaging section headers",
        "3. **Preserve answers**: Edit the speaker's responses for readability while keeping their voice",
        "4. **Add blockquotes**: Mark 1-3 particularly notable statements with > blockquotes",
        f"5. **Attribution**: Attribute insights to {speaker_name} where helpful",
        "",
        "## Topic Guidance",
    ]

    if chapter_plan.key_points:
        parts.append("")
        parts.append("This chapter should cover these topics:")
        for point in chapter_plan.key_points:
            parts.append(f"- {point}")

    parts.extend([
        "",
        "## Transcript Segment",
        f"```",
        transcript_segment,
        "```",
        "",
        "## Output Format",
        "",
        "Use this structure:",
        "```",
        "## [Topic Theme]",
        "",
        "### [Question as header]",
        "",
        "[Speaker's response, edited for readability]",
        "",
        "> [Notable quote from speaker]",
        "",
        "### [Next question]",
        "...",
        "```",
        "",
        f"Write Chapter {chapter_plan.chapter_number}: {chapter_plan.title}",
    ])

    return "\n".join(parts)
