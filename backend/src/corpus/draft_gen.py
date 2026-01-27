"""DraftGen adapter for corpus runner.

Provides unified interface for draft generation with pluggable backends:
- LocalBackend: Direct library import (same code path as production)
- HTTPBackend: HTTP client for remote server

Key constraints:
1. Always sets style_config.style.content_mode to a valid mode
2. Never re-implements generation logic; adapter only orchestrates + polls
3. Captures reproducibility metadata (commit, prompt version, seed, backend, mode)
4. Uses same DraftGenerateRequest model as production API
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import subprocess
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, Protocol, runtime_checkable

import httpx

from .thresholds import DEFAULT_OUTLINE, DEFAULT_STYLE_CONFIG

logger = logging.getLogger(__name__)


# =============================================================================
# Data Structures
# =============================================================================


@dataclass
class DraftGenRequest:
    """Input for draft generation."""

    transcript_id: str
    transcript: str
    transcript_path: str
    outline: list[dict] = field(default_factory=lambda: DEFAULT_OUTLINE.copy())
    style_config: dict = field(default_factory=lambda: DEFAULT_STYLE_CONFIG.copy())
    candidate_count: int = 1
    require_preflight_pass: bool = True

    @property
    def content_mode(self) -> str:
        """Extract content_mode from style_config."""
        style = self.style_config.get("style", self.style_config)
        return style.get("content_mode", "essay")

    @property
    def outline_sha256(self) -> str:
        """Compute SHA256 hash of outline."""
        return hashlib.sha256(
            json.dumps(self.outline, sort_keys=True).encode()
        ).hexdigest()[:16]

    @property
    def style_config_sha256(self) -> str:
        """Compute SHA256 hash of style_config."""
        return hashlib.sha256(
            json.dumps(self.style_config, sort_keys=True).encode()
        ).hexdigest()[:16]

    def to_api_request(self) -> dict:
        """Convert to API request format (DraftGenerateRequest)."""
        return {
            "transcript": self.transcript,
            "outline": self.outline,
            "style_config": self.style_config,
            "candidate_count": self.candidate_count,
            "require_preflight_pass": self.require_preflight_pass,
        }

    def to_request_json(self) -> dict:
        """Convert to request.json format for reproducibility."""
        return {
            "transcript_id": self.transcript_id,
            "transcript_path": self.transcript_path,
            "outline": self.outline,
            "style_config": self.style_config,
            "content_mode": self.content_mode,
            "candidate_count": self.candidate_count,
            "require_preflight_pass": self.require_preflight_pass,
            "outline_sha256": self.outline_sha256,
            "style_config_sha256": self.style_config_sha256,
        }


@dataclass
class DraftGenMeta:
    """Reproducibility envelope for draft generation."""

    run_id: str
    transcript_id: str
    candidate_index: int
    transcript_path: str
    draft_path: str

    # Reproducibility
    git_commit: str
    config_hash: str
    prompt_version: str
    model: str
    temperature: float
    routing_version: str

    # Runtime info
    backend: str  # "local" | "http"
    content_mode: str
    seed: Optional[int]
    normalized_sha256: str
    generation_time_s: float

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class DraftGenResult:
    """Output from draft generation."""

    success: bool
    draft_markdown: Optional[str] = None
    draft_plan: Optional[dict] = None
    error: Optional[str] = None
    error_code: Optional[str] = None
    meta: Optional[DraftGenMeta] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        result = {
            "success": self.success,
            "error": self.error,
            "error_code": self.error_code,
        }
        if self.meta:
            result["meta"] = self.meta.to_dict()
        return result


# =============================================================================
# Utility Functions
# =============================================================================


def get_git_commit() -> str:
    """Get current git commit hash."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return "unknown"


def compute_config_hash(
    prompt_version: str,
    model: str,
    temperature: float,
    routing_version: str,
) -> str:
    """Compute hash of generation configuration."""
    config_str = json.dumps({
        "prompt_version": prompt_version,
        "model": model,
        "temperature": temperature,
        "routing_version": routing_version,
    }, sort_keys=True)
    return hashlib.sha256(config_str.encode()).hexdigest()[:16]


def compute_transcript_hash(transcript: str) -> str:
    """Compute SHA256 hash of transcript content."""
    return hashlib.sha256(transcript.encode()).hexdigest()[:16]


def generate_run_id(
    transcript_id: str,
    content_mode: str,
    candidate_index: int,
    config_hash: str,
) -> str:
    """Generate stable run ID for tracking."""
    return f"{transcript_id}__{content_mode}__c{candidate_index}__{config_hash[:8]}"


# =============================================================================
# Backend Protocol
# =============================================================================


@runtime_checkable
class DraftGenBackend(Protocol):
    """Protocol for draft generation backends."""

    async def generate(
        self,
        request: DraftGenRequest,
        timeout_s: int = 600,
    ) -> DraftGenResult:
        """Generate draft asynchronously.

        Args:
            request: Generation request
            timeout_s: Timeout in seconds

        Returns:
            DraftGenResult with draft or error
        """
        ...


# =============================================================================
# Local Backend
# =============================================================================


class LocalBackend:
    """Direct library import backend - same code path as production.

    Uses draft_service.start_generation() + polling, exactly as the API does.
    """

    def __init__(self):
        self.prompt_version = "ideas_v3"  # TODO: extract from prompts module
        self.model = "gpt-4o-mini"
        self.temperature = 0.7
        self.routing_version = "2026-01-26"

    async def generate(
        self,
        request: DraftGenRequest,
        timeout_s: int = 600,
    ) -> DraftGenResult:
        """Generate draft using local draft_service."""
        from src.models import DraftGenerateRequest
        from src.services import draft_service

        start_time = time.time()

        # Build API request model
        api_request = DraftGenerateRequest(
            transcript=request.transcript,
            outline=request.outline,
            style_config=request.style_config,
            candidate_count=request.candidate_count,
            require_preflight_pass=request.require_preflight_pass,
        )

        try:
            # Start generation job
            job_id = await draft_service.start_generation(api_request)
            logger.info(f"Started generation job {job_id} for {request.transcript_id}")

            # Poll until complete
            poll_interval = 5  # seconds
            deadline = time.time() + timeout_s

            while time.time() < deadline:
                status = await draft_service.get_job_status(job_id)

                if not status:
                    return DraftGenResult(
                        success=False,
                        error=f"Job {job_id} not found",
                        error_code="JOB_NOT_FOUND",
                    )

                if status.status == "completed":
                    generation_time = time.time() - start_time

                    # Build metadata
                    config_hash = compute_config_hash(
                        self.prompt_version,
                        self.model,
                        self.temperature,
                        self.routing_version,
                    )

                    meta = DraftGenMeta(
                        run_id=generate_run_id(
                            request.transcript_id,
                            request.content_mode,
                            0,  # candidate_index
                            config_hash,
                        ),
                        transcript_id=request.transcript_id,
                        candidate_index=0,
                        transcript_path=request.transcript_path,
                        draft_path="",  # Set by caller
                        git_commit=get_git_commit(),
                        config_hash=config_hash,
                        prompt_version=self.prompt_version,
                        model=self.model,
                        temperature=self.temperature,
                        routing_version=self.routing_version,
                        backend="local",
                        content_mode=request.content_mode,
                        seed=None,
                        normalized_sha256=compute_transcript_hash(request.transcript),
                        generation_time_s=generation_time,
                    )

                    return DraftGenResult(
                        success=True,
                        draft_markdown=status.draft_markdown,
                        draft_plan=status.draft_plan,
                        meta=meta,
                    )

                elif status.status == "failed":
                    return DraftGenResult(
                        success=False,
                        error=status.error_message or "Generation failed",
                        error_code=status.error_code or "GENERATION_FAILED",
                    )

                # Still in progress, wait and poll again
                await asyncio.sleep(poll_interval)

            # Timeout
            return DraftGenResult(
                success=False,
                error=f"Generation timed out after {timeout_s}s",
                error_code="TIMEOUT",
            )

        except Exception as e:
            logger.exception(f"Generation failed for {request.transcript_id}")
            return DraftGenResult(
                success=False,
                error=str(e),
                error_code="EXCEPTION",
            )


# =============================================================================
# HTTP Backend
# =============================================================================


class HTTPBackend:
    """HTTP client backend for remote server."""

    def __init__(self, base_url: str = "http://localhost:8000/api"):
        self.base_url = base_url.rstrip("/")
        self.prompt_version = "ideas_v3"
        self.model = "gpt-4o-mini"
        self.temperature = 0.7
        self.routing_version = "2026-01-26"

    async def generate(
        self,
        request: DraftGenRequest,
        timeout_s: int = 600,
    ) -> DraftGenResult:
        """Generate draft via HTTP API."""
        start_time = time.time()

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # Start generation job
                response = await client.post(
                    f"{self.base_url}/ai/draft/generate",
                    json=request.to_api_request(),
                )
                response.raise_for_status()

                data = response.json()
                if data.get("error"):
                    return DraftGenResult(
                        success=False,
                        error=data["error"].get("message", "API error"),
                        error_code=data["error"].get("code", "API_ERROR"),
                    )

                job_id = data["data"]["job_id"]
                logger.info(f"Started HTTP job {job_id} for {request.transcript_id}")

                # Poll until complete
                poll_interval = 5
                deadline = time.time() + timeout_s

                while time.time() < deadline:
                    status_response = await client.get(
                        f"{self.base_url}/ai/draft/status/{job_id}"
                    )
                    status_response.raise_for_status()

                    status_data = status_response.json()
                    if status_data.get("error"):
                        return DraftGenResult(
                            success=False,
                            error="Job not found",
                            error_code="JOB_NOT_FOUND",
                        )

                    status = status_data["data"]

                    if status["status"] == "completed":
                        generation_time = time.time() - start_time

                        config_hash = compute_config_hash(
                            self.prompt_version,
                            self.model,
                            self.temperature,
                            self.routing_version,
                        )

                        meta = DraftGenMeta(
                            run_id=generate_run_id(
                                request.transcript_id,
                                request.content_mode,
                                0,
                                config_hash,
                            ),
                            transcript_id=request.transcript_id,
                            candidate_index=0,
                            transcript_path=request.transcript_path,
                            draft_path="",
                            git_commit=get_git_commit(),
                            config_hash=config_hash,
                            prompt_version=self.prompt_version,
                            model=self.model,
                            temperature=self.temperature,
                            routing_version=self.routing_version,
                            backend="http",
                            content_mode=request.content_mode,
                            seed=None,
                            normalized_sha256=compute_transcript_hash(request.transcript),
                            generation_time_s=generation_time,
                        )

                        return DraftGenResult(
                            success=True,
                            draft_markdown=status.get("draft_markdown"),
                            draft_plan=status.get("draft_plan"),
                            meta=meta,
                        )

                    elif status["status"] == "failed":
                        return DraftGenResult(
                            success=False,
                            error=status.get("error_message", "Generation failed"),
                            error_code=status.get("error_code", "GENERATION_FAILED"),
                        )

                    await asyncio.sleep(poll_interval)

                return DraftGenResult(
                    success=False,
                    error=f"Generation timed out after {timeout_s}s",
                    error_code="TIMEOUT",
                )

            except httpx.HTTPStatusError as e:
                return DraftGenResult(
                    success=False,
                    error=f"HTTP error: {e.response.status_code}",
                    error_code="HTTP_ERROR",
                )
            except Exception as e:
                logger.exception(f"HTTP generation failed for {request.transcript_id}")
                return DraftGenResult(
                    success=False,
                    error=str(e),
                    error_code="EXCEPTION",
                )


# =============================================================================
# Backend Factory
# =============================================================================


def create_backend(
    backend_type: str = "local",
    base_url: str = "http://localhost:8000/api",
) -> DraftGenBackend:
    """Create a draft generation backend.

    Args:
        backend_type: "local" or "http"
        base_url: API base URL (for http backend)

    Returns:
        DraftGenBackend instance
    """
    if backend_type == "local":
        return LocalBackend()
    elif backend_type == "http":
        return HTTPBackend(base_url)
    else:
        raise ValueError(f"Unknown backend type: {backend_type}")
