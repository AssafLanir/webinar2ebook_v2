# Ingesting Public Transcripts

How to convert YouTube/podcast transcripts into draft .md files for the quality harness.

## Overview

The batch evaluator expects **draft files** (markdown with `## Chapter N:` structure), not raw transcripts. For calibration purposes, we need to:

1. Get raw transcript from source
2. Convert to draft format (or run through the actual pipeline)
3. Place in `corpora/private/`

## Option A: Use Actual Pipeline (Recommended)

Run the real Ideas Edition pipeline to generate drafts from transcripts.

```bash
# If you have the full pipeline working:
# 1. Create a project with the transcript
# 2. Generate Ideas Edition draft
# 3. Export/copy the draft to corpora/private/
```

This tests the full system, not just the quality gates.

## Option B: Manual Draft Creation (For Quick Testing)

If you just want to test the harness on existing prose:

### Step 1: Get Raw Transcript

**YouTube:**
- Use browser extension (e.g., "YouTube Transcript")
- Or: YouTube → ... → Show Transcript → Copy

**Podcast:**
- Check show notes for transcript
- Or: Use Whisper/other ASR

### Step 2: Convert to Draft Format

Wrap the transcript in chapter structure:

```markdown
## Chapter 1: [Topic from first segment]

[Prose paragraph 1 - narrative summary of content]

[Prose paragraph 2 - key insights]

### Key Excerpts

> "[Actual quote from transcript]"
> — Speaker Name (ROLE)

### Core Claims

- **[Claim title]**: "[Supporting quote]"

## Chapter 2: [Next topic]

[Continue pattern...]
```

### Step 3: Save to Private Corpus

```bash
# Save with numbered prefix matching corpus_sources.md
cp draft.md backend/corpora/private/01_product_launch.md
```

## Naming Convention

Use format: `XX_short_name.md`

| # | Bucket | Filename |
|---|--------|----------|
| 01 | Product launch | 01_product_launch.md |
| 02 | Thought leadership | 02_thought_leadership.md |
| 03 | Case study | 03_case_study.md |
| 04 | Demo | 04_demo.md |
| 05 | Panel | 05_panel.md |
| 06 | Interview | 06_interview.md |
| 07 | Tutorial | 07_tutorial.md |
| 08 | Research | 08_research.md |
| 09 | Messy ASR | 09_messy_asr.md |
| 10 | Q&A-heavy | 10_qa_heavy.md |

## Minimum Requirements

Each draft must have:
- At least 2 chapters (`## Chapter N:`)
- Prose paragraphs (narrative text before Key Excerpts)
- `### Key Excerpts` section with at least 1 quote
- `### Core Claims` section (can use fallback placeholder)

## Running the Harness

After placing drafts:

```bash
cd backend

DYNAMIC_NAME_POLICY_ENABLED=true python scripts/batch_eval.py \
  --input_dir corpora/private/ \
  --out corpora/private/report.json
```

## Checklist Before Running

- [ ] All 10 drafts in `corpora/private/`
- [ ] Each draft has chapter structure
- [ ] Each draft has Key Excerpts and Core Claims sections
- [ ] `corpus_sources.md` updated with source info
- [ ] Stressor fields filled in for each source
