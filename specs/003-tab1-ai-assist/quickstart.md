# Quickstart: Tab 1 AI Assist

**Feature**: 003-tab1-ai-assist

This guide provides step-by-step instructions to implement the AI Assist feature.

---

## Prerequisites

1. **Features 001 and 002 complete**: Tab 1 UI and backend persistence working
2. **API keys configured**:
   - `OPENAI_API_KEY` in environment
   - `ANTHROPIC_API_KEY` in environment (for fallback)
3. **Dependencies installed**:
   ```bash
   cd backend
   pip install openai anthropic
   ```

---

## Implementation Order

### Phase 1: LLM Abstraction Layer (Backend)

1. **Create LLM module structure**:
   ```
   backend/src/llm/
   ├── __init__.py
   ├── models.py      # LLMRequest, LLMResponse, ChatMessage
   ├── errors.py      # LLMError hierarchy
   ├── client.py      # High-level client with fallback
   └── providers/
       ├── __init__.py
       ├── base.py     # LLMProvider ABC
       ├── openai.py   # OpenAIProvider
       └── anthropic.py # AnthropicProvider
   ```

2. **Implement in order**:
   - `models.py` - Pydantic models per `docs/llm_adapter_contract.md`
   - `errors.py` - Exception classes
   - `providers/base.py` - Abstract base class
   - `providers/openai.py` - OpenAI implementation
   - `providers/anthropic.py` - Anthropic implementation
   - `client.py` - Client with retry + fallback logic

3. **Test providers**:
   ```bash
   cd backend
   pytest tests/unit/llm/ -v
   ```

### Phase 2: AI Service Layer (Backend)

1. **Create AI service**:
   ```
   backend/src/services/ai_service.py
   ```

2. **Implement three functions**:
   - `clean_transcript(transcript: str) -> str`
   - `suggest_outline(transcript: str) -> list[SuggestedOutlineItem]`
   - `suggest_resources(transcript: str) -> list[SuggestedResource]`

3. **Each function**:
   - Constructs appropriate system prompt
   - Builds LLMRequest with correct response_format
   - Calls LLM client
   - Parses and validates response
   - Handles errors gracefully

### Phase 3: API Endpoints (Backend)

1. **Create AI router**:
   ```
   backend/src/api/routes/ai.py
   ```

2. **Implement endpoints per `contracts/ai-endpoints.yaml`**:
   - `POST /api/ai/clean-transcript`
   - `POST /api/ai/suggest-outline`
   - `POST /api/ai/suggest-resources`

3. **Register router in main.py**:
   ```python
   from api.routes.ai import router as ai_router
   app.include_router(ai_router, prefix="/api/ai", tags=["AI"])
   ```

4. **Test endpoints**:
   ```bash
   cd backend
   pytest tests/integration/test_ai_endpoints.py -v
   ```

### Phase 4: Frontend Types & API (Frontend)

1. **Create AI types**:
   ```
   frontend/src/types/ai.ts
   ```
   (See `data-model.md` for type definitions)

2. **Add API functions in `services/api.ts`**:
   ```typescript
   export async function cleanTranscript(transcript: string): Promise<CleanTranscriptResponse>
   export async function suggestOutline(transcript: string): Promise<SuggestOutlineResponse>
   export async function suggestResources(transcript: string): Promise<SuggestResourcesResponse>
   ```

### Phase 5: Frontend Context (Frontend)

1. **Extend `ProjectContext.tsx`**:
   - Add `aiAction: AIActionState` to state
   - Add `aiPreview: AIPreviewState` to state
   - Add action types for AI operations
   - Implement action handlers

2. **Key actions**:
   - `START_AI_ACTION` - Set loading state
   - `AI_ACTION_SUCCESS` - Open preview modal
   - `AI_ACTION_ERROR` - Show error, enable retry
   - `APPLY_AI_PREVIEW` - Apply and close
   - `DISCARD_AI_PREVIEW` - Close without changes

### Phase 6: Frontend Components (Frontend)

1. **Create `AIAssistSection.tsx`**:
   - Three buttons: "Clean Transcript (AI)", "Suggest Outline (AI)", "Suggest Resources (AI)"
   - Disabled when transcript empty or action in progress
   - Loading indicator during processing

2. **Create `AIPreviewModal.tsx`**:
   - Renders preview based on action type
   - Text preview for transcript cleanup
   - Selectable list for outline/resources
   - Apply/Discard buttons
   - Select all/Deselect all for lists

3. **Modify `Tab1Content.tsx`**:
   - Import and render `<AIAssistSection />` after "Fill with Sample Data" button

### Phase 7: Integration Testing

1. **Backend integration test**:
   ```python
   # tests/integration/test_ai_endpoints.py
   def test_clean_transcript_success():
       ...
   def test_suggest_outline_success():
       ...
   def test_suggest_resources_success():
       ...
   def test_ai_error_handling():
       ...
   ```

2. **Manual E2E test**:
   - Create project
   - Paste raw transcript
   - Test each AI action
   - Apply suggestions
   - Verify persistence after refresh

---

## Configuration

### Environment Variables

```bash
# Required
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Optional (defaults shown)
LLM_DEFAULT_PROVIDER=openai
LLM_TIMEOUT_SECONDS=60
LLM_MAX_RETRIES=3
```

### Model Selection

Default models (can be configured):
- OpenAI: `gpt-4o` (or `gpt-4o-mini` for cost savings)
- Anthropic: `claude-sonnet-4-5-20250929`

---

## Testing Checklist

- [ ] LLM providers unit tests pass
- [ ] AI service unit tests pass
- [ ] AI endpoints integration tests pass
- [ ] Frontend components render correctly
- [ ] Clean Transcript flow works end-to-end
- [ ] Suggest Outline flow works end-to-end
- [ ] Suggest Resources flow works end-to-end
- [ ] Error handling shows user-friendly messages
- [ ] Applied suggestions persist after refresh
- [ ] Existing Tab 1 functionality unchanged

---

## Troubleshooting

### "AI suggestions are temporarily unavailable"
- Check API keys are set in environment
- Check network connectivity to OpenAI/Anthropic
- Check server logs for detailed error

### Timeout errors
- Increase `LLM_TIMEOUT_SECONDS` for long transcripts
- Consider shortening transcript

### JSON parsing errors
- Check model supports structured output
- Verify JSON schema is valid
- Check Anthropic fallback is using tool_use pattern correctly
