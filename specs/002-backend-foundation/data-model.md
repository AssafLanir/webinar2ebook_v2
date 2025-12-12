# Data Model: Backend Foundation

**Feature**: 002-backend-foundation
**Date**: 2025-12-11

## Entity Overview

```
┌─────────────────────────────────────────────────────────────┐
│                         Project                              │
├─────────────────────────────────────────────────────────────┤
│ id: string (MongoDB ObjectId)                               │
│ name: string (required)                                     │
│ webinarType: enum (required)                                │
│ createdAt: datetime                                         │
│ updatedAt: datetime                                         │
├─────────────────────────────────────────────────────────────┤
│ Stage 1 - Transcript & Structure                            │
│ ├── transcriptText: string                                  │
│ ├── outlineItems: OutlineItem[]                             │
│ └── resources: Resource[]                                   │
├─────────────────────────────────────────────────────────────┤
│ Stage 2-4 - Forward Compatible (optional)                   │
│ ├── visuals: Visual[]                                       │
│ ├── draftText: string                                       │
│ ├── styleConfig: StyleConfig                                │
│ ├── finalTitle: string                                      │
│ ├── finalSubtitle: string                                   │
│ └── creditsText: string                                     │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────┐  ┌─────────────────────────┐
│      OutlineItem        │  │        Resource         │
├─────────────────────────┤  ├─────────────────────────┤
│ id: string              │  │ id: string              │
│ title: string           │  │ label: string           │
│ level: number (1-3)     │  │ urlOrNote: string       │
│ notes: string (optional)│  │ order: number           │
│ order: number           │  └─────────────────────────┘
└─────────────────────────┘
```

---

## Entity Definitions

### Project

The root entity representing a webinar-to-ebook conversion project.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | string | Yes (auto) | MongoDB ObjectId, auto-generated |
| name | string | Yes | Project/ebook working title |
| webinarType | WebinarType | Yes | Type of webinar content |
| createdAt | datetime | Yes (auto) | ISO timestamp, set on creation |
| updatedAt | datetime | Yes (auto) | ISO timestamp, updated on any modification |
| transcriptText | string | No | Raw transcript text, may be empty |
| outlineItems | OutlineItem[] | No | Array of outline chapters/sections |
| resources | Resource[] | No | Array of reference links/notes |
| visuals | Visual[] | No | Future: selected visuals for ebook |
| draftText | string | No | Future: generated draft content |
| styleConfig | StyleConfig | No | Future: style preferences |
| finalTitle | string | No | Future: finalized ebook title |
| finalSubtitle | string | No | Future: finalized subtitle |
| creditsText | string | No | Future: credits/attribution |

### WebinarType (Enum)

| Value | Display Label |
|-------|---------------|
| `standard_presentation` | Standard Presentation |
| `training_tutorial` | Training / Tutorial |

### OutlineItem

A chapter or section in the ebook outline.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | string | Yes | Unique identifier within project |
| title | string | Yes | Chapter/section title |
| level | number | Yes | Hierarchy depth (1=chapter, 2=section, 3=subsection) |
| notes | string | No | Optional notes for this outline item |
| order | number | Yes | Display order within outline |

**Validation Rules**:
- `level` must be between 1 and 3 inclusive
- `order` must be non-negative integer
- `title` must not be empty

### Resource

A reference link or note attached to a project.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | string | Yes | Unique identifier within project |
| label | string | Yes | Display name for the resource |
| urlOrNote | string | No | URL or free-text note content |
| order | number | Yes | Display order within resources list |

**Validation Rules**:
- `label` must not be empty
- `order` must be non-negative integer

### Visual (Future - Stage 2)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | string | Yes | Unique identifier |
| title | string | Yes | Visual title |
| description | string | No | Visual description |
| selected | boolean | Yes | Whether selected for ebook |

### StyleConfig (Future - Stage 3)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| audience | string | No | Target audience descriptor |
| tone | string | No | Writing tone preference |
| depth | string | No | Content depth level |
| targetPages | number | No | Target page count |

---

## State Transitions

### Project Lifecycle

```
┌──────────────┐     POST /projects      ┌──────────────┐
│   (none)     │ ─────────────────────▶  │   Created    │
└──────────────┘                         └──────────────┘
                                                │
                                                │ PUT /projects/{id}
                                                ▼
                                         ┌──────────────┐
                                         │   Updated    │ ◀──┐
                                         └──────────────┘    │
                                                │            │
                                                │ PUT        │
                                                └────────────┘
                                                │
                                                │ DELETE /projects/{id}
                                                ▼
                                         ┌──────────────┐
                                         │   Deleted    │
                                         └──────────────┘
```

### Field Behavior

- `createdAt`: Set once on POST, never modified
- `updatedAt`: Updated on every PUT request
- `id`: Immutable after creation

---

## MongoDB Document Structure

```json
{
  "_id": ObjectId("..."),
  "name": "My Webinar Project",
  "webinarType": "standard_presentation",
  "createdAt": ISODate("2025-12-11T10:00:00Z"),
  "updatedAt": ISODate("2025-12-11T12:30:00Z"),
  "transcriptText": "Welcome to today's webinar...",
  "outlineItems": [
    {
      "id": "item-1",
      "title": "Introduction",
      "level": 1,
      "notes": "",
      "order": 0
    },
    {
      "id": "item-2",
      "title": "Key Concepts",
      "level": 1,
      "notes": "Cover the main ideas",
      "order": 1
    }
  ],
  "resources": [
    {
      "id": "res-1",
      "label": "Slide Deck",
      "urlOrNote": "https://example.com/slides.pdf",
      "order": 0
    }
  ],
  "visuals": [],
  "draftText": "",
  "styleConfig": null,
  "finalTitle": null,
  "finalSubtitle": null,
  "creditsText": null
}
```

---

## API Response DTOs

### ProjectSummary (for list endpoint)

```json
{
  "id": "string",
  "name": "string",
  "webinarType": "standard_presentation | training_tutorial",
  "updatedAt": "ISO datetime string"
}
```

### ProjectFull (for get/create/update endpoints)

Full Project document with all fields.

---

## Frontend Type Alignment

The frontend TypeScript types must match this model:

```typescript
// types/project.ts
type WebinarType = 'standard_presentation' | 'training_tutorial';

interface OutlineItem {
  id: string;
  title: string;
  level: number;
  notes?: string;
  order: number;
}

interface Resource {
  id: string;
  label: string;
  urlOrNote: string;
  order: number;
}

interface Project {
  id: string;
  name: string;
  webinarType: WebinarType;
  createdAt: string;
  updatedAt: string;
  transcriptText: string;
  outlineItems: OutlineItem[];
  resources: Resource[];
  // Stage 2-4 fields (optional)
  visuals?: Visual[];
  draftText?: string;
  styleConfig?: StyleConfig;
  finalTitle?: string;
  finalSubtitle?: string;
  creditsText?: string;
}
```
