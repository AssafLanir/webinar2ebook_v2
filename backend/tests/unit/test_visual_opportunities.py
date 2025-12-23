"""Unit tests for visual opportunity generation."""

import pytest

from src.llm.schemas import load_visual_opportunities_schema, VISUAL_OPPORTUNITIES_SCHEMA
from src.services.prompts import (
    VISUAL_OPPORTUNITY_SYSTEM_PROMPT,
    VISUAL_DENSITY_GUIDANCE,
    build_visual_opportunity_user_prompt,
)
from src.models import ChapterPlan, TranscriptSegment


class TestVisualOpportunitiesSchema:
    """Tests for the visual opportunities JSON schema."""

    def test_schema_is_valid_structure(self):
        """Test that the schema has the expected structure."""
        schema = load_visual_opportunities_schema()

        assert schema["type"] == "object"
        assert "opportunities" in schema["properties"]
        assert schema["properties"]["opportunities"]["type"] == "array"

    def test_schema_item_has_required_fields(self):
        """Test that opportunity items have all required fields."""
        schema = load_visual_opportunities_schema()
        item_schema = schema["properties"]["opportunities"]["items"]

        required_fields = item_schema["required"]
        assert "chapter_index" in required_fields
        assert "visual_type" in required_fields
        assert "title" in required_fields
        assert "prompt" in required_fields
        assert "caption" in required_fields
        assert "rationale" in required_fields
        assert "confidence" in required_fields

    def test_schema_visual_type_enum(self):
        """Test that visual_type has the correct enum values."""
        schema = load_visual_opportunities_schema()
        item_schema = schema["properties"]["opportunities"]["items"]
        visual_type_enum = item_schema["properties"]["visual_type"]["enum"]

        expected_types = ["screenshot", "diagram", "chart", "table", "icon", "photo", "other"]
        assert visual_type_enum == expected_types

    def test_schema_is_openai_strict_compatible(self):
        """Test that schema is compatible with OpenAI strict mode."""
        schema = load_visual_opportunities_schema()

        # OpenAI strict mode requires additionalProperties: false
        assert schema.get("additionalProperties") is False
        item_schema = schema["properties"]["opportunities"]["items"]
        assert item_schema.get("additionalProperties") is False


class TestVisualOpportunityPrompts:
    """Tests for visual opportunity prompt generation."""

    def test_system_prompt_includes_key_guidance(self):
        """Test that system prompt includes key guidance."""
        assert "visual opportunities" in VISUAL_OPPORTUNITY_SYSTEM_PROMPT.lower()
        assert "chapter_index" in VISUAL_OPPORTUNITY_SYSTEM_PROMPT
        assert "visual_type" in VISUAL_OPPORTUNITY_SYSTEM_PROMPT
        assert "confidence" in VISUAL_OPPORTUNITY_SYSTEM_PROMPT

    def test_density_guidance_all_levels(self):
        """Test that all density levels have guidance."""
        assert "light" in VISUAL_DENSITY_GUIDANCE
        assert "medium" in VISUAL_DENSITY_GUIDANCE
        assert "heavy" in VISUAL_DENSITY_GUIDANCE

    def test_density_guidance_light_fewer_than_heavy(self):
        """Test that light density guidance suggests fewer opportunities."""
        light_guidance = VISUAL_DENSITY_GUIDANCE["light"].lower()
        heavy_guidance = VISUAL_DENSITY_GUIDANCE["heavy"].lower()

        # Light should mention "1-2" total, heavy should mention "2-4" per chapter
        assert "1-2" in light_guidance
        assert "2-4" in heavy_guidance
        assert "per chapter" in heavy_guidance
        assert "total" in light_guidance or "across all" in light_guidance

    def test_build_user_prompt_includes_chapters(self):
        """Test that user prompt includes chapter information."""
        chapters = [
            ChapterPlan(
                chapter_number=1,
                title="Introduction to Testing",
                outline_item_id="ch1",
                goals=["Learn testing basics"],
                key_points=["Unit tests", "Integration tests"],
                transcript_segments=[],
                estimated_words=1000,
            ),
            ChapterPlan(
                chapter_number=2,
                title="Advanced Patterns",
                outline_item_id="ch2",
                goals=["Learn patterns"],
                key_points=["Mocking", "Fixtures"],
                transcript_segments=[],
                estimated_words=1200,
            ),
        ]

        prompt = build_visual_opportunity_user_prompt(chapters, "medium")

        assert "Chapter 1: Introduction to Testing" in prompt
        assert "Chapter 2: Advanced Patterns" in prompt
        assert "Unit tests" in prompt
        assert "Mocking" in prompt

    def test_build_user_prompt_includes_density_guidance(self):
        """Test that user prompt includes density guidance."""
        chapters = [
            ChapterPlan(
                chapter_number=1,
                title="Test Chapter",
                outline_item_id="ch1",
                goals=[],
                key_points=[],
                transcript_segments=[],
                estimated_words=500,
            ),
        ]

        light_prompt = build_visual_opportunity_user_prompt(chapters, "light")
        heavy_prompt = build_visual_opportunity_user_prompt(chapters, "heavy")

        assert "1-2" in light_prompt
        assert "total" in light_prompt.lower() or "across all" in light_prompt.lower()
        assert "2-4" in heavy_prompt
        assert "per chapter" in heavy_prompt.lower()

    def test_build_user_prompt_unknown_density_uses_medium(self):
        """Test that unknown density falls back to medium."""
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

        prompt = build_visual_opportunity_user_prompt(chapters, "unknown_density")
        medium_guidance = VISUAL_DENSITY_GUIDANCE["medium"]

        assert medium_guidance in prompt


class TestVisualOpportunitySorting:
    """Tests for opportunity sorting (deterministic ordering)."""

    def test_opportunities_sorted_by_chapter_then_confidence(self):
        """Test that opportunities are sorted by chapter_index ASC, confidence DESC."""
        from src.models.visuals import VisualOpportunity, VisualPlacement, VisualType, VisualSourcePolicy

        opportunities = [
            VisualOpportunity(
                id="1",
                chapter_index=2,
                visual_type=VisualType.diagram,
                title="Diagram 1",
                prompt="Show diagram",
                caption="Caption",
                confidence=0.8,
                placement=VisualPlacement.after_heading,
                source_policy=VisualSourcePolicy.client_assets_only,
            ),
            VisualOpportunity(
                id="2",
                chapter_index=1,
                visual_type=VisualType.chart,
                title="Chart 1",
                prompt="Show chart",
                caption="Caption",
                confidence=0.6,
                placement=VisualPlacement.after_heading,
                source_policy=VisualSourcePolicy.client_assets_only,
            ),
            VisualOpportunity(
                id="3",
                chapter_index=1,
                visual_type=VisualType.table,
                title="Table 1",
                prompt="Show table",
                caption="Caption",
                confidence=0.9,
                placement=VisualPlacement.after_heading,
                source_policy=VisualSourcePolicy.client_assets_only,
            ),
        ]

        # Sort using the same logic as _generate_visual_plan
        opportunities.sort(key=lambda o: (o.chapter_index, -o.confidence))

        # Chapter 1 should come first, with higher confidence first within chapter
        assert opportunities[0].id == "3"  # Ch1, conf 0.9
        assert opportunities[1].id == "2"  # Ch1, conf 0.6
        assert opportunities[2].id == "1"  # Ch2, conf 0.8
