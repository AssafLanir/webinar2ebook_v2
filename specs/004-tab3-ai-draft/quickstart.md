# Quickstart: Tab 3 AI Draft Generation

**Feature**: 004-tab3-ai-draft
**Date**: 2025-12-17

Local development setup for implementing draft generation.

---

## Prerequisites

- Python 3.11+
- Node.js 18+
- MongoDB running locally (or Docker)
- OpenAI API key (or Anthropic API key)

## Environment Setup

### 1. Clone and Install

```bash
cd webinar2ebook_v2

# Backend
cd backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt

# Frontend
cd ../frontend
npm install
```

### 2. Environment Variables

Create `backend/.env`:
```bash
# Required: At least one LLM provider
OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...

# MongoDB (default: localhost)
MONGO_URL=mongodb://localhost:27017
MONGO_DB_NAME=webinar2ebook

# Optional: Logging
LOG_LEVEL=DEBUG
```

### 3. Start Services

```bash
# Terminal 1: MongoDB (if using Docker)
docker run -d -p 27017:27017 --name mongo mongo:7

# Terminal 2: Backend
cd backend
source venv/bin/activate
uvicorn src.api.main:app --reload --port 8000

# Terminal 3: Frontend
cd frontend
npm run dev
```

---

## Existing Code Locations

### Backend Models (already implemented)

```
backend/src/models/
├── draft_plan.py          # DraftPlan, ChapterPlan, TranscriptSegment
├── api_responses.py       # API envelope models
├── style_config.py        # StyleConfig, StyleConfigEnvelope
└── visuals.py             # VisualPlan, VisualOpportunity
```

### LLM Layer (already implemented)

```
backend/src/llm/
├── client.py              # LLMClient with fallback
├── schemas.py             # load_draft_plan_schema()
└── providers/
    ├── openai.py
    └── anthropic.py
```

### JSON Schemas (already generated)

```
specs/004-tab3-ai-draft/schemas/
├── draft_plan.internal.schema.json    # For tests/Anthropic
├── draft_plan.openai.strict.schema.json  # For OpenAI strict mode
├── DraftPlan.json
├── DraftGenerateRequest.json
├── DraftGenerateResponse.json
└── ... (all API schemas)
```

### Contract Tests (already passing)

```bash
cd backend
pytest tests/unit/test_schemas_contract.py -v
# 63 tests passing
```

---

## Implementation Checklist

### Backend: Draft Service

Create `backend/src/services/draft_service.py`:

```python
from src.llm import LLMClient, load_draft_plan_schema, ResponseFormat
from src.models import DraftPlan, ChapterPlan, VisualPlan

# Job store (in-memory for MVP)
_jobs: dict[str, GenerationJob] = {}

async def start_generation(request: DraftGenerateRequest) -> str:
    """Create job and start background task."""
    job_id = str(uuid4())
    job = GenerationJob(job_id=job_id, status=JobStatus.queued, ...)
    _jobs[job_id] = job

    # Start background task
    asyncio.create_task(generate_draft_task(job_id, request))

    return job_id

async def generate_draft_task(job_id: str, request: DraftGenerateRequest):
    """Background task for draft generation."""
    job = _jobs[job_id]

    # Phase 1: Generate DraftPlan
    job.status = JobStatus.planning
    draft_plan = await generate_draft_plan(request)

    # Phase 2: Generate chapters
    job.status = JobStatus.generating
    for chapter in draft_plan.chapters:
        if job.cancel_requested:
            break
        chapter_md = await generate_chapter(chapter, ...)
        job.chapters_completed.append(chapter_md)

    # Assemble
    job.draft_markdown = assemble_chapters(...)
    job.status = JobStatus.completed
```

### Backend: API Endpoints

Create `backend/src/api/routes/draft.py`:

```python
from fastapi import APIRouter
from src.services import draft_service

router = APIRouter(prefix="/ai/draft", tags=["Draft"])

@router.post("/generate")
async def generate_draft(request: DraftGenerateRequest):
    job_id = await draft_service.start_generation(request)
    return success_response({"job_id": job_id, "status": "queued"})

@router.get("/status/{job_id}")
async def get_status(job_id: str):
    job = draft_service.get_job(job_id)
    return success_response(job.to_status_data())

@router.post("/cancel/{job_id}")
async def cancel(job_id: str):
    result = draft_service.cancel_job(job_id)
    return success_response(result)
```

### Frontend: API Client

Create `frontend/src/services/draftApi.ts`:

```typescript
const API_BASE = '/api/ai/draft'

export async function startDraftGeneration(request: DraftGenerateRequest) {
  const res = await fetch(`${API_BASE}/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request)
  })
  return res.json()
}

export async function getDraftStatus(jobId: string) {
  const res = await fetch(`${API_BASE}/status/${jobId}`)
  return res.json()
}

export async function cancelDraft(jobId: string) {
  const res = await fetch(`${API_BASE}/cancel/${jobId}`, { method: 'POST' })
  return res.json()
}
```

### Frontend: Generation Hook

Create `frontend/src/hooks/useDraftGeneration.ts`:

```typescript
export function useDraftGeneration() {
  const [jobId, setJobId] = useState<string | null>(null)
  const [status, setStatus] = useState<DraftStatus | null>(null)

  const startGeneration = async (request: DraftGenerateRequest) => {
    const result = await startDraftGeneration(request)
    setJobId(result.data.job_id)
  }

  // Poll for status
  useEffect(() => {
    if (!jobId) return
    const poll = async () => {
      const result = await getDraftStatus(jobId)
      setStatus(result.data)
      if (!['completed', 'failed', 'cancelled'].includes(result.data.status)) {
        setTimeout(poll, 2000)
      }
    }
    poll()
  }, [jobId])

  return { startGeneration, cancelGeneration, status }
}
```

---

## Testing During Development

### Run Backend Tests

```bash
cd backend
pytest tests/ -v

# Just contract tests
pytest tests/unit/test_schemas_contract.py -v

# With coverage
pytest tests/ --cov=src --cov-report=term-missing
```

### Manual API Testing

```bash
# Start backend
uvicorn src.api.main:app --reload

# Test generate endpoint (create test project first)
curl -X POST http://localhost:8000/api/ai/draft/generate \
  -H "Content-Type: application/json" \
  -d '{
    "transcript": "Long transcript text...",
    "outline": [{"id": "1", "title": "Intro", "level": 1}],
    "style_config": {"version": 1, "preset_id": "default_webinar_ebook_v1", "style": {}}
  }'

# Poll status
curl http://localhost:8000/api/ai/draft/status/{job_id}
```

### Frontend Dev Server

```bash
cd frontend
npm run dev
# Open http://localhost:5173
```

---

## Key Files to Create

| File | Purpose |
|------|---------|
| `backend/src/services/draft_service.py` | Draft generation service |
| `backend/src/api/routes/draft.py` | API endpoints |
| `backend/tests/unit/test_draft_service.py` | Service unit tests |
| `backend/tests/unit/test_draft_api.py` | API tests |
| `frontend/src/services/draftApi.ts` | API client |
| `frontend/src/hooks/useDraftGeneration.ts` | React hook |
| `frontend/src/components/tab3/GenerateProgress.tsx` | Progress UI |
| `frontend/src/components/tab3/DraftPreviewModal.tsx` | Preview modal |

---

## Common Issues

### LLM Key Not Set
```
Error: OPENAI_API_KEY not found
```
→ Add key to `backend/.env`

### MongoDB Connection
```
Error: Connection refused to localhost:27017
```
→ Start MongoDB: `docker run -d -p 27017:27017 mongo:7`

### Schema Validation Error
```
Error: Invalid response format
```
→ Check you're using `draft_plan.openai.strict.schema.json` for OpenAI calls

### CORS Error in Frontend
```
Error: CORS policy blocked
```
→ Backend already has CORS configured in `main.py`

---

## Next Steps

After setup, run `/speckit.tasks` to generate implementation tasks.
