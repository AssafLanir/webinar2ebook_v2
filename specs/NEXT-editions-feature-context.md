# Next Feature: Editions / Output Modes

## Context (from conversation 2026-01-12)

### The Problem (User's Brother's Feedback)
> "That's basically a transcript"

The current interview mode output looks like a cleaned-up transcript, not a "book". This is **by design** for Strict Verbatim mode (fidelity over readability), but user expectations may differ.

### Current State
- Interview mode produces Q&A format with speaker labels (HOST/GUEST/CALLER/CLIP)
- Strict Verbatim mode prioritizes: fidelity + voice + zero hallucinations
- Speaker attribution is now working correctly (callers, clips, host interjections)

### The Gap
Users might expect different outputs depending on their use case:
1. **Researchers** → want verbatim fidelity (current output)
2. **Casual readers** → want synthesized "ideas book"
3. **Some users** → want something in between

### ChatGPT's Suggestions

**Spec A: "Editions" dropdown**
- Transcript (Strict Verbatim) — interview/panels where fidelity matters
- Curated Interview — still Q&A, but lightly abridged (selecting/omitting)
- Ideas / Summary — synthesized, structured "ebook"

**Spec B: Speaker diarization as preprocessing**
- If transcript has labels → deterministic parse
- If not → run labeling pass FIRST, then generate
- Cleaner than current post-processing heuristics

### What We Agreed With
1. Product positioning is valid - need to clarify what each mode produces
2. "Editions" concept makes sense for different use cases
3. Speaker labeling as preprocessing is architecturally cleaner

### What We're Skeptical About
1. "Ideas Edition" is a major new product (not just a toggle)
2. "Curated Interview" is vague - needs definition
3. External diarization adds complexity we may not need

### Questions to Explore
1. Is this about clarifying what we already have, or building a new "summary" mode?
2. What does "Curated Interview" actually mean? (omit boring parts? select highlights?)
3. Should speaker labeling move to preprocessing step?
4. What's the MVP for an "Ideas Edition"?

## Brainstorm Prompt for /superpowers:brainstorm

```
/superpowers:brainstorm Add "Editions" feature to Webinar2Ebook.

Current state: Interview mode produces Q&A transcript format with speaker labels.
Problem: Users may expect a more "book-like" output, not just a cleaned transcript.

Constraints:
- Python 3.11/FastAPI backend
- React/TypeScript frontend
- Existing OpenAI LLM infrastructure
- MongoDB for storage
- Current modes: Strict Verbatim, Curated Verbatim (content modes)

Non-goals:
- External diarization services
- Real-time processing
- Major UX redesign
- Breaking existing interview mode functionality

Options to explore:
1. Clarify/rename existing modes (product positioning only)
2. Add "Ideas/Summary Edition" as new output format
3. Add "Curated Interview" as middle ground
4. Move speaker labeling to preprocessing step

Ask clarifying questions first.
```

## Commits Made Today (Speaker Attribution Fixes)
- `8492b0d` feat(speaker): Expand HOST patterns + first-person header detection
- `6a6377e` feat(speaker): Add hard patterns + look-ahead HOST confirmation

All 39 speaker attribution tests pass.
