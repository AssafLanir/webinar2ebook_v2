#!/usr/bin/env python3
"""End-to-end test: Run Sensory webinar through Ideas Edition pipeline.

Tests two presets:
- default_webinar_ebook_v1
- saas_marketing_ebook_v1

Verifies invariants:
- Has ## Chapter N: structure
- Each chapter has ### Key Excerpts and ### Core Claims
- No interview template leakage (*Format:* Interview, ### The Conversation, *Interviewer:*)
- Demo snippets don't become weird headers
"""

import json
import re
import sys
import time
from pathlib import Path

import requests

BASE_URL = "http://localhost:8000/api"

# Style presets (matching frontend/src/constants/stylePresets.ts)
PRESETS = {
    "default_webinar_ebook_v1": {
        "version": 1,
        "preset_id": "default_webinar_ebook_v1",
        "style": {
            "target_audience": "mixed",
            "reader_role": "general",
            "primary_goal": "enable_action",
            "reader_takeaway_style": "principles",
            "tone": "professional",
            "formality": "medium",
            "brand_voice": "neutral",
            "perspective": "you",
            "reading_level": "standard",
            "book_format": "guide",
            "content_mode": "essay",
            "chapter_count_target": 8,
            "chapter_length_target": "medium",
            "total_length_preset": "standard",
            "detail_level": "balanced",
            "include_summary_per_chapter": True,
            "include_key_takeaways": True,
            "include_action_steps": True,
            "include_examples": True,
            "faithfulness_level": "balanced",
            "allowed_extrapolation": "light",
            "source_policy": "transcript_plus_provided_resources",
            "citation_style": "inline_links",
            "avoid_hallucinations": True,
            "visual_density": "light",
            "preferred_visual_types": ["diagram", "table", "screenshot"],
            "visual_source_policy": "client_assets_only",
            "caption_style": "explanatory",
            "diagram_style": "simple",
            "resolve_repetitions": "reduce",
            "handle_q_and_a": "append_as_faq",
            "include_speaker_quotes": "sparingly",
            "output_format": "markdown",
        },
    },
    "saas_marketing_ebook_v1": {
        "version": 1,
        "preset_id": "saas_marketing_ebook_v1",
        "style": {
            "book_format": "ebook_marketing",
            "content_mode": "essay",
            "primary_goal": "persuade",
            "reader_role": "marketer",
            "target_audience": "mixed",
            "tone": "professional",
            "brand_voice": "premium",
            "perspective": "you",
            "chapter_count_target": 7,
            "chapter_length_target": "medium",
            "total_length_preset": "standard",
            "detail_level": "balanced",
            "include_checklists": True,
            "include_templates": True,
            "include_examples": True,
            "faithfulness_level": "balanced",
            "allowed_extrapolation": "light",
            "source_policy": "transcript_plus_provided_resources",
            "citation_style": "inline_links",
            "visual_density": "medium",
            "preferred_visual_types": ["diagram", "chart", "table", "screenshot"],
            "visual_source_policy": "client_assets_only",
            "caption_style": "explanatory",
            "handle_q_and_a": "weave_into_chapters",
            "output_format": "markdown",
        },
    },
}

# Sample outline for the Sensory webinar
SENSORY_OUTLINE = [
    {"id": "1", "title": "Introduction to Sensory", "level": 1, "notes": "Company overview and technology foundation"},
    {"id": "2", "title": "Voice Hub: Rapid Voice UI Development", "level": 1, "notes": "Creating wake words and custom commands"},
    {"id": "3", "title": "Sensory Cloud Platform", "level": 1, "notes": "Cloud-based voice AI services"},
    {"id": "4", "title": "Speech-to-Text Capabilities", "level": 1, "notes": "Accuracy, languages, and features"},
    {"id": "5", "title": "Face Biometrics and Liveness Detection", "level": 1, "notes": "Authentication and security"},
    {"id": "6", "title": "Voice Biometrics and Sound ID", "level": 1, "notes": "Voice identification and sound recognition"},
]


def load_transcript() -> str:
    """Load the Sensory webinar transcript."""
    transcript_path = Path("/Users/assaf/Downloads/build-quality-voicevision-ai-sols-w-sensory-cloud--draft--2026-01-25.txt")
    if not transcript_path.exists():
        raise FileNotFoundError(f"Transcript not found: {transcript_path}")
    return transcript_path.read_text()


def start_draft_generation(transcript: str, outline: list, style_config: dict) -> str:
    """Start draft generation and return job_id."""
    response = requests.post(
        f"{BASE_URL}/ai/draft/generate",
        json={
            "transcript": transcript,
            "outline": outline,
            "style_config": style_config,
            "candidate_count": 1,
        },
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    if "error" in data and data["error"]:
        raise RuntimeError(f"API error: {data['error']}")
    return data["data"]["job_id"]


def poll_until_complete(job_id: str, timeout_seconds: int = 600) -> dict:
    """Poll job status until complete or failed."""
    start_time = time.time()
    while True:
        if time.time() - start_time > timeout_seconds:
            raise TimeoutError(f"Job {job_id} did not complete within {timeout_seconds}s")

        response = requests.get(f"{BASE_URL}/ai/draft/status/{job_id}", timeout=30)
        response.raise_for_status()
        data = response.json()["data"]

        status = data["status"]
        progress = data.get("progress", {})
        current = progress.get("current_chapter", 0)
        total = progress.get("total_chapters", 0)

        print(f"  Status: {status} ({current}/{total} chapters)", end="\r")

        if status == "completed":
            print()
            return data
        elif status == "failed":
            print()
            raise RuntimeError(f"Job failed: {data.get('error', 'Unknown error')}")

        time.sleep(5)


def verify_invariants(markdown: str, preset_name: str) -> tuple[bool, list[str]]:
    """Verify Ideas Edition output invariants.

    Returns (passed, list of violations).
    """
    violations = []

    # 1. Has ## Chapter N: structure
    chapter_pattern = r'(?m)^## Chapter \d+:'
    chapters = re.findall(chapter_pattern, markdown)
    if not chapters:
        violations.append("FAIL: No '## Chapter N:' structure found")
    else:
        print(f"  ✓ Found {len(chapters)} chapters")

    # 2. Each chapter has ### Key Excerpts and ### Core Claims
    key_excerpts_count = markdown.count("### Key Excerpts")
    core_claims_count = markdown.count("### Core Claims")

    if key_excerpts_count == 0:
        violations.append("FAIL: No '### Key Excerpts' sections found")
    else:
        print(f"  ✓ Found {key_excerpts_count} Key Excerpts sections")

    if core_claims_count == 0:
        violations.append("FAIL: No '### Core Claims' sections found")
    else:
        print(f"  ✓ Found {core_claims_count} Core Claims sections")

    # 3. No interview template leakage
    if "*Format:* Interview" in markdown:
        violations.append("FAIL: Found '*Format:* Interview' (interview template leakage)")
    else:
        print("  ✓ No '*Format:* Interview' found")

    if "### The Conversation" in markdown:
        violations.append("FAIL: Found '### The Conversation' (interview template leakage)")
    else:
        print("  ✓ No '### The Conversation' found")

    if re.search(r'(?m)^\*Interviewer:\*', markdown):
        violations.append("FAIL: Found '*Interviewer:*' (interview template leakage)")
    else:
        print("  ✓ No '*Interviewer:*' found")

    # 4. Demo snippets don't become weird headers
    # Check for demo voice commands becoming headers
    weird_headers = re.findall(r'(?m)^###+ Voice Genie,', markdown)
    if weird_headers:
        violations.append(f"WARN: Found {len(weird_headers)} demo commands as headers")
    else:
        print("  ✓ No demo commands as weird headers")

    # Check for excessive H4+ headers (demo artifacts)
    h4_plus_headers = re.findall(r'(?m)^####+ ', markdown)
    if len(h4_plus_headers) > 10:
        violations.append(f"WARN: Found {len(h4_plus_headers)} H4+ headers (possible demo artifacts)")
    else:
        print(f"  ✓ H4+ header count acceptable ({len(h4_plus_headers)})")

    passed = len([v for v in violations if v.startswith("FAIL:")]) == 0
    return passed, violations


def run_test(preset_name: str, transcript: str) -> bool:
    """Run end-to-end test for a single preset."""
    print(f"\n{'='*60}")
    print(f"Testing: {preset_name}")
    print("="*60)

    style_config = PRESETS[preset_name]

    print("Starting draft generation...")
    try:
        job_id = start_draft_generation(transcript, SENSORY_OUTLINE, style_config)
        print(f"  Job ID: {job_id}")
    except Exception as e:
        print(f"  FAIL: Could not start generation: {e}")
        return False

    print("Polling for completion...")
    try:
        result = poll_until_complete(job_id)
    except Exception as e:
        print(f"  FAIL: {e}")
        return False

    markdown = result.get("draft_markdown", "")
    if not markdown:
        print("  FAIL: No draft_markdown in result")
        return False

    print(f"  Draft length: {len(markdown):,} characters")

    # Save draft for inspection
    output_path = Path(f"/tmp/sensory_draft_{preset_name}.md")
    output_path.write_text(markdown)
    print(f"  Saved to: {output_path}")

    print("\nVerifying invariants:")
    passed, violations = verify_invariants(markdown, preset_name)

    if violations:
        print("\nViolations:")
        for v in violations:
            print(f"  - {v}")

    return passed


def main():
    print("Loading Sensory webinar transcript...")
    try:
        transcript = load_transcript()
        print(f"  Loaded {len(transcript):,} characters")
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    results = {}

    for preset_name in ["default_webinar_ebook_v1", "saas_marketing_ebook_v1"]:
        results[preset_name] = run_test(preset_name, transcript)

    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)

    all_passed = True
    for preset_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {preset_name}: {status}")
        if not passed:
            all_passed = False

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
