"""Unit tests for evidence extraction service (Spec 009 US1).

Tests for:
- T012: Evidence extraction functions
- T014: Empty evidence handling (FR-009a)
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import json

from src.services.evidence_service import (
    generate_evidence_map,
    extract_claims_for_chapter,
    find_supporting_quotes,
    handle_empty_evidence,
    detect_content_type,
    generate_mode_warning,
    check_interview_constraints,
    get_evidence_for_chapter,
    count_total_claims,
    evidence_map_to_summary,
    _parse_claims_response,
    _parse_must_include_response,
)
from src.models import ChapterPlan
from src.models.evidence_map import (
    EvidenceMap,
    ChapterEvidence,
    EvidenceEntry,
    SupportQuote,
    MustIncludeItem,
    MustIncludePriority,
    ClaimType,
)
from src.models.style_config import ContentMode


class TestFindSupportingQuotes:
    """Tests for find_supporting_quotes helper (T012)."""

    def test_finds_matching_sentences(self):
        """Test basic quote matching."""
        transcript = (
            "Machine learning is transforming industries. "
            "The key to success is data quality. "
            "Without good data, models fail."
        )
        claim = "Data quality is important for machine learning"

        quotes = find_supporting_quotes(claim, transcript, max_quotes=3)

        assert len(quotes) >= 1
        # Should find the data quality sentence
        assert any("data" in q.quote.lower() for q in quotes)

    def test_returns_character_positions(self):
        """Test that character positions are correct."""
        transcript = "First sentence. Second important point. Third item."
        claim = "important point"

        quotes = find_supporting_quotes(claim, transcript, max_quotes=1)

        if quotes:  # May not find matches depending on algorithm
            assert quotes[0].start_char is not None
            assert quotes[0].end_char is not None
            assert quotes[0].start_char < quotes[0].end_char

    def test_handles_empty_transcript(self):
        """Test with empty transcript."""
        quotes = find_supporting_quotes("test claim", "", max_quotes=3)
        assert quotes == []

    def test_handles_no_matches(self):
        """Test when no matching quotes found."""
        transcript = "Completely unrelated content about cats and dogs."
        claim = "Machine learning algorithms require large datasets"

        quotes = find_supporting_quotes(claim, transcript, max_quotes=3)
        # May return empty or low-confidence matches
        assert isinstance(quotes, list)

    def test_respects_max_quotes(self):
        """Test max_quotes limit."""
        transcript = (
            "Data is important. Data quality matters. "
            "Data processing is key. Data analysis helps. "
            "Data science is growing."
        )
        claim = "data is crucial"

        quotes = find_supporting_quotes(claim, transcript, max_quotes=2)
        assert len(quotes) <= 2


class TestHandleEmptyEvidence:
    """Tests for empty evidence handling (T014, FR-009a)."""

    def test_returns_unchanged_if_sufficient(self):
        """Test that chapters with enough claims are unchanged."""
        chapter = ChapterEvidence(
            chapter_index=1,
            chapter_title="Test Chapter",
            claims=[
                EvidenceEntry(
                    id="c1",
                    claim="Test claim",
                    support=[SupportQuote(quote="Test quote")],
                )
            ],
        )

        result = handle_empty_evidence(chapter, "Test Chapter", ContentMode.interview)

        assert len(result.must_include) == 0  # No warning added
        assert len(result.claims) == 1

    def test_adds_warning_if_empty(self):
        """Test warning is added for empty evidence."""
        chapter = ChapterEvidence(
            chapter_index=1,
            chapter_title="Empty Chapter",
            claims=[],
        )

        result = handle_empty_evidence(chapter, "Empty Chapter", ContentMode.interview)

        assert len(result.must_include) == 1
        assert "[SPARSE EVIDENCE]" in result.must_include[0].point

    def test_warning_priority_is_important(self):
        """Test warning has correct priority."""
        chapter = ChapterEvidence(chapter_index=1, chapter_title="Test")

        result = handle_empty_evidence(chapter, "Test", ContentMode.interview)

        assert result.must_include[0].priority == MustIncludePriority.important


class TestDetectContentType:
    """Tests for content mode detection (T022)."""

    def test_detects_interview_style(self):
        """Test interview content detection."""
        transcript = """
        Host: Welcome to the show. Thank you for joining us today.
        Guest: Thanks for having me. I'm excited to be here.
        Host: Tell us about your experience in the field.
        Guest: Well, I've been working in AI for about 10 years...
        """

        mode, confidence = detect_content_type(transcript)

        assert mode == ContentMode.interview
        assert confidence > 0.3

    def test_detects_tutorial_style(self):
        """Test tutorial content detection."""
        transcript = """
        In this tutorial, we'll learn how to build a REST API.
        Step 1: First, install the required packages.
        Step 2: Next, create your main.py file.
        Make sure you don't forget to add error handling.
        Finally, run the server with python main.py.
        """

        mode, confidence = detect_content_type(transcript)

        assert mode == ContentMode.tutorial
        assert confidence > 0.2

    def test_detects_essay_style(self):
        """Test essay content detection."""
        transcript = """
        In this paper, we argue that artificial intelligence
        will fundamentally transform education. Evidence suggests
        that personalized learning improves outcomes. Furthermore,
        research shows significant improvements in engagement.
        In conclusion, the integration of AI in education is inevitable.
        """

        mode, confidence = detect_content_type(transcript)

        assert mode == ContentMode.essay
        assert confidence > 0.2

    def test_handles_ambiguous_content(self):
        """Test with content that doesn't clearly match any mode."""
        transcript = "Some random text without clear markers."

        mode, confidence = detect_content_type(transcript)

        assert mode in [ContentMode.interview, ContentMode.essay, ContentMode.tutorial]
        # Confidence should be lower for ambiguous content


class TestGenerateModeWarning:
    """Tests for mode warning generation (T022)."""

    def test_no_warning_if_modes_match(self):
        """Test no warning when modes match."""
        warning = generate_mode_warning(
            ContentMode.interview,
            ContentMode.interview,
            0.8,
        )
        assert warning is None

    def test_warning_if_modes_differ(self):
        """Test warning when modes differ."""
        warning = generate_mode_warning(
            ContentMode.tutorial,
            ContentMode.interview,
            0.7,
        )
        assert warning is not None
        assert "tutorial" in warning.lower()
        assert "interview" in warning.lower()

    def test_no_warning_for_low_confidence(self):
        """Test no warning for low confidence detection."""
        warning = generate_mode_warning(
            ContentMode.tutorial,
            ContentMode.interview,
            0.2,  # Low confidence
        )
        assert warning is None


class TestParseClaimsResponse:
    """Tests for LLM response parsing."""

    def test_parses_valid_claims(self):
        """Test parsing valid claims response."""
        claims_data = [
            {
                "id": "claim_001",
                "claim": "Test claim about data",
                "support": [
                    {
                        "quote": "Data is important",
                        "start_char": 0,
                        "end_char": 17,
                        "speaker": "John",
                    }
                ],
                "confidence": 0.9,
                "claim_type": "factual",
            }
        ]

        entries = _parse_claims_response(claims_data, chapter_index=1)

        assert len(entries) == 1
        assert entries[0].id == "claim_001"
        assert entries[0].claim == "Test claim about data"
        assert entries[0].confidence == 0.9
        assert entries[0].claim_type == ClaimType.factual
        assert len(entries[0].support) == 1

    def test_skips_claims_without_support(self):
        """Test that claims without support are skipped."""
        claims_data = [
            {
                "id": "claim_001",
                "claim": "Unsupported claim",
                "support": [],  # No support
                "confidence": 0.9,
            }
        ]

        entries = _parse_claims_response(claims_data, chapter_index=1)

        assert len(entries) == 0

    def test_handles_invalid_claim_type(self):
        """Test handling of invalid claim type."""
        claims_data = [
            {
                "id": "c1",
                "claim": "Test",
                "support": [{"quote": "Quote"}],
                "claim_type": "invalid_type",
            }
        ]

        entries = _parse_claims_response(claims_data, chapter_index=1)

        assert len(entries) == 1
        assert entries[0].claim_type == ClaimType.factual  # Default


class TestParseMustIncludeResponse:
    """Tests for must-include parsing."""

    def test_parses_valid_items(self):
        """Test parsing valid must-include items."""
        data = [
            {
                "point": "Key point to include",
                "priority": "critical",
                "evidence_ids": ["c1", "c2"],
            }
        ]

        items = _parse_must_include_response(data)

        assert len(items) == 1
        assert items[0].point == "Key point to include"
        assert items[0].priority == MustIncludePriority.critical
        assert items[0].evidence_ids == ["c1", "c2"]

    def test_handles_invalid_priority(self):
        """Test handling of invalid priority."""
        data = [{"point": "Test", "priority": "invalid"}]

        items = _parse_must_include_response(data)

        assert len(items) == 1
        assert items[0].priority == MustIncludePriority.important  # Default


class TestEvidenceMapUtilities:
    """Tests for Evidence Map utility functions."""

    def test_get_evidence_for_chapter(self):
        """Test getting evidence for specific chapter."""
        evidence_map = EvidenceMap(
            project_id="test",
            content_mode=ContentMode.interview,
            transcript_hash="abc123",
            chapters=[
                ChapterEvidence(chapter_index=1, chapter_title="Ch 1"),
                ChapterEvidence(chapter_index=2, chapter_title="Ch 2"),
            ],
        )

        result = get_evidence_for_chapter(evidence_map, 2)

        assert result is not None
        assert result.chapter_title == "Ch 2"

    def test_get_evidence_for_missing_chapter(self):
        """Test getting evidence for non-existent chapter."""
        evidence_map = EvidenceMap(
            project_id="test",
            content_mode=ContentMode.interview,
            transcript_hash="abc",
            chapters=[],
        )

        result = get_evidence_for_chapter(evidence_map, 1)

        assert result is None

    def test_count_total_claims(self):
        """Test counting total claims."""
        evidence_map = EvidenceMap(
            project_id="test",
            content_mode=ContentMode.interview,
            transcript_hash="abc",
            chapters=[
                ChapterEvidence(
                    chapter_index=1,
                    chapter_title="Ch 1",
                    claims=[
                        EvidenceEntry(
                            id="c1", claim="Claim 1",
                            support=[SupportQuote(quote="Q1")]
                        ),
                        EvidenceEntry(
                            id="c2", claim="Claim 2",
                            support=[SupportQuote(quote="Q2")]
                        ),
                    ],
                ),
                ChapterEvidence(
                    chapter_index=2,
                    chapter_title="Ch 2",
                    claims=[
                        EvidenceEntry(
                            id="c3", claim="Claim 3",
                            support=[SupportQuote(quote="Q3")]
                        ),
                    ],
                ),
            ],
        )

        assert count_total_claims(evidence_map) == 3

    def test_evidence_map_to_summary(self):
        """Test Evidence Map summary generation."""
        evidence_map = EvidenceMap(
            project_id="test_proj",
            content_mode=ContentMode.tutorial,
            strict_grounded=False,
            transcript_hash="hash123",
            chapters=[
                ChapterEvidence(
                    chapter_index=1,
                    chapter_title="Getting Started",
                    claims=[
                        EvidenceEntry(
                            id="c1", claim="Test",
                            support=[SupportQuote(quote="Q")]
                        ),
                    ],
                    must_include=[
                        MustIncludeItem(
                            point="Include this",
                            priority=MustIncludePriority.critical,
                        )
                    ],
                ),
            ],
        )

        summary = evidence_map_to_summary(evidence_map)

        assert summary["total_claims"] == 1
        assert summary["chapters"] == 1
        assert summary["content_mode"] == "tutorial"
        assert summary["strict_grounded"] is False
        assert len(summary["per_chapter_claims"]) == 1
        assert summary["per_chapter_claims"][0]["claims"] == 1
        assert summary["per_chapter_claims"][0]["must_include"] == 1


class TestExtractClaimsForChapter:
    """Tests for claim extraction with LLM (T012)."""

    @pytest.mark.asyncio
    async def test_extracts_claims_from_transcript(self):
        """Test basic claim extraction."""
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "claims": [
                {
                    "id": "claim_001",
                    "claim": "Speaker recommends daily standups",
                    "support": [
                        {
                            "quote": "I always recommend daily standups",
                            "start_char": 10,
                            "end_char": 50,
                            "speaker": "John",
                        }
                    ],
                    "confidence": 0.85,
                    "claim_type": "recommendation",
                }
            ],
            "must_include": [
                {
                    "point": "Daily standup benefits",
                    "priority": "important",
                    "evidence_ids": ["claim_001"],
                }
            ],
        })

        with patch("src.services.evidence_service.LLMClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.complete.return_value = mock_response
            mock_client_class.return_value = mock_client

            result = await extract_claims_for_chapter(
                chapter_index=1,
                chapter_title="Test Chapter",
                transcript_segment="I always recommend daily standups for team alignment.",
                content_mode="interview",
            )

        assert len(result.claims) == 1
        assert result.claims[0].claim == "Speaker recommends daily standups"
        assert len(result.must_include) == 1

    @pytest.mark.asyncio
    async def test_handles_llm_error_gracefully(self):
        """Test graceful handling of LLM errors."""
        with patch("src.services.evidence_service.LLMClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.complete.side_effect = Exception("LLM error")
            mock_client_class.return_value = mock_client

            result = await extract_claims_for_chapter(
                chapter_index=1,
                chapter_title="Test",
                transcript_segment="Test transcript",
            )

        # Should return empty chapter evidence, not raise
        assert result.chapter_index == 1
        assert result.claims == []

    @pytest.mark.asyncio
    async def test_handles_invalid_json_response(self):
        """Test handling of invalid JSON from LLM."""
        mock_response = MagicMock()
        mock_response.content = "not valid json"

        with patch("src.services.evidence_service.LLMClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.complete.return_value = mock_response
            mock_client_class.return_value = mock_client

            result = await extract_claims_for_chapter(
                chapter_index=1,
                chapter_title="Test",
                transcript_segment="Test",
            )

        assert result.claims == []


class TestGenerateEvidenceMap:
    """Tests for full Evidence Map generation (T012)."""

    @pytest.mark.asyncio
    async def test_generates_map_for_all_chapters(self):
        """Test Evidence Map generation for multiple chapters."""
        chapters = [
            ChapterPlan(
                chapter_number=1,
                title="Introduction",
                outline_item_id="ch1",
                goals=[],
                key_points=[],
                transcript_segments=[],
                estimated_words=500,
            ),
            ChapterPlan(
                chapter_number=2,
                title="Main Content",
                outline_item_id="ch2",
                goals=[],
                key_points=[],
                transcript_segments=[],
                estimated_words=1000,
            ),
        ]

        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "claims": [{"id": "c1", "claim": "Test", "support": [{"quote": "Q"}]}],
            "must_include": [],
        })

        with patch("src.services.evidence_service.LLMClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.complete.return_value = mock_response
            mock_client_class.return_value = mock_client

            result = await generate_evidence_map(
                project_id="test_project",
                transcript="Test transcript content here",
                chapters=chapters,
                content_mode=ContentMode.interview,
            )

        assert result.project_id == "test_project"
        assert result.content_mode == ContentMode.interview
        assert len(result.chapters) == 2
        assert result.transcript_hash is not None

    @pytest.mark.asyncio
    async def test_sets_forbidden_for_interview_mode(self):
        """Test that interview mode adds forbidden patterns."""
        chapters = [
            ChapterPlan(
                chapter_number=1,
                title="Test",
                outline_item_id="ch1",
                goals=[],
                key_points=[],
                transcript_segments=[],
                estimated_words=500,
            ),
        ]

        mock_response = MagicMock()
        mock_response.content = json.dumps({"claims": [], "must_include": []})

        with patch("src.services.evidence_service.LLMClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.complete.return_value = mock_response
            mock_client_class.return_value = mock_client

            result = await generate_evidence_map(
                project_id="test",
                transcript="Test",
                chapters=chapters,
                content_mode=ContentMode.interview,
            )

        assert "action_steps" in result.chapters[0].forbidden
        assert "how_to_guides" in result.chapters[0].forbidden
