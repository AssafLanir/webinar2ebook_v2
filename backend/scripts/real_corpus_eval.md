# Real Corpus Evaluation Guide

Run the quality harness on private transcripts to validate thresholds before production rollout.

## Quick Start

```bash
cd backend

# 1. Place draft files in the private corpus folder
#    (This folder is git-ignored - never commit customer data)
cp /path/to/your/drafts/*.md corpora/private/

# 2. Run with dynamic name policy enabled
DYNAMIC_NAME_POLICY_ENABLED=true python scripts/batch_eval.py \
  --input_dir corpora/private/ \
  --out corpora/private/report.json

# 3. For CI-style pass/fail check
DYNAMIC_NAME_POLICY_ENABLED=true python scripts/batch_eval.py \
  --input_dir corpora/private/ \
  --ci
```

## Target Corpus: B2B Marketing Focus (10 transcripts)

**Distribution**: 80% on-distribution (B2B marketing) + 20% adversarial-but-realistic

### On-Distribution: B2B Marketing Webinars (8)

| # | Bucket | Key Stressors |
|---|--------|---------------|
| 1 | Product launch / feature announcement | High CTA density, product names |
| 2 | Thought leadership / trends | Abstract concepts, industry jargon |
| 3 | Customer success / case study | Company names, metrics, testimonials |
| 4 | Demo / walkthrough | Technical terms, step-by-step narration |
| 5 | Panel discussion | 3+ speakers, cross-talk, interruptions |
| 6 | Expert interview | 2 speakers, long monologues |
| 7 | How-to / tutorial | Instructional, imperative voice |
| 8 | Industry report / research | Data-heavy, citations, acronyms |

### Adversarial-but-Realistic (2)

| # | Bucket | Key Stressors |
|---|--------|---------------|
| 9 | Messy ASR | Disfluencies, filler words, poor diarization |
| 10 | Q&A-heavy | Short answers, audience questions, speaker ping-pong |

### Stressor Tracking Template

For each transcript, record:

| Field | Description |
|-------|-------------|
| **Category** | Which bucket (1-10) |
| **CTA density** | Low / Medium / High |
| **Acronym density** | Low / Medium / High |
| **# Speakers** | Count |
| **Q&A %** | Estimated % of content that's Q&A |
| **ASR quality** | Clean / Some noise / Messy |

## Reading the Results

### Results Table
```
FILE                    VERDICT DROP%   FALLBACK%  W/CH   CAUSES
marketing_webinar.md    WARN    35.2%      0.0%   95 drop_ratio_high:35%
panel_discussion.md     FAIL    62.1%     33.3%   42 drop_ratio_critical:62%
...
```

### Key Metrics

| Metric | Healthy Range | Warning | Critical |
|--------|---------------|---------|----------|
| Drop ratio | < 25% | 25-40% | > 40% |
| Fallback ratio | < 10% | 10-25% | > 50% |
| Prose words/chapter | > 120 | 50-120 | < 50 |

### Prose Distribution (for threshold tuning)
- **P10**: 10th percentile - catches weak chapters
- **Median**: Typical chapter quality

## Threshold Tuning Checklist

After running on 10 real transcripts:

1. **If ≥ 8/10 PASS**: Current thresholds are good
2. **If 5-7/10 PASS**: Review top failure causes, consider:
   - Adjusting soft thresholds
   - Moving from min to P10-based verdict
3. **If < 5/10 PASS**: Systematic issue - investigate:
   - Are drops legitimate (names in prose)?
   - Is entity allowlist missing common patterns?
   - Is transcript quality the root cause?

## Output Files

All outputs go to `corpora/private/` (git-ignored):

```
corpora/private/
├── transcript_1.md      # Input drafts
├── transcript_2.md
├── ...
├── report.json          # Full evaluation report
└── summary.md           # Your analysis notes (optional)
```

## Next Steps After Validation

Once ≥ 8/10 transcripts pass (or fail for explainable preflight reasons):

1. Document threshold decisions in this file
2. Consider enabling `DYNAMIC_NAME_POLICY_ENABLED=true` in staging
3. Proceed to Q&A Edition wiring
