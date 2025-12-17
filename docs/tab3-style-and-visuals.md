# Tab 3 Draft: Style Config + Visuals Groundwork

These files let you implement Tab 3 draft generation *without* being blocked by Tab 2 visuals management.

## What you get
- A **StyleConfig** schema (backend source-of-truth + frontend mirror)
- **Presets** (common ebook styles)
- A **Visuals** schema (VisualAsset + VisualOpportunity + VisualPlan)

## Key idea
Tab 3 can output a **VisualPlan** with suggested placements (opportunities).  
Tab 2 later lets the user upload/select **VisualAssets** and “resolve” opportunities into real images.

## Files
Backend:
- `backend/src/models/style_config.py`
- `backend/src/models/style_config_migrations.py`
- `backend/src/models/visuals.py`

Frontend:
- `frontend/src/types/style.ts`
- `frontend/src/types/visuals.ts`
- `frontend/src/constants/stylePresets.ts`

## Persistence recommendation
Persist a versioned wrapper:
- `StyleConfigEnvelope` (already included)
- Optionally persist `VisualPlan` alongside the draft (recommended)

## Note about client-provided visuals
`VisualAsset.origin="client_provided"` exists explicitly to support your requirement:
> users can upload client-provided visuals later in Tab 2.
