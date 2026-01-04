"""Schema contract tests for Evidence Map models (Spec 009).

These tests ensure the Evidence Map models serialize/deserialize correctly
and maintain schema compatibility.
"""

import pytest
from datetime import datetime, timezone

from src.models.evidence_map import (
    EvidenceMap,
    ChapterEvidence,
    EvidenceEntry,
    SupportQuote,
    MustIncludeItem,
    TranscriptRange,
    GlobalContext,
    SpeakerInfo,
    ClaimType,
    MustIncludePriority,
)
from src.models.style_config import ContentMode


class TestSupportQuote:
    """Tests for SupportQuote model."""

    def test_minimal_quote(self):
        """Test minimal SupportQuote creation."""
        quote = SupportQuote(quote="The key insight is...")
        assert quote.quote == "The key insight is..."
        assert quote.start_char is None
        assert quote.end_char is None
        assert quote.speaker is None

    def test_full_quote(self):
        """Test SupportQuote with all fields."""
        quote = SupportQuote(
            quote="I believe this approach works best",
            start_char=100,
            end_char=135,
            speaker="John Smith"
        )
        assert quote.quote == "I believe this approach works best"
        assert quote.start_char == 100
        assert quote.end_char == 135
        assert quote.speaker == "John Smith"

    def test_serialization(self):
        """Test SupportQuote serializes to dict correctly."""
        quote = SupportQuote(
            quote="Test quote",
            start_char=0,
            end_char=10,
            speaker="Speaker"
        )
        data = quote.model_dump()
        assert data["quote"] == "Test quote"
        assert data["start_char"] == 0
        assert data["end_char"] == 10
        assert data["speaker"] == "Speaker"

    def test_extra_fields_forbidden(self):
        """Test that extra fields are rejected."""
        with pytest.raises(Exception):
            SupportQuote(quote="Test", extra_field="not allowed")


class TestEvidenceEntry:
    """Tests for EvidenceEntry model."""

    def test_minimal_entry(self):
        """Test EvidenceEntry with required fields only."""
        entry = EvidenceEntry(
            id="claim_001",
            claim="Users prefer simplicity",
            support=[SupportQuote(quote="Keep it simple")]
        )
        assert entry.id == "claim_001"
        assert entry.claim == "Users prefer simplicity"
        assert len(entry.support) == 1
        assert entry.confidence == 0.8  # default
        assert entry.claim_type == ClaimType.factual  # default

    def test_full_entry(self):
        """Test EvidenceEntry with all fields."""
        entry = EvidenceEntry(
            id="claim_002",
            claim="The speaker recommends daily standups",
            support=[
                SupportQuote(quote="I recommend daily standups", speaker="Speaker A"),
                SupportQuote(quote="Standups keep the team aligned", speaker="Speaker A"),
            ],
            confidence=0.95,
            claim_type=ClaimType.recommendation
        )
        assert entry.id == "claim_002"
        assert len(entry.support) == 2
        assert entry.confidence == 0.95
        assert entry.claim_type == ClaimType.recommendation

    def test_support_required(self):
        """Test that at least one support quote is required."""
        with pytest.raises(Exception):
            EvidenceEntry(
                id="claim_003",
                claim="Unsupported claim",
                support=[]  # Empty list should fail
            )

    def test_confidence_bounds(self):
        """Test confidence is bounded 0-1."""
        with pytest.raises(Exception):
            EvidenceEntry(
                id="claim_004",
                claim="Test",
                support=[SupportQuote(quote="Test")],
                confidence=1.5  # Out of bounds
            )


class TestChapterEvidence:
    """Tests for ChapterEvidence model."""

    def test_minimal_chapter(self):
        """Test ChapterEvidence with minimal fields."""
        chapter = ChapterEvidence(
            chapter_index=1,
            chapter_title="Introduction"
        )
        assert chapter.chapter_index == 1
        assert chapter.chapter_title == "Introduction"
        assert chapter.claims == []
        assert chapter.must_include == []
        assert chapter.forbidden == []

    def test_full_chapter(self):
        """Test ChapterEvidence with all fields."""
        chapter = ChapterEvidence(
            chapter_index=2,
            chapter_title="Getting Started",
            outline_item_id="ch_002",
            claims=[
                EvidenceEntry(
                    id="claim_001",
                    claim="Test claim",
                    support=[SupportQuote(quote="Test quote")]
                )
            ],
            must_include=[
                MustIncludeItem(
                    point="Define the problem",
                    priority=MustIncludePriority.critical,
                    evidence_ids=["claim_001"]
                )
            ],
            forbidden=["action_steps", "biography"],
            transcript_range=TranscriptRange(start_char=0, end_char=1000)
        )
        assert chapter.chapter_index == 2
        assert len(chapter.claims) == 1
        assert len(chapter.must_include) == 1
        assert "action_steps" in chapter.forbidden

    def test_chapter_index_positive(self):
        """Test chapter_index must be >= 1."""
        with pytest.raises(Exception):
            ChapterEvidence(chapter_index=0, chapter_title="Bad")


class TestEvidenceMap:
    """Tests for EvidenceMap model."""

    def test_minimal_map(self):
        """Test EvidenceMap with minimal fields."""
        emap = EvidenceMap(
            project_id="proj_123",
            content_mode=ContentMode.interview,
            transcript_hash="abc123"
        )
        assert emap.version == 1
        assert emap.project_id == "proj_123"
        assert emap.content_mode == ContentMode.interview
        assert emap.strict_grounded is True
        assert emap.transcript_hash == "abc123"
        assert emap.chapters == []

    def test_full_map(self):
        """Test EvidenceMap with all fields."""
        emap = EvidenceMap(
            version=1,
            project_id="proj_456",
            content_mode=ContentMode.tutorial,
            strict_grounded=False,
            generated_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            transcript_hash="def456",
            chapters=[
                ChapterEvidence(chapter_index=1, chapter_title="Chapter 1"),
                ChapterEvidence(chapter_index=2, chapter_title="Chapter 2"),
            ],
            global_context=GlobalContext(
                speakers=[SpeakerInfo(name="John Doe", role="Host")],
                main_topics=["AI", "Machine Learning"],
                key_terms=["neural network", "deep learning"]
            )
        )
        assert len(emap.chapters) == 2
        assert emap.global_context is not None
        assert len(emap.global_context.speakers) == 1

    def test_serialization_roundtrip(self):
        """Test Evidence Map serializes and deserializes correctly."""
        original = EvidenceMap(
            project_id="proj_789",
            content_mode=ContentMode.essay,
            transcript_hash="roundtrip_test",
            chapters=[
                ChapterEvidence(
                    chapter_index=1,
                    chapter_title="Test Chapter",
                    claims=[
                        EvidenceEntry(
                            id="c1",
                            claim="Test claim",
                            support=[SupportQuote(quote="Test quote", start_char=0, end_char=10)]
                        )
                    ]
                )
            ]
        )

        # Serialize to dict
        data = original.model_dump()

        # Deserialize back
        restored = EvidenceMap.model_validate(data)

        assert restored.project_id == original.project_id
        assert restored.content_mode == original.content_mode
        assert len(restored.chapters) == 1
        assert restored.chapters[0].claims[0].id == "c1"


class TestGlobalContext:
    """Tests for GlobalContext model."""

    def test_empty_context(self):
        """Test GlobalContext with defaults."""
        ctx = GlobalContext()
        assert ctx.speakers == []
        assert ctx.main_topics == []
        assert ctx.key_terms == []

    def test_full_context(self):
        """Test GlobalContext with all fields."""
        ctx = GlobalContext(
            speakers=[
                SpeakerInfo(name="Alice", role="CEO", mentioned_credentials="MBA, Stanford"),
                SpeakerInfo(name="Bob", role="CTO"),
            ],
            main_topics=["Strategy", "Innovation"],
            key_terms=["disruption", "market fit"]
        )
        assert len(ctx.speakers) == 2
        assert ctx.speakers[0].mentioned_credentials == "MBA, Stanford"


class TestClaimTypes:
    """Tests for ClaimType enum."""

    def test_all_claim_types(self):
        """Test all claim types are valid."""
        assert ClaimType.factual.value == "factual"
        assert ClaimType.opinion.value == "opinion"
        assert ClaimType.recommendation.value == "recommendation"
        assert ClaimType.anecdote.value == "anecdote"
        assert ClaimType.definition.value == "definition"


class TestMustIncludePriority:
    """Tests for MustIncludePriority enum."""

    def test_all_priorities(self):
        """Test all priority levels are valid."""
        assert MustIncludePriority.critical.value == "critical"
        assert MustIncludePriority.important.value == "important"
        assert MustIncludePriority.optional.value == "optional"
