# Implementation Plan: Evidence-Grounded Drafting

**Branch**: `009-evidence-grounded` | **Date**: 2026-01-04 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/009-evidence-grounded/spec.md`

## Summary

Transform draft generation from "write freely then check" to "ground then write" by introducing an Evidence Map step before chapter generation. Add Content Mode (Interview/Essay/Tutorial) to control structure and constraints. Integrate targeted rewrite for any remaining QA issues (replaces Spec 008 US3).

## Technical Context

**Language/Version**: Python 3.11 (backend), TypeScript 5.x (frontend)
**Primary Dependencies**:
- Backend: FastAPI, Pydantic v2, OpenAI SDK, Anthropic SDK, motor (async MongoDB)
- Frontend: React 18, Vite, Tailwind CSS, React Context
**Storage**: MongoDB (projects), local filesystem (file uploads)
**Testing**: pytest (backend), Vitest (frontend)
**Target Platform**: Web application (Linux server backend, modern browsers frontend)
**Project Type**: Web application (backend + frontend)
**Performance Goals**: Evidence Map generation < 30 seconds, no degradation to overall draft time
**Constraints**:
- Single rewrite pass only (no loops)
- Evidence Map must fit in context window with transcript
- Maintain backward compatibility for existing projects
**Scale/Scope**: Single-user projects, 500-50,000 char transcripts

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| Existing patterns | PASS | Extends established draft_service.py job pipeline |
| Test coverage | PASS | Unit tests for Evidence Map, integration tests for constraints |
| Single source of truth | PASS | Pydantic models canonical; JSON schemas in specs/009/schemas/ |
| Error handling | PASS | Envelope pattern { data, error } established |
| No new endpoints | PASS | Reuses existing draft generation flow, adds rewrite action |

## Project Structure

### Documentation (this feature)

```text
specs/009-evidence-grounded/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── schemas/             # JSON schemas (already created)
│   ├── evidence_map.schema.json
│   └── rewrite_plan.schema.json
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── models/
│   │   ├── style_config.py        # UPDATE: Add ContentMode, strict_grounded
│   │   ├── evidence_map.py        # NEW: EvidenceMap, ChapterEvidence, EvidenceEntry
│   │   └── rewrite_plan.py        # NEW: RewritePlan, RewriteSection
│   ├── services/
│   │   ├── draft_service.py       # UPDATE: Add evidence_map phase, integrate grounding
│   │   ├── evidence_service.py    # NEW: Evidence Map generation
│   │   ├── rewrite_service.py     # NEW: Targeted rewrite service
│   │   └── prompts.py             # UPDATE: Add interview mode prompts, grounding prompts
│   └── api/
│       └── routes/
│           └── qa.py              # UPDATE: Add rewrite endpoint
└── tests/
    ├── unit/
    │   ├── test_evidence_map.py   # NEW: Evidence Map generation tests
    │   ├── test_rewrite_service.py # NEW: Rewrite service tests
    │   └── test_content_mode.py   # NEW: Content mode constraint tests
    └── integration/
        └── test_grounded_generation.py # NEW: End-to-end grounded generation

frontend/
├── src/
│   ├── components/
│   │   └── tab3/
│   │       ├── StyleControls.tsx  # UPDATE: Add Content Mode dropdown, Strict toggle
│   │       ├── Tab3Content.tsx    # UPDATE: Add "Fix Flagged Issues" button
│   │       └── RewriteDiffView.tsx # NEW: Before/after diff display
│   └── types/
│       └── style.ts               # UPDATE: Add ContentMode type
└── tests/
```

**Structure Decision**: Extends existing web application structure. Key additions are evidence_service.py and rewrite_service.py in backend.

## Complexity Tracking

No violations requiring justification. Implementation extends existing patterns without adding new architectural concepts.

---

## Phase 0: Research Required

### Unknowns to Resolve

1. **Evidence Map prompting**: How to extract claims and supporting quotes efficiently
2. **Transcript chunking for evidence**: Handle transcripts > 20K chars
3. **Constraint enforcement**: How to verify interview mode constraints at generation time
4. **Rewrite scope detection**: How to identify section boundaries for targeted rewrite

### Research Tasks

| Topic | Question | Output |
|-------|----------|--------|
| Evidence extraction | Best prompts for claim/quote extraction from interviews | research.md section |
| Constraint validation | How to test "no action steps" constraint in generated content | research.md section |
| Section boundaries | How to identify and isolate sections for targeted rewrite | research.md section |
| Content Mode detection | Heuristics to warn if Content Mode doesn't match source | research.md section |

---

## Phase 1: Design Artifacts

### Entities (data-model.md)

From spec.md, the following entities need documentation:

| Entity | Source | Status |
|--------|--------|--------|
| ContentMode | backend/src/models/style_config.py | NEW - add to StyleConfig |
| EvidenceMap | backend/src/models/evidence_map.py | NEW - create file |
| ChapterEvidence | backend/src/models/evidence_map.py | NEW - create file |
| EvidenceEntry | backend/src/models/evidence_map.py | NEW - create file |
| RewritePlan | backend/src/models/rewrite_plan.py | NEW - create file |
| RewriteSection | backend/src/models/rewrite_plan.py | NEW - create file |

### API Changes

| Change | Method | Description |
|--------|--------|-------------|
| StyleConfig update | N/A | Add content_mode, strict_grounded fields |
| Job status update | GET /draft/status | Add evidence_map to response when available |
| QA rewrite | POST /qa/rewrite | NEW: Trigger targeted rewrite for flagged issues |

### Quickstart (quickstart.md)

Local development and testing steps for this feature.

---

## What Already Exists

### Backend (from Spec 004/008)

- **Draft Service** (`backend/src/services/draft_service.py`):
  - Async job pattern with job_id, status polling
  - Chapter-by-chapter generation with context
  - Visual plan generation integrated
  - QA auto-trigger after completion (T019)

- **QA System** (`backend/src/services/qa_*.py`):
  - Structural analysis (repetition, heading hierarchy, paragraphs)
  - Semantic analysis (faithfulness, clarity, completeness)
  - QA report model and storage in project.qaReport

- **StyleConfig** (`backend/src/models/style_config.py`):
  - Comprehensive style options
  - Faithfulness level enum exists
  - include_action_steps boolean exists (can leverage)

- **Prompts** (`backend/src/services/prompts.py`):
  - Chapter generation prompts
  - Visual opportunity prompts
  - Transcript segment extraction

### Frontend (from Spec 004)

- Tab 3 UI with StyleControls, Generate button
- QA Panel from Spec 008 US2
- DraftEditor, progress indicator

### What Needs Building

1. **ContentMode enum** and strict_grounded field in StyleConfig
2. **Evidence Map service** with LLM-based extraction
3. **Interview mode prompts** with constraints
4. **Evidence-grounded chapter generation**
5. **Targeted rewrite service** using QA report + Evidence Map
6. **Frontend** Content Mode dropdown, Strict toggle, Rewrite button

---

## Integration Points

### With Existing Draft Pipeline

```
Current flow:
start_generation → planning → [visual_plan] → generating → completed → [QA auto-trigger]

New flow:
start_generation → planning → evidence_map → [visual_plan] → generating (grounded) → completed → [QA auto-trigger]
                                    ↓
                            Stored in job.evidence_map
                                    ↓
                            Used in chapter prompts
```

### With Existing QA System

```
Current:
QA detects issues → Display in QAPanel → User regenerates manually

New:
QA detects issues → Display in QAPanel → "Fix Flagged Issues" button →
Rewrite service uses Evidence Map + QA issues → Targeted rewrite →
Re-run QA to verify
```

---

## Next Steps

1. **Phase 0**: Generate `research.md` to resolve unknowns
2. **Phase 1**: Generate `data-model.md`, `quickstart.md`
3. **Phase 2**: Run `/speckit.tasks` to generate implementation tasks
