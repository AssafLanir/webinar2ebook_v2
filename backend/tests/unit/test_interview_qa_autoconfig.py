"""Tests for Interview Q&A auto-configuration (T010).

Verifies:
- normalize_style_config() enforces settings for interview_qa format
- Original settings preserved for other formats
- All required fields are set correctly when interview_qa selected
"""

import pytest

from src.services.normalization import normalize_style_config


class TestInterviewQAAutoConfiguration:
    """Test automatic configuration enforcement for interview_qa format."""

    def test_interview_qa_forces_strict_faithfulness(self):
        """interview_qa format should force faithfulness_level to strict."""
        data = {
            "version": 1,
            "preset_id": "test",
            "style": {
                "book_format": "interview_qa",
                "tone": "conversational",
                "faithfulness_level": "balanced",  # Will be overridden
            },
        }
        result = normalize_style_config(data)
        assert result is not None
        assert result.style.faithfulness_level.value == "strict"

    def test_interview_qa_disables_takeaways(self):
        """interview_qa format should disable include_key_takeaways."""
        data = {
            "version": 1,
            "preset_id": "test",
            "style": {
                "book_format": "interview_qa",
                "tone": "conversational",
                "include_key_takeaways": True,  # Will be overridden
            },
        }
        result = normalize_style_config(data)
        assert result is not None
        assert result.style.include_key_takeaways is False

    def test_interview_qa_disables_action_steps(self):
        """interview_qa format should disable include_action_steps."""
        data = {
            "version": 1,
            "preset_id": "test",
            "style": {
                "book_format": "interview_qa",
                "tone": "conversational",
                "include_action_steps": True,  # Will be overridden
            },
        }
        result = normalize_style_config(data)
        assert result is not None
        assert result.style.include_action_steps is False

    def test_interview_qa_disables_checklists(self):
        """interview_qa format should disable include_checklists."""
        data = {
            "version": 1,
            "preset_id": "test",
            "style": {
                "book_format": "interview_qa",
                "tone": "conversational",
                "include_checklists": True,  # Will be overridden
            },
        }
        result = normalize_style_config(data)
        assert result is not None
        assert result.style.include_checklists is False

    def test_interview_qa_sets_no_extrapolation(self):
        """interview_qa format should set allowed_extrapolation to none."""
        data = {
            "version": 1,
            "preset_id": "test",
            "style": {
                "book_format": "interview_qa",
                "tone": "conversational",
                "allowed_extrapolation": "moderate",  # Will be overridden
            },
        }
        result = normalize_style_config(data)
        assert result is not None
        assert result.style.allowed_extrapolation.value == "none"


class TestOtherFormatsPreserved:
    """Test that other book formats preserve their settings."""

    def test_guide_format_preserves_takeaways(self):
        """guide format should preserve include_key_takeaways setting."""
        data = {
            "version": 1,
            "preset_id": "test",
            "style": {
                "book_format": "guide",
                "tone": "professional",
                "include_key_takeaways": True,
            },
        }
        result = normalize_style_config(data)
        assert result is not None
        assert result.style.include_key_takeaways is True

    def test_tutorial_format_preserves_action_steps(self):
        """tutorial format should preserve include_action_steps setting."""
        data = {
            "version": 1,
            "preset_id": "test",
            "style": {
                "book_format": "tutorial",
                "tone": "friendly",
                "include_action_steps": True,
            },
        }
        result = normalize_style_config(data)
        assert result is not None
        assert result.style.include_action_steps is True

    def test_handbook_format_preserves_faithfulness(self):
        """handbook format should preserve faithfulness_level setting."""
        data = {
            "version": 1,
            "preset_id": "test",
            "style": {
                "book_format": "handbook",
                "tone": "professional",
                "faithfulness_level": "balanced",
            },
        }
        result = normalize_style_config(data)
        assert result is not None
        assert result.style.faithfulness_level.value == "balanced"


class TestAllSettingsEnforced:
    """Test that all required interview_qa settings are enforced together."""

    def test_all_interview_qa_settings_applied(self):
        """All interview_qa settings should be enforced at once."""
        data = {
            "version": 1,
            "preset_id": "custom",
            "style": {
                "book_format": "interview_qa",
                "tone": "conversational",
                # These should all be overridden:
                "faithfulness_level": "creative",
                "include_key_takeaways": True,
                "include_action_steps": True,
                "include_checklists": True,
                "allowed_extrapolation": "moderate",
            },
        }
        result = normalize_style_config(data)

        assert result is not None
        assert result.style.book_format.value == "interview_qa"
        assert result.style.faithfulness_level.value == "strict"
        assert result.style.include_key_takeaways is False
        assert result.style.include_action_steps is False
        assert result.style.include_checklists is False
        assert result.style.allowed_extrapolation.value == "none"

        # These should be preserved:
        assert result.style.tone.value == "conversational"
