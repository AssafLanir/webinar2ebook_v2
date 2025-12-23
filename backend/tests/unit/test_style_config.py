"""Unit tests for StyleConfig and StyleConfigEnvelope validation."""

import pytest
from pydantic import ValidationError

from src.models import (
    StyleConfig,
    StyleConfigEnvelope,
    STYLE_CONFIG_VERSION,
)
from src.models.style_config import (
    compute_words_per_chapter,
    TotalLengthPreset,
    DetailLevel,
    TOTAL_LENGTH_WORD_TARGETS,
    MIN_WORDS_PER_CHAPTER,
    MAX_WORDS_PER_CHAPTER,
)
from src.models.style_config_migrations import migrate_style_config_envelope


class TestStyleConfig:
    """Tests for StyleConfig model."""

    def test_create_default_style_config(self):
        """Test creating a StyleConfig with all defaults."""
        config = StyleConfig()
        assert config.tone == "professional"
        assert config.book_format == "guide"
        assert config.target_audience == "mixed"
        assert config.chapter_count_target == 8

    def test_create_style_config_with_values(self):
        """Test creating a StyleConfig with explicit values."""
        config = StyleConfig(
            tone="friendly",
            book_format="tutorial",
            target_audience="beginners",
            chapter_count_target=10,
        )
        assert config.tone == "friendly"
        assert config.book_format == "tutorial"
        assert config.target_audience == "beginners"
        assert config.chapter_count_target == 10

    def test_style_config_invalid_tone(self):
        """Test that invalid tone value raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            StyleConfig(tone="invalid_tone")
        assert "tone" in str(exc_info.value)

    def test_style_config_invalid_book_format(self):
        """Test that invalid book_format value raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            StyleConfig(book_format="invalid_format")
        assert "book_format" in str(exc_info.value)

    def test_style_config_chapter_count_bounds(self):
        """Test chapter_count_target bounds (ge=3, le=20)."""
        # Valid values at bounds
        config = StyleConfig(chapter_count_target=3)
        assert config.chapter_count_target == 3

        config = StyleConfig(chapter_count_target=20)
        assert config.chapter_count_target == 20

        # Invalid: below minimum
        with pytest.raises(ValidationError):
            StyleConfig(chapter_count_target=2)

        # Invalid: above maximum
        with pytest.raises(ValidationError):
            StyleConfig(chapter_count_target=21)

    def test_style_config_extra_fields_forbidden(self):
        """Test that extra fields are forbidden."""
        with pytest.raises(ValidationError) as exc_info:
            StyleConfig(unknown_field="value")
        assert "extra" in str(exc_info.value).lower()

    def test_style_config_preferred_visual_types(self):
        """Test preferred_visual_types list."""
        config = StyleConfig(
            preferred_visual_types=["diagram", "chart", "screenshot"]
        )
        assert len(config.preferred_visual_types) == 3
        assert "diagram" in config.preferred_visual_types


class TestStyleConfigEnvelope:
    """Tests for StyleConfigEnvelope model."""

    def test_create_default_envelope(self):
        """Test creating an envelope with defaults."""
        envelope = StyleConfigEnvelope()
        assert envelope.version == STYLE_CONFIG_VERSION
        assert envelope.preset_id == "default_webinar_ebook_v1"
        assert isinstance(envelope.style, StyleConfig)

    def test_create_envelope_with_preset(self):
        """Test creating an envelope with a custom preset_id."""
        envelope = StyleConfigEnvelope(
            preset_id="custom_preset",
            style=StyleConfig(tone="friendly"),
        )
        assert envelope.preset_id == "custom_preset"
        assert envelope.style.tone == "friendly"

    def test_envelope_version_must_be_positive(self):
        """Test that version must be >= 1."""
        with pytest.raises(ValidationError) as exc_info:
            StyleConfigEnvelope(version=0)
        assert "version" in str(exc_info.value)

    def test_envelope_extra_fields_forbidden(self):
        """Test that extra fields are forbidden on envelope."""
        with pytest.raises(ValidationError) as exc_info:
            StyleConfigEnvelope(unknown_field="value")
        assert "extra" in str(exc_info.value).lower()

    def test_envelope_serialization(self):
        """Test envelope serialization to dict."""
        envelope = StyleConfigEnvelope(
            preset_id="test_preset",
            style=StyleConfig(tone="authoritative"),
        )
        data = envelope.model_dump()

        assert data["version"] == STYLE_CONFIG_VERSION
        assert data["preset_id"] == "test_preset"
        assert data["style"]["tone"] == "authoritative"

    def test_envelope_deserialization(self):
        """Test envelope deserialization from dict."""
        data = {
            "version": 1,
            "preset_id": "from_dict",
            "style": {
                "tone": "authoritative",
                "book_format": "ebook_marketing",
            },
        }
        envelope = StyleConfigEnvelope.model_validate(data)

        assert envelope.version == 1
        assert envelope.preset_id == "from_dict"
        assert envelope.style.tone == "authoritative"
        assert envelope.style.book_format == "ebook_marketing"


class TestStyleConfigMigrations:
    """Tests for style config migrations."""

    def test_migrate_current_version(self):
        """Test migrating a payload at current version."""
        payload = {
            "version": STYLE_CONFIG_VERSION,
            "preset_id": "test",
            "style": {"tone": "friendly"},
        }
        result = migrate_style_config_envelope(payload)

        assert result["version"] == STYLE_CONFIG_VERSION
        assert result["preset_id"] == "test"
        assert result["style"]["tone"] == "friendly"

    def test_migrate_missing_version(self):
        """Test migrating a payload with no version defaults to 1."""
        payload = {
            "preset_id": "test",
            "style": {"tone": "friendly"},
        }
        result = migrate_style_config_envelope(payload)

        # Should treat missing version as 1
        assert result.get("version") in [None, 1, STYLE_CONFIG_VERSION]

    def test_migrate_future_version(self):
        """Test migrating a payload from a future version."""
        payload = {
            "version": STYLE_CONFIG_VERSION + 100,
            "preset_id": "future",
            "style": {"tone": "friendly"},
        }
        result = migrate_style_config_envelope(payload)

        # Future version should be capped to current
        assert result["version"] == STYLE_CONFIG_VERSION


class TestComputeWordsPerChapter:
    """Tests for compute_words_per_chapter function."""

    def test_standard_preset_8_chapters(self):
        """Test standard preset (~5000 words) with 8 chapters."""
        result = compute_words_per_chapter(TotalLengthPreset.standard, 8)
        # 5000 / 8 = 625
        assert result == 625

    def test_brief_preset_4_chapters(self):
        """Test brief preset (~2000 words) with 4 chapters."""
        result = compute_words_per_chapter(TotalLengthPreset.brief, 4)
        # 2000 / 4 = 500
        assert result == 500

    def test_comprehensive_preset_10_chapters(self):
        """Test comprehensive preset (~10000 words) with 10 chapters."""
        result = compute_words_per_chapter(TotalLengthPreset.comprehensive, 10)
        # 10000 / 10 = 1000
        assert result == 1000

    def test_clamps_to_minimum(self):
        """Test that result is clamped to minimum (250)."""
        # 2000 / 20 = 100, should clamp to 250
        result = compute_words_per_chapter(TotalLengthPreset.brief, 20)
        assert result == MIN_WORDS_PER_CHAPTER

    def test_clamps_to_maximum(self):
        """Test that result is clamped to maximum (2500)."""
        # 10000 / 2 = 5000, should clamp to 2500
        result = compute_words_per_chapter(TotalLengthPreset.comprehensive, 2)
        assert result == MAX_WORDS_PER_CHAPTER

    def test_zero_chapters_returns_minimum(self):
        """Test that 0 chapters returns minimum."""
        result = compute_words_per_chapter(TotalLengthPreset.standard, 0)
        assert result == MIN_WORDS_PER_CHAPTER

    def test_negative_chapters_returns_minimum(self):
        """Test that negative chapters returns minimum."""
        result = compute_words_per_chapter(TotalLengthPreset.standard, -5)
        assert result == MIN_WORDS_PER_CHAPTER

    def test_word_targets_constants(self):
        """Test that word target constants are correct."""
        assert TOTAL_LENGTH_WORD_TARGETS[TotalLengthPreset.brief] == 2000
        assert TOTAL_LENGTH_WORD_TARGETS[TotalLengthPreset.standard] == 5000
        assert TOTAL_LENGTH_WORD_TARGETS[TotalLengthPreset.comprehensive] == 10000


class TestStyleConfigLengthAndDetail:
    """Tests for new length and detail fields in StyleConfig."""

    def test_default_total_length_preset(self):
        """Test default value for total_length_preset."""
        config = StyleConfig()
        assert config.total_length_preset == TotalLengthPreset.standard

    def test_default_detail_level(self):
        """Test default value for detail_level."""
        config = StyleConfig()
        assert config.detail_level == DetailLevel.balanced

    def test_create_with_brief_and_concise(self):
        """Test creating config with brief + concise."""
        config = StyleConfig(
            total_length_preset="brief",
            detail_level="concise",
        )
        assert config.total_length_preset == TotalLengthPreset.brief
        assert config.detail_level == DetailLevel.concise

    def test_create_with_comprehensive_and_detailed(self):
        """Test creating config with comprehensive + detailed."""
        config = StyleConfig(
            total_length_preset="comprehensive",
            detail_level="detailed",
        )
        assert config.total_length_preset == TotalLengthPreset.comprehensive
        assert config.detail_level == DetailLevel.detailed

    def test_invalid_total_length_preset(self):
        """Test that invalid total_length_preset raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            StyleConfig(total_length_preset="invalid")
        assert "total_length_preset" in str(exc_info.value)

    def test_invalid_detail_level(self):
        """Test that invalid detail_level raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            StyleConfig(detail_level="invalid")
        assert "detail_level" in str(exc_info.value)
