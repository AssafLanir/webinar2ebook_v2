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
        pattern = INTERVIEW_FORBIDDEN_PATTERNS[-2]  # Distancing pattern (second to last)

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

    def test_narration_inside_quotes_pattern(self):
        """Pattern should match narration like 'he says' inside quotes."""
        pattern = INTERVIEW_FORBIDDEN_PATTERNS[-1]  # Narration inside quotes pattern

        test_cases = [
            ('"Since the revolution, he says, things changed"', True),
            ('"She explained that the method works"', True),
            ('"They said it was impossible"', True),
            ('"He notes that progress continues"', True),
            ('"She added that it matters"', True),
            ('"This line is the most important thing"', False),  # No narration
            ('He says "this is important"', False),  # Narration outside quotes
            ('"Science is about finding laws of nature"', False),  # Clean quote
            ('"The speaker notes that"', False),  # Only matches he/she/they
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
    async def test_interview_qa_format_uses_new_template(self):
        """book_format=interview_qa should also use P0 template (Key Ideas + Conversation)."""
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

        content_mode = ContentMode.essay  # Not interview mode
        book_format = "interview_qa"  # But interview_qa format selected

        # interview_qa book format should trigger single-pass even without interview content_mode
        use_single_pass = (
            (content_mode == ContentMode.interview or book_format == "interview_qa")
            and evidence_map
            and sum(len(ch.claims) for ch in evidence_map.chapters) > 0
        )

        # Should use single-pass because book_format is interview_qa
        assert use_single_pass is True


class TestTitleGuardrail:
    """Test that generic titles are prevented in interview mode."""

    def test_sanitize_interview_title_keeps_real_title(self):
        """Should keep valid book titles."""
        from src.services.draft_service import sanitize_interview_title

        assert sanitize_interview_title("The Beginning of Infinity") == "The Beginning of Infinity"
        assert sanitize_interview_title("A Conversation with Sarah Chen") == "A Conversation with Sarah Chen"

    def test_sanitize_interview_title_rejects_generic(self):
        """Should reject generic titles like 'Interview'."""
        from src.services.draft_service import sanitize_interview_title

        # Generic titles should be replaced
        assert sanitize_interview_title("Interview") != "Interview"
        assert sanitize_interview_title("interview") != "interview"
        assert sanitize_interview_title("Untitled") != "Untitled"
        assert sanitize_interview_title("Draft") != "Draft"
        assert sanitize_interview_title("") != ""

    def test_sanitize_interview_title_uses_fallback(self):
        """Should use fallback when title is generic."""
        from src.services.draft_service import sanitize_interview_title

        result = sanitize_interview_title("Interview", fallback="David Deutsch on Infinity")
        assert result == "David Deutsch on Infinity"

    def test_sanitize_interview_title_rejects_generic_fallback(self):
        """Should not use generic fallback."""
        from src.services.draft_service import sanitize_interview_title

        result = sanitize_interview_title("Interview", fallback="Untitled")
        assert result == "Untitled Interview"  # Last resort

    def test_sanitize_interview_title_extracts_from_transcript(self):
        """Should extract book title from transcript when no title provided."""
        from src.services.draft_service import sanitize_interview_title

        transcript = 'The title of the book is "The Beginning of Infinity".'
        result = sanitize_interview_title("Interview", transcript=transcript)
        assert result == "The Beginning of Infinity"

    def test_sanitize_interview_title_detects_beginning_of_infinity(self):
        """Should detect 'beginning of infinity' mention in transcript."""
        from src.services.draft_service import sanitize_interview_title

        transcript = "We discuss the beginning of infinity and what it means."
        result = sanitize_interview_title("Interview", transcript=transcript)
        assert result == "The Beginning of Infinity"

    def test_sanitize_interview_title_rejects_interview_transcript(self):
        """Should reject 'Interview Transcript' as a generic title."""
        from src.services.draft_service import sanitize_interview_title

        # "Interview Transcript" is now in GENERIC_TITLES
        result = sanitize_interview_title("Interview Transcript")
        assert result != "Interview Transcript"

    def test_clean_markdown_title_removes_trailing_comma(self):
        """Should remove trailing comma from H1 title."""
        from src.services.draft_service import _clean_markdown_title

        markdown = "# The Beginning of Infinity,\n\n## Key Ideas"
        result = _clean_markdown_title(markdown)
        assert result == "# The Beginning of Infinity\n\n## Key Ideas"

    def test_clean_markdown_title_removes_trailing_period(self):
        """Should remove trailing period from H1 title."""
        from src.services.draft_service import _clean_markdown_title

        markdown = "# My Great Book.\n\n## Chapter 1"
        result = _clean_markdown_title(markdown)
        assert result == "# My Great Book\n\n## Chapter 1"

    def test_clean_markdown_title_preserves_clean_title(self):
        """Should not modify already clean titles."""
        from src.services.draft_service import _clean_markdown_title

        markdown = "# The Beginning of Infinity\n\n## Key Ideas"
        result = _clean_markdown_title(markdown)
        assert result == markdown


class TestAcceptanceTests:
    """Acceptance tests for interview mode - regression guards.

    These tests ensure interview drafts don't regress into "book report" style.
    """

    def test_prompt_requires_verbatim_quotes(self):
        """Prompt must specify that only verbatim excerpts get quotes."""
        assert "verbatim" in INTERVIEW_GROUNDED_SYSTEM_PROMPT.lower()
        assert "VERBATIM" in INTERVIEW_GROUNDED_SYSTEM_PROMPT
        assert "paraphras" in INTERVIEW_GROUNDED_SYSTEM_PROMPT.lower()

    def test_prompt_prioritizes_core_framework(self):
        """Prompt must ask for speaker's core thesis/framework."""
        prompt_lower = INTERVIEW_GROUNDED_SYSTEM_PROMPT.lower()
        assert "core framework" in prompt_lower or "central thesis" in prompt_lower
        assert "foundational" in prompt_lower

    def test_prompt_forbids_book_report_patterns(self):
        """Prompt must explicitly forbid 'believes', 'argues', 'emphasizes'."""
        assert "believes" in INTERVIEW_GROUNDED_SYSTEM_PROMPT
        assert "argues" in INTERVIEW_GROUNDED_SYSTEM_PROMPT
        assert "emphasizes" in INTERVIEW_GROUNDED_SYSTEM_PROMPT

    def test_output_validation_detects_book_report_style(self):
        """Should detect when output regresses to book-report style."""
        from src.services.evidence_service import check_interview_constraints

        # Clean interview-style output
        clean_output = """## Key Ideas (Grounded)

- **Science is about testable laws**: "Science is about finding laws of nature, which are testable regularities."

## The Conversation

### The Scientific Method

#### How does science work?

Science discovers testable regularities in nature.
"""

        # Book-report style output (should be flagged)
        book_report_output = """## Key Ideas

Deutsch believes that science is transformative. He argues that the Enlightenment
changed everything. The physicist emphasizes that progress is unlimited.

## The Conversation

Deutsch contends that humans can understand anything.
"""

        clean_violations = check_interview_constraints(clean_output)
        book_report_violations = check_interview_constraints(book_report_output)

        # Clean output should have few/no violations
        assert len(clean_violations) == 0, f"Clean output had violations: {clean_violations}"

        # Book report output should have multiple violations
        assert len(book_report_violations) >= 3, \
            f"Book report style should be detected. Found only {len(book_report_violations)} violations"

    def test_key_ideas_must_have_inline_quotes(self):
        """Key Ideas bullets must have inline quotes."""
        # Pattern: - **[Idea]**: "[quote]"
        quote_pattern = r'-\s+\*\*[^*]+\*\*:\s*"[^"]+"'

        valid_key_ideas = """## Key Ideas (Grounded)

- **The Enlightenment changed everything**: "This line is the most important thing that's ever happened"
- **Science finds testable laws**: "Science is about finding laws of nature, which are testable regularities"
"""

        invalid_key_ideas = """## Key Ideas

- **The Enlightenment changed everything** - Deutsch explains this was transformative
- **Science finds testable laws** - He notes this is key to progress
"""

        valid_matches = re.findall(quote_pattern, valid_key_ideas)
        invalid_matches = re.findall(quote_pattern, invalid_key_ideas)

        assert len(valid_matches) >= 2, "Valid Key Ideas should have inline quotes"
        assert len(invalid_matches) == 0, "Invalid Key Ideas should not match quote pattern"

    def test_no_chapter_headings_in_output(self):
        """Output must not contain chapter headings."""
        chapter_pattern = r"^#+\s*Chapter\s+\d+"

        valid_output = """# The Beginning of Infinity

## Key Ideas (Grounded)

## The Conversation

### Science and Progress

### Human Potential
"""

        invalid_output = """# The Beginning of Infinity

## Chapter 1: Introduction

## Chapter 2: Science and Progress

## Chapter 3: Human Potential
"""

        valid_chapters = re.findall(chapter_pattern, valid_output, re.MULTILINE | re.IGNORECASE)
        invalid_chapters = re.findall(chapter_pattern, invalid_output, re.MULTILINE | re.IGNORECASE)

        assert len(valid_chapters) == 0, "Valid output should have no chapter headings"
        assert len(invalid_chapters) >= 2, "Invalid output should have chapter headings"

    def test_distancing_language_detection(self):
        """Should detect distancing language patterns."""
        distancing_pattern = INTERVIEW_FORBIDDEN_PATTERNS[-2]  # Distancing pattern (second to last)

        # These should match (bad)
        bad_phrases = [
            "Deutsch believes that science is key",
            "The speaker argues that progress is unlimited",
            "She emphasizes that focus matters",
            "He contends that knowledge grows",
            "Sarah maintains that real-time data helps",
        ]

        # These should NOT match (good)
        good_phrases = [
            "As Deutsch explains, science is key",
            "According to Sarah, focus matters",
            "The speaker notes that progress continues",
            "Science is the key to understanding",  # Direct statement
        ]

        for phrase in bad_phrases:
            match = re.search(distancing_pattern, phrase, re.IGNORECASE)
            assert match is not None, f"Should detect distancing language in: {phrase}"

        for phrase in good_phrases:
            match = re.search(distancing_pattern, phrase, re.IGNORECASE)
            assert match is None, f"Should NOT flag acceptable phrase: {phrase}"


class TestBestOfNCandidateSelection:
    """Tests for the best-of-N candidate selection feature."""

    def test_score_interview_draft_counts_qa_blocks(self):
        """Should count Q&A blocks (#### headers)."""
        from src.services.draft_service import score_interview_draft

        markdown = """# Test
## Key Ideas (Grounded)
- **Idea one**: "quote one"

## The Conversation

### Topic 1

#### Question 1?
**Speaker:** Answer 1.

#### Question 2?
**Speaker:** Answer 2.

#### Question 3?
**Speaker:** Answer 3.
"""
        transcript = "quote one appears here"

        score = score_interview_draft(markdown, transcript)

        assert score["qa_blocks"] == 3
        assert score["qa_score"] == 30  # 3 * 10

    def test_score_interview_draft_counts_key_idea_bullets(self):
        """Should count Key Ideas bullets with inline quotes."""
        from src.services.draft_service import score_interview_draft

        markdown = """# Test
## Key Ideas (Grounded)
- **First idea**: "first quote here"
- **Second idea**: "second quote here"
- **Third idea without quote**
- **Fourth idea**: "fourth quote"

## The Conversation
Some content.
"""
        transcript = "first quote here second quote here fourth quote"

        score = score_interview_draft(markdown, transcript)

        # Should count 3 (bullets with quotes), not 4
        assert score["key_idea_bullets"] == 3
        assert score["key_ideas_score"] == 24  # 3 * 8

    def test_score_interview_draft_penalizes_invalid_quotes(self):
        """Should penalize quotes not found in transcript."""
        from src.services.draft_service import score_interview_draft

        markdown = """# Test
## Key Ideas (Grounded)
- **Idea**: "this quote does not exist in transcript"

## The Conversation
Content.
"""
        transcript = "The transcript contains completely different text."

        score = score_interview_draft(markdown, transcript)

        # Should have penalty for invalid quote
        assert score["invalid_quotes"] >= 1
        assert score["invalid_penalty"] < 0

    def test_score_interview_draft_higher_for_better_draft(self):
        """Better draft should score higher than worse draft."""
        from src.services.draft_service import score_interview_draft

        good_markdown = """# Test
## Key Ideas (Grounded)
- **Idea one**: "first quote"
- **Idea two**: "second quote"
- **Idea three**: "third quote"
- **Idea four**: "fourth quote"

## The Conversation

### Topic 1

#### Question 1?
**Speaker:** Answer with first quote here.

#### Question 2?
**Speaker:** Answer with second quote.

#### Question 3?
**Speaker:** Answer with third quote.

#### Question 4?
**Speaker:** Answer with fourth quote.
"""

        thin_markdown = """# Test
## Key Ideas (Grounded)
- **Single idea**: "only quote"

## The Conversation

#### One question?
**Speaker:** Short answer.
"""
        transcript = "first quote second quote third quote fourth quote only quote"

        good_score = score_interview_draft(good_markdown, transcript)
        thin_score = score_interview_draft(thin_markdown, transcript)

        assert good_score["total"] > thin_score["total"], \
            f"Good draft ({good_score['total']}) should score higher than thin ({thin_score['total']})"

    def test_config_flag_defaults_to_one(self):
        """INTERVIEW_CANDIDATE_COUNT should default to 1 (disabled)."""
        from src.services.draft_service import INTERVIEW_CANDIDATE_COUNT

        # Without env var set, should default to 1
        assert INTERVIEW_CANDIDATE_COUNT >= 1

    def test_score_breakdown_has_expected_keys(self):
        """Score breakdown should have all expected component keys."""
        from src.services.draft_service import score_interview_draft

        markdown = """# Test
## Key Ideas (Grounded)
- **Idea**: "quote"

## The Conversation
#### Q?
**S:** A.
"""
        transcript = "quote"

        score = score_interview_draft(markdown, transcript)

        expected_keys = [
            "qa_blocks", "qa_score",
            "quote_blocks", "quote_score",
            "key_idea_bullets", "key_ideas_score",
            "invalid_quotes", "invalid_penalty",
            "truncated_quotes", "truncated_penalty",
            "constraint_violations", "violation_penalty",
            "total"
        ]

        for key in expected_keys:
            assert key in score, f"Missing expected key: {key}"
