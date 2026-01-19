from src.models.edition import SpeakerRole
from src.services.whitelist_service import (
    canonicalize_transcript,
    find_all_occurrences,
    resolve_speaker,
)


class TestCanonicalizeTranscript:
    def test_normalizes_smart_quotes(self):
        """Test smart quotes become straight quotes."""
        # Using unicode escapes to avoid syntax issues
        # \u201c = " (left double), \u201d = " (right double)
        # \u2018 = ' (left single), \u2019 = ' (right single)
        raw = 'He said \u201chello\u201d and \u2018goodbye\u2019'
        result = canonicalize_transcript(raw)
        assert '\u201c' not in result  # No curly left double quote
        assert '\u201d' not in result  # No curly right double quote
        assert '\u2018' not in result  # No curly left single quote
        assert '\u2019' not in result  # No curly right single quote
        assert '"hello"' in result

    def test_normalizes_dashes(self):
        """Test em-dash and en-dash become hyphens."""
        # \u2014 = em-dash, \u2013 = en-dash
        raw = "word\u2014another\u2013third"
        result = canonicalize_transcript(raw)
        assert "\u2014" not in result
        assert "\u2013" not in result
        assert result == "word-another-third"

    def test_collapses_whitespace(self):
        """Test multiple spaces/newlines collapse to single space."""
        raw = "hello   world\n\ntest"
        result = canonicalize_transcript(raw)
        assert result == "hello world test"

    def test_preserves_case(self):
        """Test case is preserved (not lowercased)."""
        raw = "Hello World"
        result = canonicalize_transcript(raw)
        assert result == "Hello World"

    def test_stability(self):
        """Test same input always produces same output."""
        raw = 'Test \u201cquote\u201d\u2014with dash'
        result1 = canonicalize_transcript(raw)
        result2 = canonicalize_transcript(raw)
        assert result1 == result2

    def test_empty_string(self):
        """Test empty string returns empty string."""
        assert canonicalize_transcript("") == ""

    def test_whitespace_only(self):
        """Test whitespace-only string returns empty string."""
        assert canonicalize_transcript("   \n\t  ") == ""


class TestFindAllOccurrences:
    def test_finds_single_occurrence(self):
        """Test finding single occurrence."""
        text = "hello world hello"
        spans = find_all_occurrences(text, "world")
        assert spans == [(6, 11)]

    def test_finds_multiple_occurrences(self):
        """Test finding multiple occurrences."""
        text = "hello world hello world"
        spans = find_all_occurrences(text, "hello")
        assert len(spans) == 2
        assert spans[0] == (0, 5)
        assert spans[1] == (12, 17)

    def test_returns_empty_for_no_match(self):
        """Test returns empty list when not found."""
        text = "hello world"
        spans = find_all_occurrences(text, "xyz")
        assert spans == []

    def test_case_sensitive(self):
        """Test search is case-sensitive."""
        text = "Hello HELLO hello"
        spans = find_all_occurrences(text, "hello")
        assert len(spans) == 1
        assert spans[0] == (12, 17)


class TestResolveSpeaker:
    def test_resolves_known_guest(self):
        """Test resolving a known guest speaker."""
        ref = resolve_speaker("David Deutsch", known_guests=["David Deutsch"])
        assert ref.speaker_id == "david_deutsch"
        assert ref.speaker_name == "David Deutsch"
        assert ref.speaker_role == SpeakerRole.GUEST

    def test_resolves_host(self):
        """Test resolving host speaker."""
        ref = resolve_speaker("Naval Ravikant", known_hosts=["Naval Ravikant"])
        assert ref.speaker_role == SpeakerRole.HOST

    def test_resolves_unknown_as_unclear(self):
        """Test unknown speaker resolves as UNCLEAR."""
        ref = resolve_speaker("Unknown")
        assert ref.speaker_role == SpeakerRole.UNCLEAR

    def test_generates_stable_id(self):
        """Test speaker_id is stable."""
        ref1 = resolve_speaker("David Deutsch", known_guests=["David Deutsch"])
        ref2 = resolve_speaker("David Deutsch", known_guests=["David Deutsch"])
        assert ref1.speaker_id == ref2.speaker_id

    def test_resolves_empty_string_as_unclear(self):
        """Test empty name resolves as UNCLEAR."""
        ref = resolve_speaker("")
        assert ref.speaker_role == SpeakerRole.UNCLEAR

    def test_resolves_unclear_string_as_unclear(self):
        """Test 'unclear' string resolves as UNCLEAR."""
        ref = resolve_speaker("unclear")
        assert ref.speaker_role == SpeakerRole.UNCLEAR
