# Data Model: Tab 4 Final Assembly + Export

**Date**: 2025-12-23

## New Entities

### ExportJob

Tracks async PDF export jobs. Follows same pattern as `GenerationJob` from Spec 004.

```python
class ExportFormat(str, Enum):
    pdf = "pdf"
    # Future: epub = "epub", docx = "docx"

class ExportJobStatus(str, Enum):
    pending = "pending"      # Job created, not started
    processing = "processing"  # PDF generation in progress
    completed = "completed"  # PDF ready for download
    failed = "failed"        # Generation failed
    cancelled = "cancelled"  # User cancelled

class ExportJob(BaseModel):
    job_id: str              # UUID
    project_id: str          # References Project.id
    format: ExportFormat     # "pdf" for now
    status: ExportJobStatus  # Job state
    progress: int            # 0-100 percentage
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    result_path: Optional[str]   # Path to generated file (if completed)
    download_filename: Optional[str]  # Sanitized filename for download
    error_message: Optional[str]  # Error details (if failed)
    cancel_requested: bool = False
```

**State Transitions**:
```
pending → processing → completed
                   ↘ failed
                   ↘ cancelled (if cancel_requested)
```

**MongoDB Collection**: `export_jobs`

**TTL**: 1 hour after completion (same as generation jobs)

---

### API Response Models

Following existing envelope pattern `{ data, error }`.

```python
# Preview response
class PreviewData(BaseModel):
    html: str  # Complete HTML document with embedded styles

class PreviewResponse(BaseModel):
    data: Optional[PreviewData]
    error: Optional[ErrorDetail]

# Export start response
class ExportStartData(BaseModel):
    job_id: str

class ExportStartResponse(BaseModel):
    data: Optional[ExportStartData]
    error: Optional[ErrorDetail]

# Export status response
class ExportStatusData(BaseModel):
    job_id: str
    status: ExportJobStatus
    progress: int
    download_url: Optional[str]  # Present when status=completed

class ExportStatusResponse(BaseModel):
    data: Optional[ExportStatusData]
    error: Optional[ErrorDetail]

# Export cancel response
class ExportCancelData(BaseModel):
    cancelled: bool

class ExportCancelResponse(BaseModel):
    data: Optional[ExportCancelData]
    error: Optional[ErrorDetail]
```

---

## Existing Entities Used

### Project (from backend/src/models/project.py)

Relevant fields for Tab 4:

| Field | Type | Usage |
|-------|------|-------|
| id | str | Project identifier |
| name | str | Fallback for title |
| draftText | str | Markdown content to render |
| finalTitle | str | Cover page title (editable) |
| finalSubtitle | str | Cover page subtitle (editable) |
| creditsText | str | Cover page credits (editable) |
| visualPlan | VisualPlan | Visual opportunities + assignments + assets |

### VisualPlan (from backend/src/models/visuals.py)

```python
class VisualPlan(BaseModel):
    opportunities: List[VisualOpportunity]  # Where images should go
    assets: List[VisualAsset]               # Uploaded images
    assignments: List[VisualAssignment]     # Links opportunities to assets
```

### VisualAssignment (from backend/src/models/visuals.py)

```python
class VisualAssignment(BaseModel):
    opportunity_id: str         # References VisualOpportunity.id
    status: VisualAssignmentStatus  # "assigned" or "skipped"
    asset_id: Optional[str]     # References VisualAsset.id (when assigned)
    user_notes: Optional[str]
    updated_at: str
```

### VisualOpportunity (from backend/src/models/visuals.py)

```python
class VisualOpportunity(BaseModel):
    id: str
    chapter_index: int          # 1-based chapter index
    section_path: Optional[str] # Section identifier within chapter
    title: str                  # Visual title
    caption: str               # Caption for figure
    # ... other fields
```

### VisualAsset (from backend/src/models/visuals.py)

```python
class VisualAsset(BaseModel):
    id: str
    filename: str
    media_type: str            # e.g., "image/png"
    storage_key: Optional[str] # GridFS key
    caption: Optional[str]
    alt_text: Optional[str]
    # ... other fields
```

---

## Image Insertion Logic

At render time, the ebook renderer:

1. Parse `draftText` markdown into chapters (split on `# ` headings)
2. For each `VisualOpportunity`:
   - Find matching `VisualAssignment` with `status="assigned"`
   - If found, get the `VisualAsset` by `asset_id`
   - Insert `<figure>` HTML at the appropriate location:
     - If `section_path` matches a heading anchor → insert after that heading
     - Otherwise → insert at start of chapter (after `<h1>`)
3. Skip opportunities with no assignment or `status="skipped"`

**Figure HTML**:
```html
<figure>
  <img src="{image_url_or_data_uri}" alt="{asset.alt_text or asset.caption or asset.filename}">
  <figcaption>{asset.caption or asset.filename}</figcaption>
</figure>
```

---

## File Storage

### Temporary PDF Files

- Generated PDFs stored temporarily in `/tmp/webinar2ebook/exports/`
- Path pattern: `/tmp/webinar2ebook/exports/{job_id}.pdf`
- Cleaned up by TTL (job expires → file deleted)

### Download Filename

Sanitized from project title:
```python
def sanitize_filename(title: str) -> str:
    """Replace non-alphanumeric chars with underscores."""
    safe = re.sub(r'[^a-zA-Z0-9\s-]', '_', title)
    safe = re.sub(r'\s+', '_', safe)
    return safe.strip('_') or 'ebook'

# Example: "My Amazing E-Book!" → "My_Amazing_E-Book"
# Filename: "My_Amazing_E-Book_2025-12-23.pdf"
```

---

## Validation Rules

### Preview Request
- Project must exist (404 if not found)
- No draftText → empty state response (not error)

### Export Request
- Project must exist (404 if not found)
- Must have draftText (400 NO_DRAFT_CONTENT if empty)
- Format must be "pdf" (400 INVALID_FORMAT otherwise)

### Export Download
- Job must exist (404 EXPORT_JOB_NOT_FOUND)
- Job must be completed (400 EXPORT_NOT_READY if not)
- File must exist (500 EXPORT_FAILED if missing)
