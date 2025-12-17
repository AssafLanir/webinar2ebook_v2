"""FastAPI application setup."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

from src.api.exceptions import (
    FileNotFoundError,
    FileTooLargeError,
    InvalidFileTypeError,
    ProjectNotFoundError,
    ValidationError,
)
from src.api.response import error_response
from src.api.routes import ai, files, health, projects
from src.llm import LLMError
from src.db.mongo import close_database


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler."""
    # Startup
    yield
    # Shutdown
    await close_database()


app = FastAPI(
    title="Webinar2Ebook API",
    description="Backend API for project persistence in Webinar2Ebook application",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware for frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handlers
@app.exception_handler(ProjectNotFoundError)
async def project_not_found_handler(request: Request, exc: ProjectNotFoundError) -> JSONResponse:
    """Handle project not found errors."""
    return JSONResponse(
        status_code=404,
        content=error_response("PROJECT_NOT_FOUND", str(exc)),
    )


@app.exception_handler(ValidationError)
async def validation_error_handler(request: Request, exc: ValidationError) -> JSONResponse:
    """Handle validation errors."""
    return JSONResponse(
        status_code=400,
        content=error_response("VALIDATION_ERROR", exc.message),
    )


@app.exception_handler(ServerSelectionTimeoutError)
async def mongo_timeout_handler(request: Request, exc: ServerSelectionTimeoutError) -> JSONResponse:
    """Handle MongoDB connection timeout."""
    return JSONResponse(
        status_code=503,
        content=error_response("DATABASE_UNAVAILABLE", "Database is not available. Please try again later."),
    )


@app.exception_handler(ConnectionFailure)
async def mongo_connection_handler(request: Request, exc: ConnectionFailure) -> JSONResponse:
    """Handle MongoDB connection failure."""
    return JSONResponse(
        status_code=503,
        content=error_response("DATABASE_UNAVAILABLE", "Database connection failed. Please try again later."),
    )


@app.exception_handler(FileTooLargeError)
async def file_too_large_handler(request: Request, exc: FileTooLargeError) -> JSONResponse:
    """Handle file too large errors."""
    return JSONResponse(
        status_code=400,
        content=error_response(
            "FILE_TOO_LARGE",
            f"File size exceeds maximum of {exc.max_size // (1024 * 1024)}MB",
        ),
    )


@app.exception_handler(InvalidFileTypeError)
async def invalid_file_type_handler(request: Request, exc: InvalidFileTypeError) -> JSONResponse:
    """Handle invalid file type errors."""
    return JSONResponse(
        status_code=400,
        content=error_response(
            "INVALID_FILE_TYPE",
            f"File type '{exc.file_type}' is not supported. Allowed: PDF, PPT, PPTX, DOC, DOCX, JPG, JPEG, PNG",
        ),
    )


@app.exception_handler(FileNotFoundError)
async def file_not_found_handler(request: Request, exc: FileNotFoundError) -> JSONResponse:
    """Handle file not found errors."""
    return JSONResponse(
        status_code=404,
        content=error_response("FILE_NOT_FOUND", str(exc)),
    )


@app.exception_handler(LLMError)
async def llm_error_handler(request: Request, exc: LLMError) -> JSONResponse:
    """Handle LLM/AI service errors."""
    return JSONResponse(
        status_code=503,
        content=error_response("AI_SERVICE_ERROR", "AI service is temporarily unavailable. Please try again."),
    )


# Register routes
app.include_router(health.router)
app.include_router(projects.router)
app.include_router(files.router)
app.include_router(ai.router, prefix="/api")
