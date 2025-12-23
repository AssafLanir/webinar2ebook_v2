# Quickstart: Tab 4 Final Assembly + Export

**Date**: 2025-12-23

## Prerequisites

### System Dependencies (WeasyPrint)

WeasyPrint requires system libraries for PDF rendering. Install before the Python package.

**macOS (Homebrew)**:
```bash
brew install pango gdk-pixbuf libffi
```

**Ubuntu/Debian**:
```bash
sudo apt-get update
sudo apt-get install -y \
  libpango-1.0-0 \
  libpangocairo-1.0-0 \
  libgdk-pixbuf2.0-0 \
  libffi-dev \
  shared-mime-info
```

**Docker (Alpine)**:
```dockerfile
RUN apk add --no-cache \
  pango \
  gdk-pixbuf \
  fontconfig \
  ttf-dejavu
```

### Python Dependencies

Add to `backend/pyproject.toml`:
```toml
[project.dependencies]
# ... existing deps
weasyprint = ">=60.0"
markdown = ">=3.5"
```

Install:
```bash
cd backend
pip install -e .
```

---

## Local Development

### 1. Start Services

```bash
# Start MongoDB (if using docker-compose)
docker-compose up -d mongodb

# Start backend
cd backend
uvicorn src.api.main:app --reload --port 8000

# Start frontend
cd frontend
npm run dev
```

### 2. Create Test Project

Using existing project with:
- Draft text (Tab 3)
- Visual assignments (Tab 2)
- Final metadata set

### 3. Test Preview Endpoint

```bash
# Get HTML preview
curl "http://localhost:8000/api/projects/{project_id}/ebook/preview"

# Response: { "data": { "html": "<!DOCTYPE html>..." }, "error": null }
```

### 4. Test PDF Export Flow

```bash
# Start export
curl -X POST "http://localhost:8000/api/projects/{project_id}/ebook/export" \
  -H "Content-Type: application/json" \
  -d '{"format": "pdf"}'
# Response: { "data": { "job_id": "abc123" }, "error": null }

# Check status (poll until completed)
curl "http://localhost:8000/api/projects/{project_id}/ebook/export/status/abc123"
# Response: { "data": { "job_id": "abc123", "status": "completed", "progress": 100, "download_url": "/api/..." }, "error": null }

# Download PDF
curl -o ebook.pdf "http://localhost:8000/api/projects/{project_id}/ebook/export/download/abc123"
```

---

## Test Scenarios

### US1: Preview with Images

1. Create project with draft text
2. Upload image via Tab 2
3. Create visual opportunity and assign image
4. Navigate to Tab 4
5. Verify preview shows:
   - Cover page with title/subtitle/credits
   - Table of contents
   - Chapter content with assigned images

### US2: PDF Export

1. Same setup as US1
2. Click "Download PDF"
3. Verify progress indicator shows
4. Verify PDF downloads on completion
5. Open PDF and verify:
   - Cover page renders correctly
   - TOC has clickable links
   - Images appear at correct locations
   - Styling is print-appropriate

### US3: Edit Metadata

1. In Tab 4, edit finalTitle field
2. Verify preview updates immediately
3. Export PDF
4. Verify PDF cover shows updated title

### Edge Cases

1. **No draft**: Preview shows empty state, export disabled
2. **No images**: Preview/PDF renders without images (no placeholders)
3. **Missing image**: Graceful degradation (skip missing)
4. **Cancel export**: Progress stops, no file produced
5. **Special characters in title**: Filename sanitized correctly

---

## Directory Structure After Implementation

```text
backend/
├── src/
│   ├── models/
│   │   ├── export_job.py           # ExportJob, ExportJobStatus
│   │   └── api_responses.py        # PreviewResponse, ExportStartResponse, etc.
│   ├── services/
│   │   ├── export_job_store.py     # ExportJobStore (MongoDB/in-memory)
│   │   ├── ebook_renderer.py       # EbookRenderer service
│   │   └── pdf_generator.py        # PdfGenerator (WeasyPrint wrapper)
│   └── api/
│       └── routes/
│           └── ebook.py            # All ebook/export endpoints
└── tests/
    ├── unit/
    │   ├── test_ebook_renderer.py
    │   └── test_export_job.py
    └── integration/
        └── test_pdf_export.py

frontend/
├── src/
│   ├── components/
│   │   └── tab4/
│   │       ├── Tab4Content.tsx
│   │       ├── MetadataPanel.tsx
│   │       ├── PreviewPanel.tsx
│   │       ├── ExportActions.tsx
│   │       └── index.ts
│   ├── hooks/
│   │   └── useExport.ts
│   ├── services/
│   │   └── exportApi.ts
│   └── types/
│       └── export.ts
```

---

## Common Issues

### WeasyPrint "missing pango" error

Install system dependencies first (see Prerequisites).

### Images not appearing in PDF

- Check GridFS storage key is correct
- Verify assignment status is "assigned"
- Check base64 encoding (look for data URI in HTML)

### Slow PDF generation

- Large images increase processing time
- Consider resizing before embedding
- Typical 20-image ebook: 10-20 seconds
