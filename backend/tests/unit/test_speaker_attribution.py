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

    def test_host_mentioning_speaker_not_clip(self):
        """Host mentioning a clip speaker should NOT become a CLIP.

        Regression test: Headers like "Stephen Hawking says fear them" are the
        host commenting, not actual Hawking clips.
        """
        markdown = """### You say don't fear them. Stephen Hawking says fear them.

**GUEST:** Yes, that is because we have to understand the lesson of universality.

### But what if the error is, to Stephen Hawking's fear, the destruction of our planet?

**GUEST:** Okay, I entirely agree with Stephen Hawking that we should hedge our bets.
"""
        result = fix_speaker_attribution(markdown)

        # These should remain as headers, NOT become CLIPs
        assert "### You say don't fear them. Stephen Hawking says fear them." in result
        assert "### But what if the error is" in result
        # Should NOT have CLIP labels for these host comments
        assert "**CLIP (Stephen Hawking):** You say don't fear" not in result
        assert "**CLIP (Stephen Hawking):** But what if" not in result

    def test_backward_clip_reference_not_intro(self):
        """Backward references to clips should NOT set clip context.

        Regression test: "We played the clip from Stephen Hawking" is a backward
        reference, not an intro. Headers after it should NOT become CLIPs.
        """
        markdown = """### We played the clip from Stephen Hawking. He talked about survival genes.

**GUEST:** The idea of an aggression gene is a misunderstanding.

### But our wars just got bigger after. Our wars just got larger, more deadly.

**GUEST:** If you think about the kind of things built into our genes...
"""
        result = fix_speaker_attribution(markdown)

        # The backward reference should stay as header
        assert "### We played the clip from Stephen Hawking" in result
        # The next header should NOT become a CLIP (no clip context from backward ref)
        assert "### But our wars just got bigger" in result
        assert "**CLIP (Stephen Hawking):** But our wars" not in result

    def test_guest_lines_after_clip_intro_become_clip(self):
        """GUEST lines after a clip intro should become CLIP labels.

        Critical: Prevents clip quotes from being attributed to Deutsch.
        """
        markdown = """### Here's the late astronomer Carl Sagan in the Cosmos series.

**GUEST:** Every human generation has asked about the origin and fate of the cosmos.

### David Deutsch, what do you say to that?

**GUEST:** I agree with Sagan's sentiment about cosmic curiosity.
"""
        result = fix_speaker_attribution(markdown)

        # Sagan's quote should become CLIP, not stay as GUEST
        assert "**CLIP (Carl Sagan):** Every human generation" in result
        assert "**GUEST:** Every human generation" not in result
        # Deutsch's response after the question should stay GUEST
        assert "**GUEST:** I agree with Sagan's" in result

    def test_multiple_guest_lines_in_clip_context(self):
        """Multiple GUEST lines after clip intro should all become CLIP."""
        markdown = """### Here's physicist Stephen Hawking speaking at Big Think.

**GUEST:** If we are the only intelligent beings in the galaxy, we should make sure we survive.

**GUEST:** But we are entering an increasingly dangerous period of our history.

### David Deutsch, what do you say?

**GUEST:** I disagree with Hawking's pessimism.
"""
        result = fix_speaker_attribution(markdown)

        # Both Hawking lines should become CLIP
        assert "**CLIP (Stephen Hawking):** If we are the only" in result
        assert "**CLIP (Stephen Hawking):** But we are entering" in result
        # Deutsch's response should stay GUEST
        assert "**GUEST:** I disagree with Hawking's" in result

    def test_clip_context_ends_at_caller(self):
        """Clip context should end when a CALLER line is encountered."""
        markdown = """### Here's Carl Sagan from Cosmos.

**GUEST:** The cosmos is all that is or was or ever will be.

### Dana in Boston, you're on the air.

**CALLER (Dana):** I loved that Sagan quote.
"""
        result = fix_speaker_attribution(markdown)

        # Sagan should be CLIP
        assert "**CLIP (Carl Sagan):** The cosmos is all" in result
        # Caller should stay as CALLER
        assert "**CALLER (Dana):** I loved that" in result


class TestClipGuestRegression:
    """Regression tests: GUEST must never contain clip speaker content."""

    def test_guest_never_contains_sagan_clip_content(self):
        """GUEST lines must not contain Carl Sagan clip quotes.

        This is a semantic error - it implies Deutsch said Sagan's words.
        """
        markdown = """### Let's hear from Carl Sagan in Cosmos.

**GUEST:** Every human generation has asked about the origin and fate of the cosmos. Ours is the first generation with a real chance of finding some of the answers.

### What do you think, David Deutsch?

**GUEST:** I find Sagan's optimism inspiring.
"""
        result = fix_speaker_attribution(markdown)

        # Extract all GUEST lines
        guest_lines = [line for line in result.split('\n') if line.startswith('**GUEST:**')]

        # No GUEST line should contain Sagan's famous clip quotes
        sagan_quotes = [
            "Every human generation has asked",
            "origin and fate of the cosmos",
            "edge of forever",
        ]
        for guest_line in guest_lines:
            for quote in sagan_quotes:
                assert quote not in guest_line, \
                    f"GUEST contains Sagan quote '{quote}': {guest_line}"

    def test_guest_never_contains_hawking_clip_content(self):
        """GUEST lines must not contain Stephen Hawking clip quotes.

        This is a semantic error - it implies Deutsch said Hawking's words.
        """
        markdown = """### Here's Stephen Hawking warning about human traits.

**GUEST:** If we are the only intelligent beings in the galaxy, we should make sure we survive and continue. But we are entering an increasingly dangerous period.

### David Deutsch, what do you say?

**GUEST:** I agree we should hedge our bets by colonizing space.
"""
        result = fix_speaker_attribution(markdown)

        # Extract all GUEST lines
        guest_lines = [line for line in result.split('\n') if line.startswith('**GUEST:**')]

        # No GUEST line should contain Hawking's famous clip quotes
        hawking_quotes = [
            "only intelligent beings in the galaxy",
            "increasingly dangerous period",
            "selfish and aggressive instincts",
        ]
        for guest_line in guest_lines:
            for quote in hawking_quotes:
                assert quote not in guest_line, \
                    f"GUEST contains Hawking quote '{quote}': {guest_line}"


class TestHostInterjections:
    """Test that short HOST interjections are detected and converted to headers."""

    def test_short_question_becomes_header(self):
        """Short questions labeled as GUEST should become headers."""
        markdown = """**GUEST:** The avoidance of hubris is what kept us suffering.

**GUEST:** But what about the environment?

**GUEST:** Well, I think that is not comparing like with like.
"""
        result = fix_speaker_attribution(markdown)

        # The short question should become a header
        assert "### But what about the environment?" in result
        # Long answers should stay as GUEST
        assert "**GUEST:** The avoidance of hubris" in result
        assert "**GUEST:** Well, I think that is not comparing" in result

    def test_short_but_pushback_becomes_header(self):
        """Very short 'But...' pushback should become headers."""
        markdown = """**GUEST:** Yes, that is because we have to understand universality.

**GUEST:** But our wars got bigger.

**GUEST:** If you think about the kind of things built into our genes...
"""
        result = fix_speaker_attribution(markdown)

        # Very short "But" pushback = host
        assert "### But our wars got bigger." in result
        # Regular GUEST stays
        assert "**GUEST:** Yes, that is because" in result

    def test_addressing_guest_becomes_header(self):
        """Lines addressing the guest directly should become headers."""
        markdown = """**GUEST:** Hi, I'm Dana.

**GUEST:** Professor Deutsch, what do you say to that?

**GUEST:** The avoidance of hubris is the thing that kept us suffering.
"""
        result = fix_speaker_attribution(markdown)

        # Addressing guest = host
        assert "### Professor Deutsch, what do you say to that?" in result
        # Others stay as GUEST
        assert "**GUEST:** Hi, I'm Dana" in result

    def test_long_response_stays_guest(self):
        """Long responses should stay as GUEST even with host-like patterns."""
        markdown = """**GUEST:** But the environment certainly looked better 50 years ago than it does today, and many species are going extinct because of human activity.
"""
        result = fix_speaker_attribution(markdown)

        # Long response stays GUEST (even though starts with "But")
        assert "**GUEST:** But the environment certainly" in result
        assert "### But the environment" not in result

    def test_you_mean_clarification_becomes_header(self):
        """Short 'You mean X' clarifications should become headers."""
        markdown = """**GUEST:** There can only be ones that have made more progress.

**GUEST:** You mean knowledge makers?

**GUEST:** Yes, broadly, exactly.
"""
        result = fix_speaker_attribution(markdown)

        # Short "You mean" = host
        assert "### You mean knowledge makers?" in result


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
