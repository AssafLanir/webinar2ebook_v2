#!/usr/bin/env python3
"""Transcript ingest script for corpus management.

Inputs: URL + format → Outputs: raw.*, extracted.txt, normalized.txt, meta.yaml, hashes

IMPORTANT: normalized.txt is a FROZEN INTERFACE for deterministic evaluation.
Never "improve" extracted/normalized text for readability—only deterministic transforms.
If anything is manually edited, run --update-hashes.

Usage:
    # Ingest from URL
    python scripts/ingest_transcript.py \
        --url "https://example.com/webinar-transcript" \
        --format html \
        --id T0011_company_topic \
        --bucket 4 \
        --title "Webinar Title" \
        --publisher "Company Name"

    # Ingest from local file
    python scripts/ingest_transcript.py \
        --file /path/to/transcript.srt \
        --format srt \
        --id T0012_company_topic \
        --bucket 2

    # Update hashes only (after manual edits)
    python scripts/ingest_transcript.py \
        --id T0001_markmonitor_web3 \
        --update-hashes

    # Strict mode (fail on low-quality transcripts)
    python scripts/ingest_transcript.py --url ... --strict
"""

import argparse
import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Optional

import yaml

# Base paths
SCRIPT_DIR = Path(__file__).parent
BACKEND_DIR = SCRIPT_DIR.parent
CORPORA_PRIVATE = BACKEND_DIR / "corpora_private"
CORPORA_PUBLIC = BACKEND_DIR / "corpora"
INDEX_FILE = CORPORA_PUBLIC / "index.jsonl"

# Format categories
TEXT_FORMATS = {"html", "srt", "vtt", "txt"}
BINARY_FORMATS = {"pdf"}

# Validation thresholds
MIN_WORDS = 1200
MIN_TIMESTAMP_LINES = 25
MIN_SPEAKER_TURNS = 40

# Regex patterns for normalization
TS_BRACKET = re.compile(r"^\[(\d{2}:\d{2}:\d{2})\]\s*(.*)$")
TS_SPEAKER = re.compile(r"^(\d{2}:\d{2}:\d{2})\s+(.+?):\s*(.+)$")
SPEAKER_ONLY = re.compile(r"^([A-Z][\w\s.\-']{1,60}):\s*(.+)$")


# =============================================================================
# File I/O Helpers
# =============================================================================


def write_text_utf8(path: Path, content: str) -> None:
    """Write text file with normalized line endings (LF only)."""
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    path.write_text(normalized, encoding="utf-8")


def write_bytes(path: Path, content: bytes) -> None:
    """Write binary file."""
    path.write_bytes(content)


def sha256_file(path: Path) -> str:
    """Compute SHA256 hash of file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch_url(url: str, format_type: str) -> tuple[Optional[str], Optional[bytes]]:
    """Fetch URL content, returning (text, None) or (None, bytes) based on format.

    Fixes: PDF URLs must be fetched as bytes, not decoded as UTF-8.
    """
    import urllib.request

    req = urllib.request.Request(
        url,
        headers={"User-Agent": "webinar2ebook-corpus-ingest/1.0"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read()

    if format_type.lower() in BINARY_FORMATS:
        return None, data
    else:
        return data.decode("utf-8", errors="replace"), None


# =============================================================================
# Text Extraction
# =============================================================================


def extract_text_html(html_content: str) -> str:
    """Extract text from HTML transcript.

    Targets transcript container to avoid nav/CTA boilerplate pollution.
    Heuristic: prefer elements with transcript-related id/class, else article/main.
    """
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_content, "html.parser")

        # Remove junk tags first
        for tag in soup(["script", "style", "nav", "header", "footer",
                         "form", "svg", "button", "aside", "noscript"]):
            tag.decompose()

        # Try to find transcript container by id/class
        transcript_selectors = [
            "[id*='transcript']",
            "[class*='transcript']",
            "[id*='webinar-transcript']",
            "[class*='webinar-transcript']",
            "[id*='caption']",
            "[class*='caption']",
            "[id*='recording-transcript']",
            "[class*='event-transcript']",
        ]

        container = None
        for selector in transcript_selectors:
            found = soup.select_one(selector)
            if found:
                container = found
                break

        # Fallback to article or main
        if not container:
            container = soup.find("article") or soup.find("main") or soup.body or soup

        # Get text
        text = container.get_text(separator="\n") if container else ""

        # Clean up whitespace
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        return "\n".join(lines)

    except ImportError:
        # Fallback: strip HTML tags with regex (less accurate)
        text = re.sub(r"<[^>]+>", "", html_content)
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        return "\n".join(lines)


def extract_text_srt(srt_content: str) -> str:
    """Extract text from SRT subtitle file.

    SRT format: sequence numbers, timestamps with comma (HH:MM:SS,mmm --> HH:MM:SS,mmm), text.
    Preserves timestamps in [HH:MM:SS] format.
    """
    lines = []
    current_time = None
    current_text = []

    for raw in srt_content.replace("\r\n", "\n").split("\n"):
        line = raw.strip()

        # Skip sequence numbers
        if re.match(r"^\d+$", line):
            continue

        # Parse timestamp line (SRT uses comma for milliseconds)
        m = re.match(r"(\d{2}:\d{2}:\d{2}),\d+\s*-->\s*(\d{2}:\d{2}:\d{2}),\d+", line)
        if m:
            # Save previous block
            if current_time and current_text:
                lines.append(f"[{current_time}] " + " ".join(current_text).strip())
            current_time = m.group(1)
            current_text = []
            continue

        # Accumulate text
        if line and current_time:
            current_text.append(line)

    # Don't forget last block
    if current_time and current_text:
        lines.append(f"[{current_time}] " + " ".join(current_text).strip())

    return "\n".join(lines)


def extract_text_vtt(vtt_content: str) -> str:
    """Extract text from WebVTT subtitle file.

    VTT format differs from SRT:
    - Uses period for milliseconds (HH:MM:SS.mmm)
    - Has WEBVTT header
    - May contain NOTE blocks and cue settings

    Skips NOTE blocks and cue settings lines.
    """
    content = vtt_content.replace("\r\n", "\n")
    out = []
    current_time = None
    current_text = []
    in_note = False

    for raw in content.split("\n"):
        line = raw.strip()

        if not line:
            # End of cue block
            if current_time and current_text:
                out.append(f"[{current_time}] " + " ".join(current_text).strip())
            current_time, current_text = None, []
            in_note = False
            continue

        # Skip WEBVTT header
        if line.startswith("WEBVTT"):
            continue

        # Skip NOTE blocks
        if line.startswith("NOTE"):
            in_note = True
            continue
        if in_note:
            continue

        # Parse timestamp line (VTT uses period for milliseconds)
        m = re.match(r"(\d{2}:\d{2}:\d{2})\.\d+\s*-->\s*(\d{2}:\d{2}:\d{2})\.\d+", line)
        if m:
            current_time = m.group(1)
            continue

        # Skip cue settings lines (contain --> but aren't timestamps we want)
        if "-->" in line:
            continue

        # Accumulate text
        if current_time:
            current_text.append(line)

    # Don't forget last block
    if current_time and current_text:
        out.append(f"[{current_time}] " + " ".join(current_text).strip())

    return "\n".join(out)


def extract_text_pdf(pdf_path: Path) -> str:
    """Extract text from PDF file.

    Note: PDF extraction may include artifacts:
    - Hyphenation at line breaks
    - Headers/footers repeated per page
    - Broken speaker turns across pages

    These should be cleaned in normalized.txt, not here.
    """
    try:
        import pypdf
        reader = pypdf.PdfReader(str(pdf_path))
        text_parts = []
        for page in reader.pages:
            text_parts.append(page.extract_text() or "")
        return "\n\n".join(text_parts)
    except ImportError:
        print("WARNING: pypdf not installed. Cannot extract PDF text.", file=sys.stderr)
        print("Install with: pip install pypdf", file=sys.stderr)
        return ""


# =============================================================================
# Normalization
# =============================================================================


def normalize_transcript(extracted: str) -> str:
    """Normalize extracted text to canonical format.

    Target format:
    [HH:MM:SS] Speaker Name: Utterance text...

    IMPORTANT: This is a FROZEN INTERFACE for deterministic evaluation.
    Do not change normalization rules casually.

    Handles:
    - "[HH:MM:SS] text" → adds "Speaker Unknown:" if no speaker
    - "HH:MM:SS Speaker: text" → converts to bracket format
    - "Speaker: text" → adds placeholder [00:00:00] timestamp
    """
    norm = []

    for raw in extracted.replace("\r\n", "\n").split("\n"):
        line = raw.strip()
        if not line:
            continue

        # Pattern: "00:00:00 Speaker: text" (no brackets, common in HTML transcripts)
        m = TS_SPEAKER.match(line)
        if m:
            t, spk, txt = m.group(1), m.group(2).strip(), m.group(3).strip()
            norm.append(f"[{t}] {spk}: {txt}")
            continue

        # Pattern: "[00:00:00] text" or "[00:00:00] Speaker: text" (SRT/VTT extracted)
        m = TS_BRACKET.match(line)
        if m:
            t, rest = m.group(1), m.group(2).strip()
            if SPEAKER_ONLY.match(rest):
                # Already has speaker label
                norm.append(f"[{t}] {rest}")
            else:
                # No speaker, add placeholder
                norm.append(f"[{t}] Speaker Unknown: {rest}")
            continue

        # Pattern: "Speaker: text" (no timestamp, common in cleaned transcripts)
        m = SPEAKER_ONLY.match(line)
        if m:
            spk, txt = m.group(1).strip(), m.group(2).strip()
            norm.append(f"[00:00:00] {spk}: {txt}")
            continue

        # Plain text line (keep as-is, may be prose intro or headers)
        norm.append(line)

    return "\n".join(norm)


# =============================================================================
# Validation
# =============================================================================


def compute_stats_and_validation(normalized: str) -> tuple[dict, dict]:
    """Compute transcript statistics and validate transcriptness.

    Prevents "recap pages" or summaries from silently entering the corpus.

    Thresholds:
    - approx_words >= 1200
    - timestamp_lines >= 25 OR speaker_turns >= 40

    Returns:
        (stats_dict, validation_dict)
    """
    words = count_words(normalized)
    lines = [l for l in normalized.split("\n") if l.strip()]

    # Count lines with timestamps
    ts_lines = sum(1 for l in lines if re.match(r"^\[\d{2}:\d{2}:\d{2}\]", l))

    # Count speaker turns (timestamp + speaker label)
    speaker_turns = sum(
        1 for l in lines
        if re.match(r"^\[\d{2}:\d{2}:\d{2}\]\s+[^:]{2,80}:\s+\S", l)
    )

    # Extract unique speakers
    speakers = set()
    for l in lines:
        m = re.match(r"^\[\d{2}:\d{2}:\d{2}\]\s+([^:]{2,80}):", l)
        if m:
            spk = m.group(1).strip()
            if spk != "Speaker Unknown":
                speakers.add(spk)

    # Detect Q&A section
    has_qa = bool(re.search(
        r"\bQ&A\b|\bquestions?\b.*\banswers?\b|\bchat\b|\braise your hand\b",
        normalized,
        re.I
    ))

    # Detect recap markers (bad sign)
    recap_markers = len(re.findall(
        r"(?i)\b(key takeaways?|summary|highlights?|recap|overview)\b",
        normalized
    ))

    # Transcriptness validation
    ok_structure = (ts_lines >= MIN_TIMESTAMP_LINES) or (speaker_turns >= MIN_SPEAKER_TURNS)
    ok_length = words >= MIN_WORDS
    suspicious_recap = recap_markers >= 5 and speaker_turns < 20

    if suspicious_recap:
        status = "FAIL"
        reasons = [f"appears_to_be_recap (markers={recap_markers}, turns={speaker_turns})"]
    elif ok_structure and ok_length:
        status = "PASS"
        reasons = []
    elif ok_length:
        status = "WARN"
        reasons = [f"low_structure (ts_lines={ts_lines}, speaker_turns={speaker_turns})"]
    else:
        status = "FAIL"
        reasons = [f"low_word_count ({words} < {MIN_WORDS})"]
        if not ok_structure:
            reasons.append(f"low_structure (ts_lines={ts_lines}, speaker_turns={speaker_turns})")

    stats = {
        "approx_words": words,
        "approx_minutes": None,  # Fill manually if known
        "speaker_count": len(speakers) if speakers else None,
        "has_qa_section": has_qa,
        "timestamp_line_count": ts_lines,
        "speaker_turn_line_count": speaker_turns,
    }

    validation = {
        "status": status,
        "reasons": reasons,
    }

    return stats, validation


def count_words(text: str) -> int:
    """Count approximate words in text."""
    return len(text.split())


# =============================================================================
# Metadata
# =============================================================================


def create_meta_yaml(
    transcript_id: str,
    bucket: int,
    title: str,
    publisher: str,
    source_url: str,
    format_type: str,
    classification: str,
    hashes: dict,
    stats: dict,
    validation: dict,
    ingest_notes: Optional[list] = None,
) -> dict:
    """Create metadata dictionary."""
    return {
        "id": transcript_id,
        "bucket": bucket,
        "title": title,
        "publisher": publisher,
        "source_url": source_url,
        "retrieved_at": date.today().isoformat(),
        "raw_snapshot_present": True,
        "format": format_type.upper(),
        "classification": classification,
        "access_friction": "none",
        "license_note": "no explicit reuse license found",
        "ingest_notes": ingest_notes or [],
        "hashes": hashes,
        "stats": stats,
        "validation": validation,
        "stressors": [],
    }


def update_index(transcript_id: str, meta: dict) -> None:
    """Update or add entry in index.jsonl.

    Uses sort_keys=True and ensure_ascii=False for stable diffs.
    """
    entries = []
    found = False

    if INDEX_FILE.exists():
        with open(INDEX_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                if entry.get("id") == transcript_id:
                    # Update existing entry
                    entry.update({
                        "bucket": meta["bucket"],
                        "title": meta["title"],
                        "publisher": meta["publisher"],
                        "format": meta["format"],
                        "classification": meta["classification"],
                        "retrieved_at": meta["retrieved_at"],
                        "approx_words": meta["stats"]["approx_words"],
                        "validation_status": meta["validation"]["status"],
                    })
                    found = True
                entries.append(entry)

    if not found:
        entries.append({
            "id": transcript_id,
            "bucket": meta["bucket"],
            "title": meta["title"],
            "publisher": meta["publisher"],
            "format": meta["format"],
            "classification": meta["classification"],
            "retrieved_at": meta["retrieved_at"],
            "approx_words": meta["stats"]["approx_words"],
            "validation_status": meta["validation"]["status"],
        })

    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        for entry in entries:
            # sort_keys=True for stable diffs, ensure_ascii=False for readability
            f.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")


# =============================================================================
# Ingest Pipeline
# =============================================================================


def ingest_transcript(
    transcript_id: str,
    bucket: int,
    title: str,
    publisher: str,
    source_url: str,
    format_type: str,
    classification: str = "Type1",
    raw_content: Optional[str] = None,
    raw_bytes: Optional[bytes] = None,
    raw_path: Optional[Path] = None,
    strict: bool = False,
) -> tuple[Path, dict]:
    """Ingest a transcript into the corpus.

    Args:
        transcript_id: Unique ID (e.g., T0001_company_topic)
        bucket: Bucket category (1-10)
        title: Webinar title
        publisher: Company name
        source_url: Original URL
        format_type: html, srt, vtt, pdf, txt
        classification: Type1, Type2, or Adversarial
        raw_content: Raw content as string (for HTML, SRT, VTT, TXT)
        raw_bytes: Raw content as bytes (for PDF)
        raw_path: Path to raw file (for local files)
        strict: If True, fail on WARN/FAIL validation

    Returns:
        (transcript_dir, meta_dict)
    """
    # Create directory
    transcript_dir = CORPORA_PRIVATE / transcript_id
    transcript_dir.mkdir(parents=True, exist_ok=True)

    # Determine raw file extension
    ext_map = {
        "html": ".html",
        "srt": ".srt",
        "vtt": ".vtt",
        "pdf": ".pdf",
        "txt": ".txt",
    }
    raw_ext = ext_map.get(format_type.lower(), ".txt")
    raw_file = transcript_dir / f"raw{raw_ext}"

    # Write raw file
    if raw_bytes:
        write_bytes(raw_file, raw_bytes)
    elif raw_content:
        write_text_utf8(raw_file, raw_content)
    elif raw_path and raw_path.exists():
        import shutil
        shutil.copy(raw_path, raw_file)
    else:
        print(f"ERROR: No raw content provided for {transcript_id}", file=sys.stderr)
        sys.exit(1)

    # Extract text
    extracted_file = transcript_dir / "extracted.txt"
    if format_type.lower() == "html":
        extracted = extract_text_html(raw_file.read_text(encoding="utf-8", errors="replace"))
    elif format_type.lower() == "srt":
        extracted = extract_text_srt(raw_file.read_text(encoding="utf-8", errors="replace"))
    elif format_type.lower() == "vtt":
        extracted = extract_text_vtt(raw_file.read_text(encoding="utf-8", errors="replace"))
    elif format_type.lower() == "pdf":
        extracted = extract_text_pdf(raw_file)
    else:
        extracted = raw_file.read_text(encoding="utf-8", errors="replace")

    write_text_utf8(extracted_file, extracted)

    # Normalize
    normalized_file = transcript_dir / "normalized.txt"
    normalized = normalize_transcript(extracted)
    write_text_utf8(normalized_file, normalized)

    # Compute hashes
    hashes = {
        "raw_sha256": sha256_file(raw_file),
        "extracted_sha256": sha256_file(extracted_file),
        "normalized_sha256": sha256_file(normalized_file),
    }

    # Compute stats and validation
    stats, validation = compute_stats_and_validation(normalized)

    # Ingest notes based on format
    ingest_notes = []
    if format_type.lower() == "srt":
        ingest_notes.append("SRT: timestamps preserved in [HH:MM:SS] format")
    elif format_type.lower() == "vtt":
        ingest_notes.append("VTT: NOTE blocks stripped, timestamps in [HH:MM:SS] format")
    elif format_type.lower() == "pdf":
        ingest_notes.append("PDF: may contain hyphenation/header/footer artifacts")

    # Create metadata
    meta = create_meta_yaml(
        transcript_id=transcript_id,
        bucket=bucket,
        title=title,
        publisher=publisher,
        source_url=source_url,
        format_type=format_type,
        classification=classification,
        hashes=hashes,
        stats=stats,
        validation=validation,
        ingest_notes=ingest_notes,
    )

    # Write meta.yaml
    meta_file = transcript_dir / "meta.yaml"
    with open(meta_file, "w", encoding="utf-8") as f:
        yaml.dump(meta, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    # Update index
    update_index(transcript_id, meta)

    # Report
    status_symbol = {"PASS": "✓", "WARN": "⚠", "FAIL": "✗"}.get(validation["status"], "?")
    print(f"{status_symbol} Ingested: {transcript_id}")
    print(f"  Directory: {transcript_dir}")
    print(f"  Words: {stats['approx_words']}")
    print(f"  Validation: {validation['status']}")
    if validation["reasons"]:
        for reason in validation["reasons"]:
            print(f"    - {reason}")
    print(f"  Raw hash: {hashes['raw_sha256'][:16]}...")

    # Strict mode check
    if strict and validation["status"] in ("WARN", "FAIL"):
        print(f"\nERROR: Strict mode enabled, validation={validation['status']}", file=sys.stderr)
        print("This may be a recap page, not a transcript. Use a backup source.", file=sys.stderr)
        sys.exit(2)

    return transcript_dir, meta


def update_hashes(transcript_id: str) -> None:
    """Update hashes in meta.yaml after manual edits."""
    transcript_dir = CORPORA_PRIVATE / transcript_id
    meta_file = transcript_dir / "meta.yaml"

    if not meta_file.exists():
        print(f"ERROR: {meta_file} not found", file=sys.stderr)
        sys.exit(1)

    with open(meta_file, encoding="utf-8") as f:
        meta = yaml.safe_load(f)

    # Recompute hashes
    raw_files = list(transcript_dir.glob("raw.*"))
    if raw_files:
        meta["hashes"]["raw_sha256"] = sha256_file(raw_files[0])

    extracted_file = transcript_dir / "extracted.txt"
    if extracted_file.exists():
        meta["hashes"]["extracted_sha256"] = sha256_file(extracted_file)

    normalized_file = transcript_dir / "normalized.txt"
    if normalized_file.exists():
        meta["hashes"]["normalized_sha256"] = sha256_file(normalized_file)

        # Also recompute stats and validation
        normalized = normalized_file.read_text(encoding="utf-8")
        stats, validation = compute_stats_and_validation(normalized)
        meta["stats"] = stats
        meta["validation"] = validation

    # Write back
    with open(meta_file, "w", encoding="utf-8") as f:
        yaml.dump(meta, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    # Update index
    update_index(transcript_id, meta)

    print(f"✓ Updated hashes for {transcript_id}")
    print(f"  Validation: {meta['validation']['status']}")


def main():
    parser = argparse.ArgumentParser(
        description="Ingest transcripts into evaluation corpus"
    )

    parser.add_argument("--id", required=True, help="Transcript ID (e.g., T0011_company_topic)")
    parser.add_argument("--url", help="Source URL to fetch")
    parser.add_argument("--file", type=Path, help="Local file to ingest")
    parser.add_argument("--format", choices=["html", "srt", "vtt", "pdf", "txt"], help="Transcript format")
    parser.add_argument("--bucket", type=int, choices=range(1, 11), metavar="1-10", help="Bucket category (1-10)")
    parser.add_argument("--title", help="Webinar title")
    parser.add_argument("--publisher", help="Company name")
    parser.add_argument("--classification", default="Type1", choices=["Type1", "Type2", "Adversarial"])
    parser.add_argument("--strict", action="store_true", help="Fail on WARN/FAIL validation (for building eval set)")
    parser.add_argument("--update-hashes", action="store_true", help="Only update hashes in meta.yaml")

    args = parser.parse_args()

    if args.update_hashes:
        update_hashes(args.id)
        return

    # Validate required args for ingest
    if not args.format:
        print("ERROR: --format is required for ingest", file=sys.stderr)
        sys.exit(1)
    if not args.bucket:
        print("ERROR: --bucket is required for ingest", file=sys.stderr)
        sys.exit(1)
    if not args.title:
        print("ERROR: --title is required for ingest", file=sys.stderr)
        sys.exit(1)
    if not args.publisher:
        print("ERROR: --publisher is required for ingest", file=sys.stderr)
        sys.exit(1)

    # Get raw content
    raw_content = None
    raw_bytes = None
    raw_path = None
    source_url = args.url or ""

    if args.file:
        raw_path = args.file
        if not raw_path.exists():
            print(f"ERROR: File not found: {raw_path}", file=sys.stderr)
            sys.exit(1)
    elif args.url:
        print(f"Fetching: {args.url}")
        try:
            raw_content, raw_bytes = fetch_url(args.url, args.format)
        except Exception as e:
            print(f"ERROR: Failed to fetch URL: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print("ERROR: Either --url or --file is required", file=sys.stderr)
        sys.exit(1)

    ingest_transcript(
        transcript_id=args.id,
        bucket=args.bucket,
        title=args.title,
        publisher=args.publisher,
        source_url=source_url,
        format_type=args.format,
        classification=args.classification,
        raw_content=raw_content,
        raw_bytes=raw_bytes,
        raw_path=raw_path,
        strict=args.strict,
    )


if __name__ == "__main__":
    main()
