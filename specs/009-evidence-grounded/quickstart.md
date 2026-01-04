# Quickstart: Evidence-Grounded Drafting

**Feature**: 009-evidence-grounded
**Date**: 2026-01-04

## Prerequisites

- MongoDB running locally (default: mongodb://localhost:27017)
- Python 3.11+ with virtual environment
- Node.js 18+ for frontend
- OpenAI API key in environment

```bash
# Backend setup
cd backend
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"

# Frontend setup
cd frontend
npm install
```

## Environment Variables

```bash
# Backend (.env or export)
OPENAI_API_KEY=sk-...
MONGODB_URI=mongodb://localhost:27017
MONGODB_DATABASE=webinar2ebook

# Optional: Anthropic fallback
ANTHROPIC_API_KEY=sk-ant-...
```

---

## Development Workflow

### 1. Start Services

```bash
# Terminal 1: Backend
cd backend
source .venv/bin/activate
uvicorn src.api.main:app --reload --port 8000

# Terminal 2: Frontend
cd frontend
npm run dev
```

### 2. Access Application

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

---

## Testing Evidence-Grounded Generation

### Manual Test Flow

1. **Create Project**
   - Navigate to Tab 1
   - Create new project with interview transcript

2. **Configure Content Mode** (Tab 3)
   - Select "Interview" from Content Mode dropdown
   - Ensure "Strict Grounded" toggle is ON

3. **Generate Draft**
   - Click "Generate Draft"
   - Observe Evidence Map phase in progress indicator
   - Wait for completion

4. **Verify Constraints**
   - Check generated draft has NO "Action Steps" sections
   - Check no invented biography for speaker
   - Check QA Panel for faithfulness score >= 85

5. **Test Targeted Rewrite** (if issues found)
   - If QA shows issues, click "Fix Flagged Issues"
   - Observe only flagged sections are rewritten
   - Verify diff view shows changes

### Test with Sample Transcript

Create a project with this interview transcript:

```text
Host: Welcome to the show. Today we have Sarah Chen, founder of DataFlow.

Sarah: Thanks for having me. I started DataFlow in 2019 after seeing how
companies struggled with data pipelines.

Host: What was the biggest challenge?

Sarah: Honestly, it was convincing enterprises that they needed real-time
data. Everyone was stuck in batch processing mindset. We had to show them
the cost of delayed insights - missed sales, stale inventory forecasts.

Host: How did you break through?

Sarah: Case studies. We ran a pilot with a retail chain and showed them
they were losing $2M per quarter from inventory misalignment. That got
their attention.

Host: What advice for other founders?

Sarah: Focus on one customer problem. Don't try to be everything. We only
did data pipelines for retail for the first two years.
```

**Expected Results**:
- Evidence Map extracts: DataFlow founding, 2019, real-time data challenge, $2M case study, focus advice
- NO section titled "Action Steps for Founders"
- NO invented details about Sarah's education or background
- Faithfulness score: 85+

---

## Running Tests

### Unit Tests

```bash
cd backend
source .venv/bin/activate

# Run all Spec 009 tests
python -m pytest tests/unit/test_evidence_map.py -v
python -m pytest tests/unit/test_rewrite_service.py -v
python -m pytest tests/unit/test_content_mode.py -v

# Run with coverage
python -m pytest tests/unit/test_evidence*.py --cov=src/services/evidence_service
```

### Integration Tests

```bash
# Requires MongoDB running
python -m pytest tests/integration/test_grounded_generation.py -v
```

### Constraint Verification Tests

```bash
# Specific tests for interview mode constraints
python -m pytest tests/unit/test_content_mode.py::test_no_action_steps -v
python -m pytest tests/unit/test_content_mode.py::test_no_invented_biography -v
python -m pytest tests/unit/test_content_mode.py::test_no_platitudes -v
```

---

## Key Files

### Backend

| File | Purpose |
|------|---------|
| `src/models/style_config.py` | ContentMode enum, strict_grounded field |
| `src/models/evidence_map.py` | EvidenceMap, ChapterEvidence, EvidenceEntry |
| `src/models/rewrite_plan.py` | RewritePlan, RewriteSection, RewriteResult |
| `src/services/evidence_service.py` | Evidence Map generation |
| `src/services/rewrite_service.py` | Targeted rewrite service |
| `src/services/draft_service.py` | Updated with evidence_map phase |
| `src/services/prompts.py` | Interview mode prompts, constraints |

### Frontend

| File | Purpose |
|------|---------|
| `src/components/tab3/StyleControls.tsx` | Content Mode dropdown, Strict toggle |
| `src/components/tab3/Tab3Content.tsx` | Fix Flagged Issues button |
| `src/components/tab3/RewriteDiffView.tsx` | Before/after diff display |
| `src/types/style.ts` | ContentMode type |

---

## Debugging

### Check Evidence Map Generation

```python
# In Python REPL
from src.services.evidence_service import generate_evidence_map
from src.models import ContentMode

evidence = await generate_evidence_map(
    project_id="...",
    transcript="...",
    chapters=[...],
    content_mode=ContentMode.interview
)
print(f"Extracted {len(evidence.chapters)} chapter evidence")
for ch in evidence.chapters:
    print(f"  Chapter {ch.chapter_index}: {len(ch.claims)} claims")
```

### Check Constraint Violations

```python
from src.services.evidence_service import check_interview_constraints
from src.models import ContentMode

violations = check_interview_constraints(
    content="## Key Action Steps\n1. First, implement...",
    mode=ContentMode.interview
)
print(f"Violations: {violations}")
# Output: ["Forbidden pattern: ##\\s*(Key\\s+)?Action\\s+(Steps?|Items?)..."]
```

### Inspect Job Evidence Map

```bash
# Via API
curl http://localhost:8000/draft/status/{job_id} | jq '.data.evidence_map'
```

---

## Common Issues

### Issue: Evidence Map empty

**Cause**: Transcript too short or not matched to chapters
**Fix**: Ensure transcript has >500 chars and outline matches content

### Issue: Action Steps appearing in interview mode

**Cause**: Prompt not including constraints or constraint check bypassed
**Fix**: Verify `content_mode=interview` in StyleConfig and check prompts.py

### Issue: Rewrite not fixing issues

**Cause**: Section boundaries not matching QA issue locations
**Fix**: Check QA issue `location` field matches section headings

---

## API Endpoints Reference

### Existing (Updated)

| Endpoint | Method | Change |
|----------|--------|--------|
| POST /draft/generate | POST | StyleConfig includes content_mode, strict_grounded |
| GET /draft/status/{job_id} | GET | Response includes evidence_map when available |

### New

| Endpoint | Method | Description |
|----------|--------|-------------|
| POST /qa/rewrite | POST | Trigger targeted rewrite for flagged issues |
| GET /qa/rewrite/{job_id} | GET | Get rewrite job status and diff |

---

## Verification Checklist

- [ ] Evidence Map generates for interview transcript
- [ ] Interview mode draft has no "Action Steps" section
- [ ] Interview mode draft has no invented biography
- [ ] Faithfulness score >= 85 for grounded content
- [ ] Evidence Map visible in job status response
- [ ] Targeted rewrite only modifies flagged sections
- [ ] Diff view shows before/after comparison
- [ ] Multiple rewrite pass shows warning
