"""Corpus runner core orchestration.

Main entry point for running end-to-end baseline testing across the corpus.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .draft_gen import (
    DraftGenRequest,
    DraftGenResult,
    DraftGenMeta,
    DraftGenBackend,
    LocalBackend,
    HTTPBackend,
    create_backend,
    compute_transcript_hash,
    compute_config_hash,
    generate_run_id,
    get_git_commit,
)
from .validators import (
    validate_structure,
    run_groundedness,
    compute_yield,
    make_gate_row,
    make_failure_gate_row,
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
from .thresholds import (
    Thresholds,
    DEFAULT_THRESHOLDS,
    DEFAULT_OUTLINE,
    DEFAULT_STYLE_CONFIG,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Corpus Loading
# =============================================================================


def load_corpus_manifest(manifest_path: Path) -> list[dict]:
    """Load corpus manifest from index.jsonl."""
    entries = []
    with open(manifest_path) as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def filter_entries(
    entries: list[dict],
    types: list[str],
    only: Optional[list[str]] = None,
    skip: Optional[list[str]] = None,
) -> list[dict]:
    """Filter corpus entries by type and ID."""
    filtered = []
    for entry in entries:
        # Type filter
        if entry.get("classification") not in types:
            continue

        # ID filters
        entry_id = entry.get("id", "")
        if only and entry_id not in only:
            continue
        if skip and entry_id in skip:
            continue

        filtered.append(entry)

    return filtered


def find_transcript_path(entry: dict, corpora_private_dir: Path) -> Optional[Path]:
    """Find transcript file path for a corpus entry."""
    entry_id = entry.get("id", "")

    for filename in ["normalized.txt", "extracted.txt"]:
        for subdir in corpora_private_dir.iterdir():
            if subdir.is_dir() and subdir.name.startswith(entry_id):
                transcript_path = subdir / filename
                if transcript_path.exists():
                    return transcript_path

    return None


def load_transcript(transcript_path: Path) -> str:
    """Load transcript text from path."""
    return transcript_path.read_text()


# =============================================================================
# Single Transcript Processing
# =============================================================================


@dataclass
class TranscriptRunConfig:
    """Configuration for running a single transcript."""
    content_mode: str
    candidate_count: int
    require_preflight_pass: bool
    timeout_s: int
    thresholds: Thresholds


async def process_transcript(
    entry: dict,
    backend: DraftGenBackend,
    corpora_private_dir: Path,
    output_dir: Path,
    config: TranscriptRunConfig,
    cache: Optional[DraftCache] = None,
    force_regen: bool = False,
) -> GateRow:
    """Process a single transcript through the full pipeline.

    Steps:
    1. Load transcript
    2. Check cache (if enabled)
    3. Generate draft (or use cached)
    4. Run validators (always)
    5. Write work unit files
    6. Return gate row

    Args:
        entry: Corpus entry dict
        backend: Draft generation backend
        corpora_private_dir: Path to corpora_private directory
        output_dir: Output directory
        config: Run configuration
        cache: Optional draft cache
        force_regen: Force regeneration even if cached

    Returns:
        GateRow with verdict and metrics
    """
    entry_id = entry.get("id", "")
    logger.info(f"Processing {entry_id}...")

    # Find and load transcript
    transcript_path = find_transcript_path(entry, corpora_private_dir)
    if not transcript_path:
        logger.error(f"Could not find transcript for {entry_id}")
        return make_failure_gate_row(
            run_id=f"{entry_id}__error",
            transcript_id=entry_id,
            candidate_index=0,
            content_mode=config.content_mode,
            error="Transcript file not found",
            error_code="TRANSCRIPT_NOT_FOUND",
        )

    transcript = load_transcript(transcript_path)
    transcript_hash = compute_transcript_hash(transcript)

    # Build style config
    style_config = DEFAULT_STYLE_CONFIG.copy()
    style_config["style"] = style_config.get("style", {}).copy()
    style_config["style"]["content_mode"] = config.content_mode

    # Compute config hash for caching
    # Use backend's config values
    prompt_version = getattr(backend, "prompt_version", "ideas_v3")
    model = getattr(backend, "model", "gpt-4o-mini")
    temperature = getattr(backend, "temperature", 0.7)
    routing_version = getattr(backend, "routing_version", "2026-01-26")

    config_hash = compute_config_hash(prompt_version, model, temperature, routing_version)

    # Build request
    request = DraftGenRequest(
        transcript_id=entry_id,
        transcript=transcript,
        transcript_path=str(transcript_path),
        outline=DEFAULT_OUTLINE.copy(),
        style_config=style_config,
        candidate_count=config.candidate_count,
        require_preflight_pass=config.require_preflight_pass,
    )

    # Check cache
    cache_key = compute_cache_key(
        transcript_hash,
        config.content_mode,
        config.candidate_count,
        config_hash,
    )

    result: Optional[DraftGenResult] = None

    if cache and not force_regen:
        cached = cache.load(cache_key)
        if cached:
            logger.info(f"Using cached draft for {entry_id}")
            # Reconstruct result from cache
            result = DraftGenResult(
                success=True,
                draft_markdown=cached.draft_markdown,
                draft_plan=None,  # Not cached
                meta=DraftGenMeta(
                    run_id=generate_run_id(entry_id, config.content_mode, 0, config_hash),
                    transcript_id=entry_id,
                    candidate_index=0,
                    transcript_path=str(transcript_path),
                    draft_path="",  # Will be set by reporter
                    git_commit=cached.draft_meta.get("git_commit", "cached"),
                    config_hash=config_hash,
                    prompt_version=prompt_version,
                    model=model,
                    temperature=temperature,
                    routing_version=routing_version,
                    backend="cached",
                    content_mode=config.content_mode,
                    seed=None,
                    normalized_sha256=transcript_hash,
                    generation_time_s=0.0,  # Cached
                ),
            )

    # Generate if not cached
    if result is None:
        result = await backend.generate(request, config.timeout_s)

        # Cache successful results
        if result.success and cache and result.meta:
            cache.store(
                cache_key,
                result.draft_markdown or "",
                result.meta.to_dict(),
                request.to_request_json(),
            )

    # Handle generation failure
    if not result.success:
        logger.error(f"Generation failed for {entry_id}: {result.error}")
        gate_row = make_failure_gate_row(
            run_id=generate_run_id(entry_id, config.content_mode, 0, config_hash),
            transcript_id=entry_id,
            candidate_index=0,
            content_mode=config.content_mode,
            error=result.error or "Unknown error",
            error_code=result.error_code or "GENERATION_FAILED",
        )

        # Still write work unit (for failure analysis)
        write_work_unit(
            out_dir=output_dir,
            transcript_id=entry_id,
            request=request,
            result=result,
            structure=None,
            groundedness=None,
            yield_result=None,
            gate_row=gate_row,
        )

        return gate_row

    # Run validators (always, even for cached drafts)
    draft_md = result.draft_markdown or ""

    # Structure validation
    structure = validate_structure(draft_md)
    logger.debug(f"{entry_id} structure: {structure.verdict}")

    # Groundedness validation
    groundedness = run_groundedness(draft_md, transcript, strict=True)
    logger.debug(f"{entry_id} groundedness: {groundedness.overall_verdict}")

    # Yield metrics
    yield_result = compute_yield(draft_md, transcript, structure, groundedness)
    logger.debug(f"{entry_id} yield: {yield_result.prose_word_count} prose words")

    # Compute gate row
    run_id = result.meta.run_id if result.meta else generate_run_id(
        entry_id, config.content_mode, 0, config_hash
    )

    gate_row = make_gate_row(
        run_id=run_id,
        transcript_id=entry_id,
        candidate_index=0,
        content_mode=config.content_mode,
        structure=structure,
        groundedness=groundedness,
        yield_result=yield_result,
        thresholds=config.thresholds,
    )

    # Write work unit
    write_work_unit(
        out_dir=output_dir,
        transcript_id=entry_id,
        request=request,
        result=result,
        structure=structure,
        groundedness=groundedness,
        yield_result=yield_result,
        gate_row=gate_row,
    )

    logger.info(f"Completed {entry_id}: {gate_row.verdict}")
    return gate_row


# =============================================================================
# Corpus Runner
# =============================================================================


async def run_corpus_async(
    manifest_path: Path,
    output_dir: Path,
    corpora_private_dir: Optional[Path] = None,
    types: Optional[list[str]] = None,
    only: Optional[list[str]] = None,
    skip: Optional[list[str]] = None,
    workers: int = 1,
    backend_type: str = "local",
    base_url: str = "http://localhost:8000/api",
    content_mode: str = "essay",
    candidate_count: int = 1,
    require_preflight_pass: bool = True,
    timeout_s: int = 600,
    cache_enabled: bool = True,
    force_regen: bool = False,
    thresholds: Optional[Thresholds] = None,
) -> dict:
    """Run corpus evaluation asynchronously.

    Args:
        manifest_path: Path to index.jsonl
        output_dir: Output directory
        corpora_private_dir: Path to corpora_private (default: sibling of manifest)
        types: Transcript types to include (default: ["Type1"])
        only: Specific transcript IDs to include
        skip: Transcript IDs to exclude
        workers: Number of parallel workers (1 = sequential)
        backend_type: "local" or "http"
        base_url: API base URL for http backend
        content_mode: Content mode to use
        candidate_count: Number of candidates
        require_preflight_pass: Fail on preflight failures
        timeout_s: Per-transcript timeout
        cache_enabled: Enable draft caching
        force_regen: Force regeneration (ignore cache)
        thresholds: Threshold configuration

    Returns:
        Corpus report dictionary
    """
    if types is None:
        types = ["Type1"]

    if thresholds is None:
        thresholds = DEFAULT_THRESHOLDS

    if corpora_private_dir is None:
        corpora_private_dir = manifest_path.parent.parent / "corpora_private"

    # Load and filter corpus
    entries = load_corpus_manifest(manifest_path)
    filtered = filter_entries(entries, types, only, skip)

    if not filtered:
        logger.warning("No transcripts match the filter criteria")
        return {"error": "No transcripts match filter criteria"}

    logger.info(f"Processing {len(filtered)} transcripts (types={types})")

    # Create backend
    backend = create_backend(backend_type, base_url)

    # Create cache
    cache = create_cache(enabled=cache_enabled) if cache_enabled else None

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Build config
    config = TranscriptRunConfig(
        content_mode=content_mode,
        candidate_count=candidate_count,
        require_preflight_pass=require_preflight_pass,
        timeout_s=timeout_s,
        thresholds=thresholds,
    )

    # Process transcripts
    gate_rows: list[GateRow] = []

    if workers == 1:
        # Sequential processing
        for entry in filtered:
            gate_row = await process_transcript(
                entry=entry,
                backend=backend,
                corpora_private_dir=corpora_private_dir,
                output_dir=output_dir,
                config=config,
                cache=cache,
                force_regen=force_regen,
            )
            gate_rows.append(gate_row)
    else:
        # Parallel processing with semaphore
        semaphore = asyncio.Semaphore(workers)

        async def process_with_semaphore(entry: dict) -> GateRow:
            async with semaphore:
                return await process_transcript(
                    entry=entry,
                    backend=backend,
                    corpora_private_dir=corpora_private_dir,
                    output_dir=output_dir,
                    config=config,
                    cache=cache,
                    force_regen=force_regen,
                )

        tasks = [process_with_semaphore(entry) for entry in filtered]
        gate_rows = await asyncio.gather(*tasks)

    # Aggregate results
    git_commit = get_git_commit()
    prompt_version = getattr(backend, "prompt_version", "ideas_v3")
    model = getattr(backend, "model", "gpt-4o-mini")
    temperature = getattr(backend, "temperature", 0.7)
    routing_version = getattr(backend, "routing_version", "2026-01-26")
    config_hash = compute_config_hash(prompt_version, model, temperature, routing_version)

    report = aggregate_corpus(
        gate_rows=gate_rows,
        git_commit=git_commit,
        config_hash=config_hash,
        prompt_version=prompt_version,
        content_mode=content_mode,
        require_preflight_pass=require_preflight_pass,
        thresholds=thresholds,
    )

    # Write reports
    write_corpus_report(output_dir, report)
    write_corpus_summary(output_dir, report)

    return report


def run_corpus(
    manifest_path: Path,
    output_dir: Path,
    **kwargs,
) -> dict:
    """Run corpus evaluation (blocking).

    See run_corpus_async for full argument list.

    Returns:
        Corpus report dictionary
    """
    return asyncio.run(run_corpus_async(manifest_path, output_dir, **kwargs))
