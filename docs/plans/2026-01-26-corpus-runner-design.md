# Corpus Runner Design: End-to-End Baseline Testing

**Date:** 2026-01-26
**Status:** Draft
**Goal:** Create a one-command corpus runner that generates Ideas Edition drafts for all corpus transcripts, runs quality + groundedness validation, and enforces rollout gates.

## Overview

The corpus runner establishes a repeatable baseline for the Groundedness Harness v1. It:
1. Generates drafts via the same code path as production (DraftGen adapter)
2. Validates Ideas Edition contract (structure) and quote provenance (groundedness)
3. Computes yield metrics for diagnostics
4. Enforces rollout gate criteria
5. Produces reproducible reports with full metadata

## Non-Goals

- Production integration (stays behind feature flag)
- Histogram/distribution visualizations (deferred until baseline exists)
- Failure classification bins (driven by actual baseline failures)
- LLM-generated outlines (use deterministic defaults for baseline isolation)
- Multi-mode runs in v1 (single content_mode per run)

## Architecture

### DraftGen Adapter

Unified interface for draft generation with pluggable backends:

```
┌─────────────────────────────────────────────────────────┐
│                    Corpus Runner CLI                     │
│  (generate_blocking in CLI layer, not adapter)          │
└─────────────────────┬───────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────┐
│                   DraftGen Adapter                       │
│  - Enforces content_mode is set                         │
│  - Captures reproducibility metadata                    │
│  - Never re-implements generation logic                 │
└─────────────────────┬───────────────────────────────────┘
                      │
          ┌───────────┴───────────┐
          ▼                       ▼
┌─────────────────┐     ┌─────────────────┐
│  LocalBackend   │     │  HTTPBackend    │
│  (direct import)│     │  (API client)   │
└─────────────────┘     └─────────────────┘
```

**Key constraints:**
1. Always sets `style_config.style.content_mode` to a valid mode (default: `"essay"`)
2. Separately enforces Ideas Edition output contract as hard-fail
3. Never re-implements generation logic; adapter only orchestrates + polls
4. Captures reproducibility metadata (commit, prompt version, seed, backend, mode)
5. Uses same `DraftGenerateRequest` model as production API

### Verdict Precedence

Overall verdict is computed with explicit precedence:

```python
def compute_verdict(structure, groundedness, yield_metrics, thresholds):
    # 1. Structure failures are fatal
    if structure.verdict == "FAIL":
        return "FAIL", ["structure_fail"]

    # 2. Preflight failures are fatal (when require_preflight_pass=True)
    if yield_metrics.preflight_verdict == "FAIL":
        return "FAIL", ["preflight_fail"]

    # 3. Groundedness failures are fatal
    if groundedness.overall_verdict == "FAIL":
        return "FAIL", ["groundedness_fail"]

    # 4. Check WARN thresholds
    warns = []
    if yield_metrics.fallback_ratio > thresholds.warn_fallback_ratio:
        warns.append("high_fallback")
    if yield_metrics.p10_prose_words < thresholds.warn_min_p10_prose:
        warns.append("low_prose")
    if groundedness.excerpt_provenance.provenance_rate < 1.0:
        warns.append("missing_excerpts")
    if groundedness.claim_support.evidence_provenance_rate < 1.0:
        warns.append("missing_evidence")

    if warns:
        return "WARN", warns

    return "PASS", []
```

### Thresholds (Single Source of Truth)

```python
# backend/src/corpus/thresholds.py

@dataclass
class Thresholds:
    """Centralized threshold definitions."""

    # Per-transcript WARN thresholds
    warn_fallback_ratio: float = 0.25
    warn_min_p10_prose: int = 60
    warn_excerpt_provenance: float = 1.0  # Any missing = WARN
    warn_claim_provenance: float = 1.0

    # Corpus-level rollout gate
    gate_max_fail: int = 0
    gate_max_warn: int = 2
    gate_max_fallback_rate: float = 0.25
    gate_min_p10_prose: int = 60

DEFAULT_THRESHOLDS = Thresholds()
```

## Work Unit Schema

### Per-Transcript Outputs

Directory: `corpus_output/{transcript_id}/`

#### 1. `request.json` — Input snapshot
```json
{
  "transcript_id": "T0001_markmonitor_web3",
  "transcript_path": "backend/corpora_private/T0001_markmonitor_web3/normalized.txt",
  "outline": [
    {"id": "1", "title": "Introduction", "level": 1},
    {"id": "2", "title": "Main Content", "level": 1},
    {"id": "3", "title": "Conclusion", "level": 1}
  ],
  "style_config": {"style": {"content_mode": "essay", ...}},
  "content_mode": "essay",
  "candidate_count": 1,
  "require_preflight_pass": true,
  "outline_sha256": "abc123...",
  "style_config_sha256": "def456..."
}
```

#### 2. `draft_meta.json` — Reproducibility envelope
```json
{
  "run_id": "T0001__essay__c1__a1b2c3",
  "transcript_id": "T0001_markmonitor_web3",
  "candidate_index": 0,
  "transcript_path": "backend/corpora_private/T0001_markmonitor_web3/normalized.txt",
  "draft_path": "corpus_output/T0001_markmonitor_web3/draft.md",

  "git_commit": "403c616",
  "config_hash": "sha256...",
  "prompt_version": "ideas_v3",
  "model": "gpt-4o-mini",
  "temperature": 0.7,
  "routing_version": "2026-01-26",

  "backend": "local",
  "content_mode": "essay",
  "seed": null,
  "normalized_sha256": "input transcript hash",
  "generation_time_s": 45.2
}
```

#### 3. `draft.md` — Generated draft markdown

#### 4. `structure.json` — Ideas Edition contract
```json
{
  "verdict": "PASS",
  "violations": [],
  "has_chapter_structure": true,
  "has_key_excerpts": true,
  "has_core_claims": true,
  "has_interview_leakage": false,
  "chapter_count": 3,
  "key_excerpt_count": 6,
  "core_claim_count": 9,
  "chapters": [
    {"n": 1, "title": "Introduction", "has_key_excerpts": true, "has_core_claims": true, "excerpt_count": 2, "claim_count": 3},
    {"n": 2, "title": "Main Content", "has_key_excerpts": true, "has_core_claims": true, "excerpt_count": 2, "claim_count": 3},
    {"n": 3, "title": "Conclusion", "has_key_excerpts": true, "has_core_claims": true, "excerpt_count": 2, "claim_count": 3}
  ]
}
```

#### 5. `groundedness.json` — Quote provenance
```json
{
  "overall_verdict": "PASS",
  "excerpt_provenance": {
    "excerpts_total": 6,
    "excerpts_found": 6,
    "excerpts_not_found": 0,
    "provenance_rate": 1.0,
    "missing_quotes": [],
    "verdict": "PASS"
  },
  "claim_support": {
    "claims_total": 9,
    "claims_with_evidence": 9,
    "evidence_quotes_found": 9,
    "evidence_quotes_not_found": 0,
    "evidence_provenance_rate": 1.0,
    "missing_evidence_quotes": [],
    "verdict": "PASS"
  }
}
```

#### 6. `yield.json` — Quality metrics (diagnostic)
```json
{
  "total_word_count": 2500,
  "prose_word_count": 1800,
  "chapter_count": 3,
  "avg_prose_words_per_chapter": 600.0,
  "prose_words_per_chapter": [550, 650, 600],
  "p10_prose_words": 550.0,
  "median_prose_words": 600.0,
  "chapters_with_fallback": 0,
  "fallback_ratio": 0.0,
  "drop_ratio": 0.15,
  "drop_reasons": {"quote_leak": 2, "banned_name": 1},
  "entity_metrics": {
    "brand_mentions": 12,
    "acronym_mentions": 5,
    "person_mentions_blocked": 2
  },
  "preflight_verdict": "PASS"
}
```

#### 7. `gate_row.json` — Rollout gate summary
```json
{
  "run_id": "T0001__essay__c1__a1b2c3",
  "transcript_id": "T0001_markmonitor_web3",
  "candidate_index": 0,
  "content_mode": "essay",
  "verdict": "PASS",
  "structure_verdict": "PASS",
  "groundedness_verdict": "PASS",
  "excerpt_provenance_rate": 1.0,
  "claim_provenance_rate": 1.0,
  "fallback_ratio": 0.0,
  "p10_prose_words": 550.0,
  "failure_causes": []
}
```

### Corpus-Level Outputs

Directory: `corpus_output/`

#### `corpus_report.json`
```json
{
  "generated_at": "2026-01-26T15:30:00Z",
  "git_commit": "403c616",
  "config_hash": "...",
  "prompt_version": "ideas_v3",
  "content_mode": "essay",
  "require_preflight_pass": true,
  "transcript_count": 12,

  "verdicts": {"PASS": 9, "WARN": 2, "FAIL": 1},

  "aggregates": {
    "avg_excerpt_provenance": 0.95,
    "avg_claim_provenance": 0.92,
    "avg_fallback_ratio": 0.08,
    "p10_prose_words": 85.0,
    "median_prose_words": 450.0
  },

  "thresholds": {
    "warn_fallback_ratio": 0.25,
    "warn_min_p10_prose": 60,
    "gate_max_fail": 0,
    "gate_max_warn": 2,
    "gate_max_fallback_rate": 0.25,
    "gate_min_p10_prose": 60
  },

  "rollout_gate": {
    "passed": false,
    "violations": ["fail_count=1 exceeds gate_max_fail=0"]
  },

  "gate_rows": [...]
}
```

#### `corpus_summary.md`
Human-readable summary with:
- Run metadata (commit, timestamp, mode)
- Verdict summary table
- Top offenders (FAIL/WARN transcripts with causes)
- Rollout gate status

## CLI Specification

```bash
# Full corpus run
python -m corpus.runner \
  --corpus backend/corpora/index.jsonl \
  --out corpus_output/ \
  --content-mode essay \
  --require-preflight

# HTTP backend
python -m corpus.runner \
  --corpus backend/corpora/index.jsonl \
  --backend http \
  --base-url http://localhost:8000/api

# CI mode (exit 1 if gate fails)
python -m corpus.runner \
  --corpus backend/corpora/index.jsonl \
  --ci

# Single transcript
python -m corpus.runner \
  --transcript-id T0001_markmonitor_web3 \
  --out corpus_output/

# Filter transcripts
python -m corpus.runner \
  --corpus backend/corpora/index.jsonl \
  --only T0002,T0003,T0010 \
  --out corpus_output/

python -m corpus.runner \
  --corpus backend/corpora/index.jsonl \
  --skip T0008,T0011 \
  --out corpus_output/
```

### CLI Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--corpus` | Required | Path to index.jsonl |
| `--out` | `corpus_output/` | Output directory |
| `--backend` | `local` | `local` or `http` |
| `--base-url` | `http://localhost:8000/api` | API base URL (http backend) |
| `--content-mode` | `essay` | `interview`, `essay`, or `tutorial` |
| `--require-preflight` | `True` | Fail on preflight failures |
| `--ci` | `False` | Exit non-zero if gate fails |
| `--only` | None | Comma-separated transcript IDs to include |
| `--skip` | None | Comma-separated transcript IDs to exclude |
| `--timeout` | `600` | Per-transcript timeout in seconds |
| `--types` | `Type1` | Transcript types to include (e.g., `Type1,Type2`) |
| `--workers` | `1` | Parallel workers (1 = sequential) |
| `--cache` | `drafts` | Cache mode: `drafts` or `off` |
| `--regen` | `False` | Force regeneration (ignore cache) |
| `--outline-mode` | `default` | `default` (3-chapter) or `corpus` (from metadata) |

## Default Outline

For baseline isolation, use minimal deterministic outline:

```python
DEFAULT_OUTLINE = [
    {"id": "1", "title": "Introduction", "level": 1},
    {"id": "2", "title": "Main Content", "level": 1},
    {"id": "3", "title": "Conclusion", "level": 1},
]
```

**Future Option D:** Deterministic outline splitter (no LLM):
- Split by timestamp thirds
- Detect agenda markers / "Q&A" sections
- Maintain full determinism

## File Structure

```
backend/
├── src/
│   └── corpus/
│       ├── __init__.py
│       ├── draft_gen.py      # DraftGen adapter + backends
│       ├── runner.py         # Main corpus runner logic
│       ├── thresholds.py     # Centralized threshold definitions
│       ├── validators.py     # Structure + yield validators
│       ├── reporters.py      # Report generation
│       └── cache.py          # Draft caching logic
├── scripts/
│   └── run_corpus.py         # CLI entrypoint (thin wrapper)
├── corpora/
│   └── index.jsonl           # Corpus manifest
└── corpus_cache/             # Draft cache directory (gitignored)
    └── {cache_key}/
        ├── draft.md
        └── draft_meta.json
```

## Acceptance Criteria

### P0: Baseline Run
- [ ] Single command runs all Type1 transcripts through generation
- [ ] Each transcript produces all 7 output files
- [ ] Corpus report includes aggregates and gate verdict
- [ ] CI mode exits non-zero on gate failure

### P1: Reproducibility
- [ ] Same inputs + same commit = same outputs (modulo LLM non-determinism)
- [ ] All metadata captured in draft_meta.json
- [ ] Config hash reproducible from stored components

### P2: Debugging Support
- [ ] `--only` / `--skip` flags work
- [ ] Per-chapter structure detail in structure.json
- [ ] Clear failure causes in gate_row.json

## Implementation Plan

1. **PR A: DraftGen Adapter** (~2-3 files)
   - `draft_gen.py` with LocalBackend + HTTPBackend
   - `thresholds.py` with centralized constants
   - Unit tests for adapter

2. **PR B: Corpus Runner Core** (~3-4 files)
   - `runner.py` main orchestration
   - `validators.py` structure + yield checks
   - `reporters.py` JSON + markdown output
   - Integration test with 1-2 transcripts

3. **PR C: CLI + CI Integration**
   - CLI entrypoint with all flags
   - CI workflow for gate enforcement
   - Documentation

## Resolved Decisions

### 1. Per-transcript custom outlines
**Decision:** Optional, off-by-default.

- v1 behavior: use `DEFAULT_OUTLINE` unless entry explicitly provides outline
- Metadata shape: allow `outline: [...]` inline or `outline_path: "path/to/outline.json"`
- CLI: `--outline-mode default|corpus` (default = deterministic 3-chapter)

### 2. Parallel vs sequential execution
**Decision:** Default sequential; bounded parallelism as optional flag.

- Default: `--workers 1` for simpler debugging + deterministic logs
- Optional: `--workers N` with semaphore-bounded concurrency
- Rationale: generation can be rate-limited; parallel failures make debugging painful

### 3. Draft caching
**Decision:** Cache generation output only, always re-run validators.

- Cache key: `normalized_sha256 + content_mode + candidate_count + config_hash`
- On cache hit: reuse `draft.md` + `draft_meta.json`
- Always re-run: structure/groundedness/yield/gate_row (validator logic evolves)
- Flags: `--cache drafts|off` (default `drafts`), `--regen` to force regeneration

### 4. Type filtering
**Decision:** Filter Type1 by default.

- Default: only process Type1 transcripts (the baseline evaluation target)
- Override: `--types Type1,Type2` or `--types Type1,Type2,Adversarial`

---

*This design is scoped for baseline establishment. Histograms, failure bins, and production integration are deferred until baseline results inform priorities.*
