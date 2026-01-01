# Data Model: Draft Quality System

**Feature**: 008-draft-quality
**Date**: 2026-01-01

## Entities

### QAReport

The main quality assessment report for a draft.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | string | Yes | Unique report ID (UUID) |
| project_id | string | Yes | Reference to project |
| draft_hash | string | Yes | Hash of draft text for cache invalidation |
| overall_score | integer | Yes | Overall quality score (1-100) |
| rubric_scores | RubricScores | Yes | Breakdown by category |
| issues | QAIssue[] | Yes | List of detected issues |
| generated_at | datetime | Yes | When report was generated |
| analysis_duration_ms | integer | Yes | How long analysis took |
| version | string | Yes | Schema version for migrations |

### RubricScores

Breakdown of quality scores by category.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| structure | integer | Yes | Heading hierarchy, chapter balance (1-100) |
| clarity | integer | Yes | Sentence length, passive voice, jargon (1-100) |
| faithfulness | integer | Yes | Alignment with source material (1-100) |
| repetition | integer | Yes | Inverse of repetition (100 = no repetition) |
| completeness | integer | Yes | Coverage of source topics (1-100) |

**Score Interpretation**:
- 90-100: Excellent
- 70-89: Good
- 50-69: Needs improvement
- 1-49: Poor

### QAIssue

A single detected quality issue.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | string | Yes | Unique issue ID |
| severity | enum | Yes | critical / warning / info |
| issue_type | string | Yes | Category (repetition, structure, clarity, faithfulness) |
| chapter_index | integer | No | Which chapter (0-based), null if global |
| heading | string | No | Heading where issue occurs |
| location | string | No | Text excerpt showing location |
| message | string | Yes | Human-readable description |
| suggestion | string | No | Actionable fix suggestion |
| metadata | object | No | Additional data (e.g., repeated phrase, count) |

**Severity Definitions**:
- **critical**: Likely hallucination, factual error, broken structure
- **warning**: Repetition, long paragraphs, clarity issues
- **info**: Minor suggestions, style improvements

### EditorPassResult (P2)

Result of an improvement pass.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | string | Yes | Unique result ID |
| project_id | string | Yes | Reference to project |
| original_draft_hash | string | Yes | Hash of draft before edit |
| improved_draft | string | Yes | Full improved text |
| changes_summary | string | Yes | Human-readable summary of changes |
| issues_addressed | string[] | Yes | IDs of issues that were fixed |
| faithfulness_preserved | boolean | Yes | Whether faithfulness check passed |
| created_at | datetime | Yes | When edit was made |

### GoldenProject (Fixtures)

Configuration for regression testing.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | string | Yes | Project ID in database |
| name | string | Yes | Human-readable name |
| baseline_scores | RubricScores | Yes | Expected scores |
| expected_issues | IssueRanges | Yes | Expected issue counts |
| last_validated | datetime | Yes | Last time baseline was verified |

## Relationships

```
Project (existing)
├── qaReport: QAReport (embedded, 1:1)
│   ├── rubric_scores: RubricScores (embedded)
│   └── issues: QAIssue[] (embedded array)
└── editorPassHistory: EditorPassResult[] (embedded array, P2)
```

## Validation Rules

### QAReport
- overall_score: 1-100
- rubric_scores: all fields 1-100
- issues: can be empty array
- draft_hash: non-empty string

### QAIssue
- severity: must be one of [critical, warning, info]
- issue_type: must be one of [repetition, structure, clarity, faithfulness, completeness]
- message: non-empty string, max 500 chars
- suggestion: max 500 chars if present

### EditorPassResult
- faithfulness_preserved: must be true for success
- improved_draft: non-empty string
- changes_summary: non-empty string

## State Transitions

### QA Report Lifecycle

```
[No Report] → analyze() → [Report Generated]
[Report Generated] → draft_changed() → [Stale]
[Stale] → re-analyze() → [Report Generated]
```

### Editor Pass Lifecycle

```
[Issues Exist] → run_improve() → [Processing]
[Processing] → success → [Improved] (new draft saved)
[Processing] → faithfulness_failed → [Rejected] (original preserved)
[Processing] → timeout → [Failed] (original preserved)
```

## MongoDB Schema Update

Add to existing Project document:

```python
class Project(BaseModel):
    # ... existing fields ...

    # New fields for QA
    qaReport: Optional[QAReport] = None
    editorPassHistory: List[EditorPassResult] = Field(default_factory=list)
```

No new collections required.
