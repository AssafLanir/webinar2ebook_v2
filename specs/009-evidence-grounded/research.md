# Research: Evidence-Grounded Drafting

**Feature**: 009-evidence-grounded
**Date**: 2026-01-04
**Status**: Complete

## Overview

This document resolves unknowns identified in the implementation plan for Evidence Map extraction, constraint enforcement, and targeted rewrite.

---

## 1. Evidence Map Prompting Strategy

### Question
How to efficiently extract claims and supporting quotes from interview transcripts?

### Decision
Use a **two-pass extraction approach**:
1. **First pass**: Extract key claims/insights per outline chapter
2. **Second pass**: For each claim, find the best supporting quote

### Rationale
- Single-pass extraction often misses context or produces weak quote matches
- Two-pass allows claim identification first, then targeted quote search
- Fits within token limits by processing outline chunks

### Alternatives Considered

| Alternative | Rejected Because |
|-------------|------------------|
| Single LLM call for all claims | Exceeds context window for long transcripts |
| Embedding-based retrieval | Adds complexity, requires vector DB setup |
| Regex quote matching | Too brittle, misses paraphrased content |

### Implementation

```python
# Pseudo-code for evidence extraction
async def generate_evidence_map(transcript: str, chapters: list[ChapterPlan]) -> EvidenceMap:
    all_evidence = []

    for chapter in chapters:
        # Get relevant transcript segment for this chapter
        segment = extract_transcript_segment(transcript, chapter)

        # Step 1: Extract claims from segment
        claims = await extract_claims(segment, chapter.title, chapter.goals)

        # Step 2: Find supporting quotes for each claim
        for claim in claims:
            quote = await find_supporting_quote(segment, claim)
            all_evidence.append(EvidenceEntry(
                claim=claim,
                support=[quote],
                confidence=quote.confidence
            ))

    return EvidenceMap(chapters=[...])
```

### System Prompt (Claim Extraction)

```text
You are extracting factual claims from an interview transcript for a specific chapter.

Chapter: {chapter_title}
Goals: {chapter_goals}

Extract claims that:
1. Are directly stated or clearly implied by the speaker
2. Relate to the chapter goals
3. Are specific enough to be verified

DO NOT extract:
- Generic statements anyone could make
- Pleasantries or social niceties
- Speculation or hypotheticals not from the speaker

Return JSON:
{
  "claims": [
    { "claim": "...", "claim_type": "factual|opinion|recommendation|anecdote" }
  ]
}
```

---

## 2. Transcript Chunking for Evidence

### Question
How to handle transcripts > 20K chars that exceed context windows?

### Decision
Use **overlapping sliding windows** with chapter-aware boundaries:
- Window size: 15,000 chars
- Overlap: 2,000 chars
- Align to sentence boundaries where possible

### Rationale
- Existing `extract_transcript_segment()` already uses char-based ranges
- Overlap prevents losing context at chunk boundaries
- Sentence alignment improves quote quality

### Implementation

```python
def chunk_transcript_for_evidence(
    transcript: str,
    chapter_ranges: list[tuple[int, int]],
    window_size: int = 15000,
    overlap: int = 2000,
) -> list[TranscriptChunk]:
    """Chunk transcript respecting chapter boundaries."""
    chunks = []

    for chapter_idx, (start, end) in enumerate(chapter_ranges):
        segment = transcript[start:end]

        if len(segment) <= window_size:
            chunks.append(TranscriptChunk(
                chapter_idx=chapter_idx,
                text=segment,
                start_char=start,
                end_char=end
            ))
        else:
            # Sliding window within chapter
            pos = 0
            while pos < len(segment):
                chunk_end = min(pos + window_size, len(segment))
                # Align to sentence boundary
                chunk_end = align_to_sentence(segment, chunk_end)

                chunks.append(TranscriptChunk(
                    chapter_idx=chapter_idx,
                    text=segment[pos:chunk_end],
                    start_char=start + pos,
                    end_char=start + chunk_end
                ))

                pos = chunk_end - overlap

    return chunks
```

---

## 3. Interview Mode Constraint Enforcement

### Question
How to verify "no action steps" and other constraints at generation time?

### Decision
**Three-layer enforcement**:
1. **Prompt-level**: Explicit negative instructions in system prompt
2. **Post-generation check**: Regex patterns for forbidden content
3. **QA verification**: Faithfulness analysis catches any escapes

### Rationale
- LLMs respond well to explicit "DO NOT" instructions
- Regex provides fast, deterministic check
- QA provides semantic fallback for edge cases

### Interview Mode Forbidden Patterns

```python
INTERVIEW_FORBIDDEN_PATTERNS = [
    # Action steps sections
    r"##\s*(Key\s+)?Action\s+(Steps?|Items?)",
    r"##\s*Next\s+Steps?",
    r"##\s*Your\s+Action\s+Plan",
    r"##\s*Implementation\s+Checklist",

    # Numbered action lists
    r"^\d+\.\s*(First|Next|Then|Finally),?\s+(you\s+should|implement|create|start)",

    # Motivational platitudes
    r"(you can do this|believe in yourself|take the first step|dream big)",
    r"(success is just around the corner|the sky is the limit)",

    # Invented biography markers
    r"(has been a leader in|is widely recognized|is known for pioneering)",
]

def check_interview_constraints(content: str, mode: ContentMode) -> list[str]:
    """Return list of constraint violations found."""
    if mode != ContentMode.interview:
        return []

    violations = []
    for pattern in INTERVIEW_FORBIDDEN_PATTERNS:
        if re.search(pattern, content, re.IGNORECASE | re.MULTILINE):
            violations.append(f"Forbidden pattern: {pattern[:50]}...")

    return violations
```

### System Prompt Addition (Interview Mode)

```text
IMPORTANT CONSTRAINTS FOR INTERVIEW MODE:

You MUST NOT include:
1. "Key Action Steps" or "Action Items" sections
2. Numbered lists of things the reader should do
3. Biography or background about the speaker unless they explicitly described it
4. Motivational platitudes like "you can do this" or "take the first step"
5. Topics or claims not present in the Evidence Map

You MUST:
1. Focus on what the speaker actually said
2. Use direct quotes where powerful
3. Structure content around insights and experiences shared
4. Only include facts that appear in the Evidence Map
```

---

## 4. Rewrite Scope Detection

### Question
How to identify section boundaries for targeted rewrite?

### Decision
Use **heading-based section identification**:
- Parse markdown for heading hierarchy
- Match QA issue locations to sections
- Extract section start/end lines

### Rationale
- Ebook drafts are structured with markdown headings
- QA issues already include `location` field with heading info
- Markdown parsing is deterministic and fast

### Implementation

```python
import re
from dataclasses import dataclass

@dataclass
class MarkdownSection:
    heading: str
    level: int
    start_line: int
    end_line: int
    content: str

def parse_markdown_sections(draft: str) -> list[MarkdownSection]:
    """Parse draft into sections based on headings."""
    lines = draft.split('\n')
    sections = []
    current_section = None

    heading_pattern = re.compile(r'^(#{1,6})\s+(.+)$')

    for i, line in enumerate(lines):
        match = heading_pattern.match(line)
        if match:
            # Close previous section
            if current_section:
                current_section.end_line = i - 1
                current_section.content = '\n'.join(
                    lines[current_section.start_line:i]
                )
                sections.append(current_section)

            # Start new section
            current_section = MarkdownSection(
                heading=match.group(2),
                level=len(match.group(1)),
                start_line=i,
                end_line=len(lines) - 1,
                content=""
            )

    # Close final section
    if current_section:
        current_section.content = '\n'.join(lines[current_section.start_line:])
        sections.append(current_section)

    return sections

def find_sections_for_issues(
    sections: list[MarkdownSection],
    issues: list[QAIssue],
) -> list[tuple[MarkdownSection, list[QAIssue]]]:
    """Match issues to their containing sections."""
    results = []

    for section in sections:
        matching_issues = [
            issue for issue in issues
            if issue.location and section.heading.lower() in issue.location.lower()
        ]
        if matching_issues:
            results.append((section, matching_issues))

    return results
```

---

## 5. Content Mode Detection (Warning)

### Question
How to warn if Content Mode doesn't match source type?

### Decision
**Heuristic-based detection** with warning (not blocking):
- Interview indicators: speaker turns, Q&A patterns, timestamps
- Tutorial indicators: numbered steps, code blocks, "how to"
- Essay indicators: thesis statements, argument structure

### Rationale
- Users know their content best; don't block them
- Warning helps catch mistakes without being prescriptive
- Simple heuristics are sufficient for warning purposes

### Detection Heuristics

```python
def detect_content_type(transcript: str) -> tuple[str, float]:
    """Detect likely content type from transcript. Returns (type, confidence)."""

    # Interview indicators
    interview_patterns = [
        r'\b(interviewer|host|guest|speaker)\b',
        r'^\s*Q:\s|^\s*A:\s',  # Q&A format
        r'\[\d{1,2}:\d{2}(:\d{2})?\]',  # Timestamps
        r'^\s*[A-Z][a-z]+:\s',  # Speaker labels (Name: ...)
    ]

    # Tutorial indicators
    tutorial_patterns = [
        r'step\s+\d|^\d+\.\s+(first|next|then)',
        r'```|<code>',  # Code blocks
        r'\bhow\s+to\b|\bguide\b|\btutorial\b',
    ]

    # Essay indicators
    essay_patterns = [
        r'\bthesis\b|\bargue\b|\bcontend\b',
        r'\bin\s+conclusion\b|\bto\s+summarize\b',
        r'\bfirstly\b.*\bsecondly\b|\bon\s+one\s+hand\b',
    ]

    interview_score = sum(1 for p in interview_patterns if re.search(p, transcript, re.I | re.M))
    tutorial_score = sum(1 for p in tutorial_patterns if re.search(p, transcript, re.I | re.M))
    essay_score = sum(1 for p in essay_patterns if re.search(p, transcript, re.I | re.M))

    scores = {
        'interview': interview_score,
        'tutorial': tutorial_score,
        'essay': essay_score,
    }

    best = max(scores, key=scores.get)
    total = sum(scores.values()) or 1
    confidence = scores[best] / total

    return (best, confidence)

def generate_mode_warning(
    selected_mode: ContentMode,
    transcript: str,
) -> Optional[str]:
    """Generate warning if selected mode doesn't match detected type."""
    detected, confidence = detect_content_type(transcript)

    if detected != selected_mode.value and confidence > 0.6:
        return (
            f"Selected '{selected_mode.value}' mode but content appears to be "
            f"'{detected}' (confidence: {confidence:.0%}). "
            f"Consider changing Content Mode for better results."
        )

    return None
```

---

## Summary of Decisions

| Topic | Decision | Key Points |
|-------|----------|------------|
| Evidence extraction | Two-pass (claims → quotes) | Fits token limits, better quote quality |
| Transcript chunking | Overlapping windows, chapter-aligned | 15K window, 2K overlap, sentence boundaries |
| Constraint enforcement | Three-layer (prompt + regex + QA) | Deterministic check with semantic fallback |
| Rewrite scope | Heading-based sections | Parse markdown, match QA locations |
| Mode detection | Heuristic warning | Non-blocking, helps catch mistakes |

---

## References

- Existing `extract_transcript_segment()` in `backend/src/services/prompts.py`
- QA issue model in `backend/src/models/qa_report.py`
- StyleConfig in `backend/src/models/style_config.py`
