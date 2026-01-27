# Webinar Transcript Corpus

This directory contains metadata and tooling for the webinar transcript evaluation corpus.

## Directory Structure

```
corpora/                        # Committed (public metadata only)
  README.md                     # This file
  index.jsonl                   # Metadata index (no transcript content)
  meta_template.yaml            # Template for new transcripts

corpora_private/                # NOT committed (gitignored)
  T0001_markmonitor_web3/
    meta.yaml                   # Full metadata
    raw.html                    # Original snapshot from source
    extracted.txt               # Plain text extraction (preserves structure)
    normalized.txt              # Pipeline-ready format
  T0002_hracuity_kpi/
    meta.yaml
    raw.srt
    extracted.txt
    normalized.txt
  ...
```

## Transcript Classification

| Type | Description | Example |
|------|-------------|---------|
| Type 1 | Raw transcript (verbatim, disfluencies preserved) | SRT captions, auto-generated |
| Type 2 | Lightly edited (cleaned but retains spoken structure) | Blog post transcripts |
| Adversarial | Auto-transcribed with errors (ASR artifacts) | Otter.ai unedited output |

## Normalization Rules

The `normalized.txt` file follows a canonical format for consistent pipeline input:

```
[HH:MM:SS] Speaker Name: Utterance text here...
[HH:MM:SS] Speaker Name: Next utterance...
```

### Format-specific normalization:

**SRT/VTT files:**
- Strip sequence numbers
- Merge wrapped lines into single utterances
- Convert timestamps to `[HH:MM:SS]` format
- Preserve speaker labels if present

**HTML transcripts:**
- Extract text from transcript container
- Parse speaker labels from formatting
- Infer timestamps from context if available

**PDF transcripts:**
- Extract text preserving paragraph structure
- Parse speaker turns from formatting patterns

## Bucket Categories

| Bucket | Category | Stressors |
|--------|----------|-----------|
| 1 | Demo/walkthrough | Product-focused, CTAs, live demo steps |
| 2 | Customer case study | External success stories, multi-speaker |
| 3 | Partner co-webinar | Two companies, shared attribution |
| 4 | Technical marketing | Jargon-heavy, DevOps/AI/Security |
| 5 | Compliance/trust | Regulatory terms, formal tone |
| 6 | Thought leadership | Exec trends, forward-looking |
| 7 | ROI/pricing focus | Financial metrics, value framing |
| 8 | CTA-heavy lead gen | Promotional, sign-up prompts |
| 9 | Messy ASR/captions | Transcription errors, [inaudible] |
| 10 | Q&A-heavy ending | Unstructured FAQ format |

## Usage

### Running quality harness on corpus

```bash
# Single transcript
python scripts/groundedness_eval.py \
  --draft output/T0001_draft.md \
  --transcript ../corpora_private/T0001_markmonitor_web3/normalized.txt

# Batch mode
python scripts/groundedness_eval.py \
  --draft_dir output/ \
  --transcript_dir ../corpora_private/ \
  --out reports/groundedness_batch.json
```

### Ingesting new transcripts

```bash
python scripts/ingest_transcript.py \
  --url "https://example.com/webinar-transcript" \
  --format html \
  --id T0011_newcompany_topic \
  --bucket 4
```

## Corpus Hygiene

- **retrieved_at**: Always record when you captured the raw snapshot
- **raw_snapshot_present**: Confirms you have the original (URLs may rot)
- **hashes**: SHA256 of raw and normalized for reproducibility
- **Never commit** `corpora_private/` to git (it's gitignored)

## Adding to index.jsonl

After ingesting, add metadata to `index.jsonl`:

```jsonl
{"id": "T0001_markmonitor_web3", "bucket": 3, "title": "Web3: Brand Security...", "classification": "Type2"}
```

This allows CI and harness scripts to enumerate the corpus without accessing private files.
