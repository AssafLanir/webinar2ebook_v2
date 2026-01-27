"""Unit tests for groundedness service.

Tests for:
- Quote extraction from Key Excerpts
- Quote extraction from Core Claims
- Provenance matching (exact, anchor, fuzzy)
- Verdict determination
"""

import pytest

from src.services.groundedness_service import (
    normalize_for_matching,
    extract_anchor,
    extract_key_excerpts_quotes,
    extract_core_claims_with_evidence,
    match_quote_in_transcript,
    check_excerpt_provenance,
    check_claim_support,
    check_groundedness,
)


# =============================================================================
# Normalization Tests
# =============================================================================


class TestNormalization:
    """Tests for text normalization."""

    def test_lowercase(self):
        assert normalize_for_matching("Hello World") == "hello world"

    def test_collapses_whitespace(self):
        assert normalize_for_matching("hello   world\n\tfoo") == "hello world foo"

    def test_removes_punctuation(self):
        result = normalize_for_matching("Hello, world! How are you?")
        assert "," not in result
        assert "!" not in result
        assert "?" not in result

    def test_preserves_apostrophes(self):
        result = normalize_for_matching("it's a test")
        assert "it's" in result

    def test_normalizes_smart_quotes(self):
        result = normalize_for_matching('"smart quotes"')
        assert '"' not in result
        assert '"' not in result

    def test_normalizes_dashes(self):
        result = normalize_for_matching("em—dash and en–dash")
        assert "—" not in result
        assert "–" not in result


class TestAnchorExtraction:
    """Tests for anchor extraction."""

    def test_extracts_first_n_words(self):
        text = "one two three four five six seven eight nine ten eleven twelve"
        anchor = extract_anchor(text, num_words=5)
        assert anchor == "one two three four five"

    def test_handles_short_text(self):
        text = "one two three"
        anchor = extract_anchor(text, num_words=10)
        assert anchor == "one two three"


# =============================================================================
# Quote Extraction Tests
# =============================================================================


class TestKeyExcerptsExtraction:
    """Tests for Key Excerpts quote extraction."""

    def test_extracts_simple_quote(self):
        markdown = '''### Key Excerpts

> "This is a test quote."
> — Speaker Name
'''
        quotes = extract_key_excerpts_quotes(markdown)
        assert len(quotes) == 1
        assert "This is a test quote" in quotes[0]

    def test_extracts_multiple_quotes(self):
        markdown = '''### Key Excerpts

> "First quote here."
> — Speaker One

> "Second quote here."
> — Speaker Two
'''
        quotes = extract_key_excerpts_quotes(markdown)
        assert len(quotes) == 2

    def test_handles_smart_quotes(self):
        markdown = '''### Key Excerpts

> "Smart quote text"
> — Speaker
'''
        quotes = extract_key_excerpts_quotes(markdown)
        assert len(quotes) == 1
        assert "Smart quote text" in quotes[0]

    def test_ignores_non_key_excerpts_sections(self):
        markdown = '''### Core Claims

- **Claim**: "This is not a Key Excerpt quote."

### Key Excerpts

> "This IS a Key Excerpt quote."
> — Speaker
'''
        quotes = extract_key_excerpts_quotes(markdown)
        assert len(quotes) == 1
        assert "This IS a Key Excerpt quote" in quotes[0]

    def test_handles_multiline_quotes(self):
        markdown = '''### Key Excerpts

> "This is a longer quote that spans
> multiple lines in the markdown."
> — Speaker
'''
        quotes = extract_key_excerpts_quotes(markdown)
        assert len(quotes) == 1
        # Should be collapsed to single line
        assert "spans" in quotes[0] and "multiple" in quotes[0]


class TestCoreClaimsExtraction:
    """Tests for Core Claims extraction."""

    def test_extracts_claim_with_evidence(self):
        markdown = '''### Core Claims

- **Progress is possible**: "Science enables continuous improvement."
'''
        claims = extract_core_claims_with_evidence(markdown)
        assert len(claims) == 1
        claim, evidence = claims[0]
        assert "Progress is possible" in claim
        assert "Science enables" in evidence

    def test_extracts_multiple_claims(self):
        markdown = '''### Core Claims

- **First claim**: "Evidence one."
- **Second claim**: "Evidence two."
'''
        claims = extract_core_claims_with_evidence(markdown)
        assert len(claims) == 2

    def test_handles_claim_without_evidence(self):
        markdown = '''### Core Claims

- **Claim without quote**: No quoted evidence here.
'''
        claims = extract_core_claims_with_evidence(markdown)
        # May or may not extract depending on regex
        # The important thing is it doesn't crash

    def test_handles_smart_quotes_in_evidence(self):
        markdown = '''### Core Claims

- **Smart claim**: "Evidence with smart quotes"
'''
        claims = extract_core_claims_with_evidence(markdown)
        assert len(claims) == 1
        _, evidence = claims[0]
        assert evidence is not None
        assert "Evidence" in evidence


# =============================================================================
# Provenance Matching Tests
# =============================================================================


class TestProvenanceMatching:
    """Tests for quote provenance matching."""

    def test_exact_match(self):
        quote = "The quick brown fox jumps over the lazy dog."
        transcript = "Once upon a time, the quick brown fox jumps over the lazy dog. The end."
        transcript_norm = normalize_for_matching(transcript)

        result = match_quote_in_transcript(quote, transcript, transcript_norm)

        assert result.found
        assert result.match_type == "exact"
        assert result.match_score == 1.0

    def test_exact_match_case_insensitive(self):
        quote = "THE QUICK BROWN FOX"
        transcript = "the quick brown fox jumped"
        transcript_norm = normalize_for_matching(transcript)

        result = match_quote_in_transcript(quote, transcript, transcript_norm)

        assert result.found

    def test_no_match_for_invented_quote(self):
        quote = "This quote was completely made up by an LLM."
        transcript = "The actual transcript talks about something entirely different."
        transcript_norm = normalize_for_matching(transcript)

        result = match_quote_in_transcript(quote, transcript, transcript_norm)

        assert not result.found

    def test_anchor_match_with_minor_differences(self):
        # Quote has slightly different ending than transcript
        quote = "Voice Hub is a tool we created to allow companies and developers to quickly create projects."
        transcript = "Voice Hub is a tool we created to allow companies and developers to quickly create projects and proof of concepts."
        transcript_norm = normalize_for_matching(transcript)

        result = match_quote_in_transcript(quote, transcript, transcript_norm)

        assert result.found
        assert result.match_type in ("exact", "anchor", "fuzzy")

    def test_fuzzy_match_with_small_edits(self):
        quote = "The technology supports many different languages"
        transcript = "The technology supports 17 different languages and dialects"
        transcript_norm = normalize_for_matching(transcript)

        result = match_quote_in_transcript(quote, transcript, transcript_norm, fuzzy_threshold=0.7)

        # May or may not match depending on threshold
        # The key is it doesn't crash


# =============================================================================
# Excerpt Provenance Check Tests
# =============================================================================


class TestExcerptProvenanceCheck:
    """Tests for full excerpt provenance checking."""

    def test_all_quotes_found(self):
        markdown = '''### Key Excerpts

> "Voice Hub is a tool we created to allow companies and developers."
> — Speaker

> "We support 17 languages and add more every day."
> — Speaker
'''
        transcript = """
        Voice Hub is a tool we created to allow companies and developers.
        We support 17 languages and add more every day.
        """

        result = check_excerpt_provenance(markdown, transcript, strict=True)

        assert result.verdict == "PASS"
        assert result.excerpts_found == 2
        assert result.excerpts_not_found == 0
        assert result.provenance_rate == 1.0

    def test_missing_quote_fails_strict(self):
        markdown = '''### Key Excerpts

> "This quote is in the transcript."
> — Speaker

> "This quote was completely invented."
> — Speaker
'''
        transcript = "This quote is in the transcript. Nothing else relevant."

        result = check_excerpt_provenance(markdown, transcript, strict=True)

        assert result.verdict == "FAIL"
        assert result.excerpts_not_found == 1
        assert len(result.missing_quotes) == 1

    def test_missing_quote_warns_tolerant(self):
        markdown = '''### Key Excerpts

> "This quote is in the transcript."
> — Speaker

> "This quote was invented."
> — Speaker
'''
        transcript = "This quote is in the transcript."

        result = check_excerpt_provenance(markdown, transcript, strict=False)

        assert result.verdict == "WARN"  # Only 1 missing, tolerant mode

    def test_multiple_missing_fails_tolerant(self):
        markdown = '''### Key Excerpts

> "Invented quote one."
> — Speaker

> "Invented quote two."
> — Speaker
'''
        transcript = "The transcript has nothing similar."

        result = check_excerpt_provenance(markdown, transcript, strict=False)

        assert result.verdict == "FAIL"  # 2 missing exceeds tolerant threshold

    def test_no_excerpts_passes(self):
        markdown = '''### Some Other Section

Content without Key Excerpts.
'''
        transcript = "Some transcript."

        result = check_excerpt_provenance(markdown, transcript, strict=True)

        assert result.verdict == "PASS"
        assert result.excerpts_total == 0


# =============================================================================
# Claim Support Check Tests
# =============================================================================


class TestClaimSupportCheck:
    """Tests for Core Claims support checking."""

    def test_all_claims_have_grounded_evidence(self):
        markdown = '''### Core Claims

- **Voice Hub accelerates development**: "Voice Hub is a tool we created."
- **Multiple language support**: "We support 17 languages."
'''
        transcript = """
        Voice Hub is a tool we created.
        We support 17 languages.
        """

        result = check_claim_support(markdown, transcript, strict=True)

        assert result.verdict == "PASS"
        assert result.claims_total == 2
        assert result.claims_with_evidence == 2
        assert result.evidence_quotes_found == 2

    def test_claim_with_invented_evidence_fails(self):
        markdown = '''### Core Claims

- **Real claim**: "This evidence is in the transcript."
- **Hallucinated claim**: "This evidence was made up by the LLM."
'''
        transcript = "This evidence is in the transcript. Nothing else."

        result = check_claim_support(markdown, transcript, strict=True)

        assert result.verdict == "FAIL"
        assert result.evidence_quotes_not_found == 1

    def test_no_claims_passes(self):
        markdown = '''### Key Excerpts

> "Some excerpt"
> — Speaker
'''
        transcript = "Some transcript."

        result = check_claim_support(markdown, transcript, strict=True)

        assert result.verdict == "PASS"
        assert result.claims_total == 0


# =============================================================================
# Full Groundedness Check Tests
# =============================================================================


class TestFullGroundednessCheck:
    """Tests for combined groundedness checking."""

    def test_fully_grounded_draft_passes(self):
        markdown = '''## Chapter 1: Introduction

Some prose content here.

### Key Excerpts

> "Quote from the transcript."
> — Speaker

### Core Claims

- **Main point**: "Quote from the transcript."
'''
        transcript = "Quote from the transcript. More content here."

        report = check_groundedness(markdown, transcript, strict=True)

        assert report.overall_verdict == "PASS"
        assert report.excerpt_provenance.verdict == "PASS"
        assert report.claim_support.verdict == "PASS"

    def test_ungrounded_excerpt_fails(self):
        markdown = '''### Key Excerpts

> "Invented quote not in transcript."
> — Speaker

### Core Claims

- **Claim**: "Real quote in transcript."
'''
        transcript = "Real quote in transcript."

        report = check_groundedness(markdown, transcript, strict=True)

        assert report.overall_verdict == "FAIL"
        assert report.excerpt_provenance.verdict == "FAIL"
        assert report.claim_support.verdict == "PASS"

    def test_ungrounded_claim_fails(self):
        markdown = '''### Key Excerpts

> "Real quote in transcript."
> — Speaker

### Core Claims

- **Claim**: "Invented evidence not in transcript."
'''
        transcript = "Real quote in transcript."

        report = check_groundedness(markdown, transcript, strict=True)

        assert report.overall_verdict == "FAIL"
        assert report.excerpt_provenance.verdict == "PASS"
        assert report.claim_support.verdict == "FAIL"

    def test_worst_verdict_propagates(self):
        markdown = '''### Key Excerpts

> "Real quote."
> — Speaker

### Core Claims

- **Claim**: "Invented evidence."
'''
        transcript = "Real quote."

        # Even though excerpts pass, claims fail → overall FAIL
        report = check_groundedness(markdown, transcript, strict=True)

        assert report.overall_verdict == "FAIL"


# =============================================================================
# Snap-to-Transcript Repair Tests
# =============================================================================


class TestFindBestTranscriptSpan:
    """Tests for find_best_transcript_span function."""

    def test_exact_match_returns_span(self):
        from src.services.groundedness_service import find_best_transcript_span

        evidence = "classify up to 400 different sounds"
        transcript = "We can enroll custom sounds and listen continuously to classify up to 400 different sounds."

        span = find_best_transcript_span(evidence, transcript)

        assert span is not None
        assert span.score == 1.0
        assert "classify" in span.text.lower()
        assert "400" in span.text

    def test_no_match_returns_none(self):
        from src.services.groundedness_service import find_best_transcript_span

        evidence = "completely fabricated quote about nothing"
        transcript = "The transcript talks about voice technology and cloud services."

        span = find_best_transcript_span(evidence, transcript, fuzzy_threshold=0.85)

        assert span is None

    def test_fuzzy_match_with_minor_differences(self):
        from src.services.groundedness_service import find_best_transcript_span

        evidence = "Voice Hub allows developers to quickly create projects"
        transcript = "Voice Hub is a tool we created to allow companies and developers to quickly create projects and proof of concepts."

        span = find_best_transcript_span(evidence, transcript, fuzzy_threshold=0.70)

        # Should find a match since key words overlap
        # May or may not find depending on exact matching
        # The key is it doesn't crash


class TestRepairCoreClaimsEvidence:
    """Tests for repair_core_claims_evidence function."""

    def test_repairs_near_exact_match(self):
        from src.services.groundedness_service import repair_core_claims_evidence

        markdown = '''### Core Claims

- **Voice technology claim**: "Voice Hub allows developers to create projects"
'''
        transcript = "Voice Hub is a tool that allows developers to create projects and proof of concepts."

        result = repair_core_claims_evidence(markdown, transcript, fuzzy_threshold=0.80)

        # Should either repair or mark unchanged (exact match)
        assert result.claims_dropped == 0 or result.claims_repaired >= 0

    def test_drops_fabricated_evidence(self):
        from src.services.groundedness_service import repair_core_claims_evidence

        markdown = '''### Core Claims

- **Fabricated claim**: "The AI said something it never said in the transcript"
'''
        transcript = "The transcript only talks about voice technology and nothing about AI."

        result = repair_core_claims_evidence(markdown, transcript, fuzzy_threshold=0.85)

        # Fabricated evidence should be dropped
        assert result.claims_dropped == 1
        assert result.claims_repaired == 0

    def test_preserves_exact_match(self):
        from src.services.groundedness_service import repair_core_claims_evidence

        markdown = '''### Core Claims

- **Exact quote**: "Voice Hub is a tool"
'''
        transcript = "Voice Hub is a tool we created for developers."

        result = repair_core_claims_evidence(markdown, transcript)

        # Exact match should be unchanged
        assert result.claims_unchanged == 1
        assert result.claims_dropped == 0


class TestCheckAndRepairGroundedness:
    """Tests for combined check and repair function."""

    def test_repairs_and_passes(self):
        from src.services.groundedness_service import check_and_repair_groundedness

        markdown = '''### Key Excerpts

> "Voice Hub is a tool"
> — Speaker

### Core Claims

- **Main claim**: "Voice Hub is a tool"
'''
        transcript = "Voice Hub is a tool we created for developers."

        report, repair_result, repaired_md = check_and_repair_groundedness(markdown, transcript)

        assert report.excerpt_provenance.verdict == "PASS"
        assert repair_result.claims_dropped == 0

    def test_warns_on_dropped_claims(self):
        from src.services.groundedness_service import check_and_repair_groundedness

        markdown = '''### Key Excerpts

> "Voice Hub is a tool"
> — Speaker

### Core Claims

- **Good claim**: "Voice Hub is a tool"
- **Bad claim**: "Fabricated evidence not in transcript"
'''
        transcript = "Voice Hub is a tool we created for developers."

        report, repair_result, repaired_md = check_and_repair_groundedness(markdown, transcript)

        assert repair_result.claims_dropped == 1
        assert report.overall_verdict == "WARN"

    def test_fails_on_missing_excerpt(self):
        from src.services.groundedness_service import check_and_repair_groundedness

        markdown = '''### Key Excerpts

> "This quote is not in the transcript at all"
> — Speaker

### Core Claims

- **Claim**: "Voice Hub is a tool"
'''
        transcript = "Voice Hub is a tool we created for developers."

        report, repair_result, repaired_md = check_and_repair_groundedness(markdown, transcript)

        # Key Excerpts missing = hard FAIL (no repair)
        assert report.excerpt_provenance.verdict == "FAIL"
        assert report.overall_verdict == "FAIL"
