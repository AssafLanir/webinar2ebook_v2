# Research: Tab 2 Visuals

**Phase 0 Output** | **Date**: 2025-12-23

This document captures research decisions for the Tab 2 Visuals feature.

---

## R1: Binary Storage Strategy

### Decision: MongoDB GridFS

**Rationale**:
- Co-locates binaries with project metadata in single database
- Native MongoDB feature, well-supported by motor (async driver)
- Automatic chunking for files > 16MB (though we cap at 10MB)
- Built-in metadata storage (filename, contentType, uploadDate)
- Simpler backup/restore vs. separate filesystem or S3

**Alternatives Considered**:

| Option | Pros | Cons | Rejected Because |
|--------|------|------|------------------|
| Local filesystem | Simple, fast | Permission issues, not portable, complicates Docker | Dev-only, not production-ready |
| S3/MinIO | Scalable, industry standard | Additional service dependency, credentials | Over-engineering for MVP |
| Base64 in MongoDB doc | No separate storage | 33% size overhead, slow queries | Performance impact |

**Implementation Notes**:
- Use `motor.motor_asyncio.AsyncIOMotorGridFSBucket`
- Store with key: `{asset_id}_{variant}` where variant is `original` or `thumb`
- Set `content_type` metadata for proper `Content-Type` header on serve

---

## R2: Image Processing Library

### Decision: Pillow (PIL)

**Rationale**:
- De facto standard for Python image processing
- Simple API for resize, format conversion
- Well-documented, stable, no native dependencies on most platforms
- Already used in similar projects

**Alternatives Considered**:

| Option | Pros | Cons | Rejected Because |
|--------|------|------|------------------|
| ImageMagick (via Wand) | More formats, CLI tools | Native dependency, heavier | Overkill for resize/convert |
| OpenCV | Fast, ML-ready | Complex API, large install | Not needed for thumbnails |
| Sharp (Node.js) | Very fast | Wrong language (Python backend) | N/A |

**Implementation Notes**:
- Thumbnail: `Image.thumbnail((512, 512), Image.Resampling.LANCZOS)`
- Format: PNG if alpha channel, else JPEG quality=85
- Compute dimensions before/after for metadata

---

## R3: Hash Algorithm for Deduplication

### Decision: SHA-256

**Rationale**:
- Cryptographically secure, collision-resistant
- Standard choice for file integrity
- Fast enough for 10MB files (<100ms)
- Python `hashlib` is built-in, no deps

**Alternatives Considered**:

| Option | Pros | Cons | Rejected Because |
|--------|------|------|------------------|
| MD5 | Faster | Collision vulnerabilities | Security concerns |
| SHA-1 | Widely used | Deprecated for security | Not recommended |
| BLAKE3 | Fastest | External dependency | Not worth it for file sizes |

**Implementation Notes**:
- Compute on upload before GridFS write
- Store in `VisualAsset.sha256`
- Optional P2: Reject duplicates with same hash

---

## R4: Upload Validation Strategy

### Decision: Backend-First Validation

**Rationale**:
- Frontend validation can be bypassed (curl, scripts)
- Backend must be authoritative for security
- Return structured errors for frontend to display

**Validation Rules**:
1. File type: `image/png`, `image/jpeg`, `image/webp` only
2. File size: ≤ 10MB per file
3. File count: ≤ 10 files per upload request
4. Asset count: ≤ 50 total assets per project (soft limit)

**Error Codes**:
- `UNSUPPORTED_MEDIA_TYPE`: Wrong content-type
- `UPLOAD_TOO_LARGE`: File exceeds 10MB
- `TOO_MANY_FILES`: More than 10 files in request
- `TOO_MANY_ASSETS`: Project at 50 asset limit

---

## R5: Thumbnail Timing

### Decision: Generate On Upload (Eager)

**Rationale**:
- Avoids repeated processing on every page load
- Thumbnails are small (~50KB), storage is cheap
- Simplifies serve endpoint (just fetch bytes)

**Alternatives Considered**:

| Option | Pros | Cons | Rejected Because |
|--------|------|------|------------------|
| Lazy (on first request) | Saves storage if never viewed | Slow first load, complexity | UX impact |
| CDN/cache layer | Fastest repeated access | Additional infrastructure | Over-engineering |

**Implementation Notes**:
- Store both `{asset_id}_original` and `{asset_id}_thumb` in GridFS
- Serve endpoint uses `?size=thumb|full` parameter

---

## R6: Default Caption Behavior

### Decision: Server-Side Default from Filename

**Rationale**:
- Ensures UI never shows blank captions
- Provides meaningful default without user effort
- Can be overwritten via metadata edit (P2)

**Implementation**:
```python
# In visual_asset_service.py
if not caption:
    caption = Path(original_filename).stem  # filename without extension
```

---

## R7: Assignment Lifecycle

### Decision: Record Presence = State

**Rationale**:
- Unassigned: No `VisualAssignment` record exists
- Assigned: Record with `status="assigned"`, `asset_id` populated
- Skipped: Record with `status="skipped"`, `asset_id=null`

**Benefits**:
- Simple query: "find assignments for opportunity X"
- No cleanup of "unassigned" tombstone records
- Matches spec section 4.3 exactly

**On Asset Delete**:
- DELETE the `VisualAssignment` record (not set status)
- Opportunity becomes unassigned (no record = unassigned)

---

## R8: Project-Scoped Endpoint Pattern

### Decision: Include `{project_id}` in all visual endpoints

**Endpoints**:
```
POST   /api/projects/{project_id}/visuals/assets/upload
GET    /api/projects/{project_id}/visuals/assets/{asset_id}/content
DELETE /api/projects/{project_id}/visuals/assets/{asset_id}
```

**Security Check**:
```python
# In each endpoint
asset = get_asset(asset_id)
if asset_id not in project.visualPlan.assets:
    raise HTTPException(404, "Asset not found")
```

**Rationale**:
- Prevents cross-project data leakage
- Matches existing patterns (e.g., `/projects/{id}/files`)
- Enables future multi-tenant without redesign
