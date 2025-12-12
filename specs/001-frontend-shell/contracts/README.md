# Contracts: Webinar2Ebook Ground Zero - Frontend Shell

**Feature**: 001-frontend-shell
**Date**: 2025-12-09

## Overview

This feature is **frontend-only** with no backend API. Contracts documented here are:

1. **Component Props Contracts** - TypeScript interfaces for React components
2. **Context API Contract** - Provider/consumer interface for ProjectContext
3. **Export File Contract** - Structure of the exported Markdown file

Backend API contracts will be added in future features when server integration is required.

---

## 1. Component Props Contracts

### Common Components

```typescript
// Button.tsx
interface ButtonProps {
  variant?: 'primary' | 'secondary' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
  disabled?: boolean;
  onClick?: () => void;
  children: React.ReactNode;
}

// Input.tsx
interface InputProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  label?: string;
  required?: boolean;
  disabled?: boolean;
}

// Textarea.tsx
interface TextareaProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  label?: string;
  rows?: number;
}

// Select.tsx
interface SelectOption {
  value: string;
  label: string;
}

interface SelectProps {
  value: string;
  onChange: (value: string) => void;
  options: SelectOption[];
  label?: string;
}

// Modal.tsx
interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
}

// Card.tsx
interface CardProps {
  title?: string;
  children: React.ReactNode;
  className?: string;
}
```

### Layout Components

```typescript
// TabBar.tsx
interface TabBarProps {
  activeTab: TabIndex;
  onTabChange: (tab: TabIndex) => void;
}

// TabNavigation.tsx
interface TabNavigationProps {
  activeTab: TabIndex;
  onPrevious: () => void;
  onNext: () => void;
}

// ProjectHeader.tsx
interface ProjectHeaderProps {
  title: string;
  webinarType: WebinarType;
}
```

### Tab-Specific Components

```typescript
// Tab 1 Components
interface TranscriptEditorProps {
  value: string;
  onChange: (value: string) => void;
}

interface OutlineEditorProps {
  items: OutlineItem[];
  onAdd: (title: string, level?: number) => void;
  onUpdate: (id: string, updates: Partial<OutlineItem>) => void;
  onRemove: (id: string) => void;
  onReorder: (orderedIds: string[]) => void;
}

interface ResourceListProps {
  resources: Resource[];
  onAdd: (label: string, urlOrNote?: string) => void;
  onUpdate: (id: string, updates: Partial<Resource>) => void;
  onRemove: (id: string) => void;
}

// Tab 2 Components
interface VisualGalleryProps {
  visuals: Visual[];
  onToggleSelection: (id: string) => void;
  onAddCustom: (title: string, description: string) => void;
}

interface VisualCardProps {
  visual: Visual;
  onToggle: () => void;
}

// Tab 3 Components
interface StyleControlsProps {
  config: StyleConfig;
  onChange: (updates: Partial<StyleConfig>) => void;
}

interface DraftEditorProps {
  value: string;
  onChange: (value: string) => void;
  onGenerate: () => void;
}

// Tab 4 Components
interface MetadataFormProps {
  finalTitle: string;
  finalSubtitle: string;
  creditsText: string;
  onTitleChange: (value: string) => void;
  onSubtitleChange: (value: string) => void;
  onCreditsChange: (value: string) => void;
}

interface StructurePreviewProps {
  chapters: OutlineItem[];      // From Tab 1
  visuals: Visual[];            // Selected visuals from Tab 2
}

interface ExportButtonProps {
  onExport: () => void;
}
```

---

## 2. Context API Contract

### Provider

```typescript
// ProjectContext.tsx

interface ProjectContextValue {
  state: ProjectState;
  dispatch: React.Dispatch<ProjectAction>;

  // Convenience methods (derived from dispatch)
  createProject: (title: string, webinarType: WebinarType) => void;
  setActiveTab: (tab: TabIndex) => void;

  // Computed values
  selectedVisuals: Visual[];    // visuals.filter(v => v.selected)
  hasProject: boolean;          // state.project !== null
}

// Usage
const ProjectProvider: React.FC<{ children: React.ReactNode }>;
const useProject: () => ProjectContextValue;
```

### State Shape

```typescript
interface ProjectState {
  project: Project | null;
  activeTab: TabIndex;
  isExportModalOpen: boolean;
}

// Initial state (before project creation)
const INITIAL_STATE: ProjectState = {
  project: null,
  activeTab: 1,
  isExportModalOpen: false
};
```

### Action Types

See `data-model.md` for complete `ProjectAction` union type.

---

## 3. Export File Contract

### Markdown Structure

When user clicks "Export", the generated file follows this structure:

```markdown
# {finalTitle}

## {finalSubtitle}

---

**Credits**: {creditsText}

**Generated from**: {project.title} ({webinarType})

---

## Table of Contents

{For each outlineItem where level === 1}
- Chapter {n}: {title}
  {For each outlineItem where level > 1 under this chapter}
  - {title}

---

## Included Visuals

{For each visual where selected === true}
- [{title}] {description}

---

## Content

{draftText}

---

*Exported on {export date}*
```

### File Metadata

| Property | Value |
|----------|-------|
| Filename | `{finalTitle or project.title}-ebook.md` |
| MIME Type | `text/markdown` |
| Encoding | UTF-8 |
| Max Size | N/A (client-side, session data only) |

---

## Future API Contracts

The following will be added when backend integration is implemented:

- `POST /api/projects` - Create project
- `GET /api/projects/{id}` - Get project
- `PUT /api/projects/{id}` - Update project
- `POST /api/projects/{id}/export` - Generate export
- `POST /api/transcribe` - AI transcription
- `POST /api/generate-outline` - AI outline generation
- `POST /api/generate-draft` - AI draft generation

These are **out of scope** for Ground Zero (001-frontend-shell).
