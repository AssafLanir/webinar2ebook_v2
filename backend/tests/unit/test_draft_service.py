"""Unit tests for draft generation service.

Tests cover:
- DraftPlan generation and validation
- Chapter generation with context
- Job lifecycle (start, progress, cancel)
- Partial results preservation
"""

import asyncio
import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models import (
    DraftPlan,
    ChapterPlan,
    TranscriptSegment,
    GenerationMetadata,
    VisualPlan,
    VisualOpportunity,
    JobStatus,
    GenerationJob,
    DraftGenerateRequest,
)
from src.services import draft_service
from src.services.job_store import JobStore


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def sample_transcript():
    """Sample transcript text (>500 chars)."""
    return """
    Welcome to today's webinar on building scalable web applications.
    We'll cover three main topics: architecture design, database optimization,
    and deployment strategies.

    First, let's talk about architecture. Modern applications need to handle
    thousands of concurrent users. The key is to design for horizontal scaling
    from day one. Use stateless services, separate your data layer, and
    implement proper caching strategies.

    Next, database optimization. Choose the right database for your use case.
    SQL for relational data, NoSQL for flexible schemas. Use indexes wisely,
    optimize your queries, and consider read replicas for scaling reads.

    Finally, deployment. Use containerization with Docker, orchestrate with
    Kubernetes, and implement CI/CD pipelines. Monitor everything and have
    a solid rollback strategy.

    Thank you for attending. Questions?
    """ * 2  # Make it longer


@pytest.fixture
def sample_outline():
    """Sample outline with 3+ items."""
    return [
        {"id": "ch1", "title": "Introduction to Scaling", "level": 1},
        {"id": "ch2", "title": "Architecture Design", "level": 1, "notes": "Focus on horizontal scaling"},
        {"id": "ch3", "title": "Database Optimization", "level": 1},
        {"id": "ch4", "title": "Deployment Strategies", "level": 1},
    ]


@pytest.fixture
def sample_style_config():
    """Sample style configuration."""
    return {
        "version": 1,
        "preset_id": "default_webinar_ebook_v1",
        "style": {
            "tone": "conversational",
            "formality": "conversational",
            "visual_density": "medium",
            "faithfulness_level": "faithful_with_polish",
            "avoid_hallucinations": True,
        }
    }


@pytest.fixture
def sample_draft_plan():
    """Sample DraftPlan for testing."""
    return DraftPlan(
        version=1,
        book_title="Building Scalable Web Applications",
        chapters=[
            ChapterPlan(
                chapter_number=1,
                title="Introduction to Scaling",
                outline_item_id="ch1",
                goals=["Understand scaling basics"],
                key_points=["Horizontal vs vertical scaling"],
                transcript_segments=[
                    TranscriptSegment(start_char=0, end_char=200, relevance="primary")
                ],
                estimated_words=500,
            ),
            ChapterPlan(
                chapter_number=2,
                title="Architecture Design",
                outline_item_id="ch2",
                goals=["Learn architecture patterns"],
                key_points=["Stateless services", "Caching"],
                transcript_segments=[
                    TranscriptSegment(start_char=200, end_char=500, relevance="primary")
                ],
                estimated_words=800,
            ),
            ChapterPlan(
                chapter_number=3,
                title="Database Optimization",
                outline_item_id="ch3",
                goals=["Optimize database performance"],
                key_points=["Index design", "Query optimization"],
                transcript_segments=[
                    TranscriptSegment(start_char=500, end_char=800, relevance="primary")
                ],
                estimated_words=700,
            ),
        ],
        visual_plan=VisualPlan(
            opportunities=[
                VisualOpportunity(
                    id="vis1",
                    chapter_index=1,
                    visual_type="diagram",
                    title="Scaling Overview",
                    prompt="A diagram showing horizontal vs vertical scaling",
                    caption="Figure 1: Scaling Approaches",
                    confidence=0.8,
                )
            ],
            assets=[],
        ),
        generation_metadata=GenerationMetadata(
            estimated_total_words=2000,
            estimated_generation_time_seconds=45,
            transcript_utilization=0.85,
        ),
    )


@pytest.fixture
def sample_generate_request(sample_transcript, sample_outline, sample_style_config):
    """Sample generation request."""
    return DraftGenerateRequest(
        transcript=sample_transcript,
        outline=sample_outline,
        style_config=sample_style_config,
    )


@pytest.fixture
def job_store():
    """Fresh job store for testing."""
    return JobStore()


# =============================================================================
# DraftPlan Generation Tests
# =============================================================================

class TestGenerateDraftPlan:
    """Tests for generate_draft_plan function."""

    @pytest.mark.asyncio
    async def test_generate_draft_plan_returns_valid_structure(
        self, sample_transcript, sample_outline, sample_style_config, sample_draft_plan
    ):
        """Test that generate_draft_plan returns a valid DraftPlan."""
        # Mock the LLM client to return our sample plan
        mock_response = MagicMock()
        mock_response.text = sample_draft_plan.model_dump_json()

        with patch("src.services.draft_service.LLMClient") as MockClient:
            mock_client = MockClient.return_value
            mock_client.generate = AsyncMock(return_value=mock_response)

            plan = await draft_service.generate_draft_plan(
                transcript=sample_transcript,
                outline=sample_outline,
                style_config=sample_style_config,
            )

        assert isinstance(plan, DraftPlan)
        assert plan.book_title
        assert len(plan.chapters) > 0
        assert plan.generation_metadata is not None

    @pytest.mark.asyncio
    async def test_generate_draft_plan_uses_openai_schema(
        self, sample_transcript, sample_outline, sample_style_config, sample_draft_plan
    ):
        """Test that OpenAI strict schema is used for structured output."""
        mock_response = MagicMock()
        mock_response.text = sample_draft_plan.model_dump_json()

        with patch("src.services.draft_service.LLMClient") as MockClient:
            mock_client = MockClient.return_value
            mock_client.generate = AsyncMock(return_value=mock_response)

            with patch("src.services.draft_service.load_draft_plan_schema") as mock_load:
                mock_load.return_value = {"type": "object"}

                await draft_service.generate_draft_plan(
                    transcript=sample_transcript,
                    outline=sample_outline,
                    style_config=sample_style_config,
                )

                # Verify schema loader was called with openai provider
                mock_load.assert_called_once_with(provider="openai")

    @pytest.mark.asyncio
    async def test_generate_draft_plan_maps_all_chapters(
        self, sample_transcript, sample_outline, sample_style_config, sample_draft_plan
    ):
        """Test that all outline items are mapped to chapters."""
        mock_response = MagicMock()
        mock_response.text = sample_draft_plan.model_dump_json()

        with patch("src.services.draft_service.LLMClient") as MockClient:
            mock_client = MockClient.return_value
            mock_client.generate = AsyncMock(return_value=mock_response)

            plan = await draft_service.generate_draft_plan(
                transcript=sample_transcript,
                outline=sample_outline,
                style_config=sample_style_config,
            )

        # Each chapter should have an outline_item_id
        for chapter in plan.chapters:
            assert chapter.outline_item_id
            assert chapter.chapter_number >= 1


# =============================================================================
# Chapter Generation Tests
# =============================================================================

class TestGenerateChapter:
    """Tests for generate_chapter function."""

    @pytest.mark.asyncio
    async def test_generate_chapter_returns_markdown(
        self, sample_transcript, sample_draft_plan, sample_style_config
    ):
        """Test that generate_chapter returns markdown string."""
        mock_response = MagicMock()
        mock_response.text = "## Chapter 1: Introduction\n\nThis is the content."

        with patch("src.services.draft_service.LLMClient") as MockClient:
            mock_client = MockClient.return_value
            mock_client.generate = AsyncMock(return_value=mock_response)

            chapter_md = await draft_service.generate_chapter(
                chapter_plan=sample_draft_plan.chapters[0],
                transcript=sample_transcript,
                book_title=sample_draft_plan.book_title,
                style_config=sample_style_config,
                chapters_completed=[],
                all_chapters=sample_draft_plan.chapters,
            )

        assert isinstance(chapter_md, str)
        assert len(chapter_md) > 0

    @pytest.mark.asyncio
    async def test_generate_chapter_no_visual_placeholders(
        self, sample_transcript, sample_draft_plan, sample_style_config
    ):
        """Test that generated chapter has NO visual placeholders."""
        mock_response = MagicMock()
        mock_response.text = "## Chapter 1: Introduction\n\nContent without placeholders."

        with patch("src.services.draft_service.LLMClient") as MockClient:
            mock_client = MockClient.return_value
            mock_client.generate = AsyncMock(return_value=mock_response)

            chapter_md = await draft_service.generate_chapter(
                chapter_plan=sample_draft_plan.chapters[0],
                transcript=sample_transcript,
                book_title=sample_draft_plan.book_title,
                style_config=sample_style_config,
                chapters_completed=[],
                all_chapters=sample_draft_plan.chapters,
            )

        # No visual placeholders allowed
        assert "[IMAGE]" not in chapter_md
        assert "VISUAL_SLOT" not in chapter_md
        assert "[FIGURE]" not in chapter_md

    @pytest.mark.asyncio
    async def test_generate_chapter_uses_transcript_segment(
        self, sample_transcript, sample_draft_plan, sample_style_config
    ):
        """Test that chapter generation uses the mapped transcript segment."""
        mock_response = MagicMock()
        mock_response.text = "## Chapter 1\n\nContent"

        captured_request = None

        async def capture_request(request):
            nonlocal captured_request
            captured_request = request
            return mock_response

        with patch("src.services.draft_service.LLMClient") as MockClient:
            mock_client = MockClient.return_value
            mock_client.generate = AsyncMock(side_effect=capture_request)

            await draft_service.generate_chapter(
                chapter_plan=sample_draft_plan.chapters[0],
                transcript=sample_transcript,
                book_title=sample_draft_plan.book_title,
                style_config=sample_style_config,
                chapters_completed=[],
                all_chapters=sample_draft_plan.chapters,
            )

        # Verify the request was made (transcript segment extraction happens in prompts)
        assert captured_request is not None


# =============================================================================
# Chapter Assembly Tests
# =============================================================================

class TestAssembleChapters:
    """Tests for assemble_chapters function."""

    def test_assemble_chapters_creates_markdown(self):
        """Test that assemble_chapters creates valid markdown."""
        chapters = [
            "## Chapter 1: Intro\n\nFirst chapter content.",
            "## Chapter 2: Main\n\nSecond chapter content.",
        ]

        result = draft_service.assemble_chapters(
            book_title="Test Book",
            chapters=chapters,
        )

        assert "# Test Book" in result
        assert "## Chapter 1: Intro" in result
        assert "## Chapter 2: Main" in result

    def test_assemble_chapters_no_visual_placeholders(self):
        """Test that assembled draft has no visual placeholders."""
        chapters = [
            "## Chapter 1\n\nContent",
            "## Chapter 2\n\nMore content",
        ]

        result = draft_service.assemble_chapters(
            book_title="Test Book",
            chapters=chapters,
        )

        assert "[IMAGE]" not in result
        assert "VISUAL_SLOT" not in result


# =============================================================================
# Job Lifecycle Tests
# =============================================================================

class TestJobLifecycle:
    """Tests for job management functions."""

    @pytest.mark.asyncio
    async def test_start_generation_creates_job(self, sample_generate_request):
        """Test that start_generation creates a job and returns ID."""
        with patch("src.services.draft_service._generate_draft_task", new_callable=AsyncMock):
            job_id = await draft_service.start_generation(sample_generate_request)

        assert job_id is not None
        assert len(job_id) > 0

    @pytest.mark.asyncio
    async def test_get_job_status_returns_data(self, sample_generate_request):
        """Test that get_job_status returns status data."""
        with patch("src.services.draft_service._generate_draft_task", new_callable=AsyncMock):
            job_id = await draft_service.start_generation(sample_generate_request)

        status = await draft_service.get_job_status(job_id)

        assert status is not None
        assert status.job_id == job_id
        assert status.status in [s.value for s in JobStatus]

    @pytest.mark.asyncio
    async def test_get_job_status_not_found(self):
        """Test that get_job_status returns None for unknown job."""
        status = await draft_service.get_job_status("nonexistent-job-id")
        assert status is None

    @pytest.mark.asyncio
    async def test_cancel_job_sets_flag(self, sample_generate_request):
        """Test that cancel_job sets the cancel flag."""
        with patch("src.services.draft_service._generate_draft_task", new_callable=AsyncMock):
            job_id = await draft_service.start_generation(sample_generate_request)

        cancel_data = await draft_service.cancel_job(job_id)

        assert cancel_data is not None
        assert cancel_data.cancelled is True

    @pytest.mark.asyncio
    async def test_cancel_job_not_found(self):
        """Test that cancel_job returns None for unknown job."""
        cancel_data = await draft_service.cancel_job("nonexistent-job-id")
        assert cancel_data is None


# =============================================================================
# Progress and Partial Results Tests
# =============================================================================

class TestProgressAndPartials:
    """Tests for progress tracking and partial results."""

    @pytest.mark.asyncio
    async def test_status_includes_progress_during_generation(self, job_store):
        """Test that status includes progress info during generation."""
        job_id = await job_store.create_job()
        await job_store.update_job(
            job_id,
            status=JobStatus.generating,
            current_chapter=2,
            total_chapters=5,
            chapters_completed=["## Ch1\n\nContent"],
        )

        job = await job_store.get_job(job_id)
        progress = job.get_progress()

        assert progress.current_chapter == 2
        assert progress.total_chapters == 5
        assert progress.chapters_completed == 1

    @pytest.mark.asyncio
    async def test_cancel_preserves_partial_results(self, job_store):
        """Test that cancellation preserves completed chapters."""
        job_id = await job_store.create_job()
        completed_chapters = [
            "## Chapter 1\n\nFirst content",
            "## Chapter 2\n\nSecond content",
        ]
        await job_store.update_job(
            job_id,
            status=JobStatus.cancelled,
            total_chapters=5,
            chapters_completed=completed_chapters,
        )

        job = await job_store.get_job(job_id)

        assert job.status == JobStatus.cancelled
        assert len(job.chapters_completed) == 2

    @pytest.mark.asyncio
    async def test_failed_job_preserves_partial_results(self, job_store):
        """Test that failed job preserves completed chapters."""
        job_id = await job_store.create_job()
        await job_store.update_job(
            job_id,
            status=JobStatus.failed,
            error="LLM timeout",
            chapters_completed=["## Ch1\n\nContent"],
        )

        job = await job_store.get_job(job_id)

        assert job.status == JobStatus.failed
        assert job.error == "LLM timeout"
        assert len(job.chapters_completed) == 1


# =============================================================================
# Visual Opportunities Tests
# =============================================================================

class TestVisualOpportunities:
    """Tests for visual opportunity generation."""

    def test_visual_opportunities_in_draft_plan(self, sample_draft_plan):
        """Test that DraftPlan includes visual opportunities."""
        assert sample_draft_plan.visual_plan is not None
        assert len(sample_draft_plan.visual_plan.opportunities) > 0

    def test_visual_opportunities_have_required_fields(self, sample_draft_plan):
        """Test that visual opportunities have all required fields."""
        for opp in sample_draft_plan.visual_plan.opportunities:
            assert opp.id
            assert opp.chapter_index >= 1
            assert opp.visual_type
            assert opp.title
            assert opp.prompt
            assert opp.caption

    def test_visual_plan_separate_from_markdown(self, sample_draft_plan):
        """Test that visual plan is separate metadata, not in markdown."""
        chapters = ["## Ch1\n\nContent without visuals"]
        markdown = draft_service.assemble_chapters(
            book_title=sample_draft_plan.book_title,
            chapters=chapters,
        )

        # Visual metadata exists
        assert len(sample_draft_plan.visual_plan.opportunities) > 0

        # But not in markdown
        assert "VISUAL" not in markdown
        assert "[IMAGE]" not in markdown
