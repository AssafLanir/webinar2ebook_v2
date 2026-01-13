"""Unit tests for Edition, Fidelity, Coverage enums and SegmentRef, Theme models.

These tests verify:
1. Enum values are correct string values
2. Enums can be constructed from strings
3. Invalid strings are rejected with ValueError
4. SegmentRef model with canonical_hash for offset drift protection
5. Theme model for Ideas Edition
"""

import pytest
from pydantic import ValidationError

from src.models.edition import Coverage, Edition, Fidelity, SegmentRef, Theme


class TestEditionEnum:
    """Test Edition enum."""

    def test_edition_values(self):
        """Verify Edition.QA.value == 'qa', Edition.IDEAS.value == 'ideas'."""
        assert Edition.QA.value == "qa"
        assert Edition.IDEAS.value == "ideas"

    def test_edition_from_string(self):
        """Verify Edition('qa') == Edition.QA."""
        assert Edition("qa") == Edition.QA
        assert Edition("ideas") == Edition.IDEAS


class TestFidelityEnum:
    """Test Fidelity enum."""

    def test_fidelity_values(self):
        """Verify both Fidelity values."""
        assert Fidelity.FAITHFUL.value == "faithful"
        assert Fidelity.VERBATIM.value == "verbatim"

    def test_fidelity_from_string(self):
        """Verify Fidelity can be constructed from strings."""
        assert Fidelity("faithful") == Fidelity.FAITHFUL
        assert Fidelity("verbatim") == Fidelity.VERBATIM


class TestCoverageEnum:
    """Test Coverage enum."""

    def test_coverage_values(self):
        """Verify all three Coverage values."""
        assert Coverage.STRONG.value == "strong"
        assert Coverage.MEDIUM.value == "medium"
        assert Coverage.WEAK.value == "weak"

    def test_coverage_from_string(self):
        """Verify Coverage can be constructed from strings."""
        assert Coverage("strong") == Coverage.STRONG
        assert Coverage("medium") == Coverage.MEDIUM
        assert Coverage("weak") == Coverage.WEAK


class TestInvalidEnumValues:
    """Test that invalid enum values are rejected."""

    def test_invalid_enum_rejected(self):
        """Verify invalid string raises ValueError."""
        with pytest.raises(ValueError):
            Edition("invalid")

        with pytest.raises(ValueError):
            Fidelity("invalid")

        with pytest.raises(ValueError):
            Coverage("invalid")


class TestSegmentRef:
    """Test SegmentRef model for transcript segment references."""

    def test_segment_ref_creation(self):
        """Verify all fields including canonical_hash are properly set."""
        segment = SegmentRef(
            start_offset=100,
            end_offset=500,
            token_count=85,
            text_preview="This is the first ~100 characters of the segment...",
            canonical_hash="abc123def456"
        )
        assert segment.start_offset == 100
        assert segment.end_offset == 500
        assert segment.token_count == 85
        assert segment.text_preview == "This is the first ~100 characters of the segment..."
        assert segment.canonical_hash == "abc123def456"

    def test_segment_ref_validation_negative_offset(self):
        """Verify start_offset < 0 raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            SegmentRef(
                start_offset=-1,
                end_offset=100,
                token_count=50,
                text_preview="preview",
                canonical_hash="hash123"
            )
        assert "start_offset" in str(exc_info.value)

    def test_segment_ref_validation_negative_end_offset(self):
        """Verify end_offset < 0 raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            SegmentRef(
                start_offset=0,
                end_offset=-1,
                token_count=50,
                text_preview="preview",
                canonical_hash="hash123"
            )
        assert "end_offset" in str(exc_info.value)

    def test_segment_ref_validation_negative_token_count(self):
        """Verify token_count < 0 raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            SegmentRef(
                start_offset=0,
                end_offset=100,
                token_count=-1,
                text_preview="preview",
                canonical_hash="hash123"
            )
        assert "token_count" in str(exc_info.value)

    def test_segment_ref_requires_canonical_hash(self):
        """Verify canonical_hash is required (not optional)."""
        with pytest.raises(ValidationError) as exc_info:
            SegmentRef(
                start_offset=0,
                end_offset=100,
                token_count=50,
                text_preview="preview"
                # canonical_hash intentionally omitted
            )
        assert "canonical_hash" in str(exc_info.value)


class TestTheme:
    """Test Theme model for Ideas Edition."""

    def test_theme_creation(self):
        """Verify theme with all fields is created correctly."""
        theme = Theme(
            id="theme-001",
            title="Introduction to Machine Learning",
            one_liner="A primer on ML fundamentals",
            keywords=["machine learning", "AI", "algorithms"],
            coverage=Coverage.STRONG,
            supporting_segments=[],
            include_in_generation=False
        )
        assert theme.id == "theme-001"
        assert theme.title == "Introduction to Machine Learning"
        assert theme.one_liner == "A primer on ML fundamentals"
        assert theme.keywords == ["machine learning", "AI", "algorithms"]
        assert theme.coverage == Coverage.STRONG
        assert theme.supporting_segments == []
        assert theme.include_in_generation is False

    def test_theme_defaults(self):
        """Verify include_in_generation defaults to True."""
        theme = Theme(
            id="theme-002",
            title="Data Processing",
            one_liner="How to handle data",
            keywords=["data", "processing"],
            coverage=Coverage.MEDIUM,
            supporting_segments=[]
        )
        assert theme.include_in_generation is True

    def test_theme_with_segments(self):
        """Verify theme can hold a list of SegmentRefs."""
        segment1 = SegmentRef(
            start_offset=0,
            end_offset=100,
            token_count=20,
            text_preview="First segment preview...",
            canonical_hash="hash_abc"
        )
        segment2 = SegmentRef(
            start_offset=150,
            end_offset=300,
            token_count=35,
            text_preview="Second segment preview...",
            canonical_hash="hash_abc"
        )
        theme = Theme(
            id="theme-003",
            title="Advanced Topics",
            one_liner="Deep dive into advanced concepts",
            keywords=["advanced", "deep dive"],
            coverage=Coverage.WEAK,
            supporting_segments=[segment1, segment2]
        )
        assert len(theme.supporting_segments) == 2
        assert theme.supporting_segments[0].start_offset == 0
        assert theme.supporting_segments[1].start_offset == 150

    def test_serialization_roundtrip(self):
        """Verify Theme with SegmentRefs serializes/deserializes correctly."""
        segment = SegmentRef(
            start_offset=50,
            end_offset=200,
            token_count=30,
            text_preview="Sample preview text",
            canonical_hash="sha256_hash_value"
        )
        original_theme = Theme(
            id="theme-roundtrip",
            title="Roundtrip Test",
            one_liner="Testing serialization",
            keywords=["test", "serialization"],
            coverage=Coverage.STRONG,
            supporting_segments=[segment],
            include_in_generation=True
        )

        # Serialize to dict/JSON
        serialized = original_theme.model_dump()

        # Deserialize back to model
        restored_theme = Theme.model_validate(serialized)

        # Verify all fields match
        assert restored_theme.id == original_theme.id
        assert restored_theme.title == original_theme.title
        assert restored_theme.one_liner == original_theme.one_liner
        assert restored_theme.keywords == original_theme.keywords
        assert restored_theme.coverage == original_theme.coverage
        assert restored_theme.include_in_generation == original_theme.include_in_generation
        assert len(restored_theme.supporting_segments) == 1

        restored_segment = restored_theme.supporting_segments[0]
        assert restored_segment.start_offset == segment.start_offset
        assert restored_segment.end_offset == segment.end_offset
        assert restored_segment.token_count == segment.token_count
        assert restored_segment.text_preview == segment.text_preview
        assert restored_segment.canonical_hash == segment.canonical_hash
