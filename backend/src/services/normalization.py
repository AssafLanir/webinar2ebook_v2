"""Normalization helpers for backward-compatible data shapes.

Ensures legacy data formats are converted to canonical shapes on load.
"""

from typing import Any

from src.models import (
    StyleConfig,
    StyleConfigEnvelope,
    STYLE_CONFIG_VERSION,
    VisualPlan,
)


def normalize_style_config(data: dict | None) -> StyleConfigEnvelope | None:
    """Normalize styleConfig to canonical StyleConfigEnvelope.

    Handles:
    - None/missing → returns None (caller decides default)
    - StyleConfigEnvelope shape → validates and returns
    - LegacyStyleConfig shape → migrates to envelope
    - Unknown dict → wraps in envelope with defaults

    Args:
        data: Raw styleConfig from database

    Returns:
        StyleConfigEnvelope or None
    """
    if data is None:
        return None

    # Check if already in envelope format (has 'style' key)
    if "style" in data and isinstance(data.get("style"), dict):
        # Already an envelope - validate and return
        return StyleConfigEnvelope.model_validate(data)

    # Check for legacy format (has old keys like 'audience', 'tone', 'depth', 'targetPages')
    legacy_keys = {"audience", "tone", "depth", "targetPages"}
    if any(key in data for key in legacy_keys):
        # Migrate legacy format
        style_fields = {}

        # Map legacy fields to new StyleConfig fields where applicable
        if data.get("audience"):
            # Map old audience values to new target_audience
            audience_map = {
                "general": "mixed",
                "technical": "intermediate",
                "executive": "advanced",
                "academic": "advanced",
            }
            style_fields["target_audience"] = audience_map.get(
                data["audience"], "mixed"
            )

        if data.get("tone"):
            # Map old tone values to new tone (some overlap)
            tone_map = {
                "formal": "professional",
                "conversational": "conversational",
                "instructional": "professional",
                "persuasive": "authoritative",
            }
            style_fields["tone"] = tone_map.get(data["tone"], "professional")

        if data.get("depth"):
            # Map depth to chapter_length_target
            depth_map = {
                "overview": "short",
                "moderate": "medium",
                "comprehensive": "long",
            }
            style_fields["chapter_length_target"] = depth_map.get(
                data["depth"], "medium"
            )

        if data.get("targetPages"):
            # Estimate chapter count from target pages (rough: ~10 pages per chapter)
            pages = data["targetPages"]
            chapter_count = max(3, min(20, pages // 10))
            style_fields["chapter_count_target"] = chapter_count

        return StyleConfigEnvelope(
            version=STYLE_CONFIG_VERSION,
            preset_id="legacy_migrated",
            style=StyleConfig(**style_fields) if style_fields else StyleConfig(),
        )

    # Unknown format - treat as partial StyleConfig fields
    try:
        style = StyleConfig.model_validate(data)
        return StyleConfigEnvelope(
            version=STYLE_CONFIG_VERSION,
            preset_id="unknown_migrated",
            style=style,
        )
    except Exception:
        # Can't parse - return None and let caller use default
        return None


def normalize_visual_plan(data: dict | None) -> VisualPlan:
    """Normalize visualPlan to canonical VisualPlan.

    Handles:
    - None/missing → returns empty VisualPlan
    - Valid VisualPlan shape → validates and returns
    - Partial data → fills missing fields with defaults
    - Missing assignments field → treated as [] (Spec 005 compatibility)

    Args:
        data: Raw visualPlan from database

    Returns:
        VisualPlan (never None)
    """
    if data is None:
        return VisualPlan(opportunities=[], assets=[], assignments=[])

    # Ensure assignments field exists (legacy projects won't have it)
    if isinstance(data, dict) and "assignments" not in data:
        data = {**data, "assignments": []}

    try:
        return VisualPlan.model_validate(data)
    except Exception:
        # Can't parse - return empty
        return VisualPlan(opportunities=[], assets=[], assignments=[])


def normalize_project_data(doc: dict) -> dict:
    """Normalize a project document from the database.

    Applies all normalization rules:
    - styleConfig → StyleConfigEnvelope
    - visualPlan → VisualPlan (initialized if missing)

    Args:
        doc: Raw document from MongoDB

    Returns:
        Document with normalized fields
    """
    # Normalize styleConfig
    raw_style = doc.get("styleConfig")
    normalized_style = normalize_style_config(raw_style)
    doc["styleConfig"] = normalized_style.model_dump() if normalized_style else None

    # Normalize visualPlan (always present, even if empty)
    raw_visual_plan = doc.get("visualPlan")
    normalized_visual_plan = normalize_visual_plan(raw_visual_plan)
    doc["visualPlan"] = normalized_visual_plan.model_dump()

    return doc
