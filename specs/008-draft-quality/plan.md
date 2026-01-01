# Implementation Plan: Draft Quality System

**Branch**: `008-draft-quality` | **Date**: 2026-01-01 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/008-draft-quality/spec.md`

## Summary

Add a systematic quality assessment system for AI-generated ebook drafts. The system produces structured QA reports with scores and issues after draft generation, displays results in a UI panel, and optionally provides an "editor pass" to fix issues. A regression suite enables measurement of quality improvements over time.

**Technical Approach**: Hybrid evaluation using regex for structural issues (fast, deterministic) + LLM for semantic analysis (faithfulness, clarity). Reuses existing job-based async patterns and LLM abstraction.

## Technical Context

**Language/Version**: Python 3.11 (backend), TypeScript 5.x (frontend)
**Primary Dependencies**: FastAPI, Pydantic v2, React, existing LLM client (OpenAI/Anthropic)
**Storage**: MongoDB (QA reports stored in project document)
**Testing**: pytest (backend), vitest (frontend)
**Target Platform**: Web application (localhost development, cloud deployment)
**Project Type**: Web application (backend + frontend)
**Performance Goals**: QA report generation < 30 seconds for 50k word drafts
**Constraints**: Must work with existing project data model, no new collections
**Scale/Scope**: Single user, projects up to 100k words

## Constitution Check

*GATE: Project constitution is a template - no specific gates defined.*

✅ No constitution violations - proceeding with standard patterns.

## Project Structure

### Documentation (this feature)

```text
specs/008-draft-quality/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (API schemas)
├── schemas/             # QA report JSON schema
├── fixtures/            # Golden projects for regression suite
└── tasks.md             # Phase 2 output
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── models/
│   │   └── qa_report.py          # QAReport, QAIssue, RubricScores models
│   ├── services/
│   │   ├── qa_evaluator.py       # QA evaluation logic (hybrid regex+LLM)
│   │   ├── qa_structural.py      # Regex-based structural analysis
│   │   ├── qa_semantic.py        # LLM-based semantic analysis
│   │   └── editor_pass.py        # P2: Editor improvement pass
│   └── api/
│       └── routes/
│           └── qa.py             # QA endpoints
└── tests/
    ├── unit/
    │   ├── test_qa_structural.py
    │   └── test_qa_semantic.py
    ├── integration/
    │   └── test_qa_api.py
    └── fixtures/
        └── golden_projects.json  # Regression suite config

frontend/
├── src/
│   ├── components/
│   │   └── tab3/
│   │       ├── QAPanel.tsx       # QA results panel
│   │       └── QAIssueList.tsx   # Issue list component
│   ├── hooks/
│   │   └── useQA.ts              # QA state management
│   ├── services/
│   │   └── qaApi.ts              # QA API client
│   └── types/
│       └── qa.ts                 # TypeScript types
└── tests/
```

**Structure Decision**: Extends existing web application structure. QA logic is primarily backend (evaluation). Frontend adds a collapsible panel to Tab3.

## File Summary

| File | Action | Phase |
|------|--------|-------|
| backend/src/models/qa_report.py | NEW | US1 |
| backend/src/services/qa_evaluator.py | NEW | US1 |
| backend/src/services/qa_structural.py | NEW | US1 |
| backend/src/services/qa_semantic.py | NEW | US1 |
| backend/src/api/routes/qa.py | NEW | US1 |
| frontend/src/components/tab3/QAPanel.tsx | NEW | US2 |
| frontend/src/components/tab3/QAIssueList.tsx | NEW | US2 |
| frontend/src/hooks/useQA.ts | NEW | US2 |
| frontend/src/services/qaApi.ts | NEW | US2 |
| frontend/src/types/qa.ts | NEW | US2 |
| backend/src/services/editor_pass.py | NEW | US3 (P2) |
| backend/tests/fixtures/golden_projects.json | NEW | US4 (P2) |

## API Design

### QA Endpoints

All endpoints follow existing `{ data, error }` envelope pattern.

```
POST /api/projects/{project_id}/qa/analyze
  → Triggers QA analysis (can be sync for small drafts, async for large)
  → Returns: { data: { job_id?, qa_report? }, error: null }

GET /api/projects/{project_id}/qa/report
  → Returns latest QA report for project
  → Returns: { data: QAReport, error: null }

POST /api/projects/{project_id}/qa/improve  (P2)
  → Triggers editor pass
  → Returns: { data: { job_id }, error: null }
```

### Integration with Draft Generation

Option A (Recommended): Auto-trigger QA after draft completion
- Modify draft_service.py to call qa_evaluator after draft saved
- QA report stored in project.qaReport field

Option B: Manual trigger only
- User clicks "Run QA" button in UI
- Separate API call

**Decision**: Option A for seamless UX, with manual re-run available.

## Implementation Strategy

### Phase 1: MVP (US1 + US2)

1. **Structural Analysis** (regex-based, no LLM)
   - Repetition detection (n-gram analysis)
   - Heading hierarchy validation
   - Paragraph length checks
   - Chapter balance analysis

2. **Semantic Analysis** (LLM-based)
   - Faithfulness scoring (compare to transcript)
   - Clarity assessment
   - Completeness check

3. **UI Panel**
   - Summary badge in Tab3
   - Expandable issue list
   - Score breakdown

### Phase 2: Improvements (US3 + US4)

4. **Editor Pass** (P2)
   - LLM-based rewriting
   - Diff generation
   - Faithfulness preservation check

5. **Regression Suite** (P2)
   - Golden project fixtures
   - Score comparison script
   - CI integration

## Complexity Tracking

No constitution violations requiring justification.
