# Research: Webinar2Ebook Ground Zero - Frontend Shell

**Feature**: 001-frontend-shell
**Date**: 2025-12-09

## Overview

This document captures research decisions for the frontend-only prototype shell. Since this is Ground Zero (no backend, no AI), the research focuses on frontend architecture patterns and component library choices.

---

## Decision 1: State Management Approach

**Decision**: React Context with useReducer pattern

**Rationale**:
- Single-project, single-user scope makes Redux/Zustand overkill
- React Context is built-in, no additional dependencies
- useReducer provides predictable state updates for the Project object
- Aligns with tech spec recommendation: "React Context for shared Project object across tabs"
- Easy to migrate to TanStack Query later when backend is added

**Alternatives Considered**:
| Alternative | Rejected Because |
|-------------|------------------|
| Redux | Over-engineered for single-project prototype |
| Zustand | Additional dependency for minimal benefit at this scale |
| Jotai/Recoil | Atomic state not needed; we have one central Project object |
| Local component state | Would require prop drilling across 4+ tab components |

**Implementation Notes**:
- Create `ProjectContext` with Provider wrapping the entire app
- Use `useReducer` for state updates (actions: UPDATE_TRANSCRIPT, ADD_OUTLINE_ITEM, etc.)
- Export custom hook `useProject()` for consuming components

---

## Decision 2: UI Component Strategy

**Decision**: Custom Tailwind components with Headless UI for complex primitives

**Rationale**:
- Tailwind CSS specified in tech stack for styling
- Custom components give full control over appearance for prototype iteration
- Headless UI provides accessible primitives (modals, dropdowns) without styling opinions
- Keeps bundle size small for a prototype
- No need for full component library overhead (MUI, Chakra, etc.)

**Alternatives Considered**:
| Alternative | Rejected Because |
|-------------|------------------|
| Material UI | Heavy, opinionated styling doesn't match "simple prototype" goal |
| Chakra UI | Additional runtime dependency, styled-system overhead |
| shadcn/ui | Good option but adds complexity for Ground Zero |
| Radix UI primitives only | Similar to Headless UI; either works |

**Implementation Notes**:
- Build 6 common components: Button, Input, Textarea, Select, Modal, Card
- Use Headless UI `Dialog` for export modal, `Listbox` for select dropdowns
- Keep component API simple and consistent

---

## Decision 3: Tab Navigation Pattern

**Decision**: Internal state-based tab switching (no router)

**Rationale**:
- Single-page prototype doesn't need URL-based routing
- Tab state can live in WorkspacePage or be derived from Project context
- Simpler mental model: tabs are UI views of the same Project
- Avoids router dependency and configuration for Ground Zero

**Alternatives Considered**:
| Alternative | Rejected Because |
|-------------|------------------|
| React Router with nested routes | Over-engineered for prototype; adds URL complexity |
| TanStack Router | Overkill for 4 static tabs |
| Hash-based routing | No benefit over simple state; adds URL noise |

**Implementation Notes**:
- `WorkspacePage` holds `activeTab` state (1-4)
- `TabBar` component renders clickable tabs, highlights active
- `TabNavigation` provides Next/Previous buttons that update activeTab
- Tab content conditionally rendered based on activeTab value

---

## Decision 4: List Reordering (Outline Items)

**Decision**: @dnd-kit/core for drag-and-drop reordering

**Rationale**:
- FR-007 requires outline items to be reorderable
- dnd-kit is the modern React DnD solution (React 18 compatible)
- Lightweight, tree-shakeable, accessible by default
- Works well with Tailwind styling

**Alternatives Considered**:
| Alternative | Rejected Because |
|-------------|------------------|
| react-beautiful-dnd | Deprecated, unmaintained |
| react-dnd | More complex setup, less accessible defaults |
| Manual drag implementation | Reinventing the wheel, accessibility concerns |
| No reordering (add/remove only) | Spec explicitly requires reorder capability |

**Implementation Notes**:
- Use `DndContext`, `SortableContext` from @dnd-kit/sortable
- Wrap OutlineEditor in DndContext
- Each OutlineItem uses useSortable hook
- On drag end, dispatch reorder action to context

---

## Decision 5: Export Implementation

**Decision**: Client-side Markdown file generation with Blob download

**Rationale**:
- FR-022 allows either file download OR summary modal
- Blob/download approach demonstrates real export behavior
- No server needed; pure frontend implementation
- Markdown is simple, human-readable, sufficient for prototype

**Alternatives Considered**:
| Alternative | Rejected Because |
|-------------|------------------|
| Summary modal only | Less demonstrative of final product behavior |
| PDF generation (jsPDF) | Adds significant complexity for prototype |
| JSON export | Less user-friendly than Markdown |
| Copy to clipboard | Doesn't feel like "export" |

**Implementation Notes**:
- `exportHelpers.ts` assembles Markdown from Project state
- Structure: Title, Subtitle, Credits, Chapters (outline), Draft content
- Create Blob with MIME type `text/markdown`
- Trigger download via temporary anchor element
- Include selected visuals as placeholder text references

---

## Decision 6: Form Validation Approach

**Decision**: Minimal inline validation with native HTML5 + simple React state

**Rationale**:
- Spec says "no validation needed beyond has some value" for style controls
- Only critical validation: project name required for creation
- Form libraries (React Hook Form, Formik) are overkill
- Keep prototype simple and fast to iterate

**Alternatives Considered**:
| Alternative | Rejected Because |
|-------------|------------------|
| React Hook Form | Over-engineered for simple forms |
| Formik + Yup | Heavy dependency for minimal validation |
| Zod schemas | Better suited for API validation, not UI forms |

**Implementation Notes**:
- Project name: `required` attribute + disabled Create button when empty
- Style controls: no validation, accept any selection
- Use controlled inputs with onChange handlers

---

## Decision 7: Sample Data Strategy

**Decision**: Static TypeScript constants in dedicated sampleData.ts file

**Rationale**:
- "Generate" buttons need hardcoded sample content per spec
- Centralizing in one file makes content easy to iterate
- TypeScript ensures sample data matches Project types
- No need for faker/random data in prototype

**Alternatives Considered**:
| Alternative | Rejected Because |
|-------------|------------------|
| Inline in components | Scattered, hard to maintain |
| JSON file import | Extra build step, no type safety |
| faker.js | Overkill for static sample data |

**Implementation Notes**:
- Export constants: SAMPLE_TRANSCRIPT, SAMPLE_OUTLINE, SAMPLE_RESOURCES
- Export: SAMPLE_VISUALS (4-8 items with titles, descriptions)
- Export: SAMPLE_DRAFT_TEXT (multi-paragraph ebook content)
- "Fill with sample data" populates from these constants

---

## Decision 8: Testing Strategy

**Decision**: Vitest + React Testing Library for unit/component, Playwright for e2e

**Rationale**:
- Vitest is fast, Vite-native, Jest-compatible API
- React Testing Library encourages testing user behavior
- Playwright provides cross-browser e2e testing
- Aligns with tech spec mentions of integration testing

**Alternatives Considered**:
| Alternative | Rejected Because |
|-------------|------------------|
| Jest | Slower, requires more config with Vite |
| Cypress | Heavier, better for larger test suites |
| Testing Library only | Missing e2e coverage for workflow |

**Implementation Notes**:
- Unit tests: context reducer logic, utility functions
- Component tests: each tab's components render correctly, handle interactions
- E2E tests: full workflow from landing → create project → navigate tabs → export

---

## Open Questions Resolved

All technical decisions have been made. No NEEDS CLARIFICATION items remain.

## Dependencies Summary

```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "@headlessui/react": "^2.0.0",
    "@dnd-kit/core": "^6.1.0",
    "@dnd-kit/sortable": "^8.0.0"
  },
  "devDependencies": {
    "typescript": "^5.3.0",
    "vite": "^5.0.0",
    "@vitejs/plugin-react": "^4.2.0",
    "tailwindcss": "^3.4.0",
    "postcss": "^8.4.0",
    "autoprefixer": "^10.4.0",
    "vitest": "^1.0.0",
    "@testing-library/react": "^14.0.0",
    "@testing-library/jest-dom": "^6.0.0",
    "@playwright/test": "^1.40.0"
  }
}
```
