# Whitelist-Based Quote Generation Design

## Problem Statement

The current Ideas Edition pipeline follows a "generate → validate → surgery" pattern:
1. LLM generates quotes freely
2. Post-processing validates against transcript
3. Invalid quotes are surgically removed

This creates an endless "whack-a-mole" pattern where each fix exposes new leaks:
- Core Claims without quotes pass hard gate, then `fix_unquoted_excerpts()` adds quotes that were never validated
- LLM can fabricate plausible-sounding quotes that happen to match transcript substrings but weren't in Evidence Map
- Each new validation rule breaks something else

## Solution: Inversion of Control

Instead of validating after generation, we **constrain generation to only use validated quotes**:

1. **Extract validated excerpts from transcript FIRST** → build whitelist
2. **Give LLM a whitelist of quotes it can use** → constrained generation
3. **Enforce that only whitelisted quotes survive** → hard guarantee

This converges because the whitelist is the single source of truth.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        PHASE 1: PRE-GENERATION                       │
│                           (Deterministic)                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Evidence Map ──┬──► Whitelist Builder ──► Quote Whitelist          │
│                 │         │                    │                     │
│  Transcript ────┘         │                    ▼                     │
│  (raw + canonical)        │           Coverage Scorer                │
│                           │                    │                     │
│                           │                    ▼                     │
│                           │           Merge Weak Chapters            │
│                           │                    │                     │
│                           │                    ▼                     │
│                           └────────► Deterministic Excerpt           │
│                                      Selector                        │
│                                           │                          │
│                                           ▼                          │
│                                    Prompt Builder                    │
│                                    (inject excerpts)                 │
│                                           │                          │
└───────────────────────────────────────────┼──────────────────────────┘
                                            │
                                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        PHASE 2: GENERATION                           │
│                             (LLM)                                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│                     LLM generates chapter                            │
│                   (Key Excerpts pre-filled)                          │
│                                                                      │
└───────────────────────────────────────────┼──────────────────────────┘
                                            │
                                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       PHASE 3: ENFORCEMENT                           │
│                        (Hard Guarantee)                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Strip LLM Blockquotes ──► Whitelist Enforcer ──► GUEST-Only Filter │
│         │                        │                      │            │
│         │                        │                      │            │
│         ▼                        ▼                      ▼            │
│  Remove blockquotes       Replace valid quotes    Drop non-GUEST    │
│  outside Key Excerpts     Drop invalid quotes     Core Claims       │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Data Structures

### Speaker Typing

```python
class SpeakerRole(str, Enum):
    HOST = "host"
    GUEST = "guest"
    CALLER = "caller"
    CLIP = "clip"
    UNCLEAR = "unclear"

class SpeakerRef(BaseModel):
    speaker_id: str              # Canonical stable ID (e.g., "david_deutsch")
    speaker_name: str            # Display name (e.g., "David Deutsch")
    speaker_role: SpeakerRole    # Role for filtering (GUEST for Core Claims)
```

### Transcript Pair

```python
class TranscriptPair(BaseModel):
    """Both transcript forms needed for whitelist building."""
    raw: str              # Original transcript (for quote_text extraction)
    canonical: str        # Normalized (for matching)
```

### Whitelist Quote

```python
class WhitelistQuote(BaseModel):
    """A validated quote that can be used in generation."""
    quote_id: str                      # Stable ID: sha256(speaker_id|quote_canonical)[:16]
    quote_text: str                    # EXACT from raw transcript (for output)
    quote_canonical: str               # Casefolded/normalized (for matching only)
    speaker: SpeakerRef
    source_evidence_ids: list[str]     # Which Evidence Map entries sourced this
    chapter_indices: list[int]         # Which chapters can use this quote
    match_spans: list[tuple[int, int]] # Character positions in canonical transcript
```

### Coverage Metrics

```python
class CoverageLevel(str, Enum):
    STRONG = "strong"   # >= 5 usable quotes, >= 50 words/claim
    MEDIUM = "medium"   # >= 3 usable quotes, >= 30 words/claim
    WEAK = "weak"       # Below MEDIUM thresholds

class ChapterCoverage(BaseModel):
    chapter_index: int
    level: CoverageLevel
    usable_quotes: int           # Quotes >= MIN_USABLE_QUOTE_LENGTH
    quote_words_per_claim: float # Total quote words / claim count
    quotes_per_claim: float      # Quote count / claim count
    target_words: int            # Adjusted based on level
    generation_mode: str         # "normal" | "thin" | "excerpt_only"
```

---

## Component Details

### 1. Whitelist Builder

**Purpose:** Build the whitelist of validated quotes from Evidence Map.

**Key Design Decisions:**
- Uses **canonical transcript** for matching (normalized: straight quotes, dashes, collapsed whitespace)
- Extracts **exact quote_text from raw transcript** (preserves original formatting)
- Keys by `(speaker_id, quote_canonical)` → allows multiple candidates per key
- Self-healing: quote_text comes from transcript, not Evidence Map original

```python
def build_quote_whitelist(
    evidence_map: EvidenceMap,
    transcript: TranscriptPair,
) -> list[WhitelistQuote]:
    """
    Build whitelist by validating Evidence Map quotes against transcript.

    Returns only quotes that:
    1. Have a speaker (Unknown attribution rejected)
    2. Match as substring in canonical transcript
    3. Have speaker resolved to SpeakerRef
    """
    canonical_lower = transcript.canonical.casefold()
    whitelist_map: dict[tuple[str, str], WhitelistQuote] = {}

    for chapter_idx, chapter in enumerate(evidence_map.chapters):
        for claim in chapter.claims:
            for support in claim.support:
                if not support.speaker:
                    continue  # Unknown attribution

                speaker_ref = resolve_speaker(support.speaker)
                quote_for_match = canonicalize(support.quote).casefold()

                # Find in canonical transcript
                spans = find_all_occurrences(canonical_lower, quote_for_match)
                if not spans:
                    continue  # Not in transcript

                # Extract exact text from RAW transcript
                start, end = spans[0]
                exact_quote = transcript.raw[start:end]

                key = (speaker_ref.speaker_id, quote_for_match)

                if key in whitelist_map:
                    # Merge: add chapter, evidence ID
                    existing = whitelist_map[key]
                    if chapter_idx not in existing.chapter_indices:
                        existing.chapter_indices.append(chapter_idx)
                    existing.source_evidence_ids.append(support.evidence_id)
                else:
                    # Create new entry
                    quote_id = sha256(
                        f"{speaker_ref.speaker_id}|{quote_for_match}".encode()
                    ).hexdigest()[:16]

                    whitelist_map[key] = WhitelistQuote(
                        quote_id=quote_id,
                        quote_text=exact_quote,
                        quote_canonical=quote_for_match,
                        speaker=speaker_ref,
                        source_evidence_ids=[support.evidence_id],
                        chapter_indices=[chapter_idx],
                        match_spans=spans,
                    )

    return list(whitelist_map.values())
```

### 2. Coverage Scorer

**Purpose:** Assess each chapter's quote coverage before generation.

**Key Design Decisions:**
- Filters quotes by `MIN_USABLE_QUOTE_LENGTH` (e.g., 8 words)
- Uses `quote_words_per_claim` as primary density metric
- Drives generation mode: normal → thin → excerpt_only
- Tracks `target_words` for prompt injection

```python
MIN_USABLE_QUOTE_LENGTH = 8  # words
STRONG_QUOTES = 5
STRONG_WORDS_PER_CLAIM = 50
MEDIUM_QUOTES = 3
MEDIUM_WORDS_PER_CLAIM = 30

def compute_chapter_coverage(
    chapter_evidence: ChapterEvidence,
    whitelist: list[WhitelistQuote],
    chapter_index: int,
) -> ChapterCoverage:
    """Compute coverage metrics for a single chapter."""

    # Filter whitelist to this chapter
    chapter_quotes = [
        q for q in whitelist
        if chapter_index in q.chapter_indices
    ]

    # Filter by minimum length
    usable_quotes = [
        q for q in chapter_quotes
        if len(q.quote_text.split()) >= MIN_USABLE_QUOTE_LENGTH
    ]

    claim_count = len(chapter_evidence.claims)
    total_quote_words = sum(len(q.quote_text.split()) for q in usable_quotes)

    # Compute metrics
    quotes_per_claim = len(usable_quotes) / max(claim_count, 1)
    quote_words_per_claim = total_quote_words / max(claim_count, 1)

    # Determine level
    if len(usable_quotes) >= STRONG_QUOTES and quote_words_per_claim >= STRONG_WORDS_PER_CLAIM:
        level = CoverageLevel.STRONG
        target_words = 800
        mode = "normal"
    elif len(usable_quotes) >= MEDIUM_QUOTES and quote_words_per_claim >= MEDIUM_WORDS_PER_CLAIM:
        level = CoverageLevel.MEDIUM
        target_words = 500
        mode = "thin"
    else:
        level = CoverageLevel.WEAK
        target_words = 250
        mode = "excerpt_only"

    return ChapterCoverage(
        chapter_index=chapter_index,
        level=level,
        usable_quotes=len(usable_quotes),
        quote_words_per_claim=quote_words_per_claim,
        quotes_per_claim=quotes_per_claim,
        target_words=target_words,
        generation_mode=mode,
    )
```

### 3. Chapter Merger

**Purpose:** Merge adjacent WEAK chapters to improve coverage.

**Key Design Decisions:**
- Only merges adjacent WEAK chapters
- Re-validates combined coverage (might still be WEAK)
- Returns index mapping for downstream use

```python
def merge_weak_chapters(
    coverages: list[ChapterCoverage],
    evidence_map: EvidenceMap,
    whitelist: list[WhitelistQuote],
) -> tuple[list[ChapterCoverage], dict[int, int]]:
    """
    Merge adjacent WEAK chapters.

    Returns:
        merged_coverages: New coverage list with merged chapters
        index_map: old_index → new_index mapping
    """
    merged = []
    index_map: dict[int, int] = {}

    i = 0
    new_idx = 0
    while i < len(coverages):
        if (coverages[i].level == CoverageLevel.WEAK and
            i + 1 < len(coverages) and
            coverages[i + 1].level == CoverageLevel.WEAK):

            # Merge i and i+1
            combined = combine_coverages(
                coverages[i], coverages[i + 1],
                evidence_map, whitelist
            )
            merged.append(combined)
            index_map[i] = new_idx
            index_map[i + 1] = new_idx
            i += 2
        else:
            index_map[i] = new_idx
            merged.append(coverages[i])
            i += 1

        new_idx += 1

    return merged, index_map
```

### 4. Deterministic Excerpt Selector

**Purpose:** Select Key Excerpts from whitelist (valid by construction).

**Key Design Decisions:**
- Excerpts are selected, not generated—can never fail validation
- Uses stable tie-breakers: `(len(quote_text) desc, quote_id asc)`
- Quantity varies by coverage level
- GUEST quotes only

```python
EXCERPT_COUNTS = {
    CoverageLevel.STRONG: 4,
    CoverageLevel.MEDIUM: 3,
    CoverageLevel.WEAK: 2,
}

def select_deterministic_excerpts(
    whitelist: list[WhitelistQuote],
    chapter_index: int,
    coverage_level: CoverageLevel,
) -> list[WhitelistQuote]:
    """
    Select Key Excerpts deterministically from whitelist.

    Valid by construction: these quotes come from whitelist,
    so they're guaranteed to be transcript substrings with known speakers.
    """
    # Filter to this chapter, GUEST only
    candidates = [
        q for q in whitelist
        if chapter_index in q.chapter_indices
        and q.speaker.speaker_role == SpeakerRole.GUEST
    ]

    # Stable sort: longest first, then by quote_id for ties
    candidates.sort(key=lambda q: (-len(q.quote_text), q.quote_id))

    count = EXCERPT_COUNTS[coverage_level]
    return candidates[:count]
```

### 5. Whitelist Enforcer

**Purpose:** THE GUARANTEE—validate all quotes against whitelist.

**Key Design Decisions:**
- Processes BOTH block quotes and inline quotes
- Valid quotes: replaced with exact `quote_text` from whitelist
- Invalid quotes: dropped (block) or unquoted (inline)
- Uses multi-candidate lookup: `(speaker_id, quote_canonical) → list[WhitelistQuote]`

```python
def enforce_quote_whitelist(
    generated_text: str,
    whitelist: list[WhitelistQuote],
    chapter_index: int,
) -> EnforcementResult:
    """
    Enforce ALL quotes against whitelist.

    This is the hard guarantee. Quotes not in whitelist are removed.
    Quotes in whitelist are replaced with exact quote_text.
    """
    # Build lookup index
    lookup: dict[tuple[str, str], list[WhitelistQuote]] = {}
    for q in whitelist:
        key = (q.speaker.speaker_id, q.quote_canonical)
        lookup.setdefault(key, []).append(q)

    result = generated_text
    dropped = []
    replaced = []

    # Process block quotes (> "quote" — Speaker)
    for match in BLOCKQUOTE_PATTERN.finditer(result):
        quote_text = match.group("quote")
        speaker_text = match.group("speaker")

        validated = validate_blockquote(
            quote_text, speaker_text, chapter_index, lookup
        )

        if validated:
            result = replace_blockquote(result, match, validated)
            replaced.append(validated)
        else:
            result = drop_blockquote(result, match)
            dropped.append(quote_text)

    # Process inline quotes ("...")
    for match in INLINE_QUOTE_PATTERN.finditer(result):
        quote_text = match.group("quote")

        validated = validate_inline(quote_text, chapter_index, lookup)

        if validated:
            result = replace_inline(result, match, validated.quote_text)
            replaced.append(validated)
        else:
            result = unquote_inline(result, match)
            dropped.append(quote_text)

    return EnforcementResult(
        text=result,
        replaced=replaced,
        dropped=dropped,
    )

def validate_blockquote(
    quote_text: str,
    speaker_text: str | None,
    chapter_index: int,
    lookup: dict[tuple[str, str], list[WhitelistQuote]],
) -> WhitelistQuote | None:
    """Find matching whitelist entry for a block quote."""
    quote_canonical = canonicalize(quote_text).casefold()

    # Try to resolve speaker
    if speaker_text:
        speaker_id = resolve_speaker_id(speaker_text)
        candidates = lookup.get((speaker_id, quote_canonical), [])
    else:
        # No speaker—search all entries with this quote
        candidates = []
        for (sid, qc), entries in lookup.items():
            if qc == quote_canonical:
                candidates.extend(entries)

    # Find best match for this chapter
    for candidate in candidates:
        if chapter_index in candidate.chapter_indices:
            return candidate

    # Fall back to any candidate
    return candidates[0] if candidates else None
```

### 6. GUEST-Only Filter for Core Claims

**Purpose:** Ensure Core Claims only cite GUEST speakers.

**Key Design Decisions:**
- Uses whitelist speaker role, not parsed attribution text
- Drops claims whose quote isn't from GUEST
- Doesn't modify claims, just filters

```python
def enforce_core_claims_guest_only(
    claims: list[CoreClaim],
    whitelist: list[WhitelistQuote],
    chapter_index: int,
) -> list[CoreClaim]:
    """
    Filter Core Claims to only include GUEST quotes.

    Uses whitelist speaker role—doesn't parse attribution from text.
    """
    # Build quote lookup
    quote_to_entry: dict[str, WhitelistQuote] = {}
    for q in whitelist:
        if chapter_index in q.chapter_indices:
            quote_to_entry[q.quote_canonical] = q

    valid_claims = []
    for claim in claims:
        quote_canonical = canonicalize(claim.supporting_quote).casefold()

        entry = quote_to_entry.get(quote_canonical)
        if not entry:
            continue  # Quote not in whitelist

        if entry.speaker.speaker_role != SpeakerRole.GUEST:
            continue  # Not from guest

        valid_claims.append(claim)

    return valid_claims
```

### 7. LLM Blockquote Stripper

**Purpose:** Remove blockquotes LLM added outside Key Excerpts section.

**Key Design Decisions:**
- Key Excerpts section is preserved (injected deterministically)
- Blockquotes in narrative are stripped (narrative should paraphrase)
- Guards against LLM ignoring instructions

```python
def strip_llm_blockquotes(generated_text: str) -> str:
    """
    Remove blockquote syntax LLM added outside Key Excerpts.

    Key Excerpts section was injected deterministically and is preserved.
    Narrative should paraphrase, not quote—strip any blockquotes there.
    """
    # Find Key Excerpts section
    key_excerpts_match = re.search(r"### Key Excerpts", generated_text)

    if key_excerpts_match:
        before = generated_text[:key_excerpts_match.start()]
        after = generated_text[key_excerpts_match.start():]

        # Strip blockquotes from narrative (before Key Excerpts)
        before = re.sub(r"^>\s*.*$", "", before, flags=re.MULTILINE)

        # Find Core Claims section within after
        core_claims_match = re.search(r"### Core Claims", after)
        if core_claims_match:
            excerpts_section = after[:core_claims_match.start()]
            claims_and_rest = after[core_claims_match.start():]

            # Strip blockquotes from Core Claims too (quotes inline only)
            claims_and_rest = re.sub(r"^>\s*.*$", "", claims_and_rest, flags=re.MULTILINE)

            return before + excerpts_section + claims_and_rest

        return before + after

    # No Key Excerpts found—strip all blockquotes
    return re.sub(r"^>\s*.*$", "", generated_text, flags=re.MULTILINE)
```

---

## Complete Pipeline

```python
async def generate_ideas_edition_chapter(
    chapter_index: int,
    evidence_map: EvidenceMap,
    transcript: TranscriptPair,
) -> ChapterDraft:
    """
    Complete Ideas Edition pipeline with whitelist-based quote generation.

    Guarantees:
    1. Key Excerpts are exact transcript substrings (by construction)
    2. Core Claims reference only validated GUEST quotes
    3. Inline quotes in narrative are whitelist-enforced
    4. No fabricated quotes survive
    """

    # ═══════════════════════════════════════════════════════════════════
    # PHASE 1: PRE-GENERATION (Deterministic)
    # ═══════════════════════════════════════════════════════════════════

    # 1a. Build whitelist
    whitelist = build_quote_whitelist(evidence_map, transcript)

    # 1b. Compute coverage for all chapters
    coverages = [
        compute_chapter_coverage(ch, whitelist, i)
        for i, ch in enumerate(evidence_map.chapters)
    ]

    # 1c. Merge weak chapters
    coverages, index_map = merge_weak_chapters(coverages, evidence_map, whitelist)

    # 1d. Get effective chapter index and coverage
    effective_index = index_map.get(chapter_index, chapter_index)
    coverage = coverages[effective_index]

    # 1e. Select deterministic excerpts
    excerpts = select_deterministic_excerpts(
        whitelist=whitelist,
        chapter_index=effective_index,
        coverage_level=coverage.level,
    )

    # 1f. Build prompt with injected excerpts
    excerpts_markdown = format_excerpts_markdown(excerpts)
    prompt = IDEAS_PROMPT_TEMPLATE.replace(
        "{{KEY_EXCERPTS_PLACEHOLDER}}",
        excerpts_markdown,
    )
    prompt = prompt.replace("{{TARGET_WORDS}}", str(coverage.target_words))
    prompt = prompt.replace("{{GENERATION_MODE}}", coverage.generation_mode)

    # ═══════════════════════════════════════════════════════════════════
    # PHASE 2: GENERATION (LLM)
    # ═══════════════════════════════════════════════════════════════════

    generated = await llm_client.generate(prompt)

    # ═══════════════════════════════════════════════════════════════════
    # PHASE 3: ENFORCEMENT (Hard Guarantee)
    # ═══════════════════════════════════════════════════════════════════

    # 3a. Strip LLM blockquotes outside Key Excerpts
    cleaned = strip_llm_blockquotes(generated)

    # 3b. Enforce all quotes against whitelist
    enforcement_result = enforce_quote_whitelist(
        cleaned, whitelist, effective_index
    )

    # 3c. Parse structured sections
    parsed = parse_ideas_chapter(enforcement_result.text)

    # 3d. Enforce Core Claims GUEST-only
    parsed.core_claims = enforce_core_claims_guest_only(
        parsed.core_claims, whitelist, effective_index
    )

    # 3e. Final assembly
    return ChapterDraft(
        chapter_index=chapter_index,
        effective_index=effective_index,
        title=parsed.title,
        narrative=parsed.narrative,
        key_excerpts=excerpts,  # Deterministic, not parsed
        core_claims=parsed.core_claims,
        coverage=coverage,
        enforcement=enforcement_result,
    )
```

---

## What Gets Removed/Replaced

### Removed from Current Pipeline
- `fix_unquoted_excerpts()` — quotes are now injected deterministically
- `validate_quote_against_transcript()` — replaced by whitelist validation
- Quote validation that runs after LLM generation — now pre-validated

### New Components
- `build_quote_whitelist()` — builds validated quote whitelist
- `compute_chapter_coverage()` — assesses coverage pre-generation
- `merge_weak_chapters()` — handles sparse chapters
- `select_deterministic_excerpts()` — picks Key Excerpts from whitelist
- `enforce_quote_whitelist()` — THE GUARANTEE
- `enforce_core_claims_guest_only()` — filters by speaker role
- `strip_llm_blockquotes()` — guards against LLM adding quotes

### Modified Components
- Prompt template — gets `{{KEY_EXCERPTS_PLACEHOLDER}}` and `{{TARGET_WORDS}}`
- Chapter generation entry point — uses new 3-phase pipeline

---

## Error Handling

| Situation | Handling |
|-----------|----------|
| Evidence Map quote not in transcript | Excluded from whitelist (logged) |
| Unknown speaker attribution | Excluded from whitelist |
| Whitelist empty for chapter | Generate excerpt-only mode |
| LLM ignores excerpt placeholder | Strip blockquotes, enforce inline |
| Quote matches whitelist but wrong chapter | Fall back to any chapter match |
| Core Claim quotes HOST | Dropped in GUEST-only filter |

---

## Testing Strategy

### Unit Tests
- Whitelist builder: various Evidence Map → whitelist scenarios
- Coverage scorer: STRONG/MEDIUM/WEAK thresholds
- Excerpt selector: stable ordering, correct counts
- Whitelist enforcer: valid replacement, invalid dropping
- GUEST-only filter: role-based filtering
- Blockquote stripper: preserves Key Excerpts section

### Integration Tests
- Full pipeline: Evidence Map → generated chapter
- Coverage-driven generation: STRONG vs WEAK output
- Merged chapters: index mapping correctness

### Regression Tests
- Canonicalization stability (same input → same canonical)
- Quote ID stability (deterministic hashing)
- Offset validity (extracted text matches)
- No fabricated quotes survive (adversarial prompts)

---

## Non-Goals

- Breaking existing modes (Verbatim, Curated Verbatim)
- Major UX changes
- Real-time processing
- Changing Evidence Map structure

---

## Success Criteria

1. **Zero fabricated quotes** — every quote in output exists in whitelist
2. **Key Excerpts valid by construction** — not validated, selected
3. **Core Claims GUEST-only** — no HOST quotes in claims
4. **Coverage-aware generation** — sparse chapters handled gracefully
5. **Convergent behavior** — no whack-a-mole, system stabilizes
