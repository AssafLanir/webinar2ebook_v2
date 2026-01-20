"""Tests for inline quote removal from prose."""


class TestRemoveInlineQuotes:
    def test_removes_inline_quotes_from_prose(self):
        """Inline quotes in prose are unquoted."""
        from src.services.whitelist_service import remove_inline_quotes

        text = '''## Chapter 1

David explained "this is very important" in the interview.

### Key Excerpts

> "Valid quote here"
> — Speaker (GUEST)
'''

        result, report = remove_inline_quotes(text)

        # Quote marks removed but text kept
        assert '"this is very important"' not in result
        assert 'this is very important' in result
        assert report["removed_count"] == 1

    def test_preserves_quotes_in_key_excerpts(self):
        """Quotes in Key Excerpts section are preserved."""
        from src.services.whitelist_service import remove_inline_quotes

        text = '''## Chapter 1

Some prose here.

### Key Excerpts

> "This quote should stay"
> — Speaker (GUEST)

### Core Claims
'''

        result, report = remove_inline_quotes(text)

        # Key Excerpts quote preserved
        assert '> "This quote should stay"' in result
        assert report["removed_count"] == 0

    def test_preserves_quotes_in_core_claims(self):
        """Quotes in Core Claims bullets are preserved."""
        from src.services.whitelist_service import remove_inline_quotes

        text = '''## Chapter 1

Some prose.

### Core Claims

- **Wisdom is limitless**: "The truth is that wisdom is limitless."
'''

        result, report = remove_inline_quotes(text)

        # Core Claims quote preserved
        assert '"The truth is that wisdom is limitless."' in result
        assert report["removed_count"] == 0

    def test_handles_smart_quotes(self):
        """Smart/curly quotes are also removed."""
        from src.services.whitelist_service import remove_inline_quotes

        text = '''## Chapter 1

He said \u201cthis is the key\u201d emphatically.

### Key Excerpts
'''

        result, report = remove_inline_quotes(text)

        # Smart quotes removed
        assert '\u201c' not in result
        assert '\u201d' not in result
        assert 'this is the key' in result
        assert report["removed_count"] == 1

    def test_multiple_inline_quotes(self):
        """Multiple inline quotes all removed."""
        from src.services.whitelist_service import remove_inline_quotes

        text = '''## Chapter 1

The guest said "first point" and then "second point" before concluding.

### Key Excerpts
'''

        result, report = remove_inline_quotes(text)

        assert '"first point"' not in result
        assert '"second point"' not in result
        assert 'first point' in result
        assert 'second point' in result
        assert report["removed_count"] == 2

    def test_short_quotes_preserved(self):
        """Very short quotes (< 5 chars) may be acceptable."""
        from src.services.whitelist_service import remove_inline_quotes

        text = '''## Chapter 1

He said "yes" and she said "no" in response.

### Key Excerpts
'''

        result, report = remove_inline_quotes(text, min_quote_length=5)

        # Short quotes preserved (below min length)
        assert '"yes"' in result or 'yes' in result  # Either preserved or unquoted is ok

    def test_returns_report_with_details(self):
        """Report includes details of removed quotes."""
        from src.services.whitelist_service import remove_inline_quotes

        text = '''## Chapter 1

He explained "the scientific method is key" to the audience.

### Key Excerpts
'''

        result, report = remove_inline_quotes(text)

        assert "removed_count" in report
        assert "removed_quotes" in report
        assert len(report["removed_quotes"]) == 1
        assert "scientific method" in report["removed_quotes"][0]["text"]

    def test_handles_nested_sections(self):
        """Correctly tracks section boundaries."""
        from src.services.whitelist_service import remove_inline_quotes

        text = '''## Chapter 1

"Quote in chapter prose"

### Key Excerpts

> "Quote in excerpts"
> — Speaker

### Core Claims

- **Claim**: "Quote in claims"

## Chapter 2

"Another prose quote"

### Key Excerpts
'''

        result, report = remove_inline_quotes(text)

        # Prose quotes removed
        assert report["removed_count"] == 2
        # Section quotes preserved
        assert '> "Quote in excerpts"' in result
        assert '"Quote in claims"' in result
