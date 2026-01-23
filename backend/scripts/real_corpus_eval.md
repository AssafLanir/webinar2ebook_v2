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

| # | Bucket | Gate Stress Points |
|---|--------|-------------------|
| 1 | Demo / walkthrough | Product names, technical terms, step-by-step narration |
| 2 | Customer case study | Customer + vendor names, metrics, testimonials |
| 3 | Partner co-webinar | Two company names, cross-promotion, shared CTAs |
| 4 | Technical marketing | Acronym soup (DevOps/Security/Data/AI), product names |
| 5 | Compliance / trust | SOC2, HIPAA, GDPR, ISO mentions, regulatory language |
| 6 | Thought leadership / POV | Exec narrative, abstract concepts, speaker framing |
| 7 | ROI / pricing / business case | Numbers, metrics, value framing, competitor mentions |
| 8 | CTA-heavy lead gen | Book demo, next steps, links, promotional language |

### Adversarial-but-Realistic (2)

| # | Bucket | Gate Stress Points |
|---|--------|-------------------|
| 9 | Messy ASR / diarization | Disfluencies, filler words, speaker overlap, poor segmentation |
| 10 | Q&A-heavy ending | Short answers, audience questions, speaker ping-pong |

### Stressor Tracking (maps to quality gates)

For each transcript, record these fields that correlate with gate behavior:

| Field | Values | Relevant Gate |
|-------|--------|---------------|
| **cta_density** | Low / Med / High | Meta-discourse, CTA removal |
| **acronym_density** | Low / Med / High | Entity allowlist |
| **speaker_count** | 1 / 2 / 3+ | Person blacklist, speaker framing |
| **qna_ratio** | Low / Med / High | Prose thinness, fallback usage |
| **entity_load** | Low / Med / High | Entity allowlist (brands/products per minute) |

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
