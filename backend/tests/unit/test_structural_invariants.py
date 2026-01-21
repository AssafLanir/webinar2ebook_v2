"""Structural invariants for Ideas Edition output.

These tests assert properties that must NEVER be violated in final output.
"""
import re

from src.services.structural_invariants import (
    find_empty_sections,
    find_inline_quote_violations,
)


class TestKeyExcerptsInvariant:
    """Key Excerpts header must never be followed by empty content."""

    def test_no_empty_key_excerpts_section(self):
        """### Key Excerpts must have content or not appear at all."""
        # Pattern: ### Key Excerpts followed by only whitespace until next heading
        empty_pattern = re.compile(
            r'### Key Excerpts\s*\n\s*(?=### |## |\Z)',
            re.MULTILINE
        )

        sample_bad = '''## Chapter 1

Prose here.

### Key Excerpts

### Core Claims
'''
        sample_good = '''## Chapter 1

Prose here.

### Key Excerpts

> "Valid quote here"
> — Speaker (GUEST)

### Core Claims
'''

        assert empty_pattern.search(sample_bad) is not None, "Bad sample should match"
        assert empty_pattern.search(sample_good) is None, "Good sample should not match"

    def test_detect_empty_key_excerpts_in_multi_chapter(self):
        """Detect empties across multiple chapters."""
        doc = '''## Chapter 1

### Key Excerpts

> "Quote"
> — Speaker (GUEST)

## Chapter 2

### Key Excerpts

### Core Claims

- **Claim**: Some claim here
'''
        empties = find_empty_sections(doc)
        assert len(empties) == 1
        assert empties[0]["chapter"] == 2
        assert empties[0]["section"] == "Key Excerpts"


class TestCoreClaimsInvariant:
    """Core Claims must have content or a placeholder."""

    def test_no_empty_core_claims_without_placeholder(self):
        """### Core Claims must have bullets or placeholder."""
        doc = '''## Chapter 1

### Core Claims

## Chapter 2
'''
        empties = find_empty_sections(doc)
        assert len(empties) == 1
        assert empties[0]["section"] == "Core Claims"

    def test_placeholder_is_acceptable(self):
        """Placeholder message is not considered 'empty'."""
        doc = '''## Chapter 1

### Core Claims

*No fully grounded claims available for this chapter.*

## Chapter 2
'''
        empties = find_empty_sections(doc)
        assert len(empties) == 0


class TestNoInlineQuotesInvariant:
    """Quotes only allowed in Key Excerpts and Core Claims."""

    def test_detects_inline_quotes_in_prose(self):
        """Quotes in narrative prose are violations."""
        doc = '''## Chapter 1

David said "this is important" in the interview.

### Key Excerpts

> "Valid quote"
> — Speaker (GUEST)
'''
        violations = find_inline_quote_violations(doc)
        assert len(violations) == 1
        assert "this is important" in violations[0]["quote"]

    def test_allows_quotes_in_key_excerpts(self):
        """Quotes inside Key Excerpts are fine."""
        doc = '''## Chapter 1

Prose without quotes.

### Key Excerpts

> "This quote is allowed"
> — Speaker (GUEST)

### Core Claims

- **Claim**: "This quote is also allowed"
'''
        violations = find_inline_quote_violations(doc)
        assert len(violations) == 0


class TestPlaceholderGlueInvariant:
    """No placeholder glue strings should appear in output."""

    def test_detects_excerpts_above_placeholder(self):
        """Detect '[as discussed in the excerpts above]' placeholder."""
        from src.services.structural_invariants import find_placeholder_glue

        doc = '''## Chapter 1

The speaker's perspective on knowledge is illuminating [as discussed in the excerpts above].

### Key Excerpts

> "Knowledge is infinite"
> — David (GUEST)
'''
        violations = find_placeholder_glue(doc)
        assert len(violations) == 1
        assert "as discussed in the excerpts above" in violations[0]["text"].lower()

    def test_detects_various_placeholder_patterns(self):
        """Detect multiple placeholder glue patterns."""
        from src.services.structural_invariants import find_placeholder_glue

        doc = '''## Chapter 1

See the key excerpts for more detail.

As noted in the quotes above, this is important.

[See excerpt above]

### Key Excerpts
'''
        violations = find_placeholder_glue(doc)
        assert len(violations) >= 2

    def test_no_violations_in_clean_prose(self):
        """Clean prose has no placeholder glue."""
        from src.services.structural_invariants import find_placeholder_glue

        doc = '''## Chapter 1

The speaker articulates a compelling vision of infinite knowledge.
Progress comes not from certainty but from error correction.

### Key Excerpts

> "Knowledge is infinite"
> — David (GUEST)
'''
        violations = find_placeholder_glue(doc)
        assert len(violations) == 0


class TestVerbatimLeakInvariant:
    """No whitelist quotes should appear verbatim in prose (even unquoted)."""

    def test_detects_verbatim_quote_in_prose(self):
        """Detect whitelist quote appearing unquoted in prose."""
        from src.services.structural_invariants import find_verbatim_leaks

        whitelist_quotes = [
            "Knowledge without error correction is impossible",
            "We never reach final truth",
        ]

        doc = '''## Chapter 1

The central thesis is clear: knowledge without error correction is impossible.
This fundamentally reshapes how we think about progress.

### Key Excerpts

> "Knowledge without error correction is impossible"
> — David (GUEST)
'''
        violations = find_verbatim_leaks(doc, whitelist_quotes)
        assert len(violations) == 1
        assert violations[0]["chapter"] == 1
        assert "knowledge without error correction" in violations[0]["matched_text"].lower()

    def test_ignores_quotes_in_key_excerpts(self):
        """Verbatim text in Key Excerpts section is allowed."""
        from src.services.structural_invariants import find_verbatim_leaks

        whitelist_quotes = ["Knowledge is infinite"]

        doc = '''## Chapter 1

The discussion covers many topics.

### Key Excerpts

> "Knowledge is infinite"
> — David (GUEST)
'''
        violations = find_verbatim_leaks(doc, whitelist_quotes)
        assert len(violations) == 0

    def test_detects_partial_verbatim_substring(self):
        """Detect long substrings of whitelist quotes in prose."""
        from src.services.structural_invariants import find_verbatim_leaks

        whitelist_quotes = [
            "The growth of knowledge depends on conjecture and refutation cycles"
        ]

        doc = '''## Chapter 1

Progress depends on conjecture and refutation cycles as a core mechanism.

### Key Excerpts
'''
        violations = find_verbatim_leaks(doc, whitelist_quotes, min_substring_len=20)
        assert len(violations) == 1


class TestClaimsFallbackInvariant:
    """If chapter has excerpts, it must have claims or be merged."""

    def test_detects_chapter_with_excerpts_but_no_claims(self):
        """Chapter with >= 2 excerpts but placeholder claims is a violation."""
        from src.services.structural_invariants import find_claims_coverage_gaps

        doc = '''## Chapter 1

### Key Excerpts

> "First important quote here"
> — David (GUEST)

> "Second important quote here"
> — David (GUEST)

### Core Claims

*No fully grounded claims available for this chapter.*
'''
        gaps = find_claims_coverage_gaps(doc, min_excerpts_for_claims=2)
        assert len(gaps) == 1
        assert gaps[0]["chapter"] == 1
        assert gaps[0]["excerpt_count"] >= 2
        assert gaps[0]["claim_count"] == 0

    def test_passes_chapter_with_excerpts_and_claims(self):
        """Chapter with excerpts AND claims passes."""
        from src.services.structural_invariants import find_claims_coverage_gaps

        doc = '''## Chapter 1

### Key Excerpts

> "First important quote here"
> — David (GUEST)

> "Second important quote here"
> — David (GUEST)

### Core Claims

- **Claim**: Knowledge grows through error correction. "First important quote here"
'''
        gaps = find_claims_coverage_gaps(doc, min_excerpts_for_claims=2)
        assert len(gaps) == 0

    def test_passes_chapter_with_one_excerpt(self):
        """Chapter with only 1 excerpt doesn't require claims."""
        from src.services.structural_invariants import find_claims_coverage_gaps

        doc = '''## Chapter 1

### Key Excerpts

> "Single quote here"
> — David (GUEST)

### Core Claims

*No fully grounded claims available for this chapter.*
'''
        gaps = find_claims_coverage_gaps(doc, min_excerpts_for_claims=2)
        assert len(gaps) == 0


class TestShortSupportGateInvariant:
    """Claims must not be supported by very short acknowledgements."""

    def test_detects_yes_only_support(self):
        """Detect claims supported only by 'Yes.' or similar."""
        from src.services.structural_invariants import find_short_support_claims

        doc = '''## Chapter 1

### Core Claims

- **Claim**: The universe is fundamentally unpredictable. "Yes."
'''
        violations = find_short_support_claims(doc)
        assert len(violations) == 1
        assert violations[0]["support_text"] == "Yes."

    def test_detects_various_short_supports(self):
        """Detect No., OK., Right., Sure. as short supports."""
        from src.services.structural_invariants import find_short_support_claims

        doc = '''## Chapter 1

### Core Claims

- **Claim**: First claim here. "No."
- **Claim**: Second claim. "OK."
- **Claim**: Third claim. "Right."
- **Claim**: Fourth claim. "Sure."
'''
        violations = find_short_support_claims(doc)
        assert len(violations) == 4

    def test_passes_substantive_support(self):
        """Claims with substantive quotes pass."""
        from src.services.structural_invariants import find_short_support_claims

        doc = '''## Chapter 1

### Core Claims

- **Claim**: Knowledge grows through conjecture. "We make progress by proposing bold theories and then subjecting them to criticism."
'''
        violations = find_short_support_claims(doc)
        assert len(violations) == 0

    def test_passes_claim_without_quote(self):
        """Claims without quotes are handled separately."""
        from src.services.structural_invariants import find_short_support_claims

        doc = '''## Chapter 1

### Core Claims

- **Claim**: This is a claim without a supporting quote.
'''
        violations = find_short_support_claims(doc)
        assert len(violations) == 0


class TestDanglingAttributionInvariant:
    """No dangling attribution wrappers in final output."""

    def test_detects_dangling_argues(self):
        """Detect 'Deutsch argues,' at end of line."""
        from src.services.structural_invariants import find_dangling_attributions

        doc = '''## Chapter 1

The impact was profound. Deutsch argues,
The next sentence starts here.

### Key Excerpts
'''
        violations = find_dangling_attributions(doc)
        assert len(violations) == 1
        assert "Deutsch argues," in violations[0]["text"]

    def test_detects_dangling_notes_period(self):
        """Detect 'Deutsch notes.' as dangling attribution."""
        from src.services.structural_invariants import find_dangling_attributions

        doc = '''## Chapter 1

The discussion continues. Deutsch notes.
This creates confusion.

### Key Excerpts
'''
        violations = find_dangling_attributions(doc)
        assert len(violations) == 1
        assert "Deutsch notes." in violations[0]["text"]

    def test_detects_orphan_saying(self):
        """Detect orphan 'saying.' participial."""
        from src.services.structural_invariants import find_dangling_attributions

        doc = '''## Chapter 1

David Deutsch captures this idea, saying.
The next part continues.

### Key Excerpts
'''
        violations = find_dangling_attributions(doc)
        assert len(violations) == 1
        assert "saying." in violations[0]["text"]

    def test_passes_valid_attribution(self):
        """Valid attributions with content pass."""
        from src.services.structural_invariants import find_dangling_attributions

        doc = '''## Chapter 1

Deutsch argues that knowledge is infinite.
He notes the importance of error correction.

### Key Excerpts
'''
        violations = find_dangling_attributions(doc)
        assert len(violations) == 0


class TestTokenCorruptionInvariant:
    """No token corruption from bad replacements."""

    def test_detects_he_oxygen_pattern(self):
        """Detect 'he oxygen' corruption pattern."""
        from src.services.structural_invariants import find_token_corruption

        doc = '''## Chapter 1

The oxygen and H2O that people use will be generated by technology, he oxygen, showing how humans can transform barren landscapes.

### Key Excerpts
'''
        violations = find_token_corruption(doc)
        assert len(violations) >= 1
        assert any("he oxygen" in v["text"].lower() or v["pattern"] == "corrupted_article" for v in violations)

    def test_detects_double_punctuation(self):
        """Detect leftover double punctuation."""
        from src.services.structural_invariants import find_token_corruption

        doc = '''## Chapter 1

The argument is clear,. This shows the connection.

### Key Excerpts
'''
        violations = find_token_corruption(doc)
        assert len(violations) >= 1
        assert any(v["pattern"] == "double_punctuation" for v in violations)

    def test_passes_clean_prose(self):
        """Clean prose passes without violations."""
        from src.services.structural_invariants import find_token_corruption

        doc = '''## Chapter 1

The oxygen and H2O that people need will be generated by human technology. This shows remarkable progress.

### Key Excerpts
'''
        violations = find_token_corruption(doc)
        assert len(violations) == 0
