"""Draft caching for corpus runner.

Caches only generation output (draft.md + draft_meta.json + request.json).
Validators always re-run since their logic evolves.

Cache key: normalized_sha256 + content_mode + candidate_count + config_hash
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class CachedDraft:
    """Cached draft data."""
    draft_markdown: str
    draft_meta: dict
    request_json: dict


def compute_cache_key(
    normalized_sha256: str,
    content_mode: str,
    candidate_count: int,
    config_hash: str,
) -> str:
    """Compute cache key for draft lookup.

    Args:
        normalized_sha256: SHA256 hash of normalized transcript
        content_mode: Content mode used
        candidate_count: Number of candidates
        config_hash: Configuration hash

    Returns:
        Cache key string
    """
    return f"{normalized_sha256}_{content_mode}_c{candidate_count}_{config_hash}"


class DraftCache:
    """Draft-only cache for corpus runner.

    Cache structure:
        cache_dir/
            {cache_key}/
                draft.md
                draft_meta.json
                request.json
    """

    def __init__(self, cache_dir: Path):
        """Initialize cache.

        Args:
            cache_dir: Directory for cache storage
        """
        self.cache_dir = cache_dir
        self.enabled = True

    def disable(self) -> None:
        """Disable caching."""
        self.enabled = False

    def enable(self) -> None:
        """Enable caching."""
        self.enabled = True

    def _get_cache_path(self, cache_key: str) -> Path:
        """Get cache directory path for a key."""
        return self.cache_dir / cache_key

    def has(self, cache_key: str) -> bool:
        """Check if cache entry exists.

        Args:
            cache_key: Cache key to check

        Returns:
            True if cached draft exists
        """
        if not self.enabled:
            return False

        cache_path = self._get_cache_path(cache_key)
        draft_path = cache_path / "draft.md"
        meta_path = cache_path / "draft_meta.json"

        return draft_path.exists() and meta_path.exists()

    def load(self, cache_key: str) -> Optional[CachedDraft]:
        """Load cached draft.

        Args:
            cache_key: Cache key to load

        Returns:
            CachedDraft if found, None otherwise
        """
        if not self.enabled:
            return None

        cache_path = self._get_cache_path(cache_key)

        try:
            draft_path = cache_path / "draft.md"
            meta_path = cache_path / "draft_meta.json"
            request_path = cache_path / "request.json"

            if not draft_path.exists() or not meta_path.exists():
                return None

            draft_markdown = draft_path.read_text()
            draft_meta = json.loads(meta_path.read_text())

            # request.json is optional (older cache entries may not have it)
            request_json = {}
            if request_path.exists():
                request_json = json.loads(request_path.read_text())

            logger.info(f"Cache hit for {cache_key}")
            return CachedDraft(
                draft_markdown=draft_markdown,
                draft_meta=draft_meta,
                request_json=request_json,
            )

        except Exception as e:
            logger.warning(f"Failed to load cache for {cache_key}: {e}")
            return None

    def store(
        self,
        cache_key: str,
        draft_markdown: str,
        draft_meta: dict,
        request_json: dict,
    ) -> bool:
        """Store draft in cache.

        Args:
            cache_key: Cache key
            draft_markdown: Draft markdown content
            draft_meta: Draft metadata
            request_json: Request snapshot

        Returns:
            True if stored successfully
        """
        if not self.enabled:
            return False

        try:
            cache_path = self._get_cache_path(cache_key)
            cache_path.mkdir(parents=True, exist_ok=True)

            # Write draft
            draft_path = cache_path / "draft.md"
            draft_path.write_text(draft_markdown)

            # Write metadata
            meta_path = cache_path / "draft_meta.json"
            meta_path.write_text(json.dumps(draft_meta, indent=2))

            # Write request
            request_path = cache_path / "request.json"
            request_path.write_text(json.dumps(request_json, indent=2))

            logger.info(f"Cached draft for {cache_key}")
            return True

        except Exception as e:
            logger.warning(f"Failed to cache draft for {cache_key}: {e}")
            return False

    def clear(self, cache_key: Optional[str] = None) -> int:
        """Clear cache entries.

        Args:
            cache_key: Specific key to clear, or None to clear all

        Returns:
            Number of entries cleared
        """
        import shutil

        if cache_key:
            cache_path = self._get_cache_path(cache_key)
            if cache_path.exists():
                shutil.rmtree(cache_path)
                return 1
            return 0

        # Clear all
        count = 0
        if self.cache_dir.exists():
            for entry in self.cache_dir.iterdir():
                if entry.is_dir():
                    shutil.rmtree(entry)
                    count += 1

        return count

    def list_keys(self) -> list[str]:
        """List all cache keys.

        Returns:
            List of cache keys
        """
        if not self.cache_dir.exists():
            return []

        return [
            entry.name
            for entry in self.cache_dir.iterdir()
            if entry.is_dir() and (entry / "draft.md").exists()
        ]


def get_default_cache_dir() -> Path:
    """Get default cache directory.

    Returns:
        Path to default cache directory (backend/corpus_cache/)
    """
    # Relative to backend directory
    return Path(__file__).parent.parent.parent / "corpus_cache"


def create_cache(
    cache_dir: Optional[Path] = None,
    enabled: bool = True,
) -> DraftCache:
    """Create a draft cache instance.

    Args:
        cache_dir: Cache directory (default: backend/corpus_cache/)
        enabled: Whether caching is enabled

    Returns:
        DraftCache instance
    """
    if cache_dir is None:
        cache_dir = get_default_cache_dir()

    cache = DraftCache(cache_dir)

    if not enabled:
        cache.disable()

    return cache
