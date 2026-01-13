"""Unit tests for canonical transcript service.

These tests ensure text canonicalization is consistent and offset-safe.
The canonical transcript is the reference text for all SegmentRef offsets.
"""

from src.services.canonical_service import (
    canonicalize,
    canonicalize_structured,
    compute_hash,
    freeze_canonical_transcript,
    normalize_for_comparison,
    verify_canonical,
)


class TestCanonicalize:
    """Tests for text canonicalization."""

    def test_collapses_whitespace(self):
        """Multiple spaces should collapse to single space."""
        assert canonicalize("Hello    world") == "Hello world"

    def test_collapses_newlines_to_space(self):
        """Newlines should collapse to single space."""
        assert canonicalize("Hello\n\nworld") == "Hello world"

    def test_normalizes_smart_quotes(self):
        """Smart/curly double quotes should normalize to straight quotes."""
        # \u201c = left double quote, \u201d = right double quote
        assert canonicalize('\u201csmart\u201d') == '"smart"'

    def test_normalizes_curly_apostrophes(self):
        """Curly apostrophes should normalize to straight apostrophes."""
        # \u2019 = right single quote (curly apostrophe)
        assert canonicalize("it\u2019s") == "it's"

    def test_normalizes_left_curly_apostrophe(self):
        """Left curly apostrophe should normalize to straight apostrophe."""
        # \u2018 = left single quote
        assert canonicalize("\u2018twas") == "'twas"

    def test_normalizes_dashes(self):
        """Em and en dashes should normalize to hyphens."""
        # \u2014 = em dash, \u2013 = en dash
        assert canonicalize("em\u2014dash en\u2013dash") == "em-dash en-dash"

    def test_strips_whitespace(self):
        """Leading and trailing whitespace should be stripped."""
        assert canonicalize("  padded  ") == "padded"

    def test_idempotent(self):
        """CRITICAL: canonicalize(canonicalize(x)) == canonicalize(x)."""
        # Use unicode escapes for special characters
        # \u201c = left double quote, \u201d = right double quote
        # \u2019 = curly apostrophe, \u2014 = em dash
        text = '\u201cHello\u201d   world\u2019s\n\nem\u2014dash'
        once = canonicalize(text)
        twice = canonicalize(once)
        assert once == twice

    def test_line_endings_normalize_same(self):
        """\\r\\n and \\n normalize to same canonical form."""
        unix = "line1\nline2"
        windows = "line1\r\nline2"
        assert canonicalize(unix) == canonicalize(windows)

    def test_empty_string(self):
        """Empty string should return empty string."""
        assert canonicalize("") == ""

    def test_only_whitespace(self):
        """String with only whitespace should return empty string."""
        assert canonicalize("   \n\t\r\n   ") == ""

    def test_mixed_whitespace(self):
        """Mixed whitespace types should all collapse."""
        assert canonicalize("hello\t\n  \r\n  world") == "hello world"

    def test_preserves_single_spaces(self):
        """Single spaces between words should be preserved."""
        assert canonicalize("hello world test") == "hello world test"

    def test_handles_multiple_quote_styles(self):
        """All quote variations should normalize consistently."""
        # Left double quote (\u201c), right double quote (\u201d)
        assert canonicalize('\u201cquoted\u201d') == '"quoted"'
        # Ensure both styles become straight
        assert '\u201c' not in canonicalize('\u201ctest\u201d')
        assert '\u201d' not in canonicalize('\u201ctest\u201d')

    def test_handles_unicode_nbsp(self):
        """Non-breaking spaces should normalize to regular space."""
        # U+00A0 non-breaking space
        text = "hello\u00a0world"
        assert canonicalize(text) == "hello world"

    def test_unicode_nfc_normalization(self):
        """Composed and decomposed Unicode characters should normalize identically.

        NFC normalization ensures that:
        - 'cafe' (composed e with acute) and 'cafe\u0301' (e + combining acute)
          produce the same canonical result.
        """
        # Composed form: e with acute accent as single character (\u00e9)
        composed = "caf\u00e9"
        # Decomposed form: e + combining acute accent (\u0301)
        decomposed = "cafe\u0301"

        # Both should produce identical canonical output
        assert canonicalize(composed) == canonicalize(decomposed)

        # Verify the result is the NFC form (composed)
        assert canonicalize(decomposed) == "caf\u00e9"


class TestCanonicalizeStructured:
    """Tests for structured text canonicalization (preserves paragraphs)."""

    def test_preserves_paragraph_breaks(self):
        """Double newlines should be preserved as paragraph separators."""
        text = "First paragraph.\n\nSecond paragraph."
        result = canonicalize_structured(text)
        assert result == "First paragraph.\n\nSecond paragraph."

    def test_normalizes_multiple_blank_lines(self):
        """3+ newlines should normalize to double newline."""
        text = "First.\n\n\n\nSecond."
        result = canonicalize_structured(text)
        assert result == "First.\n\nSecond."

    def test_collapses_whitespace_within_paragraphs(self):
        """Multiple spaces within paragraphs should collapse."""
        text = "Hello    world.\n\nSecond   paragraph."
        result = canonicalize_structured(text)
        assert result == "Hello world.\n\nSecond paragraph."

    def test_normalizes_smart_quotes(self):
        """Smart quotes should normalize like flat canonical."""
        text = '\u201cHello\u201d\n\n\u201cWorld\u201d'
        result = canonicalize_structured(text)
        assert result == '"Hello"\n\n"World"'

    def test_normalizes_dashes(self):
        """Em/en dashes should normalize like flat canonical."""
        text = "em\u2014dash\n\nen\u2013dash"
        result = canonicalize_structured(text)
        assert result == "em-dash\n\nen-dash"

    def test_idempotent(self):
        """CRITICAL: canonicalize_structured(canonicalize_structured(x)) == canonicalize_structured(x)."""
        text = "First   para.\n\n\n\nSecond\u2014para."
        once = canonicalize_structured(text)
        twice = canonicalize_structured(once)
        assert once == twice

    def test_handles_windows_line_endings(self):
        """\\r\\n should normalize to \\n for paragraph detection."""
        text = "First.\r\n\r\nSecond."
        result = canonicalize_structured(text)
        assert result == "First.\n\nSecond."

    def test_single_newlines_collapse_within_paragraph(self):
        """Single newlines within a paragraph should collapse to space."""
        text = "Line one\nLine two\n\nNew paragraph."
        result = canonicalize_structured(text)
        assert result == "Line one Line two\n\nNew paragraph."

    def test_empty_string(self):
        """Empty string should return empty string."""
        assert canonicalize_structured("") == ""

    def test_only_whitespace(self):
        """String with only whitespace should return empty string."""
        assert canonicalize_structured("   \n\n\n   ") == ""

    def test_speaker_turns_preserved(self):
        """Interview format with speaker labels should preserve turns."""
        text = """Host: What is knowledge?

David: Knowledge is conjectural.

Host: Interesting!"""
        result = canonicalize_structured(text)
        assert "Host: What is knowledge?" in result
        assert "David: Knowledge is conjectural." in result
        assert result.count("\n\n") == 2  # Two paragraph breaks

    def test_unicode_nfc_normalization(self):
        """Composed and decomposed characters should normalize identically."""
        composed = "caf\u00e9\n\ntest"
        decomposed = "cafe\u0301\n\ntest"
        assert canonicalize_structured(composed) == canonicalize_structured(decomposed)


class TestFlatVsStructured:
    """Tests comparing flat and structured canonicalization."""

    def test_same_character_normalizations(self):
        """Both modes should apply same character normalizations."""
        text = '\u201cHello\u201d \u2014 it\u2019s\u00a0here'
        flat = canonicalize(text)
        structured = canonicalize_structured(text)
        # Both should have straight quotes, hyphens, straight apostrophes
        assert '"Hello"' in flat
        assert '"Hello"' in structured
        assert "it's" in flat
        assert "it's" in structured
        assert "-" in flat
        assert "-" in structured

    def test_flat_loses_paragraphs(self):
        """Flat canonical collapses paragraphs to spaces."""
        text = "First.\n\nSecond."
        flat = canonicalize(text)
        structured = canonicalize_structured(text)
        assert "\n" not in flat  # No newlines in flat
        assert flat == "First. Second."
        assert "\n\n" in structured  # Paragraphs preserved

    def test_flat_for_offsets_structured_for_display(self):
        """Demonstrate the intended use case for each mode."""
        raw = """Host: Question one?

Guest: Answer one.

Host: Question two?"""

        # Flat for offsets - all on one line
        flat = canonicalize(raw)
        assert flat == "Host: Question one? Guest: Answer one. Host: Question two?"

        # Structured for display - paragraphs preserved
        structured = canonicalize_structured(raw)
        lines = structured.split("\n\n")
        assert len(lines) == 3
        assert lines[0] == "Host: Question one?"
        assert lines[1] == "Guest: Answer one."
        assert lines[2] == "Host: Question two?"


class TestNormalizeForComparison:
    """Tests for comparison-ready normalization."""

    def test_applies_canonicalization(self):
        """Should apply all canonicalization rules."""
        assert normalize_for_comparison("Hello    World") == "hello world"

    def test_lowercases(self):
        """Should convert to lowercase."""
        assert normalize_for_comparison("HELLO") == "hello"

    def test_combined_normalization(self):
        """Should apply both canonicalization and lowercase."""
        # \u201c, \u201d = curly double quotes, \u2019 = curly apostrophe
        text = '\u201cHello\u201d   World\u2019s\n\nTEST'
        result = normalize_for_comparison(text)
        assert result == "\"hello\" world's test"


class TestComputeHash:
    """Tests for SHA256 hash computation."""

    def test_hash_is_sha256_hex(self):
        """Hash should be 64-character hex string."""
        result = compute_hash("test")
        assert len(result) == 64
        assert all(c in '0123456789abcdef' for c in result)

    def test_hash_stability(self):
        """Same input always produces same hash."""
        text = "Hello world"
        assert compute_hash(text) == compute_hash(text)

    def test_different_input_different_hash(self):
        """Different inputs produce different hashes."""
        assert compute_hash("hello") != compute_hash("world")

    def test_empty_string_hash(self):
        """Empty string should produce valid hash."""
        result = compute_hash("")
        assert len(result) == 64
        assert all(c in '0123456789abcdef' for c in result)

    def test_known_hash_value(self):
        """Verify hash matches expected SHA256 value."""
        # SHA256 of "test" is well-known
        expected = "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"
        assert compute_hash("test") == expected


class TestVerifyCanonical:
    """Tests for canonical verification."""

    def test_matching_hash_returns_true(self):
        """Matching hash should return True."""
        text = "Hello world"
        canonical, hash_val = freeze_canonical_transcript(text)
        assert verify_canonical(text, hash_val) is True

    def test_modified_transcript_returns_false(self):
        """Modified transcript should not match hash."""
        text = "Hello world"
        _, hash_val = freeze_canonical_transcript(text)
        modified = "Hello world MODIFIED"
        assert verify_canonical(modified, hash_val) is False

    def test_whitespace_variations_match(self):
        """Whitespace variations should match after canonicalization."""
        original = "Hello    world"
        _, hash_val = freeze_canonical_transcript(original)
        # Different whitespace but same canonical form
        variation = "Hello world"
        assert verify_canonical(variation, hash_val) is True

    def test_quote_variations_match(self):
        """Quote variations should match after canonicalization."""
        # \u201c, \u201d = curly double quotes
        original = '\u201cquoted\u201d'
        _, hash_val = freeze_canonical_transcript(original)
        # Straight quotes should match
        variation = '"quoted"'
        assert verify_canonical(variation, hash_val) is True


class TestFreezeCanonicalTranscript:
    """Tests for freezing canonical transcript."""

    def test_returns_tuple(self):
        """Should return (canonical_text, hash) tuple."""
        result = freeze_canonical_transcript("test")
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_canonical_text_is_normalized(self):
        """Canonical text should be normalized."""
        canonical, _ = freeze_canonical_transcript("Hello    world")
        assert canonical == "Hello world"

    def test_hash_matches_canonical(self):
        """Hash should match the canonical text, not original."""
        original = "Hello    world"
        canonical, hash_val = freeze_canonical_transcript(original)
        assert compute_hash(canonical) == hash_val

    def test_hash_is_valid_sha256(self):
        """Hash should be valid SHA256."""
        _, hash_val = freeze_canonical_transcript("test")
        assert len(hash_val) == 64
        assert all(c in '0123456789abcdef' for c in hash_val)


class TestOffsetValidity:
    """CRITICAL: Tests for offset validity after canonicalization."""

    def test_offset_slicing_returns_expected_text(self):
        """CRITICAL: Offsets into canonical transcript return expected substring."""
        raw = '"Hello"   world\n\ntest'
        canonical, _ = freeze_canonical_transcript(raw)
        # After canonicalization: "Hello" world test
        # Find "world" in canonical
        start = canonical.find("world")
        end = start + len("world")
        assert canonical[start:end] == "world"

    def test_offsets_valid_after_canonicalization(self):
        """Offsets computed on canonical text remain valid."""
        raw = "  Multiple   spaces  and\n\nnewlines  "
        canonical, hash_val = freeze_canonical_transcript(raw)
        # canonical should be "Multiple spaces and newlines"
        assert "Multiple" in canonical
        start = canonical.find("Multiple")
        end = start + len("Multiple")
        assert canonical[start:end] == "Multiple"

    def test_canonical_offsets_stable_across_calls(self):
        """Same raw text produces same canonical offsets."""
        raw = "  Hello    world   test  "
        canonical1, _ = freeze_canonical_transcript(raw)
        canonical2, _ = freeze_canonical_transcript(raw)

        # Find positions in both
        pos1 = canonical1.find("world")
        pos2 = canonical2.find("world")
        assert pos1 == pos2

    def test_offset_for_quote_extraction(self):
        """Simulate extracting a quote using offsets."""
        raw = 'Speaker said "Important   point" during the talk'
        canonical, _ = freeze_canonical_transcript(raw)

        # Find the quote in canonical
        quote_text = "Important point"  # Canonical form
        start = canonical.find(quote_text)
        end = start + len(quote_text)

        # Verify extraction works
        assert start >= 0  # Found
        assert canonical[start:end] == quote_text

    def test_multi_paragraph_offset_stability(self):
        """Offsets work correctly for multi-paragraph text."""
        raw = """First paragraph.

Second paragraph.

Third paragraph."""
        canonical, _ = freeze_canonical_transcript(raw)
        # Should become: "First paragraph. Second paragraph. Third paragraph."

        # Find each paragraph marker
        assert "First paragraph." in canonical
        assert "Second paragraph." in canonical
        assert "Third paragraph." in canonical

        # Verify we can extract them
        first_start = canonical.find("First paragraph.")
        second_start = canonical.find("Second paragraph.")
        third_start = canonical.find("Third paragraph.")

        # They should be in order
        assert first_start < second_start < third_start
