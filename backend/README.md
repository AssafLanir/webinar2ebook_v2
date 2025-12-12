# Webinar2Ebook Backend

Backend API for project persistence in the Webinar2Ebook application.

## Tech Stack

- **Framework**: FastAPI
- **Database**: MongoDB with Motor (async driver)
- **Validation**: Pydantic v2
- **Testing**: pytest + pytest-asyncio + httpx

## Setup

### Prerequisites

- Python 3.11+
- MongoDB 6.0+ running locally (or Docker)

### Installation

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"
```

### Running the Server

```bash
# Development mode with hot reload
uvicorn src.api.main:app --reload --port 8000
```

### Running Tests

```bash
pytest
pytest -v  # verbose
pytest --cov=src  # with coverage
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MONGODB_URL` | `mongodb://localhost:27017` | MongoDB connection string |
| `DATABASE_NAME` | `webinar2ebook` | Database name |

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/projects` | List all projects |
| POST | `/projects` | Create project |
| GET | `/projects/{id}` | Get project by ID |
| PUT | `/projects/{id}` | Update project |
| DELETE | `/projects/{id}` | Delete project |

## Project Structure

```
backend/
├── src/
│   ├── models/        # Pydantic models
│   ├── services/      # Business logic
│   ├── api/
│   │   ├── routes/    # API endpoints
│   │   └── main.py    # FastAPI app
│   └── db/            # Database setup
├── tests/             # Test files
├── pyproject.toml     # Dependencies
└── README.md
```
