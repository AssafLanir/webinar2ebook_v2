"""Unit tests for data normalization helpers."""

import pytest

from src.services.normalization import (
    normalize_style_config,
    normalize_visual_plan,
    normalize_project_data,
)
from src.models import StyleConfigEnvelope, VisualPlan, STYLE_CONFIG_VERSION


class TestNormalizeStyleConfig:
    """Tests for style config normalization."""

    def test_normalize_none_returns_none(self):
        """Test that None input returns None."""
        result = normalize_style_config(None)
        assert result is None

    def test_normalize_valid_envelope_passthrough(self):
        """Test that valid envelope format passes through."""
        data = {
            "version": 1,
            "preset_id": "test_preset",
            "style": {
                "tone": "friendly",
                "target_audience": "beginners",
            },
        }
        result = normalize_style_config(data)

        assert isinstance(result, StyleConfigEnvelope)
        assert result.version == 1
        assert result.preset_id == "test_preset"
        assert result.style.tone == "friendly"
        assert result.style.target_audience == "beginners"

    def test_normalize_legacy_format_migrates(self):
        """Test that legacy format is migrated to envelope."""
        legacy_data = {
            "audience": "technical",
            "tone": "formal",
            "depth": "comprehensive",
            "targetPages": 80,
        }
        result = normalize_style_config(legacy_data)

        assert isinstance(result, StyleConfigEnvelope)
        assert result.version == STYLE_CONFIG_VERSION
        assert result.preset_id == "legacy_migrated"
        # Check mapped values
        assert result.style.target_audience == "intermediate"  # technical -> intermediate
        assert result.style.tone == "professional"  # formal -> professional
        assert result.style.chapter_length_target == "long"  # comprehensive -> long
        assert result.style.chapter_count_target == 8  # 80 pages / 10 = 8 chapters

    def test_normalize_legacy_audience_mapping(self):
        """Test legacy audience value mapping."""
        test_cases = [
            ("general", "mixed"),
            ("technical", "intermediate"),
            ("executive", "advanced"),
            ("academic", "advanced"),
        ]
        for legacy_value, expected in test_cases:
            result = normalize_style_config({"audience": legacy_value})
            assert result.style.target_audience == expected, f"Failed for {legacy_value}"

    def test_normalize_legacy_tone_mapping(self):
        """Test legacy tone value mapping."""
        test_cases = [
            ("formal", "professional"),
            ("conversational", "conversational"),
            ("instructional", "professional"),
            ("persuasive", "authoritative"),
        ]
        for legacy_value, expected in test_cases:
            result = normalize_style_config({"tone": legacy_value})
            assert result.style.tone == expected, f"Failed for {legacy_value}"

    def test_normalize_legacy_depth_mapping(self):
        """Test legacy depth value mapping to chapter_length_target."""
        test_cases = [
            ("overview", "short"),
            ("moderate", "medium"),
            ("comprehensive", "long"),
        ]
        for legacy_value, expected in test_cases:
            result = normalize_style_config({"depth": legacy_value})
            assert result.style.chapter_length_target == expected, f"Failed for {legacy_value}"

    def test_normalize_legacy_target_pages(self):
        """Test legacy targetPages conversion to chapter_count_target."""
        test_cases = [
            (10, 3),   # 10 pages -> 3 chapters (minimum)
            (30, 3),   # 30 pages -> 3 chapters
            (50, 5),   # 50 pages -> 5 chapters
            (100, 10),  # 100 pages -> 10 chapters
            (200, 20),  # 200 pages -> 20 chapters (maximum)
            (300, 20),  # 300 pages -> 20 chapters (capped)
        ]
        for pages, expected in test_cases:
            result = normalize_style_config({"targetPages": pages})
            assert result.style.chapter_count_target == expected, f"Failed for {pages} pages"

    def test_normalize_partial_style_config(self):
        """Test normalizing a partial StyleConfig (not legacy, not envelope)."""
        # This tests the fallback path - note that "tone" is also a legacy key
        # so it will trigger legacy migration, but with new-style values
        partial_data = {
            "tone": "friendly",
        }
        result = normalize_style_config(partial_data)

        assert isinstance(result, StyleConfigEnvelope)
        # "tone" is a legacy key, so triggers legacy migration
        assert result.preset_id == "legacy_migrated"
        # But the mapping falls through since "friendly" isn't in the legacy map
        assert result.style.tone == "professional"  # Default since "friendly" not in map

    def test_normalize_unknown_format_returns_none(self):
        """Test that completely unknown format returns None."""
        # Data that doesn't match envelope, legacy, or partial style config
        unknown_data = {
            "completely_unknown_field": "value",
        }
        result = normalize_style_config(unknown_data)
        # Falls through to try parsing as StyleConfig, which fails, returns None
        assert result is None

    def test_normalize_empty_legacy_uses_defaults(self):
        """Test that empty legacy format uses StyleConfig defaults."""
        # Just has a legacy key but empty value
        result = normalize_style_config({"audience": None})

        assert isinstance(result, StyleConfigEnvelope)
        # Should have default values
        assert result.style.tone == "professional"


class TestNormalizeVisualPlan:
    """Tests for visual plan normalization."""

    def test_normalize_none_returns_empty_plan(self):
        """Test that None input returns empty VisualPlan."""
        result = normalize_visual_plan(None)

        assert isinstance(result, VisualPlan)
        assert result.opportunities == []
        assert result.assets == []

    def test_normalize_valid_plan_passthrough(self):
        """Test that valid plan passes through."""
        data = {
            "opportunities": [
                {
                    "id": "opp-1",
                    "chapter_index": 2,
                    "visual_type": "diagram",
                    "title": "Test",
                    "prompt": "Test prompt",
                    "caption": "Test caption",
                }
            ],
            "assets": [
                {
                    "id": "asset-1",
                    "filename": "test.png",
                    "media_type": "image/png",
                }
            ],
        }
        result = normalize_visual_plan(data)

        assert isinstance(result, VisualPlan)
        assert len(result.opportunities) == 1
        assert result.opportunities[0].id == "opp-1"
        assert len(result.assets) == 1
        assert result.assets[0].id == "asset-1"

    def test_normalize_empty_dict_returns_empty_plan(self):
        """Test that empty dict returns empty VisualPlan."""
        result = normalize_visual_plan({})

        assert isinstance(result, VisualPlan)
        assert result.opportunities == []
        assert result.assets == []

    def test_normalize_partial_plan_fills_defaults(self):
        """Test that partial plan fills missing fields."""
        data = {"opportunities": []}  # Missing assets
        result = normalize_visual_plan(data)

        assert isinstance(result, VisualPlan)
        assert result.opportunities == []
        assert result.assets == []

    def test_normalize_invalid_data_returns_empty(self):
        """Test that invalid data returns empty VisualPlan."""
        invalid_data = {"invalid_field": "value"}
        result = normalize_visual_plan(invalid_data)

        assert isinstance(result, VisualPlan)
        assert result.opportunities == []
        assert result.assets == []


class TestNormalizeProjectData:
    """Tests for full project data normalization."""

    def test_normalize_project_with_legacy_style(self):
        """Test normalizing project doc with legacy style config."""
        doc = {
            "_id": "test-id",
            "name": "Test Project",
            "styleConfig": {"audience": "executive", "tone": "formal"},
            "visualPlan": None,
        }
        result = normalize_project_data(doc)

        # styleConfig should be normalized to envelope
        assert result["styleConfig"] is not None
        assert result["styleConfig"]["version"] == STYLE_CONFIG_VERSION
        assert result["styleConfig"]["preset_id"] == "legacy_migrated"
        assert result["styleConfig"]["style"]["target_audience"] == "advanced"

        # visualPlan should be initialized
        assert result["visualPlan"] is not None
        assert result["visualPlan"]["opportunities"] == []
        assert result["visualPlan"]["assets"] == []

    def test_normalize_project_with_canonical_shapes(self):
        """Test normalizing project that already has canonical shapes."""
        doc = {
            "_id": "test-id",
            "name": "Test Project",
            "styleConfig": {
                "version": 1,
                "preset_id": "test",
                "style": {"tone": "friendly"},
            },
            "visualPlan": {
                "opportunities": [],
                "assets": [],
            },
        }
        result = normalize_project_data(doc)

        # Should pass through unchanged
        assert result["styleConfig"]["preset_id"] == "test"
        assert result["visualPlan"]["opportunities"] == []

    def test_normalize_project_with_missing_fields(self):
        """Test normalizing project with missing styleConfig and visualPlan."""
        doc = {
            "_id": "test-id",
            "name": "Test Project",
            # styleConfig and visualPlan missing
        }
        result = normalize_project_data(doc)

        # styleConfig should be None (caller decides default)
        assert result["styleConfig"] is None

        # visualPlan should be initialized to empty
        assert result["visualPlan"] is not None
        assert result["visualPlan"]["opportunities"] == []
        assert result["visualPlan"]["assets"] == []

    def test_round_trip_preserves_canonical_shapes(self):
        """Test that normalizing canonical shapes preserves them exactly."""
        original = {
            "_id": "test-id",
            "styleConfig": {
                "version": 1,
                "preset_id": "custom",
                "style": {
                    "tone": "authoritative",
                    "target_audience": "advanced",
                    "book_format": "executive_brief",
                },
            },
            "visualPlan": {
                "opportunities": [
                    {
                        "id": "opp-1",
                        "chapter_index": 1,
                        "visual_type": "chart",
                        "title": "Revenue Chart",
                        "prompt": "Show revenue growth",
                        "caption": "Figure 1",
                    }
                ],
                "assets": [],
            },
        }

        result = normalize_project_data(original.copy())

        # Style config should be preserved
        assert result["styleConfig"]["preset_id"] == "custom"
        assert result["styleConfig"]["style"]["tone"] == "authoritative"

        # Visual plan should be preserved
        assert len(result["visualPlan"]["opportunities"]) == 1
        assert result["visualPlan"]["opportunities"][0]["title"] == "Revenue Chart"
