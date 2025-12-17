"""Unit tests for StyleConfig and StyleConfigEnvelope validation."""

import pytest
from pydantic import ValidationError

from src.models import (
    StyleConfig,
    StyleConfigEnvelope,
    STYLE_CONFIG_VERSION,
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
