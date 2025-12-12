# Implementation Plan: Webinar2Ebook Ground Zero - Frontend Shell

**Branch**: `001-frontend-shell` | **Date**: 2025-12-09 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-frontend-shell/spec.md`

## Summary

Build a frontend-only prototype shell with a 4-tab workflow (Transcript/Outline/Resources → Visuals → Draft → Final/Export) to validate UX, navigation, and stage modularity. Uses React with TypeScript, Vite bundler, Tailwind CSS styling, and React Context for in-memory state management. No backend integration - all data persists in browser session only.

## Technical Context

**Language/Version**: TypeScript 5.x, React 18.x
**Primary Dependencies**: React, Vite, Tailwind CSS, React Context (state)
**Storage**: In-memory (React Context) - session persistence only, no database
**Testing**: Vitest (unit), React Testing Library (component), Playwright (e2e)
**Target Platform**: Modern web browsers (Chrome, Firefox, Safari, Edge)
**Project Type**: Web application (frontend-only for Ground Zero)
**Performance Goals**: <200ms perceived UI response time per SC-006
**Constraints**: Single-user, single-project, session-only persistence
**Scale/Scope**: 1 user, 1 project, 4 screens/tabs, ~15-20 components

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Status**: PASS - Constitution file contains template placeholders only; no project-specific rules defined yet. This feature establishes the initial codebase structure.

**Post-Design Re-check**: PASS - No violations as this is the initial feature establishing project patterns.

## Project Structure

### Documentation (this feature)

```text
specs/001-frontend-shell/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (minimal - frontend-only)
└── tasks.md             # Phase 2 output (created by /speckit.tasks)
```

### Source Code (repository root)

```text
frontend/
├── src/
│   ├── components/
│   │   ├── common/           # Shared UI components
│   │   │   ├── Button.tsx
│   │   │   ├── Input.tsx
│   │   │   ├── Textarea.tsx
│   │   │   ├── Select.tsx
│   │   │   ├── Modal.tsx
│   │   │   └── Card.tsx
│   │   ├── layout/           # Layout components
│   │   │   ├── TabBar.tsx
│   │   │   ├── TabNavigation.tsx
│   │   │   └── ProjectHeader.tsx
│   │   ├── tab1/             # Transcript, Outline & Resources
│   │   │   ├── TranscriptEditor.tsx
│   │   │   ├── OutlineEditor.tsx
│   │   │   ├── OutlineItem.tsx
│   │   │   ├── ResourceList.tsx
│   │   │   └── ResourceItem.tsx
│   │   ├── tab2/             # Visuals
│   │   │   ├── VisualGallery.tsx
│   │   │   ├── VisualCard.tsx
│   │   │   └── AddCustomVisual.tsx
│   │   ├── tab3/             # Draft
│   │   │   ├── StyleControls.tsx
│   │   │   └── DraftEditor.tsx
│   │   └── tab4/             # Final & Export
│   │       ├── MetadataForm.tsx
│   │       ├── StructurePreview.tsx
│   │       └── ExportButton.tsx
│   ├── context/
│   │   └── ProjectContext.tsx  # React Context for Project state
│   ├── pages/
│   │   ├── LandingPage.tsx     # Project creation
│   │   └── WorkspacePage.tsx   # 4-tab workflow container
│   ├── types/
│   │   └── project.ts          # TypeScript interfaces
│   ├── data/
│   │   └── sampleData.ts       # Hardcoded sample content
│   ├── utils/
│   │   ├── exportHelpers.ts    # Export functionality
│   │   └── idGenerator.ts      # ID generation utilities
│   ├── App.tsx
│   ├── main.tsx
│   └── index.css               # Tailwind imports
├── tests/
│   ├── unit/
│   │   └── context/
│   ├── component/
│   │   ├── tab1/
│   │   ├── tab2/
│   │   ├── tab3/
│   │   └── tab4/
│   └── e2e/
│       └── workflow.spec.ts
├── index.html
├── package.json
├── vite.config.ts
├── tailwind.config.js
├── tsconfig.json
└── vitest.config.ts
```

**Structure Decision**: Frontend-only SPA structure. Backend folder will be added in future features when API integration is needed. The frontend structure follows React best practices with components organized by feature/tab, shared context for state management, and clear separation of types, utilities, and sample data.

## Complexity Tracking

> No violations - this is the initial feature establishing baseline patterns.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| N/A | N/A | N/A |
