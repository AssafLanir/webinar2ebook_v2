# Implementation Plan: Tab 4 Final Assembly + Preview + PDF Export

**Branch**: `006-tab4-export` | **Date**: 2025-12-23 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/006-tab4-export/spec.md`

## Summary

Tab 4 completes the webinar-to-ebook workflow by rendering an HTML preview (combining markdown draft + visual assignments) and exporting to PDF via WeasyPrint. Uses the existing async job pattern (from Spec 004) for long-running PDF generation with progress tracking and cancellation support.

## Technical Context

**Language/Version**: Python 3.11 (backend), TypeScript 5.x (frontend)
**Primary Dependencies**:
- Backend: FastAPI, Pydantic v2, motor (async MongoDB), WeasyPrint (PDF generation), markdown (HTML rendering)
- Frontend: React 18, Vite, Tailwind CSS, React Context
**Storage**: MongoDB (projects, export jobs), GridFS (images)
**Testing**: pytest (backend), Vitest (frontend)
**Target Platform**: Web application (Linux server backend, modern browsers frontend)
**Project Type**: Web application (backend + frontend)
**Performance Goals**: PDF export <30 seconds for typical ebook (10 chapters, 20 images)
**Constraints**:
- Preview rendering <3 seconds
- Images embedded as base64 data URIs in PDF (WeasyPrint HTTP fetch workaround)
- PDF file size <50MB for typical content
**Scale/Scope**: Single-user projects, 8-15 chapters typical

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Note**: Constitution template has placeholders, so applying sensible defaults:

| Principle | Status | Notes |
|-----------|--------|-------|
| Existing patterns | PASS | Reuses job store pattern from Spec 004, API envelope pattern |
| Test coverage | PASS | Integration tests for export flow |
| Single source of truth | PASS | Pydantic models canonical, HTML rendered from markdown |
| Error handling | PASS | Envelope pattern { data, error } with defined error codes |

## Project Structure

### Documentation (this feature)

```text
specs/006-tab4-export/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (API contracts)
├── checklists/          # Validation checklists
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── models/
│   │   ├── export_job.py           # NEW: ExportJob model
│   │   └── api_responses.py        # UPDATE: Export response models
│   ├── services/
│   │   ├── job_store.py            # EXISTS: Reuse/extend for export jobs
│   │   ├── export_job_store.py     # NEW: Export-specific job store
│   │   ├── ebook_renderer.py       # NEW: Markdown+images → HTML
│   │   └── pdf_generator.py        # NEW: HTML → PDF via WeasyPrint
│   └── api/
│       └── routes/
│           └── ebook.py            # NEW: Export endpoints
└── tests/
    ├── unit/
    │   ├── test_ebook_renderer.py  # NEW
    │   └── test_export_job.py      # NEW
    └── integration/
        └── test_pdf_export.py      # NEW

frontend/
├── src/
│   ├── components/
│   │   └── tab4/
│   │       ├── Tab4Content.tsx     # NEW: Main tab container
│   │       ├── MetadataPanel.tsx   # NEW: Title/subtitle/credits editing
│   │       ├── PreviewPanel.tsx    # NEW: HTML preview renderer
│   │       ├── ExportActions.tsx   # NEW: Export button + progress
│   │       └── index.ts            # NEW: Exports
│   ├── hooks/
│   │   └── useExport.ts            # NEW: Export hook with polling
│   ├── services/
│   │   └── exportApi.ts            # NEW: API client
│   └── types/
│       └── export.ts               # NEW: TypeScript types
└── tests/
    └── ...
```

**Structure Decision**: Web application with existing backend/frontend split. This feature adds export service layer (reusing job pattern) and Tab 4 frontend components.

## Complexity Tracking

No violations requiring justification. The implementation follows established patterns from Spec 004 (draft generation job pattern).

---

## Phase 0: Research Required

### Unknowns to Resolve

1. **WeasyPrint setup**: System dependencies (cairo, pango, gdk-pixbuf) required on Linux/macOS/Docker
2. **Image embedding strategy**: Best approach for base64 data URIs in HTML for WeasyPrint
3. **TOC generation**: Library choice for extracting headings and generating anchor links
4. **Markdown rendering**: Library choice (markdown, markdown-it-py, mistune) with HTML output
5. **CSS styling for PDF**: Print-friendly CSS for WeasyPrint rendering

### Research Tasks

| Topic | Question | Output |
|-------|----------|--------|
| WeasyPrint dependencies | System packages needed for cairo/pango on Ubuntu/macOS/Docker | research.md section |
| Image data URIs | Best practice for embedding images as base64 in HTML for PDF | research.md section |
| Markdown to HTML | Library comparison for markdown → HTML with heading extraction | research.md section |
| PDF styling | CSS patterns for print-friendly PDF rendering | research.md section |
| Job store reuse | Can we extend existing GenerationJob or need separate ExportJob? | research.md section |

---

## Phase 1: Design Artifacts

### Entities (data-model.md)

| Entity | Source | Status |
|--------|--------|--------|
| ExportJob | NEW | NEEDS DESIGN |
| EbookPreview | NEW (response model) | NEEDS DESIGN |
| Project (existing) | backend/src/models/project.py | EXISTS - use finalTitle, finalSubtitle, creditsText |
| VisualPlan (existing) | backend/src/models/visuals.py | EXISTS - use for image insertion |
| VisualAssignment (existing) | backend/src/models/visuals.py | EXISTS - filter by status=assigned |
| VisualAsset (existing) | backend/src/models/visuals.py | EXISTS - get asset metadata |

### API Contracts (contracts/)

| Endpoint | Method | Schema File | Status |
|----------|--------|-------------|--------|
| /api/projects/{id}/ebook/preview | GET | PreviewResponse.json | NEW |
| /api/projects/{id}/ebook/export | POST | ExportStartResponse.json | NEW |
| /api/projects/{id}/ebook/export/status/{job_id} | GET | ExportStatusResponse.json | NEW |
| /api/projects/{id}/ebook/export/download/{job_id} | GET | (binary PDF) | NEW |
| /api/projects/{id}/ebook/export/cancel/{job_id} | POST | ExportCancelResponse.json | NEW |

### Quickstart (quickstart.md)

Local development setup including WeasyPrint system dependencies.

---

## What Already Exists

### Backend (from previous specs)

- **Job Store** (`backend/src/services/job_store.py`):
  - MongoJobStore with TTL cleanup
  - Can be extended or paralleled for export jobs

- **Models** (all in `backend/src/models/`):
  - `Project` with finalTitle, finalSubtitle, creditsText fields
  - `VisualPlan`, `VisualOpportunity`, `VisualAsset`, `VisualAssignment`
  - API envelope models pattern

- **GridFS Service** (`backend/src/services/gridfs_service.py`):
  - Store/retrieve binary assets
  - Fetch original images for embedding in PDF

### Frontend (from previous specs)

- Tab navigation infrastructure
- React Context for project state
- Type definitions for Project, VisualPlan, etc.
- Existing Tab 4 placeholder (likely needs replacement)

### What Needs Building

1. **EbookRenderer service** - combine markdown + images → HTML
2. **PdfGenerator service** - HTML → PDF via WeasyPrint
3. **Export job store** - track export job state (reuse pattern)
4. **Export API endpoints** - preview, start, status, download, cancel
5. **Tab 4 frontend** - metadata panel, preview panel, export actions

---

## Next Steps

1. **Phase 0**: Generate `research.md` to resolve unknowns
2. **Phase 1**: Generate `data-model.md`, `contracts/`, `quickstart.md`
3. **Phase 2**: Run `/speckit.tasks` to generate implementation tasks
