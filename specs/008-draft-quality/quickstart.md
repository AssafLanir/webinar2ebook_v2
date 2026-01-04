# Quickstart: Draft Quality System

**Feature**: 008-draft-quality
**Date**: 2026-01-01

## Prerequisites

1. Backend running on http://localhost:8000
2. Frontend running on http://localhost:5173
3. MongoDB running with existing projects
4. At least one project with a generated draft

## Scenario 1: Automatic QA After Draft Generation

**Goal**: Verify QA runs automatically when draft is generated

1. Open the application and select a project
2. Navigate to Tab 3 (Draft)
3. Click "Generate Draft" button
4. Wait for draft generation to complete
5. **Expected**: QA panel appears showing:
   - Summary badge: "QA: X issues"
   - Overall score: 1-100
   - Expandable issue list

**Verification**:
```bash
curl http://localhost:8000/api/projects/{project_id}/qa/report | jq '.data.overall_score'
```

## Scenario 2: View QA Report Details

**Goal**: Verify QA issues are displayed with proper details

1. After draft generation, locate the QA panel in Tab 3
2. Click to expand the issue list
3. **Expected**: Issues grouped by severity:
   - Critical issues (red) at top
   - Warning issues (yellow) in middle
   - Info issues (blue) at bottom
4. Click on an issue
5. **Expected**: See:
   - Severity icon
   - Chapter/heading location
   - Description message
   - Suggestion (if available)

## Scenario 3: Manual QA Re-run

**Goal**: Verify QA can be triggered manually

1. Open a project with existing draft
2. Navigate to Tab 3
3. Click "Re-run QA" button (or similar)
4. **Expected**:
   - Loading indicator appears
   - New QA report generated within 30 seconds
   - Results update in panel

**Verification**:
```bash
curl -X POST http://localhost:8000/api/projects/{project_id}/qa/analyze | jq '.data'
```

## Scenario 4: Editor Pass (P2)

**Goal**: Verify editor pass improves quality

1. Open a project with QA report showing issues
2. Note current repetition score
3. Click "Run Improve Pass" button
4. Wait for improvement to complete
5. **Expected**:
   - Before/after comparison shown
   - Repetition score improves
   - Faithfulness score maintained or improved
   - Original draft available for revert

## Scenario 5: Regression Suite (P2)

**Goal**: Verify regression suite catches quality regressions

```bash
# From backend directory
cd backend

# Run regression suite
python -m pytest tests/fixtures/test_regression.py -v

# Expected output:
# - Each golden project tested
# - Scores compared to baselines
# - PASS if within tolerance
# - FAIL if regression detected
```

## API Quick Reference

```bash
# Get QA report
curl http://localhost:8000/api/projects/{id}/qa/report

# Trigger QA analysis
curl -X POST http://localhost:8000/api/projects/{id}/qa/analyze

# Run editor pass (P2)
curl -X POST http://localhost:8000/api/projects/{id}/qa/improve
```

## Troubleshooting

### QA report not appearing
1. Check draft exists: `curl http://localhost:8000/projects/{id} | jq '.data.draftText'`
2. Check backend logs for errors
3. Manually trigger: `POST /api/projects/{id}/qa/analyze`

### Low faithfulness score
1. Verify transcript is available in project
2. Check if draft significantly diverges from source
3. Review "faithfulness" issues in report

### Editor pass fails
1. Check if issues exist in report
2. Verify LLM API keys are configured
3. Check backend logs for timeout/error
