"""Tests for render guard (empty section header removal)."""


class TestStripEmptySectionHeaders:
    def test_removes_empty_key_excerpts(self):
        """Empty Key Excerpts header is removed."""
        from src.services.draft_service import strip_empty_section_headers

        doc = '''## Chapter 1: The Beginning

Some prose here.

### Key Excerpts

### Core Claims

- **Claim**: "Quote"
'''

        result = strip_empty_section_headers(doc)

        assert "### Key Excerpts" not in result
        assert "### Core Claims" in result
        assert "Some prose here" in result

    def test_removes_empty_core_claims(self):
        """Empty Core Claims header is removed."""
        from src.services.draft_service import strip_empty_section_headers

        doc = '''## Chapter 1: The Beginning

Some prose here.

### Key Excerpts

> "Quote here"
> — Speaker (GUEST)

### Core Claims

## Chapter 2
'''

        result = strip_empty_section_headers(doc)

        assert "### Core Claims" not in result
        assert "### Key Excerpts" in result
        assert '> "Quote here"' in result

    def test_preserves_non_empty_sections(self):
        """Non-empty sections are preserved."""
        from src.services.draft_service import strip_empty_section_headers

        doc = '''## Chapter 1: The Beginning

Some prose here.

### Key Excerpts

> "Quote here"
> — Speaker (GUEST)

### Core Claims

- **Claim**: "Support"

## Chapter 2
'''

        result = strip_empty_section_headers(doc)

        assert "### Key Excerpts" in result
        assert "### Core Claims" in result
        assert '> "Quote here"' in result
        assert "**Claim**" in result

    def test_removes_multiple_empty_sections(self):
        """Multiple empty sections across chapters are removed."""
        from src.services.draft_service import strip_empty_section_headers

        doc = '''## Chapter 1

### Key Excerpts

### Core Claims

## Chapter 2

### Key Excerpts

> "Quote"
> — Speaker (GUEST)

### Core Claims

'''

        result = strip_empty_section_headers(doc)

        # Chapter 1 Key Excerpts and Core Claims should be removed
        # Chapter 2 Key Excerpts should be preserved, Core Claims removed
        lines = result.split('\n')
        key_excerpts_count = sum(1 for line in lines if "### Key Excerpts" in line)
        core_claims_count = sum(1 for line in lines if "### Core Claims" in line)

        assert key_excerpts_count == 1  # Only chapter 2's
        assert core_claims_count == 0   # Both empty

    def test_handles_placeholder_as_content(self):
        """Placeholder text counts as content."""
        from src.services.draft_service import strip_empty_section_headers

        doc = '''## Chapter 1

### Core Claims

*No fully grounded claims available for this chapter.*

## Chapter 2
'''

        result = strip_empty_section_headers(doc)

        assert "### Core Claims" in result
        assert "*No fully grounded claims" in result

    def test_handles_whitespace_only_as_empty(self):
        """Whitespace-only content is treated as empty."""
        from src.services.draft_service import strip_empty_section_headers

        doc = '''## Chapter 1

### Key Excerpts


### Core Claims
'''

        result = strip_empty_section_headers(doc)

        assert "### Key Excerpts" not in result
