# Quickstart: Tab 4 EPUB Export

**Date**: 2025-12-31
**Feature**: [spec.md](./spec.md)

## Prerequisites

- Python 3.11+
- Node.js 18+
- MongoDB running locally
- Existing Spec 006 (PDF export) implementation

## Setup

### 1. Install ebooklib

```bash
cd backend
pip install ebooklib>=0.18
```

Or add to `pyproject.toml`:

```toml
[project]
dependencies = [
    # ... existing deps
    "ebooklib>=0.18",
]
```

Then:

```bash
pip install -e .
```

### 2. Verify Installation

```python
# Quick test
from ebooklib import epub

book = epub.EpubBook()
book.set_identifier('test-123')
book.set_title('Test Book')
book.set_language('en')

chapter = epub.EpubHtml(title='Test', file_name='test.xhtml')
chapter.content = '<html><body><h1>Test</h1></body></html>'
book.add_item(chapter)

book.toc = (epub.Link('test.xhtml', 'Test', 'test'),)
book.add_item(epub.EpubNcx())
book.add_item(epub.EpubNav())
book.spine = ['nav', chapter]

epub.write_epub('/tmp/test.epub', book)
print("EPUB created successfully!")
```

## Development Workflow

### Backend

```bash
cd backend
source .venv/bin/activate  # or venv/bin/activate

# Run tests
python -m pytest tests/unit/test_epub_generator.py -v
python -m pytest tests/integration/test_epub_export.py -v

# Run server
uvicorn src.api.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend

# Run dev server
npm run dev

# Build
npm run build
```

### Test EPUB Export

1. Create a project with draft text and images
2. Navigate to Tab 4 (Export)
3. Click "Download EPUB"
4. Verify EPUB downloads with correct content

### Validate EPUB (Optional)

Install epubcheck for validation:

```bash
# macOS
brew install epubcheck

# Validate
epubcheck /tmp/webinar2ebook/exports/your-export.epub
```

## File Locations

| What | Where |
|------|-------|
| EpubGenerator service | `backend/src/services/epub_generator.py` |
| Unit tests | `backend/tests/unit/test_epub_generator.py` |
| Integration tests | `backend/tests/integration/test_epub_export.py` |
| Export endpoint | `backend/src/api/routes/ebook.py` |
| Frontend button | `frontend/src/components/tab4/ExportActions.tsx` |

## Key Patterns

### Async Job Pattern (from Spec 006)

```python
# Start export
POST /api/projects/{id}/ebook/export
Body: {"format": "epub"}
Response: {"data": {"job_id": "abc123"}}

# Poll status
GET /api/projects/{id}/ebook/export/status/{job_id}
Response: {"data": {"status": "processing", "progress": 45}}

# Download when complete
GET /api/projects/{id}/ebook/export/download/{job_id}
Response: Binary EPUB file
```

### Progress Callback

```python
async def generate_epub_with_progress(project, output_path, job_store, job_id):
    async def update_progress(pct: int):
        await job_store.update_progress(job_id, pct)

    generator = EpubGenerator()
    await generator.generate(project, output_path, progress_callback=update_progress)
```

## Common Issues

### "No module named 'ebooklib'"

```bash
pip install ebooklib>=0.18
```

### EPUB validation errors

Run epubcheck to see specific issues:

```bash
epubcheck output.epub
```

Common fixes:
- Ensure proper XML escaping in chapter content
- Verify image MIME types match file extensions
- Check that all images referenced in HTML are added to book

### Images not showing in EPUB

1. Verify images are added to book: `book.add_item(image_item)`
2. Check file paths match: `src="images/abc123.jpg"`
3. Ensure correct MIME type: `image/jpeg` or `image/png`
