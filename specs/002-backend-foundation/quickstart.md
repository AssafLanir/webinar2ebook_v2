# Quickstart: Backend Foundation

**Feature**: 002-backend-foundation
**Date**: 2025-12-11

## Prerequisites

- Python 3.11+ installed
- Node.js 18+ installed (for frontend)
- MongoDB 6.0+ running locally (or Docker)

## Quick Setup

### 1. Start MongoDB

**Option A: Docker (recommended)**
```bash
docker run -d --name mongodb -p 27017:27017 mongo:6.0
```

**Option B: Local MongoDB**
```bash
# macOS with Homebrew
brew services start mongodb-community

# Verify connection
mongosh --eval "db.runCommand({ping:1})"
```

### 2. Backend Setup

```bash
# Create backend directory
mkdir -p backend
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies (after pyproject.toml exists)
pip install -e ".[dev]"

# Run backend
uvicorn src.api.main:app --reload --port 8000
```

### 3. Frontend Setup

```bash
cd frontend

# Install dependencies (if not done)
npm install

# Run frontend
npm run dev
```

### 4. Verify Setup

```bash
# Backend health check
curl http://localhost:8000/health
# Expected: {"data":{"status":"ok"},"error":null}

# Test project creation
curl -X POST http://localhost:8000/projects \
  -H "Content-Type: application/json" \
  -d '{"name":"Test Project","webinarType":"standard_presentation"}'
# Expected: {"data":{"id":"...","name":"Test Project",...},"error":null}

# List projects
curl http://localhost:8000/projects
# Expected: {"data":[{"id":"...","name":"Test Project",...}],"error":null}

# Run backend tests
cd backend && python -m pytest tests/ -v
# Expected: All tests pass (16 tests)

# Frontend
open http://localhost:5173
# Expected: Project list page loads, can create/open/delete projects
```

### 5. Full Integration Test

1. **Create Project**: Click "+ Create New Project", enter name, select type, click Create
2. **Open Project**: Click "Open" on a project in the list
3. **Edit Content**: Add transcript text in Tab 1, navigate to Tab 2
4. **Auto-Save**: Verify "Saving..." indicator appears when switching tabs
5. **Persistence**: Refresh browser, reopen project - data should be preserved
6. **Delete**: Go back to list, click trash icon, confirm deletion

## Development Commands

### Backend

| Command | Description |
|---------|-------------|
| `uvicorn src.api.main:app --reload` | Run with hot reload |
| `pytest` | Run all tests |
| `pytest -v` | Run tests with verbose output |
| `pytest --cov=src` | Run tests with coverage |

### Frontend

| Command | Description |
|---------|-------------|
| `npm run dev` | Start dev server |
| `npm run build` | Production build |
| `npm test` | Run unit tests |
| `npm run lint` | Run ESLint |

## Environment Variables

### Backend

| Variable | Default | Description |
|----------|---------|-------------|
| `MONGODB_URL` | `mongodb://localhost:27017` | MongoDB connection string |
| `DATABASE_NAME` | `webinar2ebook` | Database name |
| `CORS_ORIGINS` | `http://localhost:5173` | Allowed CORS origins |

### Frontend

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_API_URL` | `/api` | Backend API base URL |

## API Quick Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/projects` | List all projects |
| POST | `/projects` | Create project |
| GET | `/projects/{id}` | Get project |
| PUT | `/projects/{id}` | Update project |
| DELETE | `/projects/{id}` | Delete project |

## Troubleshooting

### MongoDB Connection Failed
```
# Check if MongoDB is running
docker ps | grep mongo
# or
brew services list | grep mongodb

# Restart if needed
docker restart mongodb
# or
brew services restart mongodb-community
```

### CORS Errors
Ensure backend CORS is configured for `http://localhost:5173`:
```python
# In backend/src/api/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Port Already in Use
```bash
# Find process using port 8000
lsof -i :8000
# Kill it
kill -9 <PID>

# Or use different port
uvicorn src.api.main:app --reload --port 8001
```

## Project Structure After Implementation

```
webinar2ebook_v2/
├── backend/
│   ├── src/
│   │   ├── api/
│   │   │   ├── main.py
│   │   │   └── routes/
│   │   ├── models/
│   │   ├── services/
│   │   └── db/
│   ├── tests/
│   ├── pyproject.toml
│   └── README.md
├── frontend/
│   ├── src/
│   │   ├── services/
│   │   │   └── api.ts        # NEW
│   │   ├── pages/
│   │   │   ├── LandingPage.tsx  # MODIFIED → ProjectListPage
│   │   │   └── WorkspacePage.tsx # MODIFIED
│   │   └── context/
│   │       └── ProjectContext.tsx # MODIFIED
│   └── ...
└── specs/
    └── 002-backend-foundation/
        ├── spec.md
        ├── plan.md
        ├── research.md
        ├── data-model.md
        ├── quickstart.md
        └── contracts/
            └── openapi.yaml
```
