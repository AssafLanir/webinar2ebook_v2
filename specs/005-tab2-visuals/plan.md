# Implementation Plan: Tab 2 Visuals - Upload Library + Assign Assets

**Branch**: `005-tab2-visuals` | **Date**: 2025-12-23 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/005-tab2-visuals/spec.md`

## Summary

Tab 2 becomes a "Visuals Workbench" where users can:
1. Upload client-provided images (PNG/JPG/WebP) into a Visual Library with thumbnails
2. View AI-suggested visual opportunities generated from Tab 3 (`project.visualPlan.opportunities`)
3. Assign library assets to opportunities or mark them as "skipped"
4. Persist everything to the Project for refresh/reload consistency

**Technical Approach**: Use MongoDB GridFS for binary storage (original + thumbnail), Pillow for image processing, and project-scoped REST endpoints for security. Frontend uses React components with debounced autosave via existing `saveProject()`.

## Technical Context

**Language/Version**: Python 3.11 (backend), TypeScript 5.x (frontend)
**Primary Dependencies**: FastAPI, Pydantic v2, React, Tailwind CSS, Pillow, motor (MongoDB async)
**Storage**: MongoDB (projects collection) + GridFS (image binaries)
**Testing**: pytest (backend), manual acceptance scenarios (frontend MVP)
**Target Platform**: Web application (localhost dev, cloud deployment later)
**Project Type**: Web (backend + frontend)
**Performance Goals**: Upload < 3s for 10MB image, thumbnail generation < 500ms
**Constraints**: Max 10MB per file, max 10 files per project, PNG/JPG/WebP only
**Scale/Scope**: Single user, ~50 images per project max

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Constitution Status**: No custom constitution defined for this project. Using default best practices:

| Principle | Status | Notes |
|-----------|--------|-------|
| Extend existing models | PASS | Spec explicitly extends `VisualAsset`, adds `VisualAssignment` |
| Reuse existing patterns | PASS | Uses existing `saveProject()`, `{data, error}` envelope |
| Project-scoped security | PASS | Endpoints verify asset belongs to project |
| Backend validation | PASS | Type/size/count enforced server-side |
| No over-engineering | PASS | MVP scope clearly defined, P2 deferred |

## Project Structure

### Documentation (this feature)

```text
specs/005-tab2-visuals/
├── plan.md              # This file
├── research.md          # Phase 0 output (GridFS, Pillow decisions)
├── data-model.md        # Phase 1 output (VisualAsset extensions, VisualAssignment)
├── quickstart.md        # Phase 1 output (dev setup, test scenarios)
├── contracts/           # Phase 1 output (OpenAPI for visuals endpoints)
└── tasks.md             # Phase 2 output (already exists - 52 tasks)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── api/
│   │   └── routes/
│   │       └── visuals.py        # NEW: Upload, serve, delete endpoints
│   ├── db/
│   │   └── mongo.py              # UPDATE: Add GridFS helper
│   ├── models/
│   │   └── visuals.py            # UPDATE: Extend VisualAsset, add VisualAssignment
│   └── services/
│       ├── gridfs_service.py     # NEW: GridFS operations
│       ├── visual_asset_service.py # NEW: Upload, thumbnail, hash
│       └── image_utils.py        # NEW: Pillow utilities
└── tests/
    └── integration/
        └── test_visuals_endpoints.py  # NEW: Upload/serve/delete tests

frontend/
├── src/
│   ├── components/
│   │   └── tab2/
│   │       ├── Tab2Content.tsx       # UPDATE: New layout
│   │       ├── FileUploadDropzone.tsx # NEW
│   │       ├── AssetCard.tsx         # NEW
│   │       ├── AssetGrid.tsx         # NEW
│   │       ├── OpportunityCard.tsx   # NEW
│   │       ├── OpportunityList.tsx   # NEW
│   │       ├── AssetPickerModal.tsx  # NEW
│   │       └── AssetMetadataModal.tsx # NEW (P2)
│   ├── context/
│   │   └── ProjectContext.tsx    # UPDATE: Add visual asset actions
│   ├── services/
│   │   └── visualsApi.ts         # NEW: Upload, serve URL helper
│   ├── types/
│   │   └── visuals.ts            # UPDATE: Add VisualAssignment type
│   └── utils/
│       └── visualMigration.ts    # NEW: Legacy project.visuals migration
└── tests/
    └── (manual acceptance for MVP)
```

**Structure Decision**: Web application with existing backend/frontend split. New files follow established patterns (routes in `api/routes/`, services in `services/`, components in `components/tab2/`).

## Complexity Tracking

No constitution violations requiring justification. Design follows existing patterns.

## Key Architectural Decisions

### 1. Binary Storage: GridFS

**Decision**: Store image binaries in MongoDB GridFS, not filesystem.
**Rationale**:
- Keeps data co-located with project metadata
- Easier backup/restore (single DB)
- No filesystem permission issues
- Supports cloud deployment without separate object storage

### 2. Thumbnail Strategy: On-Upload

**Decision**: Generate thumbnails immediately during upload, store both variants.
**Rationale**:
- Avoids repeated processing on every view
- Enables fast grid rendering
- Storage cost is acceptable (512px max = ~50KB per thumb)

### 3. Project-Scoped Endpoints

**Decision**: All asset endpoints include `{project_id}` and verify ownership.
**Rationale**:
- Prevents cross-project data leakage
- Matches existing API patterns
- Enables future multi-user without redesign

### 4. Assignment Model: Records for Assigned/Skipped Only

**Decision**: Unassigned = no record. Only create VisualAssignment for assigned/skipped.
**Rationale**:
- Simpler queries (presence = state)
- No orphan record cleanup needed
- Matches spec section 4.3

### 5. MVP Assignment Flow: Opportunity-Driven

**Decision**: User assigns from OpportunityCard, not AssetCard.
**Rationale**:
- Clearer user mental model ("I need to fill this slot")
- Simpler UI (no reverse picker)
- AssetCard "Assign..." deferred to P2
