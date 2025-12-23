# Spec 006 — Tab 4: Final Assembly + Preview + PDF Export

**Feature Branch**: `006-tab4-export`
**Created**: 2025-12-23
**Status**: Draft
**Owner**: Assaf
**Scope**: MVP (P1) focused on **HTML preview** with inserted images and **PDF export** via WeasyPrint.

---

## 0. Summary

Tab 4 should let a user:

1. **Preview** the assembled ebook as rendered HTML (cover + TOC + chapters + images)
2. **Export** the ebook as a downloadable PDF file
3. Edit final metadata (title, subtitle, credits) before export

This spec combines draft markdown + visual assignments into a complete ebook preview and PDF output.

---

## 1. Goals

- Render an **HTML preview** in Tab 4 that combines:
  - `project.draftText` (markdown)
  - `project.visualPlan.opportunities` (where images should go)
  - `project.visualPlan.assignments` (which images are assigned)
  - `project.visualPlan.assets` (image metadata + GridFS storage)
- Insert assigned images at render time (do NOT modify stored markdown)
- Generate **PDF export** using WeasyPrint
- Use job-based async pattern for PDF generation (like Spec 004 draft generation)
- Support cover page (title, subtitle, credits) and auto-generated TOC

---

## 2. Non-Goals (for this spec)

- No EPUB or DOCX export (Spec 007)
- No advanced typography, headers/footers, page numbers (Spec 007)
- No custom templates or themes
- No inline markdown modification (images inserted at render time only)
- No image editing/cropping in preview

---

## 3. User Stories

### US1 (P1) — Preview assembled ebook with images

As a user, I can see a rendered preview of my ebook in Tab 4 that includes:
- Cover page with title, subtitle, and credits
- Table of contents generated from headings
- Chapters rendered from markdown
- Assigned images inserted at appropriate locations

**Why this priority**: Users need to see how their ebook looks with images before exporting. This validates that Tab 2 assignments are correct.

**Independent Test**: Open Tab 4 with a project that has draft + assigned images → preview shows chapters with images in place.

**Acceptance Scenarios**:

1. **Given** a project with draftText and visual assignments, **When** user views Tab 4, **Then** preview panel shows rendered ebook with images inserted at assigned opportunities
2. **Given** a project with no assignments, **When** user views Tab 4, **Then** preview shows ebook without images (no empty placeholders)
3. **Given** a project with no draftText, **When** user views Tab 4, **Then** preview shows empty state prompting user to generate draft in Tab 3

---

### US2 (P1) — Export ebook as PDF

As a user, I can download my assembled ebook as a PDF file with all content and images embedded.

**Why this priority**: PDF is the primary deliverable format. Users need to produce a client-ready file.

**Independent Test**: Click "Download PDF" → PDF file downloads with correct content and images.

**Acceptance Scenarios**:

1. **Given** a project with draftText and images, **When** user clicks "Download PDF", **Then** system starts PDF generation and shows progress
2. **Given** PDF generation completes, **When** user is notified, **Then** PDF file downloads automatically with filename `{safe_title}_{YYYY-MM-DD}.pdf`
3. **Given** PDF generation is in progress, **When** user clicks cancel, **Then** generation stops and no file is produced
4. **Given** a project with missing images (deleted assets), **When** user exports PDF, **Then** PDF renders without those images (graceful degradation)

---

### US3 (P2) — Edit final metadata

As a user, I can edit the title, subtitle, and credits that appear on the cover page before exporting.

**Why this priority**: Users may want to customize the final presentation without changing the draft content.

**Independent Test**: Edit title in Tab 4 → preview updates → export PDF shows new title.

**Acceptance Scenarios**:

1. **Given** Tab 4 is open, **When** user edits finalTitle field, **Then** preview cover page updates immediately
2. **Given** user edits metadata, **When** changes are saved, **Then** values persist on page refresh

---

### Edge Cases

- What happens when an assigned image was deleted from GridFS? → Render without that image, no error shown
- What happens when draftText is empty? → Show empty state, disable export button
- What happens when PDF generation times out? → Show error message, allow retry
- What happens when project has no outline/headings? → TOC section is omitted
- What happens when title contains special characters? → Sanitize for filename (replace with underscores)

---

## 4. Tab 4 UX / UI

### 4.1 Layout

Tab 4 has three sections:

**A) Metadata Panel (top)**
- Editable fields: Final Title, Final Subtitle, Credits
- Auto-populated from project.finalTitle, project.finalSubtitle, project.creditsText
- Changes trigger preview refresh

**B) Preview Panel (main area)**
- Rendered HTML view of the ebook in sandboxed iframe (no scripts allowed)
- Scrollable container with page-like styling
- Sections:
  - **Cover Page**: Title (large), subtitle, credits
  - **Table of Contents**: Auto-generated from H1/H2 headings in draft
  - **Chapters**: Rendered markdown with images inserted at opportunities
- Empty state if no draft: "Generate a draft in Tab 3 to see preview"

**C) Export Actions (bottom/header)**
- "Download PDF" button with dropdown (future: other formats)
- Progress indicator during generation
- Cancel button when generation in progress

### 4.2 Image Insertion Rules

Images are inserted at render time based on visual assignments:

1. For each `VisualOpportunity` with a matching `VisualAssignment` (status=assigned):
   - Find the chapter by `chapter_index` (1-based)
   - If `section_path` exists and matches a heading anchor, insert after that heading
   - Otherwise, insert at the start of the chapter (after chapter heading)
2. Render as: `<figure><img src="..." alt="..."><figcaption>...</figcaption></figure>`
3. Use caption from asset metadata; fallback to filename
4. Use alt_text from asset metadata; fallback to caption

### 4.3 Cover Page Design

Simple styled HTML:
- Title: Large, bold, centered
- Subtitle: Medium, centered, below title
- Credits: Smaller, centered, at bottom of cover
- Optional: Simple border or background color
- No graphics or complex layouts for MVP

### 4.4 Table of Contents

- Extract H1 and H2 headings from rendered markdown
- Generate anchor links for each
- Display as numbered list with indentation for H2s
- Skip if no headings found

---

## 5. API Endpoints

### 5.1 Preview Endpoint

```
GET /api/projects/{project_id}/ebook/preview?include_images=true|false
```

**Query Parameters**:
- `include_images` (optional, default: true) - Include assigned images in preview

**Response** (success):
```json
{
  "data": {
    "html": "<html>...</html>"
  },
  "error": null
}
```

**Response** (error):
```json
{
  "data": null,
  "error": {
    "code": "PROJECT_NOT_FOUND",
    "message": "Project not found"
  }
}
```

**Notes**:
- Images rendered as `<img src="http://localhost:8000/api/projects/{id}/visuals/assets/{asset_id}/content?size=full">`
- Preview is generated on-demand (not cached)

### 5.2 Start Export Job

```
POST /api/projects/{project_id}/ebook/export
```

**Request Body**:
```json
{
  "format": "pdf"
}
```

**Response** (success):
```json
{
  "data": {
    "job_id": "abc123"
  },
  "error": null
}
```

**Notes**:
- Returns immediately with job_id
- PDF generation runs asynchronously
- For PDF: images embedded as base64 data URIs (not HTTP URLs) to avoid WeasyPrint fetch issues

### 5.3 Check Export Status

```
GET /api/projects/{project_id}/ebook/export/status/{job_id}
```

**Response** (in progress):
```json
{
  "data": {
    "job_id": "abc123",
    "status": "processing",
    "progress": 45,
    "download_url": null
  },
  "error": null
}
```

**Response** (completed):
```json
{
  "data": {
    "job_id": "abc123",
    "status": "completed",
    "progress": 100,
    "download_url": "/api/projects/{project_id}/ebook/export/download/abc123"
  },
  "error": null
}
```

**Status values**: `pending`, `processing`, `completed`, `failed`, `cancelled`

### 5.4 Download Export File

```
GET /api/projects/{project_id}/ebook/export/download/{job_id}
```

**Response**: Binary PDF stream with headers:
- `Content-Type: application/pdf`
- `Content-Disposition: attachment; filename="{safe_title}_{YYYY-MM-DD}.pdf"`

**Notes**:
- Filename title precedence: `finalTitle` → `name` → "ebook"
- Filename sanitization: Replace non-alphanumeric chars (except spaces/hyphens) with underscores
- Max filename length: 80 characters (truncate if longer)

### 5.5 Cancel Export Job

```
POST /api/projects/{project_id}/ebook/export/cancel/{job_id}
```

**Response**:
```json
{
  "data": {
    "cancelled": true
  },
  "error": null
}
```

---

## 6. Data Model

### 6.1 Export Job

Reuse pattern from Spec 004 (GenerationJob):

```
ExportJob:
  - job_id: string (UUID)
  - project_id: string
  - format: "pdf" | "epub" | "docx" (future)
  - status: "pending" | "processing" | "completed" | "failed" | "cancelled"
  - progress: number (0-100)
  - created_at: datetime
  - updated_at: datetime
  - result_path: string (path to generated file, if completed)
  - error_message: string (if failed)
```

### 6.2 Existing Entities Used

- `Project.draftText` - Markdown content
- `Project.finalTitle`, `Project.finalSubtitle`, `Project.creditsText` - Cover page content
- `Project.outlineItems` - For TOC generation (optional, can also parse from markdown)
- `Project.visualPlan.opportunities` - Where images should be inserted
- `Project.visualPlan.assignments` - Which images are assigned
- `Project.visualPlan.assets` - Image metadata

---

## 7. Error Handling

| Code | HTTP | When |
|------|------|------|
| PROJECT_NOT_FOUND | 404 | Project ID doesn't exist |
| NO_DRAFT_CONTENT | 400 | Project has no draftText |
| EXPORT_JOB_NOT_FOUND | 404 | Job ID doesn't exist |
| EXPORT_NOT_READY | 400 | Download requested but job not completed |
| EXPORT_FAILED | 500 | PDF generation failed |
| INVALID_FORMAT | 400 | Requested format not supported |

---

## 8. Requirements

### Functional Requirements

- **FR-001**: System MUST render HTML preview combining markdown draft with assigned images
- **FR-002**: System MUST generate cover page with title, subtitle, and credits
- **FR-003**: System MUST generate table of contents from document headings
- **FR-004**: System MUST insert assigned images at their designated chapter/section locations
- **FR-005**: System MUST export ebook as PDF with all content and images embedded
- **FR-006**: System MUST use async job pattern for PDF generation with progress tracking
- **FR-007**: System MUST allow cancellation of in-progress export jobs
- **FR-008**: System MUST sanitize filenames for download (safe characters only)
- **FR-009**: System MUST gracefully handle missing images (render without them)
- **FR-010**: System MUST embed images as data URIs in PDF (not HTTP URLs)

### Key Entities

- **ExportJob**: Tracks async PDF generation (job_id, status, progress, result)
- **EbookRenderer**: Service that combines markdown + images into HTML
- **PdfGenerator**: Service that converts HTML to PDF via WeasyPrint

---

## 9. Success Criteria

### Measurable Outcomes

- **SC-001**: Users can preview their ebook with images in under 3 seconds
- **SC-002**: PDF export completes within 30 seconds for typical ebooks (10 chapters, 20 images)
- **SC-003**: Exported PDF file size is reasonable (under 50MB for typical content)
- **SC-004**: 95% of export attempts succeed without errors
- **SC-005**: Users can complete the full workflow (Tab 1 → Tab 3 → Tab 2 → Tab 4 → PDF) in a single session

---

## 10. Dependencies

### New Dependencies

- **WeasyPrint**: Python library for HTML/CSS to PDF conversion
- **System packages for WeasyPrint**: cairo, pango, gdk-pixbuf (required for PDF rendering)

### Integration Notes

- WeasyPrint requires system-level dependencies (not pure Python)
- Docker/CI environments need these packages installed
- Add to `backend/pyproject.toml`: `weasyprint`
- Update `spec0_tech.md` with WeasyPrint dependency note

---

## 11. Assumptions

- Preview rendering is fast enough to not require caching (regenerate on each request)
- PDF files stored on local disk (`/tmp/webinar2ebook/exports/`); single-instance deployment assumed for MVP
- Job state stored in MongoDB with TTL cleanup (same pattern as Spec 004 draft generation, with in-memory fallback for testing)
- Single concurrent export per project is sufficient for MVP
- WeasyPrint produces acceptable PDF quality without extensive CSS customization
