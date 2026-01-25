#!/usr/bin/env python3
"""Transcript ingest script for corpus management.

Inputs: URL + format → Outputs: raw.*, extracted.txt, normalized.txt, meta.yaml, hashes

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


def sha256_file(path: Path) -> str:
    """Compute SHA256 hash of file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def extract_text_html(html_content: str) -> str:
    """Extract text from HTML transcript.

    Attempts to find transcript container and extract speaker turns.
    """
    # Try to import BeautifulSoup, fall back to regex
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_content, "html.parser")

        # Remove script and style elements
        for element in soup(["script", "style", "nav", "header", "footer"]):
            element.decompose()

        # Get text
        text = soup.get_text(separator="\n")

        # Clean up whitespace
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        return "\n".join(lines)
    except ImportError:
        # Fallback: strip HTML tags with regex
        text = re.sub(r"<[^>]+>", "", html_content)
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        return "\n".join(lines)


def extract_text_srt(srt_content: str) -> str:
    """Extract text from SRT subtitle file.

    Preserves timestamps in extracted form.
    """
    lines = []
    current_time = None
    current_text = []

    for line in srt_content.split("\n"):
        line = line.strip()

        # Skip sequence numbers
        if re.match(r"^\d+$", line):
            continue

        # Parse timestamp line
        time_match = re.match(r"(\d{2}:\d{2}:\d{2}),\d+ --> ", line)
        if time_match:
            # Save previous block
            if current_time and current_text:
                text = " ".join(current_text)
                lines.append(f"[{current_time}] {text}")
            current_time = time_match.group(1)
            current_text = []
            continue

        # Accumulate text
        if line and current_time:
            current_text.append(line)

    # Don't forget last block
    if current_time and current_text:
        text = " ".join(current_text)
        lines.append(f"[{current_time}] {text}")

    return "\n".join(lines)


def extract_text_pdf(pdf_path: Path) -> str:
    """Extract text from PDF file."""
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


def normalize_transcript(extracted: str) -> str:
    """Normalize extracted text to canonical format.

    Target format:
    [HH:MM:SS] Speaker Name: Utterance text...
    """
    lines = []

    for line in extracted.split("\n"):
        line = line.strip()
        if not line:
            continue

        # Already has timestamp prefix
        if re.match(r"\[\d{2}:\d{2}:\d{2}\]", line):
            lines.append(line)
            continue

        # Has speaker label (Name: text)
        speaker_match = re.match(r"^([A-Z][a-zA-Z\s]+):\s*(.+)$", line)
        if speaker_match:
            speaker = speaker_match.group(1).strip()
            text = speaker_match.group(2).strip()
            lines.append(f"[00:00:00] {speaker}: {text}")
            continue

        # Plain text line
        lines.append(line)

    return "\n".join(lines)


def count_words(text: str) -> int:
    """Count approximate words in text."""
    return len(text.split())


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
        "stressors": [],
    }


def update_index(transcript_id: str, meta: dict) -> None:
    """Update or add entry in index.jsonl."""
    entries = []
    found = False

    if INDEX_FILE.exists():
        with open(INDEX_FILE) as f:
            for line in f:
                entry = json.loads(line.strip())
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
        })

    with open(INDEX_FILE, "w") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")


def ingest_transcript(
    transcript_id: str,
    bucket: int,
    title: str,
    publisher: str,
    source_url: str,
    format_type: str,
    classification: str = "Type1",
    raw_content: Optional[str] = None,
    raw_path: Optional[Path] = None,
) -> Path:
    """Ingest a transcript into the corpus.

    Args:
        transcript_id: Unique ID (e.g., T0001_company_topic)
        bucket: Bucket category (1-10)
        title: Webinar title
        publisher: Company name
        source_url: Original URL
        format_type: html, srt, vtt, pdf, txt
        classification: Type1, Type2, or Adversarial
        raw_content: Raw content as string (for HTML, SRT, TXT)
        raw_path: Path to raw file (for PDF or local files)

    Returns:
        Path to created transcript directory
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

    # Write or copy raw file
    if raw_content:
        raw_file.write_text(raw_content)
    elif raw_path and raw_path.exists():
        import shutil
        shutil.copy(raw_path, raw_file)
    else:
        print(f"ERROR: No raw content provided for {transcript_id}", file=sys.stderr)
        return transcript_dir

    # Extract text
    extracted_file = transcript_dir / "extracted.txt"
    if format_type.lower() == "html":
        extracted = extract_text_html(raw_file.read_text())
    elif format_type.lower() in ("srt", "vtt"):
        extracted = extract_text_srt(raw_file.read_text())
    elif format_type.lower() == "pdf":
        extracted = extract_text_pdf(raw_file)
    else:
        extracted = raw_file.read_text()

    extracted_file.write_text(extracted)

    # Normalize
    normalized_file = transcript_dir / "normalized.txt"
    normalized = normalize_transcript(extracted)
    normalized_file.write_text(normalized)

    # Compute hashes
    hashes = {
        "raw_sha256": sha256_file(raw_file),
        "extracted_sha256": sha256_file(extracted_file),
        "normalized_sha256": sha256_file(normalized_file),
    }

    # Compute stats
    stats = {
        "approx_words": count_words(normalized),
        "approx_minutes": None,  # Can be filled in manually
        "speaker_count": None,
        "has_qa_section": False,
    }

    # Ingest notes based on format
    ingest_notes = []
    if format_type.lower() in ("srt", "vtt"):
        ingest_notes.append("Timestamps preserved in extracted.txt")
        ingest_notes.append("Normalized to [HH:MM:SS] format")

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
        ingest_notes=ingest_notes,
    )

    # Write meta.yaml
    meta_file = transcript_dir / "meta.yaml"
    with open(meta_file, "w") as f:
        yaml.dump(meta, f, default_flow_style=False, sort_keys=False)

    # Update index
    update_index(transcript_id, meta)

    print(f"Ingested: {transcript_id}")
    print(f"  Directory: {transcript_dir}")
    print(f"  Words: {stats['approx_words']}")
    print(f"  Raw hash: {hashes['raw_sha256'][:16]}...")

    return transcript_dir


def update_hashes(transcript_id: str) -> None:
    """Update hashes in meta.yaml after manual edits."""
    transcript_dir = CORPORA_PRIVATE / transcript_id
    meta_file = transcript_dir / "meta.yaml"

    if not meta_file.exists():
        print(f"ERROR: {meta_file} not found", file=sys.stderr)
        return

    with open(meta_file) as f:
        meta = yaml.safe_load(f)

    # Recompute hashes
    for filename in ["raw", "extracted.txt", "normalized.txt"]:
        if filename == "raw":
            # Find raw file with any extension
            raw_files = list(transcript_dir.glob("raw.*"))
            if raw_files:
                meta["hashes"]["raw_sha256"] = sha256_file(raw_files[0])
        else:
            file_path = transcript_dir / filename
            if file_path.exists():
                key = filename.replace(".txt", "_sha256")
                meta["hashes"][key] = sha256_file(file_path)

    # Update word count
    normalized_file = transcript_dir / "normalized.txt"
    if normalized_file.exists():
        meta["stats"]["approx_words"] = count_words(normalized_file.read_text())

    # Write back
    with open(meta_file, "w") as f:
        yaml.dump(meta, f, default_flow_style=False, sort_keys=False)

    print(f"Updated hashes for {transcript_id}")


def main():
    parser = argparse.ArgumentParser(
        description="Ingest transcripts into evaluation corpus"
    )

    parser.add_argument("--id", required=True, help="Transcript ID (e.g., T0011_company_topic)")
    parser.add_argument("--url", help="Source URL to fetch")
    parser.add_argument("--file", type=Path, help="Local file to ingest")
    parser.add_argument("--format", choices=["html", "srt", "vtt", "pdf", "txt"], help="Transcript format")
    parser.add_argument("--bucket", type=int, choices=range(1, 11), help="Bucket category (1-10)")
    parser.add_argument("--title", help="Webinar title")
    parser.add_argument("--publisher", help="Company name")
    parser.add_argument("--classification", default="Type1", choices=["Type1", "Type2", "Adversarial"])
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
    raw_path = None
    source_url = args.url or ""

    if args.file:
        raw_path = args.file
        if not raw_path.exists():
            print(f"ERROR: File not found: {raw_path}", file=sys.stderr)
            sys.exit(1)
    elif args.url:
        # Fetch URL
        try:
            import urllib.request
            print(f"Fetching: {args.url}")
            with urllib.request.urlopen(args.url, timeout=30) as response:
                raw_content = response.read().decode("utf-8", errors="replace")
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
        raw_path=raw_path,
    )


if __name__ == "__main__":
    main()
