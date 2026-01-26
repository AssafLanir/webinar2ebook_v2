"""Corpus runner package for end-to-end baseline testing.

Provides:
- DraftGen adapter with Local + HTTP backends
- Centralized threshold definitions
- Structure and yield validators
- Report generation
- Draft caching

Usage:
    python -m corpus.runner --corpus backend/corpora/index.jsonl --out corpus_output/
"""

from .thresholds import Thresholds, DEFAULT_THRESHOLDS, DEFAULT_OUTLINE, DEFAULT_STYLE_CONFIG
from .draft_gen import (
    DraftGenRequest,
    DraftGenResult,
    DraftGenMeta,
    DraftGenBackend,
    LocalBackend,
    HTTPBackend,
    create_backend,
)
from .validators import (
    validate_structure,
    run_groundedness,
    compute_yield,
    make_gate_row,
    StructureResult,
    GroundednessResult,
    YieldResult,
    GateRow,
)
from .reporters import (
    write_work_unit,
    aggregate_corpus,
    write_corpus_report,
    write_corpus_summary,
)
from .cache import DraftCache, create_cache, compute_cache_key
from .runner import run_corpus, run_corpus_async

__all__ = [
    # Thresholds
    "Thresholds",
    "DEFAULT_THRESHOLDS",
    "DEFAULT_OUTLINE",
    "DEFAULT_STYLE_CONFIG",
    # DraftGen
    "DraftGenRequest",
    "DraftGenResult",
    "DraftGenMeta",
    "DraftGenBackend",
    "LocalBackend",
    "HTTPBackend",
    "create_backend",
    # Validators
    "validate_structure",
    "run_groundedness",
    "compute_yield",
    "make_gate_row",
    "StructureResult",
    "GroundednessResult",
    "YieldResult",
    "GateRow",
    # Reporters
    "write_work_unit",
    "aggregate_corpus",
    "write_corpus_report",
    "write_corpus_summary",
    # Cache
    "DraftCache",
    "create_cache",
    "compute_cache_key",
    # Runner
    "run_corpus",
    "run_corpus_async",
]
