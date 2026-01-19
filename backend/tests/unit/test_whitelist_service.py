from dataclasses import dataclass

import pytest
from src.models.edition import SpeakerRef, SpeakerRole, TranscriptPair, WhitelistQuote
from src.services.whitelist_service import (
    build_quote_whitelist,
    canonicalize_transcript,
    enforce_core_claims_guest_only,
    enforce_quote_whitelist,
    EnforcementResult,
    find_all_occurrences,
    resolve_speaker,
    select_deterministic_excerpts,
)
from src.models.evidence_map import EvidenceMap, ChapterEvidence, EvidenceEntry, SupportQuote


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


class TestBuildQuoteWhitelist:
    @pytest.fixture
    def sample_transcript_pair(self):
        """Transcript with smart quotes in raw, straight in canonical."""
        raw = 'David said "Wisdom is limitless" and also "Knowledge grows"'
        canonical = 'David said "Wisdom is limitless" and also "Knowledge grows"'
        return TranscriptPair(raw=raw, canonical=canonical)

    @pytest.fixture
    def sample_evidence_map(self):
        """Evidence map with claims and quotes."""
        return EvidenceMap(
            version=1,
            project_id="test",
            content_mode="essay",
            transcript_hash="abc123",
            chapters=[
                ChapterEvidence(
                    chapter_index=1,
                    chapter_title="Chapter 1",
                    claims=[
                        EvidenceEntry(
                            id="ev1",
                            claim="Wisdom has no bounds",
                            support=[
                                SupportQuote(
                                    quote="Wisdom is limitless",
                                    speaker="David Deutsch",
                                )
                            ],
                        )
                    ],
                )
            ],
        )

    def test_builds_whitelist_from_evidence(self, sample_transcript_pair, sample_evidence_map):
        """Test whitelist is built from evidence map."""
        whitelist = build_quote_whitelist(
            sample_evidence_map,
            sample_transcript_pair,
            known_guests=["David Deutsch"],
        )
        assert len(whitelist) == 1
        assert whitelist[0].quote_text == "Wisdom is limitless"
        assert whitelist[0].speaker.speaker_role == SpeakerRole.GUEST

    def test_rejects_quote_not_in_transcript(self):
        """Test quotes not in transcript are excluded."""
        transcript = TranscriptPair(raw="Hello world", canonical="Hello world")
        evidence = EvidenceMap(
            version=1, project_id="test", content_mode="essay", transcript_hash="abc",
            chapters=[
                ChapterEvidence(
                    chapter_index=1, chapter_title="Ch1",
                    claims=[
                        EvidenceEntry(
                            id="ev1", claim="Test",
                            support=[SupportQuote(quote="Not in transcript", speaker="Someone")],
                        )
                    ],
                )
            ],
        )
        whitelist = build_quote_whitelist(evidence, transcript)
        assert len(whitelist) == 0

    def test_rejects_unknown_speaker(self):
        """Test None/Unknown attribution is excluded."""
        transcript = TranscriptPair(raw="Wisdom is limitless", canonical="Wisdom is limitless")
        evidence = EvidenceMap(
            version=1, project_id="test", content_mode="essay", transcript_hash="abc",
            chapters=[
                ChapterEvidence(
                    chapter_index=1, chapter_title="Ch1",
                    claims=[
                        EvidenceEntry(
                            id="ev1", claim="Test",
                            support=[SupportQuote(quote="Wisdom is limitless", speaker=None)],
                        )
                    ],
                )
            ],
        )
        whitelist = build_quote_whitelist(evidence, transcript)
        assert len(whitelist) == 0

    def test_rejects_unclear_speaker(self):
        """Test speaker resolving to UNCLEAR is excluded."""
        transcript = TranscriptPair(raw="Wisdom is limitless", canonical="Wisdom is limitless")
        evidence = EvidenceMap(
            version=1, project_id="test", content_mode="essay", transcript_hash="abc",
            chapters=[
                ChapterEvidence(
                    chapter_index=1, chapter_title="Ch1",
                    claims=[
                        EvidenceEntry(
                            id="ev1", claim="Test",
                            support=[SupportQuote(quote="Wisdom is limitless", speaker="Unknown")],
                        )
                    ],
                )
            ],
        )
        # "Unknown" resolves to UNCLEAR role
        whitelist = build_quote_whitelist(evidence, transcript)
        assert len(whitelist) == 0

    def test_merges_duplicate_quotes(self):
        """Test same quote from same speaker merges chapter_indices."""
        transcript = TranscriptPair(raw="Wisdom is limitless", canonical="Wisdom is limitless")
        evidence = EvidenceMap(
            version=1, project_id="test", content_mode="essay", transcript_hash="abc",
            chapters=[
                ChapterEvidence(
                    chapter_index=1, chapter_title="Ch1",
                    claims=[
                        EvidenceEntry(id="ev1", claim="Claim 1",
                            support=[SupportQuote(quote="Wisdom is limitless", speaker="David")]),
                    ],
                ),
                ChapterEvidence(
                    chapter_index=2, chapter_title="Ch2",
                    claims=[
                        EvidenceEntry(id="ev2", claim="Claim 2",
                            support=[SupportQuote(quote="Wisdom is limitless", speaker="David")]),
                    ],
                ),
            ],
        )
        whitelist = build_quote_whitelist(evidence, transcript, known_guests=["David"])
        assert len(whitelist) == 1
        assert 0 in whitelist[0].chapter_indices  # 0-indexed from 1-based
        assert 1 in whitelist[0].chapter_indices

    def test_generates_stable_quote_id(self):
        """Test quote_id is deterministic."""
        transcript = TranscriptPair(raw="Wisdom is limitless", canonical="Wisdom is limitless")
        evidence = EvidenceMap(
            version=1, project_id="test", content_mode="essay", transcript_hash="abc",
            chapters=[
                ChapterEvidence(
                    chapter_index=1, chapter_title="Ch1",
                    claims=[
                        EvidenceEntry(id="ev1", claim="Test",
                            support=[SupportQuote(quote="Wisdom is limitless", speaker="David")]),
                    ],
                )
            ],
        )
        whitelist1 = build_quote_whitelist(evidence, transcript, known_guests=["David"])
        whitelist2 = build_quote_whitelist(evidence, transcript, known_guests=["David"])
        assert whitelist1[0].quote_id == whitelist2[0].quote_id


from src.services.whitelist_service import compute_chapter_coverage
from src.models.edition import CoverageLevel, ChapterCoverage


class TestComputeChapterCoverage:
    def test_strong_coverage(self):
        """Test STRONG coverage with >= 5 quotes and >= 50 words/claim."""
        whitelist = [
            _make_quote(f"Quote {i} " * 15, chapter_indices=[0])  # ~15 words each
            for i in range(6)
        ]
        chapter = _make_chapter_evidence(claim_count=2)

        coverage = compute_chapter_coverage(chapter, whitelist, chapter_index=0)

        assert coverage.level == CoverageLevel.STRONG
        assert coverage.usable_quotes >= 5
        assert coverage.target_words == 800
        assert coverage.generation_mode == "normal"

    def test_medium_coverage(self):
        """Test MEDIUM coverage with 3-4 quotes."""
        whitelist = [
            _make_quote(f"Quote {i} " * 10, chapter_indices=[0])
            for i in range(3)
        ]
        chapter = _make_chapter_evidence(claim_count=2)

        coverage = compute_chapter_coverage(chapter, whitelist, chapter_index=0)

        assert coverage.level == CoverageLevel.MEDIUM
        assert coverage.target_words == 500
        assert coverage.generation_mode == "thin"

    def test_weak_coverage(self):
        """Test WEAK coverage with < 3 quotes."""
        whitelist = [
            _make_quote("Short quote", chapter_indices=[0])
        ]
        chapter = _make_chapter_evidence(claim_count=2)

        coverage = compute_chapter_coverage(chapter, whitelist, chapter_index=0)

        assert coverage.level == CoverageLevel.WEAK
        assert coverage.target_words == 250
        assert coverage.generation_mode == "excerpt_only"

    def test_filters_short_quotes(self):
        """Test quotes < 8 words are not counted as usable."""
        whitelist = [
            _make_quote("Short", chapter_indices=[0]),  # 1 word - not usable
            _make_quote("This is a longer quote with enough words", chapter_indices=[0]),  # 8 words
        ]
        chapter = _make_chapter_evidence(claim_count=1)

        coverage = compute_chapter_coverage(chapter, whitelist, chapter_index=0)

        assert coverage.usable_quotes == 1  # Only the long one

    def test_filters_by_chapter_index(self):
        """Test only quotes for this chapter are counted."""
        whitelist = [
            _make_quote("Quote for chapter 0 with enough words here", chapter_indices=[0]),
            _make_quote("Quote for chapter 1 with enough words here", chapter_indices=[1]),
        ]
        chapter = _make_chapter_evidence(claim_count=1)

        coverage = compute_chapter_coverage(chapter, whitelist, chapter_index=0)

        assert coverage.usable_quotes == 1


class TestWhitelistBuilderHardGate:
    """HARD GATE 1: Whitelist builder correctness tests.

    These tests prove:
    - quote_text is exact raw substring
    - quote_canonical matches canonical transcript
    - Curly quotes/dashes/whitespace handled correctly
    - Duplicates merged properly
    """

    def test_curly_quotes_matched_correctly(self):
        """Test curly quotes in raw don't break matching."""
        raw = 'He said "Wisdom is limitless" today'  # curly quotes
        canonical = 'He said "Wisdom is limitless" today'  # straight quotes
        transcript = TranscriptPair(raw=raw, canonical=canonical)

        evidence = EvidenceMap(
            version=1, project_id="test", content_mode="essay", transcript_hash="abc",
            chapters=[ChapterEvidence(
                chapter_index=1, chapter_title="Ch1",
                claims=[EvidenceEntry(
                    id="ev1", claim="Test",
                    support=[SupportQuote(quote="Wisdom is limitless", speaker="David")],
                )],
            )],
        )
        whitelist = build_quote_whitelist(evidence, transcript, known_guests=["David"])
        assert len(whitelist) == 1
        # quote_text from raw should preserve curly quotes
        assert "Wisdom is limitless" in whitelist[0].quote_text

    def test_em_dash_matched_correctly(self):
        """Test em-dash in raw doesn't break matching."""
        raw = "Knowledge—the key—unlocks everything"  # em-dashes
        canonical = "Knowledge-the key-unlocks everything"  # hyphens
        transcript = TranscriptPair(raw=raw, canonical=canonical)

        evidence = EvidenceMap(
            version=1, project_id="test", content_mode="essay", transcript_hash="abc",
            chapters=[ChapterEvidence(
                chapter_index=1, chapter_title="Ch1",
                claims=[EvidenceEntry(
                    id="ev1", claim="Test",
                    support=[SupportQuote(quote="the key", speaker="David")],
                )],
            )],
        )
        whitelist = build_quote_whitelist(evidence, transcript, known_guests=["David"])
        assert len(whitelist) == 1

    def test_whitespace_variations_matched(self):
        """Test whitespace variations don't break matching."""
        raw = "Wisdom   is\nlimitless"  # extra spaces, newline
        canonical = "Wisdom is limitless"  # normalized
        transcript = TranscriptPair(raw=raw, canonical=canonical)

        evidence = EvidenceMap(
            version=1, project_id="test", content_mode="essay", transcript_hash="abc",
            chapters=[ChapterEvidence(
                chapter_index=1, chapter_title="Ch1",
                claims=[EvidenceEntry(
                    id="ev1", claim="Test",
                    support=[SupportQuote(quote="Wisdom is limitless", speaker="David")],
                )],
            )],
        )
        whitelist = build_quote_whitelist(evidence, transcript, known_guests=["David"])
        assert len(whitelist) == 1

    def test_quote_text_is_exact_raw_substring(self):
        """CRITICAL: quote_text must be exact substring from raw transcript."""
        raw = 'The "truth" is—complex'
        canonical = 'The "truth" is-complex'
        transcript = TranscriptPair(raw=raw, canonical=canonical)

        evidence = EvidenceMap(
            version=1, project_id="test", content_mode="essay", transcript_hash="abc",
            chapters=[ChapterEvidence(
                chapter_index=1, chapter_title="Ch1",
                claims=[EvidenceEntry(
                    id="ev1", claim="Test",
                    support=[SupportQuote(quote="truth", speaker="David")],
                )],
            )],
        )
        whitelist = build_quote_whitelist(evidence, transcript, known_guests=["David"])
        assert len(whitelist) == 1

        # Verify quote_text is extractable from raw
        quote_text = whitelist[0].quote_text
        assert quote_text in raw, f"quote_text '{quote_text}' not found in raw transcript"

    def test_quote_canonical_matches_canonical_transcript(self):
        """CRITICAL: quote_canonical must be findable in canonical transcript."""
        raw = 'He said "Wisdom is limitless"'
        canonical = 'He said "Wisdom is limitless"'
        transcript = TranscriptPair(raw=raw, canonical=canonical)

        evidence = EvidenceMap(
            version=1, project_id="test", content_mode="essay", transcript_hash="abc",
            chapters=[ChapterEvidence(
                chapter_index=1, chapter_title="Ch1",
                claims=[EvidenceEntry(
                    id="ev1", claim="Test",
                    support=[SupportQuote(quote="Wisdom is limitless", speaker="David")],
                )],
            )],
        )
        whitelist = build_quote_whitelist(evidence, transcript, known_guests=["David"])
        assert len(whitelist) == 1

        quote_canonical = whitelist[0].quote_canonical
        assert quote_canonical in canonical.casefold()

    def test_duplicate_quotes_different_chapters_merged(self):
        """Test same quote in different chapters creates single entry with both indices."""
        transcript = TranscriptPair(raw="Wisdom is limitless", canonical="Wisdom is limitless")
        evidence = EvidenceMap(
            version=1, project_id="test", content_mode="essay", transcript_hash="abc",
            chapters=[
                ChapterEvidence(
                    chapter_index=1, chapter_title="Ch1",
                    claims=[EvidenceEntry(
                        id="ev1", claim="Claim 1",
                        support=[SupportQuote(quote="Wisdom is limitless", speaker="David")],
                    )],
                ),
                ChapterEvidence(
                    chapter_index=2, chapter_title="Ch2",
                    claims=[EvidenceEntry(
                        id="ev2", claim="Claim 2",
                        support=[SupportQuote(quote="Wisdom is limitless", speaker="David")],
                    )],
                ),
                ChapterEvidence(
                    chapter_index=3, chapter_title="Ch3",
                    claims=[EvidenceEntry(
                        id="ev3", claim="Claim 3",
                        support=[SupportQuote(quote="Wisdom is limitless", speaker="David")],
                    )],
                ),
            ],
        )
        whitelist = build_quote_whitelist(evidence, transcript, known_guests=["David"])

        # Should be single entry
        assert len(whitelist) == 1
        # With all three chapter indices (0-indexed)
        assert set(whitelist[0].chapter_indices) == {0, 1, 2}
        # With all three evidence IDs
        assert set(whitelist[0].source_evidence_ids) == {"ev1", "ev2", "ev3"}

    def test_same_quote_different_speakers_separate_entries(self):
        """Test same quote from different speakers creates separate entries."""
        transcript = TranscriptPair(raw="The truth matters", canonical="The truth matters")
        evidence = EvidenceMap(
            version=1, project_id="test", content_mode="essay", transcript_hash="abc",
            chapters=[ChapterEvidence(
                chapter_index=1, chapter_title="Ch1",
                claims=[
                    EvidenceEntry(
                        id="ev1", claim="Claim 1",
                        support=[SupportQuote(quote="The truth matters", speaker="David")],
                    ),
                    EvidenceEntry(
                        id="ev2", claim="Claim 2",
                        support=[SupportQuote(quote="The truth matters", speaker="Naval")],
                    ),
                ],
            )],
        )
        whitelist = build_quote_whitelist(
            evidence, transcript,
            known_guests=["David", "Naval"],
        )

        # Should be two entries (one per speaker)
        assert len(whitelist) == 2
        speakers = {w.speaker.speaker_name for w in whitelist}
        assert speakers == {"David", "Naval"}


# Helper functions for tests
def _make_quote(text: str, chapter_indices: list[int]) -> WhitelistQuote:
    """Create a WhitelistQuote for testing."""
    from hashlib import sha256
    quote_id = sha256(f"test|{text}".encode()).hexdigest()[:16]
    return WhitelistQuote(
        quote_id=quote_id,
        quote_text=text,
        quote_canonical=text.lower(),
        speaker=SpeakerRef(
            speaker_id="test_speaker",
            speaker_name="Test Speaker",
            speaker_role=SpeakerRole.GUEST,
        ),
        source_evidence_ids=["ev1"],
        chapter_indices=chapter_indices,
        match_spans=[(0, len(text))],
    )


def _make_chapter_evidence(claim_count: int) -> ChapterEvidence:
    """Create ChapterEvidence for testing."""
    return ChapterEvidence(
        chapter_index=1,
        chapter_title="Test Chapter",
        claims=[
            EvidenceEntry(
                id=f"claim_{i}",
                claim=f"Claim {i}",
                support=[SupportQuote(quote="test", speaker="Test")],
            )
            for i in range(claim_count)
        ],
    )


from hashlib import sha256


def _make_guest_quote(text: str, chapter_indices: list[int] | None = None, speaker_name: str = "Guest Speaker") -> WhitelistQuote:
    """Create a GUEST WhitelistQuote for testing."""
    if chapter_indices is None:
        chapter_indices = [0]
    quote_id = sha256(f"{speaker_name}|{text}".encode()).hexdigest()[:16]
    return WhitelistQuote(
        quote_id=quote_id,
        quote_text=text,
        quote_canonical=text.lower(),
        speaker=SpeakerRef(
            speaker_id=speaker_name.lower().replace(" ", "_"),
            speaker_name=speaker_name,
            speaker_role=SpeakerRole.GUEST,
        ),
        source_evidence_ids=["ev1"],
        chapter_indices=chapter_indices,
        match_spans=[(0, len(text))],
    )


def _make_host_quote(text: str, chapter_indices: list[int] | None = None) -> WhitelistQuote:
    """Create a HOST WhitelistQuote for testing."""
    if chapter_indices is None:
        chapter_indices = [0]
    quote_id = sha256(text.encode()).hexdigest()[:16]
    return WhitelistQuote(
        quote_id=quote_id,
        quote_text=text,
        quote_canonical=text.lower(),
        speaker=SpeakerRef(
            speaker_id="host_speaker",
            speaker_name="Host Speaker",
            speaker_role=SpeakerRole.HOST,
        ),
        source_evidence_ids=["ev1"],
        chapter_indices=chapter_indices,
        match_spans=[(0, len(text))],
    )


class TestSelectDeterministicExcerpts:
    def test_selects_correct_count_for_strong(self):
        """Test STRONG coverage gets 4 excerpts."""
        whitelist = [_make_guest_quote(f"Quote {i} with enough words here") for i in range(10)]
        excerpts = select_deterministic_excerpts(whitelist, chapter_index=0, coverage_level=CoverageLevel.STRONG)
        assert len(excerpts) == 4

    def test_selects_correct_count_for_medium(self):
        """Test MEDIUM coverage gets 3 excerpts."""
        whitelist = [_make_guest_quote(f"Quote {i} with enough words here") for i in range(10)]
        excerpts = select_deterministic_excerpts(whitelist, chapter_index=0, coverage_level=CoverageLevel.MEDIUM)
        assert len(excerpts) == 3

    def test_selects_correct_count_for_weak(self):
        """Test WEAK coverage gets 2 excerpts."""
        whitelist = [_make_guest_quote(f"Quote {i} with enough words here") for i in range(10)]
        excerpts = select_deterministic_excerpts(whitelist, chapter_index=0, coverage_level=CoverageLevel.WEAK)
        assert len(excerpts) == 2

    def test_filters_to_guest_only(self):
        """Test only GUEST quotes are selected."""
        whitelist = [
            _make_guest_quote("Guest quote 1 with enough words"),
            _make_host_quote("Host quote with enough words here"),
            _make_guest_quote("Guest quote 2 with enough words"),
        ]
        excerpts = select_deterministic_excerpts(whitelist, chapter_index=0, coverage_level=CoverageLevel.STRONG)
        for e in excerpts:
            assert e.speaker.speaker_role == SpeakerRole.GUEST

    def test_filters_to_chapter(self):
        """Test only quotes for this chapter are selected."""
        whitelist = [
            _make_guest_quote("Quote ch0 with enough words", chapter_indices=[0]),
            _make_guest_quote("Quote ch1 with enough words", chapter_indices=[1]),
        ]
        excerpts = select_deterministic_excerpts(whitelist, chapter_index=0, coverage_level=CoverageLevel.STRONG)
        for e in excerpts:
            assert 0 in e.chapter_indices

    def test_stable_ordering(self):
        """Test same input always produces same order."""
        whitelist = [_make_guest_quote(f"Quote {i} with enough words") for i in range(10)]
        excerpts1 = select_deterministic_excerpts(whitelist, chapter_index=0, coverage_level=CoverageLevel.STRONG)
        excerpts2 = select_deterministic_excerpts(whitelist, chapter_index=0, coverage_level=CoverageLevel.STRONG)
        assert [e.quote_id for e in excerpts1] == [e.quote_id for e in excerpts2]

    def test_prefers_longer_quotes(self):
        """Test longer quotes are selected first."""
        whitelist = [
            _make_guest_quote("Short"),
            _make_guest_quote("This is a much longer quote with many words here"),
            _make_guest_quote("Medium length quote here now"),
        ]
        excerpts = select_deterministic_excerpts(whitelist, chapter_index=0, coverage_level=CoverageLevel.WEAK)
        # First excerpt should be the longest
        assert "much longer" in excerpts[0].quote_text


class TestEnforcementResult:
    def test_enforcement_result_model(self):
        """Test EnforcementResult model structure."""
        result = EnforcementResult(
            text="cleaned text",
            replaced=[],
            dropped=["invalid quote"],
        )
        assert result.text == "cleaned text"
        assert len(result.dropped) == 1


class TestEnforceQuoteWhitelist:
    def test_replaces_valid_blockquote_with_exact_text(self):
        """Test valid blockquotes are replaced with exact quote_text."""
        whitelist = [_make_guest_quote("Wisdom is limitless")]
        text = '> "wisdom is limitless"\n> — Guest Speaker'

        result = enforce_quote_whitelist(text, whitelist, chapter_index=0)

        assert "Wisdom is limitless" in result.text  # Exact from whitelist
        assert len(result.replaced) == 1
        assert len(result.dropped) == 0

    def test_drops_invalid_blockquote(self):
        """Test invalid blockquotes are dropped entirely."""
        whitelist = [_make_guest_quote("Wisdom is limitless")]
        text = '> "This quote is not in whitelist"\n> — Someone'

        result = enforce_quote_whitelist(text, whitelist, chapter_index=0)

        assert "not in whitelist" not in result.text
        assert len(result.dropped) == 1

    def test_replaces_valid_inline_quote(self):
        """Test valid inline quotes are replaced with exact text."""
        whitelist = [_make_guest_quote("Wisdom is limitless")]
        text = 'He said "wisdom is limitless" today.'

        result = enforce_quote_whitelist(text, whitelist, chapter_index=0)

        assert '"Wisdom is limitless"' in result.text

    def test_unquotes_invalid_inline_quote(self):
        """Test invalid inline quotes have quotes removed."""
        whitelist = [_make_guest_quote("Wisdom is limitless")]
        text = 'He said "fabricated quote" today.'

        result = enforce_quote_whitelist(text, whitelist, chapter_index=0)

        # Quote marks removed but text preserved
        assert '"fabricated quote"' not in result.text
        assert 'fabricated quote' in result.text

    def test_multi_candidate_lookup_same_quote_different_speakers(self):
        """Test multi-candidate lookup handles same quote from different speakers."""
        whitelist = [
            _make_guest_quote("The truth matters", speaker_name="David"),
            _make_guest_quote("The truth matters", speaker_name="Naval"),
        ]
        text = '> "The truth matters"\n> — David'

        result = enforce_quote_whitelist(text, whitelist, chapter_index=0)

        assert len(result.replaced) == 1

    def test_chapter_scoping(self):
        """Test quotes are scoped to chapter."""
        whitelist = [_make_guest_quote("Chapter 0 only", chapter_indices=[0])]
        text = '> "Chapter 0 only"\n> — Guest Speaker'

        # Chapter 0 - should match
        result0 = enforce_quote_whitelist(text, whitelist, chapter_index=0)
        assert len(result0.replaced) == 1

        # Chapter 1 - should still match (fallback to any chapter)
        result1 = enforce_quote_whitelist(text, whitelist, chapter_index=1)
        assert len(result1.replaced) == 1


@dataclass
class CoreClaimTest:
    """Simple CoreClaim for testing."""
    claim_text: str
    supporting_quote: str


class TestEnforceCoreClaimsGuestOnly:
    def test_keeps_guest_claims(self):
        """Test claims with GUEST quotes are kept."""
        whitelist = [_make_guest_quote("Wisdom is limitless")]
        claims = [CoreClaimTest(claim_text="Wisdom has no bounds", supporting_quote="Wisdom is limitless")]

        result = enforce_core_claims_guest_only(claims, whitelist, chapter_index=0)

        assert len(result) == 1

    def test_drops_host_claims(self):
        """Test claims with HOST quotes are dropped."""
        whitelist = [_make_host_quote("Welcome everyone")]
        claims = [CoreClaimTest(claim_text="Greeting", supporting_quote="Welcome everyone")]

        result = enforce_core_claims_guest_only(claims, whitelist, chapter_index=0)

        assert len(result) == 0

    def test_drops_claims_not_in_whitelist(self):
        """Test claims with quotes not in whitelist are dropped."""
        whitelist = [_make_guest_quote("Wisdom is limitless")]
        claims = [CoreClaimTest(claim_text="Test", supporting_quote="Not in whitelist")]

        result = enforce_core_claims_guest_only(claims, whitelist, chapter_index=0)

        assert len(result) == 0

    def test_filters_by_chapter(self):
        """Test claims are filtered by chapter index."""
        whitelist = [_make_guest_quote("Chapter 0 quote", chapter_indices=[0])]
        claims = [CoreClaimTest(claim_text="Test", supporting_quote="Chapter 0 quote")]

        result0 = enforce_core_claims_guest_only(claims, whitelist, chapter_index=0)
        result1 = enforce_core_claims_guest_only(claims, whitelist, chapter_index=1)

        assert len(result0) == 1
        assert len(result1) == 0  # Not in chapter 1

    def test_empty_claims_returns_empty(self):
        """Test empty claims list returns empty."""
        whitelist = [_make_guest_quote("Quote")]
        result = enforce_core_claims_guest_only([], whitelist, chapter_index=0)
        assert result == []

    def test_empty_whitelist_returns_empty(self):
        """Test empty whitelist returns empty."""
        claims = [CoreClaimTest(claim_text="Test", supporting_quote="Quote")]
        result = enforce_core_claims_guest_only(claims, [], chapter_index=0)
        assert result == []
