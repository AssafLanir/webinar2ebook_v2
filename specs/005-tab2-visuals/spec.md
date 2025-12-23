# Spec 005 — Tab 2 (Visuals): Upload Library + Assign Assets to Visual Opportunities

**Status:** Draft (v2 — aligned to existing code/models)
**Owner:** Assaf
**Scope:** MVP (P1) focused on **client-provided visuals** and **connecting them to AI visual opportunities** produced in Tab 3.

---

## 0. Summary

Tab 2 should let a user:

1) Upload image assets (client-provided) into a **Visual Library**
2) View AI-suggested **visual opportunities** (from `project.visualPlan.opportunities`)
3) **Assign** library assets to opportunities (or mark an opportunity as "skip")
4) Persist everything to the Project so refresh/reload keeps assignments

This spec **does not** insert visuals into the markdown draft. Visual insertion happens later (Tab 4 / export).

---

## 1. Goals

- Provide a **first-class image library** in Tab 2 (upload, preview, metadata).
- Provide a **workflow to satisfy visual opportunities** created in Tab 3:
  - "This section should have a chart" → user assigns an uploaded chart image.
- Persist:
  - image metadata in `project.visualPlan.assets`
  - opportunity assignments in `project.visualPlan.assignments`
- Keep scope tight:
  - Reuse existing `saveProject()` (PUT `/api/projects/:id`) for metadata + assignments.
  - Add the *minimum* backend endpoints required for file upload + serving image bytes.

---

## 2. Non-Goals (for this spec)

- No AI image generation, no prompt-to-image flows.
- No inline markdown placeholders inserted into the draft (e.g., `![...]()`).
- No advanced image editing (crop/rotate/annotate).
- No auth/multi-user permission overhaul (assume local dev).

---

## 3. User Stories

### US1 (P1) — Upload client visuals into a library
As a user, I can upload PNG/JPG/WebP images and see them as thumbnails in Tab 2.

### US2 (P1) — Assign an uploaded asset to an AI opportunity
As a user, I can pick an image from the library and attach it to a specific visual opportunity (or mark it skipped).

### US3 (P1) — Persist library + assignments
As a user, I can refresh the page and still see the same assets and assignments.

### US4 (P2) — Download/copy an asset
As a user, I can download an uploaded image from the library, or copy its URL/markdown snippet to clipboard.

> **Note:** "Copy image to clipboard" (binary) is excluded due to browser permission complexity. Instead:
> - **Copy URL**: Copies the project-scoped content endpoint URL
> - **Copy Markdown**: Copies `![caption](url)` snippet for pasting into external docs

### US5 (P2) — Lightweight metadata editing
As a user, I can edit caption/alt text for an image.

---

## 4. Tab 2 UX / UI

### 4.1 Layout

Tab 2 is split into two sections:

**A) Visual Opportunities**
- If opportunities exist:
  - Show list grouped by chapter (use `chapter_index` / `chapter_title` if present; otherwise fallback to order).
  - Opportunity card shows:
    - `title`
    - `visual_type` (diagram / chart / photo / screenshot / table / icon / etc.)
    - `rationale` (short)
    - `suggested_caption`
    - `source_policy` badge (usually `client_assets_only`)
    - Assignment state:
      - **Unassigned** → CTA "Assign"
      - **Assigned** → thumbnail + filename + "Change / Unassign"
      - **Skipped** → greyed + "Unskip"
- If no opportunities:
  - Empty state: "No visual opportunities yet. Generate a draft in Tab 3 to get suggestions."
  - Still allow uploads in library.

**B) Visual Library**
- Upload dropzone + button ("Upload Images")
- Grid of thumbnails
- Each asset card:
  - Thumbnail
  - Filename (truncated)
  - Size + dimensions (e.g., `1200×800`)
  - Actions:
    - "Download" (P2)
    - "Copy URL" / "Copy Markdown" (P2)
    - "Delete"
    - "Edit metadata" (P2: caption/alt text)
    - "Assign…" (P2 — opens opportunity picker filtered to *unassigned* opportunities)

> **MVP Note:** Assignment is **opportunity-driven only** in P1 — user clicks "Assign" on an OpportunityCard and picks from the library. The reverse flow (AssetCard → "Assign to opportunity...") is P2.

> **P2 Note:** For large libraries (50+ images), consider adding pagination or infinite scroll.

### 4.2 Assignment Rules (P1)

- Assigning an asset to an opportunity creates/updates a `VisualAssignment` record.
- Unassigning removes the record (or sets status to "unassigned"; see 6.3).
- Skipping creates/updates a record with status `skipped` and `asset_id = null`.
- If an assigned asset is deleted:
  - remove asset from library
  - any assignments referencing it become **unassigned**

### 4.3 "Unassigned" definition (important)

**An opportunity with no matching `VisualAssignment` entry is considered UNASSIGNED.**
(We do **not** store explicit `"unassigned"` records in MVP.)

### 4.4 Save behavior (P1)

- Any upload / assign / skip / delete marks Tab 2 "dirty".
- Persistence strategy:
  - Reuse existing `saveProject()` with a **debounced autosave** (e.g. 750ms).
  - Must avoid stale state saves (same pattern used in Tab 3: save after state updates reflect the change).

---

## 5. Data Model (align to existing repo models)

> IMPORTANT: The repo already has `backend/src/models/visuals.py` with `VisualAsset` and `VisualOpportunity`.
> This spec extends the existing models rather than replacing them.

### 5.1 Existing VisualAsset (current)
Existing fields (as implemented today):
- `id: str`
- `filename: str`
- `media_type: str`
- `origin: VisualAssetOrigin`
- `source_url?: str`
- `storage_key?: str`
- `width?: int`
- `height?: int`
- `alt_text?: str`
- `tags: List[str]`

### 5.2 Additions to VisualAsset (P1)
Add these fields to the existing model (backward-compatible defaults):
- `original_filename: Optional[str]`
- `size_bytes: Optional[int]`
- `caption: Optional[str]`
- `sha256: Optional[str]`
- `created_at: Optional[str]` (ISO string)

**Naming rule:** keep existing names (`media_type`, `origin`) to avoid churn.
(Frontend can display "MIME type" label but store it as `media_type`.)

### 5.3 New VisualAssignment (P1)
Add a new model (backend + frontend) stored at `project.visualPlan.assignments[]`:

```ts
type VisualAssignmentStatus = "assigned" | "skipped";

interface VisualAssignment {
  opportunity_id: string;      // matches VisualOpportunity.id
  status: VisualAssignmentStatus;
  asset_id: string | null;     // required when status="assigned"
  user_notes: string | null;   // optional
  updated_at: string;          // ISO
}
```

### 5.4 VisualPlan (update)
Ensure `VisualPlan` contains:
- `opportunities: VisualOpportunity[]`
- `assets: VisualAsset[]`
- `assignments: VisualAssignment[]`  // NEW

**Migration/defaulting:** if `assignments` missing on load, treat as `[]`.

---

## 6. Transition / Migration Notes (important)

### 6.1 Project currently has `project.visuals` (legacy Tab 2)
Current frontend Tab 2 uses:
- `project.visuals` (array of "visual objects")

This spec makes `project.visualPlan.assets` canonical.

**Migration strategy (MVP-friendly):**
- On project load:
  - If `project.visualPlan.assets` exists: use it.
  - Else if `project.visuals` exists: map them into `visualPlan.assets` in memory.
- On first save from Tab 2:
  - Persist into `project.visualPlan.assets`
  - Leave `project.visuals` untouched (read-only legacy).

**Legacy `Visual` → `VisualAsset` field mapping:**
| Legacy `Visual` field | Maps to `VisualAsset` field |
|-----------------------|-----------------------------|
| `id` | `id` |
| `title` | `caption` (or `alt_text`) |
| `description` | `alt_text` |
| `url` | `source_url` |
| `selected` | (ignore for MVP) |

> Note: Legacy visuals without `storage_key` or `sha256` are display-only placeholders until the user re-uploads actual image files.

Add a TODO note to deprecate `project.visuals` later.

---

## 7. Backend / API Requirements

### 7.1 Upload endpoint (P1)
**POST** `/api/projects/{project_id}/visuals/assets/upload`

- Content-Type: `multipart/form-data`
- Fields:
  - `files`: one or multiple images
  - `origin` (optional): `"client_upload"` default
- Validations:
  - accept only PNG/JPEG/WebP
  - max per-file size: 10 MB
  - max files per request: 10
- Behavior:
  - Compute `sha256`, dimensions (Pillow)
  - Store original bytes + thumbnail variant in **GridFS** (or local filesystem for dev)
  - Populate `created_at` server-side (ISO timestamp)
- Response (envelope):
```json
{
  "data": {
    "assets": [ /* VisualAsset[] with all fields including created_at */ ]
  },
  "error": null
}
```

### 7.2 Serve asset content (P1) — scoped by project
To avoid cross-project access and simplify ownership checks:

**GET** `/api/projects/{project_id}/visuals/assets/{asset_id}/content?size=thumb|full`

- Returns raw bytes with correct `Content-Type`
- Must verify:
  - the `asset_id` exists **and** is referenced by that project's `visualPlan.assets`
- 404 if not found or not owned by the project

### 7.3 Delete asset (P1)
**DELETE** `/api/projects/{project_id}/visuals/assets/{asset_id}`

- Deletes original + thumbnail bytes from storage
- Returns:
```json
{ "data": { "deleted": true }, "error": null }
```

> **NOTE:** Metadata removal from `project.visualPlan.assets[]` + assignment cleanup is handled by frontend state + `saveProject()` after this delete succeeds.

> **Edge case:** If user closes browser after delete but before save, bytes are gone but metadata remains. This is acceptable for MVP — stale metadata simply shows a broken thumbnail and can be cleaned up on next interaction.

---

## 8. Thumbnail generation (implementation guidance, P1)

Generate thumbnails **on upload**.
- Tooling: Pillow
- Rule: scale down so max dimension is 512px (preserve aspect)
- Output format:
  - If original is PNG with alpha → thumbnail PNG
  - Else → thumbnail JPEG (quality ~85)
- Store thumb bytes alongside original (GridFS or equivalent), keyed by `asset_id` + suffix.

---

## 9. Draft regeneration & opportunity invalidation (UX)

If Tab 3 regenerates the draft and replaces `visualPlan.opportunities`, opportunity IDs may change.

MVP rule:
- If user triggers regenerate while there are existing assignments:
  - Show a warning: "Regenerating visuals will clear existing visual assignments. Continue?"
  - If confirmed: clear `visualPlan.assignments` (assets remain)

(Do not attempt fuzzy remapping in MVP.)

Add acceptance scenario AS-006 for this warning flow.

---

## 10. Error Handling

Backend uses existing `{data, error}` envelope:
```json
{
  "data": null,
  "error": { "code": "UPLOAD_TOO_LARGE", "message": "..." }
}
```

Suggested error codes:
- `UNSUPPORTED_MEDIA_TYPE`
- `UPLOAD_TOO_LARGE`
- `UPLOAD_LIMIT_EXCEEDED`
- `ASSET_NOT_FOUND`
- `STORAGE_ERROR`
- `DUPLICATE_ASSET` (optional if you dedupe by sha256)

Frontend:
- Upload: per-file error toast; continue others
- Assign/save: inline "Save failed" banner with retry

---

## 11. Acceptance Scenarios

**AS-001 Upload image shows in library**
- Upload `diagram.png`
- Thumbnail appears in library grid
- Refresh keeps it visible

**AS-002 Assign asset to opportunity**
- Assign `diagram.png` to opportunity `O1`
- Opportunity shows assigned with thumbnail
- Refresh preserves assignment

**AS-003 Skip opportunity**
- Mark `O2` as skipped
- Refresh preserves skipped state

**AS-004 Delete assigned asset**
- Delete `diagram.png`
- It disappears
- `O1` becomes unassigned

**AS-005 No opportunities state**
- If no opportunities exist
- Show empty message and still allow uploads

**AS-006 Regenerate clears assignments (with warning)**
- If assignments exist and user triggers regenerate
- Show warning
- On confirm, assignments cleared; assets preserved

**AS-007 Upload validation error**
- User attempts to upload a PDF or file exceeding 10MB
- Toast shows appropriate error ("Unsupported file type" or "File too large")
- Other valid files in the same batch still upload successfully

---

## 12. P2 (explicitly out of MVP)

- Use `VisualOpportunity.candidate_asset_ids` to highlight "suggested assets" in the picker.
- Download button + Copy URL / Copy Markdown buttons (see US4).
- AssetCard → "Assign to opportunity..." flow (MVP uses opportunity-driven assignment only).
- "Selected for export" flag (prefer computed from assignments or add later).
- Pagination/infinite scroll for large asset libraries.
