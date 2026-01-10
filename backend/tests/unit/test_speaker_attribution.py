"""Tests for speaker attribution heuristics.

Ensures callers are never mislabeled as GUEST.
"""

import pytest
from src.services.draft_service import fix_speaker_attribution


class TestCallerDetection:
    """Test caller intro detection and relabeling."""

    def test_dana_caller_detected(self):
        """Dana's speech should be labeled as CALLER, not GUEST."""
        markdown = """# The Beginning of Infinity

## The Conversation

### David Deutsch, please stand by. Let me bring our listeners in. Dana in South Wellfleet, Massachusetts, you're on the air with David Deutsch in Oxford, England. Welcome, Dana. You're on the air.

**GUEST:** Hi, Tom. Mr. Deutsch, given our record of hubris and the resulting plunder of this planet, I really hope your thesis is wrong.

### Dana, let us pick it up. David Deutsch, what do you say?

**GUEST:** The avoidance of hubris and the glorification of humility is the thing that kept us suffering for hundreds of thousands of years.
"""
        result = fix_speaker_attribution(markdown)

        # Dana's speech should be CALLER, not GUEST
        assert "**CALLER (Dana):** Hi, Tom." in result
        # Deutsch's response should still be GUEST
        assert "**GUEST:** The avoidance of hubris" in result
        # Dana should NOT be labeled as GUEST
        assert "**GUEST:** Hi, Tom." not in result

    def test_joe_caller_detected(self):
        """Joe's speech should be labeled as CALLER, not GUEST."""
        markdown = """### David Deutsch, let's go straight to our listeners. Joe in Farmville, Virginia. Joe, you're on the air with David Deutsch.

**GUEST:** I have a question for Mr. Deutsch. Before that, let me make a comment.

### You've got a specific question about that, Joe. Give it to us.

**GUEST:** Yes. The idea is that because of the expansion of the universe, all the galaxies are going away from us.
"""
        result = fix_speaker_attribution(markdown)

        # Joe's speeches should be CALLER
        assert "**CALLER (Joe):** I have a question" in result
        assert "**CALLER (Joe):** Yes. The idea is" in result
        # Should NOT be labeled as GUEST
        assert "**GUEST:** I have a question" not in result

    def test_vj_caller_detected(self):
        """VJ calling from Cambridge should be detected."""
        markdown = """### VJ is calling from Cambridge, Massachusetts. VJ, you're on the air with David Deutsch. Thanks for calling.

**GUEST:** Hi, Tom. I think that Professor Deutsch's thesis is deeply misguided.

### VJ, standby. David Deutsch, what do you say?

**GUEST:** Okay. To deal with the first question first...
"""
        result = fix_speaker_attribution(markdown)

        # VJ's speech should be CALLER
        assert "**CALLER (VJ):** Hi, Tom. I think" in result
        # Deutsch's response should be GUEST
        assert "**GUEST:** Okay. To deal with" in result

    def test_guest_remains_guest_outside_caller_context(self):
        """GUEST labels should remain when not in a caller context."""
        markdown = """### What is the significance of the scientific method?

**GUEST:** Science is about finding laws of nature, which are testable regularities.

### How does progress continue?

**GUEST:** After the Enlightenment, it was the exact opposite.
"""
        result = fix_speaker_attribution(markdown)

        # Both should remain as GUEST (no caller context)
        assert "**GUEST:** Science is about" in result
        assert "**GUEST:** After the Enlightenment" in result


class TestHostTransition:
    """Test that host transitions end caller segments."""

    def test_host_transition_ends_caller_segment(self):
        """After host says 'David Deutsch, what do you say', GUEST is Deutsch."""
        markdown = """### Dana in South Wellfleet, you're on the air.

**GUEST:** Hi, Tom. I hope your thesis is wrong.

### Dana, I'll put that to David Deutsch, what do you say to these observations?

**GUEST:** The avoidance of hubris is the thing that kept us suffering.
"""
        result = fix_speaker_attribution(markdown)

        # Dana should be CALLER
        assert "**CALLER (Dana):** Hi, Tom." in result
        # After host transition, response is GUEST (Deutsch)
        assert "**GUEST:** The avoidance of hubris" in result


class TestEdgeCases:
    """Test edge cases and safety."""

    def test_empty_markdown(self):
        """Empty markdown should return empty."""
        result = fix_speaker_attribution("")
        assert result == ""

    def test_no_guest_labels(self):
        """Markdown without GUEST labels should pass through unchanged."""
        markdown = """# Title

## Key Ideas

- Point one
- Point two
"""
        result = fix_speaker_attribution(markdown)
        assert result == markdown

    def test_multiple_callers_in_sequence(self):
        """Multiple callers should each be detected separately."""
        markdown = """### Dana in Boston, you're on the air.

**GUEST:** Hi, I'm Dana.

### Dana, let me pick it up with our guest.

**GUEST:** Thank you for the question.

### Joe in New York, you're on the air.

**GUEST:** Hi, I'm Joe.

### Joe, David Deutsch, what do you say?

**GUEST:** Well, to answer Joe's question...
"""
        result = fix_speaker_attribution(markdown)

        # Dana should be CALLER (Dana)
        assert "**CALLER (Dana):** Hi, I'm Dana" in result
        # Joe should be CALLER (Joe)
        assert "**CALLER (Joe):** Hi, I'm Joe" in result
        # Deutsch's responses should be GUEST
        assert "**GUEST:** Thank you for the question" in result
        assert "**GUEST:** Well, to answer Joe's" in result
