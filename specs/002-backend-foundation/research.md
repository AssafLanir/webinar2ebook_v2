# Research: Backend Foundation

**Feature**: 002-backend-foundation
**Date**: 2025-12-11

## Research Summary

This document captures technology decisions and best practices research for implementing the backend foundation feature.

---

## 1. Backend Framework Selection

### Decision: FastAPI

**Rationale**:
- Native async support for I/O-bound operations (database calls)
- Built-in Pydantic integration for request/response validation
- Automatic OpenAPI documentation generation
- Excellent Python typing support
- Lightweight and fast for development

**Alternatives Considered**:
| Alternative | Why Rejected |
|-------------|--------------|
| Flask | No built-in async, requires extensions for validation |
| Django REST Framework | Too heavy for simple CRUD API, slower development |
| Express.js (Node) | Would require separate language from potential future Python ML integrations |

---

## 2. Database Selection

### Decision: MongoDB

**Rationale**:
- Document structure naturally fits Project model (nested outlineItems, resources)
- Schema flexibility for future field additions (Stage 2-4 fields)
- Simple local setup with MongoDB Community or Docker
- Motor (async MongoDB driver) integrates well with FastAPI
- No migrations needed for schema evolution

**Alternatives Considered**:
| Alternative | Why Rejected |
|-------------|--------------|
| PostgreSQL | Would require ORM/migrations for nested arrays; overkill for single-user |
| SQLite | Poor support for nested arrays; would need JSON column workarounds |
| File-based JSON | No concurrent access safety; harder to query |

---

## 3. API Response Format

### Decision: Envelope Pattern with data/error

**Rationale**:
- Consistent structure across all endpoints
- Clear separation of success payload and error information
- Error codes enable client-side error handling logic
- Frontend can have a single response parser

**Format**:
```json
// Success
{
  "data": { ... },
  "error": null
}

// Error
{
  "data": null,
  "error": {
    "code": "PROJECT_NOT_FOUND",
    "message": "Project with ID xyz does not exist"
  }
}
```

---

## 4. Frontend API Integration

### Decision: Fetch-based API client with async/await

**Rationale**:
- Native browser API (no additional dependencies)
- Simple to implement with TypeScript typing
- Vite proxy can handle CORS during development
- Centralized error handling in API client module

**Implementation Pattern**:
```typescript
// services/api.ts
const API_BASE = '/api';

export async function fetchProjects(): Promise<ProjectSummary[]> {
  const res = await fetch(`${API_BASE}/projects`);
  const json = await res.json();
  if (json.error) throw new ApiError(json.error);
  return json.data;
}
```

---

## 5. Auto-Save Strategy

### Decision: Save on tab change only (blocking)

**Rationale**:
- Spec explicitly requires tab-change saves only (FR-012 excludes debounced saves)
- Blocking approach ensures data consistency before navigation
- User sees immediate feedback on save success/failure
- Simpler implementation than optimistic updates

**Implementation Pattern**:
1. User clicks tab or Next/Previous
2. Frontend intercepts navigation
3. Calls PUT /projects/{id} with current state
4. On success: proceed to new tab
5. On failure: show error, stay on current tab, offer retry

---

## 6. Project ID Strategy

### Decision: MongoDB ObjectId (string representation)

**Rationale**:
- MongoDB generates unique IDs automatically
- String representation is URL-safe
- No need for custom ID generation
- Standard pattern for MongoDB-backed APIs

---

## 7. CORS Configuration

### Decision: Allow localhost:5173 in development

**Rationale**:
- Vite dev server runs on port 5173 by default
- Backend will run on different port (e.g., 8000)
- CORS middleware required for cross-origin requests
- Can be tightened for production deployment

**Implementation**:
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## 8. Testing Strategy

### Backend Tests

**Decision**: pytest with httpx TestClient

**Rationale**:
- pytest is standard Python testing framework
- httpx provides async-compatible test client for FastAPI
- pytest-asyncio for async test support
- mongomock or testcontainers for test database isolation

### Frontend Tests

**Decision**: Playwright for E2E, Vitest for unit

**Rationale**:
- Playwright already in devDependencies
- Can test full create→edit→save→reopen flow
- MSW (Mock Service Worker) for API mocking in unit tests

---

## 9. Error Handling Patterns

### Backend

**Decision**: Custom exception handlers with consistent error response

**Implementation**:
```python
class ProjectNotFoundError(Exception):
    pass

@app.exception_handler(ProjectNotFoundError)
async def project_not_found_handler(request, exc):
    return JSONResponse(
        status_code=404,
        content={"data": None, "error": {"code": "PROJECT_NOT_FOUND", "message": str(exc)}}
    )
```

### Frontend

**Decision**: Try-catch with user-friendly toast notifications

**Implementation**:
- API client throws typed errors
- Components catch and display toast/banner
- Auto-save failures block navigation with retry option

---

## 10. Development Workflow

### Decision: Concurrent backend + frontend development

**Rationale**:
- Backend on port 8000 (uvicorn)
- Frontend on port 5173 (vite dev)
- Vite proxy or CORS for API calls
- Hot reload on both sides

**Commands**:
```bash
# Terminal 1: Backend
cd backend && uvicorn src.api.main:app --reload --port 8000

# Terminal 2: Frontend
cd frontend && npm run dev
```

---

## Open Questions Resolved

All technical decisions have been made. No NEEDS CLARIFICATION items remain.

## Next Steps

1. Generate data-model.md with entity definitions
2. Generate OpenAPI contract specification
3. Generate quickstart.md with setup instructions
