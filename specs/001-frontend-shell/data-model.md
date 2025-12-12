# Data Model: Webinar2Ebook Ground Zero - Frontend Shell

**Feature**: 001-frontend-shell
**Date**: 2025-12-09

## Overview

This document defines the TypeScript interfaces for the frontend-only prototype. All data is held in-memory via React Context during a session. These types will be implemented in `frontend/src/types/project.ts`.

---

## Core Entities

### Project

The central data container holding all ebook conversion state.

```typescript
interface Project {
  // Identity & Metadata
  projectId: string;           // Unique identifier (UUID)
  title: string;               // Working project/ebook title
  webinarType: WebinarType;    // Type of source webinar
  createdAt: Date;             // Session creation timestamp

  // Stage 1: Transcript, Outline & Resources
  transcriptText: string;
  outlineItems: OutlineItem[];
  resources: Resource[];

  // Stage 2: Visuals
  visuals: Visual[];

  // Stage 3: Draft
  draftText: string;
  styleConfig: StyleConfig;

  // Stage 4: Final & Export
  finalTitle: string;
  finalSubtitle: string;
  creditsText: string;
}
```

**Validation Rules**:
- `projectId`: Auto-generated, immutable after creation
- `title`: Required, non-empty string (validated at creation)
- `webinarType`: Must be valid enum value
- All other fields: Optional/empty initially, no validation required

**State Transitions**:
- Created → Active (only transition; no save/load in Ground Zero)

---

### WebinarType (Enum)

```typescript
type WebinarType = 'standard_presentation' | 'training';
```

**Values**:
| Value | Display Label |
|-------|--------------|
| `standard_presentation` | Standard Presentation |
| `training` | Training |

---

### OutlineItem

A chapter or section in the ebook structure.

```typescript
interface OutlineItem {
  id: string;           // Unique identifier (UUID)
  title: string;        // Chapter/section title
  level: number;        // Hierarchy level (1 = top-level chapter, 2 = subsection, etc.)
  notes?: string;       // Optional notes/description
  order: number;        // Position in list for sorting
}
```

**Validation Rules**:
- `id`: Auto-generated on creation
- `title`: Required when adding (can be empty string initially)
- `level`: Defaults to 1; valid range 1-3
- `order`: Managed by reorder operations

**Relationships**:
- Belongs to: Project (one-to-many)
- Referenced by: Tab 4 chapter preview

---

### Resource

A reference item (link, note, or source material).

```typescript
interface Resource {
  id: string;           // Unique identifier (UUID)
  label: string;        // Display name/title
  urlOrNote: string;    // URL or descriptive text
  order: number;        // Position in list
}
```

**Validation Rules**:
- `id`: Auto-generated on creation
- `label`: Required (non-empty)
- `urlOrNote`: Optional; can be URL or free text

**Relationships**:
- Belongs to: Project (one-to-many)

---

### Visual

An image or diagram entry for ebook inclusion.

```typescript
interface Visual {
  id: string;           // Unique identifier (UUID)
  title: string;        // Visual title/caption
  description: string;  // Description of the visual
  selected: boolean;    // Whether to include in ebook export
  isCustom: boolean;    // True if user-added (vs. pre-populated example)
  order: number;        // Position in gallery
}
```

**Validation Rules**:
- `id`: Auto-generated on creation
- `selected`: Defaults to false for examples, true for custom
- `isCustom`: Set at creation, immutable

**Relationships**:
- Belongs to: Project (one-to-many)
- Referenced by: Tab 4 visuals preview (filtered by `selected: true`)

---

### StyleConfig

Draft generation style preferences.

```typescript
interface StyleConfig {
  audience: AudienceType;
  tone: ToneType;
  depth: DepthLevel;
  targetPages: number;
}
```

**Nested Types**:

```typescript
type AudienceType =
  | 'general'
  | 'technical'
  | 'executive'
  | 'academic';

type ToneType =
  | 'formal'
  | 'conversational'
  | 'instructional'
  | 'persuasive';

type DepthLevel =
  | 'overview'
  | 'moderate'
  | 'comprehensive';
```

**Default Values**:
```typescript
const DEFAULT_STYLE_CONFIG: StyleConfig = {
  audience: 'general',
  tone: 'conversational',
  depth: 'moderate',
  targetPages: 20
};
```

---

## Factory Functions

```typescript
// Create new project with defaults
function createProject(title: string, webinarType: WebinarType): Project;

// Create new outline item
function createOutlineItem(title: string, level?: number): OutlineItem;

// Create new resource
function createResource(label: string, urlOrNote?: string): Resource;

// Create new custom visual
function createCustomVisual(title: string, description: string): Visual;
```

---

## Context State Shape

The React Context will hold:

```typescript
interface ProjectState {
  project: Project | null;      // null = on landing page
  activeTab: TabIndex;          // Current tab (1-4)
  isExportModalOpen: boolean;   // Export modal visibility
}

type TabIndex = 1 | 2 | 3 | 4;
```

---

## Action Types (for useReducer)

```typescript
type ProjectAction =
  // Project lifecycle
  | { type: 'CREATE_PROJECT'; payload: { title: string; webinarType: WebinarType } }

  // Tab navigation
  | { type: 'SET_ACTIVE_TAB'; payload: TabIndex }

  // Tab 1: Transcript, Outline & Resources
  | { type: 'UPDATE_TRANSCRIPT'; payload: string }
  | { type: 'ADD_OUTLINE_ITEM'; payload: { title: string; level?: number } }
  | { type: 'UPDATE_OUTLINE_ITEM'; payload: { id: string; updates: Partial<OutlineItem> } }
  | { type: 'REMOVE_OUTLINE_ITEM'; payload: string }
  | { type: 'REORDER_OUTLINE_ITEMS'; payload: string[] }  // Array of IDs in new order
  | { type: 'ADD_RESOURCE'; payload: { label: string; urlOrNote?: string } }
  | { type: 'UPDATE_RESOURCE'; payload: { id: string; updates: Partial<Resource> } }
  | { type: 'REMOVE_RESOURCE'; payload: string }
  | { type: 'FILL_SAMPLE_DATA' }

  // Tab 2: Visuals
  | { type: 'TOGGLE_VISUAL_SELECTION'; payload: string }
  | { type: 'ADD_CUSTOM_VISUAL'; payload: { title: string; description: string } }

  // Tab 3: Draft
  | { type: 'UPDATE_STYLE_CONFIG'; payload: Partial<StyleConfig> }
  | { type: 'UPDATE_DRAFT'; payload: string }
  | { type: 'GENERATE_SAMPLE_DRAFT' }

  // Tab 4: Final & Export
  | { type: 'UPDATE_FINAL_TITLE'; payload: string }
  | { type: 'UPDATE_FINAL_SUBTITLE'; payload: string }
  | { type: 'UPDATE_CREDITS'; payload: string }
  | { type: 'TOGGLE_EXPORT_MODAL' };
```

---

## Sample Data Constants

Pre-populated example visuals (loaded on project creation):

```typescript
const EXAMPLE_VISUALS: Omit<Visual, 'id' | 'order'>[] = [
  {
    title: "Introduction Slide",
    description: "Opening slide with webinar title and presenter info",
    selected: false,
    isCustom: false
  },
  {
    title: "Key Concepts Diagram",
    description: "Visual overview of main topics covered",
    selected: false,
    isCustom: false
  },
  {
    title: "Process Flow Chart",
    description: "Step-by-step workflow illustration",
    selected: false,
    isCustom: false
  },
  {
    title: "Data Comparison Table",
    description: "Side-by-side comparison of options discussed",
    selected: false,
    isCustom: false
  },
  {
    title: "Architecture Overview",
    description: "System or concept architecture diagram",
    selected: false,
    isCustom: false
  },
  {
    title: "Summary Infographic",
    description: "Visual summary of key takeaways",
    selected: false,
    isCustom: false
  }
];
```

---

## Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                         Project                              │
├─────────────────────────────────────────────────────────────┤
│ projectId: string (PK)                                       │
│ title: string                                                │
│ webinarType: WebinarType                                     │
│ createdAt: Date                                              │
│ transcriptText: string                                       │
│ draftText: string                                            │
│ finalTitle: string                                           │
│ finalSubtitle: string                                        │
│ creditsText: string                                          │
│ styleConfig: StyleConfig (embedded)                          │
└─────────────────────────────────────────────────────────────┘
          │ 1:N              │ 1:N              │ 1:N
          ▼                  ▼                  ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  OutlineItem    │  │    Resource     │  │     Visual      │
├─────────────────┤  ├─────────────────┤  ├─────────────────┤
│ id: string (PK) │  │ id: string (PK) │  │ id: string (PK) │
│ title: string   │  │ label: string   │  │ title: string   │
│ level: number   │  │ urlOrNote: str  │  │ description: str│
│ notes?: string  │  │ order: number   │  │ selected: bool  │
│ order: number   │  └─────────────────┘  │ isCustom: bool  │
└─────────────────┘                       │ order: number   │
                                          └─────────────────┘
```
