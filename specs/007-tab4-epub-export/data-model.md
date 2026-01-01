# Data Model: Tab 4 EPUB Export

**Date**: 2025-12-31
**Feature**: [spec.md](./spec.md)

## Entity Changes

### ExportFormat (UPDATE)

**File**: `backend/src/models/export_job.py`

Add "epub" to the existing enum:

```python
class ExportFormat(str, Enum):
    PDF = "pdf"
    EPUB = "epub"  # NEW
```

### ExportJob (UNCHANGED)

**File**: `backend/src/models/export_job.py`

No changes needed. The existing ExportJob model already supports:

```python
class ExportJob(BaseModel):
    job_id: str
    project_id: str
    format: ExportFormat  # Already supports new EPUB value
    status: ExportStatus
    progress: int = 0
    created_at: datetime
    updated_at: datetime
    result_path: Optional[str] = None
    error_message: Optional[str] = None
```

---

## New Service

### EpubGenerator

**File**: `backend/src/services/epub_generator.py`

New service that converts markdown + images → EPUB file.

**Interface**:

```python
class EpubGenerator:
    """Generates EPUB files from project content."""

    async def generate(
        self,
        project: Project,
        output_path: str,
        progress_callback: Optional[Callable[[int], Awaitable[None]]] = None
    ) -> None:
        """
        Generate EPUB file from project content.

        Args:
            project: Project with draftText, visualPlan, and metadata
            output_path: Path to write the .epub file
            progress_callback: Optional async callback for progress updates (0-100)

        Raises:
            ValueError: If project has no draftText
            EpubGenerationError: If EPUB generation fails
        """
```

**Dependencies**:
- `ebooklib` - EPUB generation
- `EbookRenderer` - Reuse chapter extraction and image logic from Spec 006

---

## Existing Entities Used (No Changes)

### Project

**File**: `backend/src/models/project.py`

Fields used for EPUB generation:

| Field | Type | Usage |
|-------|------|-------|
| `draftText` | `str` | Markdown content for chapters |
| `finalTitle` | `Optional[str]` | EPUB metadata and cover page |
| `finalSubtitle` | `Optional[str]` | Cover page subtitle |
| `creditsText` | `Optional[str]` | Cover page credits |
| `outlineItems` | `List[OutlineItem]` | Chapter structure (for TOC) |
| `visualPlan` | `Optional[VisualPlan]` | Image assignments |

### VisualPlan

**File**: `backend/src/models/visuals.py`

Fields used for image embedding:

| Field | Type | Usage |
|-------|------|-------|
| `opportunities` | `List[VisualOpportunity]` | Where images should be inserted |
| `assignments` | `Dict[str, str]` | opportunity_id → asset_id mapping |
| `assets` | `List[VisualAsset]` | Image metadata (gridfs_id, filename, etc.) |

### VisualAsset

**File**: `backend/src/models/visuals.py`

Fields used for image retrieval:

| Field | Type | Usage |
|-------|------|-------|
| `asset_id` | `str` | Unique identifier |
| `gridfs_id` | `str` | GridFS file ID for image data |
| `filename` | `str` | Original filename (for EPUB file naming) |
| `mime_type` | `str` | MIME type (image/jpeg, image/png) |

---

## EPUB Content Structure

The generated EPUB contains:

```
{safe_title}_{YYYY-MM-DD}.epub
├── mimetype
├── META-INF/
│   └── container.xml
└── EPUB/
    ├── content.opf           # Package document
    ├── toc.ncx              # EPUB 2.0 navigation
    ├── nav.xhtml            # EPUB 3.0 navigation
    ├── styles.css           # Stylesheet
    ├── cover.xhtml          # Cover page
    ├── chapter_01.xhtml     # Chapter content
    ├── chapter_02.xhtml
    └── images/
        ├── {asset_id}.jpg
        └── {asset_id}.png
```

**Note**: ebooklib generates mimetype, META-INF, content.opf, toc.ncx automatically. We create the content items (cover, chapters, images, stylesheet).

---

## Type Updates (Frontend)

### ExportFormat (UPDATE)

**File**: `frontend/src/types/export.ts`

```typescript
export type ExportFormat = 'pdf' | 'epub';  // Add 'epub'
```

No other frontend type changes needed - existing types support the new format.
