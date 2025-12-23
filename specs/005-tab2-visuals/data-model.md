# Data Model: Tab 2 Visuals

**Phase 1 Output** | **Date**: 2025-12-23

This document defines the data model extensions for the Tab 2 Visuals feature.

---

## Entity Overview

```
Project
└── visualPlan: VisualPlan
    ├── opportunities: VisualOpportunity[]  # From Tab 3 (existing)
    ├── assets: VisualAsset[]               # Extended in this spec
    └── assignments: VisualAssignment[]     # NEW in this spec
```

---

## VisualAsset (Extended)

**Location**: `backend/src/models/visuals.py`

### Existing Fields (unchanged)

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | UUID, primary key |
| `filename` | `str` | Display filename |
| `media_type` | `str` | MIME type (e.g., `image/png`) |
| `origin` | `VisualAssetOrigin` | Enum: `client_upload`, `ai_generated`, `external_url` |
| `source_url` | `Optional[str]` | For external assets |
| `storage_key` | `Optional[str]` | GridFS key for binaries |
| `width` | `Optional[int]` | Image width in pixels |
| `height` | `Optional[int]` | Image height in pixels |
| `alt_text` | `Optional[str]` | Accessibility text |
| `tags` | `List[str]` | User-defined tags |

### New Fields (P1)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `original_filename` | `Optional[str]` | `None` | Original upload filename (before sanitization) |
| `size_bytes` | `Optional[int]` | `None` | File size in bytes |
| `caption` | `Optional[str]` | filename stem | Display caption (defaults to filename without extension) |
| `sha256` | `Optional[str]` | `None` | SHA-256 hash of original bytes |
| `created_at` | `Optional[str]` | server time | ISO 8601 timestamp |

### Backend Model (Pydantic)

```python
class VisualAsset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: str(uuid4()))
    filename: str
    media_type: str
    origin: VisualAssetOrigin = VisualAssetOrigin.client_upload
    source_url: Optional[str] = None
    storage_key: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    alt_text: Optional[str] = None
    tags: List[str] = Field(default_factory=list)

    # New fields (P1)
    original_filename: Optional[str] = None
    size_bytes: Optional[int] = None
    caption: Optional[str] = None
    sha256: Optional[str] = None
    created_at: Optional[str] = None
```

### Frontend Type (TypeScript)

```typescript
interface VisualAsset {
  id: string;
  filename: string;
  media_type: string;
  origin: 'client_upload' | 'ai_generated' | 'external_url';
  source_url?: string;
  storage_key?: string;
  width?: number;
  height?: number;
  alt_text?: string;
  tags: string[];

  // New fields (P1)
  original_filename?: string;
  size_bytes?: number;
  caption?: string;
  sha256?: string;
  created_at?: string;
}
```

---

## VisualAssignment (New)

**Location**: `backend/src/models/visuals.py`

### Purpose

Links a `VisualOpportunity` to a `VisualAsset` (or marks it skipped).

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `opportunity_id` | `str` | Yes | References `VisualOpportunity.id` |
| `status` | `VisualAssignmentStatus` | Yes | `assigned` or `skipped` |
| `asset_id` | `Optional[str]` | No | References `VisualAsset.id` (required when `status=assigned`) |
| `user_notes` | `Optional[str]` | No | Optional user comment |
| `updated_at` | `str` | Yes | ISO 8601 timestamp |

### Status Enum

```python
class VisualAssignmentStatus(str, Enum):
    assigned = "assigned"
    skipped = "skipped"
```

### Lifecycle Rules

| State | Record Exists? | `status` | `asset_id` |
|-------|----------------|----------|------------|
| Unassigned | No | N/A | N/A |
| Assigned | Yes | `assigned` | `{asset_id}` |
| Skipped | Yes | `skipped` | `null` |

### Backend Model (Pydantic)

```python
class VisualAssignment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    opportunity_id: str
    status: VisualAssignmentStatus
    asset_id: Optional[str] = None
    user_notes: Optional[str] = None
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

    @model_validator(mode='after')
    def validate_asset_id(self) -> 'VisualAssignment':
        if self.status == VisualAssignmentStatus.assigned and not self.asset_id:
            raise ValueError("asset_id required when status is 'assigned'")
        return self
```

### Frontend Type (TypeScript)

```typescript
type VisualAssignmentStatus = 'assigned' | 'skipped';

interface VisualAssignment {
  opportunity_id: string;
  status: VisualAssignmentStatus;
  asset_id: string | null;
  user_notes: string | null;
  updated_at: string;
}
```

---

## VisualPlan (Updated)

**Location**: `backend/src/models/visuals.py`

### Updated Fields

| Field | Type | Description |
|-------|------|-------------|
| `opportunities` | `List[VisualOpportunity]` | AI-generated opportunities (from Tab 3) |
| `assets` | `List[VisualAsset]` | Uploaded image assets |
| `assignments` | `List[VisualAssignment]` | **NEW**: Opportunity-to-asset mappings |

### Backend Model

```python
class VisualPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    opportunities: List[VisualOpportunity] = Field(default_factory=list)
    assets: List[VisualAsset] = Field(default_factory=list)
    assignments: List[VisualAssignment] = Field(default_factory=list)  # NEW
```

### Migration/Defaulting

On project load, if `assignments` is missing, treat as empty list `[]`.

---

## GridFS Storage Model

**Not a Pydantic model** - direct GridFS metadata.

### Storage Keys

| Key Pattern | Description |
|-------------|-------------|
| `{asset_id}_original` | Full-size original image |
| `{asset_id}_thumb` | 512px max thumbnail |

### Metadata Fields (GridFS)

| Field | Value |
|-------|-------|
| `filename` | `{asset_id}_{variant}` |
| `content_type` | MIME type (e.g., `image/png`) |
| `metadata.project_id` | Project ID for ownership verification |
| `metadata.asset_id` | Asset ID for lookup |
| `metadata.variant` | `original` or `thumb` |

---

## Legacy Migration: project.visuals

### Current State

Some projects have `project.visuals[]` with legacy `Visual` objects:

```typescript
// Legacy type (Tab 2 before this spec)
interface Visual {
  id: string;
  title: string;
  description: string;
  url?: string;
  selected: boolean;
}
```

### Migration Strategy

1. On project load, check if `visualPlan.assets` exists
2. If not, map `project.visuals[]` to `visualPlan.assets[]`:

| Legacy `Visual` | Maps To `VisualAsset` |
|-----------------|----------------------|
| `id` | `id` |
| `title` | `caption` |
| `description` | `alt_text` |
| `url` | `source_url` |
| `selected` | (ignored) |

3. On first save from Tab 2, persist to `visualPlan.assets`
4. Leave `project.visuals` untouched (read-only legacy)

### Frontend Helper

```typescript
// frontend/src/utils/visualMigration.ts
export function migrateVisualsToAssets(
  legacyVisuals: Visual[]
): VisualAsset[] {
  return legacyVisuals.map(v => ({
    id: v.id,
    filename: v.title || 'untitled',
    media_type: 'image/png', // assume
    origin: 'external_url',
    source_url: v.url,
    caption: v.title,
    alt_text: v.description,
    tags: [],
  }));
}
```
