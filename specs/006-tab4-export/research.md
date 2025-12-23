# Research: Tab 4 Final Assembly + Export

**Date**: 2025-12-23
**Status**: Complete

## 1. WeasyPrint System Dependencies

**Decision**: Use WeasyPrint with documented system dependencies

**Rationale**: WeasyPrint is the most mature Python library for HTML-to-PDF conversion with good CSS support. It requires system libraries but these are well-documented and available on all major platforms.

**System Dependencies**:

```bash
# Ubuntu/Debian
apt-get install -y \
  libpango-1.0-0 \
  libpangocairo-1.0-0 \
  libgdk-pixbuf2.0-0 \
  libffi-dev \
  shared-mime-info

# macOS (via Homebrew)
brew install pango gdk-pixbuf libffi

# Alpine (Docker)
apk add --no-cache \
  pango \
  gdk-pixbuf \
  fontconfig \
  ttf-dejavu
```

**Python Installation**:
```bash
pip install weasyprint>=60.0
```

**Alternatives Considered**:
- **pdfkit/wkhtmltopdf**: Requires wkhtmltopdf binary, more complex installation, worse CSS support
- **reportlab**: Low-level API, doesn't accept HTML input
- **xhtml2pdf**: Less maintained, limited CSS support

---

## 2. Image Embedding Strategy

**Decision**: Embed images as base64 data URIs in HTML before PDF generation

**Rationale**: WeasyPrint can fetch images via HTTP, but this adds latency and potential auth issues. Base64 embedding ensures images are self-contained in the PDF.

**Implementation Pattern**:
```python
import base64

def embed_image(image_bytes: bytes, media_type: str) -> str:
    """Convert image bytes to data URI for HTML embedding."""
    b64 = base64.b64encode(image_bytes).decode('utf-8')
    return f"data:{media_type};base64,{b64}"

# Usage in HTML
# <img src="data:image/png;base64,iVBORw0KGgoAAAA..." alt="...">
```

**Performance Considerations**:
- Base64 increases size by ~33% but this is acceptable for typical ebook images
- Images already stored in GridFS; fetch once and embed
- For preview, can use HTTP URLs (faster); for PDF, embed as data URIs

**Alternatives Considered**:
- **HTTP URLs**: WeasyPrint timeout issues, auth complexity
- **Local file paths**: Security concerns, temporary file cleanup needed

---

## 3. Markdown to HTML Rendering

**Decision**: Use Python `markdown` library with toc extension

**Rationale**: Python-Markdown is the most mature library, included in many projects, and has built-in TOC support via the `toc` extension.

**Implementation**:
```python
import markdown
from markdown.extensions.toc import TocExtension

md = markdown.Markdown(extensions=[
    'tables',
    'fenced_code',
    TocExtension(
        baselevel=1,
        toc_depth=2,  # H1 and H2 only
        title='Table of Contents',
    ),
])

html_content = md.convert(markdown_text)
toc_html = md.toc  # Generated TOC HTML
```

**TOC Generation**:
- The `toc` extension automatically extracts headings and generates anchor IDs
- Access via `md.toc` after conversion
- Returns HTML `<div class="toc">` with nested `<ul>` lists

**Alternatives Considered**:
- **mistune**: Faster but less extension support
- **markdown-it-py**: Good but more complex setup for TOC
- **commonmark**: Strict spec compliance but no TOC extension

---

## 4. PDF Styling (CSS)

**Decision**: Use minimal print-friendly CSS with page breaks

**Rationale**: WeasyPrint supports most CSS including `@page` rules. Keep styling simple for MVP; can enhance in future specs.

**Core CSS**:
```css
@page {
  size: A4;
  margin: 2cm;
}

/* Cover page */
.cover {
  page-break-after: always;
  text-align: center;
  padding-top: 30%;
}

.cover h1 {
  font-size: 32pt;
  margin-bottom: 0.5em;
}

.cover h2 {
  font-size: 18pt;
  font-weight: normal;
  color: #666;
}

.cover .credits {
  position: absolute;
  bottom: 2cm;
  width: 100%;
  font-size: 10pt;
  color: #888;
}

/* Table of Contents */
.toc {
  page-break-after: always;
}

.toc h2 {
  font-size: 18pt;
  margin-bottom: 1em;
}

.toc ul {
  list-style-type: none;
  padding-left: 0;
}

.toc li {
  margin: 0.5em 0;
}

.toc li li {
  padding-left: 1.5em;
}

/* Chapter content */
h1 {
  page-break-before: always;
  font-size: 24pt;
}

h2 {
  font-size: 18pt;
  margin-top: 1.5em;
}

/* Images */
figure {
  text-align: center;
  margin: 1.5em 0;
  page-break-inside: avoid;
}

figure img {
  max-width: 100%;
  max-height: 400px;
}

figcaption {
  font-size: 10pt;
  color: #666;
  margin-top: 0.5em;
}

/* Avoid orphans/widows */
p {
  orphans: 3;
  widows: 3;
}
```

---

## 5. Job Store Strategy

**Decision**: Create separate ExportJobStore following same pattern as GenerationJob

**Rationale**: Export jobs have different state (format, result_path) than draft generation jobs. Separate stores avoid model complexity while reusing the same MongoDB/in-memory pattern.

**ExportJob vs GenerationJob**:

| Field | GenerationJob | ExportJob |
|-------|---------------|-----------|
| job_id | ✓ | ✓ |
| project_id | ✓ | ✓ |
| status | queued/planning/generating/completed/failed/cancelled | pending/processing/completed/failed/cancelled |
| progress | chapters completed | percentage (0-100) |
| result | draft_markdown, visual_plan | result_path (file path) |
| format | N/A | pdf/epub/docx (future) |

**Implementation**:
- Create `ExportJob` model in `backend/src/models/export_job.py`
- Create `ExportJobStore` in `backend/src/services/export_job_store.py`
- Reuse BaseJobStore pattern for MongoDB/in-memory support
- Separate collection: `export_jobs` (vs `generation_jobs`)

**Alternatives Considered**:
- **Extend GenerationJob**: Would add fields that are null for most jobs, confusing
- **Single generic Job model**: Over-engineering for current needs

---

## Summary

All unknowns resolved. Ready for Phase 1 design artifacts:

| Topic | Decision |
|-------|----------|
| PDF Library | WeasyPrint with system dependencies |
| Image Embedding | Base64 data URIs |
| Markdown Library | Python `markdown` with toc extension |
| PDF Styling | Minimal print-friendly CSS |
| Job Store | Separate ExportJobStore (same pattern) |
