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
    book_format = style_config.get("book_format", "guide")

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

    # Prose style guidance - always included, stronger for essay format
    lines.extend([
        "",
        "PROSE QUALITY:",
        "- Write with confidence and precision. No hedging phrases.",
        "- Vary sentence length and structure. Mix short punchy sentences with longer flowing ones.",
        "- Start paragraphs differently - avoid repetitive openers.",
        "- Use concrete examples before abstractions.",
        "- Trust the reader's intelligence - don't over-explain or recap what was just said.",
        "",
        "BANNED PHRASES (never use these):",
        '- "In conclusion", "To conclude", "In summary"',
        '- "Moreover", "Furthermore", "Additionally", "However" as sentence starters',
        '- "It is important to note", "It should be noted"',
        '- "This highlights", "This demonstrates", "This shows"',
        '- "As mentioned earlier", "As we discussed"',
        '- "Let\'s explore", "Let\'s dive into", "Let\'s take a look"',
    ])

    # Explicit forbid for essay format or when takeaways/actions are disabled
    if book_format == "essay" or (not include_takeaways and not include_actions):
        lines.extend([
            "",
            "FORBIDDEN SECTIONS (do NOT include these):",
            '- "Key Takeaways" or "Takeaways" sections',
            '- "Action Steps", "Action Items", or "Actionable Steps" sections',
            '- Bullet-point summaries at chapter end',
            '- Template conclusions that recap the chapter',
            "- Any wrap-up section with numbered or bulleted lists",
            "",
            "Instead, end chapters with flowing prose that transitions naturally or leaves the reader with a thought-provoking insight.",
        ])

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


# ==============================================================================
# Interview Mode Single-Pass Generation (P0: New Output Template)
# ==============================================================================

INTERVIEW_GROUNDED_SYSTEM_PROMPT = """You are transforming an interview transcript into an ebook with a SPECIFIC two-part structure.

## Output Structure (MANDATORY)

Your output MUST have exactly these two sections:

### Part 1: Key Ideas (Grounded)
A list of 5-10 bullet points capturing the speaker's most important ideas.
EVERY bullet MUST include an inline quote (max 40 words) from the transcript as evidence.

**CRITICAL - INTELLECTUAL SPINE FIRST**: The first 2-3 Key Ideas MUST capture the speaker's CORE FRAMEWORK - the foundational concepts that make their thinking distinctive. Ask yourself:

1. **What is their central METHOD or CRITERION?** (e.g., "good explanations vs bad explanations", "first principles thinking", "skin in the game")
2. **What key DISTINCTION do they introduce?** (e.g., "finite vs infinite", "fragile vs antifragile", "known vs knowable")
3. **What is their MAIN THESIS?** (e.g., "progress is unlimited", "randomness is misunderstood")

These core concepts are the "intellectual spine" - the ideas that all their other points hang on. Surface these FIRST, before covering specific applications or examples.

If the speaker defines a term or introduces a framework (like "what makes an explanation good"), that definition MUST appear in Key Ideas.

Format each bullet as:
- **[Idea statement]**: "[exact verbatim quote from transcript]"

### Part 2: The Conversation
The full interview formatted as readable Q&A, organized by topic.

## Critical Rules

1. **Inline Quotes are MANDATORY**: Every Key Idea bullet MUST contain a direct quote
2. **No Chapters**: Do NOT use "Chapter 1", "Chapter 2" etc. - use topic headers instead
3. **No Action Steps**: This is NOT a how-to guide. No "Key Takeaways", "Action Items", or "Steps to..."
4. **No Biography**: Do NOT invent speaker background unless EXPLICITLY stated in transcript
5. **No Platitudes**: No generic wisdom like "believe in yourself" or "the key to success is..."
6. **Bullet #1 MUST be definitional/criterial**: The FIRST Key Idea must quote a line where the speaker DEFINES, DISTINGUISHES, or EXPLAINS THEIR METHOD. Look for phrases like "is essentially", "rather than", "the method is", "what makes X good/bad".
7. **No generic textbook definitions**: Do NOT use generic phrases like "Science is about finding laws of nature" when the speaker provides a SHARPER criterion (like "good explanations rather than bad explanations"). Always prefer the more distinctive, quotable line.

## Quote Hygiene (CRITICAL)

**Only use quotation marks for VERBATIM transcript excerpts.**

- ✅ CORRECT: "This line is the most important thing that's ever happened" (exact words from transcript)
- ❌ WRONG: "The Enlightenment was transformative" (paraphrase presented as quote)
- ❌ WRONG: "Since the revolution, he says, things changed" (narration inside quotes - NEVER do this)
- ❌ WRONG: "...would not have changed and would not..." (truncated mid-sentence)

**Rules:**
1. Every quoted string must be a contiguous excerpt that actually appears in the transcript
2. NEVER include narration like "he says", "she notes", "they explained" INSIDE quotation marks
3. Quotes must be COMPLETE SENTENCES - never truncate mid-thought (use ellipsis "..." only at natural breaks)
4. If you're paraphrasing, do NOT use quotation marks - write it as plain text instead

## Attribution Rules

When referencing what the speaker said, you MAY use phrases like:
- "As [Name] explains, ..."
- "[Name] notes that ..."
- "According to [Name], ..."

Do NOT use distancing language like:
- "[Name] believes..." (implies skepticism)
- "[Name] argues..." (implies contentiousness)
- "[Name] emphasizes..." (vague, often used to pad)

The speaker is sharing their experience and insights - present them directly.

## Structure Template

**IMPORTANT**: Start with an H1 title using the BOOK TITLE provided in the Book Context section below.
Do NOT use generic titles like "# Interview" or "# Interview Transcript".
Use the actual book title: "# {book_title}" (the title will be provided in Book Context).

```markdown
# {Book Title from Context}

## Key Ideas (Grounded)

- **Good explanations vs vague ones**: "We discovered this method—the scientific method—which I think is essentially trying to find good explanations of what happens rather than bad explanations."
- **After the Enlightenment, improvement became the norm**: "We have learned to live with the fact that everything improves in every generation."
- **We still have a choice**: "We don't have to jump on this bandwagon of this built-in potential of the universe if we don't want to."
- **Wisdom is not static**: "The truth of the matter is that wisdom, like scientific knowledge, is also limitless."
... (5-10 bullets total - core concepts FIRST, then supporting ideas)
```

**Key Ideas label rules:**
- Labels should be SHORT, PLAIN ENGLISH summaries (5-10 words max)
- NO meta-language like "The speaker's central METHOD" or "A KEY DISTINCTION"
- NO all-caps words like "CRITERION" or "THESIS"
- The label should MATCH the quote's actual content
- Think: what would a newspaper headline say?

**BAD labels** (too meta, too shouty):
- "The speaker's central METHOD/CRITERION for evaluating ideas"
- "A KEY DISTINCTION introduced regarding human potential"
- "Their MAIN THESIS about wisdom"

**GOOD labels** (plain, specific, human):
- "Good explanations vs vague ones"
- "Progress became the expectation after the Enlightenment"
- "We have a choice about our future"

## The Conversation

Format as Q&A preserving the EXACT questions and COMPLETE answers from the transcript.

```markdown
### You draw an enormous line through human history at the Enlightenment and Scientific Revolution. Describe the before and after a little bit for us in broad strokes.

**GUEST:** This line is the most important thing that's ever happened because prior to it, the world was static in terms of ideas. Things did improve, but from the point of view of any individual, the technology, the economics, the ways of life—everything they could notice about the world—would not have changed and would not have improved. After the Enlightenment, it was the exact opposite. We have learned to live with the fact that everything improves in every generation. What's more, previous ways of life become unviable as better ways of life appear. This staticity was a horrible practical joke played on the human race by nature because, for hundreds of thousands of years, we had the capacity to improve, to reduce human suffering, to increase our knowledge of the world, but almost none of that happened. Then suddenly, there was this explosion where it has happened.

### It's not just a matter of us then going on to develop all kinds of technology from microwave ovens to high-speed cars. You say that this change introduced us or created the beginning of infinity, the title of your book. What do you mean by that?

**GUEST:** The phrase "the beginning of infinity" primarily means the universal power of explanatory knowledge. It turned out—and I didn't really plan this when I wrote the book—but it turned out that in every chapter, there were several different meanings, several different senses in which there was a beginning of infinity, which hadn't happened before: either a condition for unlimited progress or a beginning of unlimited progress or the sense in which progress can be unlimited.
```

**CRITICAL RULES**:
1. Use `### [EXACT question from transcript]` - copy the host's question VERBATIM, do not paraphrase
2. Use `**GUEST:**` for ALL answers (not the speaker's name)
3. Include the COMPLETE answer - do NOT summarize or truncate
4. NO topic grouping headers (no "### The Enlightenment" section headers) - just Q&A pairs
5. Quote blocks (> "...") are optional highlights only
"""


def build_interview_grounded_system_prompt(
    book_title: str,
    speaker_name: str,
) -> str:
    """Build system prompt for grounded interview generation (P0 format).

    This produces the new output structure:
    - ## Key Ideas (Grounded) - with inline quotes
    - ## The Conversation - Q&A format

    Args:
        book_title: Title of the ebook.
        speaker_name: Name of the interview subject/speaker.

    Returns:
        Formatted system prompt string.
    """
    return f"""{INTERVIEW_GROUNDED_SYSTEM_PROMPT}

## Book Context

- **Book title (USE THIS AS H1)**: "{book_title}"
- Primary speaker: {speaker_name}

**START YOUR OUTPUT WITH**: # {book_title}

All quotes should be from {speaker_name} unless otherwise indicated.
Use {speaker_name}'s name naturally in the text for attribution."""


def build_interview_grounded_user_prompt(
    transcript: str,
    speaker_name: str,
    evidence_claims: list[dict],
) -> str:
    """Build user prompt for grounded interview generation.

    This is a SINGLE-PASS generation (no chapters) that produces the
    Key Ideas + Conversation format.

    Args:
        transcript: Full transcript text.
        speaker_name: Name of the speaker.
        evidence_claims: List of extracted claims with supporting quotes.

    Returns:
        Formatted user prompt string.
    """
    parts = [
        "## Source Transcript",
        "```",
        transcript,
        "```",
        "",
        "## Evidence Map (Claims You Can Use)",
        "",
        "Use ONLY these verified claims and their supporting quotes for the Key Ideas section:",
        "",
    ]

    # Include evidence claims with their quotes
    for i, claim in enumerate(evidence_claims[:15], 1):  # Limit to top 15 claims
        claim_text = claim.get("claim", "")
        parts.append(f"{i}. **{claim_text}**")
        for quote in claim.get("support", [])[:1]:  # First supporting quote
            quote_text = quote.get("quote", "")
            if quote_text:
                # Truncate to ~40 words for inline use
                words = quote_text.split()
                if len(words) > 40:
                    quote_text = " ".join(words[:40]) + "..."
                parts.append(f'   - Quote: "{quote_text}"')
        parts.append("")

    parts.extend([
        "## Instructions",
        "",
        f"Generate an ebook about this conversation with {speaker_name}.",
        "",
        "Your output MUST follow this exact structure:",
        "",
        "1. **## Key Ideas (Grounded)** - 5-10 bullets, each with an inline quote",
        "2. **## The Conversation** - The COMPLETE interview as Q&A",
        "",
        "CRITICAL RULES FOR THE CONVERSATION SECTION:",
        "- Use **GUEST:** for all speaker answers (not the speaker's name)",
        "- Copy each question VERBATIM from the transcript as a ### header",
        "- Include the COMPLETE answer - do NOT summarize, truncate, or paraphrase",
        "- NO topic grouping headers - just direct Q&A pairs",
        "- Include ALL Q&A exchanges from the transcript",
        "",
        "Remember:",
        "- Every Key Idea bullet needs a supporting quote (use the Evidence Map above)",
        "- No chapter headings like 'Chapter 1'",
        "- No 'Key Takeaways', 'Action Steps', or how-to content",
        f"- Do NOT invent {speaker_name}'s biography",
        "",
        "Begin generating the ebook:",
    ])

    return "\n".join(parts)


# ==============================================================================
# Evidence Map Prompts (Spec 009)
# ==============================================================================

EVIDENCE_EXTRACTION_SYSTEM_PROMPT = """You are an expert at extracting factual claims and supporting evidence from transcripts.

Your task is to analyze transcript text and extract:
1. **Claims**: Specific statements that can be made based on the transcript
2. **Support**: Exact quotes from the transcript that support each claim
3. **Claim types**: factual, opinion, recommendation, anecdote, or definition

Rules:
- ONLY extract claims that are directly supported by transcript text
- Include EXACT quotes as support - no paraphrasing
- Provide character offsets (start_char, end_char) for each quote when possible
- Include speaker attribution when identifiable
- Assign confidence scores (0.0-1.0) based on how clearly the claim is supported
- Claims should be specific and verifiable, not vague generalizations

For each claim, ensure there is at least one supporting quote that directly backs it up.
Do NOT generate claims that require external knowledge or inference beyond the transcript."""


def build_claim_extraction_prompt(
    chapter_title: str,
    transcript_segment: str,
    content_mode: str = "interview",
) -> str:
    """Build user prompt for claim extraction from transcript.

    Args:
        chapter_title: Title of the chapter being processed.
        transcript_segment: The transcript text to extract claims from.
        content_mode: Content mode (interview/essay/tutorial).

    Returns:
        Formatted user prompt string.
    """
    mode_guidance = {
        "interview": """Focus on:
- Speaker insights and perspectives
- Anecdotes and experiences shared
- Recommendations made by speakers
- Key definitions or explanations given
- Avoid: action steps, how-to instructions, biographical details not mentioned""",
        "essay": """Focus on:
- Main arguments and thesis statements
- Supporting evidence and examples
- Logical connections between ideas
- Conclusions and implications""",
        "tutorial": """Focus on:
- Step-by-step instructions
- Best practices and recommendations
- Warnings and common mistakes
- Technical explanations and definitions""",
    }

    guidance = mode_guidance.get(content_mode, mode_guidance["interview"])

    return f"""## Chapter: {chapter_title}

## Content Mode: {content_mode}
{guidance}

## Transcript Segment
```
{transcript_segment}
```

## Instructions
Extract all supportable claims from this transcript segment. For each claim:
1. Identify the specific claim that can be made
2. Find the exact quote(s) that support it
3. Classify the claim type
4. Assign a confidence score

Return a JSON object with:
{{
    "claims": [
        {{
            "id": "claim_001",
            "claim": "The specific claim text",
            "support": [
                {{
                    "quote": "Exact quote from transcript",
                    "start_char": 0,
                    "end_char": 50,
                    "speaker": "Speaker name if known"
                }}
            ],
            "confidence": 0.85,
            "claim_type": "factual|opinion|recommendation|anecdote|definition"
        }}
    ],
    "must_include": [
        {{
            "point": "Key point that must appear in the chapter",
            "priority": "critical|important|optional",
            "evidence_ids": ["claim_001"]
        }}
    ]
}}"""


# ==============================================================================
# Interview Mode Constraints (Spec 009)
# ==============================================================================

# Patterns that are FORBIDDEN in interview mode drafts
INTERVIEW_FORBIDDEN_PATTERNS = [
    r"(?i)key\s+action\s+steps?",
    r"(?i)action\s+items?",
    r"(?i)(?:here\s+are\s+)?(?:the\s+)?(?:\d+\s+)?steps?\s+(?:to|you\s+can)",
    r"(?i)how\s+to\s+(?:get\s+started|begin|implement)",
    r"(?i)(?:first|second|third|next|finally),?\s+(?:you\s+(?:should|need\s+to|can|must))",
    r"(?i)biography|background|early\s+life|education|career\s+history",
    r"(?i)(?:was|is)\s+born\s+(?:in|on)",
    r"(?i)graduated\s+from|attended\s+(?:\w+\s+)*(?:university|college|school)",
    r"(?i)believe\s+in\s+yourself|never\s+give\s+up|follow\s+your\s+(?:dreams?|passion)",
    r"(?i)the\s+(?:key|secret)\s+to\s+success\s+is",
    r"(?i)(?:anyone|you)\s+can\s+(?:do|achieve)\s+(?:it|this|anything)",
    r"(?i)(?:just|simply)\s+(?:remember|keep\s+in\s+mind)\s+that",
    # P1: Distancing attribution patterns
    r"(?i)\b\w+\s+(?:believes?|argues?|emphasizes?|contends?|maintains?|insists?)\s+that",
    # Narration inside quotes (fabricated quotes indicator)
    r'"[^"]*\b(?:he|she|they)\s+(?:says?|said|notes?|explained?|added?)\b[^"]*"',
]

# System prompt additions for interview mode
INTERVIEW_MODE_CONSTRAINTS = """
INTERVIEW MODE CONSTRAINTS:
You are writing based on an interview/webinar transcript. Follow these rules strictly:

DO NOT include:
- "Key Action Steps" or "Action Items" sections
- Step-by-step how-to instructions
- Biographical information not explicitly mentioned in the transcript
- Motivational platitudes or generic advice not from the source
- Topics or claims not present in the provided Evidence Map

DO include:
- Direct quotes from speakers (attributed when possible)
- Speaker insights, opinions, and perspectives
- Anecdotes and stories shared during the interview
- Key definitions and explanations from the transcript
- The narrative flow of the conversation

Write in a narrative style that reflects the conversational nature of the source material.
Ground every claim in evidence from the transcript."""


# Mode-specific prompt templates
ESSAY_MODE_PROMPT = """
ESSAY MODE (Ideas Edition):
Transform the transcript into a coherent thematic exploration of the speaker's ideas.

CHAPTER STRUCTURE (use this exact format for each chapter):

## Chapter N: [Title]

[Synthesis section - 3-5 paragraphs of tight, grounded prose weaving together the speaker's ideas on this theme. Every claim must be tied to evidence. Include inline quotes.]

### Key Excerpts

[Include 2-4 substantial verbatim passages (2-4 sentences each) that capture the speaker's voice on this theme. Format as block quotes with attribution.]

CRITICAL: Every excerpt MUST be wrapped in quotation marks. Never omit the quotes.

> "[Exact verbatim quote from transcript - multiple sentences allowed]"
> — [Speaker name]

> "[Another substantial verbatim passage]"
> — [Speaker name]

WRONG: > Before the Enlightenment, there was practically nobody...
RIGHT: > "Before the Enlightenment, there was practically nobody..."

### Core Claims

[Bullet list of 3-5 key claims from this chapter, each with supporting quote.]

CRITICAL: Every supporting quote MUST be wrapped in quotation marks.

- **[Claim in your words]**: "[Supporting quote from transcript]"
- **[Another claim]**: "[Supporting quote]"

WRONG: - **Claim**: the thing is, humans can decide...
RIGHT: - **Claim**: "The thing is, humans can decide..."

VERBATIM EVIDENCE RULE (CRITICAL):
- Evidence quotes MUST be copied VERBATIM from the transcript (8–25 words)
- NEVER paraphrase, summarize, or rephrase evidence
- If you cannot find an exact verbatim quote to support a claim, OMIT the claim entirely
- The groundedness checker will REJECT paraphrased evidence

---

EVIDENCE DENSITY REQUIREMENTS:
- Synthesis: At least 6 inline quotes per chapter, 1 quote per 150-200 words
- Key Excerpts: 2-4 substantial multi-sentence verbatim passages per chapter
- Core Claims: 3-5 quote-backed claims per chapter
- Total quotes per chapter: 12-15 minimum

STRICT CONTENT RULES:
- NEVER add contemporary examples not in the transcript (no "climate change", "AI", "social media", "inequality", "today's world", "modern challenges")
- NEVER add moralizing language unless directly quoting ("should", "must", "duty", "responsibility", "crucial for survival", "moral imperative")
- NEVER add poetic embellishments ("as if nature mocked humanity", "vigilant stewards")
- NEVER add biographical details not in the transcript ("noted physicist", "renowned philosopher")
- If the transcript doesn't say it, you cannot say it
- Key Excerpts must be EXACT verbatim quotes copied from transcript - no paraphrasing, no ellipsis, no word substitutions (groundedness checker will REJECT non-verbatim excerpts)

SYNTHESIS GUIDELINES:
- Present the speaker's main argument clearly using their words
- Build logical connections between ideas using brief, neutral transitions
- Let the quotes carry the meaning - your prose is connective tissue only
- Write in a clear, neutral style

PROSE STYLE RULES (Critical - prevents verbatim leak):
- NO PERSON NAMES IN PROSE: Narrative prose must not include any person names (e.g., David Deutsch, Hawking, Einstein). Names appear only in Key Excerpts attribution lines.
- NO SPEAKER FRAMING: Do NOT write "X says...", "he notes...", "she argues...", or any attribution phrases in prose. Attribution belongs only in Key Excerpts.
- Do NOT reproduce distinctive phrases from the conversation in prose. Paraphrase abstractly using general terms.
- Prefer general nouns over concrete phrasing. Write "progress" not the speaker's specific phrase, "knowledge" not their exact words, "constraints" not their particular formulation.
- If you find yourself wanting to quote or attribute to the speaker in prose, STOP. Move that quote to Key Excerpts instead.

Your job is to organize and present the speaker's ideas with maximum fidelity to the source, not to add your own commentary or modern framing."""


TUTORIAL_MODE_PROMPT = """
TUTORIAL MODE:
Structure the content as an instructional guide:
- Include step-by-step instructions where appropriate
- Highlight best practices and common pitfalls
- Use clear, actionable language
- Include practical examples and exercises

Focus on helping readers implement what they learn."""


def get_content_mode_prompt(content_mode: str) -> str:
    """Get the mode-specific prompt additions.

    Args:
        content_mode: Content mode (interview/essay/tutorial).

    Returns:
        Mode-specific prompt text to append to system prompt.
    """
    mode_prompts = {
        "interview": INTERVIEW_MODE_CONSTRAINTS,
        "essay": ESSAY_MODE_PROMPT,
        "tutorial": TUTORIAL_MODE_PROMPT,
    }
    return mode_prompts.get(content_mode, INTERVIEW_MODE_CONSTRAINTS)


# ==============================================================================
# Evidence-Grounded Chapter Generation (Spec 009)
# ==============================================================================

def build_grounded_chapter_system_prompt(
    book_title: str,
    chapter_number: int,
    style_config: dict,
    words_per_chapter_target: int = 625,
    detail_level: str = "balanced",
    content_mode: str = "interview",
    strict_grounded: bool = True,
) -> str:
    """Build system prompt for evidence-grounded chapter generation.

    This extends build_chapter_system_prompt with Evidence Map constraints.

    Args:
        book_title: Title of the ebook.
        chapter_number: 1-based chapter number.
        style_config: StyleConfig dict (unwrapped from envelope).
        words_per_chapter_target: Target word count for this chapter.
        detail_level: Detail level (concise/balanced/detailed).
        content_mode: Content mode (interview/essay/tutorial).
        strict_grounded: If True, only use claims from Evidence Map.

    Returns:
        Formatted system prompt string.
    """
    # Start with base chapter prompt
    base_prompt = build_chapter_system_prompt(
        book_title=book_title,
        chapter_number=chapter_number,
        style_config=style_config,
        words_per_chapter_target=words_per_chapter_target,
        detail_level=detail_level,
    )

    # Add Evidence Map grounding rules
    grounding_rules = """

EVIDENCE-GROUNDED GENERATION:
You have been provided with an Evidence Map containing claims and supporting quotes from the transcript.

"""
    if strict_grounded:
        grounding_rules += """STRICT GROUNDING MODE:
- ONLY include claims that appear in the Evidence Map
- Use the provided supporting quotes as the basis for content
- Do NOT add information, examples, or claims not in the Evidence Map
- If the Evidence Map is sparse, write a shorter chapter rather than adding filler
"""
    else:
        grounding_rules += """GROUNDED MODE:
- Prioritize claims from the Evidence Map
- You may add light connective tissue between claims
- Avoid adding substantial new information not in the transcript
"""

    # Add content mode specific constraints
    mode_prompt = get_content_mode_prompt(content_mode)

    return base_prompt + grounding_rules + mode_prompt


def build_grounded_chapter_user_prompt(
    chapter_plan: "ChapterPlan",
    evidence_claims: list[dict],
    must_include: list[dict],
    transcript_segment: str,
    previous_chapter_ending: Optional[str] = None,
    next_chapter_preview: Optional[tuple[str, list[str]]] = None,
) -> str:
    """Build user prompt for evidence-grounded chapter generation.

    Args:
        chapter_plan: The ChapterPlan for this chapter.
        evidence_claims: List of EvidenceEntry dicts for this chapter.
        must_include: List of MustIncludeItem dicts.
        transcript_segment: The mapped transcript text.
        previous_chapter_ending: Last paragraphs of previous chapter.
        next_chapter_preview: Tuple of (title, first_points) for next chapter.

    Returns:
        Formatted user prompt string.
    """
    parts = [
        "## Evidence Map for This Chapter",
        "",
        "### Claims You Can Make (with supporting evidence):",
    ]

    for claim in evidence_claims:
        parts.append(f"\n**Claim**: {claim.get('claim', 'Unknown claim')}")
        parts.append(f"**Type**: {claim.get('claim_type', 'factual')}")
        parts.append(f"**Confidence**: {claim.get('confidence', 0.8)}")
        parts.append("**Supporting quotes**:")
        for quote in claim.get('support', []):
            speaker = quote.get('speaker', 'Speaker')
            parts.append(f'  - "{quote.get("quote", "")}" — {speaker}')

    if must_include:
        parts.extend([
            "",
            "### Must Include (priority items):",
        ])
        for item in must_include:
            priority = item.get('priority', 'important')
            parts.append(f"- [{priority.upper()}] {item.get('point', '')}")

    parts.extend([
        "",
        "## Raw Transcript Segment (for reference)",
        f"```\n{transcript_segment[:5000]}\n```",  # Truncate if very long
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
        "## Instructions",
        f"Write Chapter {chapter_plan.chapter_number}: {chapter_plan.title}",
        "",
        "Use ONLY the claims and quotes from the Evidence Map above.",
        "Transform the evidence into flowing prose that reads naturally.",
        "Attribute quotes to speakers when possible.",
    ])

    return "\n".join(parts)


# ==============================================================================
# Rewrite Prompts (Spec 009 US3)
# ==============================================================================

REWRITE_SYSTEM_PROMPT = """You are an expert editor specializing in targeted text revisions.

Your task is to rewrite specific sections of an ebook draft to fix identified issues
WITHOUT adding new information or changing the overall meaning.

Rules:
1. ONLY modify the specific section provided
2. Do NOT add claims or facts not in the original or Evidence Map
3. Preserve all markdown formatting (headings, lists, code blocks)
4. Maintain the same approximate length (±20%)
5. Fix the specific issues identified while preserving good content
6. Keep the same voice and tone as the original

You will be given:
- The original section text
- The issues to fix
- Allowed evidence (claims you can use)
- Preservation requirements"""


def build_rewrite_section_prompt(
    original_text: str,
    issues: list[dict],
    allowed_claims: list[dict],
    preserve: list[str],
    rewrite_instructions: Optional[str] = None,
) -> str:
    """Build prompt for rewriting a specific section.

    Args:
        original_text: The original section to rewrite.
        issues: List of IssueReference dicts describing problems.
        allowed_claims: Claims from Evidence Map that can be used.
        preserve: List of elements to preserve (e.g., "heading", "bullet_structure").
        rewrite_instructions: Optional specific instructions.

    Returns:
        Formatted prompt for section rewrite.
    """
    parts = [
        "## Original Section",
        f"```markdown\n{original_text}\n```",
        "",
        "## Issues to Fix",
    ]

    for issue in issues:
        issue_type = issue.get('issue_type', 'unknown')
        message = issue.get('issue_message', 'No details')
        parts.append(f"- **{issue_type}**: {message}")

    parts.extend([
        "",
        "## Allowed Evidence (claims you can use)",
    ])

    if allowed_claims:
        for claim in allowed_claims:
            parts.append(f"- {claim.get('claim', 'Unknown claim')}")
    else:
        parts.append("- Use only information from the original text")

    parts.extend([
        "",
        "## Preserve",
    ])
    for item in preserve:
        parts.append(f"- {item}")

    if rewrite_instructions:
        parts.extend([
            "",
            "## Specific Instructions",
            rewrite_instructions,
        ])

    parts.extend([
        "",
        "## Task",
        "Rewrite the section to fix the issues while following all rules.",
        "Return ONLY the rewritten markdown, no explanations.",
    ])

    return "\n".join(parts)
