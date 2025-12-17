"""Contract tests for JSON schemas.

These tests ensure:
1. JSON schemas are valid and can be loaded
2. Pydantic models generate valid JSON schemas
3. Sample data validates against schemas
4. Round-trip serialization works correctly
"""

import json
from pathlib import Path

import pytest

from src.models import (
    # Core models
    StyleConfig,
    StyleConfigEnvelope,
    VisualPlan,
    VisualOpportunity,
    VisualAsset,
    VisualAssetOrigin,
    VisualPlacement,
    VisualType,
    VisualSourcePolicy,
    # Draft plan models
    DraftPlan,
    ChapterPlan,
    TranscriptSegment,
    GenerationMetadata,
    TranscriptRelevance,
    # API response models
    DraftGenerateRequest,
    DraftGenerateResponse,
    DraftStatusResponse,
    DraftCancelResponse,
    DraftRegenerateRequest,
    DraftRegenerateResponse,
    GenerationProgress,
    GenerationStats,
    TokenUsage,
    JobStatus,
)

# Path to JSON schemas
SCHEMAS_DIR = Path(__file__).parent.parent.parent.parent / "specs" / "004-tab3-ai-draft" / "schemas"


class TestJsonSchemaFiles:
    """Test that JSON schema files exist and are valid JSON."""

    @pytest.fixture
    def schema_files(self):
        """List of expected schema files."""
        return [
            "StyleConfig.json",
            "StyleConfigEnvelope.json",
            "VisualPlan.json",
            "VisualOpportunity.json",
            "VisualAsset.json",
            "DraftPlan.json",
            "ChapterPlan.json",
            "TranscriptSegment.json",
            "GenerationMetadata.json",
            "DraftGenerateRequest.json",
            "DraftGenerateResponse.json",
            "DraftStatusResponse.json",
            "DraftCancelResponse.json",
            "DraftRegenerateRequest.json",
            "DraftRegenerateResponse.json",
            "GenerationProgress.json",
            "GenerationStats.json",
            "TokenUsage.json",
        ]

    def test_schemas_directory_exists(self):
        """Verify schemas directory exists."""
        assert SCHEMAS_DIR.exists(), f"Schemas directory not found: {SCHEMAS_DIR}"

    def test_all_schema_files_exist(self, schema_files):
        """Verify all expected schema files exist."""
        for filename in schema_files:
            schema_path = SCHEMAS_DIR / filename
            assert schema_path.exists(), f"Schema file not found: {schema_path}"

    @pytest.mark.parametrize("filename", [
        "StyleConfig.json",
        "StyleConfigEnvelope.json",
        "VisualPlan.json",
        "VisualOpportunity.json",
        "VisualAsset.json",
        "DraftPlan.json",
        "ChapterPlan.json",
        "TranscriptSegment.json",
        "GenerationMetadata.json",
        "DraftGenerateRequest.json",
        "DraftGenerateResponse.json",
        "DraftStatusResponse.json",
        "DraftCancelResponse.json",
        "DraftRegenerateRequest.json",
        "DraftRegenerateResponse.json",
        "GenerationProgress.json",
        "GenerationStats.json",
        "TokenUsage.json",
    ])
    def test_schema_is_valid_json(self, filename):
        """Verify each schema file contains valid JSON."""
        schema_path = SCHEMAS_DIR / filename
        with open(schema_path) as f:
            schema = json.load(f)
        assert isinstance(schema, dict)
        assert "type" in schema or "$defs" in schema or "properties" in schema


class TestPydanticSchemaGeneration:
    """Test that Pydantic models generate valid JSON schemas."""

    @pytest.mark.parametrize("model,filename", [
        (StyleConfig, "StyleConfig.json"),
        (StyleConfigEnvelope, "StyleConfigEnvelope.json"),
        (VisualPlan, "VisualPlan.json"),
        (VisualOpportunity, "VisualOpportunity.json"),
        (VisualAsset, "VisualAsset.json"),
        (DraftPlan, "DraftPlan.json"),
        (ChapterPlan, "ChapterPlan.json"),
        (TranscriptSegment, "TranscriptSegment.json"),
        (GenerationMetadata, "GenerationMetadata.json"),
        (DraftGenerateResponse, "DraftGenerateResponse.json"),
        (DraftStatusResponse, "DraftStatusResponse.json"),
        (DraftCancelResponse, "DraftCancelResponse.json"),
        (DraftRegenerateResponse, "DraftRegenerateResponse.json"),
        (GenerationProgress, "GenerationProgress.json"),
        (GenerationStats, "GenerationStats.json"),
        (TokenUsage, "TokenUsage.json"),
    ])
    def test_model_generates_matching_schema(self, model, filename):
        """Verify Pydantic model generates schema matching the file."""
        schema_path = SCHEMAS_DIR / filename
        with open(schema_path) as f:
            file_schema = json.load(f)

        model_schema = model.model_json_schema()

        # Compare key structural elements
        assert model_schema.get("title") == file_schema.get("title"), \
            f"Title mismatch for {filename}"
        assert model_schema.get("type") == file_schema.get("type"), \
            f"Type mismatch for {filename}"


class TestCoreModelsSampleData:
    """Test that sample data validates against core models."""

    def test_style_config_envelope_sample(self):
        """Test StyleConfigEnvelope with sample data."""
        sample = {
            "version": 1,
            "preset_id": "default_webinar_ebook_v1",
            "style": {
                "target_audience": "mixed",
                "tone": "professional",
                "book_format": "guide",
            }
        }
        envelope = StyleConfigEnvelope.model_validate(sample)
        assert envelope.version == 1
        assert envelope.preset_id == "default_webinar_ebook_v1"
        assert envelope.style.target_audience.value == "mixed"

    def test_visual_opportunity_sample(self):
        """Test VisualOpportunity with sample data."""
        sample = {
            "id": "vo-123",
            "chapter_index": 2,
            "section_path": "2.1",
            "placement": "after_heading",
            "visual_type": "diagram",
            "source_policy": "client_assets_only",
            "title": "System Architecture",
            "prompt": "A diagram showing system components",
            "caption": "Figure 2.1: Architecture Overview",
            "required": False,
            "candidate_asset_ids": [],
            "confidence": 0.8,
            "rationale": "Helps visualize the system"
        }
        opp = VisualOpportunity.model_validate(sample)
        assert opp.id == "vo-123"
        assert opp.chapter_index == 2
        assert opp.visual_type == VisualType.diagram

    def test_visual_asset_sample(self):
        """Test VisualAsset with sample data."""
        sample = {
            "id": "asset-456",
            "filename": "architecture.png",
            "media_type": "image/png",
            "origin": "client_provided",
            "width": 800,
            "height": 600,
            "alt_text": "System architecture diagram",
            "tags": ["architecture", "diagram"]
        }
        asset = VisualAsset.model_validate(sample)
        assert asset.id == "asset-456"
        assert asset.origin == VisualAssetOrigin.client_provided

    def test_visual_plan_sample(self):
        """Test VisualPlan with sample data."""
        sample = {
            "opportunities": [
                {
                    "id": "vo-1",
                    "chapter_index": 1,
                    "visual_type": "screenshot",
                    "title": "Dashboard",
                    "prompt": "Show the main dashboard",
                    "caption": "Figure 1.1: Main Dashboard"
                }
            ],
            "assets": []
        }
        plan = VisualPlan.model_validate(sample)
        assert len(plan.opportunities) == 1
        assert len(plan.assets) == 0


class TestDraftPlanModelsSampleData:
    """Test that sample data validates against draft plan models."""

    def test_transcript_segment_sample(self):
        """Test TranscriptSegment with sample data."""
        sample = {
            "start_char": 0,
            "end_char": 500,
            "relevance": "primary"
        }
        segment = TranscriptSegment.model_validate(sample)
        assert segment.start_char == 0
        assert segment.relevance == TranscriptRelevance.primary

    def test_chapter_plan_sample(self):
        """Test ChapterPlan with sample data."""
        sample = {
            "chapter_number": 1,
            "title": "Introduction",
            "outline_item_id": "outline-1",
            "goals": ["Understand the basics", "Learn key concepts"],
            "key_points": ["Point A", "Point B", "Point C"],
            "transcript_segments": [
                {"start_char": 0, "end_char": 500, "relevance": "primary"}
            ],
            "estimated_words": 1500
        }
        plan = ChapterPlan.model_validate(sample)
        assert plan.chapter_number == 1
        assert len(plan.goals) == 2
        assert len(plan.transcript_segments) == 1

    def test_generation_metadata_sample(self):
        """Test GenerationMetadata with sample data."""
        sample = {
            "estimated_total_words": 10000,
            "estimated_generation_time_seconds": 120,
            "transcript_utilization": 0.85
        }
        metadata = GenerationMetadata.model_validate(sample)
        assert metadata.estimated_total_words == 10000
        assert metadata.transcript_utilization == 0.85

    def test_draft_plan_sample(self):
        """Test DraftPlan with sample data."""
        sample = {
            "version": 1,
            "book_title": "My Ebook",
            "chapters": [
                {
                    "chapter_number": 1,
                    "title": "Introduction",
                    "outline_item_id": "outline-1",
                    "goals": ["Understand basics"],
                    "key_points": ["Key point"],
                    "transcript_segments": [],
                    "estimated_words": 1000
                }
            ],
            "visual_plan": {
                "opportunities": [],
                "assets": []
            },
            "generation_metadata": {
                "estimated_total_words": 1000,
                "estimated_generation_time_seconds": 30,
                "transcript_utilization": 0.9
            }
        }
        plan = DraftPlan.model_validate(sample)
        assert plan.book_title == "My Ebook"
        assert len(plan.chapters) == 1


class TestApiResponseModelsSampleData:
    """Test that sample data validates against API response models."""

    def test_token_usage_sample(self):
        """Test TokenUsage with sample data."""
        sample = {
            "prompt_tokens": 1000,
            "completion_tokens": 2000,
            "total_tokens": 3000
        }
        usage = TokenUsage.model_validate(sample)
        assert usage.total_tokens == 3000

    def test_generation_progress_sample(self):
        """Test GenerationProgress with sample data."""
        sample = {
            "current_chapter": 3,
            "total_chapters": 8,
            "current_chapter_title": "Pricing Strategy",
            "chapters_completed": 2,
            "estimated_remaining_seconds": 90
        }
        progress = GenerationProgress.model_validate(sample)
        assert progress.current_chapter == 3
        assert progress.total_chapters == 8

    def test_generation_stats_sample(self):
        """Test GenerationStats with sample data."""
        sample = {
            "chapters_generated": 8,
            "total_words": 12000,
            "generation_time_ms": 45000,
            "tokens_used": {
                "prompt_tokens": 15000,
                "completion_tokens": 20000,
                "total_tokens": 35000
            }
        }
        stats = GenerationStats.model_validate(sample)
        assert stats.chapters_generated == 8
        assert stats.tokens_used.total_tokens == 35000

    def test_draft_generate_response_queued(self):
        """Test DraftGenerateResponse in queued state."""
        sample = {
            "job_id": "job-123",
            "status": "queued",
            "progress": None,
            "draft_markdown": None,
            "draft_plan": None,
            "visual_plan": None,
            "generation_stats": None,
            "error": None,
            "error_code": None
        }
        response = DraftGenerateResponse.model_validate(sample)
        assert response.status == JobStatus.queued
        assert response.draft_markdown is None

    def test_draft_status_response_generating(self):
        """Test DraftStatusResponse in generating state."""
        sample = {
            "job_id": "job-123",
            "status": "generating",
            "progress": {
                "current_chapter": 3,
                "total_chapters": 8,
                "current_chapter_title": "Chapter 3",
                "chapters_completed": 2,
                "estimated_remaining_seconds": 60
            }
        }
        response = DraftStatusResponse.model_validate(sample)
        assert response.status == JobStatus.generating
        assert response.progress.current_chapter == 3

    def test_draft_cancel_response_sample(self):
        """Test DraftCancelResponse with sample data."""
        sample = {
            "job_id": "job-123",
            "status": "cancelled",
            "cancelled": True,
            "message": "Generation cancelled after chapter 4",
            "partial_draft_markdown": "# My Ebook\n\n## Chapter 1...",
            "chapters_available": 4
        }
        response = DraftCancelResponse.model_validate(sample)
        assert response.cancelled is True
        assert response.chapters_available == 4


class TestRoundTripSerialization:
    """Test that models round-trip through JSON correctly."""

    def test_style_config_envelope_roundtrip(self):
        """Test StyleConfigEnvelope serializes and deserializes correctly."""
        original = StyleConfigEnvelope(
            version=1,
            preset_id="test",
            style=StyleConfig()
        )
        json_str = original.model_dump_json()
        restored = StyleConfigEnvelope.model_validate_json(json_str)
        assert restored.version == original.version
        assert restored.preset_id == original.preset_id

    def test_visual_plan_roundtrip(self):
        """Test VisualPlan serializes and deserializes correctly."""
        original = VisualPlan(
            opportunities=[
                VisualOpportunity(
                    id="vo-1",
                    chapter_index=1,
                    visual_type=VisualType.diagram,
                    title="Test",
                    prompt="Test prompt",
                    caption="Test caption"
                )
            ],
            assets=[]
        )
        json_str = original.model_dump_json()
        restored = VisualPlan.model_validate_json(json_str)
        assert len(restored.opportunities) == 1
        assert restored.opportunities[0].id == "vo-1"

    def test_draft_plan_roundtrip(self):
        """Test DraftPlan serializes and deserializes correctly."""
        original = DraftPlan(
            version=1,
            book_title="Test Book",
            chapters=[
                ChapterPlan(
                    chapter_number=1,
                    title="Intro",
                    outline_item_id="o-1",
                    estimated_words=1000
                )
            ],
            visual_plan=VisualPlan(),
            generation_metadata=GenerationMetadata(
                estimated_total_words=1000,
                estimated_generation_time_seconds=30,
                transcript_utilization=0.8
            )
        )
        json_str = original.model_dump_json()
        restored = DraftPlan.model_validate_json(json_str)
        assert restored.book_title == "Test Book"
        assert len(restored.chapters) == 1


class TestExtraFieldsForbidden:
    """Test that extra fields are rejected (schema drift prevention)."""

    def test_style_config_rejects_extra_fields(self):
        """StyleConfig should reject unknown fields."""
        with pytest.raises(Exception):  # ValidationError
            StyleConfig.model_validate({"unknown_field": "value"})

    def test_visual_opportunity_rejects_extra_fields(self):
        """VisualOpportunity should reject unknown fields."""
        with pytest.raises(Exception):
            VisualOpportunity.model_validate({
                "id": "vo-1",
                "chapter_index": 1,
                "visual_type": "diagram",
                "title": "Test",
                "prompt": "Test",
                "caption": "Test",
                "unknown_field": "value"
            })

    def test_draft_plan_rejects_extra_fields(self):
        """DraftPlan should reject unknown fields."""
        with pytest.raises(Exception):
            DraftPlan.model_validate({
                "version": 1,
                "book_title": "Test",
                "chapters": [],
                "visual_plan": {"opportunities": [], "assets": []},
                "generation_metadata": {
                    "estimated_total_words": 1000,
                    "estimated_generation_time_seconds": 30,
                    "transcript_utilization": 0.8
                },
                "unknown_field": "value"
            })
