"""QA Evaluator - combines structural and semantic analysis.

T015: Main orchestrator for quality assessment.
- Runs structural analysis (fast, regex-based)
- Runs semantic analysis (LLM-based)
- Combines scores into overall quality score
- Handles issue truncation (max 300 issues)
- Generates hash for cache invalidation
"""

from __future__ import annotations

import hashlib
import logging
import time
from typing import Optional
from uuid import uuid4

from src.models.qa_report import (
    QAReport,
    QAIssue,
    RubricScores,
    IssueSeverity,
    MAX_ISSUES,
)
from .qa_structural import analyze_structure
from .qa_semantic import analyze_semantics

logger = logging.getLogger(__name__)


def compute_draft_hash(draft: str) -> str:
    """Compute a hash of the draft for cache invalidation."""
    return hashlib.sha256(draft.encode('utf-8')).hexdigest()[:16]


def compute_overall_score(rubric: RubricScores) -> int:
    """Compute weighted overall score from rubric scores.

    Weights:
    - Faithfulness: 30% (most important - factual accuracy)
    - Completeness: 20%
    - Structure: 20%
    - Clarity: 15%
    - Repetition: 15%
    """
    weighted = (
        rubric.faithfulness * 0.30 +
        rubric.completeness * 0.20 +
        rubric.structure * 0.20 +
        rubric.clarity * 0.15 +
        rubric.repetition * 0.15
    )
    return max(1, min(100, int(weighted)))


async def evaluate_draft(
    project_id: str,
    draft: str,
    transcript: Optional[str] = None,
) -> QAReport:
    """Run full QA evaluation on a draft.

    Args:
        project_id: The project ID
        draft: The draft text to evaluate
        transcript: Optional source transcript for faithfulness analysis

    Returns:
        QAReport with scores and issues
    """
    start_time = time.time()

    if not draft or len(draft.strip()) < 50:
        # Return minimal report for empty/tiny drafts
        return QAReport(
            id=str(uuid4()),
            project_id=project_id,
            draft_hash=compute_draft_hash(draft or ""),
            overall_score=50,
            rubric_scores=RubricScores(
                structure=50,
                clarity=50,
                faithfulness=50,
                repetition=50,
                completeness=50,
            ),
            issues=[QAIssue(
                id="empty-0",
                severity=IssueSeverity.warning,
                issue_type="structure",
                message="Draft is too short for meaningful analysis",
                suggestion="Generate more content before running QA",
            )],
            analysis_duration_ms=int((time.time() - start_time) * 1000),
        )

    logger.info(f"Starting QA evaluation for project {project_id}")

    # Run structural analysis (fast, no async needed)
    structural_result = analyze_structure(draft)
    logger.debug(
        f"Structural analysis complete: structure={structural_result.structure_score}, "
        f"repetition={structural_result.repetition_score}, "
        f"clarity={structural_result.clarity_score}"
    )

    # Run semantic analysis (LLM-based, async)
    semantic_result = await analyze_semantics(draft, transcript)
    logger.debug(
        f"Semantic analysis complete: faithfulness={semantic_result.faithfulness_score}, "
        f"clarity={semantic_result.clarity_score}, "
        f"completeness={semantic_result.completeness_score}"
    )

    # Combine all issues
    all_issues = structural_result.issues + semantic_result.issues

    # Combine clarity scores (average of structural and semantic)
    combined_clarity = (
        structural_result.clarity_score + semantic_result.clarity_score
    ) // 2

    # Build rubric scores
    rubric_scores = RubricScores(
        structure=structural_result.structure_score,
        clarity=combined_clarity,
        faithfulness=semantic_result.faithfulness_score,
        repetition=structural_result.repetition_score,
        completeness=semantic_result.completeness_score,
    )

    # Compute overall score
    overall_score = compute_overall_score(rubric_scores)

    # Calculate duration
    duration_ms = int((time.time() - start_time) * 1000)

    # Create report with automatic truncation
    report = QAReport.from_issues(
        id=str(uuid4()),
        project_id=project_id,
        draft_hash=compute_draft_hash(draft),
        overall_score=overall_score,
        rubric_scores=rubric_scores,
        all_issues=all_issues,
        analysis_duration_ms=duration_ms,
    )

    logger.info(
        f"QA evaluation complete for project {project_id}: "
        f"score={overall_score}, issues={report.total_issue_count}, "
        f"duration={duration_ms}ms"
    )

    return report


async def should_run_qa(
    draft: str,
    existing_report: Optional[QAReport] = None,
) -> bool:
    """Check if QA should run based on draft changes.

    Args:
        draft: Current draft text
        existing_report: Existing QA report if any

    Returns:
        True if QA should run (draft changed or no report)
    """
    if not existing_report:
        return True

    current_hash = compute_draft_hash(draft)
    return current_hash != existing_report.draft_hash
