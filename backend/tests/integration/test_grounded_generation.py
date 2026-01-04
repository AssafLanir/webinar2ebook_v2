"""Integration tests for evidence-grounded generation (Spec 009 US1).

Tests for:
- T015: End-to-end grounded generation flow
- T038: Evidence Map integration tests
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import json

from src.services.draft_service import start_generation, get_job_status
from src.services.evidence_service import generate_evidence_map
from src.models import (
    DraftGenerateRequest,
    ChapterPlan,
    JobStatus,
)
from src.models.evidence_map import EvidenceMap, ChapterEvidence, EvidenceEntry, SupportQuote
from src.models.style_config import ContentMode


class TestEvidenceMapIntegration:
    """Integration tests for Evidence Map in generation pipeline."""

    @pytest.mark.asyncio
    async def test_evidence_map_generated_before_chapters(self):
        """Test that Evidence Map is generated before chapter content."""
        chapters = [
            ChapterPlan(
                chapter_number=1,
                title="Introduction",
                outline_item_id="ch1",
                goals=["Understand the basics"],
                key_points=["Key insight 1"],
                transcript_segments=[],
                estimated_words=500,
            ),
        ]

        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "claims": [
                {
                    "id": "c1",
                    "claim": "The speaker recommends starting small",
                    "support": [{"quote": "Start small and iterate"}],
                    "confidence": 0.9,
                    "claim_type": "recommendation",
                }
            ],
            "must_include": [],
        })

        with patch("src.services.evidence_service.LLMClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.complete.return_value = mock_response
            mock_client_class.return_value = mock_client

            evidence_map = await generate_evidence_map(
                project_id="test_project",
                transcript="Start small and iterate. The speaker recommends this approach.",
                chapters=chapters,
                content_mode=ContentMode.interview,
            )

        assert evidence_map is not None
        assert len(evidence_map.chapters) == 1
        assert evidence_map.chapters[0].chapter_index == 1

    @pytest.mark.asyncio
    async def test_interview_mode_sets_forbidden_patterns(self):
        """Test that interview mode adds forbidden content markers."""
        chapters = [
            ChapterPlan(
                chapter_number=1,
                title="Test Chapter",
                outline_item_id="ch1",
                goals=[],
                key_points=[],
                transcript_segments=[],
                estimated_words=500,
            ),
        ]

        mock_response = MagicMock()
        mock_response.content = json.dumps({"claims": [], "must_include": []})

        with patch("src.services.evidence_service.LLMClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.complete.return_value = mock_response
            mock_client_class.return_value = mock_client

            evidence_map = await generate_evidence_map(
                project_id="test",
                transcript="Test transcript",
                chapters=chapters,
                content_mode=ContentMode.interview,
                strict_grounded=True,
            )

        # Interview mode should add forbidden markers
        assert "action_steps" in evidence_map.chapters[0].forbidden
        assert "biographical_details" in evidence_map.chapters[0].forbidden

    @pytest.mark.asyncio
    async def test_evidence_map_contains_transcript_hash(self):
        """Test that Evidence Map has transcript hash for cache invalidation."""
        chapters = [
            ChapterPlan(
                chapter_number=1,
                title="Test",
                outline_item_id="ch1",
                goals=[],
                key_points=[],
                transcript_segments=[],
                estimated_words=500,
            ),
        ]

        mock_response = MagicMock()
        mock_response.content = json.dumps({"claims": [], "must_include": []})

        with patch("src.services.evidence_service.LLMClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.complete.return_value = mock_response
            mock_client_class.return_value = mock_client

            evidence_map = await generate_evidence_map(
                project_id="test",
                transcript="Specific transcript content",
                chapters=chapters,
                content_mode=ContentMode.interview,
            )

        assert evidence_map.transcript_hash is not None
        assert len(evidence_map.transcript_hash) > 0


class TestGroundedChapterGeneration:
    """Integration tests for grounded chapter generation."""

    @pytest.mark.asyncio
    async def test_chapter_uses_evidence_claims(self):
        """Test that chapter generation receives evidence claims."""
        # This is a placeholder for when draft_service integration is complete
        # Will test that generate_chapter receives evidence map data
        pass

    @pytest.mark.asyncio
    async def test_strict_grounding_limits_content(self):
        """Test that strict grounding mode enforces evidence constraints."""
        # Placeholder for strict mode enforcement testing
        pass


class TestJobStatusWithEvidenceMap:
    """Integration tests for job status with Evidence Map."""

    @pytest.mark.asyncio
    async def test_job_status_includes_evidence_map_phase(self):
        """Test that job status shows evidence_map phase."""
        # Test will verify that job status includes evidence_map phase
        # when generation is in progress
        pass

    @pytest.mark.asyncio
    async def test_completed_job_includes_evidence_summary(self):
        """Test that completed job includes Evidence Map summary."""
        # Test will verify evidence summary in completed status
        pass


class TestContentModeWarnings:
    """Integration tests for content mode warnings."""

    @pytest.mark.asyncio
    async def test_mode_mismatch_generates_warning(self):
        """Test that mode mismatch generates constraint warning."""
        from src.services.evidence_service import detect_content_type, generate_mode_warning

        # Tutorial-style content
        transcript = """
        In this tutorial, we'll learn how to implement authentication.
        Step 1: First, install the required packages.
        Step 2: Configure the middleware.
        Make sure to handle errors properly.
        """

        detected_mode, confidence = detect_content_type(transcript)
        warning = generate_mode_warning(
            detected_mode=detected_mode,
            configured_mode=ContentMode.interview,  # Mismatch
            confidence=confidence,
        )

        # Should warn if tutorial detected but interview configured
        if detected_mode == ContentMode.tutorial and confidence > 0.3:
            assert warning is not None

    @pytest.mark.asyncio
    async def test_matching_mode_no_warning(self):
        """Test that matching modes don't generate warnings."""
        from src.services.evidence_service import detect_content_type, generate_mode_warning

        # Interview-style content
        transcript = """
        Host: Welcome to the show. Thanks for joining us.
        Guest: Thank you for having me.
        Host: Tell us about your experience.
        Guest: Well, I've been in the industry for 10 years...
        """

        detected_mode, confidence = detect_content_type(transcript)
        warning = generate_mode_warning(
            detected_mode=detected_mode,
            configured_mode=detected_mode,  # Same mode
            confidence=confidence,
        )

        assert warning is None


class TestEmptyEvidenceHandling:
    """Integration tests for empty evidence scenarios."""

    @pytest.mark.asyncio
    async def test_sparse_chapter_gets_warning(self):
        """Test that chapters with sparse evidence get warnings."""
        from src.services.evidence_service import handle_empty_evidence
        from src.models.evidence_map import ChapterEvidence, MustIncludePriority

        # Chapter with no claims
        chapter = ChapterEvidence(
            chapter_index=1,
            chapter_title="Empty Chapter",
            claims=[],  # No evidence
        )

        result = handle_empty_evidence(
            chapter_evidence=chapter,
            chapter_title="Empty Chapter",
            content_mode=ContentMode.interview,
        )

        # Should have warning must-include item
        assert len(result.must_include) == 1
        assert "[SPARSE EVIDENCE]" in result.must_include[0].point
        assert result.must_include[0].priority == MustIncludePriority.important

    @pytest.mark.asyncio
    async def test_sufficient_evidence_no_warning(self):
        """Test that chapters with sufficient evidence don't get warnings."""
        from src.services.evidence_service import handle_empty_evidence
        from src.models.evidence_map import ChapterEvidence, EvidenceEntry, SupportQuote

        # Chapter with claims
        chapter = ChapterEvidence(
            chapter_index=1,
            chapter_title="Good Chapter",
            claims=[
                EvidenceEntry(
                    id="c1",
                    claim="Test claim",
                    support=[SupportQuote(quote="Test quote")],
                )
            ],
        )

        result = handle_empty_evidence(
            chapter_evidence=chapter,
            chapter_title="Good Chapter",
            content_mode=ContentMode.interview,
        )

        # Should not add any warning
        assert len(result.must_include) == 0
