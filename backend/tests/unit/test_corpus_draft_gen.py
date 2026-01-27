"""Unit tests for corpus draft_gen adapter.

Tests the DraftGen adapter dataclasses and utilities without requiring
actual LLM calls or running server.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from corpus.draft_gen import (
    DraftGenRequest,
    DraftGenResult,
    DraftGenMeta,
    LocalBackend,
    HTTPBackend,
    create_backend,
    compute_config_hash,
    compute_transcript_hash,
    generate_run_id,
    get_git_commit,
)
from corpus.thresholds import (
    Thresholds,
    DEFAULT_THRESHOLDS,
    DEFAULT_OUTLINE,
    DEFAULT_STYLE_CONFIG,
)


# =============================================================================
# Thresholds Tests
# =============================================================================


class TestThresholds:
    def test_default_thresholds(self):
        """Default thresholds have expected values."""
        t = DEFAULT_THRESHOLDS
        assert t.gate_max_fail == 0
        assert t.gate_max_warn == 2
        assert t.gate_max_fallback_rate == 0.25
        assert t.gate_min_p10_prose == 60

    def test_thresholds_to_dict(self):
        """Thresholds can be serialized to dict."""
        t = Thresholds(gate_max_fail=1, gate_max_warn=3)
        d = t.to_dict()
        assert d["gate_max_fail"] == 1
        assert d["gate_max_warn"] == 3

    def test_default_outline(self):
        """Default outline has 3 chapters."""
        assert len(DEFAULT_OUTLINE) == 3
        assert DEFAULT_OUTLINE[0]["title"] == "Introduction"

    def test_default_style_config(self):
        """Default style config has essay content_mode."""
        assert DEFAULT_STYLE_CONFIG["style"]["content_mode"] == "essay"


# =============================================================================
# DraftGenRequest Tests
# =============================================================================


class TestDraftGenRequest:
    def test_content_mode_extraction(self):
        """content_mode property extracts from style_config."""
        request = DraftGenRequest(
            transcript_id="T0001",
            transcript="test transcript",
            transcript_path="/path/to/transcript.txt",
            style_config={"style": {"content_mode": "tutorial"}},
        )
        assert request.content_mode == "tutorial"

    def test_content_mode_default(self):
        """content_mode defaults to essay."""
        request = DraftGenRequest(
            transcript_id="T0001",
            transcript="test transcript",
            transcript_path="/path/to/transcript.txt",
        )
        assert request.content_mode == "essay"

    def test_outline_sha256_deterministic(self):
        """outline_sha256 is deterministic."""
        request1 = DraftGenRequest(
            transcript_id="T0001",
            transcript="test",
            transcript_path="/path",
            outline=[{"id": "1", "title": "Test"}],
        )
        request2 = DraftGenRequest(
            transcript_id="T0001",
            transcript="test",
            transcript_path="/path",
            outline=[{"id": "1", "title": "Test"}],
        )
        assert request1.outline_sha256 == request2.outline_sha256

    def test_style_config_sha256_deterministic(self):
        """style_config_sha256 is deterministic."""
        request1 = DraftGenRequest(
            transcript_id="T0001",
            transcript="test",
            transcript_path="/path",
            style_config={"style": {"content_mode": "essay"}},
        )
        request2 = DraftGenRequest(
            transcript_id="T0001",
            transcript="test",
            transcript_path="/path",
            style_config={"style": {"content_mode": "essay"}},
        )
        assert request1.style_config_sha256 == request2.style_config_sha256

    def test_to_api_request(self):
        """to_api_request produces valid API request dict."""
        request = DraftGenRequest(
            transcript_id="T0001",
            transcript="test transcript content",
            transcript_path="/path/to/transcript.txt",
            candidate_count=2,
            require_preflight_pass=True,
        )
        api_req = request.to_api_request()
        assert api_req["transcript"] == "test transcript content"
        assert api_req["candidate_count"] == 2
        assert api_req["require_preflight_pass"] is True
        assert "transcript_id" not in api_req  # Not part of API

    def test_to_request_json(self):
        """to_request_json produces reproducibility snapshot."""
        request = DraftGenRequest(
            transcript_id="T0001",
            transcript="test transcript",
            transcript_path="/path/to/transcript.txt",
        )
        req_json = request.to_request_json()
        assert req_json["transcript_id"] == "T0001"
        assert req_json["transcript_path"] == "/path/to/transcript.txt"
        assert "outline_sha256" in req_json
        assert "style_config_sha256" in req_json
        assert "transcript" not in req_json  # Not in snapshot


# =============================================================================
# DraftGenMeta Tests
# =============================================================================


class TestDraftGenMeta:
    def test_to_dict(self):
        """DraftGenMeta can be serialized to dict."""
        meta = DraftGenMeta(
            run_id="T0001__essay__c0__abc123",
            transcript_id="T0001",
            candidate_index=0,
            transcript_path="/path/to/transcript.txt",
            draft_path="/path/to/draft.md",
            git_commit="abc123",
            config_hash="def456",
            prompt_version="ideas_v3",
            model="gpt-4o-mini",
            temperature=0.7,
            routing_version="2026-01-26",
            backend="local",
            content_mode="essay",
            seed=None,
            normalized_sha256="ghi789",
            generation_time_s=45.2,
        )
        d = meta.to_dict()
        assert d["run_id"] == "T0001__essay__c0__abc123"
        assert d["backend"] == "local"
        assert d["seed"] is None


# =============================================================================
# DraftGenResult Tests
# =============================================================================


class TestDraftGenResult:
    def test_success_result(self):
        """Successful result has draft and meta."""
        result = DraftGenResult(
            success=True,
            draft_markdown="# Draft",
            draft_plan={"title": "Test"},
        )
        assert result.success is True
        assert result.draft_markdown == "# Draft"
        assert result.error is None

    def test_failure_result(self):
        """Failed result has error info."""
        result = DraftGenResult(
            success=False,
            error="Generation failed",
            error_code="TIMEOUT",
        )
        assert result.success is False
        assert result.error == "Generation failed"
        assert result.error_code == "TIMEOUT"


# =============================================================================
# Utility Function Tests
# =============================================================================


class TestUtilities:
    def test_compute_config_hash_deterministic(self):
        """config_hash is deterministic for same inputs."""
        hash1 = compute_config_hash("v1", "gpt-4o", 0.7, "2026-01-26")
        hash2 = compute_config_hash("v1", "gpt-4o", 0.7, "2026-01-26")
        assert hash1 == hash2

    def test_compute_config_hash_differs_for_different_inputs(self):
        """config_hash differs for different inputs."""
        hash1 = compute_config_hash("v1", "gpt-4o", 0.7, "2026-01-26")
        hash2 = compute_config_hash("v2", "gpt-4o", 0.7, "2026-01-26")
        assert hash1 != hash2

    def test_compute_transcript_hash(self):
        """transcript_hash is deterministic."""
        hash1 = compute_transcript_hash("hello world")
        hash2 = compute_transcript_hash("hello world")
        assert hash1 == hash2
        assert len(hash1) == 16  # Truncated

    def test_generate_run_id(self):
        """run_id follows expected format."""
        run_id = generate_run_id("T0001_test", "essay", 0, "abcdef12")
        assert run_id == "T0001_test__essay__c0__abcdef12"

    def test_get_git_commit(self):
        """get_git_commit returns non-empty string."""
        commit = get_git_commit()
        assert isinstance(commit, str)
        assert len(commit) > 0


# =============================================================================
# Backend Factory Tests
# =============================================================================


class TestBackendFactory:
    def test_create_local_backend(self):
        """create_backend returns LocalBackend for 'local'."""
        backend = create_backend("local")
        assert isinstance(backend, LocalBackend)

    def test_create_http_backend(self):
        """create_backend returns HTTPBackend for 'http'."""
        backend = create_backend("http", "http://example.com/api")
        assert isinstance(backend, HTTPBackend)
        assert backend.base_url == "http://example.com/api"

    def test_create_backend_invalid_type(self):
        """create_backend raises for unknown type."""
        with pytest.raises(ValueError, match="Unknown backend type"):
            create_backend("unknown")


# =============================================================================
# LocalBackend Tests (Mocked)
# =============================================================================


class TestLocalBackendMocked:
    @pytest.mark.asyncio
    async def test_generate_success(self):
        """LocalBackend returns success on completed job."""
        backend = LocalBackend()

        # Mock draft_service (imported inside the method)
        mock_status = MagicMock()
        mock_status.status = "completed"
        mock_status.draft_markdown = "# Generated Draft"
        mock_status.draft_plan = {"title": "Test"}

        with patch("src.services.draft_service.start_generation", new_callable=AsyncMock) as mock_start, \
             patch("src.services.draft_service.get_job_status", new_callable=AsyncMock) as mock_status_fn:
            mock_start.return_value = "job-123"
            mock_status_fn.return_value = mock_status

            request = DraftGenRequest(
                transcript_id="T0001",
                transcript="test transcript content",
                transcript_path="/path/to/transcript.txt",
            )

            result = await backend.generate(request, timeout_s=10)

            assert result.success is True
            assert result.draft_markdown == "# Generated Draft"
            assert result.meta is not None
            assert result.meta.backend == "local"

    @pytest.mark.asyncio
    async def test_generate_failure(self):
        """LocalBackend returns failure on failed job."""
        backend = LocalBackend()

        mock_status = MagicMock()
        mock_status.status = "failed"
        mock_status.error_message = "LLM error"
        mock_status.error_code = "LLM_ERROR"

        with patch("src.services.draft_service.start_generation", new_callable=AsyncMock) as mock_start, \
             patch("src.services.draft_service.get_job_status", new_callable=AsyncMock) as mock_status_fn:
            mock_start.return_value = "job-123"
            mock_status_fn.return_value = mock_status

            request = DraftGenRequest(
                transcript_id="T0001",
                transcript="test",
                transcript_path="/path",
            )

            result = await backend.generate(request, timeout_s=10)

            assert result.success is False
            assert result.error == "LLM error"
            assert result.error_code == "LLM_ERROR"


# =============================================================================
# HTTPBackend Tests (Mocked)
# =============================================================================


class TestHTTPBackendMocked:
    @pytest.mark.asyncio
    async def test_generate_success(self):
        """HTTPBackend returns success on completed job."""
        backend = HTTPBackend("http://test.local/api")

        with patch("corpus.draft_gen.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Mock POST /generate response
            mock_generate_response = MagicMock()
            mock_generate_response.json.return_value = {
                "data": {"job_id": "job-456"},
            }
            mock_generate_response.raise_for_status = MagicMock()

            # Mock GET /status response
            mock_status_response = MagicMock()
            mock_status_response.json.return_value = {
                "data": {
                    "status": "completed",
                    "draft_markdown": "# HTTP Draft",
                    "draft_plan": {"title": "HTTP Test"},
                },
            }
            mock_status_response.raise_for_status = MagicMock()

            mock_client.post = AsyncMock(return_value=mock_generate_response)
            mock_client.get = AsyncMock(return_value=mock_status_response)

            request = DraftGenRequest(
                transcript_id="T0002",
                transcript="test transcript",
                transcript_path="/path/to/transcript.txt",
            )

            result = await backend.generate(request, timeout_s=10)

            assert result.success is True
            assert result.draft_markdown == "# HTTP Draft"
            assert result.meta is not None
            assert result.meta.backend == "http"
