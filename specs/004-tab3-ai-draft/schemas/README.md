# JSON Schemas for Spec 004

These JSON schemas are auto-generated from the Pydantic models in `backend/src/models/`.

## Files

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

### API Request/Response Models
- **DraftGenerateRequest.json** - Request body for draft generation
- **DraftGenerateResponse.json** - Response for POST /api/ai/draft/generate
- **DraftStatusResponse.json** - Response for GET /api/ai/draft/status/:job_id
- **DraftCancelResponse.json** - Response for POST /api/ai/draft/cancel/:job_id
- **DraftRegenerateRequest.json** - Request body for section regeneration
- **DraftRegenerateResponse.json** - Response for POST /api/ai/draft/regenerate
- **GenerationProgress.json** - Progress information during generation
- **GenerationStats.json** - Statistics about the completed generation
- **TokenUsage.json** - Token usage statistics

## Regenerating Schemas

To regenerate these schemas after model changes:

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
    DraftGenerateResponse,
    DraftStatusResponse,
    DraftCancelResponse,
    DraftRegenerateRequest,
    DraftRegenerateResponse,
    GenerationProgress,
    GenerationStats,
    TokenUsage,
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
    (DraftGenerateResponse, 'DraftGenerateResponse'),
    (DraftStatusResponse, 'DraftStatusResponse'),
    (DraftCancelResponse, 'DraftCancelResponse'),
    (DraftRegenerateRequest, 'DraftRegenerateRequest'),
    (DraftRegenerateResponse, 'DraftRegenerateResponse'),
    (GenerationProgress, 'GenerationProgress'),
    (GenerationStats, 'GenerationStats'),
    (TokenUsage, 'TokenUsage'),
]:
    schema = model.model_json_schema()
    with open(f'{schemas_dir}/{name}.json', 'w') as f:
        json.dump(schema, f, indent=2)
"
```

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
