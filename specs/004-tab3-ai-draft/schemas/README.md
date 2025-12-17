# JSON Schemas for Spec 004

These JSON schemas are auto-generated from the Pydantic models in `backend/src/models/`.

## Files

- **StyleConfig.json** - The comprehensive style configuration with ~35 fields
- **StyleConfigEnvelope.json** - Versioned wrapper for StyleConfig (used for persistence)
- **VisualPlan.json** - Container for visual opportunities and assets
- **VisualOpportunity.json** - A suggested visual placement in the ebook
- **VisualAsset.json** - An actual image/file asset

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
)

for model, name in [
    (StyleConfig, 'StyleConfig'),
    (StyleConfigEnvelope, 'StyleConfigEnvelope'),
    (VisualPlan, 'VisualPlan'),
    (VisualOpportunity, 'VisualOpportunity'),
    (VisualAsset, 'VisualAsset'),
]:
    schema = model.model_json_schema()
    with open(f'../specs/004-tab3-ai-draft/schemas/{name}.json', 'w') as f:
        json.dump(schema, f, indent=2)
"
```

## Source of Truth

The Pydantic models in `backend/src/models/` are the source of truth. These JSON schemas are derived artifacts.
