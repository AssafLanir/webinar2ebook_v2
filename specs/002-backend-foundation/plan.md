# Implementation Plan: Backend Foundation

**Branch**: `002-backend-foundation` | **Date**: 2025-12-11 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/002-backend-foundation/spec.md`

## Summary

Implement a backend API for Project CRUD operations and integrate it with the existing React frontend to enable project persistence. The frontend will be updated to show a Project List on app load, with auto-save on tab navigation. This transforms the app from an in-memory demo to a persistent application.

## Technical Context

**Backend**:
- **Language/Version**: Python 3.11+
- **Framework**: FastAPI (async, Pydantic validation, auto OpenAPI docs)
- **Storage**: MongoDB (document store fits Project structure naturally)
- **Testing**: pytest + pytest-asyncio + httpx for async API tests

**Frontend** (existing):
- **Language/Version**: TypeScript 5.9, React 19
- **Build Tool**: Vite 7.x
- **Styling**: Tailwind CSS 4.x
- **Testing**: Vitest + Testing Library + Playwright

**Target Platform**: Web (localhost development initially)
**Project Type**: Web application (frontend + backend)
**Performance Goals**: API responses < 300ms for typical operations
**Constraints**: Single-user (no auth), CORS enabled for localhost:5173
**Scale/Scope**: Small (dozens of projects, single user)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The constitution template is not yet customized for this project. Proceeding with standard best practices:

| Gate | Status | Notes |
|------|--------|-------|
| Simplicity | PASS | Minimal CRUD API, no over-engineering |
| Testing | PASS | Backend and frontend tests planned |
| Clear Contracts | PASS | OpenAPI spec will define API contracts |

## Project Structure

### Documentation (this feature)

```text
specs/002-backend-foundation/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (OpenAPI spec)
└── tasks.md             # Phase 2 output (from /speckit.tasks)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── models/
│   │   └── project.py       # Pydantic models for Project, OutlineItem, Resource
│   ├── services/
│   │   └── project_service.py  # Business logic for project CRUD
│   ├── api/
│   │   ├── routes/
│   │   │   ├── health.py    # GET /health
│   │   │   └── projects.py  # Project CRUD endpoints
│   │   └── main.py          # FastAPI app setup
│   └── db/
│       └── mongo.py         # MongoDB connection setup
├── tests/
│   ├── conftest.py          # Test fixtures
│   ├── test_health.py
│   └── test_projects.py     # Project CRUD tests
├── pyproject.toml           # Python dependencies
└── README.md

frontend/
├── src/
│   ├── components/
│   │   ├── common/          # Existing: Button, Card, Input, etc.
│   │   ├── layout/          # Existing: TabBar, ProjectHeader, etc.
│   │   ├── tab1/            # Existing: TranscriptEditor, OutlineEditor, etc.
│   │   ├── tab2/            # Existing
│   │   ├── tab3/            # Existing
│   │   └── tab4/            # Existing
│   ├── pages/
│   │   ├── LandingPage.tsx  # MODIFY: Becomes ProjectListPage
│   │   └── WorkspacePage.tsx # MODIFY: Add auto-save, back button
│   ├── services/
│   │   └── api.ts           # NEW: API client for backend calls
│   ├── context/
│   │   └── ProjectContext.tsx # MODIFY: Integrate with API
│   └── types/
│       └── project.ts       # MODIFY: Ensure alignment with backend
└── tests/
    └── integration/
        └── project-lifecycle.spec.ts  # NEW: E2E test for create/edit/save/reopen
```

**Structure Decision**: Web application with separate `backend/` and `frontend/` directories. Backend is new; frontend extends existing Ground Zero implementation.

## Complexity Tracking

No violations to justify - design follows simplicity principle with standard REST patterns.
