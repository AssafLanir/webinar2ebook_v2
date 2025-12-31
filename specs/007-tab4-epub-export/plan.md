# Implementation Plan: Tab 4 EPUB Export

**Branch**: `007-tab4-epub-export` | **Date**: 2025-12-31 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/007-tab4-epub-export/spec.md`

## Summary

Tab 4 currently supports PDF export (Spec 006). This spec adds EPUB export using ebooklib, reusing the existing async job pattern (job_id → polling → cancel) and the same input data (markdown draft + visual assignments + metadata). EPUB is a pure Python solution with no system dependencies.

## Technical Context

**Language/Version**: Python 3.11 (backend), TypeScript 5.x (frontend)
**Primary Dependencies**:
- Backend: FastAPI, Pydantic v2, motor (async MongoDB), ebooklib (EPUB generation)
- Frontend: React 18, Vite, Tailwind CSS (minor UI additions)
**Storage**: MongoDB (projects, export jobs), GridFS (images), local disk (temp EPUB files)

**Temp File Lifecycle** (mirrors Spec 006 PDF pattern):
- **Location**: `/tmp/webinar2ebook/exports/{job_id}.epub`
- **Naming**: `{job_id}.epub` (UUID-based, unique per export)
- **Creation**: Written by EpubGenerator during async job execution
- **result_path**: Stores absolute path to generated file (e.g., `/tmp/webinar2ebook/exports/abc123.epub`)
- **Cleanup**: Deleted on MongoDB TTL expiration (job document cleanup triggers file deletion)
- **Download**: Served via FileResponse from result_path, then optionally deleted after successful download

**Testing**: pytest (backend)
**Target Platform**: Web application (Linux server backend, modern browsers frontend)
**Project Type**: Web application (backend + frontend)
**Performance Goals**: EPUB export <30 seconds for typical ebook (10 chapters, 20 images)
**Constraints**:
- Reflowable EPUB only (no fixed-layout)
- Images embedded in EPUB package as JPEG/PNG
- EPUB file size <50MB for typical content
**Scale/Scope**: Single-user projects, 8-15 chapters typical

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Note**: Constitution template has placeholders, so applying sensible defaults:

| Principle | Status | Notes |
|-----------|--------|-------|
| Existing patterns | PASS | Reuses ExportJobStore, API envelope pattern from Spec 006 |
| Test coverage | PASS | Integration tests for EPUB export flow |
| Single source of truth | PASS | Extends existing ExportFormat enum |
| Error handling | PASS | Same envelope pattern { data, error } |

## Project Structure

### Documentation (this feature)

```text
specs/007-tab4-epub-export/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (no new contracts needed)
├── checklists/          # Validation checklists
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── models/
│   │   └── export_job.py           # UPDATE: Add epub to ExportFormat enum
│   ├── services/
│   │   ├── epub_generator.py       # NEW: Markdown+images → EPUB
│   │   ├── ebook_renderer.py       # EXISTS: Reuse for chapter/image logic
│   │   ├── pdf_generator.py        # EXISTS: Unchanged
│   │   └── export_job_store.py     # EXISTS: Unchanged
│   └── api/
│       └── routes/
│           └── ebook.py            # UPDATE: Add epub format handling
└── tests/
    ├── unit/
    │   └── test_epub_generator.py  # NEW
    └── integration/
        └── test_epub_export.py     # NEW

frontend/
├── src/
│   ├── components/
│   │   └── tab4/
│   │       └── ExportActions.tsx   # UPDATE: Add EPUB button
│   ├── hooks/
│   │   └── useExport.ts            # EXISTS: Works for EPUB (format param)
│   ├── services/
│   │   └── exportApi.ts            # EXISTS: Works for EPUB (format param)
│   └── types/
│       └── export.ts               # UPDATE: Add epub to format type
└── tests/
    └── ...
```

**Structure Decision**: Minimal additions to existing structure. EPUB generator is new service; UI adds one button.

## Complexity Tracking

No violations requiring justification. The implementation extends Spec 006 patterns with a new generator service.

---

## Phase 0: Research Required

### Unknowns to Resolve

1. **ebooklib setup**: Python library installation and basic usage
2. **EPUB structure**: Required files and folder structure
3. **Image embedding**: How to embed images in EPUB package
4. **TOC generation**: How ebooklib handles navigation
5. **CSS for EPUB**: E-reader compatible styling

### Research Tasks

| Topic | Question | Output |
|-------|----------|--------|
| ebooklib basics | API for creating EPUB files with chapters | research.md section |
| EPUB structure | Required files (OPF, NCX, mimetype, etc.) | research.md section |
| Image handling | How to add images to EPUB package | research.md section |
| Navigation | TOC/NCX generation with ebooklib | research.md section |
| Styling | CSS patterns for e-reader compatibility | research.md section |

---

## Phase 1: Design Artifacts

### Entities (data-model.md)

| Entity | Source | Status |
|--------|--------|--------|
| ExportFormat | backend/src/models/export_job.py | UPDATE: Add "epub" value |
| EpubGenerator | NEW service | NEEDS DESIGN |
| Project (existing) | backend/src/models/project.py | EXISTS - unchanged |
| VisualPlan (existing) | backend/src/models/visuals.py | EXISTS - unchanged |

### API Contracts (contracts/)

| Endpoint | Method | Schema File | Status |
|----------|--------|-------------|--------|
| /api/projects/{id}/ebook/export | POST | (existing) | UPDATE: Accept format="epub" |
| /api/projects/{id}/ebook/export/status/{job_id} | GET | (existing) | UNCHANGED |
| /api/projects/{id}/ebook/export/download/{job_id} | GET | (binary) | UPDATE: Return EPUB |
| /api/projects/{id}/ebook/export/cancel/{job_id} | POST | (existing) | UNCHANGED |

**Note**: No new endpoint contracts needed. The existing export endpoints support the new format via the `format` parameter.

### Quickstart (quickstart.md)

Local development setup including ebooklib installation.

---

## What Already Exists (from Spec 006)

### Backend

- **Export Job Store** (`backend/src/services/export_job_store.py`):
  - MongoJobStore with TTL cleanup
  - Already supports job_id, status, progress, result_path
  - Just needs epub format to work

- **Export Endpoints** (`backend/src/api/routes/ebook.py`):
  - POST /export, GET /status, GET /download, POST /cancel
  - Already has format parameter - just need to handle "epub"

- **Ebook Renderer** (`backend/src/services/ebook_renderer.py`):
  - Combines markdown + images → structured data
  - Can reuse chapter extraction and image logic

- **Models** (`backend/src/models/export_job.py`):
  - ExportJob, ExportFormat enum
  - Just add "epub" to ExportFormat enum

### Frontend

- **Export UI** (`frontend/src/components/tab4/ExportActions.tsx`):
  - Button and progress UI
  - Add second button for EPUB

- **Export Hook** (`frontend/src/hooks/useExport.ts`):
  - Handles start, poll, cancel, download
  - Already accepts format parameter

- **Export API** (`frontend/src/services/exportApi.ts`):
  - API client functions
  - Already accepts format parameter

### What Needs Building

1. **EpubGenerator service** - markdown + images → EPUB file
2. **Update export endpoint** - handle format="epub"
3. **Update ExportFormat enum** - add "epub" value
4. **Update frontend** - add EPUB button
5. **Tests** - unit and integration for EPUB generation

### Integration Test Requirements

The integration tests MUST verify download response headers:

```python
# In test_epub_export.py
def test_epub_download_headers(client, completed_epub_job):
    """Verify EPUB download returns correct headers."""
    response = client.get(f"/api/projects/{project_id}/ebook/export/download/{job_id}")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/epub+zip"
    assert "attachment" in response.headers["content-disposition"]
    assert ".epub" in response.headers["content-disposition"]
    # Filename format: {safe_title}_{YYYY-MM-DD}.epub
    assert re.match(r'filename="[^"]+_\d{4}-\d{2}-\d{2}\.epub"',
                    response.headers["content-disposition"])
```

This prevents regressions on MIME type and filename format.

---

## Next Steps

1. **Phase 0**: Generate `research.md` to resolve ebooklib unknowns
2. **Phase 1**: Generate `data-model.md`, `quickstart.md`
3. **Phase 2**: Run `/speckit.tasks` to generate implementation tasks
