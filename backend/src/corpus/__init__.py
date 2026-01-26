"""Corpus runner package for end-to-end baseline testing.

Provides:
- DraftGen adapter with Local + HTTP backends
- Centralized threshold definitions
- Structure and yield validators
- Report generation

Usage:
    python -m corpus.runner --corpus backend/corpora/index.jsonl --out corpus_output/
"""

from .thresholds import Thresholds, DEFAULT_THRESHOLDS
from .draft_gen import (
    DraftGenRequest,
    DraftGenResult,
    DraftGenMeta,
    DraftGenBackend,
    LocalBackend,
    HTTPBackend,
)

__all__ = [
    "Thresholds",
    "DEFAULT_THRESHOLDS",
    "DraftGenRequest",
    "DraftGenResult",
    "DraftGenMeta",
    "DraftGenBackend",
    "LocalBackend",
    "HTTPBackend",
]
