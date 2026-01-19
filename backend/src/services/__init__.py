"""Services package for backend business logic."""

from . import canonical_service
from . import draft_service
from . import evidence_service

from .whitelist_service import (
    canonicalize_transcript,
    build_quote_whitelist,
    compute_chapter_coverage,
    select_deterministic_excerpts,
    enforce_quote_whitelist,
    enforce_core_claims_guest_only,
    strip_llm_blockquotes,
    format_excerpts_markdown,
    fix_quote_artifacts,
    detect_verbatim_leakage,
    EnforcementResult,
)

__all__ = [
    "canonical_service",
    "draft_service",
    "evidence_service",
    # Whitelist service functions
    "canonicalize_transcript",
    "build_quote_whitelist",
    "compute_chapter_coverage",
    "select_deterministic_excerpts",
    "enforce_quote_whitelist",
    "enforce_core_claims_guest_only",
    "strip_llm_blockquotes",
    "format_excerpts_markdown",
    "fix_quote_artifacts",
    "detect_verbatim_leakage",
    "EnforcementResult",
]
