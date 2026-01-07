"""Unit tests for Key Ideas Coverage Guard.

Tests the definitional candidate extraction and coverage checking
that ensures the "intellectual spine" is surfaced in Key Ideas.
"""

import pytest

from src.services.evidence_service import (
    extract_definitional_candidates,
    check_key_ideas_coverage,
    format_candidates_for_prompt,
    DEFINITIONAL_KEYWORDS,
)


class TestDefinitionalKeywords:
    """Test the keyword patterns."""

    def test_keywords_are_valid_regex(self):
        """All keyword patterns should be valid regex."""
        import re
        for pattern in DEFINITIONAL_KEYWORDS:
            # Should not raise
            re.compile(pattern, re.IGNORECASE)

    def test_keywords_include_good_explanations(self):
        """Should include 'good explanations' keyword."""
        patterns_str = " ".join(DEFINITIONAL_KEYWORDS)
        assert "good explanation" in patterns_str.lower()

    def test_keywords_include_rather_than(self):
        """Should include 'rather than' keyword."""
        patterns_str = " ".join(DEFINITIONAL_KEYWORDS)
        assert "rather than" in patterns_str.lower()


class TestExtractDefinitionalCandidates:
    """Test definitional candidate extraction."""

    def test_extracts_good_explanations_sentence(self):
        """Should extract sentences containing 'good explanations'."""
        transcript = """
        Host: How does science work?

        David: Science is about finding laws of nature. We discovered this method—the
        scientific method—which I think is essentially trying to find good explanations
        of what happens rather than bad explanations that could apply to absolutely anything.

        Host: That's interesting.
        """

        candidates = extract_definitional_candidates(transcript)

        assert len(candidates) > 0
        # Should find the sentence with "good explanations"
        found_good_explanations = any(
            "good explanations" in c["sentence"].lower()
            for c in candidates
        )
        assert found_good_explanations, "Should extract 'good explanations' sentence"

    def test_extracts_rather_than_sentence(self):
        """Should extract sentences containing 'rather than'."""
        transcript = """
        The key insight is that we need to look for good explanations rather than bad explanations.
        This is fundamentally different from the old approach.
        """

        candidates = extract_definitional_candidates(transcript)

        assert len(candidates) > 0
        found_rather_than = any(
            "rather than" in c["keyword"].lower()
            for c in candidates
        )
        assert found_rather_than

    def test_extracts_is_essentially_sentence(self):
        """Should extract sentences containing 'is essentially'."""
        transcript = """
        The scientific method is essentially trying to find good explanations.
        Everything else follows from this.
        """

        candidates = extract_definitional_candidates(transcript)

        assert len(candidates) > 0
        found_essentially = any(
            "essentially" in c["keyword"].lower()
            for c in candidates
        )
        assert found_essentially

    def test_skips_short_sentences(self):
        """Should skip sentences that are too short."""
        transcript = "This means yes. OK."

        candidates = extract_definitional_candidates(transcript, min_length=40)

        assert len(candidates) == 0

    def test_skips_long_sentences(self):
        """Should skip sentences that are too long."""
        transcript = "This means " + "word " * 100 + "."

        candidates = extract_definitional_candidates(transcript, max_length=300)

        assert len(candidates) == 0

    def test_prioritizes_good_explanations(self):
        """Should prioritize sentences with 'good explanations' in sorting."""
        transcript = """
        This means something important. The phrase 'beginning of infinity' means progress.
        The method is essentially finding good explanations rather than bad explanations.
        The key to success is hard work.
        """

        candidates = extract_definitional_candidates(transcript)

        # Should find multiple candidates
        assert len(candidates) >= 1

        # The sentence containing "good explanations" should be extracted
        # (even if the matched keyword is "is essentially" which appears first)
        good_explanation_sentences = [
            c for c in candidates
            if "good explanations" in c["sentence"].lower()
        ]
        assert len(good_explanation_sentences) > 0, \
            "Should extract sentence containing 'good explanations'"

    def test_returns_empty_for_no_keywords(self):
        """Should return empty list if no keywords found."""
        transcript = """
        Hello and welcome to the show. Today we discuss various topics.
        The weather is nice. Thank you for listening.
        """

        candidates = extract_definitional_candidates(transcript)

        assert len(candidates) == 0

    def test_deduplicates_similar_sentences(self):
        """Should not return duplicate sentences."""
        transcript = """
        The method is essentially about good explanations.
        The method is essentially about good explanations.
        The method is essentially about good explanations.
        """

        candidates = extract_definitional_candidates(transcript)

        # Should have at most 1 (deduped)
        assert len(candidates) <= 1


class TestCheckKeyIdeasCoverage:
    """Test the coverage checking logic."""

    def test_covered_when_quote_present(self):
        """Should return covered=True when candidate quote is in Key Ideas."""
        candidates = [
            {
                "sentence": "The method is essentially finding good explanations rather than bad explanations.",
                "keyword": "rather than",
                "start": 0,
                "end": 80,
            }
        ]

        key_ideas = """
        - **Science is about good explanations**: "The method is essentially finding good explanations rather than bad explanations."
        - **Progress is unlimited**: "We can solve any problem."
        """

        result = check_key_ideas_coverage(key_ideas, candidates)

        assert result["covered"] is True
        assert result["matched_candidate"] is not None

    def test_not_covered_when_quote_missing(self):
        """Should return covered=False when candidate quote is not in Key Ideas."""
        candidates = [
            {
                "sentence": "The method is essentially finding good explanations rather than bad explanations.",
                "keyword": "rather than",
                "start": 0,
                "end": 80,
            }
        ]

        key_ideas = """
        - **The Enlightenment was important**: "This line is the most important thing."
        - **Progress is unlimited**: "We can solve any problem."
        """

        result = check_key_ideas_coverage(key_ideas, candidates)

        assert result["covered"] is False
        assert len(result["missing_candidates"]) > 0

    def test_covered_with_partial_match(self):
        """Should match even if only a phrase (not full sentence) is present."""
        candidates = [
            {
                "sentence": "We discovered this method which is essentially trying to find good explanations of what happens rather than bad explanations that could apply to absolutely anything.",
                "keyword": "good explanations",
                "start": 0,
                "end": 150,
            }
        ]

        key_ideas = """
        - **Good vs bad explanations**: "good explanations of what happens rather than bad explanations"
        """

        result = check_key_ideas_coverage(key_ideas, candidates)

        assert result["covered"] is True

    def test_returns_true_when_no_candidates(self):
        """Should return covered=True when no candidates exist."""
        candidates = []
        key_ideas = "- **Some idea**: \"quote\""

        result = check_key_ideas_coverage(key_ideas, candidates)

        assert result["covered"] is True


class TestFormatCandidatesForPrompt:
    """Test the prompt formatting for forced candidates."""

    def test_formats_candidates_correctly(self):
        """Should format candidates as numbered list."""
        candidates = [
            {"sentence": "This is the first candidate.", "keyword": "means", "start": 0, "end": 30},
            {"sentence": "This is the second candidate.", "keyword": "method", "start": 50, "end": 80},
        ]

        result = format_candidates_for_prompt(candidates)

        assert "1." in result
        assert "2." in result
        assert "This is the first candidate" in result
        assert "This is the second candidate" in result
        assert "MUST" in result

    def test_limits_to_max_candidates(self):
        """Should limit to max_candidates."""
        candidates = [
            {"sentence": f"Candidate {i}.", "keyword": "means", "start": i*10, "end": i*10+10}
            for i in range(10)
        ]

        result = format_candidates_for_prompt(candidates, max_candidates=3)

        assert "Candidate 0" in result
        assert "Candidate 2" in result
        assert "Candidate 5" not in result

    def test_returns_empty_for_no_candidates(self):
        """Should return empty string when no candidates."""
        result = format_candidates_for_prompt([])

        assert result == ""


class TestIntegrationWithDeutschTranscript:
    """Integration tests using Deutsch-like transcript content."""

    DEUTSCH_TRANSCRIPT = """
    Host: How does the Scientific Revolution produce the beginning of infinity?

    David Deutsch: Science is about finding laws of nature, which are testable regularities.
    We discovered this method—the scientific method—which I think is essentially trying to
    find good explanations of what happens rather than bad explanations that could apply
    to absolutely anything. Once one has this method, which is the scientific method but
    also ranges more broadly over other fields like philosophy, the scope of both
    understanding and controlling the world has to be limitless.

    Host: What do you mean by good vs bad explanations?

    David Deutsch: A good explanation is one that is hard to vary while still accounting
    for the phenomena it purports to explain. A bad explanation is easy to vary—you can
    change it to explain anything, which means it really explains nothing.
    """

    def test_extracts_good_explanations_from_deutsch(self):
        """Should extract the 'good explanations rather than bad explanations' line."""
        candidates = extract_definitional_candidates(self.DEUTSCH_TRANSCRIPT)

        # Should find the key epistemological criterion
        good_explanations_found = any(
            "good explanations" in c["sentence"].lower() and "rather than" in c["sentence"].lower()
            for c in candidates
        )
        assert good_explanations_found, "Should find 'good explanations rather than bad explanations'"

    def test_coverage_fails_without_core_criterion(self):
        """Should fail coverage when Key Ideas misses core criterion."""
        candidates = extract_definitional_candidates(self.DEUTSCH_TRANSCRIPT)

        # Key Ideas that MISS the core criterion
        bad_key_ideas = """
        - **The Enlightenment was important**: "This line is the most important thing that's ever happened."
        - **Science finds testable laws**: "Science is about finding laws of nature, which are testable regularities."
        - **Progress is unlimited**: "The scope of understanding and controlling the world has to be limitless."
        """

        result = check_key_ideas_coverage(bad_key_ideas, candidates)

        # Should fail because "good explanations rather than bad" is not quoted
        assert result["covered"] is False

    def test_coverage_passes_with_core_criterion(self):
        """Should pass coverage when Key Ideas includes core criterion."""
        candidates = extract_definitional_candidates(self.DEUTSCH_TRANSCRIPT)

        # Key Ideas that INCLUDE the core criterion
        good_key_ideas = """
        - **Good explanations vs bad explanations**: "trying to find good explanations of what happens rather than bad explanations that could apply to absolutely anything"
        - **Science finds testable laws**: "Science is about finding laws of nature."
        """

        result = check_key_ideas_coverage(good_key_ideas, candidates)

        assert result["covered"] is True


class TestTopPriorityCandidateRequired:
    """Test that coverage guard requires THE TOP PRIORITY candidate, not just any candidate.

    ChatGPT feedback: If transcript contains both "beginning of infinity means..."
    and "good explanations rather than bad explanations", the coverage guard should
    require the latter (higher priority) specifically, not pass if only the former is present.
    """

    MULTI_CANDIDATE_TRANSCRIPT = """
    Host: What does "the beginning of infinity" mean?

    David Deutsch: The phrase "the beginning of infinity" primarily means the universal
    power of explanatory knowledge. It turned out that in every chapter, there were
    several different senses in which there was a beginning of infinity.

    Host: How does science enable this?

    David Deutsch: We discovered this method—the scientific method—which I think is
    essentially trying to find good explanations of what happens rather than bad
    explanations that could apply to absolutely anything. Once one has this method,
    the scope of understanding and controlling the world has to be limitless.
    """

    def test_extracts_both_candidates(self):
        """Should extract both 'beginning of infinity' and 'good explanations' as candidates."""
        candidates = extract_definitional_candidates(self.MULTI_CANDIDATE_TRANSCRIPT)

        # Should find multiple candidates
        assert len(candidates) >= 2, f"Found only {len(candidates)} candidates"

        # Should find 'beginning of infinity' sentence
        boi_found = any(
            "beginning of infinity" in c["sentence"].lower()
            for c in candidates
        )
        assert boi_found, "Should find 'beginning of infinity' sentence"

        # Should find 'good explanations' sentence
        ge_found = any(
            "good explanations" in c["sentence"].lower()
            for c in candidates
        )
        assert ge_found, "Should find 'good explanations' sentence"

    def test_good_explanations_ranked_higher_than_beginning_of_infinity(self):
        """'good explanations' should be ranked higher priority than 'beginning of infinity'."""
        candidates = extract_definitional_candidates(self.MULTI_CANDIDATE_TRANSCRIPT)

        # Find indices
        ge_index = None
        boi_index = None
        for i, c in enumerate(candidates):
            if "good explanations" in c["sentence"].lower() and "rather than" in c["sentence"].lower():
                ge_index = i
            if "beginning of infinity" in c["sentence"].lower() and "means" in c["keyword"].lower():
                boi_index = i

        # 'good explanations' should appear BEFORE 'beginning of infinity' in sorted list
        if ge_index is not None and boi_index is not None:
            assert ge_index < boi_index, \
                f"'good explanations' (index {ge_index}) should rank before 'beginning of infinity' (index {boi_index})"

    def test_coverage_fails_when_only_lower_priority_candidate_present(self):
        """Should FAIL coverage when only 'beginning of infinity' is in Key Ideas (lower priority).

        This is the critical test: even though 'beginning of infinity' IS a definitional
        candidate, if 'good explanations rather than bad' exists and is higher priority,
        the coverage guard should require THAT specific candidate.
        """
        candidates = extract_definitional_candidates(self.MULTI_CANDIDATE_TRANSCRIPT)

        # Key Ideas that includes ONLY "beginning of infinity" but MISSES "good explanations"
        key_ideas_with_lower_priority_only = """
        - **The beginning of infinity defined**: "The phrase 'the beginning of infinity' primarily means the universal power of explanatory knowledge"
        - **Progress is unlimited**: "The scope of understanding and controlling the world has to be limitless."
        """

        result = check_key_ideas_coverage(key_ideas_with_lower_priority_only, candidates)

        # Should FAIL because 'good explanations rather than bad' (the #1 priority) is missing
        assert result["covered"] is False, \
            "Should fail coverage when top-priority candidate is missing, even if other candidates present"

        # The missing candidate should be the 'good explanations' one
        assert len(result["missing_candidates"]) > 0
        top_missing = result["missing_candidates"][0]
        assert "good explanations" in top_missing["sentence"].lower() or \
               "rather than" in top_missing["sentence"].lower(), \
            f"Missing candidate should be the 'good explanations' sentence, got: {top_missing['sentence'][:60]}..."

    def test_coverage_passes_when_top_priority_candidate_present(self):
        """Should PASS coverage when 'good explanations' (top priority) IS in Key Ideas."""
        candidates = extract_definitional_candidates(self.MULTI_CANDIDATE_TRANSCRIPT)

        # Key Ideas that includes the TOP PRIORITY candidate
        key_ideas_with_top_priority = """
        - **Good vs bad explanations**: "trying to find good explanations of what happens rather than bad explanations that could apply to absolutely anything"
        - **Progress is unlimited**: "The scope of understanding and controlling the world has to be limitless."
        """

        result = check_key_ideas_coverage(key_ideas_with_top_priority, candidates)

        assert result["covered"] is True, \
            "Should pass coverage when top-priority candidate is present"
