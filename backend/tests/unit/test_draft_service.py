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
    """Fresh in-memory job store for testing."""
    from src.services.job_store import InMemoryJobStore, set_job_store
    store = InMemoryJobStore()
    set_job_store(store)
    yield store
    set_job_store(None)


# =============================================================================
# DraftPlan Generation Tests
# =============================================================================

class TestGenerateDraftPlan:
    """Tests for generate_draft_plan function (outline-driven)."""

    @pytest.mark.asyncio
    async def test_generate_draft_plan_returns_valid_structure(
        self, sample_transcript, sample_outline, sample_style_config
    ):
        """Test that generate_draft_plan returns a valid DraftPlan."""
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
    async def test_generate_draft_plan_chapters_from_outline(
        self, sample_transcript, sample_outline, sample_style_config
    ):
        """Test that chapters are derived from outline (not LLM)."""
        plan = await draft_service.generate_draft_plan(
            transcript=sample_transcript,
            outline=sample_outline,
            style_config=sample_style_config,
        )

        # Should have same number of chapters as level-1 outline items
        level_1_count = sum(1 for item in sample_outline if item.get("level", 1) == 1)
        assert len(plan.chapters) == level_1_count

    @pytest.mark.asyncio
    async def test_generate_draft_plan_maps_all_chapters(
        self, sample_transcript, sample_outline, sample_style_config
    ):
        """Test that all outline items are mapped to chapters."""
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
    async def test_start_generation_creates_job(self, sample_generate_request, job_store):
        """Test that start_generation creates a job and returns ID."""
        with patch("src.services.draft_service._generate_draft_task", new_callable=AsyncMock):
            job_id = await draft_service.start_generation(sample_generate_request)

        assert job_id is not None
        assert len(job_id) > 0

    @pytest.mark.asyncio
    async def test_get_job_status_returns_data(self, sample_generate_request, job_store):
        """Test that get_job_status returns status data."""
        with patch("src.services.draft_service._generate_draft_task", new_callable=AsyncMock):
            job_id = await draft_service.start_generation(sample_generate_request)

        status = await draft_service.get_job_status(job_id)

        assert status is not None
        assert status.job_id == job_id
        assert status.status in [s.value for s in JobStatus]

    @pytest.mark.asyncio
    async def test_get_job_status_not_found(self, job_store):
        """Test that get_job_status returns None for unknown job."""
        status = await draft_service.get_job_status("nonexistent-job-id")
        assert status is None

    @pytest.mark.asyncio
    async def test_cancel_job_sets_flag(self, sample_generate_request, job_store):
        """Test that cancel_job sets the cancel flag."""
        with patch("src.services.draft_service._generate_draft_task", new_callable=AsyncMock):
            job_id = await draft_service.start_generation(sample_generate_request)

        cancel_data = await draft_service.cancel_job(job_id)

        assert cancel_data is not None
        assert cancel_data.cancelled is True

    @pytest.mark.asyncio
    async def test_cancel_job_not_found(self, job_store):
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


# =============================================================================
# Outline-Driven Chapter Structure Tests
# =============================================================================

class TestOutlineDrivenChapters:
    """Tests for outline-driven chapter structure."""

    @pytest.mark.asyncio
    async def test_total_chapters_equals_top_level_outline_items(
        self, sample_transcript, sample_style_config
    ):
        """Test that total chapters equals number of top-level (level=1) outline items."""
        outline = [
            {"id": "ch1", "title": "Introduction", "level": 1, "order": 0},
            {"id": "ch1-sec1", "title": "Background", "level": 2, "order": 1},
            {"id": "ch2", "title": "Main Content", "level": 1, "order": 2},
            {"id": "ch2-sec1", "title": "Details", "level": 2, "order": 3},
            {"id": "ch2-sec2", "title": "Examples", "level": 2, "order": 4},
            {"id": "ch3", "title": "Conclusion", "level": 1, "order": 5},
        ]

        plan = await draft_service.generate_draft_plan(
            transcript=sample_transcript,
            outline=outline,
            style_config=sample_style_config,
        )

        # Should have exactly 3 chapters (level=1 items)
        assert len(plan.chapters) == 3

        # Verify chapter titles match top-level outline items
        assert plan.chapters[0].title == "Introduction"
        assert plan.chapters[1].title == "Main Content"
        assert plan.chapters[2].title == "Conclusion"

    @pytest.mark.asyncio
    async def test_chapter_titles_match_outline(self, sample_transcript, sample_style_config):
        """Test that chapter titles exactly match the outline item titles."""
        outline = [
            {"id": "ch1", "title": "Getting Started with Python", "level": 1, "order": 0},
            {"id": "ch2", "title": "Advanced Techniques", "level": 1, "order": 1},
            {"id": "ch3", "title": "Best Practices", "level": 1, "order": 2},
        ]

        plan = await draft_service.generate_draft_plan(
            transcript=sample_transcript,
            outline=outline,
            style_config=sample_style_config,
        )

        assert plan.chapters[0].title == "Getting Started with Python"
        assert plan.chapters[1].title == "Advanced Techniques"
        assert plan.chapters[2].title == "Best Practices"

    @pytest.mark.asyncio
    async def test_nested_items_become_key_points(
        self, sample_transcript, sample_style_config
    ):
        """Test that nested outline items (level > 1) become key_points in chapters."""
        outline = [
            {"id": "ch1", "title": "Chapter One", "level": 1, "order": 0},
            {"id": "sec1", "title": "First Section", "level": 2, "order": 1, "notes": "Important details"},
            {"id": "sec2", "title": "Second Section", "level": 2, "order": 2},
            {"id": "ch2", "title": "Chapter Two", "level": 1, "order": 3},
        ]

        plan = await draft_service.generate_draft_plan(
            transcript=sample_transcript,
            outline=outline,
            style_config=sample_style_config,
        )

        # Chapter 1 should have key_points from nested items
        assert len(plan.chapters[0].key_points) == 2
        assert "First Section: Important details" in plan.chapters[0].key_points
        assert "Second Section" in plan.chapters[0].key_points

        # Chapter 2 should have no key_points (no nested items)
        assert len(plan.chapters[1].key_points) == 0

    @pytest.mark.asyncio
    async def test_chapter_order_respects_outline_order(
        self, sample_transcript, sample_style_config
    ):
        """Test that chapters are ordered according to outline order field."""
        # Outline items not in order by index
        outline = [
            {"id": "ch3", "title": "Third", "level": 1, "order": 2},
            {"id": "ch1", "title": "First", "level": 1, "order": 0},
            {"id": "ch2", "title": "Second", "level": 1, "order": 1},
        ]

        plan = await draft_service.generate_draft_plan(
            transcript=sample_transcript,
            outline=outline,
            style_config=sample_style_config,
        )

        # Chapters should be ordered by 'order' field
        assert plan.chapters[0].title == "First"
        assert plan.chapters[0].chapter_number == 1
        assert plan.chapters[1].title == "Second"
        assert plan.chapters[1].chapter_number == 2
        assert plan.chapters[2].title == "Third"
        assert plan.chapters[2].chapter_number == 3

    @pytest.mark.asyncio
    async def test_outline_item_ids_preserved(self, sample_transcript, sample_style_config):
        """Test that outline_item_id is preserved from source outline."""
        outline = [
            {"id": "unique-id-123", "title": "Chapter One", "level": 1, "order": 0},
            {"id": "unique-id-456", "title": "Chapter Two", "level": 1, "order": 1},
        ]

        plan = await draft_service.generate_draft_plan(
            transcript=sample_transcript,
            outline=outline,
            style_config=sample_style_config,
        )

        assert plan.chapters[0].outline_item_id == "unique-id-123"
        assert plan.chapters[1].outline_item_id == "unique-id-456"

    @pytest.mark.asyncio
    async def test_transcript_segments_mapped_to_chapters(
        self, sample_transcript, sample_style_config
    ):
        """Test that transcript segments are mapped to chapters."""
        outline = [
            {"id": "ch1", "title": "Part One", "level": 1, "order": 0},
            {"id": "ch2", "title": "Part Two", "level": 1, "order": 1},
        ]

        plan = await draft_service.generate_draft_plan(
            transcript=sample_transcript,
            outline=outline,
            style_config=sample_style_config,
        )

        # Each chapter should have transcript segments
        for chapter in plan.chapters:
            assert len(chapter.transcript_segments) > 0
            seg = chapter.transcript_segments[0]
            assert seg.start_char >= 0
            assert seg.end_char > seg.start_char

    @pytest.mark.asyncio
    async def test_empty_outline_creates_fallback_chapter(
        self, sample_transcript, sample_style_config
    ):
        """Test that empty outline creates a single fallback chapter."""
        plan = await draft_service.generate_draft_plan(
            transcript=sample_transcript,
            outline=[],
            style_config=sample_style_config,
        )

        # Should create one fallback chapter
        assert len(plan.chapters) == 1
        assert plan.chapters[0].title == "Content"

    @pytest.mark.asyncio
    async def test_book_title_from_first_outline_item(
        self, sample_transcript, sample_style_config
    ):
        """Test that book title is derived from first top-level outline item."""
        outline = [
            {"id": "ch1", "title": "The Complete Guide", "level": 1, "order": 0},
            {"id": "ch2", "title": "Advanced Topics", "level": 1, "order": 1},
        ]

        plan = await draft_service.generate_draft_plan(
            transcript=sample_transcript,
            outline=outline,
            style_config=sample_style_config,
        )

        assert plan.book_title == "The Complete Guide"


# =============================================================================
# Essay Format Enforcement Tests
# =============================================================================


class TestStripBannedSections:
    """Tests for strip_banned_sections function."""

    def test_strips_key_takeaways_section(self):
        """Test removal of Key Takeaways section with bullets."""
        text = """# Chapter Title

Some introductory text here.

## Key Takeaways
- First takeaway point
- Second takeaway point
- Third takeaway point

More content after."""

        result, removed = draft_service.strip_banned_sections(text, "essay")

        assert "Key Takeaways" not in result
        assert "First takeaway point" not in result
        assert "More content after" in result
        assert len(removed) == 1
        assert "Key Takeaways" in removed[0]

    def test_strips_action_steps_section(self):
        """Test removal of Action Steps section."""
        text = """# Chapter

Content here.

## Action Steps
1. Do this first
2. Then do this
3. Finally this

Next section content."""

        result, removed = draft_service.strip_banned_sections(text, "essay")

        assert "Action Steps" not in result
        assert "Do this first" not in result
        assert "Next section content" in result

    def test_strips_actionable_items_section(self):
        """Test removal of Actionable Items variation."""
        text = """# Chapter

Content.

### Actionable Items
- Item one
- Item two

Final paragraph."""

        result, removed = draft_service.strip_banned_sections(text, "essay")

        assert "Actionable Items" not in result
        assert "Item one" not in result

    def test_preserves_non_banned_sections(self):
        """Test that non-banned sections are preserved."""
        text = """# Chapter Title

## Introduction
This is important content.

## Main Discussion
More substantive content here.

## Conclusion
Final thoughts on the matter."""

        result, removed = draft_service.strip_banned_sections(text, "essay")

        assert result == text
        assert len(removed) == 0

    def test_handles_conclusion_with_bullets(self):
        """Test removal of conclusion section with bullet recap."""
        text = """# Chapter

Content here.

## Conclusion
- Point one
- Point two
- Point three

"""

        result, removed = draft_service.strip_banned_sections(text, "essay")

        assert "Conclusion" not in result or "Point one" not in result


class TestCountBannedPhrases:
    """Tests for count_banned_phrases function."""

    def test_counts_in_conclusion(self):
        """Test counting of 'In conclusion' phrase."""
        text = "In conclusion, this is important. Moreover, we should note that..."

        counts = draft_service.count_banned_phrases(text)

        assert counts.get("In conclusion", 0) >= 1

    def test_counts_multiple_occurrences(self):
        """Test counting multiple occurrences of same phrase."""
        text = "Moreover, this is true. Moreover, we see that. Moreover, it follows."

        counts = draft_service.count_banned_phrases(text)

        assert counts.get("Moreover", 0) == 3

    def test_counts_lets_explore(self):
        """Test counting of conversational AI phrases."""
        text = "Let's explore the topic. Let's dive into the details."

        counts = draft_service.count_banned_phrases(text)

        assert counts.get("Let's explore", 0) == 1
        assert counts.get("Let's dive into", 0) == 1

    def test_returns_empty_for_clean_text(self):
        """Test that clean text returns empty counts."""
        text = """This chapter examines the key principles of knowledge creation.
        David Deutsch argues that explanations must be hard to vary.
        The implications extend beyond physics into epistemology."""

        counts = draft_service.count_banned_phrases(text)

        total = sum(counts.values())
        assert total == 0


class TestEnforceProseQuality:
    """Tests for enforce_prose_quality function."""

    def test_combines_strip_and_count(self):
        """Test that enforcement combines section stripping and phrase counting."""
        text = """# Chapter

Good content here.

## Key Takeaways
- Takeaway one
- Takeaway two

In conclusion, this demonstrates the importance."""

        result, report = draft_service.enforce_prose_quality(text, "essay")

        assert "Key Takeaways" not in result
        assert "sections_removed" in report
        assert "banned_phrase_counts" in report or "banned_phrase_count" in report

    def test_preserves_clean_essay_content(self):
        """Test that clean essay content passes through unchanged."""
        text = """# The Fabric of Reality

David Deutsch's conception of knowledge begins with a simple observation:
we cannot see atoms, yet we know they exist. Our knowledge of them comes
not from direct observation but from explanation—theories that account
for what we do observe while being hard to vary without losing their
explanatory power.

This criterion of hard-to-vary explanations distinguishes genuine
understanding from mere description. A myth that attributes thunder
to angry gods can easily accommodate any observed pattern; its
flexibility is precisely what makes it hollow. A theory of atmospheric
electricity, by contrast, makes specific predictions that could
prove it wrong.

The deeper question concerns the nature of these explanations
themselves. Where do they come from? They cannot emerge from data
alone—no amount of observation can logically compel a theory."""

        result, report = draft_service.enforce_prose_quality(text, "essay")

        # Clean text should pass through with minimal changes
        assert "sections_removed" in report
        assert len(report["sections_removed"]) == 0


# =============================================================================
# Quote Substring Validation Tests
# =============================================================================


class TestExtractQuotes:
    """Tests for extract_quotes function."""

    def test_extracts_straight_quotes(self):
        """Test extraction of straight double quotes."""
        text = 'He said "this is important" and then "another quote" followed.'
        quotes = draft_service.extract_quotes(text)
        assert len(quotes) == 2
        assert quotes[0]['quote'] == 'this is important'
        assert quotes[1]['quote'] == 'another quote'

    def test_extracts_smart_quotes(self):
        """Test extraction of smart/curly quotes."""
        text = "He said \u201cthis is important\u201d and then \u201canother quote\u201d followed."
        quotes = draft_service.extract_quotes(text)
        assert len(quotes) == 2
        assert quotes[0]["quote"] == "this is important"

    def test_returns_empty_for_no_quotes(self):
        """Test that text without quotes returns empty list."""
        text = 'This text has no quotes at all.'
        quotes = draft_service.extract_quotes(text)
        assert len(quotes) == 0


class TestNormalizeForComparison:
    """Tests for normalize_for_comparison function."""

    def test_normalizes_smart_quotes(self):
        """Test smart quote normalization."""
        text = "\u201cHello\u201d and \u2018world\u2019"  # "Hello" and 'world'
        normalized = draft_service.normalize_for_comparison(text)
        # Smart quotes should be converted to straight quotes
        assert '"hello" and' in normalized
        assert "world" in normalized

    def test_normalizes_dashes(self):
        """Test em-dash and en-dash normalization."""
        text = "one\u2014two\u2013three"  # one—two–three
        normalized = draft_service.normalize_for_comparison(text)
        assert "\u2014" not in normalized  # em-dash
        assert "\u2013" not in normalized  # en-dash
        assert "one-two-three" in normalized

    def test_normalizes_whitespace(self):
        """Test whitespace normalization."""
        text = 'multiple   spaces   here'
        normalized = draft_service.normalize_for_comparison(text)
        assert 'multiple spaces here' in normalized

    def test_lowercases(self):
        """Test lowercase conversion."""
        text = 'Hello World'
        normalized = draft_service.normalize_for_comparison(text)
        assert normalized == 'hello world'


class TestValidateQuoteAgainstTranscript:
    """Tests for validate_quote_against_transcript function."""

    def test_valid_exact_match(self):
        """Test that exact substring match is valid."""
        transcript = "The speaker said that knowledge is infinite and progress is possible."
        quote = "knowledge is infinite"
        result = draft_service.validate_quote_against_transcript(quote, transcript)
        assert result['valid'] is True
        assert result['reason'] == 'exact_match'

    def test_valid_with_case_difference(self):
        """Test that case-insensitive match is valid."""
        transcript = "Knowledge is infinite."
        quote = "knowledge is infinite"
        result = draft_service.validate_quote_against_transcript(quote, transcript)
        assert result['valid'] is True

    def test_invalid_ellipsis_three_dots(self):
        """Test that quotes with ... ellipsis are rejected."""
        transcript = "Once one has this method, the scope of understanding is limitless."
        quote = "Once one has this method... the scope"
        result = draft_service.validate_quote_against_transcript(quote, transcript)
        assert result['valid'] is False
        assert result['reason'] == 'contains_ellipsis'

    def test_invalid_ellipsis_unicode(self):
        """Test that quotes with … (unicode ellipsis) are rejected."""
        transcript = "Once one has this method, the scope of understanding is limitless."
        quote = "Once one has this method… the scope"
        result = draft_service.validate_quote_against_transcript(quote, transcript)
        assert result['valid'] is False
        assert result['reason'] == 'contains_ellipsis'

    def test_invalid_fabricated_quote(self):
        """Test that fabricated quotes are rejected."""
        transcript = "The speaker discussed quantum computing."
        quote = "a leading voice in quantum computing"
        result = draft_service.validate_quote_against_transcript(quote, transcript)
        assert result['valid'] is False
        assert result['reason'] == 'not_in_transcript'

    def test_invalid_truncation_em_dash(self):
        """Test that quotes ending with em-dash are rejected as truncated."""
        transcript = "You're grossly underestimating how bad the past was, how totally violent."
        quote = "you're grossly underestimating how bad the past was, how totally—"
        result = draft_service.validate_quote_against_transcript(quote, transcript)
        assert result['valid'] is False
        assert result['reason'] == 'truncated_quote'

    def test_invalid_truncation_en_dash(self):
        """Test that quotes ending with en-dash are rejected as truncated."""
        transcript = "The world was static in terms of ideas and progress."
        quote = "The world was static in terms of ideas–"
        result = draft_service.validate_quote_against_transcript(quote, transcript)
        assert result['valid'] is False
        assert result['reason'] == 'truncated_quote'

    def test_invalid_truncation_hyphen(self):
        """Test that quotes ending with hyphen are rejected as truncated."""
        transcript = "Knowledge is power and progress is possible."
        quote = "Knowledge is power and progress-"
        result = draft_service.validate_quote_against_transcript(quote, transcript)
        assert result['valid'] is False
        assert result['reason'] == 'truncated_quote'

    def test_valid_quote_with_internal_dash(self):
        """Test that quotes with internal dashes (not at end) are still valid."""
        transcript = "The pre-Enlightenment world was static."
        quote = "pre-Enlightenment world"
        result = draft_service.validate_quote_against_transcript(quote, transcript)
        assert result['valid'] is True

    def test_valid_with_smart_quote_mismatch(self):
        """Test that smart/straight quote differences don't cause false negatives."""
        transcript = 'He said "knowledge is power" clearly.'
        quote = "knowledge is power"  # Using straight quotes in generated text
        result = draft_service.validate_quote_against_transcript(quote, transcript)
        assert result['valid'] is True


class TestValidateQuotesInText:
    """Tests for validate_quotes_in_text function."""

    def test_all_valid_quotes(self):
        """Test text where all quotes are valid."""
        transcript = "The Enlightenment changed everything. Progress became possible."
        text = 'He said "The Enlightenment changed everything" which was profound.'
        result = draft_service.validate_quotes_in_text(text, transcript)
        assert result['valid'] is True
        assert result['summary']['invalid'] == 0

    def test_mixed_valid_and_invalid(self):
        """Test text with both valid and invalid quotes."""
        transcript = "Knowledge is infinite. Progress is possible."
        text = 'He said "Knowledge is infinite" and also "fabricated quote here".'
        result = draft_service.validate_quotes_in_text(text, transcript)
        assert result['valid'] is False
        assert result['summary']['valid'] == 1
        assert result['summary']['fabricated'] == 1

    def test_ellipsis_counted_separately(self):
        """Test that ellipsis violations are counted separately from fabricated."""
        transcript = "Once one has this method, the scope is limitless."
        text = 'He said "Once one has this method... the scope" which is wrong.'
        result = draft_service.validate_quotes_in_text(text, transcript)
        assert result['valid'] is False
        assert result['summary']['ellipsis_violations'] == 1
        assert result['summary']['fabricated'] == 0


class TestEnforceQuoteGrounding:
    """Tests for enforce_quote_grounding function."""

    def test_converts_invalid_quote_to_paraphrase(self):
        """Test that invalid quotes become paraphrases (quotes removed, text kept)."""
        transcript = "Knowledge is power. Progress is possible."
        text = (
            "First paragraph here.\n\n"
            'He claimed "this is a fabricated quote" in his speech.\n\n'
            "Last paragraph here."
        )
        result, report = draft_service.enforce_quote_grounding(text, transcript, convert_invalid=True)
        # Text content is preserved, but without quotes
        assert "this is a fabricated quote" in result
        assert '"this is a fabricated quote"' not in result
        assert "First paragraph" in result
        assert "Last paragraph" in result
        assert len(report['converted_quotes']) == 1
        assert report['converted_quotes'][0] == "this is a fabricated quote"

    def test_preserves_valid_quotes(self):
        """Test that valid quotes are preserved with their quotation marks."""
        transcript = "Knowledge is power and progress is possible."
        text = 'He said "Knowledge is power" clearly.'
        result, report = draft_service.enforce_quote_grounding(text, transcript, convert_invalid=True)
        assert '"Knowledge is power"' in result
        assert len(report['converted_quotes']) == 0

    def test_converts_ellipsis_quotes_to_paraphrase(self):
        """Test that quotes with ellipsis become paraphrases."""
        transcript = "Once one has this method, the scope of understanding is limitless."
        text = 'Deutsch notes: "Once one has this method... the scope" is key.'
        result, report = draft_service.enforce_quote_grounding(text, transcript, convert_invalid=True)
        # Quote marks removed but text kept
        assert "Once one has this method... the scope" in result
        assert '"Once one has this method... the scope"' not in result
        assert report['summary']['ellipsis_violations'] == 1


class TestGlobalEllipsisBan:
    """Tests for global ellipsis ban (Step B)."""

    def test_finds_three_dot_ellipsis(self):
        """Test detection of ... ellipsis."""
        text = "First sentence. He said something... and then continued. Last sentence."
        ellipses = draft_service.find_ellipses_in_text(text)
        assert len(ellipses) == 1
        assert ellipses[0]['match'] == '...'

    def test_finds_unicode_ellipsis(self):
        """Test detection of \u2026 (unicode ellipsis)."""
        text = "First sentence. He trailed off\u2026 mysteriously. Last sentence."
        ellipses = draft_service.find_ellipses_in_text(text)
        assert len(ellipses) == 1
        assert ellipses[0]['match'] == '\u2026'

    def test_finds_multiple_ellipses(self):
        """Test detection of multiple ellipses."""
        text = "First... second\u2026 third. No ellipsis here."
        ellipses = draft_service.find_ellipses_in_text(text)
        assert len(ellipses) == 2

    def test_removes_sentence_with_ellipsis(self):
        """Test that sentences containing ellipsis are removed."""
        text = (
            "First paragraph here.\n\n"
            "Deutsch argues, once one has this method... the scope is limitless.\n\n"
            "Last paragraph here."
        )
        result, report = draft_service.enforce_ellipsis_ban(text, remove_sentences=True)
        assert "..." not in result
        assert "First paragraph" in result
        assert "Last paragraph" in result
        assert report['ellipses_found'] == 1
        assert len(report['removed_sentences']) == 1

    def test_preserves_text_without_ellipsis(self):
        """Test that text without ellipsis is preserved."""
        text = "First sentence. Second sentence. Third sentence."
        result, report = draft_service.enforce_ellipsis_ban(text, remove_sentences=True)
        assert result == text
        assert report['ellipses_found'] == 0
        assert len(report['removed_sentences']) == 0

    def test_removes_multiple_ellipsis_sentences(self):
        """Test removal of multiple sentences with ellipses."""
        text = (
            "Keep this sentence.\n\n"
            "Remove this... has ellipsis.\n\n"
            "Keep this one too.\n\n"
            "Also remove\u2026 this one."
        )
        result, report = draft_service.enforce_ellipsis_ban(text, remove_sentences=True)
        assert "Keep this sentence" in result
        assert "Keep this one too" in result
        assert "Remove this..." not in result
        assert "Also remove" not in result
        assert report['ellipses_found'] == 2


class TestAttributedSpeechEnforcement:
    """Tests for attributed-speech enforcement (Step A)."""

    def test_finds_prefix_attribution(self):
        """Test detection of 'Speaker argues, X' pattern."""
        text = "Deutsch argues, knowledge is the key to unlimited progress."
        attributed = draft_service.find_attributed_speech(text)
        assert len(attributed) == 1
        assert attributed[0]['speaker'] == 'Deutsch'
        assert 'knowledge is the key' in attributed[0]['content']
        assert attributed[0]['pattern_type'] == 'prefix'

    def test_finds_suffix_attribution(self):
        """Test detection of 'X, Speaker argues' pattern."""
        text = "Knowledge is the key to unlimited progress, Deutsch argues."
        attributed = draft_service.find_attributed_speech(text)
        assert len(attributed) == 1
        assert attributed[0]['speaker'] == 'Deutsch'
        assert 'Knowledge is the key' in attributed[0]['content']
        assert attributed[0]['pattern_type'] == 'suffix'

    def test_finds_mid_sentence_attribution(self):
        """Test detection of 'X, he says, Y' pattern (mid-sentence attribution)."""
        text = "The truth of the matter is that wisdom is limitless, he says, pushing us to rethink our capabilities."
        attributed = draft_service.find_attributed_speech(text)
        assert len(attributed) == 1
        assert attributed[0]['speaker'].lower() == 'he'
        assert 'wisdom is limitless' in attributed[0]['content']
        assert attributed[0]['pattern_type'] == 'mid'

    def test_finds_saying_verb_form(self):
        """Test detection of 'saying' verb form (participial pattern)."""
        text = "Deutsch agrees with Hawking, saying we should hedge our bets by moving away from the Earth."
        attributed = draft_service.find_attributed_speech(text)
        assert len(attributed) >= 1
        assert any('hedge our bets' in a['content'] for a in attributed)
        assert any(a['pattern_type'] == 'participial' for a in attributed)

    def test_finds_extended_colon_attribution(self):
        """Test detection of 'Speaker's thoughts illustrate this: X' pattern."""
        text = "Deutsch's thoughts on our environmental history illustrate this: Ironically, the reverse is the case and the Earth was killing us."
        attributed = draft_service.find_attributed_speech(text)
        assert len(attributed) == 1
        assert attributed[0]['speaker'] == 'Deutsch'
        assert 'Ironically' in attributed[0]['content']
        assert attributed[0]['pattern_type'] == 'colon_extended'

    def test_finds_as_prefix_attribution(self):
        """Test detection of 'As Speaker puts it, X' pattern."""
        text = "As Deutsch puts it, we are a player—the player—in the universe."
        attributed = draft_service.find_attributed_speech(text)
        assert len(attributed) == 1
        assert attributed[0]['speaker'] == 'Deutsch'
        assert 'we are a player' in attributed[0]['content']
        assert attributed[0]['pattern_type'] == 'as_prefix'

    def test_finds_various_verbs(self):
        """Test detection with different attribution verbs."""
        verbs = ['argues', 'says', 'notes', 'observes', 'warns', 'asserts', 'claims', 'explains']
        for verb in verbs:
            text = f"Deutsch {verb}, this is important content here."
            attributed = draft_service.find_attributed_speech(text)
            assert len(attributed) == 1, f"Failed to detect verb: {verb}"

    def test_finds_ing_verb_forms(self):
        """Test detection with -ing verb forms (participial patterns)."""
        verbs = ['arguing', 'saying', 'noting', 'observing', 'warning', 'explaining']
        for verb in verbs:
            # Participial pattern: "Speaker verbs, verb_ing content."
            text = f"Deutsch agrees with this point, {verb} this is important content here."
            attributed = draft_service.find_attributed_speech(text)
            assert len(attributed) >= 1, f"Failed to detect -ing verb: {verb}"
            assert any(a['pattern_type'] == 'participial' for a in attributed), f"No participial pattern for {verb}"

    def test_validates_against_transcript(self):
        """Test validation of attributed content against transcript."""
        transcript = "Knowledge is power and progress is possible through understanding."

        # Valid content (is in transcript)
        result = draft_service.validate_attributed_content('Knowledge is power', transcript)
        assert result['valid'] is True

        # Invalid content (not in transcript)
        result = draft_service.validate_attributed_content('the universe is a simulation', transcript)
        assert result['valid'] is False
        assert result['reason'] == 'not_in_transcript'

    def test_deletes_invalid_attribution_hard(self):
        """Test that invalid attributions DELETE entire sentence (hard enforcement)."""
        transcript = "Knowledge is power."
        text = (
            "First sentence here.\n\n"
            "Deutsch argues, the universe is fundamentally unpredictable.\n\n"
            "Last sentence here."
        )
        result, report = draft_service.enforce_attributed_speech(text, transcript)
        # HARD enforcement: entire invalid sentence is DELETED
        assert "Deutsch argues" not in result
        assert "universe is fundamentally unpredictable" not in result  # Content also gone
        assert "First sentence" in result
        assert "Last sentence" in result
        assert report['invalid_deleted'] == 1

    def test_preserves_valid_attribution_and_wraps_quotes(self):
        """Test that valid attributions are preserved AND wrapped in quotes if not already."""
        transcript = "Knowledge is power and progress is always possible."
        text = "Deutsch argues, knowledge is power and progress is always possible."
        result, report = draft_service.enforce_attributed_speech(text, transcript)
        # Valid attribution preserved with quotes wrapped
        assert "Deutsch argues" in result
        assert report['valid_converted'] == 1
        assert report['invalid_deleted'] == 0
        # Should have quotes around the content
        assert '"knowledge is power' in result or '"Knowledge is power' in result

    def test_handles_full_name(self):
        """Test detection with full name like 'David Deutsch'."""
        text = "David Deutsch argues, the scientific method enables unlimited progress."
        attributed = draft_service.find_attributed_speech(text)
        assert len(attributed) == 1
        assert attributed[0]['speaker'] == 'David Deutsch'

    def test_hard_enforcement_deletes_invalid_argues_that(self):
        """Test that 'Deutsch argues that X' with invalid X is entirely deleted."""
        transcript = "Knowledge is power."
        text = "Deutsch argues that the universe is fundamentally creative."
        result, report = draft_service.enforce_attributed_speech(text, transcript)
        # HARD: entire sentence deleted, not just attribution stripped
        assert "Deutsch argues" not in result
        assert "universe is fundamentally creative" not in result
        assert report['invalid_deleted'] == 1

    def test_handles_argues_that_pattern(self):
        """Test detection of 'Speaker argues that X' pattern."""
        text = "Deutsch argues that knowledge enables unlimited progress."
        attributed = draft_service.find_attributed_speech(text)
        assert len(attributed) == 1
        assert attributed[0]['speaker'] == 'Deutsch'

    def test_hard_enforcement_no_leftover_content(self):
        """Test that invalid X leaves no 'cosmic architects'-type orphan content."""
        transcript = "The scientific method works."
        text = (
            "The Enlightenment was important.\n\n"
            "Deutsch notes, we are cosmic architects shaping the future.\n\n"
            "Science continues to progress."
        )
        result, report = draft_service.enforce_attributed_speech(text, transcript)
        # "cosmic architects" content should be entirely gone
        assert "cosmic architects" not in result
        assert "shaping the future" not in result
        # Other sentences preserved
        assert "Enlightenment was important" in result
        assert "Science continues" in result

    def test_valid_attribution_without_quotes_gets_quoted(self):
        """Test that valid X without quotes gets wrapped in quotes."""
        transcript = "progress is always possible through knowledge"
        text = "Deutsch says, progress is always possible through knowledge."
        result, report = draft_service.enforce_attributed_speech(text, transcript)
        # Should wrap content in quotes
        assert 'Deutsch says, "progress is always possible' in result or 'Deutsch says, "Progress is always possible' in result
        assert report['valid_converted'] == 1

    def test_already_quoted_attribution_not_double_processed(self):
        """Test that already quoted attribution is not detected for re-processing.

        Already-quoted content is treated as a direct quote and doesn't need
        attribution enforcement - it's already in the correct format.
        """
        transcript = "progress is always possible"
        text = 'Deutsch says, "progress is always possible."'
        result, report = draft_service.enforce_attributed_speech(text, transcript)
        # Already quoted - should be preserved as-is (not re-detected)
        assert 'Deutsch says, "progress is always possible' in result
        # Attribution patterns only match unquoted content, so total_found is 0
        assert report['total_found'] == 0

    def test_mixed_punctuation_colon(self):
        """Test attribution with colon: 'Deutsch: X'."""
        transcript = "the universe follows physical laws"
        text = "Deutsch: the universe follows physical laws."
        result, report = draft_service.enforce_attributed_speech(text, transcript)
        assert report['valid_converted'] >= 1 or report['total_found'] >= 1

    def test_mixed_punctuation_em_dash(self):
        """Test attribution with em-dash: 'Deutsch argues—X'."""
        transcript = "knowledge is limitless"
        text = "Deutsch argues—knowledge is limitless."
        result, report = draft_service.enforce_attributed_speech(text, transcript)
        # Should detect and validate
        assert report['total_found'] >= 1


class TestGrammarRepair:
    """Tests for grammar repair and pronoun orphan detection."""

    def test_removes_pronoun_orphan_it(self):
        """Test removal of orphaned 'It grows...' paragraph."""
        text = (
            "## Chapter 2: Human Potential\n\n"
            "It grows and changes, much like scientific knowledge.\n\n"
            "The Enlightenment sparked new ideas."
        )
        result = draft_service.repair_grammar_fragments(text)
        assert "It grows and changes" not in result
        assert "Enlightenment sparked" in result
        assert "## Chapter 2" in result

    def test_removes_pronoun_orphan_this(self):
        """Test removal of orphaned 'This challenges...' paragraph."""
        text = (
            "## Chapter 1\n\n"
            "This challenges the traditional view of progress.\n\n"
            "Knowledge expands over time."
        )
        result = draft_service.repair_grammar_fragments(text)
        assert "This challenges" not in result
        assert "Knowledge expands" in result

    def test_preserves_pronoun_with_antecedent(self):
        """Test that pronouns with clear antecedents are preserved."""
        text = (
            "The Enlightenment was a major intellectual movement that changed everything.\n\n"
            "This movement challenged traditional beliefs and promoted reason."
        )
        result = draft_service.repair_grammar_fragments(text)
        # "This movement" has a clear antecedent ("The Enlightenment... movement")
        # so it should be preserved
        assert "This movement" in result

    def test_removes_orphan_after_heading(self):
        """Test removal of pronoun orphan right after a heading."""
        text = (
            "## New Section\n\n"
            "It reflects a fundamental shift in thinking.\n\n"
            "The scientific method emerged during this period."
        )
        result = draft_service.repair_grammar_fragments(text)
        # Directly after a heading with no content - definitely orphaned
        assert "It reflects" not in result
        assert "scientific method" in result

    def test_removes_lowercase_fragment(self):
        """Test removal of fragments starting with lowercase."""
        text = (
            "First proper sentence here.\n\n"
            "and the universe keeps expanding.\n\n"
            "Last proper sentence here."
        )
        result = draft_service.repair_grammar_fragments(text)
        assert "and the universe" not in result
        assert "First proper" in result
        assert "Last proper" in result

    def test_preserves_valid_content(self):
        """Test that valid content is preserved."""
        text = (
            "## Chapter 1: The Impact\n\n"
            "The Enlightenment marked a turning point in human history.\n\n"
            "David Deutsch argues that knowledge is infinite.\n\n"
            "This perspective challenges old assumptions about human limits."
        )
        result = draft_service.repair_grammar_fragments(text)
        # All content should be preserved - no orphans
        assert "Enlightenment marked" in result
        assert "David Deutsch argues" in result
        assert "This perspective" in result


class TestAnachronismFilter:
    """Tests for anachronism keyword filtering in Ideas Edition."""

    def test_removes_paragraph_with_climate_change(self):
        """Test removal of paragraph with 'climate change' and no quote."""
        text = (
            "## Chapter 1\n\n"
            "The Enlightenment changed everything.\n\n"
            "As we face climate change and other modern challenges, these ideas remain relevant.\n\n"
            "Knowledge continues to grow."
        )
        result, report = draft_service.filter_anachronism_paragraphs(text)
        assert "climate change" not in result
        assert "Enlightenment changed" in result
        assert "Knowledge continues" in result
        assert report["paragraphs_removed"] == 1

    def test_removes_paragraph_with_social_media(self):
        """Test removal of paragraph with 'social media' and no quote."""
        text = (
            "## Chapter 2\n\n"
            "In today's world of social media, information spreads quickly.\n\n"
            "The scientific method offers clarity."
        )
        result, report = draft_service.filter_anachronism_paragraphs(text)
        assert "social media" not in result
        assert "scientific method" in result
        assert report["paragraphs_removed"] == 1

    def test_preserves_paragraph_with_quote_despite_keyword(self):
        """Test that paragraphs with anachronism keywords are preserved if they have a quote."""
        text = (
            "## Chapter 1\n\n"
            'Deutsch notes, "The internet has changed how we share knowledge."\n\n'
            "This reflects the power of technology."
        )
        result, report = draft_service.filter_anachronism_paragraphs(text)
        # Should be preserved because it has a quote
        assert "internet" in result
        assert report["paragraphs_removed"] == 0

    def test_removes_moralizing_language(self):
        """Test removal of moralizing without evidence."""
        text = (
            "## Chapter 3\n\n"
            "It is our moral duty to protect the environment.\n\n"
            "The laws of physics are universal."
        )
        result, report = draft_service.filter_anachronism_paragraphs(text)
        assert "moral duty" not in result
        assert "laws of physics" in result
        assert report["paragraphs_removed"] == 1

    def test_preserves_headings(self):
        """Test that headings are always preserved even with keywords."""
        text = (
            "## Chapter 1: Contemporary Issues\n\n"
            "The Enlightenment was transformative."
        )
        result, report = draft_service.filter_anachronism_paragraphs(text)
        # Heading preserved even with "contemporary"
        assert "## Chapter 1: Contemporary Issues" in result
        assert report["paragraphs_removed"] == 0

    def test_case_insensitive_matching(self):
        """Test that keyword matching is case-insensitive."""
        text = (
            "## Chapter 1\n\n"
            "CLIMATE CHANGE threatens our future.\n\n"
            "Progress is possible."
        )
        result, report = draft_service.filter_anachronism_paragraphs(text)
        assert "CLIMATE CHANGE" not in result
        assert "Progress is possible" in result
        assert report["paragraphs_removed"] == 1

    def test_multiple_paragraphs_removed(self):
        """Test removal of multiple paragraphs with different keywords."""
        text = (
            "## Chapter 1\n\n"
            "Knowledge grows infinitely.\n\n"
            "In today's world, we face new challenges.\n\n"
            "Social media has transformed communication.\n\n"
            "The scientific method endures."
        )
        result, report = draft_service.filter_anachronism_paragraphs(text)
        assert "today's world" not in result
        assert "Social media" not in result
        assert "Knowledge grows" in result
        assert "scientific method" in result
        assert report["paragraphs_removed"] == 2

    def test_report_includes_details(self):
        """Test that the report includes details about removed paragraphs."""
        text = (
            "## Chapter 1\n\n"
            "Good paragraph here.\n\n"
            "In the 21st century, things have changed dramatically.\n\n"
            "Another good paragraph."
        )
        result, report = draft_service.filter_anachronism_paragraphs(text)
        assert report["paragraphs_removed"] == 1
        assert len(report["removed_details"]) == 1
        assert "21st century" in report["removed_details"][0]["keyword"]


class TestWhitespaceRepair:
    """Tests for whitespace repair after deletions."""

    def test_fixes_missing_space_after_quote(self):
        """Test fixing missing space after closing quote."""
        text = 'He said, "This is wrong."This is the next sentence.'
        result = draft_service.repair_whitespace(text)
        assert '." This' in result

    def test_fixes_missing_space_after_smart_quote(self):
        """Test fixing missing space after smart closing quote."""
        text = 'He said, "This is wrong.\u201dThis is next.'
        result = draft_service.repair_whitespace(text)
        assert '\u201d This' in result

    def test_fixes_leading_space_on_paragraph(self):
        """Test removing leading spaces from paragraphs."""
        text = "First paragraph.\n\n The second has leading space."
        result = draft_service.repair_whitespace(text)
        assert "\n\nThe second" in result

    def test_normalizes_multiple_blank_lines(self):
        """Test normalizing multiple blank lines."""
        text = "First paragraph.\n\n\n\nSecond paragraph."
        result = draft_service.repair_whitespace(text)
        assert text.count('\n\n\n') == 1  # Original has it
        assert result.count('\n\n\n') == 0  # Result doesn't

    def test_normalizes_multiple_spaces(self):
        """Test normalizing multiple spaces."""
        text = "This has   multiple   spaces."
        result = draft_service.repair_whitespace(text)
        assert "   " not in result
        assert "multiple spaces" in result

    def test_preserves_valid_formatting(self):
        """Test that valid formatting is preserved."""
        text = '## Chapter 1\n\nDeutsch argues, "This is valid." The next sentence follows.'
        result = draft_service.repair_whitespace(text)
        assert result == text


class TestMarkdownHeaderNormalizer:
    """Tests for normalize_markdown_headers - blank line before headers."""

    def test_inserts_blank_line_before_key_excerpts_draft21(self):
        """REGRESSION Draft 21: Missing blank line before ### Key Excerpts."""
        text = '''## Chapter 1: The Impact

Some prose here.
### Key Excerpts

> "Quote"
> — Speaker'''

        result, report = draft_service.normalize_markdown_headers(text)

        # Should have blank line before ### Key Excerpts
        assert "\n\n### Key Excerpts" in result
        assert report["blank_lines_inserted"] >= 1

    def test_inserts_blank_line_before_core_claims_draft21(self):
        """REGRESSION Draft 21: Missing blank line before ### Core Claims."""
        text = '''### Key Excerpts

> "Quote"
> — Speaker
### Core Claims

- **Claim**: "Support."'''

        result, report = draft_service.normalize_markdown_headers(text)

        # Should have blank line before ### Core Claims
        assert "\n\n### Core Claims" in result
        assert report["blank_lines_inserted"] >= 1

    def test_inserts_blank_line_before_chapter_header(self):
        """Missing blank line before ## Chapter should be fixed."""
        text = '''### Core Claims

- **Claim**: "Support."
## Chapter 2: Human Potential

More prose here.'''

        result, report = draft_service.normalize_markdown_headers(text)

        # Should have blank line before ## Chapter 2
        assert "\n\n## Chapter 2" in result
        assert report["blank_lines_inserted"] >= 1

    def test_preserves_already_correct_formatting(self):
        """Already correct formatting should not be changed."""
        text = '''## Chapter 1: The Impact

Some prose here.

### Key Excerpts

> "Quote"
> — Speaker

### Core Claims

- **Claim**: "Support."

## Chapter 2: Human Potential

More prose here.'''

        result, report = draft_service.normalize_markdown_headers(text)

        # No changes needed
        assert report["blank_lines_inserted"] == 0
        # Content should be unchanged (after triple newline normalization)
        assert "Some prose here.\n\n### Key Excerpts" in result

    def test_does_not_create_triple_newlines(self):
        """Should not create triple newlines when fixing."""
        text = '''Some prose.

### Key Excerpts'''

        result, report = draft_service.normalize_markdown_headers(text)

        # Should not have triple newlines
        assert "\n\n\n" not in result


class TestHeShePronounOrphan:
    """Tests for He/She pronoun orphan detection."""

    def test_removes_orphan_he_after_heading(self):
        """Test removal of 'He envisions...' orphan after heading."""
        text = (
            "## Chapter 2\n\n"
            "He envisions a future where humanity thrives.\n\n"
            "The scientific method offers clarity."
        )
        result = draft_service.repair_grammar_fragments(text)
        assert "He envisions" not in result
        assert "scientific method" in result

    def test_removes_orphan_she_argues(self):
        """Test removal of 'She argues...' orphan."""
        text = (
            "## Section\n\n"
            "She argues that progress is inevitable.\n\n"
            "Knowledge continues to grow."
        )
        result = draft_service.repair_grammar_fragments(text)
        assert "She argues" not in result
        assert "Knowledge continues" in result

    def test_preserves_he_with_antecedent(self):
        """Test that He is preserved when previous paragraph provides context."""
        text = (
            "David Deutsch is a physicist known for his work on quantum computing and the philosophy of science.\n\n"
            "He argues that progress is possible through the creation of knowledge."
        )
        result = draft_service.repair_grammar_fragments(text)
        # Should be preserved because previous paragraph establishes "David Deutsch"
        assert "He argues" in result

    def test_removes_mid_sentence_orphan_he(self):
        """Test removal of mid-sentence 'He challenges...' orphan."""
        text = (
            "Human society has evolved with knowledge. Scientific inquiry deepens understanding. "
            "He challenges the common belief that humility protects us."
        )
        result = draft_service.repair_grammar_fragments(text)
        assert "He challenges" not in result
        assert "Scientific inquiry deepens understanding." in result

    def test_removes_mid_sentence_orphan_he_with_comma(self):
        """Test removal of mid-sentence 'He states, X' orphan with comma after verb."""
        text = (
            "Knowledge and technology can change our lives. "
            'He states, "It has only been since the invention of human technology."'
        )
        result = draft_service.repair_grammar_fragments(text)
        assert "He states" not in result
        assert "change our lives." in result

    def test_removes_mid_sentence_orphan_she(self):
        """Test removal of mid-sentence 'She argues...' orphan."""
        text = (
            "The Enlightenment changed everything. She argues that progress is inevitable. "
            "This led to major advancements."
        )
        result = draft_service.repair_grammar_fragments(text)
        assert "She argues" not in result
        assert "Enlightenment changed everything." in result

    def test_preserves_mid_sentence_named_attribution(self):
        """Test that named attributions mid-sentence are preserved."""
        text = (
            "The Enlightenment changed everything. Deutsch argues that progress is inevitable."
        )
        result = draft_service.repair_grammar_fragments(text)
        # Named attributions should be preserved (handled by attribution enforcement instead)
        assert "Deutsch argues" in result


class TestFixUnquotedExcerpts:
    """Tests for fixing unquoted block quotes and Core Claims."""

    def test_fixes_unquoted_block_quote(self):
        """Test wrapping unquoted block quote in quotation marks."""
        text = (
            "### Key Excerpts\n\n"
            "> Before the Enlightenment, there was practically nobody.\n"
            "> — David Deutsch"
        )
        result, report = draft_service.fix_unquoted_excerpts(text)
        assert '> "Before the Enlightenment, there was practically nobody."' in result
        assert report["fixes_made"] == 1

    def test_preserves_already_quoted_block_quote(self):
        """Test that already quoted block quotes are preserved."""
        text = (
            "### Key Excerpts\n\n"
            '> "This is already quoted."\n'
            "> — David Deutsch"
        )
        result, report = draft_service.fix_unquoted_excerpts(text)
        assert '> "This is already quoted."' in result
        assert report["fixes_made"] == 0

    def test_fixes_unquoted_core_claim(self):
        """Test wrapping unquoted Core Claim in quotation marks."""
        text = (
            "### Core Claims\n\n"
            "- **Wisdom evolves**: the truth is that wisdom is limitless."
        )
        result, report = draft_service.fix_unquoted_excerpts(text)
        assert '- **Wisdom evolves**: "The truth is that wisdom is limitless."' in result
        assert report["fixes_made"] == 1

    def test_preserves_already_quoted_core_claim(self):
        """Test that already quoted Core Claims are preserved."""
        text = (
            "### Core Claims\n\n"
            '- **Wisdom evolves**: "The truth is that wisdom is limitless."'
        )
        result, report = draft_service.fix_unquoted_excerpts(text)
        assert '- **Wisdom evolves**: "The truth is that wisdom is limitless."' in result
        assert report["fixes_made"] == 0

    def test_skips_attribution_lines(self):
        """Test that attribution lines (— Speaker) are not modified."""
        text = "> — David Deutsch"
        result, report = draft_service.fix_unquoted_excerpts(text)
        assert result == text
        assert report["fixes_made"] == 0

    def test_handles_mixed_content(self):
        """Test handling mix of quoted and unquoted content."""
        text = (
            "### Key Excerpts\n\n"
            '> "Already quoted passage."\n'
            "> — David Deutsch\n\n"
            "> Unquoted passage here.\n"
            "> — David Deutsch\n\n"
            "### Core Claims\n\n"
            '- **Claim one**: "Already quoted."\n'
            "- **Claim two**: not quoted yet."
        )
        result, report = draft_service.fix_unquoted_excerpts(text)
        assert '> "Unquoted passage here."' in result
        assert '- **Claim two**: "Not quoted yet."' in result
        assert report["fixes_made"] == 2


class TestValidateCoreClaimsStructure:
    """Tests for validate_core_claims_structure - structural safety net."""

    def test_drops_claim_with_missing_closing_quote(self):
        """Test that claims without closing quote are dropped."""
        text = (
            "## Chapter 1\n\n"
            "### Core Claims\n\n"
            '- **Valid claim**: "This is properly quoted."\n'
            '- **Broken claim**: "This quote has no closing quote\n'
            "\n## Chapter 2"
        )

        result, report = draft_service.validate_core_claims_structure(text)

        assert "Valid claim" in result
        assert "Broken claim" not in result
        assert report["dropped_count"] == 1
        assert report["dropped"][0]["reason"] == "missing_closing_quote"

    def test_drops_claim_with_garbage_suffix(self):
        """Test that claims with ' choose.' garbage suffix are dropped."""
        text = (
            "## Chapter 1\n\n"
            "### Core Claims\n\n"
            '- **Valid claim**: "This is properly quoted."\n'
            '- **Corrupted claim**: "This quote has garbage choose."\n'
            "\n## Chapter 2"
        )

        result, report = draft_service.validate_core_claims_structure(text)

        assert "Valid claim" in result
        assert "Corrupted claim" not in result
        assert report["dropped_count"] == 1
        assert report["dropped"][0]["reason"] == "garbage_suffix_in_quote"

    def test_preserves_valid_claims(self):
        """Test that valid claims are preserved."""
        text = (
            "## Chapter 1\n\n"
            "### Core Claims\n\n"
            '- **First claim**: "Valid quote one."\n'
            '- **Second claim**: "Valid quote two."\n'
            "\n## Chapter 2"
        )

        result, report = draft_service.validate_core_claims_structure(text)

        assert "First claim" in result
        assert "Second claim" in result
        assert report["dropped_count"] == 0

    def test_handles_empty_core_claims(self):
        """Test that empty Core Claims section is handled."""
        text = (
            "## Chapter 1\n\n"
            "### Core Claims\n\n"
            "*No fully grounded claims available.*\n"
            "\n## Chapter 2"
        )

        result, report = draft_service.validate_core_claims_structure(text)

        assert "*No fully grounded claims available.*" in result
        assert report["dropped_count"] == 0


class TestDropClaimsWithInvalidQuotes:
    """Tests for drop_claims_with_invalid_quotes - Core Claims hard gate."""

    def test_drops_claim_with_fabricated_quote(self):
        """Test that claims with fabricated quotes are dropped entirely."""
        transcript = "Wisdom is limitless. The truth is clear."
        text = (
            "## Chapter 1\n\n"
            "Some prose here.\n\n"
            "### Core Claims\n\n"
            '- **Claim about wisdom**: "Wisdom is limitless."\n'
            '- **Fabricated claim**: "This quote does not exist in transcript."\n'
            '- **Another valid claim**: "The truth is clear."'
        )
        result, report = draft_service.drop_claims_with_invalid_quotes(text, transcript)

        # Fabricated claim should be dropped
        assert "Fabricated claim" not in result
        assert "This quote does not exist" not in result

        # Valid claims should remain
        assert "Claim about wisdom" in result
        assert "Wisdom is limitless" in result
        assert "Another valid claim" in result
        assert "The truth is clear" in result

        # Report should show 1 dropped
        assert report["dropped_count"] == 1
        assert report["dropped_claims"][0]["reason"] == "not_in_transcript"

    def test_preserves_all_valid_claims(self):
        """Test that all claims with valid quotes are preserved."""
        transcript = "Wisdom is limitless. Knowledge grows forever."
        text = (
            "### Core Claims\n\n"
            '- **First claim**: "Wisdom is limitless."\n'
            '- **Second claim**: "Knowledge grows forever."'
        )
        result, report = draft_service.drop_claims_with_invalid_quotes(text, transcript)

        assert "First claim" in result
        assert "Second claim" in result
        assert report["dropped_count"] == 0

    def test_handles_empty_section_after_all_dropped(self):
        """Test placeholder is added when all claims are dropped."""
        transcript = "This is the only valid text."
        text = (
            "### Core Claims\n\n"
            '- **Fabricated one**: "Not in transcript."\n'
            '- **Fabricated two**: "Also not in transcript."\n\n'
            "### Key Excerpts"
        )
        result, report = draft_service.drop_claims_with_invalid_quotes(text, transcript)

        assert report["dropped_count"] == 2
        assert "No fully grounded claims available" in result
        # Key Excerpts section should remain
        assert "### Key Excerpts" in result

    def test_handles_multiline_bullet(self):
        """Test that multi-line bullets are dropped completely."""
        transcript = "Wisdom is limitless."
        text = (
            "### Core Claims\n\n"
            '- **A valid claim**: "Wisdom is limitless."\n'
            '- **An invalid multi-line claim**: "This is fabricated"\n'
            "  and continues on the next line\n"
            "  with more text.\n"
            '- **Another valid**: "Wisdom is limitless."'
        )
        result, report = draft_service.drop_claims_with_invalid_quotes(text, transcript)

        # Invalid multi-line bullet should be entirely gone
        assert "invalid multi-line claim" not in result
        assert "continues on the next line" not in result
        assert "with more text" not in result

        # Valid claims should remain
        assert "A valid claim" in result
        assert "Another valid" in result
        assert report["dropped_count"] == 1

    def test_only_affects_core_claims_section(self):
        """Test that narrative prose with invalid quotes is NOT affected."""
        transcript = "Wisdom is limitless."
        text = (
            "## Chapter 1\n\n"
            'He said "This is fabricated" but we continue.\n\n'
            "### Core Claims\n\n"
            '- **Valid claim**: "Wisdom is limitless."\n\n'
            "### Key Excerpts\n\n"
            '> "Also fabricated but in Key Excerpts"\n'
            "> — Speaker"
        )
        result, report = draft_service.drop_claims_with_invalid_quotes(text, transcript)

        # Core Claims with valid quote remains
        assert "Valid claim" in result

        # Narrative prose NOT touched (even if it has invalid quotes)
        assert "This is fabricated" in result

        # Key Excerpts NOT touched
        assert "Also fabricated but in Key Excerpts" in result

        assert report["dropped_count"] == 0

    def test_drops_claim_with_ellipsis_in_quote(self):
        """Test that claims with ellipsis quotes are dropped."""
        transcript = "Wisdom is limitless and grows forever."
        text = (
            "### Core Claims\n\n"
            '- **Truncated claim**: "Wisdom is limitless... and grows forever."'
        )
        result, report = draft_service.drop_claims_with_invalid_quotes(text, transcript)

        assert "Truncated claim" not in result
        assert report["dropped_count"] == 1
        assert report["dropped_claims"][0]["reason"] == "contains_ellipsis"

    def test_handles_multiple_chapters(self):
        """Test that function works across multiple chapters."""
        transcript = "Valid quote one. Valid quote two."
        text = (
            "## Chapter 1\n\n"
            "### Core Claims\n\n"
            '- **Valid in ch1**: "Valid quote one."\n'
            '- **Invalid in ch1**: "Fabricated for chapter one."\n\n'
            "## Chapter 2\n\n"
            "### Core Claims\n\n"
            '- **Valid in ch2**: "Valid quote two."\n'
            '- **Invalid in ch2**: "Fabricated for chapter two."'
        )
        result, report = draft_service.drop_claims_with_invalid_quotes(text, transcript)

        # Valid claims remain in both chapters
        assert "Valid in ch1" in result
        assert "Valid in ch2" in result

        # Invalid claims dropped in both chapters
        assert "Invalid in ch1" not in result
        assert "Invalid in ch2" not in result

        assert report["dropped_count"] == 2

    def test_preserves_claim_without_quote(self):
        """Test that claims without any quote (edge case) are preserved."""
        transcript = "Some text."
        text = (
            "### Core Claims\n\n"
            "- **A claim with no quote**: This has no quotation marks."
        )
        result, report = draft_service.drop_claims_with_invalid_quotes(text, transcript)

        # Claim without quote should be preserved (can't validate what's not quoted)
        assert "A claim with no quote" in result
        assert report["dropped_count"] == 0


class TestDropExcerptsWithInvalidQuotes:
    """Tests for drop_excerpts_with_invalid_quotes - Key Excerpts hard gate."""

    def test_drops_excerpt_with_fabricated_quote(self):
        """Test that excerpts with fabricated quotes are dropped entirely."""
        transcript = "Wisdom is limitless. The truth is clear."
        text = (
            "### Key Excerpts\n\n"
            '> "Wisdom is limitless."\n'
            "> — David Deutsch\n\n"
            '> "This quote does not exist in transcript."\n'
            "> — David Deutsch\n\n"
            '> "The truth is clear."\n'
            "> — David Deutsch"
        )
        result, report = draft_service.drop_excerpts_with_invalid_quotes(text, transcript)

        # Fabricated excerpt should be dropped (quote + attribution)
        assert "This quote does not exist" not in result

        # Valid excerpts should remain
        assert "Wisdom is limitless" in result
        assert "The truth is clear" in result

        assert report["dropped_count"] == 1
        assert report["dropped_excerpts"][0]["reason"] == "not_in_transcript"

    def test_drops_excerpt_with_unknown_attribution(self):
        """Test that excerpts with Unknown attribution are dropped."""
        transcript = "Wisdom is limitless. The truth is clear."
        text = (
            "### Key Excerpts\n\n"
            '> "Wisdom is limitless."\n'
            "> — David Deutsch\n\n"
            '> "The truth is clear."\n'
            "> — Unknown"
        )
        result, report = draft_service.drop_excerpts_with_invalid_quotes(text, transcript)

        # Unknown attribution excerpt should be dropped
        assert "Unknown" not in result
        assert "The truth is clear" not in result

        # Valid excerpt should remain
        assert "Wisdom is limitless" in result
        assert "David Deutsch" in result

        assert report["dropped_count"] == 1
        assert report["dropped_excerpts"][0]["reason"] == "unknown_attribution"

    def test_preserves_all_valid_excerpts(self):
        """Test that all excerpts with valid quotes are preserved."""
        transcript = "Wisdom is limitless. Knowledge grows forever."
        text = (
            "### Key Excerpts\n\n"
            '> "Wisdom is limitless."\n'
            "> — David Deutsch\n\n"
            '> "Knowledge grows forever."\n'
            "> — David Deutsch"
        )
        result, report = draft_service.drop_excerpts_with_invalid_quotes(text, transcript)

        assert "Wisdom is limitless" in result
        assert "Knowledge grows forever" in result
        assert report["dropped_count"] == 0

    def test_handles_empty_section_after_all_dropped(self):
        """Test placeholder is added when all excerpts are dropped."""
        transcript = "This is the only valid text."
        text = (
            "### Key Excerpts\n\n"
            '> "Not in transcript."\n'
            "> — David Deutsch\n\n"
            '> "Also not in transcript."\n'
            "> — David Deutsch\n\n"
            "### Core Claims"
        )
        result, report = draft_service.drop_excerpts_with_invalid_quotes(text, transcript)

        assert report["dropped_count"] == 2
        assert "No fully grounded excerpts available" in result
        # Core Claims section should remain
        assert "### Core Claims" in result

    def test_only_affects_key_excerpts_section(self):
        """Test that narrative prose and Core Claims are NOT affected."""
        transcript = "Wisdom is limitless."
        text = (
            "## Chapter 1\n\n"
            '> "This is a block quote in narrative - fabricated"\n\n'
            "### Key Excerpts\n\n"
            '> "Wisdom is limitless."\n'
            "> — David Deutsch\n\n"
            "### Core Claims\n\n"
            '- **Claim**: "Wisdom is limitless."'
        )
        result, report = draft_service.drop_excerpts_with_invalid_quotes(text, transcript)

        # Key Excerpts with valid quote remains
        assert '> "Wisdom is limitless."' in result

        # Narrative block quote NOT touched (even if fabricated)
        assert "This is a block quote in narrative" in result

        # Core Claims NOT touched
        assert '- **Claim**: "Wisdom is limitless."' in result

        assert report["dropped_count"] == 0

    def test_drops_excerpt_with_ellipsis_in_quote(self):
        """Test that excerpts with ellipsis quotes are dropped."""
        transcript = "Wisdom is limitless and grows forever."
        text = (
            "### Key Excerpts\n\n"
            '> "Wisdom is limitless... and grows forever."\n'
            "> — David Deutsch"
        )
        result, report = draft_service.drop_excerpts_with_invalid_quotes(text, transcript)

        assert "Wisdom is limitless" not in result
        assert report["dropped_count"] == 1
        assert report["dropped_excerpts"][0]["reason"] == "contains_ellipsis"

    def test_handles_multiple_chapters(self):
        """Test that function works across multiple chapters."""
        transcript = "Valid quote one. Valid quote two."
        text = (
            "## Chapter 1\n\n"
            "### Key Excerpts\n\n"
            '> "Valid quote one."\n'
            "> — David Deutsch\n\n"
            '> "Fabricated for chapter one."\n'
            "> — David Deutsch\n\n"
            "## Chapter 2\n\n"
            "### Key Excerpts\n\n"
            '> "Valid quote two."\n'
            "> — David Deutsch\n\n"
            '> "Fabricated for chapter two."\n'
            "> — David Deutsch"
        )
        result, report = draft_service.drop_excerpts_with_invalid_quotes(text, transcript)

        # Valid excerpts remain in both chapters
        assert "Valid quote one" in result
        assert "Valid quote two" in result

        # Invalid excerpts dropped in both chapters
        assert "Fabricated for chapter one" not in result
        assert "Fabricated for chapter two" not in result

        assert report["dropped_count"] == 2

    def test_handles_long_single_line_quote(self):
        """Test that long quotes on a single line are handled correctly."""
        transcript = "This is a long quote that contains many words and spans what might be a very long sentence in the original transcript."
        text = (
            "### Key Excerpts\n\n"
            '> "This is a long quote that contains many words and spans what might be a very long sentence in the original transcript."\n'
            "> — David Deutsch"
        )
        result, report = draft_service.drop_excerpts_with_invalid_quotes(text, transcript)

        # This should be preserved as valid
        assert "This is a long quote" in result
        assert report["dropped_count"] == 0

    def test_drops_excerpt_with_dash_unknown(self):
        """Test that excerpts with '- Unknown' attribution are also dropped."""
        transcript = "The truth is clear."
        text = (
            "### Key Excerpts\n\n"
            '> "The truth is clear."\n'
            "> - Unknown"
        )
        result, report = draft_service.drop_excerpts_with_invalid_quotes(text, transcript)

        # Should be dropped due to Unknown attribution
        assert "The truth is clear" not in result
        assert report["dropped_count"] == 1
        assert report["dropped_excerpts"][0]["reason"] == "unknown_attribution"


class TestVerbatimLeakGate:
    """Tests for enforce_verbatim_leak_gate - drops sentences with whitelist quote text in prose.

    PHASE 2: Now uses sentence-level dropping instead of paragraph-level to preserve
    more prose while still enforcing the verbatim leak constraint.
    """

    def test_drops_sentence_with_full_quote_preserves_others(self):
        """PHASE 2: Only the leaking sentence is dropped, other sentences preserved."""
        whitelist = ["I entirely agree with Stephen Hawking that we should hedge our bets"]
        text = """## Chapter 1

The Enlightenment changed everything.

Colonization becomes a pressing topic. I entirely agree with Stephen Hawking that we should hedge our bets by moving away from Earth. This is important for survival.

### Key Excerpts

> "I entirely agree with Stephen Hawking that we should hedge our bets"
> — David Deutsch (GUEST)"""

        result, report = draft_service.enforce_verbatim_leak_gate(text, whitelist)

        # Extract prose section (before Key Excerpts)
        prose_section = result.split('### Key Excerpts')[0]

        # Leaking sentence should be dropped from prose
        assert "I entirely agree with Stephen Hawking that we should hedge our bets by moving" not in prose_section
        # But other sentences in same paragraph should be preserved
        assert "Colonization becomes a pressing topic" in prose_section
        assert "This is important for survival" in prose_section
        # Key Excerpts should still be preserved (quote is allowed there)
        assert "Key Excerpts" in result
        assert report["sentences_dropped"] == 1
        assert report["paragraphs_dropped"] == 0  # Paragraph preserved with remaining sentences

    def test_drops_sentence_with_substring_match(self):
        """Sentence containing significant substring of whitelist quote is dropped."""
        whitelist = ["The truth of the matter is that wisdom, like scientific knowledge, is also limitless"]
        text = """## Chapter 1

The Enlightenment sparked change.

Deutsch argues that wisdom, like scientific knowledge, is also limitless and ever-growing. Other ideas matter too.

### Key Excerpts"""

        result, report = draft_service.enforce_verbatim_leak_gate(text, whitelist, min_match_len=25)

        # Leaking sentence should be dropped
        assert "wisdom, like scientific knowledge" not in result
        # Other sentence preserved
        assert "Other ideas matter too" in result
        assert report["sentences_dropped"] == 1

    def test_drops_sentence_with_verbatim_plus_he_says_draft17(self):
        """REGRESSION Draft 17: Verbatim quote with ', he says.' suffix must be caught.

        Draft 17 had this exact pattern:
        'I entirely agree with Stephen Hawking...and so on, he says.'
        This is the whitelist quote with a suffix attribution - still a verbatim leak.

        PHASE 2: Now only the leaking sentence is dropped, other sentences preserved.
        """
        whitelist = [
            "I entirely agree with Stephen Hawking that we should hedge our bets by moving away from the Earth and colonizing the solar system and then the galaxy and so on"
        ]
        text = """## Chapter 2: Human Potential and the Universe

Deutsch sees the cosmos as a vast frontier that humanity should actively explore. I entirely agree with Stephen Hawking that we should hedge our bets by moving away from the Earth and colonizing the solar system and then the galaxy and so on, he says. Such endeavors reflect the core of human potential.

### Key Excerpts

> "I entirely agree with Stephen Hawking that we should hedge our bets by moving away from the Earth and colonizing the solar system and then the galaxy and so on."
> — David Deutsch (GUEST)"""

        result, report = draft_service.enforce_verbatim_leak_gate(text, whitelist)

        # Extract prose section (before Key Excerpts)
        prose_section = result.split('### Key Excerpts')[0]

        # Leaking sentence should be dropped from prose
        assert "I entirely agree with Stephen Hawking that we should hedge" not in prose_section
        # But other sentences in same paragraph should be preserved
        assert "Deutsch sees the cosmos" in prose_section
        assert "Such endeavors reflect" in prose_section
        # Key Excerpts should be preserved (quote is allowed there)
        assert "Key Excerpts" in result
        assert '> "I entirely agree' in result
        assert report["sentences_dropped"] == 1
        assert report["paragraphs_dropped"] == 0  # Paragraph preserved

    def test_preserves_key_excerpts_with_whitelist_text(self):
        """Key Excerpts section is allowed to contain whitelist quote text."""
        whitelist = ["This is a valid quote from the transcript"]
        text = """## Chapter 1

Clean prose here.

### Key Excerpts

> "This is a valid quote from the transcript"
> — Speaker (GUEST)

### Core Claims"""

        result, report = draft_service.enforce_verbatim_leak_gate(text, whitelist)

        # Key Excerpts should be preserved
        assert "This is a valid quote from the transcript" in result
        assert report["sentences_dropped"] == 0
        assert report["paragraphs_dropped"] == 0

    def test_preserves_core_claims_with_whitelist_text(self):
        """Core Claims section is allowed to contain whitelist quote text."""
        whitelist = ["Knowledge is infinite"]
        text = """## Chapter 1

### Core Claims

- **Claim**: Knowledge grows forever. "Knowledge is infinite"

### Key Excerpts"""

        result, report = draft_service.enforce_verbatim_leak_gate(text, whitelist)

        # Core Claims should be preserved
        assert "Knowledge is infinite" in result
        assert report["sentences_dropped"] == 0
        assert report["paragraphs_dropped"] == 0

    def test_preserves_clean_prose(self):
        """Prose without whitelist text is preserved."""
        whitelist = ["Specific quote text here"]
        text = """## Chapter 1

This is clean prose that doesn't contain any whitelist quotes.

The ideas are paraphrased in original language.

### Key Excerpts"""

        result, report = draft_service.enforce_verbatim_leak_gate(text, whitelist)

        # Clean prose should be preserved
        assert "clean prose" in result
        assert "paraphrased in original language" in result
        assert report["sentences_dropped"] == 0
        assert report["paragraphs_dropped"] == 0

    def test_catches_short_verbatim_leak_12_chars(self):
        """REGRESSION: 12-char threshold catches shorter verbatim leaks."""
        # "how totally—" is 12 chars and should be detected
        whitelist = ["you're grossly underestimating how bad the past was, how totally—"]
        text = """## Chapter 1

Looking back, we see a stark reality: you're grossly underestimating how bad the past was, how totally— Deutsch's acknowledgment of past suffering matters. History shows progress.

### Key Excerpts"""

        result, report = draft_service.enforce_verbatim_leak_gate(text, whitelist, min_match_len=12)

        # Leaking sentence should be dropped
        assert "how totally—" not in result
        # Other sentence preserved
        assert "History shows progress" in result
        assert report["sentences_dropped"] >= 1

    def test_drops_paragraph_when_all_sentences_leak(self):
        """PHASE 2: Paragraph dropped when all its sentences contain leaks."""
        whitelist = [
            "wisdom is limitless",
            "knowledge grows forever"
        ]
        text = """## Chapter 1

Clean prose before.

Wisdom is limitless according to the view. Knowledge grows forever in this framework.

Clean prose after.

### Key Excerpts"""

        result, report = draft_service.enforce_verbatim_leak_gate(text, whitelist, min_match_len=12)

        # All sentences leaked, so paragraph dropped
        assert "Wisdom is limitless" not in result
        assert "Knowledge grows forever" not in result
        # But other paragraphs preserved
        assert "Clean prose before" in result
        assert "Clean prose after" in result
        assert report["sentences_dropped"] == 2
        assert report["paragraphs_dropped"] == 1

    def test_grammar_stitch_removes_orphan_however_at_start(self):
        """PHASE 2: Grammar stitch removes orphan 'However,' when it becomes first sentence."""
        whitelist = ["verbatim leak text here"]
        # Structure: leak is the FIRST sentence, then "However, ..." which becomes orphaned
        text = """## Chapter 1

Verbatim leak text here appears first. However, the argument continues.

### Key Excerpts"""

        result, report = draft_service.enforce_verbatim_leak_gate(text, whitelist, min_match_len=12)

        # Leaking sentence dropped
        assert "verbatim leak text here" not in result.lower()
        # "However," at paragraph start should be cleaned up -> "The argument continues"
        assert "The argument continues" in result
        # Should not have orphan "However," at start of paragraph
        assert result.count("However,") == 0
        assert report["sentences_dropped"] == 1

    def test_grammar_stitch_preserves_however_after_context(self):
        """PHASE 2: 'However,' is preserved when it follows another sentence (not orphaned)."""
        whitelist = ["verbatim leak text here"]
        text = """## Chapter 1

First context stays. Verbatim leak text here is leaked. However, this continues.

### Key Excerpts"""

        result, report = draft_service.enforce_verbatim_leak_gate(text, whitelist, min_match_len=12)

        # Leaking sentence dropped
        assert "verbatim leak text here" not in result.lower()
        # "However," is fine after "First context stays." - should be preserved
        assert "First context stays" in result
        assert "However, this continues" in result  # Preserved because it follows context
        assert report["sentences_dropped"] == 1


class TestDanglingAttributionGate:
    """Tests for enforce_dangling_attribution_gate - rewrites to indirect speech."""

    def test_rewrites_noting_comma_capital(self):
        """'noting, For ages...' is rewritten to 'noting that for ages...'."""
        text = """## Chapter 1

David Deutsch marks this period as crucial, noting, For ages, human progress crawled slowly.

### Key Excerpts"""

        result, report = draft_service.enforce_dangling_attribution_gate(text)

        assert "noting, For ages" not in result
        assert "noting that for ages" in result
        assert report["rewrites_applied"] == 1

    def test_rewrites_stating_comma_capital(self):
        """'stating, This idea...' is rewritten to 'stating that this idea...'."""
        text = """## Chapter 1

Deutsch underscores this by stating, This idea captures the essence of progress.

### Key Excerpts"""

        result, report = draft_service.enforce_dangling_attribution_gate(text)

        assert "stating, This idea" not in result
        assert "stating that this idea" in result
        assert report["rewrites_applied"] == 1

    def test_rewrites_observes_comma_capital(self):
        """'Deutsch observes, Before...' is rewritten to 'Deutsch observes that before...'."""
        text = """## Chapter 1

Deutsch observes, Before the Enlightenment, there was practically nobody who questioned slavery.

### Key Excerpts"""

        result, report = draft_service.enforce_dangling_attribution_gate(text)

        assert "observes, Before" not in result
        assert "observes that before" in result
        assert report["rewrites_applied"] == 1

    def test_rewrites_he_says_comma_capital(self):
        """'He says, This...' is rewritten to 'He says that this...'."""
        text = """## Chapter 1

He says, This idea challenges us to rethink what it means to be wise.

### Key Excerpts"""

        result, report = draft_service.enforce_dangling_attribution_gate(text)

        assert "He says, This" not in result
        assert "He says that this" in result
        assert report["rewrites_applied"] == 1

    def test_rewrites_he_cautions_comma_capital(self):
        """'He cautions, To...' is rewritten to 'He cautions that to...'."""
        text = """## Chapter 1

He cautions, To try to do that is a recipe for disaster.

### Key Excerpts"""

        result, report = draft_service.enforce_dangling_attribution_gate(text)

        assert "He cautions, To" not in result
        assert "He cautions that to" in result
        assert report["rewrites_applied"] == 1

    def test_rewrites_points_to_points_out(self):
        """'David Deutsch points, there...' becomes 'points out that there...'."""
        text = """## Chapter 1

David Deutsch points, there is only one set of laws of physics.

### Key Excerpts"""

        result, report = draft_service.enforce_dangling_attribution_gate(text)

        assert "points, there" not in result
        assert "points out that there" in result
        assert report["rewrites_applied"] == 1

    def test_rewrites_insists_comma_capital(self):
        """'Deutsch insists, The...' is rewritten to 'Deutsch insists that the...'."""
        text = """## Chapter 1

Deutsch insists, The Enlightenment ushered in a new era.

### Key Excerpts"""

        result, report = draft_service.enforce_dangling_attribution_gate(text)

        assert "insists, The" not in result
        assert "insists that the" in result
        assert report["rewrites_applied"] == 1

    def test_rewrites_lowercase_first_letter(self):
        """'Deutsch insists, because...' (lowercase) is rewritten correctly."""
        text = """## Chapter 1

Deutsch insists, because we are capable of explanatory knowledge.

Deutsch points, environments usually kill their species.

### Key Excerpts"""

        result, report = draft_service.enforce_dangling_attribution_gate(text)

        assert "insists, because" not in result
        assert "insists that because" in result
        assert "points, environments" not in result
        assert "points out that environments" in result
        assert report["rewrites_applied"] == 2

    def test_preserves_proper_attribution_with_that(self):
        """'Deutsch argues that knowledge...' (already indirect) is preserved."""
        text = """## Chapter 1

Deutsch argues that knowledge is infinite and ever-growing.

### Key Excerpts"""

        result, report = draft_service.enforce_dangling_attribution_gate(text)

        # This is already valid indirect speech
        assert "Deutsch argues that knowledge" in result
        assert report["rewrites_applied"] == 0

    def test_preserves_key_excerpts(self):
        """Key Excerpts section is never modified."""
        text = """## Chapter 1

### Key Excerpts

> "noting, For ages this was true"
> — Speaker (GUEST)"""

        result, report = draft_service.enforce_dangling_attribution_gate(text)

        # Key Excerpts content should be preserved unchanged
        assert "Key Excerpts" in result
        assert "noting, For ages" in result  # Preserved in quotes
        assert report["rewrites_applied"] == 0

    def test_preserves_clean_prose(self):
        """Clean prose without dangling patterns is preserved."""
        text = """## Chapter 1

The Enlightenment changed how we think about progress.

Knowledge grew rapidly during this period.

### Key Excerpts"""

        result, report = draft_service.enforce_dangling_attribution_gate(text)

        assert "Enlightenment changed" in result
        assert "Knowledge grew" in result
        assert report["rewrites_applied"] == 0

    def test_rewrites_extended_colon_captures_this(self):
        """'Deutsch captures, This...' is rewritten to indirect speech."""
        text = """## Chapter 1

Deutsch captures, This shift changed how people approached knowledge.

### Key Excerpts"""

        result, report = draft_service.enforce_dangling_attribution_gate(text)

        assert "captures, This" not in result
        assert "captures that this" in result
        assert report["rewrites_applied"] == 1

    def test_rewrites_suggests_comma_capital(self):
        """'Deutsch suggests, humans...' is rewritten correctly."""
        text = """## Chapter 1

Deutsch suggests, humans can decide that any pattern of behavior is best.

### Key Excerpts"""

        result, report = draft_service.enforce_dangling_attribution_gate(text)

        assert "suggests, humans" not in result
        assert "suggests that humans" in result
        assert report["rewrites_applied"] == 1

    def test_rewrites_multiple_patterns_in_document(self):
        """Multiple dangling patterns are all rewritten."""
        text = """## Chapter 1

He says, This idea challenges us.

He cautions, To try is risky.

Deutsch points, there is only one truth.

### Key Excerpts"""

        result, report = draft_service.enforce_dangling_attribution_gate(text)

        assert report["rewrites_applied"] == 3
        assert "says that this" in result
        assert "cautions that to" in result
        assert "points out that there" in result

    def test_fixes_that_this_capitalization(self):
        """REGRESSION: 'that This' is fixed to 'that this'."""
        text = """## Chapter 1

Deutsch suggests that This view opened up possibilities.

### Key Excerpts"""

        result, report = draft_service.enforce_dangling_attribution_gate(text)

        # The capitalization fixer should lowercase "This" after "that"
        assert "that This" not in result
        assert "that this" in result

    def test_removes_colon_wrapper(self):
        """REGRESSION: 'Deutsch captures this: This...' removes wrapper."""
        text = """## Chapter 1

David Deutsch captures this connection: This revolution reshaped our understanding.

### Key Excerpts"""

        result, report = draft_service.enforce_dangling_attribution_gate(text)

        # The colon wrapper should be removed
        assert "captures this connection:" not in result
        # Content should remain (starting with "This")
        assert "This revolution reshaped" in result
        assert report["rewrites_applied"] >= 1

    def test_removes_sums_it_up_colon_wrapper(self):
        """REGRESSION: 'Deutsch sums it up: The...' removes wrapper."""
        text = """## Chapter 1

Deutsch sums it up: The Enlightenment changed everything.

### Key Excerpts"""

        result, report = draft_service.enforce_dangling_attribution_gate(text)

        assert "sums it up:" not in result
        assert "The Enlightenment changed" in result

    def test_preserves_proper_nouns_after_that(self):
        """Proper nouns like 'Earth' should NOT be lowercased after 'that'."""
        text = """## Chapter 1

Deutsch argues that Earth is our home.

### Key Excerpts"""

        result, report = draft_service.enforce_dangling_attribution_gate(text)

        # "Earth" should stay capitalized (it's a proper noun)
        assert "that Earth" in result

    def test_preserves_parenthetical_attribution(self):
        """REGRESSION: Parenthetical ', Deutsch points out,' must NOT be rewritten.

        Input: 'Our surroundings, Deutsch points out, are not hospitable.'
        This is a valid parenthetical structure and must remain grammatical.
        Adding 'that' would produce broken grammar: 'points out that are'.
        """
        text = """## Chapter 1

Our natural surroundings, Deutsch points out, are not particularly hospitable.

### Key Excerpts"""

        result, report = draft_service.enforce_dangling_attribution_gate(text)

        # Must NOT contain the broken grammar "points out that are"
        assert "points out that are" not in result
        # Must preserve the valid parenthetical structure
        assert "Deutsch points out, are" in result

    def test_rewrites_introducer_but_not_parenthetical(self):
        """Introducer patterns get 'that', parenthetical ones don't."""
        text = """## Chapter 1

Deutsch points out, This is important.

Our surroundings, Deutsch notes, are hostile.

### Key Excerpts"""

        result, report = draft_service.enforce_dangling_attribution_gate(text)

        # Introducer should be rewritten
        assert "points out that this" in result
        # Parenthetical should be preserved
        assert "Deutsch notes, are" in result
        assert "notes that are" not in result

    def test_skips_as_x_notes_interpolation(self):
        """REGRESSION: 'as Deutsch notes' interpolations must NOT get 'that'.

        Input: 'Science, as Deutsch notes, is about finding laws of nature.'
        This is a valid "as X notes" interpolation where the speaker attribution
        is inserted mid-sentence. Adding 'that' would break grammar.
        """
        text = """## Chapter 1

Science, as Deutsch notes, is about finding laws of nature.

### Key Excerpts"""

        result, report = draft_service.enforce_dangling_attribution_gate(text)

        # Must NOT add 'that' to "as X notes" pattern
        assert "as Deutsch notes that" not in result
        # Must preserve the original structure
        assert "as Deutsch notes, is" in result

    def test_skips_as_x_notes_without_comma(self):
        """'as Deutsch notes' without comma should also be skipped."""
        text = """## Chapter 1

The insight, as He points out is crucial for understanding.

### Key Excerpts"""

        result, report = draft_service.enforce_dangling_attribution_gate(text)

        # Must NOT add 'that' to "as X notes" pattern
        assert "as He points out that" not in result

    def test_skips_as_x_argues_interpolation_draft16(self):
        """REGRESSION Draft 16: 'as Deutsch argues, is key' must NOT get 'that'.

        Input: 'Explanatory knowledge, as Deutsch argues, is key'
        This is a valid interpolation where the attribution is parenthetical.
        Adding 'that' would produce: 'as Deutsch argues that is key' (ungrammatical)
        """
        text = """## Chapter 1

Explanatory knowledge, as Deutsch argues, is key to human innovation and progress.

### Key Excerpts"""

        result, report = draft_service.enforce_dangling_attribution_gate(text)

        # Must NOT add 'that' to "as X argues" interpolation
        assert "as Deutsch argues that" not in result
        # Must preserve the original structure
        assert "as Deutsch argues, is" in result
        # No rewrites should have been applied
        assert report["rewrites_applied"] == 0

    def test_removes_orphan_wrapper_noting(self):
        """REGRESSION: Orphan wrappers like 'noting. This' should be cleaned up.

        When LLM drops a quote but leaves the participial verb, we get broken
        patterns like 'noting. This' or 'observing. The'. These orphan verbs
        should be removed.
        """
        text = """## Chapter 1

The Enlightenment changed things, noting. This shift led to progress.

### Key Excerpts"""

        result, report = draft_service.enforce_dangling_attribution_gate(text)

        # Orphan 'noting' should be removed
        assert "noting. This" not in result
        # Sentence should flow properly
        assert ". This shift" in result

    def test_removes_orphan_wrapper_observing(self):
        """Orphan 'observing' wrapper should be removed."""
        text = """## Chapter 1

Science evolved, observing. The method changed everything.

### Key Excerpts"""

        result, report = draft_service.enforce_dangling_attribution_gate(text)

        # Orphan 'observing' should be removed
        assert "observing. The" not in result
        # Sentence should flow
        assert ". The method" in result

    def test_rewrites_sentence_start_as_x_remarks(self):
        """REGRESSION Draft 13: Sentence-start 'As X remarks, This' SHOULD be rewritten.

        Input: 'As Deutsch poignantly remarks, This insight reflects...'
        Unlike mid-sentence ', as X notes, is', this is a sentence-start introducer
        that needs 'that' insertion.
        """
        text = """## Chapter 1

As Deutsch poignantly remarks, This insight reflects the spirit of the Enlightenment.

### Key Excerpts"""

        result, report = draft_service.enforce_dangling_attribution_gate(text)

        # Should be rewritten to indirect speech
        assert "remarks that this insight" in result
        # Original dangling pattern should be gone
        assert "remarks, This" not in result
        assert report["rewrites_applied"] >= 1

    def test_rewrites_he_predicts_comma(self):
        """REGRESSION Draft 13: 'He predicts, This' should be rewritten.

        Input: 'He predicts, This vision highlights...'
        """
        text = """## Chapter 1

He predicts, This vision highlights human ingenuity's role.

### Key Excerpts"""

        result, report = draft_service.enforce_dangling_attribution_gate(text)

        # Should be rewritten to indirect speech
        assert "predicts that this vision" in result
        assert "predicts, This" not in result
        assert report["rewrites_applied"] >= 1

    def test_still_skips_mid_sentence_as_x_notes(self):
        """Mid-sentence ', as X notes, is' should still be skipped.

        This ensures the lookbehind refinement didn't break the skip logic.
        """
        text = """## Chapter 1

Science, as Deutsch notes, is about finding laws of nature. As He remarks, This is key.

### Key Excerpts"""

        result, report = draft_service.enforce_dangling_attribution_gate(text)

        # Mid-sentence interpolation should NOT be rewritten
        assert "as Deutsch notes, is" in result
        assert "notes that is" not in result
        # But sentence-start introducer SHOULD be rewritten
        assert "remarks that this is key" in result

    def test_drops_sentence_with_recalling_verb_draft20(self):
        """REGRESSION Draft 20: 'recalling, <Capital>' must DROP the sentence.

        Input: 'Deutsch mentions the famous exchange, recalling, It's funny...'
        This is a double-wrapper pattern where the LLM generated an attribution
        wrapper around recalled speech. Cannot be cleanly rewritten - must drop.
        """
        text = """## Chapter 1

The Enlightenment marked a turning point in history. Deutsch mentions the famous exchange between Bohr and Einstein, recalling, It's funny you should mention the Bohr-Einstein debate. Such discussions drive the quest for knowledge.

### Key Excerpts"""

        result, report = draft_service.enforce_dangling_attribution_gate(text)

        # The sentence with "recalling, It's" should be dropped
        assert "recalling, It's" not in result
        assert "Deutsch mentions" not in result
        # Other sentences should be preserved
        assert "The Enlightenment marked a turning point" in result
        assert "Such discussions drive the quest" in result
        # Report should track the drop
        assert report["sentences_dropped"] >= 1

    def test_drops_sentence_with_remembering_verb(self):
        """'remembering, <Capital>' triggers sentence drop."""
        text = """## Chapter 1

The speaker shared insights. He paused, remembering, When I first learned this concept. The audience listened.

### Key Excerpts"""

        result, report = draft_service.enforce_dangling_attribution_gate(text)

        # Sentence with recall verb should be dropped
        assert "remembering, When" not in result
        assert "He paused" not in result
        # Other sentences preserved
        assert "The speaker shared insights" in result
        assert "The audience listened" in result
        assert report["sentences_dropped"] >= 1

    def test_preserves_sentences_without_recall_verbs(self):
        """Sentences with normal attribution verbs should be rewritten, not dropped."""
        text = """## Chapter 1

Deutsch notes, This is important. He argues, The evidence supports this.

### Key Excerpts"""

        result, report = draft_service.enforce_dangling_attribution_gate(text)

        # These should be REWRITTEN, not dropped
        assert "notes that this is important" in result
        assert "argues that the evidence" in result
        # No sentences should be dropped for these normal verbs
        assert report["sentences_dropped"] == 0
        assert report["rewrites_applied"] >= 2

    def test_drops_sentence_with_as_verb_that_draft22(self):
        """REGRESSION Draft 22: 'As Deutsch notes that ...' must DROP the sentence.

        Input: 'As Deutsch notes that what we call wisdom...'
        This is grammatically broken speaker framing. Valid forms are:
          - 'As Deutsch notes, what we call...' (interpolation with comma)
          - 'Deutsch notes that what we call...' (indirect speech)
        The 'As X verb that' form is broken and indicates leaked speaker framing.
        """
        text = """## Chapter 2

Reflecting on these themes, we see a broader narrative. As Deutsch notes that what we call wisdom today is going to be laughable silliness in centuries to come. This forward-looking view invites exploration.

### Key Excerpts"""

        result, report = draft_service.enforce_dangling_attribution_gate(text)

        # The sentence with "As Deutsch notes that" should be dropped
        assert "As Deutsch notes that" not in result
        assert "what we call wisdom" not in result
        # Other sentences should be preserved
        assert "Reflecting on these themes" in result
        assert "This forward-looking view invites exploration" in result
        # Report should track the drop
        assert report["sentences_dropped"] >= 1
        # Check drop details
        as_verb_that_drops = [d for d in report["drop_details"] if d["type"] == "as_verb_that_leak"]
        assert len(as_verb_that_drops) >= 1

    def test_drops_sentence_with_as_he_argues_that(self):
        """'As He argues that ...' triggers sentence drop."""
        text = """## Chapter 1

Science evolves. As He argues that knowledge is limitless. This view challenges limits.

### Key Excerpts"""

        result, report = draft_service.enforce_dangling_attribution_gate(text)

        # Sentence with "As He argues that" should be dropped
        assert "As He argues that" not in result
        assert "knowledge is limitless" not in result
        # Other sentences preserved
        assert "Science evolves" in result
        assert "This view challenges limits" in result
        assert report["sentences_dropped"] >= 1

    def test_preserves_valid_as_notes_interpolation(self):
        """Valid 'as X notes,' interpolation should NOT be dropped.

        This ensures we don't over-drop. The pattern targets 'As X verb that'
        not ', as X verb,' interpolations.
        """
        text = """## Chapter 1

Science, as Deutsch notes, is about finding testable regularities.

### Key Excerpts"""

        result, report = draft_service.enforce_dangling_attribution_gate(text)

        # Valid interpolation must be preserved
        assert "as Deutsch notes, is" in result
        # No sentences dropped
        assert report["sentences_dropped"] == 0


class TestFixTruncatedAttributions:
    """Tests for fix_truncated_attributions - joins split attribution lines."""

    def test_joins_truncated_notes_comma(self):
        """'Deutsch notes,' at EOL followed by content is joined."""
        text = """## Chapter 1

Deutsch notes,

This transformation went beyond gadgets.

### Key Excerpts"""

        result, report = draft_service.fix_truncated_attributions(text)

        assert "notes," not in result or "notes, " in result  # Either joined or unchanged
        assert "notes that this transformation" in result
        assert report["fixes_applied"] == 1

    def test_joins_truncated_says_comma(self):
        """'He says,' at EOL is joined with next paragraph."""
        text = """## Chapter 1

He says,

This idea challenges us.

### Key Excerpts"""

        result, report = draft_service.fix_truncated_attributions(text)

        assert "says that this idea" in result
        assert report["fixes_applied"] == 1

    def test_joins_truncated_points_adds_out(self):
        """'Deutsch points,' becomes 'Deutsch points out that'."""
        text = """## Chapter 1

Deutsch points,

There is only one truth.

### Key Excerpts"""

        result, report = draft_service.fix_truncated_attributions(text)

        assert "points out that there" in result
        assert report["fixes_applied"] == 1

    def test_preserves_non_truncated(self):
        """Normal paragraphs are not modified."""
        text = """## Chapter 1

The Enlightenment changed everything.

Progress accelerated rapidly.

### Key Excerpts"""

        result, report = draft_service.fix_truncated_attributions(text)

        assert "Enlightenment changed everything" in result
        assert "Progress accelerated rapidly" in result
        assert report["fixes_applied"] == 0

    def test_does_not_join_with_headers(self):
        """Truncated attribution before header is not joined."""
        text = """## Chapter 1

Deutsch notes,

### Key Excerpts"""

        result, report = draft_service.fix_truncated_attributions(text)

        # Should not try to join with the header
        assert "### Key Excerpts" in result
        assert report["fixes_applied"] == 0


class TestRemoveDiscourseMarkers:
    """Tests for remove_discourse_markers - removes verbal fillers from prose."""

    def test_removes_okay_at_sentence_start(self):
        """'Okay,' at sentence start is removed."""
        text = """## Chapter 1

Okay, I entirely agree with the idea.

### Key Excerpts"""

        result, report = draft_service.remove_discourse_markers(text)

        assert "Okay," not in result
        assert "I entirely agree" in result
        assert report["markers_removed"] == 1

    def test_removes_in_fact(self):
        """'In fact,' at sentence start is removed."""
        text = """## Chapter 1

He explained. In fact, that's not the case.

### Key Excerpts"""

        result, report = draft_service.remove_discourse_markers(text)

        assert "In fact," not in result
        assert "That's not the case" in result
        assert report["markers_removed"] == 1

    def test_removes_yes_period(self):
        """'Yes.' at sentence start is removed."""
        text = """## Chapter 1

Yes. This is not only desirable but inevitable.

### Key Excerpts"""

        result, report = draft_service.remove_discourse_markers(text)

        assert "Yes." not in result
        assert "This is not only desirable" in result
        assert report["markers_removed"] == 1

    def test_preserves_key_excerpts(self):
        """Discourse markers in Key Excerpts are preserved (verbatim quotes)."""
        text = """## Chapter 1

### Key Excerpts

> "Okay, I entirely agree with Stephen Hawking."
> — Speaker (GUEST)"""

        result, report = draft_service.remove_discourse_markers(text)

        # Quote content should be preserved
        assert "Okay, I entirely agree" in result
        assert report["markers_removed"] == 0

    def test_preserves_core_claims(self):
        """Discourse markers in Core Claims are preserved."""
        text = """## Chapter 1

### Core Claims

- **Claim**: "Yes, this is true."
"""

        result, report = draft_service.remove_discourse_markers(text)

        # Core Claims content should be preserved
        assert "Yes, this is true" in result
        assert report["markers_removed"] == 0

    def test_removes_multiple_markers(self):
        """Multiple markers in prose are all removed."""
        text = """## Chapter 1

Okay, first point here. Well, second point here. Actually, third point.

### Key Excerpts"""

        result, report = draft_service.remove_discourse_markers(text)

        assert "Okay," not in result
        assert "Well," not in result
        assert "Actually," not in result
        assert report["markers_removed"] == 3


class TestAnchorSentencePolicy:
    """Tests for repair_orphan_chapter_openers - fixes bad chapter openers."""

    def test_detects_and_repairs_understanding_these_opener_draft21(self):
        """REGRESSION Draft 21: 'Understanding these laws...' opener should be repaired.

        Chapter 3 in Draft 21 starts with 'Understanding these laws helps us...'
        which has no antecedent for 'these'. Should prepend fallback.
        """
        text = '''## Chapter 1: The Impact

The Enlightenment changed everything.

### Key Excerpts

> "Quote"
> — Speaker

### Core Claims

- **Claim**: "Support."

## Chapter 2: Human Potential

Human wisdom knows no bounds.

### Key Excerpts

> "Quote"
> — Speaker

### Core Claims

- **Claim**: "Support."

## Chapter 3: The Role of Knowledge

Understanding these laws helps us grasp our place in the cosmos.

### Key Excerpts

> "Quote"
> — Speaker

### Core Claims

- **Claim**: "Support."'''

        result, report = draft_service.repair_orphan_chapter_openers(text)

        # Chapter 3 should be repaired
        assert report["chapters_repaired"] >= 1
        repairs = report["repairs"]
        ch3_repairs = [r for r in repairs if r["chapter"] == 3]
        assert len(ch3_repairs) == 1
        assert ch3_repairs[0]["action"] == "fallback_prepended"
        # Fallback should be prepended, not replace
        assert "Understanding these laws" in result  # Original preserved
        # Should have a fallback variant before it
        has_fallback = (
            "This chapter develops" in result or
            "The core tension" in result or
            "This chapter threads" in result
        )
        assert has_fallback

    def test_detects_it_prompts_opener(self):
        """'It prompts us...' opener should be repaired."""
        text = '''## Chapter 1: First

It prompts us to rethink our relationship with the universe.

### Key Excerpts

> "Quote"
> — Speaker

### Core Claims

- **Claim**: "Support."'''

        result, report = draft_service.repair_orphan_chapter_openers(text)

        assert report["chapters_repaired"] == 1
        assert "fallback_prepended" in report["repairs"][0]["action"]
        # Original preserved
        assert "It prompts us" in result

    def test_detects_however_opener(self):
        """'However, ...' opener should be repaired."""
        text = '''## Chapter 1: First

However, a counter-narrative suggests humans are insignificant.

### Key Excerpts

> "Quote"
> — Speaker

### Core Claims

- **Claim**: "Support."'''

        result, report = draft_service.repair_orphan_chapter_openers(text)

        assert report["chapters_repaired"] == 1
        assert "However, a counter-narrative" in result  # Preserved

    def test_detects_he_warned_opener_draft22(self):
        """REGRESSION Draft 22: 'He warned...' opener should be repaired.

        Chapter 2 in Draft 22 starts with 'He warned that these traits...'
        which has no antecedent for 'He'. Pronoun subject at chapter start
        always lacks antecedent.
        """
        text = '''## Chapter 1: First

The Enlightenment changed everything.

### Key Excerpts

> "Quote"
> — Speaker

### Core Claims

- **Claim**: "Support."

## Chapter 2: Human Potential

He warned that these traits, once crucial, now pose dangers.

### Key Excerpts

> "Quote"
> — Speaker

### Core Claims

- **Claim**: "Support."'''

        result, report = draft_service.repair_orphan_chapter_openers(text)

        # Chapter 2 should be repaired
        assert report["chapters_repaired"] >= 1
        repairs = report["repairs"]
        ch2_repairs = [r for r in repairs if r["chapter"] == 2]
        assert len(ch2_repairs) == 1
        assert ch2_repairs[0]["action"] == "fallback_prepended"
        # Original preserved after fallback
        assert "He warned" in result

    def test_preserves_good_opener(self):
        """Chapter with good opener (proper subject) should not be modified."""
        text = '''## Chapter 1: The Impact

The Enlightenment marked a turning point in human history.

### Key Excerpts

> "Quote"
> — Speaker

### Core Claims

- **Claim**: "Support."

## Chapter 2: Human Potential

David Deutsch envisions a future where human wisdom knows no bounds.

### Key Excerpts

> "Quote"
> — Speaker

### Core Claims

- **Claim**: "Support."'''

        result, report = draft_service.repair_orphan_chapter_openers(text)

        # No repairs needed
        assert report["chapters_repaired"] == 0
        # Content unchanged
        assert "The Enlightenment marked" in result
        assert "David Deutsch envisions" in result

    def test_salvage_from_original_prose(self):
        """If original prose provided, should salvage safe sentence."""
        current_text = '''## Chapter 1: The Impact

This shows the significance of the change.

### Key Excerpts

> "Quote"
> — Speaker'''

        # Original prose had a good anchor sentence
        original_prose = {
            1: "The Enlightenment was a pivotal moment in human intellectual development. This shows the significance of the change."
        }

        result, report = draft_service.repair_orphan_chapter_openers(
            current_text,
            original_prose_by_chapter=original_prose,
        )

        assert report["chapters_repaired"] == 1
        repairs = report["repairs"]
        assert repairs[0]["action"] == "salvage_prepended"
        # Salvage sentence should be prepended
        assert "The Enlightenment was a pivotal moment" in result
        # Original content preserved
        assert "This shows the significance" in result


class TestChapterProseMetrics:
    """Tests for compute_chapter_prose_metrics - quality tracking."""

    def test_counts_sentences_per_chapter(self):
        """Should count sentences in prose sections correctly."""
        text = '''## Chapter 1: First

The Enlightenment changed everything. It marked a turning point in history. Progress became possible.

### Key Excerpts

> "Quote"
> — Speaker

### Core Claims

- **Claim**: "Support."

## Chapter 2: Second

Human wisdom knows no bounds. We can shape our future.

### Key Excerpts

> "Quote"
> — Speaker'''

        metrics = draft_service.compute_chapter_prose_metrics(text)

        assert metrics["total_chapters"] == 2
        assert metrics["chapters"][0]["chapter"] == 1
        assert metrics["chapters"][0]["sentences_kept"] == 3
        assert metrics["chapters"][1]["chapter"] == 2
        assert metrics["chapters"][1]["sentences_kept"] == 2
        assert metrics["total_sentences_kept"] == 5

    def test_detects_fallback_usage(self):
        """Should detect when fallback narrative was used."""
        text = '''## Chapter 1: First

This chapter develops the theme of progress by linking concrete moments to claims.

### Key Excerpts

> "Quote"
> — Speaker

## Chapter 2: Second

Human wisdom knows no bounds. This is real prose.

### Key Excerpts

> "Quote"
> — Speaker'''

        metrics = draft_service.compute_chapter_prose_metrics(text)

        assert metrics["fallback_chapters"] == 1
        assert metrics["chapters"][0]["fallback_used"] is True
        assert metrics["chapters"][1]["fallback_used"] is False

    def test_handles_prose_zero_chapters(self):
        """Should handle chapters with no prose."""
        text = '''## Chapter 1: First

### Key Excerpts

> "Quote"
> — Speaker

### Core Claims

- **Claim**: "Support."'''

        metrics = draft_service.compute_chapter_prose_metrics(text)

        assert metrics["total_chapters"] == 1
        assert metrics["chapters"][0]["sentences_kept"] == 0


class TestChapterNarrativeFallback:
    """Tests for ensure_chapter_narrative_minimum - prevents content collapse."""

    def test_inserts_fallback_for_prose_zero_chapter(self):
        """Chapter with only Key Excerpts gets fallback narrative."""
        text = """## Chapter 1: The Impact

### Key Excerpts

> "Quote here"
> — Speaker (GUEST)

### Core Claims

- **Claim**: Support text."""

        result, report = draft_service.ensure_chapter_narrative_minimum(text)

        # Should have inserted fallback
        assert report["chapters_fixed"] == 1
        # Fallback should be one of the three variants
        has_variant = (
            "This chapter develops" in result or  # Variant A
            "The core tension" in result or  # Variant B
            "This chapter threads" in result  # Variant C
        )
        assert has_variant, f"Expected fallback variant, got: {result}"
        # Structure preserved
        assert "Key Excerpts" in result
        assert "Core Claims" in result

    def test_preserves_chapter_with_prose(self):
        """Chapter with existing prose is not modified."""
        text = """## Chapter 2: Human Potential

This is existing prose that should be preserved.

### Key Excerpts

> "Quote here"
> — Speaker (GUEST)"""

        result, report = draft_service.ensure_chapter_narrative_minimum(text)

        # Should not have modified
        assert report["chapters_fixed"] == 0
        assert "This is existing prose" in result

    def test_handles_multiple_chapters(self):
        """Correctly handles mix of prose and prose-zero chapters."""
        text = """## Chapter 1: First

This chapter has prose.

### Key Excerpts

> "Quote"
> — Speaker

## Chapter 2: Second

### Key Excerpts

> "Another quote"
> — Speaker

## Chapter 3: Third

This chapter also has prose.

### Key Excerpts

> "Third quote"
> — Speaker"""

        result, report = draft_service.ensure_chapter_narrative_minimum(text)

        # Only Chapter 2 should be fixed
        assert report["chapters_fixed"] == 1
        assert report["fixed_details"][0]["chapter"] == 2
        # Original prose preserved
        assert "This chapter has prose" in result
        assert "This chapter also has prose" in result

    def test_fallback_uses_chapter_title(self):
        """Fallback narrative incorporates chapter title."""
        text = """## Chapter 1: Human Potential and the Universe

### Key Excerpts

> "Quote"
> — Speaker"""

        result, report = draft_service.ensure_chapter_narrative_minimum(text)

        # Should reference the title theme
        assert report["chapters_fixed"] == 1
        # The fallback should mention the title (lowercased)
        assert "human potential" in result.lower()

    def test_fallback_variants_differ_across_chapters(self):
        """REGRESSION Draft 18: Fallback text must differ across chapters.

        Draft 18 had identical boilerplate for Ch1/Ch3 and Ch2/Ch4.
        The hash-based variant selection ensures diversity.
        """
        # Four chapters with no prose - all need fallback
        text = """## Chapter 1: The Impact of the Enlightenment

### Key Excerpts

> "Quote 1"
> — Speaker

## Chapter 2: Human Potential and the Universe

### Key Excerpts

> "Quote 2"
> — Speaker

## Chapter 3: The Role of Knowledge

### Key Excerpts

> "Quote 3"
> — Speaker

## Chapter 4: Scientific Inquiry

### Key Excerpts

> "Quote 4"
> — Speaker"""

        result, report = draft_service.ensure_chapter_narrative_minimum(text)

        # All 4 chapters should get fallback
        assert report["chapters_fixed"] == 4

        # Extract the fallback narratives (text between chapter header and ### Key Excerpts)
        import re
        fallbacks = re.findall(
            r'## Chapter \d+[^\n]*\n\n([^#]+?)### Key Excerpts',
            result,
            re.DOTALL
        )

        # Should have 4 fallbacks
        assert len(fallbacks) == 4

        # Strip and get unique fallbacks
        unique_fallbacks = set(f.strip() for f in fallbacks)

        # At least 2 different variants should be used (not all identical)
        assert len(unique_fallbacks) >= 2, (
            f"Expected at least 2 different fallback variants, got {len(unique_fallbacks)}. "
            f"Fallbacks were: {unique_fallbacks}"
        )

    def test_fallback_is_deterministic(self):
        """Same chapter always gets same fallback variant."""
        text = """## Chapter 1: Human Potential

### Key Excerpts

> "Quote"
> — Speaker"""

        result1, _ = draft_service.ensure_chapter_narrative_minimum(text)
        result2, _ = draft_service.ensure_chapter_narrative_minimum(text)

        # Same input should produce identical output
        assert result1 == result2


class TestCleanupDanglingConnectives:
    """Tests for cleanup_dangling_connectives - fixes orphaned articles/connectives."""

    def test_fixes_dangling_article_offers_a(self):
        """REGRESSION Draft 12: 'offers a .' with dropped payload is cleaned up.

        Input: 'However, Stephen Hawking offers a . Traits that once helped...'
        The 'a' was supposed to introduce a noun/quote that got dropped.
        We delete the broken clause and keep the next sentence.
        """
        text = """## Chapter 2

However, Stephen Hawking offers a . Traits that once helped humans survive could now pose serious risks.

### Key Excerpts"""

        result, report = draft_service.cleanup_dangling_connectives(text)

        # The dangling "offers a ." should be removed
        assert "offers a ." not in result
        # The next sentence should survive
        assert "Traits that once helped" in result
        assert report["cleanups_applied"] >= 1

    def test_fixes_dangling_that_introducer(self):
        """REGRESSION Draft 12: ', suggesting that .' with dropped clause is cleaned up.

        Input: 'Deutsch warns of the danger, suggesting that . This stark warning...'
        The 'that' was supposed to introduce a clause that got dropped.
        We replace ', suggesting that .' with '. '
        """
        text = """## Chapter 4

Deutsch warns of the danger of rejecting these principles, suggesting that . This stark warning urges us to stay committed.

### Key Excerpts"""

        result, report = draft_service.cleanup_dangling_connectives(text)

        # The dangling ", suggesting that ." should become ". "
        assert ", suggesting that ." not in result
        # The next sentence should survive
        assert "This stark warning" in result
        # Should have proper sentence boundary
        assert ". This stark warning" in result
        assert report["cleanups_applied"] >= 1

    def test_preserves_valid_article_usage(self):
        """Valid 'a' usage should not be modified."""
        text = """## Chapter 1

This represents a major shift in understanding. The change was profound.

### Key Excerpts"""

        result, report = draft_service.cleanup_dangling_connectives(text)

        # Valid article usage preserved
        assert "a major shift" in result
        assert report["cleanups_applied"] == 0

    def test_preserves_key_excerpts(self):
        """Key Excerpts should not be modified."""
        text = """## Chapter 1

Some prose here.

### Key Excerpts

> "He offers a . strange view"
> — Speaker"""

        result, report = draft_service.cleanup_dangling_connectives(text)

        # Key Excerpts preserved even with odd content
        assert 'offers a . strange' in result

    def test_fixes_dangling_the(self):
        """Dangling 'the' before period should be cleaned."""
        text = """## Chapter 1

Science provides the . Evidence shows this clearly.

### Key Excerpts"""

        result, report = draft_service.cleanup_dangling_connectives(text)

        # Dangling "the ." should be handled
        assert "provides the ." not in result
        assert "Evidence shows" in result


class TestTokenIntegrityValidator:
    """Tests for validate_token_integrity function - HARD GATE for token truncation."""

    def test_detects_truncated_he_fragment(self):
        """REGRESSION Draft 15: 'he n,' pattern must be detected as truncation."""
        text = """## Chapter 1

This environment can help humans thrive, he n, framing progress as necessary.

### Key Excerpts

> "Some quote"
> — Speaker"""

        is_valid, report = draft_service.validate_token_integrity(text)

        assert not is_valid
        assert report["violation_count"] >= 1
        violations = report["violations"]
        assert any(v["type"] == "truncated_he_fragment" for v in violations)
        assert any("he n" in v["matched"] for v in violations)

    def test_detects_he_power_truncation(self):
        """REGRESSION Draft 15: 'he power,' pattern must be detected as truncation."""
        text = """## Chapter 2

We have the power to get things right, he power, capturing the essence.

### Key Excerpts

> "Some quote"
> — Speaker"""

        is_valid, report = draft_service.validate_token_integrity(text)

        assert not is_valid
        assert report["violation_count"] >= 1
        violations = report["violations"]
        assert any(v["type"] == "truncated_he_fragment" for v in violations)

    def test_detects_orphan_tail_so_choose(self):
        """REGRESSION Draft 15: 'so choose.' orphan line must be detected."""
        text = """## Chapter 1

Some valid prose here.

### Core Claims

- **A claim**: "Evidence"

so choose.

## Chapter 2

More prose."""

        is_valid, report = draft_service.validate_token_integrity(text)

        assert not is_valid
        assert report["violation_count"] >= 1
        violations = report["violations"]
        assert any(v["type"] == "orphan_tail_line" for v in violations)

    def test_detects_single_letter_truncation(self):
        """Mid-word truncation like ', n,' must be detected."""
        text = """## Chapter 1

The technology, n, advanced rapidly.

### Key Excerpts

> "Quote"
> — Speaker"""

        is_valid, report = draft_service.validate_token_integrity(text)

        assert not is_valid
        violations = report["violations"]
        assert any(v["type"] == "mid_word_truncation" for v in violations)

    def test_passes_valid_prose(self):
        """Valid prose should pass integrity check."""
        text = """## Chapter 1

David Deutsch argues that progress is limitless. He notes that the Enlightenment changed everything. This represents a major shift in understanding.

### Key Excerpts

> "The lesson of universality is that there is only one set of laws."
> — David Deutsch (GUEST)

### Core Claims

- **Universal laws govern physics**: "The lesson of universality is that there is only one set of laws."

## Chapter 2

More valid prose here. He is clearly correct about this."""

        is_valid, report = draft_service.validate_token_integrity(text)

        assert is_valid
        assert report["violation_count"] == 0

    def test_allows_valid_he_verbs(self):
        """Valid 'he says' / 'he notes' patterns should pass."""
        text = """## Chapter 1

Deutsch makes a key point, he says, about progress.

The idea, he notes, is profound.

### Key Excerpts"""

        is_valid, report = draft_service.validate_token_integrity(text)

        assert is_valid
        assert report["violation_count"] == 0

    def test_preserves_key_excerpts_with_oddities(self):
        """Key Excerpts should not be checked for violations."""
        text = """## Chapter 1

Valid prose here.

### Key Excerpts

> "Quote with, he n, oddity"
> — Speaker

### Core Claims

- **Claim**: "so choose."
"""

        is_valid, report = draft_service.validate_token_integrity(text)

        # Should pass - violations in Key Excerpts and Core Claims are OK
        assert is_valid


class TestOrphanFragmentCleanup:
    """Tests for cleanup_orphan_fragments_between_sections - removes debris between sections."""

    def test_removes_orphan_after_core_claims_draft19(self):
        """REGRESSION Draft 19: 'ethos of inquiry.' orphan after Core Claims must be removed."""
        text = '''## Chapter 1: The Impact

Some prose here.

### Key Excerpts

> "Quote here."
> — Speaker

### Core Claims

- **After the Enlightenment**: "We have learned to live with improvement."

ethos of inquiry.

## Chapter 2: Human Potential

More prose.'''

        result, report = draft_service.cleanup_orphan_fragments_between_sections(text)

        # Orphan should be removed
        assert "ethos of inquiry" not in result
        # Chapter structure preserved
        assert "## Chapter 1" in result
        assert "## Chapter 2" in result
        assert "### Core Claims" in result
        assert report["fragments_removed"] == 1
        assert "ethos of inquiry." in report["removed_fragments"]

    def test_preserves_valid_core_claims_content(self):
        """Valid Core Claims bullets and placeholders should not be removed."""
        text = '''## Chapter 1

### Core Claims

- **Claim one**: "Support text one."
- **Claim two**: "Support text two."

## Chapter 2

### Core Claims

*No claims available for this chapter.*'''

        result, report = draft_service.cleanup_orphan_fragments_between_sections(text)

        # All content preserved
        assert "Claim one" in result
        assert "Claim two" in result
        assert "*No claims available" in result
        assert report["fragments_removed"] == 0

    def test_removes_multiple_orphan_lines(self):
        """Multiple orphan lines after Core Claims should all be removed."""
        text = '''## Chapter 1

### Core Claims

- **Claim**: "Support."

orphan line one.
orphan line two.
third orphan.

## Chapter 2'''

        result, report = draft_service.cleanup_orphan_fragments_between_sections(text)

        assert "orphan line" not in result
        assert "third orphan" not in result
        assert report["fragments_removed"] == 3


class TestEnsureRequiredSectionsExist:
    """Tests for ensure_required_sections_exist - inserts missing section headers."""

    def test_inserts_missing_core_claims_draft19(self):
        """REGRESSION Draft 19: Missing Core Claims section should be inserted."""
        text = '''## Chapter 1: The Impact

Some prose.

### Key Excerpts

> "Quote 1"
> — Speaker

### Core Claims

- **Claim 1**: "Support."

## Chapter 2: Human Potential

More prose.

### Key Excerpts

> "Quote 2"
> — Speaker'''

        result, report = draft_service.ensure_required_sections_exist(text)

        # Chapter 2 should now have Core Claims (Ch1 already has it)
        assert result.count("### Core Claims") == 2  # Ch1 existing + Ch2 inserted
        assert "*No claims available.*" in result
        assert report["sections_inserted"] == 1
        assert any(s["chapter"] == 2 and s["section"] == "Core Claims" for s in report["inserted"])

    def test_inserts_both_missing_sections(self):
        """Chapter missing both sections should get both inserted."""
        text = '''## Chapter 1: First

Prose only, no sections.

## Chapter 2: Second

More prose.'''

        result, report = draft_service.ensure_required_sections_exist(text)

        # Both sections inserted for each chapter
        assert result.count("### Key Excerpts") == 2
        assert result.count("### Core Claims") == 2
        assert report["sections_inserted"] == 4

    def test_preserves_complete_chapters(self):
        """Chapters with both sections should not be modified."""
        text = '''## Chapter 1

### Key Excerpts

> "Quote"
> — Speaker

### Core Claims

- **Claim**: "Support."

## Chapter 2

### Key Excerpts

> "Quote 2"
> — Speaker

### Core Claims

- **Claim 2**: "Support."'''

        result, report = draft_service.ensure_required_sections_exist(text)

        # No changes needed
        assert report["sections_inserted"] == 0
        assert result == text


class TestStructuralIntegrityValidator:
    """Tests for validate_structural_integrity function - P0 hard gate."""

    def test_detects_unclosed_quote_in_core_claim(self):
        """REGRESSION Draft 16: Core Claim with unclosed quote must be detected."""
        text = '''## Chapter 2

Some prose here.

### Core Claims

- **Human influence is inevitable**: "Yes. This is not only desirable, as Stephen Hawking says, but it's really inevitable. Human history is deeply connected

## Chapter 3

More prose here.'''

        is_valid, report = draft_service.validate_structural_integrity(text)

        assert not is_valid
        assert report["violation_count"] >= 1
        violations = report["violations"]
        assert any(v["type"] == "unclosed_quote_in_core_claim" for v in violations)

    def test_detects_heading_absorbed_by_core_claim(self):
        """Core Claim that absorbed a chapter heading must be detected."""
        text = '''## Chapter 2

### Core Claims

- **Claim with absorbed content**: "Quote starts here but never ends

## Chapter 3: This heading got absorbed

More content here.

### Key Excerpts'''

        is_valid, report = draft_service.validate_structural_integrity(text)

        assert not is_valid
        violations = report["violations"]
        # Should detect either unclosed quote or heading absorption
        assert len(violations) >= 1

    def test_passes_valid_core_claims(self):
        """Valid Core Claims with proper quotes should pass."""
        text = '''## Chapter 1

Some prose here.

### Key Excerpts

> "Quote here."
> — Speaker

### Core Claims

- **The Enlightenment marked a significant change**: "This line is the most important thing that's ever happened."
- **Science is about laws**: "Science is about finding laws of nature."
- **Progress is possible**: "We have learned to live with the fact that everything improves."

## Chapter 2

More prose.

### Key Excerpts

> "Another quote."
> — Speaker

### Core Claims

- **Claim here**: "Support text."'''

        is_valid, report = draft_service.validate_structural_integrity(text)

        assert is_valid
        assert report["violation_count"] == 0

    def test_passes_core_claims_with_canonical_placeholder(self):
        """Core Claims with our canonical placeholder should pass."""
        # Use the exact canonical placeholder from draft_service
        text = '''## Chapter 1

Some prose.

### Key Excerpts

> "Quote here."
> — Speaker

### Core Claims

*No claims available.*

## Chapter 2

More prose.

### Key Excerpts

> "Quote."
> — Speaker

### Core Claims

*No claims available.*'''

        is_valid, report = draft_service.validate_structural_integrity(text)

        assert is_valid
        assert report["violation_count"] == 0

    def test_detects_multi_paragraph_quote_absorption(self):
        """Quote that spans multiple paragraphs indicates structural corruption."""
        # This simulates Draft 16's issue where quote absorbed entire chapter
        text = '''## Chapter 2

### Core Claims

- **Human influence is inevitable**: "Yes. This is not only desirable.

Human history is deeply connected to how we develop knowledge.

The Enlightenment marked a turning point.

## Chapter 3'''

        is_valid, report = draft_service.validate_structural_integrity(text)

        assert not is_valid
        # Should detect unclosed quote in the Core Claim bullet
        violations = report["violations"]
        assert any(v["type"] == "unclosed_quote_in_core_claim" for v in violations)

    def test_detects_orphan_fragment_between_sections_draft19(self):
        """REGRESSION Draft 19: 'ethos of inquiry.' orphan fragment must be detected.

        Draft 19 had this exact pattern - a short fragment appearing between
        Core Claims section and next chapter header.
        """
        text = '''## Chapter 1: The Impact of the Enlightenment

Some prose here.

### Core Claims

- **After the Enlightenment**: "We have learned to live with the fact that everything improves."

ethos of inquiry.

## Chapter 2: Human Potential

More prose here.

### Key Excerpts

> "Quote here"
> — Speaker'''

        is_valid, report = draft_service.validate_structural_integrity(text)

        assert not is_valid
        violations = report["violations"]
        orphan_violations = [v for v in violations if v["type"] == "orphan_fragment_between_sections"]
        assert len(orphan_violations) >= 1
        assert any("ethos of inquiry" in v.get("fragment", "") for v in orphan_violations)

    def test_detects_missing_core_claims_section_draft19(self):
        """REGRESSION Draft 19: Chapter 2 missing Core Claims section must be detected.

        Draft 19 had Chapter 2 jump from Key Excerpts straight to Chapter 3
        without any Core Claims section.
        """
        text = '''## Chapter 1: The Impact

Some prose.

### Key Excerpts

> "Quote"
> — Speaker

### Core Claims

- **Claim**: "Support text."

## Chapter 2: Human Potential

More prose.

### Key Excerpts

> "Quote"
> — Speaker

## Chapter 3: Knowledge'''

        is_valid, report = draft_service.validate_structural_integrity(text)

        assert not is_valid
        violations = report["violations"]
        missing_violations = [v for v in violations if v["type"] == "missing_core_claims_section"]
        assert len(missing_violations) >= 1
        assert any(v.get("chapter") == 2 for v in missing_violations)

    def test_passes_complete_chapter_structure(self):
        """All chapters with both Key Excerpts and Core Claims should pass."""
        text = '''## Chapter 1: First

Prose here.

### Key Excerpts

> "Quote 1"
> — Speaker

### Core Claims

- **Claim 1**: "Support."

## Chapter 2: Second

More prose.

### Key Excerpts

> "Quote 2"
> — Speaker

### Core Claims

- **Claim 2**: "Support."'''

        is_valid, report = draft_service.validate_structural_integrity(text)

        assert is_valid
        assert report["violation_count"] == 0

    def test_detects_llm_generated_core_claims_placeholder_draft20(self):
        """REGRESSION Draft 20: LLM-generated placeholder text must be detected.

        Draft 20 had Chapter 4 with:
            ### Core Claims
            *No fully grounded claims available for this chapter.*

        This is LLM-generated text, not our canonical placeholder. Core Claims
        must be COMPILED, not LLM-authored. This is a P0 ownership violation.
        """
        text = '''## Chapter 1: Impact

Prose here.

### Key Excerpts

> "Quote"
> — Speaker

### Core Claims

- **Valid claim**: "Support text."

## Chapter 2: Human Potential

More prose.

### Key Excerpts

> "Quote 2"
> — Speaker

### Core Claims

*No fully grounded claims available for this chapter.*'''

        is_valid, report = draft_service.validate_structural_integrity(text)

        assert not is_valid
        violations = report["violations"]
        llm_violations = [v for v in violations if v["type"] == "llm_generated_core_claims_placeholder"]
        assert len(llm_violations) >= 1
        assert any(v.get("chapter") == 2 for v in llm_violations)

    def test_detects_unable_to_extract_llm_placeholder(self):
        """LLM-generated 'Unable to extract' text must be detected."""
        text = '''## Chapter 1: First

Prose.

### Key Excerpts

> "Quote"
> — Speaker

### Core Claims

Unable to extract any grounded claims from this section.'''

        is_valid, report = draft_service.validate_structural_integrity(text)

        assert not is_valid
        violations = report["violations"]
        assert any(v["type"] == "llm_generated_core_claims_placeholder" for v in violations)


class TestSpeakerFramingSanitizer:
    """Tests for sanitize_speaker_framing - verb-agnostic attribution drop."""

    def test_drops_attribution_comma_capital_draft24(self):
        """REGRESSION Draft 24: 'He elaborates, In every...' must be dropped.

        Verb-agnostic pattern: (Name|He|She|They) <words>, <Capital>
        This catches ALL attribution wrappers without needing a verb list.
        """
        text = """## Chapter 1: The Enlightenment

The Enlightenment changed everything. He elaborates, In every chapter there was a beginning. This was transformative.

### Key Excerpts"""

        result, report = draft_service.sanitize_speaker_framing(text)

        # Sentence with attribution wrapper should be dropped
        assert "He elaborates, In" not in result
        # Other sentences preserved
        assert "The Enlightenment changed everything" in result
        assert "This was transformative" in result
        assert report["sentences_dropped"] >= 1

    def test_drops_possessive_attribution_draft24(self):
        """REGRESSION Draft 24: 'Deutsch's book suggests...' must be dropped.

        Pattern: Name's <noun> <verb>
        """
        text = """## Chapter 1: First

Progress is key. Deutsch's book suggests this shift was pivotal. Understanding grew.

### Key Excerpts"""

        result, report = draft_service.sanitize_speaker_framing(text)

        # Sentence with possessive attribution should be dropped
        assert "Deutsch's book" not in result
        # Other sentences preserved
        assert "Progress is key" in result
        assert "Understanding grew" in result
        assert report["sentences_dropped"] >= 1

    def test_drops_according_to(self):
        """'According to Deutsch, ...' must be dropped."""
        text = """## Chapter 1: First

Science evolves. According to Deutsch, progress is unlimited. This view prevails.

### Key Excerpts"""

        result, report = draft_service.sanitize_speaker_framing(text)

        # According to sentence should be dropped
        assert "According to Deutsch" not in result
        # Other sentences preserved
        assert "Science evolves" in result
        assert "This view prevails" in result
        assert report["sentences_dropped"] >= 1

    def test_drops_as_name_verb_that(self):
        """'As Deutsch aptly suggests that...' must be dropped."""
        text = """## Chapter 1: First

Progress matters. As Deutsch aptly suggests that we are at the beginning. This is key.

### Key Excerpts"""

        result, report = draft_service.sanitize_speaker_framing(text)

        # As X verb that sentence should be dropped
        assert "As Deutsch aptly suggests that" not in result
        # Other sentences preserved
        assert "Progress matters" in result
        assert "This is key" in result
        assert report["sentences_dropped"] >= 1

    def test_preserves_key_excerpts(self):
        """Key Excerpts must never be modified."""
        text = """## Chapter 1: First

Some prose here.

### Key Excerpts

> "Deutsch argues that this is important."
> — David Deutsch (GUEST)

### Core Claims"""

        result, report = draft_service.sanitize_speaker_framing(text)

        # Key Excerpts preserved verbatim
        assert "Deutsch argues that this is important" in result
        assert "David Deutsch (GUEST)" in result
        # No drops in excerpts
        assert report["sentences_dropped"] == 0

    def test_preserves_core_claims(self):
        """Core Claims must never be modified."""
        text = """## Chapter 1: First

Some prose here.

### Key Excerpts

> "Quote"
> — Speaker

### Core Claims

- **Deutsch argues that progress matters**: "Quote text here."
"""

        result, report = draft_service.sanitize_speaker_framing(text)

        # Core Claims preserved verbatim
        assert "Deutsch argues that progress matters" in result

    def test_drops_generic_speaker_attribution_draft25(self):
        """REGRESSION Draft 25: 'One scholar noted...' must be dropped.

        Generic speaker attribution violates timeless essay style.
        """
        text = """## Chapter 1: First

Progress is key. One scholar noted, The scientific method became a driving force. This changed everything.

### Key Excerpts"""

        result, report = draft_service.sanitize_speaker_framing(text)

        # Generic speaker attribution should be dropped
        assert "One scholar noted" not in result
        # Other sentences preserved
        assert "Progress is key" in result
        assert "This changed everything" in result
        assert report["sentences_dropped"] >= 1

    def test_drops_influential_thinker_remarked_draft25(self):
        """REGRESSION Draft 25: 'An influential thinker once remarked,' must be dropped."""
        text = """## Chapter 1: First

The era began. An influential thinker once remarked, This insight changed history.

### Key Excerpts"""

        result, report = draft_service.sanitize_speaker_framing(text)

        # Generic speaker attribution should be dropped
        assert "An influential thinker" not in result
        assert "once remarked" not in result
        # Other sentences preserved
        assert "The era began" in result
        assert report["sentences_dropped"] >= 1

    def test_drops_as_one_scholar_noted(self):
        """'As one scholar noted...' must be dropped."""
        text = """## Chapter 1: First

Science evolved. As one scholar noted, this was pivotal. Understanding grew.

### Key Excerpts"""

        result, report = draft_service.sanitize_speaker_framing(text)

        # As generic speaker should be dropped
        assert "As one scholar noted" not in result
        # Other sentences preserved
        assert "Science evolved" in result
        assert "Understanding grew" in result
        assert report["sentences_dropped"] >= 1

    def test_drops_orphan_pronoun_no_antecedent(self):
        """If no sentences kept yet, orphan It/This/They should drop."""
        text = """## Chapter 1: First

One scholar noted the importance. It touched the core of potential. Understanding grew.

### Key Excerpts"""

        result, report = draft_service.sanitize_speaker_framing(text)

        # Generic speaker dropped (first sentence)
        assert "One scholar noted" not in result
        # Orphan "It" with no antecedent should also be dropped
        assert "It touched" not in result
        # Third sentence preserved (it's now the first kept sentence)
        assert "Understanding grew" in result
        # Should have dropped 2 sentences
        assert report["sentences_dropped"] >= 2
        # Check for orphan_pronoun_no_antecedent type
        orphan_drops = [d for d in report["drop_details"] if d["type"] == "orphan_pronoun_no_antecedent"]
        assert len(orphan_drops) >= 1

    def test_preserves_pronoun_with_antecedent(self):
        """Pronouns with antecedent (previous sentence kept) should be preserved."""
        text = """## Chapter 1: First

The Enlightenment changed everything. It marked a turning point. This was transformative.

### Key Excerpts"""

        result, report = draft_service.sanitize_speaker_framing(text)

        # All sentences should be preserved (valid antecedents)
        assert "The Enlightenment changed everything" in result
        assert "It marked a turning point" in result
        assert "This was transformative" in result
        assert report["sentences_dropped"] == 0


class TestSpeakerFramingInvariant:
    """Tests for enforce_speaker_framing_invariant - drop remaining speaker framing."""

    def test_drops_remaining_framing_after_sanitizer(self):
        """Any speaker framing that survives sanitizer must be dropped."""
        text = """## Chapter 1: First

The Enlightenment changed everything. Deutsch notes the importance of this shift. Progress became possible.

### Key Excerpts"""

        result, report = draft_service.enforce_speaker_framing_invariant(text)

        # Sentence with remaining framing should be dropped
        assert "Deutsch notes" not in result
        # Other sentences preserved
        assert "The Enlightenment changed everything" in result
        assert "Progress became possible" in result
        assert report["speaker_framing_sentences_dropped"] >= 1

    def test_drops_according_to_remaining(self):
        """'According to X' remaining sentences are dropped."""
        text = """## Chapter 2: Second

Knowledge grows. According to Hawking, the universe is vast. We must explore.

### Key Excerpts"""

        result, report = draft_service.enforce_speaker_framing_invariant(text)

        # Sentence dropped
        assert "According to Hawking" not in result
        # Others preserved
        assert "Knowledge grows" in result
        assert "We must explore" in result
        assert report["speaker_framing_sentences_dropped"] >= 1

    def test_preserves_key_excerpts(self):
        """Key Excerpts are never touched by invariant enforcement."""
        text = """## Chapter 1: First

Clean prose here.

### Key Excerpts

> "Deutsch argues that this matters."
> — David Deutsch (GUEST)"""

        result, report = draft_service.enforce_speaker_framing_invariant(text)

        # Key Excerpts preserved
        assert "Deutsch argues that this matters" in result
        assert "David Deutsch (GUEST)" in result
        # No drops
        assert report["speaker_framing_sentences_dropped"] == 0


class TestFirstParagraphPronounRepair:
    """Tests for repair_first_paragraph_pronouns - fix pronouns in first paragraph."""

    def test_replaces_it_with_enlightenment_draft23(self):
        """REGRESSION Draft 23: 'It introduced...' → 'The Enlightenment introduced...'.

        Input: 'Before these eras... It introduced testable laws...'
        The 'It' has no antecedent and should be replaced with chapter title noun.
        """
        text = """## Chapter 1: The Impact of the Enlightenment

Before these eras, ideas stagnated. It introduced testable laws of nature.

### Key Excerpts"""

        result, report = draft_service.repair_first_paragraph_pronouns(text)

        # "It" should be replaced with "The Enlightenment"
        assert "It introduced" not in result
        assert "The Enlightenment introduced" in result
        assert report["sentences_repaired"] >= 1

    def test_replaces_this_with_chapter_noun(self):
        """'This shows...' in first paragraph gets replaced with title noun."""
        text = """## Chapter 2: Human Potential and the Universe

The speaker shared insights. This shows our capacity.

### Key Excerpts"""

        result, report = draft_service.repair_first_paragraph_pronouns(text)

        # "This" should be replaced with "Human Potential" (preserves title casing)
        assert "This shows" not in result
        assert "Human Potential shows" in result
        assert report["sentences_repaired"] >= 1

    def test_preserves_pronouns_in_later_paragraphs(self):
        """Pronouns in non-first paragraphs are not modified."""
        text = """## Chapter 1: The Impact of the Enlightenment

The first paragraph has good prose here.

It is in the second paragraph. This is also fine here.

### Key Excerpts"""

        result, report = draft_service.repair_first_paragraph_pronouns(text)

        # Second paragraph pronouns preserved
        assert "It is in the second paragraph" in result
        assert "This is also fine here" in result
        # No repairs needed
        assert report["sentences_repaired"] == 0

    def test_handles_empty_title_gracefully(self):
        """Empty title should not cause errors - sentence may be dropped or left."""
        text = """## Chapter 1:

It shows something.

### Key Excerpts"""

        result, report = draft_service.repair_first_paragraph_pronouns(text)

        # Function should not crash and produce valid output
        assert "### Key Excerpts" in result
        # Either dropped or repaired (depending on title extraction)
        assert report["sentences_dropped"] >= 0
        assert report["sentences_repaired"] >= 0

    def test_handles_multiple_pronoun_sentences(self):
        """Multiple pronoun-start sentences in first paragraph all get fixed."""
        text = """## Chapter 3: The Role of Knowledge in Human Progress

It began with observation. This led to experiments. They confirmed theories.

### Key Excerpts"""

        result, report = draft_service.repair_first_paragraph_pronouns(text)

        # All three pronouns should be replaced with "Knowledge"
        assert "It began" not in result
        assert "This led" not in result
        assert "They confirmed" not in result
        # Replaced with knowledge
        assert "Knowledge began" in result
        assert "Knowledge led" in result
        assert "Knowledge confirmed" in result
        assert report["sentences_repaired"] >= 3
