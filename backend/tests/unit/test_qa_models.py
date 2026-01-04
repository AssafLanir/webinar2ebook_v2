"""Contract tests for QA Report models.

These tests ensure:
1. Pydantic models validate correctly
2. Sample data works with models
3. Issue truncation works correctly
4. Round-trip serialization works
5. Extra fields are rejected (drift prevention)
6. Schema matches specs/008-draft-quality/schemas/qa_report.schema.json
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from src.models.qa_report import (
    QAReport,
    QAIssue,
    RubricScores,
    IssueCounts,
    IssueSeverity,
    IssueType,
    MAX_ISSUES,
    QA_REPORT_VERSION,
    qa_report_json_schema,
)


# Path to JSON schema
QA_SCHEMA_PATH = Path(__file__).parent.parent.parent.parent / "specs" / "008-draft-quality" / "schemas" / "qa_report.schema.json"


class TestQAReportSchema:
    """Test QA report schema file exists and is valid."""

    def test_schema_file_exists(self):
        """Verify qa_report.schema.json exists."""
        assert QA_SCHEMA_PATH.exists(), f"Schema not found: {QA_SCHEMA_PATH}"

    def test_schema_is_valid_json(self):
        """Verify schema file contains valid JSON."""
        with open(QA_SCHEMA_PATH) as f:
            schema = json.load(f)
        assert isinstance(schema, dict)
        assert "properties" in schema

    def test_schema_has_required_fields(self):
        """Verify schema defines all required fields."""
        with open(QA_SCHEMA_PATH) as f:
            schema = json.load(f)

        required = schema.get("required", [])
        expected_required = [
            "id", "project_id", "draft_hash", "overall_score",
            "rubric_scores", "issues", "issue_counts", "truncated",
            "total_issue_count", "generated_at", "analysis_duration_ms", "version"
        ]
        for field in expected_required:
            assert field in required, f"Missing required field: {field}"


class TestIssueCounts:
    """Test IssueCounts model."""

    def test_default_values(self):
        """Test default values are zero."""
        counts = IssueCounts()
        assert counts.critical == 0
        assert counts.warning == 0
        assert counts.info == 0

    def test_total_property(self):
        """Test total property sums counts."""
        counts = IssueCounts(critical=5, warning=10, info=20)
        assert counts.total == 35

    def test_validation(self):
        """Test validation rejects negative values."""
        with pytest.raises(Exception):
            IssueCounts(critical=-1)


class TestRubricScores:
    """Test RubricScores model."""

    def test_valid_scores(self):
        """Test valid score values."""
        scores = RubricScores(
            structure=85,
            clarity=70,
            faithfulness=90,
            repetition=60,
            completeness=75
        )
        assert scores.structure == 85
        assert scores.clarity == 70

    def test_average_calculation(self):
        """Test average score calculation."""
        scores = RubricScores(
            structure=80,
            clarity=80,
            faithfulness=80,
            repetition=80,
            completeness=80
        )
        assert scores.average() == 80.0

    def test_score_range_validation(self):
        """Test score must be 1-100."""
        with pytest.raises(Exception):
            RubricScores(
                structure=0,  # Invalid: below 1
                clarity=70,
                faithfulness=90,
                repetition=60,
                completeness=75
            )

        with pytest.raises(Exception):
            RubricScores(
                structure=101,  # Invalid: above 100
                clarity=70,
                faithfulness=90,
                repetition=60,
                completeness=75
            )


class TestQAIssue:
    """Test QAIssue model."""

    def test_minimal_issue(self):
        """Test issue with only required fields."""
        issue = QAIssue(
            id="issue-1",
            severity=IssueSeverity.warning,
            issue_type=IssueType.repetition,
            message="Repeated phrase detected"
        )
        assert issue.id == "issue-1"
        assert issue.severity == IssueSeverity.warning
        assert issue.chapter_index is None
        assert issue.suggestion is None

    def test_full_issue(self):
        """Test issue with all fields."""
        issue = QAIssue(
            id="issue-2",
            severity=IssueSeverity.critical,
            issue_type=IssueType.faithfulness,
            chapter_index=3,
            heading="Chapter 4: Results",
            location="...the data shows...",
            message="Claim not found in transcript",
            suggestion="Remove or verify this claim",
            metadata={"claim": "Sales increased by 200%"}
        )
        assert issue.chapter_index == 3
        assert issue.metadata is not None

    def test_message_length_validation(self):
        """Test message must be 1-500 chars."""
        with pytest.raises(Exception):
            QAIssue(
                id="issue-3",
                severity=IssueSeverity.info,
                issue_type=IssueType.clarity,
                message=""  # Too short
            )

    def test_severity_enum_values(self):
        """Test all severity values work."""
        for severity in IssueSeverity:
            issue = QAIssue(
                id=f"issue-{severity.value}",
                severity=severity,
                issue_type=IssueType.structure,
                message=f"Test {severity.value}"
            )
            assert issue.severity == severity

    def test_issue_type_enum_values(self):
        """Test all issue type values work."""
        for issue_type in IssueType:
            issue = QAIssue(
                id=f"issue-{issue_type.value}",
                severity=IssueSeverity.info,
                issue_type=issue_type,
                message=f"Test {issue_type.value}"
            )
            assert issue.issue_type == issue_type


class TestQAReport:
    """Test QAReport model."""

    @pytest.fixture
    def sample_scores(self):
        """Sample rubric scores."""
        return RubricScores(
            structure=85,
            clarity=70,
            faithfulness=90,
            repetition=60,
            completeness=75
        )

    @pytest.fixture
    def sample_issues(self):
        """Sample issues list."""
        return [
            QAIssue(
                id="issue-1",
                severity=IssueSeverity.warning,
                issue_type=IssueType.repetition,
                message="Phrase repeated 5 times"
            ),
            QAIssue(
                id="issue-2",
                severity=IssueSeverity.critical,
                issue_type=IssueType.faithfulness,
                message="Claim not in transcript"
            ),
            QAIssue(
                id="issue-3",
                severity=IssueSeverity.info,
                issue_type=IssueType.clarity,
                message="Consider shorter sentences"
            ),
        ]

    def test_create_report_directly(self, sample_scores, sample_issues):
        """Test creating a report with direct construction."""
        report = QAReport(
            id=str(uuid4()),
            project_id="proj-123",
            draft_hash="abc123",
            overall_score=76,
            rubric_scores=sample_scores,
            issues=sample_issues,
            issue_counts=IssueCounts(critical=1, warning=1, info=1),
            truncated=False,
            total_issue_count=3,
            generated_at=datetime.now(timezone.utc),
            analysis_duration_ms=1500,
            version=QA_REPORT_VERSION
        )
        assert report.overall_score == 76
        assert len(report.issues) == 3
        assert report.truncated is False

    def test_from_issues_factory(self, sample_scores, sample_issues):
        """Test creating a report with from_issues factory."""
        report = QAReport.from_issues(
            id=str(uuid4()),
            project_id="proj-123",
            draft_hash="abc123",
            overall_score=76,
            rubric_scores=sample_scores,
            all_issues=sample_issues,
            analysis_duration_ms=1500
        )
        assert report.overall_score == 76
        assert len(report.issues) == 3
        assert report.truncated is False
        assert report.total_issue_count == 3
        assert report.issue_counts.critical == 1
        assert report.issue_counts.warning == 1
        assert report.issue_counts.info == 1

    def test_issue_truncation(self, sample_scores):
        """Test that issues are truncated at MAX_ISSUES."""
        # Create more issues than MAX_ISSUES
        many_issues = [
            QAIssue(
                id=f"issue-{i}",
                severity=IssueSeverity.info,
                issue_type=IssueType.clarity,
                message=f"Issue {i}"
            )
            for i in range(MAX_ISSUES + 50)
        ]

        report = QAReport.from_issues(
            id=str(uuid4()),
            project_id="proj-123",
            draft_hash="abc123",
            overall_score=50,
            rubric_scores=sample_scores,
            all_issues=many_issues,
            analysis_duration_ms=2000
        )

        assert len(report.issues) == MAX_ISSUES
        assert report.truncated is True
        assert report.total_issue_count == MAX_ISSUES + 50
        assert report.issue_counts.info == MAX_ISSUES + 50

    def test_truncation_preserves_critical_first(self, sample_scores):
        """Test that truncation keeps critical issues first."""
        # Create mix of severities
        issues = []
        for i in range(100):
            issues.append(QAIssue(
                id=f"info-{i}",
                severity=IssueSeverity.info,
                issue_type=IssueType.clarity,
                message=f"Info issue {i}"
            ))
        for i in range(100):
            issues.append(QAIssue(
                id=f"warning-{i}",
                severity=IssueSeverity.warning,
                issue_type=IssueType.structure,
                message=f"Warning issue {i}"
            ))
        for i in range(150):
            issues.append(QAIssue(
                id=f"critical-{i}",
                severity=IssueSeverity.critical,
                issue_type=IssueType.faithfulness,
                message=f"Critical issue {i}"
            ))

        # Total: 350 issues (100 info + 100 warning + 150 critical)
        # After truncation to 300, we should have all 150 critical + 100 warning + 50 info

        report = QAReport.from_issues(
            id=str(uuid4()),
            project_id="proj-123",
            draft_hash="abc123",
            overall_score=30,
            rubric_scores=sample_scores,
            all_issues=issues,
            analysis_duration_ms=3000
        )

        assert report.truncated is True
        assert report.total_issue_count == 350

        # Count severities in stored issues
        stored_critical = sum(1 for i in report.issues if i.severity == IssueSeverity.critical)
        stored_warning = sum(1 for i in report.issues if i.severity == IssueSeverity.warning)
        stored_info = sum(1 for i in report.issues if i.severity == IssueSeverity.info)

        # All critical should be preserved
        assert stored_critical == 150
        # All warning should be preserved
        assert stored_warning == 100
        # Only 50 info should remain (300 - 150 - 100 = 50)
        assert stored_info == 50


class TestQAReportSerialization:
    """Test QAReport serialization."""

    @pytest.fixture
    def sample_report(self):
        """Create a sample report for serialization tests."""
        return QAReport(
            id="report-123",
            project_id="proj-456",
            draft_hash="hash789",
            overall_score=75,
            rubric_scores=RubricScores(
                structure=80,
                clarity=70,
                faithfulness=85,
                repetition=65,
                completeness=75
            ),
            issues=[
                QAIssue(
                    id="issue-1",
                    severity=IssueSeverity.warning,
                    issue_type=IssueType.repetition,
                    message="Test issue"
                )
            ],
            issue_counts=IssueCounts(critical=0, warning=1, info=0),
            truncated=False,
            total_issue_count=1,
            generated_at=datetime.now(timezone.utc),
            analysis_duration_ms=1000,
            version=QA_REPORT_VERSION
        )

    def test_json_roundtrip(self, sample_report):
        """Test JSON serialization roundtrip."""
        json_str = sample_report.model_dump_json()
        restored = QAReport.model_validate_json(json_str)

        assert restored.id == sample_report.id
        assert restored.overall_score == sample_report.overall_score
        assert len(restored.issues) == len(sample_report.issues)

    def test_dict_roundtrip(self, sample_report):
        """Test dict serialization roundtrip."""
        data = sample_report.model_dump()
        restored = QAReport.model_validate(data)

        assert restored.id == sample_report.id
        assert restored.overall_score == sample_report.overall_score

    def test_json_schema_generation(self):
        """Test that JSON schema can be generated."""
        schema = qa_report_json_schema()
        assert isinstance(schema, dict)
        assert "properties" in schema


class TestExtraFieldsRejected:
    """Test that extra fields are rejected (drift prevention)."""

    def test_issue_counts_rejects_extra(self):
        """IssueCounts should reject unknown fields."""
        with pytest.raises(Exception):
            IssueCounts.model_validate({
                "critical": 1,
                "warning": 2,
                "info": 3,
                "unknown": 4
            })

    def test_rubric_scores_rejects_extra(self):
        """RubricScores should reject unknown fields."""
        with pytest.raises(Exception):
            RubricScores.model_validate({
                "structure": 80,
                "clarity": 70,
                "faithfulness": 85,
                "repetition": 65,
                "completeness": 75,
                "unknown": 50
            })

    def test_qa_issue_rejects_extra(self):
        """QAIssue should reject unknown fields."""
        with pytest.raises(Exception):
            QAIssue.model_validate({
                "id": "issue-1",
                "severity": "warning",
                "issue_type": "repetition",
                "message": "Test",
                "unknown": "value"
            })

    def test_qa_report_rejects_extra(self):
        """QAReport should reject unknown fields."""
        with pytest.raises(Exception):
            QAReport.model_validate({
                "id": "report-1",
                "project_id": "proj-1",
                "draft_hash": "hash",
                "overall_score": 75,
                "rubric_scores": {
                    "structure": 80,
                    "clarity": 70,
                    "faithfulness": 85,
                    "repetition": 65,
                    "completeness": 75
                },
                "issues": [],
                "issue_counts": {"critical": 0, "warning": 0, "info": 0},
                "truncated": False,
                "total_issue_count": 0,
                "generated_at": "2026-01-01T00:00:00Z",
                "analysis_duration_ms": 1000,
                "version": "1.0",
                "unknown": "value"
            })
