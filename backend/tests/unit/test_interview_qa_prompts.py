"""Tests for Interview Q&A format prompts (T004).

Verifies:
- INTERVIEW_QA_SYSTEM_PROMPT contains Q&A structure instructions
- build_interview_qa_chapter_prompt includes question extraction
- Prompts forbid takeaways/action steps
"""

import pytest

from src.services.prompts import (
    INTERVIEW_QA_SYSTEM_PROMPT,
    build_interview_qa_system_prompt,
    build_interview_qa_chapter_prompt,
)
from src.models import ChapterPlan


class TestInterviewQASystemPrompt:
    """Test INTERVIEW_QA_SYSTEM_PROMPT content."""

    def test_prompt_exists(self):
        """INTERVIEW_QA_SYSTEM_PROMPT should be defined."""
        assert INTERVIEW_QA_SYSTEM_PROMPT is not None
        assert len(INTERVIEW_QA_SYSTEM_PROMPT) > 100

    def test_contains_qa_structure_instructions(self):
        """Prompt should instruct Q&A structure."""
        prompt = INTERVIEW_QA_SYSTEM_PROMPT
        assert "question" in prompt.lower()
        assert "###" in prompt  # Questions at h3 level
        assert "##" in prompt   # Topics at h2 level

    def test_contains_speaker_voice_instruction(self):
        """Prompt should instruct preserving speaker voice."""
        prompt = INTERVIEW_QA_SYSTEM_PROMPT
        assert any(word in prompt.lower() for word in ["voice", "quote", "speaker"])

    def test_forbids_takeaways(self):
        """Prompt should forbid Key Takeaways sections."""
        prompt = INTERVIEW_QA_SYSTEM_PROMPT
        assert "takeaway" in prompt.lower()
        assert any(word in prompt.lower() for word in ["do not", "never", "forbid", "avoid"])

    def test_forbids_action_steps(self):
        """Prompt should forbid Action Steps sections."""
        prompt = INTERVIEW_QA_SYSTEM_PROMPT
        assert "action" in prompt.lower()


class TestBuildInterviewQASystemPrompt:
    """Test build_interview_qa_system_prompt function."""

    def test_includes_book_title(self):
        """System prompt should include book title."""
        prompt = build_interview_qa_system_prompt(
            book_title="Conversations with David Deutsch",
            speaker_name="David Deutsch",
        )
        assert "Conversations with David Deutsch" in prompt

    def test_includes_speaker_name(self):
        """System prompt should include speaker name."""
        prompt = build_interview_qa_system_prompt(
            book_title="Test Book",
            speaker_name="Sarah Chen",
        )
        assert "Sarah Chen" in prompt


class TestBuildInterviewQAChapterPrompt:
    """Test build_interview_qa_chapter_prompt function."""

    @pytest.fixture
    def sample_chapter_plan(self):
        """Create sample chapter plan for tests."""
        return ChapterPlan(
            chapter_number=1,
            title="On the Nature of Knowledge",
            outline_item_id="ch1",
            goals=["Explore epistemology concepts"],
            key_points=["Knowledge is conjectural", "Error correction is key"],
            transcript_segments=[],
            estimated_words=800,
        )

    @pytest.fixture
    def sample_transcript(self):
        """Sample interview transcript segment."""
        return """Host: What is the nature of knowledge?

David: Knowledge is fundamentally conjectural. We never prove things true -
we can only refute them. This is Popper's key insight.

Host: How does this apply to everyday thinking?

David: It means we should embrace criticism and error correction. Our best
theories are the ones that have survived the most criticism."""

    def test_includes_transcript(self, sample_chapter_plan, sample_transcript):
        """User prompt should include transcript segment."""
        prompt = build_interview_qa_chapter_prompt(
            chapter_plan=sample_chapter_plan,
            transcript_segment=sample_transcript,
            speaker_name="David Deutsch",
        )
        assert "conjectural" in prompt
        assert "Popper" in prompt

    def test_instructs_question_headers(self, sample_chapter_plan, sample_transcript):
        """Prompt should instruct using questions as headers."""
        prompt = build_interview_qa_chapter_prompt(
            chapter_plan=sample_chapter_plan,
            transcript_segment=sample_transcript,
            speaker_name="David Deutsch",
        )
        assert "question" in prompt.lower()
        assert "###" in prompt or "header" in prompt.lower()

    def test_includes_speaker_name(self, sample_chapter_plan, sample_transcript):
        """Prompt should include speaker name for attribution."""
        prompt = build_interview_qa_chapter_prompt(
            chapter_plan=sample_chapter_plan,
            transcript_segment=sample_transcript,
            speaker_name="David Deutsch",
        )
        assert "David Deutsch" in prompt

    def test_requests_blockquotes(self, sample_chapter_plan, sample_transcript):
        """Prompt should request blockquotes for notable statements."""
        prompt = build_interview_qa_chapter_prompt(
            chapter_plan=sample_chapter_plan,
            transcript_segment=sample_transcript,
            speaker_name="David Deutsch",
        )
        assert any(word in prompt.lower() for word in ["blockquote", ">", "notable", "quote"])
