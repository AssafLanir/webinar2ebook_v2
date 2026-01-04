# Implementation Plan: Interview Q&A Book Format

**Branch**: `004-interview-qa-format` | **Date**: 2026-01-04 | **Spec**: `spec4.md` (Sections 10.4.1, 11.2, AS-008, AS-009)
**Input**: Enhancement to existing Spec 004 - adding `interview_qa` book format

## Summary

Add a new `interview_qa` book format that generates Q&A-structured ebooks from interview transcripts. Unlike traditional chapter-based formats, this preserves the conversational structure using questions as section headers and maintains the speaker's voice with direct quotes.

**Key Difference from Existing Formats:**
- Standard formats: Transform content into structured chapters with takeaways
- Interview Q&A: Preserve conversational flow with question-based sections

## Technical Context

**Language/Version**: Python 3.11 (backend), TypeScript 5.x (frontend)
**Primary Dependencies**: FastAPI, Pydantic v2, React, OpenAI/Anthropic LLM
**Storage**: MongoDB (existing project model)
**Testing**: pytest (backend), vitest (frontend)
**Target Platform**: Web application
**Project Type**: web (backend + frontend)

## Constitution Check

*Project uses lightweight constitution - no blocking gates identified.*

## Scope Analysis

### What Changes

| Layer | File | Change Type |
|-------|------|-------------|
| **Backend Model** | `src/models/style_config.py` | Add `interview_qa` to `BookFormat` enum |
| **Backend Prompts** | `src/services/prompts.py` | Add Q&A-specific generation prompts |
| **Backend Service** | `src/services/draft_service.py` | Handle format-specific generation logic |
| **Frontend Types** | `src/types/style.ts` | Add `interview_qa` to BookFormat type |
| **Frontend UI** | `src/constants/stylePresets.ts` | Add Interview Q&A preset |
| **Tests** | `tests/unit/`, `tests/integration/` | New tests for Q&A format |

### What Stays the Same

- Project model structure (no new fields)
- API endpoints (same `/api/ai/draft/generate`)
- Frontend draft editor
- Visual opportunities system
- QA system (Spec 008)

## Project Structure

```text
backend/
├── src/
│   ├── models/
│   │   └── style_config.py      # Add interview_qa enum value
│   └── services/
│       ├── prompts.py           # Add Q&A generation prompts
│       └── draft_service.py     # Format-specific logic
└── tests/
    ├── unit/
    │   └── test_interview_qa_format.py    # NEW
    └── integration/
        └── test_interview_qa_generation.py # NEW

frontend/
├── src/
│   ├── types/
│   │   └── style.ts             # Add interview_qa type
│   └── constants/
│       └── stylePresets.ts      # Add preset
└── tests/
    └── style.test.ts            # Update tests
```

## Design Decisions

### D1: Auto-Configuration Behavior

When `book_format: "interview_qa"` is selected, these settings are automatically enforced:
- `content_mode`: "interview" (from Spec 009)
- `faithfulness_level`: "strict"
- `include_key_takeaways`: false
- `include_action_steps`: false
- `include_checklists`: false

**Rationale**: Interview Q&A format's value is preserving the speaker's actual words. Allowing creative additions would undermine the format's purpose.

### D2: Chapter Count Handling

For interview_qa, `chapter_count_target` is interpreted as a *suggestion* for topic groupings, not a hard requirement. The LLM groups questions by theme rather than forcing a specific count.

**Rationale**: Natural interview flow doesn't always fit predetermined chapter counts.

### D3: Prompt Structure

Q&A generation uses a two-phase approach:
1. **Topic Extraction**: Identify major themes/topics from the interview
2. **Q&A Mapping**: Group questions under topics, preserving original phrasing

**Rationale**: This produces more natural groupings than forcing questions into pre-defined chapters.

## Acceptance Criteria (from spec)

### AS-008: Interview Q&A Format
- Draft uses questions as section headers (`###` level)
- Topics grouped under thematic `##` headers
- Speaker's voice preserved with direct quotes
- Blockquotes highlight notable statements
- NO "Key Takeaways" or "Action Steps" sections
- NO invented biography or background
- Content stays faithful to source

### AS-009: Interview Q&A Auto-Configuration
- Settings auto-applied when format selected
- User cannot override while interview_qa is selected

## Implementation Phases

### Phase 1: Backend Model & Validation
- Add `interview_qa` to `BookFormat` enum
- Add auto-configuration logic for interview_qa format
- Unit tests for model changes

### Phase 2: Prompts & Generation
- Create `INTERVIEW_QA_SYSTEM_PROMPT`
- Create `build_interview_qa_chapter_prompt()`
- Update `generate_chapter()` to handle Q&A format
- Unit tests for prompt generation

### Phase 3: Frontend Updates
- Add `interview_qa` to TypeScript types
- Add "Interview Q&A" preset to dropdown
- UI for locked settings when interview_qa selected
- Update tests

### Phase 4: Integration Testing
- End-to-end test with sample interview transcript
- Verify output structure matches spec
- Verify forbidden patterns are excluded

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| LLM doesn't follow Q&A structure | Medium | Strong system prompt + few-shot examples |
| Questions not extracted correctly | Medium | Pattern matching in post-processing |
| Performance impact from two-phase | Low | Topic extraction is lightweight |

## Dependencies

- Spec 009 (Evidence-Grounded Drafting) - for `content_mode: interview` constraints
- Existing draft generation pipeline

## Estimated Effort

| Phase | Tasks | Complexity |
|-------|-------|------------|
| Phase 1 | 3 | Low |
| Phase 2 | 4 | Medium |
| Phase 3 | 3 | Low |
| Phase 4 | 2 | Low |
| **Total** | **12 tasks** | **~1 day** |
