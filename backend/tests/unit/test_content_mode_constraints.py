"""Unit tests for content mode constraints (Spec 009 US2).

Tests for:
- T013: Interview mode constraint checking
- Forbidden pattern detection
- Content mode prompt generation
"""

import pytest

from src.services.evidence_service import (
    check_interview_constraints,
    InterviewConstraintViolation,
)
from src.services.prompts import (
    INTERVIEW_FORBIDDEN_PATTERNS,
    INTERVIEW_MODE_CONSTRAINTS,
    ESSAY_MODE_PROMPT,
    TUTORIAL_MODE_PROMPT,
    get_content_mode_prompt,
)


class TestInterviewForbiddenPatterns:
    """Tests for INTERVIEW_FORBIDDEN_PATTERNS regex list (T023)."""

    def test_detects_action_steps(self):
        """Test detection of action step patterns."""
        texts = [
            "Here are the key action steps you should follow.",
            "Key Action Steps for Success",
            "Take these action items home with you.",
        ]

        for text in texts:
            violations = check_interview_constraints(text)
            assert len(violations) > 0, f"Should detect: {text}"

    def test_detects_how_to_instructions(self):
        """Test detection of how-to patterns."""
        texts = [
            "Here are the steps to get started with the process.",
            "How to begin implementing this strategy.",
            "First, you should create an account.",
            "Second, you need to configure the settings.",
        ]

        for text in texts:
            violations = check_interview_constraints(text)
            assert len(violations) > 0, f"Should detect: {text}"

    def test_detects_biographical_patterns(self):
        """Test detection of biographical content."""
        texts = [
            "John was born in 1980 in New York.",
            "She graduated from Stanford University.",
            "He attended Harvard Business School.",
            "Her early life was marked by challenges.",
        ]

        for text in texts:
            violations = check_interview_constraints(text)
            assert len(violations) > 0, f"Should detect: {text}"

    def test_detects_motivational_platitudes(self):
        """Test detection of generic motivational content."""
        texts = [
            "Just believe in yourself and anything is possible.",
            "Never give up on your dreams.",
            "The key to success is persistence.",
            "Anyone can achieve this with dedication.",
        ]

        for text in texts:
            violations = check_interview_constraints(text)
            assert len(violations) > 0, f"Should detect: {text}"

    def test_allows_valid_interview_content(self):
        """Test that valid interview content passes."""
        texts = [
            "In the interview, John shared his perspective on market trends.",
            "The speaker explained that their team focuses on user research.",
            "According to the guest, the biggest challenge was scaling.",
            '"I think the industry is moving towards automation," said the CEO.',
        ]

        for text in texts:
            violations = check_interview_constraints(text)
            assert len(violations) == 0, f"Should not flag: {text}"


class TestCheckInterviewConstraints:
    """Tests for check_interview_constraints function (T024)."""

    def test_returns_violation_details(self):
        """Test that violations include all required details."""
        text = "The key action steps are simple."

        violations = check_interview_constraints(text)

        assert len(violations) >= 1
        violation = violations[0]
        assert "pattern" in violation
        assert "matched_text" in violation
        assert "start" in violation
        assert "end" in violation
        assert "context" in violation

    def test_returns_empty_for_clean_text(self):
        """Test empty list for constraint-compliant text."""
        text = """
        The speaker shared their insights about the current market situation.
        They explained that their company has been focusing on innovation.
        "We've seen tremendous growth in the past year," they noted.
        """

        violations = check_interview_constraints(text)

        assert len(violations) == 0

    def test_detects_multiple_violations(self):
        """Test detection of multiple violations in same text."""
        text = """
        Here are the key action steps:
        First, you should create an account.
        Second, you need to set up your profile.
        The key to success is believing in yourself.
        """

        violations = check_interview_constraints(text)

        # Should detect multiple issues
        assert len(violations) >= 2

    def test_raises_on_violation_when_requested(self):
        """Test raising exception on violation."""
        text = "Here are the key action steps for you."

        with pytest.raises(InterviewConstraintViolation):
            check_interview_constraints(text, raise_on_violation=True)

    def test_includes_context_around_match(self):
        """Test that context includes surrounding text."""
        text = "This is some text. Here are the key action steps to follow. More text here."

        violations = check_interview_constraints(text)

        assert len(violations) >= 1
        # Context should include surrounding text
        assert len(violations[0]["context"]) > len(violations[0]["matched_text"])


class TestContentModePrompts:
    """Tests for content mode prompt templates (T025-T027)."""

    def test_interview_mode_constraints_content(self):
        """Test INTERVIEW_MODE_CONSTRAINTS has required elements."""
        assert "INTERVIEW MODE" in INTERVIEW_MODE_CONSTRAINTS
        assert "DO NOT include" in INTERVIEW_MODE_CONSTRAINTS
        assert "Action Steps" in INTERVIEW_MODE_CONSTRAINTS
        assert "biographical" in INTERVIEW_MODE_CONSTRAINTS.lower()
        assert "DO include" in INTERVIEW_MODE_CONSTRAINTS
        assert "quotes" in INTERVIEW_MODE_CONSTRAINTS.lower()

    def test_essay_mode_prompt_content(self):
        """Test ESSAY_MODE_PROMPT has required elements."""
        assert "ESSAY MODE" in ESSAY_MODE_PROMPT
        assert "argument" in ESSAY_MODE_PROMPT.lower()
        assert "evidence" in ESSAY_MODE_PROMPT.lower()

    def test_tutorial_mode_prompt_content(self):
        """Test TUTORIAL_MODE_PROMPT has required elements."""
        assert "TUTORIAL MODE" in TUTORIAL_MODE_PROMPT
        assert "step" in TUTORIAL_MODE_PROMPT.lower()
        assert "instruction" in TUTORIAL_MODE_PROMPT.lower()

    def test_get_content_mode_prompt_interview(self):
        """Test getting interview mode prompt."""
        prompt = get_content_mode_prompt("interview")
        assert prompt == INTERVIEW_MODE_CONSTRAINTS

    def test_get_content_mode_prompt_essay(self):
        """Test getting essay mode prompt."""
        prompt = get_content_mode_prompt("essay")
        assert prompt == ESSAY_MODE_PROMPT

    def test_get_content_mode_prompt_tutorial(self):
        """Test getting tutorial mode prompt."""
        prompt = get_content_mode_prompt("tutorial")
        assert prompt == TUTORIAL_MODE_PROMPT

    def test_get_content_mode_prompt_unknown_defaults_to_interview(self):
        """Test unknown mode defaults to interview."""
        prompt = get_content_mode_prompt("unknown_mode")
        assert prompt == INTERVIEW_MODE_CONSTRAINTS


class TestForbiddenPatternRegex:
    """Tests for INTERVIEW_FORBIDDEN_PATTERNS regex validity."""

    def test_all_patterns_are_valid_regex(self):
        """Test that all patterns compile without error."""
        import re

        for pattern in INTERVIEW_FORBIDDEN_PATTERNS:
            try:
                re.compile(pattern)
            except re.error as e:
                pytest.fail(f"Invalid regex pattern '{pattern}': {e}")

    def test_patterns_are_case_insensitive(self):
        """Test patterns work case-insensitively."""
        test_cases = [
            ("KEY ACTION STEPS", True),
            ("Key Action Steps", True),
            ("key action steps", True),
            ("HOW TO GET STARTED", True),
            ("How To Get Started", True),
        ]

        for text, should_match in test_cases:
            violations = check_interview_constraints(text)
            if should_match:
                assert len(violations) > 0, f"Should match (case insensitive): {text}"


class TestConstraintEdgeCases:
    """Edge case tests for constraint checking."""

    def test_empty_text(self):
        """Test with empty text."""
        violations = check_interview_constraints("")
        assert len(violations) == 0

    def test_whitespace_only(self):
        """Test with whitespace only."""
        violations = check_interview_constraints("   \n\t  ")
        assert len(violations) == 0

    def test_special_characters(self):
        """Test with special characters."""
        text = "!@#$%^&*()[]{}|;':\",./<>?"
        violations = check_interview_constraints(text)
        assert len(violations) == 0

    def test_unicode_text(self):
        """Test with unicode characters."""
        text = "The speaker said, 'Innovation is key' — a profound insight."
        violations = check_interview_constraints(text)
        assert len(violations) == 0

    def test_very_long_text(self):
        """Test with very long text."""
        # Generate long valid text
        text = "The speaker shared insights. " * 1000

        violations = check_interview_constraints(text)
        assert len(violations) == 0

    def test_multiline_text(self):
        """Test multiline text with violation."""
        text = """
        Line one is fine.
        Line two is also okay.
        Line three has key action steps.
        Line four is fine again.
        """

        violations = check_interview_constraints(text)
        assert len(violations) >= 1


class TestTranscriptExemption:
    """Tests for verbatim transcript exemption (false positive fix)."""

    def test_verbatim_quote_not_flagged_when_in_transcript(self):
        """Test that 'I believe that' is NOT flagged when it's in the transcript."""
        transcript = "David Deutsch: I believe that the Enlightenment has tried to happen several times."
        draft = "**David Deutsch:** I believe that the Enlightenment has tried to happen several times."

        violations = check_interview_constraints(draft, transcript=transcript)

        assert len(violations) == 0, "Verbatim quotes from transcript should not be flagged"

    def test_fabricated_phrase_still_flagged_when_not_in_transcript(self):
        """Test that 'I believe that' IS flagged when NOT in transcript."""
        transcript = "David Deutsch: The Enlightenment was a pivotal moment in history."
        draft = "The speaker believes that progress is inevitable."

        violations = check_interview_constraints(draft, transcript=transcript)

        assert len(violations) >= 1, "Fabricated attribution phrases should be flagged"

    def test_without_transcript_all_patterns_flagged(self):
        """Test backward compatibility: without transcript, all patterns flagged."""
        draft = "The speaker believes that we can achieve anything."

        violations = check_interview_constraints(draft)  # No transcript

        assert len(violations) >= 1, "Without transcript, should flag patterns"

    def test_partial_match_not_exempt(self):
        """Test that partial matches are not exempt (context must match)."""
        transcript = "Host: Do you believe that? David: Yes, I do believe that."
        # Draft uses same words but different context
        draft = "The author believes that his methodology is superior."

        violations = check_interview_constraints(draft, transcript=transcript)

        # "believes that" appears in both but context differs
        assert len(violations) >= 1, "Different context should still be flagged"

    def test_case_insensitive_transcript_matching(self):
        """Test that transcript matching is case-insensitive."""
        transcript = "DAVID DEUTSCH: I BELIEVE THAT THE ENLIGHTENMENT..."
        draft = "**David Deutsch:** I believe that the Enlightenment..."

        violations = check_interview_constraints(draft, transcript=transcript)

        assert len(violations) == 0, "Case should not affect transcript matching"

    def test_whitespace_normalized_in_transcript_matching(self):
        """Test that whitespace differences don't break matching."""
        transcript = "David   Deutsch:   I   believe   that   the   Enlightenment..."
        draft = "**David Deutsch:** I believe that the Enlightenment..."

        violations = check_interview_constraints(draft, transcript=transcript)

        assert len(violations) == 0, "Whitespace differences should be normalized"

    def test_multiple_patterns_some_verbatim_some_not(self):
        """Test mixed case: some patterns verbatim, some fabricated."""
        # Transcript has both "I believe that" and "the key to success"
        # but draft only quotes "I believe that" verbatim
        transcript = "David: I believe that progress is important. We must keep trying."
        draft = """
        **David:** I believe that progress is important.
        The key to success is never giving up.
        """

        violations = check_interview_constraints(draft, transcript=transcript)

        # "I believe that" is verbatim (context matches) - not flagged
        # "key to success" is fabricated - should be flagged
        # Check that at least one violation exists (the fabricated one)
        assert len(violations) >= 1

        # Verify the verbatim one is NOT in violations
        violation_texts = [v["matched_text"].lower() for v in violations]
        assert not any("i believe that" in v for v in violation_texts), \
            "Verbatim 'I believe that' should not appear in violations"
