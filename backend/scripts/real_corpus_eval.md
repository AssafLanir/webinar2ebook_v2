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

## Target Corpus Diversity (10 transcripts)

For meaningful threshold calibration, include these verticals:

| # | Type | What to look for |
|---|------|------------------|
| 1 | CTA-heavy marketing webinar | Heavy call-to-action, promotional language |
| 2 | Panel discussion | Multiple speakers, cross-talk |
| 3 | Q&A-heavy webinar | Short answers, speaker back-and-forth |
| 4 | Devtools webinar | Acronym soup (API, SDK, CI/CD, etc.) |
| 5 | Healthcare/finance compliance | Regulatory language (HIPAA, SOC2, etc.) |
| 6 | Training/education style | Instructional, step-by-step |
| 7 | Messy transcript | Disfluencies, poor diarization |
| 8 | Long-form interview | Extended monologues |
| 9 | Product demo | Feature walkthroughs, technical terms |
| 10 | Thought leadership | Abstract concepts, philosophical |

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
