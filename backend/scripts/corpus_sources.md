# Corpus Sources Registry

Track permitted transcript sources for the calibration corpus.

## Source Template

Copy this block for each transcript:

```
### [ID] Title
- **URL**:
- **Bucket**: (1-10, see real_corpus_eval.md)
- **Category**: (e.g., Demo, Case study, Technical marketing)
- **Permission**: (Customer-provided / Public with license / Internal evaluation only)
- **Stressors** (map to quality gates):
  - cta_density: Low / Med / High
  - acronym_density: Low / Med / High
  - speaker_count: 1 / 2 / 3+
  - qna_ratio: Low / Med / High
  - entity_load: Low / Med / High
- **Notes**:
- **Local file**: corpora/private/XX_short_name.md
```

---

## On-Distribution: B2B Marketing (8)

### 01 [Title TBD]
- **URL**:
- **Bucket**: 1 (Demo / walkthrough)
- **Category**: Demo / walkthrough
- **Permission**:
- **Stressors**:
  - cta_density:
  - acronym_density:
  - speaker_count:
  - qna_ratio:
  - entity_load:
- **Notes**:
- **Local file**: corpora/private/01_demo.md

### 02 [Title TBD]
- **URL**:
- **Bucket**: 2 (Customer case study)
- **Category**: Customer case study
- **Permission**:
- **Stressors**:
  - cta_density:
  - acronym_density:
  - speaker_count:
  - qna_ratio:
  - entity_load:
- **Notes**:
- **Local file**: corpora/private/02_case_study.md

### 03 [Title TBD]
- **URL**:
- **Bucket**: 3 (Partner co-webinar)
- **Category**: Partner co-webinar
- **Permission**:
- **Stressors**:
  - cta_density:
  - acronym_density:
  - speaker_count:
  - qna_ratio:
  - entity_load:
- **Notes**:
- **Local file**: corpora/private/03_partner.md

### 04 [Title TBD]
- **URL**:
- **Bucket**: 4 (Technical marketing)
- **Category**: Technical marketing (DevOps/Security/Data/AI)
- **Permission**:
- **Stressors**:
  - cta_density:
  - acronym_density:
  - speaker_count:
  - qna_ratio:
  - entity_load:
- **Notes**:
- **Local file**: corpora/private/04_technical.md

### 05 [Title TBD]
- **URL**:
- **Bucket**: 5 (Compliance / trust)
- **Category**: Compliance / trust (SOC2, HIPAA, GDPR, ISO)
- **Permission**:
- **Stressors**:
  - cta_density:
  - acronym_density:
  - speaker_count:
  - qna_ratio:
  - entity_load:
- **Notes**:
- **Local file**: corpora/private/05_compliance.md

### 06 [Title TBD]
- **URL**:
- **Bucket**: 6 (Thought leadership)
- **Category**: Thought leadership / POV
- **Permission**:
- **Stressors**:
  - cta_density:
  - acronym_density:
  - speaker_count:
  - qna_ratio:
  - entity_load:
- **Notes**:
- **Local file**: corpora/private/06_thought_leadership.md

### 07 [Title TBD]
- **URL**:
- **Bucket**: 7 (ROI / pricing)
- **Category**: ROI / pricing / business case
- **Permission**:
- **Stressors**:
  - cta_density:
  - acronym_density:
  - speaker_count:
  - qna_ratio:
  - entity_load:
- **Notes**:
- **Local file**: corpora/private/07_roi.md

### 08 [Title TBD]
- **URL**:
- **Bucket**: 8 (CTA-heavy lead gen)
- **Category**: CTA-heavy lead gen
- **Permission**:
- **Stressors**:
  - cta_density: High
  - acronym_density:
  - speaker_count:
  - qna_ratio:
  - entity_load:
- **Notes**:
- **Local file**: corpora/private/08_cta_heavy.md

---

## Adversarial-but-Realistic (2)

### 09 [Title TBD]
- **URL**:
- **Bucket**: 9 (Messy ASR)
- **Category**: Messy ASR / diarization
- **Permission**:
- **Stressors**:
  - cta_density:
  - acronym_density:
  - speaker_count:
  - qna_ratio:
  - entity_load:
- **Notes**: Intentionally poor transcript quality
- **Local file**: corpora/private/09_messy_asr.md

### 10 [Title TBD]
- **URL**:
- **Bucket**: 10 (Q&A-heavy)
- **Category**: Q&A-heavy ending
- **Permission**:
- **Stressors**:
  - cta_density:
  - acronym_density:
  - speaker_count:
  - qna_ratio: High
  - entity_load:
- **Notes**: Heavy audience Q&A section
- **Local file**: corpora/private/10_qa_heavy.md
