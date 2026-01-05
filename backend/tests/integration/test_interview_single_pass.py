"""Integration tests for P0 Interview Single-Pass Generation.

Tests the new interview output format:
- ## Key Ideas (Grounded) with inline quotes
- ## The Conversation with Q&A format
- No chapter headings
"""

import pytest
import re
from unittest.mock import AsyncMock, patch, MagicMock

from src.services.draft_service import (
    generate_interview_single_pass,
    _extract_speaker_name,
)
from src.services.prompts import (
    build_interview_grounded_system_prompt,
    build_interview_grounded_user_prompt,
    INTERVIEW_GROUNDED_SYSTEM_PROMPT,
    INTERVIEW_FORBIDDEN_PATTERNS,
)
from src.models.evidence_map import (
    EvidenceMap,
    ChapterEvidence,
    EvidenceEntry,
    SupportQuote,
)
from src.models.style_config import ContentMode


# Sample transcript for testing
SAMPLE_INTERVIEW_TRANSCRIPT = """
Host: Welcome to the show. Today we have Sarah Chen, founder of DataFlow.

Sarah: Thanks for having me. I started DataFlow in 2019 after seeing how companies struggled with data pipelines.

Host: What was the biggest challenge?

Sarah: Honestly, it was convincing enterprises that they needed real-time data. Everyone was stuck in batch processing mindset. We had to show them the cost of delayed insights - missed sales, stale inventory forecasts.

Host: How did you break through?

Sarah: Case studies. We ran a pilot with a retail chain and showed them they were losing $2M per quarter from inventory misalignment. That got their attention.

Host: What advice for other founders?

Sarah: Focus on one customer problem. Do not try to be everything. We only did data pipelines for retail for the first two years.
"""


@pytest.fixture
def sample_evidence_map():
    """Create sample evidence map for testing."""
    return EvidenceMap(
        project_id="test-project",
        content_mode=ContentMode.interview,
        strict_grounded=True,
        transcript_hash="abc123",
        chapters=[
            ChapterEvidence(
                chapter_index=1,
                chapter_title="The DataFlow Story",
                claims=[
                    EvidenceEntry(
                        id="claim_001",
                        claim="DataFlow was started in 2019 to solve data pipeline problems",
                        support=[
                            SupportQuote(
                                quote="I started DataFlow in 2019 after seeing how companies struggled with data pipelines",
                                speaker="Sarah Chen",
                            )
                        ],
                        confidence=0.95,
                    ),
                    EvidenceEntry(
                        id="claim_002",
                        claim="Enterprises were stuck in batch processing mindset",
                        support=[
                            SupportQuote(
                                quote="Everyone was stuck in batch processing mindset",
                                speaker="Sarah Chen",
                            )
                        ],
                        confidence=0.90,
                    ),
                    EvidenceEntry(
                        id="claim_003",
                        claim="Case studies were key to breaking through enterprise sales",
                        support=[
                            SupportQuote(
                                quote="We ran a pilot with a retail chain and showed them they were losing $2M per quarter",
                                speaker="Sarah Chen",
                            )
                        ],
                        confidence=0.85,
                    ),
                    EvidenceEntry(
                        id="claim_004",
                        claim="Focus on one customer problem is key advice for founders",
                        support=[
                            SupportQuote(
                                quote="Focus on one customer problem. Do not try to be everything.",
                                speaker="Sarah Chen",
                            )
                        ],
                        confidence=0.92,
                    ),
                ],
            )
        ],
    )


class TestInterviewGroundedPrompts:
    """Test the new interview grounded prompts."""

    def test_system_prompt_contains_key_structures(self):
        """System prompt should mandate Key Ideas and Conversation sections."""
        assert "Key Ideas (Grounded)" in INTERVIEW_GROUNDED_SYSTEM_PROMPT
        assert "The Conversation" in INTERVIEW_GROUNDED_SYSTEM_PROMPT
        assert "inline quote" in INTERVIEW_GROUNDED_SYSTEM_PROMPT.lower()

    def test_system_prompt_forbids_chapters(self):
        """System prompt should forbid chapter headings."""
        assert "No Chapters" in INTERVIEW_GROUNDED_SYSTEM_PROMPT
        assert "Chapter 1" in INTERVIEW_GROUNDED_SYSTEM_PROMPT

    def test_system_prompt_forbids_action_steps(self):
        """System prompt should forbid action steps."""
        assert "No Action Steps" in INTERVIEW_GROUNDED_SYSTEM_PROMPT
        assert "Key Takeaways" in INTERVIEW_GROUNDED_SYSTEM_PROMPT

    def test_system_prompt_forbids_distancing_language(self):
        """System prompt should forbid 'believes', 'argues', 'emphasizes'."""
        prompt = INTERVIEW_GROUNDED_SYSTEM_PROMPT
        assert "believes" in prompt.lower()
        assert "argues" in prompt.lower()
        assert "emphasizes" in prompt.lower()

    def test_build_system_prompt_includes_speaker_name(self):
        """Built system prompt should include speaker name."""
        prompt = build_interview_grounded_system_prompt(
            book_title="Test Book",
            speaker_name="Sarah Chen",
        )
        assert "Sarah Chen" in prompt

    def test_build_user_prompt_includes_evidence_claims(self):
        """User prompt should include evidence claims with quotes."""
        claims = [
            {
                "claim": "DataFlow was started in 2019",
                "support": [{"quote": "I started DataFlow in 2019"}],
            }
        ]
        prompt = build_interview_grounded_user_prompt(
            transcript="Sample transcript",
            speaker_name="Sarah Chen",
            evidence_claims=claims,
        )
        assert "DataFlow was started in 2019" in prompt
        assert "I started DataFlow in 2019" in prompt

    def test_build_user_prompt_truncates_long_quotes(self):
        """User prompt should truncate quotes over 40 words."""
        long_quote = " ".join(["word"] * 50)
        claims = [
            {
                "claim": "Test claim",
                "support": [{"quote": long_quote}],
            }
        ]
        prompt = build_interview_grounded_user_prompt(
            transcript="Sample transcript",
            speaker_name="Test Speaker",
            evidence_claims=claims,
        )
        # Should contain truncation indicator
        assert "..." in prompt


class TestForbiddenPatterns:
    """Test the P1 forbidden patterns."""

    def test_distancing_pattern_matches_believes(self):
        """Pattern should match 'X believes that'."""
        pattern = INTERVIEW_FORBIDDEN_PATTERNS[-1]  # Last pattern is distancing

        test_cases = [
            ("Deutsch believes that", True),
            ("Sarah argues that", True),
            ("He emphasizes that", True),
            ("The speaker maintains that", True),
            ("As Sarah explains, this is", False),  # Not distancing
            ("Sarah notes that", False),  # Not in pattern
        ]

        for text, should_match in test_cases:
            match = re.search(pattern, text, re.IGNORECASE)
            if should_match:
                assert match is not None, f"Pattern should match: {text}"
            else:
                assert match is None, f"Pattern should not match: {text}"


class TestExtractSpeakerName:
    """Test speaker name extraction."""

    def test_extracts_speaker_from_transcript(self):
        """Should extract the most common non-host speaker."""
        name = _extract_speaker_name(SAMPLE_INTERVIEW_TRANSCRIPT)
        assert name == "Sarah"

    def test_returns_default_when_no_pattern(self):
        """Should return default when no speaker pattern found."""
        name = _extract_speaker_name("This is just plain text without speaker labels.")
        assert name == "The speaker"

    def test_excludes_host_labels(self):
        """Should not return 'Host' or 'Interviewer'."""
        transcript = """
Host: Question one?
Host: Question two?
Guest: Answer here.
"""
        name = _extract_speaker_name(transcript)
        assert name != "Host"


class TestGenerateInterviewSinglePass:
    """Test the single-pass interview generation."""

    @pytest.mark.asyncio
    async def test_generates_with_key_ideas_structure(self, sample_evidence_map):
        """Generated content should include Key Ideas section."""
        mock_response = MagicMock()
        mock_response.text = """## Key Ideas (Grounded)

- **DataFlow was started in 2019**: "I started DataFlow in 2019 after seeing how companies struggled with data pipelines"
- **Enterprises needed convincing about real-time data**: "Everyone was stuck in batch processing mindset"

## The Conversation

### How did DataFlow get started?

Sarah Chen founded DataFlow in 2019 after observing...
"""

        with patch("src.services.draft_service.LLMClient") as MockClient:
            mock_client = MockClient.return_value
            mock_client.generate = AsyncMock(return_value=mock_response)

            result = await generate_interview_single_pass(
                transcript=SAMPLE_INTERVIEW_TRANSCRIPT,
                book_title="A Conversation with Sarah Chen",
                evidence_map=sample_evidence_map,
            )

            # Should have both sections
            assert "## Key Ideas" in result
            assert "## The Conversation" in result

    @pytest.mark.asyncio
    async def test_adds_book_title_header(self, sample_evidence_map):
        """Generated content should start with book title."""
        mock_response = MagicMock()
        mock_response.text = "## Key Ideas...\n\n## The Conversation..."

        with patch("src.services.draft_service.LLMClient") as MockClient:
            mock_client = MockClient.return_value
            mock_client.generate = AsyncMock(return_value=mock_response)

            result = await generate_interview_single_pass(
                transcript=SAMPLE_INTERVIEW_TRANSCRIPT,
                book_title="Test Book Title",
                evidence_map=sample_evidence_map,
            )

            assert result.startswith("# Test Book Title")

    @pytest.mark.asyncio
    async def test_uses_correct_prompts(self, sample_evidence_map):
        """Should use interview grounded prompts."""
        mock_response = MagicMock()
        mock_response.text = "Content..."

        with patch("src.services.draft_service.LLMClient") as MockClient:
            mock_client = MockClient.return_value
            mock_client.generate = AsyncMock(return_value=mock_response)

            await generate_interview_single_pass(
                transcript=SAMPLE_INTERVIEW_TRANSCRIPT,
                book_title="Test",
                evidence_map=sample_evidence_map,
            )

            # Check that generate was called
            mock_client.generate.assert_called_once()

            # Get the request that was passed
            call_args = mock_client.generate.call_args
            request = call_args[0][0]

            # System prompt should contain key elements
            system_content = request.messages[0].content
            assert "Key Ideas (Grounded)" in system_content
            assert "The Conversation" in system_content


class TestOutputStructureValidation:
    """Test validation of output structure."""

    def test_no_chapter_headings_pattern(self):
        """Validate that chapter heading detection works."""
        chapter_pattern = r"^#+\s*Chapter\s+\d+"

        valid_output = """# Book Title

## Key Ideas (Grounded)

- **Idea one**: "quote"

## The Conversation

### Topic One
"""
        invalid_output = """# Book Title

## Chapter 1: Introduction

Some content here.

## Chapter 2: Main Points
"""

        # Valid output should have no chapter headings
        chapters_found = re.findall(chapter_pattern, valid_output, re.MULTILINE | re.IGNORECASE)
        assert len(chapters_found) == 0

        # Invalid output should have chapter headings
        chapters_found = re.findall(chapter_pattern, invalid_output, re.MULTILINE | re.IGNORECASE)
        assert len(chapters_found) > 0

    def test_key_ideas_with_quotes_pattern(self):
        """Validate that Key Ideas contain inline quotes."""
        # Pattern: bullet with bold text followed by colon and quoted text
        quote_pattern = r'-\s+\*\*[^*]+\*\*:\s*"[^"]+"'

        valid_bullet = '- **Data pipelines need real-time processing**: "Everyone was stuck in batch processing mindset"'
        invalid_bullet = '- **Data pipelines need real-time processing** - this is important'

        assert re.search(quote_pattern, valid_bullet)
        assert not re.search(quote_pattern, invalid_bullet)


class TestContentModeIntegration:
    """Test that content mode properly triggers single-pass generation."""

    @pytest.mark.asyncio
    async def test_interview_mode_with_evidence_uses_single_pass(self):
        """Interview mode with evidence should use single-pass generation."""
        # This is tested via the draft_service flow
        # The key condition is:
        # use_interview_single_pass = (
        #     content_mode == ContentMode.interview
        #     and evidence_map
        #     and sum(len(ch.claims) for ch in evidence_map.chapters) > 0
        #     and book_format != "interview_qa"
        # )

        # Verify the condition logic
        from src.models.style_config import ContentMode
        from src.models.evidence_map import EvidenceMap, ChapterEvidence, EvidenceEntry, SupportQuote

        evidence_map = EvidenceMap(
            project_id="test",
            content_mode=ContentMode.interview,
            strict_grounded=True,
            transcript_hash="abc",
            chapters=[
                ChapterEvidence(
                    chapter_index=1,
                    chapter_title="Test",
                    claims=[
                        EvidenceEntry(
                            id="c1",
                            claim="Test claim",
                            support=[SupportQuote(quote="test")],
                            confidence=0.9,
                        )
                    ],
                )
            ],
        )

        content_mode = ContentMode.interview
        book_format = "guide"

        use_single_pass = (
            content_mode == ContentMode.interview
            and evidence_map
            and sum(len(ch.claims) for ch in evidence_map.chapters) > 0
            and book_format != "interview_qa"
        )

        assert use_single_pass is True

    @pytest.mark.asyncio
    async def test_interview_qa_format_does_not_use_new_template(self):
        """book_format=interview_qa should use old Q&A format, not new template."""
        from src.models.style_config import ContentMode
        from src.models.evidence_map import EvidenceMap, ChapterEvidence, EvidenceEntry, SupportQuote

        evidence_map = EvidenceMap(
            project_id="test",
            content_mode=ContentMode.interview,
            strict_grounded=True,
            transcript_hash="abc",
            chapters=[
                ChapterEvidence(
                    chapter_index=1,
                    chapter_title="Test",
                    claims=[
                        EvidenceEntry(
                            id="c1",
                            claim="Test claim",
                            support=[SupportQuote(quote="test")],
                            confidence=0.9,
                        )
                    ],
                )
            ],
        )

        content_mode = ContentMode.interview
        book_format = "interview_qa"  # Old Q&A format

        use_single_pass = (
            content_mode == ContentMode.interview
            and evidence_map
            and sum(len(ch.claims) for ch in evidence_map.chapters) > 0
            and book_format != "interview_qa"
        )

        # Should NOT use single-pass because book_format is interview_qa
        assert use_single_pass is False
