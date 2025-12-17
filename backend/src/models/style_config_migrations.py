"""Style config migrations.

Only needed once you persist StyleConfigEnvelope across time and evolve the schema.
"""

from __future__ import annotations

from typing import Any, Dict

from .style_config import STYLE_CONFIG_VERSION


def migrate_style_config_envelope(payload: Dict[str, Any]) -> Dict[str, Any]:
    version = int(payload.get("version", 1))

    # Example future migrations:
    # if version == 1:
    #     style = payload.setdefault("style", {})
    #     style.setdefault("language", "en")
    #     payload["version"] = 2
    #     version = 2

    if version > STYLE_CONFIG_VERSION:
        payload["version"] = STYLE_CONFIG_VERSION

    return payload
