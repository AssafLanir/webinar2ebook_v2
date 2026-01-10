"""Tests for speaker attribution heuristics.

Ensures callers are never mislabeled as GUEST.
Tests for caller persistence, disambiguation, header sanity, and clip detection.
"""

import pytest
from src.services.draft_service import (
    fix_speaker_attribution,
    _fix_speaker_labels,
    _fix_malformed_headers,
    _fix_clip_headers,
)


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

### Joe, you're breaking up, but I think we've got it. David Deutsch, in that case, how do we get out there?

**GUEST:** Yes. I only heard part of that question, but I think I understood what it was.
"""
        result = fix_speaker_attribution(markdown)

        # Joe's speeches should be CALLER
        assert "**CALLER (Joe):** I have a question" in result
        # Second Joe speech after host comment should also be CALLER
        assert "**CALLER (Joe):** Yes. The idea is" in result
        # Deutsch's response should be GUEST
        assert "**GUEST:** Yes. I only heard" in result

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


class TestCallerPersistence:
    """Test that caller mode persists correctly until explicit Deutsch handoff."""

    def test_caller_persists_through_host_comment(self):
        """Caller segment should persist through host comments like 'I'll put that to'."""
        markdown = """### Dana in South Wellfleet, you're on the air.

**GUEST:** Hi, Tom. I hope your thesis is wrong.

### Dana, I'll put that to David Deutsch, but he's kind of suggesting it is inevitable.

**GUEST:** Well, he's handing a sword then to the religious fundamentalists.

### Dana, let us pick it up. David Deutsch, what do you say to these observations?

**GUEST:** The avoidance of hubris is the thing that kept us suffering.
"""
        result = fix_speaker_attribution(markdown)

        # Dana's first speech
        assert "**CALLER (Dana):** Hi, Tom." in result
        # Dana's SECOND speech should also be CALLER (persistence through host comment)
        assert "**CALLER (Dana):** Well, he's handing" in result
        # Deutsch's response after explicit handoff
        assert "**GUEST:** The avoidance of hubris" in result

    def test_caller_persists_through_followup_question(self):
        """Caller segment persists when host asks caller to continue."""
        markdown = """### Joe in Farmville, Virginia. Joe, you're on the air.

**GUEST:** I have a question for Mr. Deutsch.

### You've got a specific question about that, Joe. Give it to us.

**GUEST:** Yes. The idea is that because of the expansion...

### Joe, you're breaking up. David Deutsch, how do we get out there?

**GUEST:** The exact implications are not well known yet.
"""
        result = fix_speaker_attribution(markdown)

        # Both Joe speeches should be CALLER
        assert "**CALLER (Joe):** I have a question" in result
        assert "**CALLER (Joe):** Yes. The idea is" in result
        # Deutsch's response
        assert "**GUEST:** The exact implications" in result


class TestCallerDisambiguation:
    """Test disambiguation of caller names that might conflict with guest name."""

    def test_david_in_boston_is_caller_not_deutsch(self):
        """'David in Boston' should be recognized as a caller, not confused with David Deutsch."""
        markdown = """### Let me get one more right here. David in Boston. David, thank you for calling.

**GUEST:** Yeah, thanks for having me on. Mr. Deutsch, I'm certainly a fan of science.

### David, let us pick it up. David Deutsch, what do you say?

**GUEST:** First of all, you're grossly underestimating how bad the past was.
"""
        result = fix_speaker_attribution(markdown)

        # "David in Boston" should be CALLER (David)
        assert "**CALLER (David):** Yeah, thanks for having" in result
        # Deutsch's response should be GUEST
        assert "**GUEST:** First of all" in result


class TestHeaderSanity:
    """Test that malformed headers are converted to text."""

    def test_non_question_header_becomes_text(self):
        """A ### header that doesn't end with ? followed by GUEST continuation becomes text."""
        markdown = """### What is new about what I said?

**GUEST:** To answer your question...

### Now, what is new about what I said, to answer your second question, is simply listen to the other commenters.

**GUEST:** Yes, exactly. They are saying that gaining control is impossible.
"""
        result = fix_speaker_attribution(markdown)

        # The malformed header should become GUEST text
        assert "**GUEST:** Now, what is new about" in result
        # Should NOT remain as a header
        assert "### Now, what is new about" not in result


class TestClipDetection:
    """Test that external clips are labeled correctly."""

    def test_carl_sagan_clip_detected(self):
        """Carl Sagan clips should be labeled as CLIP."""
        markdown = """### Let's hear from Carl Sagan in the Cosmos series.

### Every human generation has asked about the origin and fate of the cosmos.

### Or to put it another way, maybe at the beginning of infinity.
"""
        result = fix_speaker_attribution(markdown)

        # Sagan's quote should become CLIP
        assert "**CLIP (Carl Sagan):** Every human generation" in result

    def test_stephen_hawking_clip_detected(self):
        """Stephen Hawking clips should be labeled as CLIP."""
        markdown = """### Here's physicist Stephen Hawking, warning about human traits.

### If we are the only intelligent beings in the galaxy, we should make sure we survive.

### David Deutsch, what do you say to that?
"""
        result = fix_speaker_attribution(markdown)

        # Hawking's quote should become CLIP
        assert "**CLIP (Stephen Hawking):** If we are the only intelligent" in result


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
        assert "# Title" in result
        assert "## Key Ideas" in result

    def test_multiple_callers_in_sequence(self):
        """Multiple callers should each be detected separately."""
        markdown = """### Dana in Boston, you're on the air.

**GUEST:** Hi, I'm Dana.

### Dana, let me pick it up. David Deutsch, what do you say?

**GUEST:** Thank you for the question.

### Joe in New York, you're on the air.

**GUEST:** Hi, I'm Joe.

### Joe, standby. David Deutsch, what do you say?

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
