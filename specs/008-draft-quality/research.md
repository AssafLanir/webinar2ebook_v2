# Research: Draft Quality System

**Feature**: 008-draft-quality
**Date**: 2026-01-01

## 1. Repetition Detection Algorithm

**Decision**: N-gram based detection with configurable thresholds

**Rationale**:
- N-grams (3-5 word sequences) catch meaningful repetition without false positives on common phrases
- Threshold of 3+ occurrences balances signal vs noise
- Can run entirely in Python without LLM calls (fast, deterministic)

**Alternatives Considered**:
- TF-IDF similarity: Too coarse, misses exact repetition
- Sentence embeddings: Requires LLM, slower, overkill for exact matches
- Simple word frequency: Too many false positives on common words

**Implementation**:
```python
def find_repeated_phrases(text: str, min_words: int = 3, max_words: int = 8, min_count: int = 3) -> list[tuple[str, int]]:
    # Generate n-grams, count occurrences, filter by threshold
```

## 2. Faithfulness Scoring Approach

**Decision**: LLM-based comparison with structured prompt

**Rationale**:
- Faithfulness requires semantic understanding (not pattern matching)
- LLM can compare draft claims against transcript content
- Structured output ensures consistent scoring

**Alternatives Considered**:
- Keyword overlap: Misses paraphrasing, too simplistic
- Embedding similarity: Doesn't catch factual errors, only topic drift
- Manual annotation: Not scalable

**Implementation**:
- Send transcript + draft chapter to LLM
- Ask for: faithfulness score (1-100), list of unsupported claims
- Use existing LLM client with retry/fallback

## 3. Structural Analysis Rules

**Decision**: Regex-based rules with configurable thresholds

| Rule | Threshold | Severity |
|------|-----------|----------|
| Paragraph too long | > 300 words | warning |
| Sentence too long | > 50 words | info |
| Heading skip level | H1 → H3 (skipped H2) | warning |
| Chapter imbalance | > 3x length variance | info |
| Excessive passive voice | > 30% of sentences | info |
| Repeated phrase | 3+ occurrences | warning |

**Rationale**: These are industry-standard readability guidelines that can be checked without LLM.

## 4. QA Report Storage

**Decision**: Store in project document as `qaReport` field

**Rationale**:
- Avoids new MongoDB collection
- QA report is 1:1 with project
- Easy to fetch with project data
- Follows existing pattern (draftText, visualPlan, etc.)

**Alternatives Considered**:
- Separate collection: Overhead for 1:1 relationship
- File storage: Harder to query, no atomicity
- In-memory only: Lost on restart

## 5. Editor Pass Safety

**Decision**: Single-pass with faithfulness verification

**Rationale**:
- Recursive passes risk content drift
- Post-edit faithfulness check catches new hallucinations
- User must explicitly trigger (not automatic)

**Guardrails**:
1. Limit to single pass per user action
2. Preserve markdown structure (headings, lists, code blocks)
3. Re-run faithfulness check after edit
4. Show diff for user review
5. Allow revert to original

## 6. Regression Suite Design

**Decision**: JSON fixture file with baseline scores

**Structure**:
```json
{
  "version": "1.0",
  "projects": [
    {
      "id": "abc123",
      "name": "David Deutsch - Beginning of Infinity",
      "baseline_scores": {
        "overall": 72,
        "structure": 85,
        "clarity": 70,
        "faithfulness": 80,
        "repetition": 60,
        "completeness": 75
      },
      "expected_issues": {
        "critical": 0,
        "warning": { "min": 5, "max": 15 },
        "info": { "min": 10, "max": 30 }
      }
    }
  ]
}
```

**Rationale**:
- Simple JSON is easy to maintain
- Tolerance ranges handle natural variation
- Can run in CI without database access (uses stored drafts)

## 7. Performance Optimization

**Decision**: Hybrid approach with fast path

**Strategy**:
1. **Structural analysis first** (< 1 second) - regex-based
2. **Semantic analysis second** (5-20 seconds) - LLM-based
3. **Cache LLM results** per draft hash
4. **Skip semantic if draft unchanged**

**Rationale**: 60%+ of issues are structural and can be caught instantly.
