"""Centralized threshold definitions for corpus runner.

Single source of truth for all validation thresholds and rollout gate criteria.
"""

from dataclasses import dataclass


@dataclass
class Thresholds:
    """Threshold configuration for corpus evaluation.

    Per-transcript WARN thresholds determine individual transcript verdicts.
    Corpus-level gate criteria determine overall rollout readiness.
    """

    # =========================================================================
    # Per-transcript WARN thresholds
    # =========================================================================

    # Fallback usage: WARN if more than this fraction of chapters use fallback
    warn_fallback_ratio: float = 0.25

    # Prose word count: WARN if p10 prose words per chapter below this
    warn_min_p10_prose: int = 60

    # Excerpt provenance: WARN if any excerpts missing (< 1.0)
    warn_excerpt_provenance: float = 1.0

    # Claim provenance: WARN if any claim evidence missing (< 1.0)
    warn_claim_provenance: float = 1.0

    # =========================================================================
    # Corpus-level rollout gate criteria
    # =========================================================================

    # Maximum FAIL verdicts allowed (0 = no failures permitted)
    gate_max_fail: int = 0

    # Maximum WARN verdicts allowed
    gate_max_warn: int = 2

    # Maximum average fallback rate across corpus
    gate_max_fallback_rate: float = 0.25

    # Minimum p10 prose words across corpus
    gate_min_p10_prose: int = 60

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "warn_fallback_ratio": self.warn_fallback_ratio,
            "warn_min_p10_prose": self.warn_min_p10_prose,
            "warn_excerpt_provenance": self.warn_excerpt_provenance,
            "warn_claim_provenance": self.warn_claim_provenance,
            "gate_max_fail": self.gate_max_fail,
            "gate_max_warn": self.gate_max_warn,
            "gate_max_fallback_rate": self.gate_max_fallback_rate,
            "gate_min_p10_prose": self.gate_min_p10_prose,
        }


# Default thresholds for production use
DEFAULT_THRESHOLDS = Thresholds()


# Default outline for baseline isolation (deterministic, no LLM)
DEFAULT_OUTLINE = [
    {"id": "1", "title": "Introduction", "level": 1},
    {"id": "2", "title": "Main Content", "level": 1},
    {"id": "3", "title": "Conclusion", "level": 1},
]


# Default style config for Ideas Edition baseline
DEFAULT_STYLE_CONFIG = {
    "version": 1,
    "preset_id": "corpus_baseline_v1",
    "style": {
        "content_mode": "essay",
        "book_format": "guide",
        "target_audience": "mixed",
        "reader_role": "general",
        "primary_goal": "enable_action",
        "tone": "professional",
        "formality": "medium",
        "brand_voice": "neutral",
        "perspective": "you",
        "reading_level": "standard",
        "chapter_count_target": 3,
        "chapter_length_target": "medium",
        "total_length_preset": "standard",
        "detail_level": "balanced",
        "include_summary_per_chapter": False,
        "include_key_takeaways": False,
        "include_action_steps": False,
        "include_examples": True,
        "faithfulness_level": "balanced",
        "allowed_extrapolation": "light",
        "source_policy": "transcript_plus_provided_resources",
        "citation_style": "inline_links",
        "avoid_hallucinations": True,
        "visual_density": "none",
        "output_format": "markdown",
    },
}
