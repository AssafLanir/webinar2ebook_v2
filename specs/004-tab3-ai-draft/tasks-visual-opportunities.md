# Tasks: Visual Opportunity Generation (Spec 004.1)

**Purpose**: Implement `_generate_visual_plan()` so Tab 2 has opportunities to display
**Scope**: 6 tasks
**Blocks**: Spec 005 (Tab 2 needs opportunities to be useful)

---

## Tasks

- [ ] T001 Create OpenAI-compatible JSON schema for VisualOpportunity[] in `backend/src/llm/schemas.py`
  - Include: id, chapter_index, visual_type, title, prompt, caption, rationale, confidence
  - Exclude complex fields: placement (default), source_policy (default), candidate_asset_ids (empty)

- [ ] T002 Create visual opportunity prompt template in `backend/src/services/prompts.py`
  - System prompt: "You are analyzing ebook chapters to suggest visual opportunities"
  - Include visual_density guidance:
    - light: 1-2 per 3 chapters
    - medium: 1-2 per chapter
    - heavy: 2-4 per chapter
  - User prompt: chapter title, key points, transcript segment summary

- [ ] T003 Implement `_generate_visual_plan()` LLM call in `backend/src/services/draft_service.py`
  - If visual_density == "none": return empty (already done)
  - Else: call LLM with structured output schema
  - Generate opportunities for each chapter based on density
  - Assign unique IDs (uuid4)
  - Sort opportunities by chapter_index ASC, then confidence DESC (deterministic ordering)

- [ ] T004 Integrate visual opportunity generation into draft workflow in `backend/src/services/draft_service.py`
  - Call after chapters are planned
  - Log opportunity count generated
  - Handle LLM errors gracefully (log error, return empty opportunities, draft still succeeds)

- [ ] T005 [P] Add unit test for visual opportunity generation in `backend/tests/unit/test_visual_opportunities.py`
  - Test schema validates correctly
  - Test density-based opportunity count guidance
  - Test sorting order (chapter_index ASC, confidence DESC)

- [ ] T006 Manual integration test: generate draft with visual_density=medium
  - Verify opportunities appear in `project.visualPlan.opportunities`
  - Verify Tab 2 displays them in empty state or opportunity list
  - Include instructions + screenshots in PR description

---

## Definition of Done

1. Generating a draft with `visual_density != none` produces non-empty `project.visualPlan.opportunities`
2. Each opportunity has stable fields: `id`, `chapter_index`, `visual_type`, `title`, `prompt`, `rationale`, `confidence`
3. Opportunities are sorted by `chapter_index` ASC, then `confidence` DESC (prevents UI jumping)
4. On LLM failure, we log the error and return empty opportunities (draft generation still succeeds)
5. "light" density produces fewer opportunities than "medium"/"heavy" for the same outline

---

## Files Changed (PR Scope)

- `backend/src/llm/schemas.py`
- `backend/src/services/prompts.py`
- `backend/src/services/draft_service.py`
- `backend/tests/unit/test_visual_opportunities.py` (new)

No Tab 2 work in this PR.
