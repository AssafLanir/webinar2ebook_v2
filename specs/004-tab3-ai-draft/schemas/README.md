# JSON Schemas for Spec 004

These JSON schemas are auto-generated from the Pydantic models in `backend/src/models/`.

## LLM Schemas

Two self-contained DraftPlan schemas are maintained for different use cases:

### Internal Schema (Tests & Documentation)

**`draft_plan.internal.schema.json`** - The expressive schema for internal use, tests, and documentation. Uses `allOf` for `$ref` composition, optional fields via defaults. This is what Pydantic generates.

Use for:
- Contract tests
- Documentation
- Non-OpenAI providers (Anthropic tool_use)
- Internal validation

### OpenAI Strict Schema (Production LLM Calls)

**`draft_plan.openai.strict.schema.json`** - Compatible with OpenAI's `response_format.json_schema` strict mode.

Rules for OpenAI strict mode:
- NO `allOf`, `oneOf` with multiple object variants
- `additionalProperties: false` on every object
- Every object has ALL keys in `required` array
- Optional fields use nullable pattern: `{ "anyOf": [{"type":"string"},{"type":"null"}] }`

Use for:
- OpenAI structured output calls
- Any provider requiring strict JSON schema compliance

## Response Envelope Pattern

All API responses follow the standard `{ data, error }` envelope pattern:

```json
{
  "data": { ... },  // Response payload on success
  "error": null     // null on success
}
```

```json
{
  "data": null,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message"
  }
}
```

## Files

### LLM Schemas
- **draft_plan.internal.schema.json** - Internal/test schema (expressive)
- **draft_plan.openai.strict.schema.json** - OpenAI strict mode schema (production)

### Core Models
- **StyleConfig.json** - The comprehensive style configuration with ~35 fields
- **StyleConfigEnvelope.json** - Versioned wrapper for StyleConfig (used for persistence)
- **VisualPlan.json** - Container for visual opportunities and assets
- **VisualOpportunity.json** - A suggested visual placement in the ebook
- **VisualAsset.json** - An actual image/file asset

### Draft Plan Models
- **DraftPlan.json** - Complete generation plan for an ebook draft
- **ChapterPlan.json** - Plan for generating a single chapter
- **TranscriptSegment.json** - A mapped segment of the source transcript
- **GenerationMetadata.json** - Metadata about the generation plan

### API Request Models
- **DraftGenerateRequest.json** - Request body for draft generation
- **DraftRegenerateRequest.json** - Request body for section regeneration

### API Data Models (inner payload)
- **DraftGenerateData.json** - Data payload for generate response
- **DraftStatusData.json** - Data payload for status response
- **DraftCancelData.json** - Data payload for cancel response
- **DraftRegenerateData.json** - Data payload for regenerate response

### API Response Envelopes
- **DraftGenerateResponse.json** - Envelope for POST /api/ai/draft/generate
- **DraftStatusResponse.json** - Envelope for GET /api/ai/draft/status/:job_id
- **DraftCancelResponse.json** - Envelope for POST /api/ai/draft/cancel/:job_id
- **DraftRegenerateResponse.json** - Envelope for POST /api/ai/draft/regenerate

### Supporting Models
- **GenerationProgress.json** - Progress information during generation
- **GenerationStats.json** - Statistics about the completed generation
- **TokenUsage.json** - Token usage statistics
- **ErrorDetail.json** - Error detail structure

## Regenerating Schemas

To regenerate base schemas after model changes:

```bash
cd backend
python -c "
import json
from src.models import (
    StyleConfig,
    StyleConfigEnvelope,
    VisualPlan,
    VisualOpportunity,
    VisualAsset,
    DraftPlan,
    ChapterPlan,
    TranscriptSegment,
    GenerationMetadata,
    DraftGenerateRequest,
    DraftRegenerateRequest,
    DraftGenerateData,
    DraftStatusData,
    DraftCancelData,
    DraftRegenerateData,
    DraftGenerateResponse,
    DraftStatusResponse,
    DraftCancelResponse,
    DraftRegenerateResponse,
    GenerationProgress,
    GenerationStats,
    TokenUsage,
    ErrorDetail,
)

schemas_dir = '../specs/004-tab3-ai-draft/schemas'

for model, name in [
    (StyleConfig, 'StyleConfig'),
    (StyleConfigEnvelope, 'StyleConfigEnvelope'),
    (VisualPlan, 'VisualPlan'),
    (VisualOpportunity, 'VisualOpportunity'),
    (VisualAsset, 'VisualAsset'),
    (DraftPlan, 'DraftPlan'),
    (ChapterPlan, 'ChapterPlan'),
    (TranscriptSegment, 'TranscriptSegment'),
    (GenerationMetadata, 'GenerationMetadata'),
    (DraftGenerateRequest, 'DraftGenerateRequest'),
    (DraftRegenerateRequest, 'DraftRegenerateRequest'),
    (DraftGenerateData, 'DraftGenerateData'),
    (DraftStatusData, 'DraftStatusData'),
    (DraftCancelData, 'DraftCancelData'),
    (DraftRegenerateData, 'DraftRegenerateData'),
    (DraftGenerateResponse, 'DraftGenerateResponse'),
    (DraftStatusResponse, 'DraftStatusResponse'),
    (DraftCancelResponse, 'DraftCancelResponse'),
    (DraftRegenerateResponse, 'DraftRegenerateResponse'),
    (GenerationProgress, 'GenerationProgress'),
    (GenerationStats, 'GenerationStats'),
    (TokenUsage, 'TokenUsage'),
    (ErrorDetail, 'ErrorDetail'),
]:
    schema = model.model_json_schema()
    with open(f'{schemas_dir}/{name}.json', 'w') as f:
        json.dump(schema, f, indent=2)
"
```

Then manually update the LLM schemas:

1. Copy `DraftPlan.json` to `draft_plan.internal.schema.json` and update metadata:
```bash
cp DraftPlan.json draft_plan.internal.schema.json
# Add $schema, $id, $comment fields at the top
```

2. The OpenAI strict schema must be manually maintained (transformations are non-trivial):
- Replace all `allOf` with direct `$ref` or inlined enums
- Add ALL property keys to `required` arrays
- Use nullable pattern `{ "anyOf": [..., {"type":"null"}] }` for optional fields

## Source of Truth

The Pydantic models in `backend/src/models/` are the source of truth. These JSON schemas are derived artifacts.

## Schema Categories

### Style Configuration
Controls how the ebook is generated - tone, audience, structure, visual density, etc.

### Visual Planning
Manages visual opportunities (suggestions) and assets (actual images):
- Opportunities are generated during draft planning
- Assets are attached in Tab 2 (Spec 005)

### Draft Planning
The internal plan used for chunked generation:
- Maps transcript segments to chapters
- Enables regeneration of individual sections
- Tracks generation metadata

### API Layer
Request/response models for the async job pattern:
- Generation is queued and polled
- Progress updates during generation
- Cancellation with partial results
- All responses use `{ data, error }` envelope
