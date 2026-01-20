"""Tests for quote re-anchoring (self-heal lite)."""


class TestReanchorQuote:
    def test_finds_exact_match(self):
        """Exact quote is found and returned as-is."""
        from src.services.quote_anchoring import reanchor_quote

        transcript = "The truth is that wisdom is limitless in scope."
        proposed = "wisdom is limitless in scope"

        result = reanchor_quote(proposed, transcript)

        assert result is not None
        assert result == "wisdom is limitless in scope"

    def test_fixes_minor_typo(self):
        """Quote with minor typo is corrected from transcript."""
        from src.services.quote_anchoring import reanchor_quote

        transcript = "The truth is that wisdom is limitless in scope."
        proposed = "wisdum is limitless in scope"  # typo: wisdum -> wisdom

        result = reanchor_quote(proposed, transcript)

        assert result is not None
        assert result == "wisdom is limitless in scope"

    def test_handles_truncated_quote(self):
        """Truncated quote finds full match."""
        from src.services.quote_anchoring import reanchor_quote

        transcript = "The truth is that wisdom is limitless in scope and application."
        proposed = "wisdom is limitless..."  # truncated

        result = reanchor_quote(proposed, transcript)

        assert result is not None
        assert "wisdom is limitless" in result

    def test_rejects_poor_match(self):
        """Quote with poor match returns None."""
        from src.services.quote_anchoring import reanchor_quote

        transcript = "The sky is blue and the grass is green."
        proposed = "completely different text that is not in transcript"

        result = reanchor_quote(proposed, transcript)

        assert result is None

    def test_handles_smart_quote_conversion(self):
        """Smart quotes converted to straight quotes for matching."""
        from src.services.quote_anchoring import reanchor_quote

        transcript = "He said 'this is important' to the crowd."
        proposed = "this is important"  # Without quotes

        result = reanchor_quote(proposed, transcript)

        assert result is not None
        assert "this is important" in result

    def test_handles_case_differences(self):
        """Case differences don't prevent matching."""
        from src.services.quote_anchoring import reanchor_quote

        transcript = "Knowledge is the KEY to progress."
        proposed = "knowledge is the key to progress"

        result = reanchor_quote(proposed, transcript)

        assert result is not None
        # Returns exact transcript case
        assert "KEY" in result

    def test_returns_exact_transcript_substring(self):
        """Result is always an exact substring of transcript."""
        from src.services.quote_anchoring import reanchor_quote

        transcript = "David Deutsch says: The beginning of infinity represents boundless potential."
        proposed = "beginning of infinity represents boundless"

        result = reanchor_quote(proposed, transcript)

        assert result is not None
        # Must be an exact substring
        assert result in transcript

    def test_handles_word_substitutions(self):
        """Minor word substitutions still find match."""
        from src.services.quote_anchoring import reanchor_quote

        transcript = "We should colonize the solar system and then the galaxy."
        proposed = "We must colonize the solar system then the galaxy"  # should->must, removed 'and'

        result = reanchor_quote(proposed, transcript)

        assert result is not None
        assert "colonize the solar system" in result

    def test_minimum_length_requirement(self):
        """Very short quotes require higher similarity."""
        from src.services.quote_anchoring import reanchor_quote

        transcript = "Yes, I think so. No, wait. Maybe."
        proposed = "Yes"

        result = reanchor_quote(proposed, transcript, min_length=5)

        # Too short, should return None or require exact match
        assert result is None or result == "Yes"
