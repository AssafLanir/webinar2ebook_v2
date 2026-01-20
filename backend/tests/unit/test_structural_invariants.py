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
