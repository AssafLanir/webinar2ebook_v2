# Spec 007 — Tab 4: EPUB Export

**Feature Branch**: `007-tab4-epub-export`
**Created**: 2025-12-31
**Status**: Draft
**Owner**: Assaf
**Scope**: MVP (P1) focused on **EPUB export** using ebooklib, mirroring the async job pattern from Spec 006.

---

## 0. Summary

Tab 4 currently supports PDF export (Spec 006). This spec adds:

1. **EPUB export** option alongside existing PDF export
2. Same async job pattern (job_id → polling → cancel)
3. Same data inputs (draft markdown + visual assignments + metadata)

EPUB is a widely-used ebook format compatible with Kindle, Apple Books, Kobo, and other e-readers.

---

## 1. Goals

- Add **EPUB export** option in Tab 4 alongside existing PDF export
- Reuse existing final assembly inputs:
  - `project.draftText` (markdown)
  - `project.visualPlan.assignments` (which images are assigned)
  - `project.visualPlan.assets` (image metadata + GridFS storage)
  - `project.finalTitle`, `project.finalSubtitle`, `project.creditsText`
- Insert assigned images at render time (do NOT modify stored markdown)
- Use same async job pattern as PDF export (Spec 006)
- Generate reflowable EPUB 3.0 format
- Embed images inside EPUB package

---

## 2. Non-Goals (for this spec)

- No Gamma export / MCP integration
- No "Design Pack ZIP" export (Spec 008)
- No new editor UI beyond adding EPUB option
- No EPUB-specific styling/themes beyond basic formatting
- No DRM or encryption
- No fixed-layout EPUB (only reflowable)
- No advanced EPUB features (audio, video, JavaScript)

---

## 3. User Stories

### US1 (P1) — Export ebook as EPUB

As a user, I can download my assembled ebook as an EPUB file with all content and images embedded.

**Why this priority**: EPUB is the standard ebook format for e-readers. Users need this to distribute their ebook on platforms like Amazon Kindle, Apple Books, and Kobo.

**Independent Test**: Click "Export EPUB" → EPUB file downloads with correct content and images readable in any e-reader app.

**Acceptance Scenarios**:

1. **Given** a project with draftText and images, **When** user clicks "Export EPUB", **Then** system starts EPUB generation and shows progress
2. **Given** EPUB generation completes, **When** user is notified, **Then** EPUB file downloads automatically with filename `{safe_title}_{YYYY-MM-DD}.epub`
3. **Given** EPUB generation is in progress, **When** user clicks cancel, **Then** generation stops and no file is produced
4. **Given** a project with missing images (deleted assets), **When** user exports EPUB, **Then** EPUB renders without those images (graceful degradation)
5. **Given** exported EPUB file, **When** user opens it in an e-reader, **Then** content displays correctly with proper chapter navigation

---

### US2 (P2) — Export format selection

As a user, I can choose between PDF and EPUB formats when exporting my ebook.

**Why this priority**: Users need flexibility to choose the right format for their distribution channel.

**Independent Test**: Export dropdown shows both PDF and EPUB options → each produces correct file format.

**Acceptance Scenarios**:

1. **Given** Tab 4 is open, **When** user views export options, **Then** both "PDF" and "EPUB" options are available
2. **Given** user selects EPUB, **When** export completes, **Then** downloaded file has `.epub` extension
3. **Given** user selects PDF, **When** export completes, **Then** downloaded file has `.pdf` extension (existing behavior)

---

### Edge Cases

- What happens when an assigned image was deleted from GridFS? → Render without that image, no error shown
- What happens when draftText is empty? → Show error, disable export button
- What happens when EPUB generation times out? → Show error message, allow retry
- What happens when title contains special characters? → Sanitize for filename (replace with underscores)
- What happens when image format is not EPUB-compatible? → Convert to JPEG/PNG during EPUB assembly
- What happens when markdown contains unsupported elements? → Render as best effort, skip unsupported elements

---

## 4. Tab 4 UX / UI

### 4.1 Changes to Existing Layout

The export section in Tab 4 is modified:

**Current (Spec 006)**:
- Single "Download PDF" button

**New (Spec 007)**:
- Export dropdown/selector with options: "PDF", "EPUB"
- "Export" button that triggers selected format
- Or: Two separate buttons "Download PDF" / "Download EPUB"

**Recommended approach**: Two separate buttons for clarity:
- "Download PDF" (existing)
- "Download EPUB" (new)

Both buttons share the same progress/cancel UI when export is in progress.

### 4.2 Progress and Status

Same UX as PDF export:
- Progress bar during generation
- Cancel button when in progress
- Success state with download link
- Error state with retry option

### 4.3 EPUB Content Structure

The generated EPUB contains:

1. **Cover Page** (cover.xhtml)
   - Title (large, centered)
   - Subtitle (if present)
   - Credits (if present)

2. **Table of Contents** (toc.ncx + nav.xhtml)
   - Auto-generated from H1/H2 headings in draft
   - EPUB3 navigation document

3. **Chapters** (chapter-N.xhtml)
   - Each top-level section becomes a chapter
   - Images inserted at assigned opportunities
   - Basic CSS styling for readability

4. **Images** (/images/ folder)
   - All assigned images embedded in EPUB package
   - Referenced by relative paths in chapter HTML

5. **Stylesheet** (styles.css)
   - Basic typography for readability
   - Responsive to e-reader settings

---

## 5. API Endpoints

### 5.1 Start Export Job (Modified)

```
POST /api/projects/{project_id}/ebook/export
```

**Request Body**:
```json
{
  "format": "epub"
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
- `format` now accepts: `"pdf"` | `"epub"`
- Same endpoint as Spec 006, extended to support EPUB
- Returns immediately with job_id

### 5.2 Check Export Status (Unchanged)

```
GET /api/projects/{project_id}/ebook/export/status/{job_id}
```

**Response** (same as Spec 006):
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

### 5.3 Download Export File (Extended)

```
GET /api/projects/{project_id}/ebook/export/download/{job_id}
```

**Response for EPUB**: Binary EPUB stream with headers:
- `Content-Type: application/epub+zip`
- `Content-Disposition: attachment; filename="{safe_title}_{YYYY-MM-DD}.epub"`

**Filename Rules** (same as PDF):
- Title precedence: `finalTitle` → `name` → "ebook"
- Filename sanitization: Replace non-alphanumeric chars (except spaces/hyphens) with underscores
- Max filename length: 80 characters (truncate if longer)
- Date format: YYYY-MM-DD

### 5.4 Cancel Export Job (Unchanged)

```
POST /api/projects/{project_id}/ebook/export/cancel/{job_id}
```

**Response** (same as Spec 006):
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

### 6.1 Export Job (Extended)

Extends Spec 006 ExportJob:

```
ExportJob:
  - job_id: string (UUID)
  - project_id: string
  - format: "pdf" | "epub"  # Extended to include epub
  - status: "pending" | "processing" | "completed" | "failed" | "cancelled"
  - progress: number (0-100)
  - created_at: datetime
  - updated_at: datetime
  - result_path: string (path to generated file, if completed)
  - error_message: string (if failed)
```

### 6.2 Existing Entities Used (Same as Spec 006)

- `Project.draftText` - Markdown content
- `Project.finalTitle`, `Project.finalSubtitle`, `Project.creditsText` - Cover page content
- `Project.outlineItems` - For TOC generation (optional)
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
| EXPORT_FAILED | 500 | EPUB generation failed |
| INVALID_FORMAT | 400 | Requested format not supported (not pdf/epub) |
| IMAGE_PROCESSING_ERROR | 500 | Failed to process/embed image (logged, graceful degradation) |

---

## 8. Requirements

### Functional Requirements

- **FR-001**: System MUST generate EPUB 3.0 format files
- **FR-002**: System MUST embed all assigned images inside EPUB package
- **FR-003**: System MUST generate navigation document (TOC) from markdown headings
- **FR-004**: System MUST insert assigned images at their designated chapter/section locations
- **FR-005**: System MUST use async job pattern with progress tracking (same as PDF)
- **FR-006**: System MUST allow cancellation of in-progress export jobs
- **FR-007**: System MUST sanitize filenames for download (safe characters only)
- **FR-008**: System MUST gracefully handle missing images (render without them)
- **FR-009**: System MUST generate cover page with title, subtitle, and credits
- **FR-010**: System MUST produce valid EPUB files that pass epubcheck validation
- **FR-011**: System MUST support both PDF and EPUB export from same UI

### Key Entities

- **ExportJob**: Tracks async EPUB generation (job_id, status, progress, result)
- **EpubGenerator**: Service that assembles markdown + images into EPUB package

---

## 9. Success Criteria

### Measurable Outcomes

- **SC-001**: EPUB export completes within 30 seconds for typical ebooks (10 chapters, 20 images)
- **SC-002**: Exported EPUB file size is reasonable (under 50MB for typical content)
- **SC-003**: 95% of EPUB export attempts succeed without errors
- **SC-004**: Exported EPUB files pass epubcheck validation
- **SC-005**: Users can open exported EPUB in common e-readers (Apple Books, Calibre, Kindle app)

---

## 10. Dependencies

### New Dependencies

- **ebooklib**: Python library for EPUB generation (BSD licensed)
- No new system-level dependencies (pure Python)

### Integration Notes

- Add to `backend/pyproject.toml`: `ebooklib`
- ebooklib handles EPUB structure (OPF, NCX, container.xml)
- Images must be JPEG or PNG (convert if needed using existing Pillow dependency)

---

## 11. Assumptions

- EPUB files stored on local disk (`/tmp/webinar2ebook/exports/`); same as PDF (single-instance deployment)
- Job state stored in MongoDB with TTL cleanup (same pattern as PDF export)
- Single concurrent export per project is sufficient for MVP
- ebooklib produces valid EPUB files without extensive configuration
- Basic CSS styling is sufficient for MVP (no custom themes)
- Reflowable EPUB is the only layout mode needed (no fixed-layout)

---

## 12. Future Work (Explicitly Deferred)

- **Spec 008**: Design Pack ZIP export (markdown + images + manifest for external tools)
- **Post-MVP**: Gamma export / MCP integration
- **Post-MVP**: Custom EPUB themes/templates
- **Post-MVP**: EPUB accessibility features (WCAG compliance)
- **Post-MVP**: Advanced typography (custom fonts, drop caps)
