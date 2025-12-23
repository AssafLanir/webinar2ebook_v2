"""Contract tests for JSON schemas.

These tests ensure:
1. JSON schemas are valid and can be loaded
2. Pydantic models generate valid JSON schemas
3. Sample data validates against schemas
4. Round-trip serialization works correctly
5. LLM schemas are self-contained (internal and OpenAI strict)
6. OpenAI strict schema meets strict mode requirements
7. API responses follow { data, error } envelope pattern
8. Schema loader utility works correctly
"""

import json
from pathlib import Path

import pytest

from src.llm import load_draft_plan_schema, get_draft_plan_schema_path
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
    # API request/response models
    DraftGenerateRequest,
    DraftRegenerateRequest,
    # Data models (inner payload)
    DraftGenerateData,
    DraftStatusData,
    DraftCancelData,
    DraftRegenerateData,
    # Response envelopes
    DraftGenerateResponse,
    DraftStatusResponse,
    DraftCancelResponse,
    DraftRegenerateResponse,
    # Supporting models
    GenerationProgress,
    GenerationStats,
    TokenUsage,
    JobStatus,
    ErrorDetail,
)

# Path to JSON schemas
SCHEMAS_DIR = Path(__file__).parent.parent.parent.parent / "specs" / "004-tab3-ai-draft" / "schemas"


class TestJsonSchemaFiles:
    """Test that JSON schema files exist and are valid JSON."""

    @pytest.fixture
    def schema_files(self):
        """List of expected schema files."""
        return [
            # Core models
            "StyleConfig.json",
            "StyleConfigEnvelope.json",
            "VisualPlan.json",
            "VisualOpportunity.json",
            "VisualAsset.json",
            # Draft plan
            "DraftPlan.json",
            "ChapterPlan.json",
            "TranscriptSegment.json",
            "GenerationMetadata.json",
            # LLM schemas (two versions)
            "draft_plan.internal.schema.json",
            "draft_plan.openai.strict.schema.json",
            # API request/response
            "DraftGenerateRequest.json",
            "DraftRegenerateRequest.json",
            "DraftGenerateData.json",
            "DraftStatusData.json",
            "DraftCancelData.json",
            "DraftRegenerateData.json",
            "DraftGenerateResponse.json",
            "DraftStatusResponse.json",
            "DraftCancelResponse.json",
            "DraftRegenerateResponse.json",
            # Supporting
            "GenerationProgress.json",
            "GenerationStats.json",
            "TokenUsage.json",
            "ErrorDetail.json",
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
        "draft_plan.internal.schema.json",
        "draft_plan.openai.strict.schema.json",
        "DraftGenerateResponse.json",
        "DraftStatusResponse.json",
        "DraftCancelResponse.json",
        "DraftRegenerateResponse.json",
    ])
    def test_schema_is_valid_json(self, filename):
        """Verify each schema file contains valid JSON."""
        schema_path = SCHEMAS_DIR / filename
        with open(schema_path) as f:
            schema = json.load(f)
        assert isinstance(schema, dict)
        assert "type" in schema or "$defs" in schema or "properties" in schema


class TestInternalLlmSchema:
    """Test the internal LLM-facing schema."""

    def test_internal_schema_exists(self):
        """Verify draft_plan.internal.schema.json exists."""
        schema_path = SCHEMAS_DIR / "draft_plan.internal.schema.json"
        assert schema_path.exists()

    def test_internal_schema_is_self_contained(self):
        """Verify schema has no external $ref (only internal #/$defs/)."""
        schema_path = SCHEMAS_DIR / "draft_plan.internal.schema.json"
        with open(schema_path) as f:
            content = f.read()

        # Should have internal refs
        assert "#/$defs/" in content

        # Should NOT have external file refs (except its own filename in $id)
        assert ".json" not in content.replace("draft_plan.internal.schema.json", "")

    def test_internal_schema_has_metadata(self):
        """Verify schema has $schema and $id fields."""
        schema_path = SCHEMAS_DIR / "draft_plan.internal.schema.json"
        with open(schema_path) as f:
            schema = json.load(f)

        assert "$schema" in schema
        assert "$id" in schema
        assert schema["$id"] == "draft_plan.internal.schema.json"

    def test_internal_schema_includes_all_defs(self):
        """Verify all required definitions are inlined."""
        schema_path = SCHEMAS_DIR / "draft_plan.internal.schema.json"
        with open(schema_path) as f:
            schema = json.load(f)

        defs = schema.get("$defs", {})
        required_defs = [
            "ChapterPlan",
            "TranscriptSegment",
            "GenerationMetadata",
            "VisualPlan",
            "VisualOpportunity",
            "VisualAsset",
        ]
        for def_name in required_defs:
            assert def_name in defs, f"Missing definition: {def_name}"


class TestOpenAIStrictSchema:
    """Test the OpenAI strict mode compatible schema."""

    def test_openai_strict_schema_exists(self):
        """Verify draft_plan.openai.strict.schema.json exists."""
        schema_path = SCHEMAS_DIR / "draft_plan.openai.strict.schema.json"
        assert schema_path.exists()

    def test_openai_strict_schema_has_metadata(self):
        """Verify schema has $schema and $id fields."""
        schema_path = SCHEMAS_DIR / "draft_plan.openai.strict.schema.json"
        with open(schema_path) as f:
            schema = json.load(f)

        assert "$schema" in schema
        assert "$id" in schema
        assert schema["$id"] == "draft_plan.openai.strict.schema.json"

    def test_openai_strict_schema_is_self_contained(self):
        """Verify schema has no external $ref."""
        schema_path = SCHEMAS_DIR / "draft_plan.openai.strict.schema.json"
        with open(schema_path) as f:
            content = f.read()

        # Should NOT have external file refs (except its own filename in $id)
        assert ".json" not in content.replace("draft_plan.openai.strict.schema.json", "")

    def test_openai_strict_schema_no_allof(self):
        """OpenAI strict mode forbids allOf in schema structure."""
        schema_path = SCHEMAS_DIR / "draft_plan.openai.strict.schema.json"
        with open(schema_path) as f:
            schema = json.load(f)

        def find_allof(obj, path="root"):
            """Recursively check for allOf keywords in schema structure."""
            if isinstance(obj, dict):
                if "allOf" in obj:
                    return path
                for key, value in obj.items():
                    if key in ("$comment", "$schema", "$id"):
                        continue  # Skip metadata fields
                    result = find_allof(value, f"{path}.{key}")
                    if result:
                        return result
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    result = find_allof(item, f"{path}[{i}]")
                    if result:
                        return result
            return None

        allof_path = find_allof(schema)
        assert allof_path is None, f"OpenAI strict schema must not use allOf (found at {allof_path})"

    def test_openai_strict_schema_has_additional_properties_false(self):
        """OpenAI strict mode requires additionalProperties: false on all objects."""
        schema_path = SCHEMAS_DIR / "draft_plan.openai.strict.schema.json"
        with open(schema_path) as f:
            schema = json.load(f)

        def check_additional_properties(obj, path="root"):
            """Recursively check all object definitions have additionalProperties: false."""
            if isinstance(obj, dict):
                if obj.get("type") == "object":
                    assert obj.get("additionalProperties") is False, \
                        f"Object at {path} must have additionalProperties: false"
                for key, value in obj.items():
                    check_additional_properties(value, f"{path}.{key}")
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    check_additional_properties(item, f"{path}[{i}]")

        check_additional_properties(schema)

    def test_openai_strict_schema_all_properties_required(self):
        """OpenAI strict mode requires all properties to be in required array."""
        schema_path = SCHEMAS_DIR / "draft_plan.openai.strict.schema.json"
        with open(schema_path) as f:
            schema = json.load(f)

        def check_required_complete(obj, path="root"):
            """Recursively check all object definitions have complete required arrays."""
            if isinstance(obj, dict):
                if obj.get("type") == "object" and "properties" in obj:
                    props = set(obj["properties"].keys())
                    required = set(obj.get("required", []))
                    missing = props - required
                    assert not missing, \
                        f"Object at {path} has properties not in required: {missing}"
                for key, value in obj.items():
                    check_required_complete(value, f"{path}.{key}")
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    check_required_complete(item, f"{path}[{i}]")

        check_required_complete(schema)

    def test_openai_strict_schema_ref_must_be_alone(self):
        """OpenAI strict mode forbids any keys alongside $ref.

        If $ref is present, it must be the ONLY key in the object.
        OpenAI returns: "$ref cannot have keywords {'description'}" otherwise.
        """
        schema_path = SCHEMAS_DIR / "draft_plan.openai.strict.schema.json"
        with open(schema_path) as f:
            schema = json.load(f)

        def check_ref_alone(obj, path="root"):
            """Recursively check that $ref has no sibling keys."""
            if isinstance(obj, dict):
                if "$ref" in obj:
                    extra_keys = set(obj.keys()) - {"$ref"}
                    assert not extra_keys, \
                        f"$ref at {path} cannot have sibling keys: {extra_keys}. " \
                        f"OpenAI strict mode requires $ref to be alone."
                for key, value in obj.items():
                    check_ref_alone(value, f"{path}.{key}")
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    check_ref_alone(item, f"{path}[{i}]")

        check_ref_alone(schema)

    def test_openai_strict_schema_includes_all_defs(self):
        """Verify all required definitions are inlined."""
        schema_path = SCHEMAS_DIR / "draft_plan.openai.strict.schema.json"
        with open(schema_path) as f:
            schema = json.load(f)

        defs = schema.get("$defs", {})
        required_defs = [
            "ChapterPlan",
            "TranscriptSegment",
            "GenerationMetadata",
            "VisualPlan",
            "VisualOpportunity",
            "VisualAsset",
        ]
        for def_name in required_defs:
            assert def_name in defs, f"Missing definition: {def_name}"


class TestSchemaLoaderUtility:
    """Test the schema loader utility functions."""

    def test_load_draft_plan_schema_openai(self):
        """Test loading the OpenAI strict schema."""
        schema = load_draft_plan_schema(provider="openai")
        assert isinstance(schema, dict)
        assert schema["$id"] == "draft_plan.openai.strict.schema.json"
        # Verify it doesn't have allOf in structure (excluding metadata)
        assert "allOf" not in schema.get("properties", {})

    def test_load_draft_plan_schema_has_object_type(self):
        """Test that loaded OpenAI schema has type='object' at root."""
        schema = load_draft_plan_schema(provider="openai")
        assert schema.get("type") == "object", \
            "OpenAI strict schema must have type='object' at root level"

    def test_schema_works_with_normalizer(self):
        """Test that loaded schema works correctly with OpenAI normalizer."""
        from src.llm.providers.openai import _normalize_openai_json_schema

        # Load schema and wrap it like draft_service.py does
        raw_schema = load_draft_plan_schema(provider="openai")
        wrapped_schema = {
            "name": "DraftPlan",
            "strict": True,
            "schema": raw_schema,
        }

        # Normalizer should accept this pre-wrapped schema
        result = _normalize_openai_json_schema(wrapped_schema)

        # Should preserve the wrapper's name (not change to "response")
        assert result["name"] == "DraftPlan"
        assert result["strict"] is True
        assert result["schema"]["type"] == "object"

    def test_schema_path_is_absolute(self):
        """Test that schema path uses absolute paths (not relative to cwd)."""
        path = get_draft_plan_schema_path(provider="openai")
        assert path.is_absolute(), "Schema path should be absolute"
        assert path.exists(), f"Schema path should exist: {path}"

    def test_load_draft_plan_schema_anthropic(self):
        """Test loading schema for Anthropic (uses internal)."""
        schema = load_draft_plan_schema(provider="anthropic")
        assert isinstance(schema, dict)
        assert schema["$id"] == "draft_plan.internal.schema.json"

    def test_load_draft_plan_schema_internal(self):
        """Test loading the internal schema."""
        schema = load_draft_plan_schema(provider="internal")
        assert isinstance(schema, dict)
        assert schema["$id"] == "draft_plan.internal.schema.json"

    def test_get_draft_plan_schema_path_openai(self):
        """Test getting the OpenAI schema path."""
        path = get_draft_plan_schema_path(provider="openai")
        assert path.name == "draft_plan.openai.strict.schema.json"
        assert path.exists()

    def test_get_draft_plan_schema_path_internal(self):
        """Test getting the internal schema path."""
        path = get_draft_plan_schema_path(provider="internal")
        assert path.name == "draft_plan.internal.schema.json"
        assert path.exists()


class TestEnvelopePattern:
    """Test that API responses follow { data, error } envelope pattern."""

    def test_generate_response_has_envelope_fields(self):
        """DraftGenerateResponse should have data and error fields."""
        schema = DraftGenerateResponse.model_json_schema()
        props = schema.get("properties", {})
        assert "data" in props
        assert "error" in props

    def test_status_response_has_envelope_fields(self):
        """DraftStatusResponse should have data and error fields."""
        schema = DraftStatusResponse.model_json_schema()
        props = schema.get("properties", {})
        assert "data" in props
        assert "error" in props

    def test_cancel_response_has_envelope_fields(self):
        """DraftCancelResponse should have data and error fields."""
        schema = DraftCancelResponse.model_json_schema()
        props = schema.get("properties", {})
        assert "data" in props
        assert "error" in props

    def test_regenerate_response_has_envelope_fields(self):
        """DraftRegenerateResponse should have data and error fields."""
        schema = DraftRegenerateResponse.model_json_schema()
        props = schema.get("properties", {})
        assert "data" in props
        assert "error" in props

    def test_success_response_pattern(self):
        """Test creating a success response with data."""
        data = DraftGenerateData(
            job_id="job-123",
            status=JobStatus.queued
        )
        response = DraftGenerateResponse(data=data, error=None)
        assert response.data is not None
        assert response.error is None
        assert response.data.job_id == "job-123"

    def test_error_response_pattern(self):
        """Test creating an error response."""
        error = ErrorDetail(code="INVALID_INPUT", message="Transcript too short")
        response = DraftGenerateResponse(data=None, error=error)
        assert response.data is None
        assert response.error is not None
        assert response.error.code == "INVALID_INPUT"


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


class TestApiDataModelsSampleData:
    """Test that sample data validates against API data models."""

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

    def test_draft_generate_data_queued(self):
        """Test DraftGenerateData in queued state."""
        sample = {
            "job_id": "job-123",
            "status": "queued",
            "progress": None,
            "draft_markdown": None,
            "draft_plan": None,
            "visual_plan": None,
            "generation_stats": None
        }
        data = DraftGenerateData.model_validate(sample)
        assert data.status == JobStatus.queued
        assert data.draft_markdown is None

    def test_draft_status_data_generating(self):
        """Test DraftStatusData in generating state."""
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
        data = DraftStatusData.model_validate(sample)
        assert data.status == JobStatus.generating
        assert data.progress.current_chapter == 3

    def test_draft_cancel_data_sample(self):
        """Test DraftCancelData with sample data."""
        sample = {
            "job_id": "job-123",
            "status": "cancelled",
            "cancelled": True,
            "message": "Generation cancelled after chapter 4",
            "partial_draft_markdown": "# My Ebook\n\n## Chapter 1...",
            "chapters_available": 4
        }
        data = DraftCancelData.model_validate(sample)
        assert data.cancelled is True
        assert data.chapters_available == 4

    def test_draft_regenerate_data_sample(self):
        """Test DraftRegenerateData with sample data."""
        sample = {
            "section_markdown": "## Chapter 3\n\nContent...",
            "section_start_line": 100,
            "section_end_line": 150
        }
        data = DraftRegenerateData.model_validate(sample)
        assert data.section_start_line == 100


class TestApiEnvelopeResponsesSampleData:
    """Test full envelope responses with sample data."""

    def test_generate_response_success(self):
        """Test DraftGenerateResponse success envelope."""
        sample = {
            "data": {
                "job_id": "job-123",
                "status": "queued"
            },
            "error": None
        }
        response = DraftGenerateResponse.model_validate(sample)
        assert response.data is not None
        assert response.error is None

    def test_generate_response_error(self):
        """Test DraftGenerateResponse error envelope."""
        sample = {
            "data": None,
            "error": {
                "code": "INVALID_INPUT",
                "message": "Transcript too short"
            }
        }
        response = DraftGenerateResponse.model_validate(sample)
        assert response.data is None
        assert response.error is not None
        assert response.error.code == "INVALID_INPUT"

    def test_status_response_completed(self):
        """Test DraftStatusResponse completed envelope."""
        sample = {
            "data": {
                "job_id": "job-123",
                "status": "completed",
                "draft_markdown": "# My Ebook"
            },
            "error": None
        }
        response = DraftStatusResponse.model_validate(sample)
        assert response.data.status == JobStatus.completed

    def test_cancel_response_success(self):
        """Test DraftCancelResponse success envelope."""
        sample = {
            "data": {
                "job_id": "job-123",
                "status": "cancelled",
                "cancelled": True,
                "message": "Cancelled"
            },
            "error": None
        }
        response = DraftCancelResponse.model_validate(sample)
        assert response.data.cancelled is True


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

    def test_envelope_response_roundtrip(self):
        """Test envelope response serializes and deserializes correctly."""
        data = DraftGenerateData(job_id="job-123", status=JobStatus.queued)
        original = DraftGenerateResponse(data=data, error=None)
        json_str = original.model_dump_json()
        restored = DraftGenerateResponse.model_validate_json(json_str)
        assert restored.data.job_id == "job-123"
        assert restored.error is None


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

    def test_envelope_rejects_extra_fields(self):
        """Envelope responses should reject unknown fields."""
        with pytest.raises(Exception):
            DraftGenerateResponse.model_validate({
                "data": {"job_id": "job-123", "status": "queued"},
                "error": None,
                "unknown_field": "value"
            })
