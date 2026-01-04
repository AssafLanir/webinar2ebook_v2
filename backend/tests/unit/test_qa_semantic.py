"""Unit tests for QA semantic analysis.

T007: Tests for:
- T013: Faithfulness scoring (LLM-based)
- T014: Clarity assessment (LLM-based)
- Completeness scoring (LLM-based)

Uses mocked LLM responses for deterministic testing.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.qa_report import IssueSeverity, IssueType
from src.services.qa_semantic import (
    ClarityResult,
    CompletenessResult,
    FaithfulnessResult,
    SemanticAnalysisResult,
    analyze_clarity_semantic,
    analyze_completeness,
    analyze_faithfulness,
    analyze_semantics,
    MIN_TRANSCRIPT_LENGTH,
)


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def sample_draft():
    """Sample ebook draft for testing."""
    return """# Introduction

Welcome to this comprehensive guide on software development.
We will explore various techniques and best practices.

# Chapter 1: Getting Started

In this chapter, we discuss the fundamentals of programming.
The key concepts include variables, loops, and functions.

# Chapter 2: Advanced Topics

Here we cover more advanced material like design patterns
and architecture considerations for large-scale systems.

# Conclusion

Thank you for reading this guide on software development.
"""


@pytest.fixture
def sample_transcript():
    """Sample transcript for testing."""
    return """
Today we're going to talk about software development.

First, let's discuss the fundamentals of programming.
Variables are containers for storing data.
Loops allow us to repeat operations.
Functions help us organize and reuse code.

Now, moving to more advanced topics.
Design patterns are reusable solutions to common problems.
Architecture is important for large-scale systems.
We need to think about scalability and maintainability.

That's the overview of software development fundamentals.
"""


# ============================================================================
# Helper Functions
# ============================================================================

def create_mock_llm_response(data: dict) -> MagicMock:
    """Create a mock LLM response object."""
    mock_response = MagicMock()
    mock_response.text = json.dumps(data)
    return mock_response


# ============================================================================
# T013: Faithfulness Scoring Tests
# ============================================================================

class TestAnalyzeFaithfulness:
    """Tests for T013: Faithfulness scoring."""

    @pytest.mark.asyncio
    async def test_short_transcript_returns_default(self):
        """Short transcript returns score 100 (assume faithful)."""
        result = await analyze_faithfulness(
            draft="Some draft content",
            transcript="Too short"  # Less than MIN_TRANSCRIPT_LENGTH
        )
        assert isinstance(result, FaithfulnessResult)
        assert result.score == 100
        assert len(result.issues) == 0
        assert "No transcript" in result.summary

    @pytest.mark.asyncio
    async def test_faithful_draft_high_score(self, sample_draft, sample_transcript):
        """Draft faithful to transcript gets high score."""
        mock_response_data = {
            "score": 95,
            "issues": [],
            "summary": "Draft is largely faithful to the transcript."
        }

        with patch("src.services.qa_semantic.LLMClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.generate.return_value = create_mock_llm_response(mock_response_data)
            mock_client_class.return_value = mock_client

            result = await analyze_faithfulness(sample_draft, sample_transcript)

        assert result.score == 95
        assert len(result.issues) == 0
        assert "faithful" in result.summary.lower()

    @pytest.mark.asyncio
    async def test_unfaithful_claims_flagged(self, sample_draft, sample_transcript):
        """Unfaithful claims are detected and flagged."""
        mock_response_data = {
            "score": 65,
            "issues": [
                {
                    "claim": "The company was founded in 1985",
                    "location": "Chapter 2",
                    "reason": "No founding date mentioned in transcript"
                },
                {
                    "claim": "Studies show 90% improvement",
                    "location": "Introduction",
                    "reason": "No statistics in source material"
                }
            ],
            "summary": "Several claims lack source support."
        }

        with patch("src.services.qa_semantic.LLMClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.generate.return_value = create_mock_llm_response(mock_response_data)
            mock_client_class.return_value = mock_client

            result = await analyze_faithfulness(sample_draft, sample_transcript)

        assert result.score == 65
        assert len(result.issues) == 2
        assert all(i.issue_type == IssueType.faithfulness for i in result.issues)

    @pytest.mark.asyncio
    async def test_critical_severity_for_fabrication(self, sample_draft, sample_transcript):
        """Claims flagged as fabricated get critical severity."""
        mock_response_data = {
            "score": 40,
            "issues": [
                {
                    "claim": "Made up quote from CEO",
                    "location": "Chapter 1",
                    "reason": "This is definitely not in the transcript, appears fabricated"
                }
            ],
            "summary": "Contains fabricated content."
        }

        with patch("src.services.qa_semantic.LLMClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.generate.return_value = create_mock_llm_response(mock_response_data)
            mock_client_class.return_value = mock_client

            result = await analyze_faithfulness(sample_draft, sample_transcript)

        assert len(result.issues) == 1
        assert result.issues[0].severity == IssueSeverity.critical

    @pytest.mark.asyncio
    async def test_llm_error_returns_neutral_score(self, sample_draft, sample_transcript):
        """LLM error returns neutral score with error info."""
        with patch("src.services.qa_semantic.LLMClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.generate.side_effect = Exception("API Error")
            mock_client_class.return_value = mock_client

            result = await analyze_faithfulness(sample_draft, sample_transcript)

        assert result.score == 75  # Neutral score
        assert len(result.issues) == 1
        assert "could not be completed" in result.issues[0].message

    @pytest.mark.asyncio
    async def test_score_clamped_to_valid_range(self, sample_draft, sample_transcript):
        """Score is clamped between 1-100."""
        mock_response_data = {
            "score": 150,  # Invalid, should be clamped
            "issues": [],
            "summary": "Test"
        }

        with patch("src.services.qa_semantic.LLMClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.generate.return_value = create_mock_llm_response(mock_response_data)
            mock_client_class.return_value = mock_client

            result = await analyze_faithfulness(sample_draft, sample_transcript)

        assert result.score == 100  # Clamped to max

    @pytest.mark.asyncio
    async def test_issues_limited_to_ten(self, sample_draft, sample_transcript):
        """Number of issues is limited to 10."""
        many_issues = [
            {"claim": f"Claim {i}", "location": f"Loc {i}", "reason": f"Reason {i}"}
            for i in range(20)
        ]
        mock_response_data = {
            "score": 30,
            "issues": many_issues,
            "summary": "Many issues"
        }

        with patch("src.services.qa_semantic.LLMClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.generate.return_value = create_mock_llm_response(mock_response_data)
            mock_client_class.return_value = mock_client

            result = await analyze_faithfulness(sample_draft, sample_transcript)

        assert len(result.issues) <= 10


# ============================================================================
# T014: Clarity Assessment Tests
# ============================================================================

class TestAnalyzeClarity:
    """Tests for T014: Clarity assessment."""

    @pytest.mark.asyncio
    async def test_short_draft_returns_perfect_score(self):
        """Very short draft returns score 100."""
        result = await analyze_clarity_semantic("Hi")  # Too short
        assert isinstance(result, ClarityResult)
        assert result.score == 100
        assert len(result.issues) == 0

    @pytest.mark.asyncio
    async def test_clear_writing_high_score(self, sample_draft):
        """Clear writing gets high clarity score."""
        mock_response_data = {
            "score": 90,
            "issues": []
        }

        with patch("src.services.qa_semantic.LLMClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.generate.return_value = create_mock_llm_response(mock_response_data)
            mock_client_class.return_value = mock_client

            result = await analyze_clarity_semantic(sample_draft)

        assert result.score == 90
        assert len(result.issues) == 0

    @pytest.mark.asyncio
    async def test_unclear_writing_flagged(self, sample_draft):
        """Unclear writing issues are detected."""
        mock_response_data = {
            "score": 60,
            "issues": [
                {
                    "location": "Chapter 1, paragraph 3",
                    "problem": "Overly complex sentence structure",
                    "suggestion": "Break into shorter sentences"
                },
                {
                    "location": "Introduction",
                    "problem": "Undefined jargon: 'refactoring'",
                    "suggestion": "Define technical terms for general audience"
                }
            ]
        }

        with patch("src.services.qa_semantic.LLMClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.generate.return_value = create_mock_llm_response(mock_response_data)
            mock_client_class.return_value = mock_client

            result = await analyze_clarity_semantic(sample_draft)

        assert result.score == 60
        assert len(result.issues) == 2
        assert all(i.issue_type == IssueType.clarity for i in result.issues)
        assert all(i.severity == IssueSeverity.info for i in result.issues)

    @pytest.mark.asyncio
    async def test_llm_error_returns_default_score(self, sample_draft):
        """LLM error returns neutral score with no issues."""
        with patch("src.services.qa_semantic.LLMClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.generate.side_effect = Exception("API Error")
            mock_client_class.return_value = mock_client

            result = await analyze_clarity_semantic(sample_draft)

        assert result.score == 75  # Neutral
        assert len(result.issues) == 0


# ============================================================================
# Completeness Scoring Tests
# ============================================================================

class TestAnalyzeCompleteness:
    """Tests for completeness scoring."""

    @pytest.mark.asyncio
    async def test_short_transcript_returns_default(self):
        """Short transcript returns score 100."""
        result = await analyze_completeness(
            draft="Some draft content",
            transcript="Short"
        )
        assert isinstance(result, CompletenessResult)
        assert result.score == 100
        assert len(result.issues) == 0
        assert result.covered_topics == []
        assert result.missing_topics == []

    @pytest.mark.asyncio
    async def test_complete_coverage_high_score(self, sample_draft, sample_transcript):
        """Complete topic coverage gets high score."""
        mock_response_data = {
            "score": 95,
            "covered_topics": ["programming fundamentals", "variables", "loops", "design patterns"],
            "missing_topics": [],
            "issues": []
        }

        with patch("src.services.qa_semantic.LLMClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.generate.return_value = create_mock_llm_response(mock_response_data)
            mock_client_class.return_value = mock_client

            result = await analyze_completeness(sample_draft, sample_transcript)

        assert result.score == 95
        assert len(result.covered_topics) == 4
        assert len(result.missing_topics) == 0
        assert len(result.issues) == 0

    @pytest.mark.asyncio
    async def test_missing_topics_flagged(self, sample_draft, sample_transcript):
        """Missing topics are detected and flagged."""
        mock_response_data = {
            "score": 70,
            "covered_topics": ["programming fundamentals", "variables"],
            "missing_topics": ["error handling", "testing"],
            "issues": [
                {
                    "topic": "error handling",
                    "importance": "high",
                    "suggestion": "Add a section on exception handling"
                },
                {
                    "topic": "testing",
                    "importance": "medium",
                    "suggestion": "Consider adding a testing chapter"
                }
            ]
        }

        with patch("src.services.qa_semantic.LLMClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.generate.return_value = create_mock_llm_response(mock_response_data)
            mock_client_class.return_value = mock_client

            result = await analyze_completeness(sample_draft, sample_transcript)

        assert result.score == 70
        assert len(result.missing_topics) == 2
        assert len(result.issues) == 2
        assert all(i.issue_type == IssueType.completeness for i in result.issues)

    @pytest.mark.asyncio
    async def test_high_importance_gets_warning_severity(self, sample_draft, sample_transcript):
        """High importance missing topics get warning severity."""
        mock_response_data = {
            "score": 60,
            "covered_topics": [],
            "missing_topics": ["critical topic"],
            "issues": [
                {
                    "topic": "critical topic",
                    "importance": "high",
                    "suggestion": "Must add this"
                }
            ]
        }

        with patch("src.services.qa_semantic.LLMClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.generate.return_value = create_mock_llm_response(mock_response_data)
            mock_client_class.return_value = mock_client

            result = await analyze_completeness(sample_draft, sample_transcript)

        assert len(result.issues) == 1
        assert result.issues[0].severity == IssueSeverity.warning

    @pytest.mark.asyncio
    async def test_llm_error_returns_default(self, sample_draft, sample_transcript):
        """LLM error returns neutral score with empty lists."""
        with patch("src.services.qa_semantic.LLMClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.generate.side_effect = Exception("API Error")
            mock_client_class.return_value = mock_client

            result = await analyze_completeness(sample_draft, sample_transcript)

        assert result.score == 75
        assert result.covered_topics == []
        assert result.missing_topics == []


# ============================================================================
# Combined Semantic Analysis Tests
# ============================================================================

class TestAnalyzeSemantics:
    """Tests for combined semantic analysis."""

    @pytest.mark.asyncio
    async def test_without_transcript(self, sample_draft):
        """Analysis without transcript skips faithfulness and completeness."""
        mock_clarity_response = {
            "score": 85,
            "issues": []
        }

        with patch("src.services.qa_semantic.LLMClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.generate.return_value = create_mock_llm_response(mock_clarity_response)
            mock_client_class.return_value = mock_client

            result = await analyze_semantics(sample_draft, transcript=None)

        assert isinstance(result, SemanticAnalysisResult)
        assert result.faithfulness_score == 100  # Default when no transcript
        assert result.completeness_score == 100  # Default when no transcript
        assert result.clarity_score == 85

    @pytest.mark.asyncio
    async def test_with_transcript_runs_all_analyses(self, sample_draft, sample_transcript):
        """Analysis with transcript runs faithfulness, clarity, and completeness."""
        # Setup different responses for each analysis
        call_count = 0
        responses = [
            # Faithfulness
            {"score": 90, "issues": [], "summary": "Faithful"},
            # Completeness
            {"score": 85, "issues": [], "covered_topics": ["topic"], "missing_topics": []},
            # Clarity
            {"score": 80, "issues": []}
        ]

        async def mock_generate(*args, **kwargs):
            nonlocal call_count
            response = create_mock_llm_response(responses[call_count % len(responses)])
            call_count += 1
            return response

        with patch("src.services.qa_semantic.LLMClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.generate = mock_generate
            mock_client_class.return_value = mock_client

            result = await analyze_semantics(sample_draft, sample_transcript)

        assert result.faithfulness_score == 90
        assert result.completeness_score == 85
        assert result.clarity_score == 80

    @pytest.mark.asyncio
    async def test_issues_combined_from_all_analyses(self, sample_draft, sample_transcript):
        """Issues from all analyses are combined in result."""
        call_count = 0
        responses = [
            # Faithfulness with issues
            {
                "score": 80,
                "issues": [{"claim": "X", "location": "Y", "reason": "Z"}],
                "summary": "Issues found"
            },
            # Completeness with issues
            {
                "score": 75,
                "issues": [{"topic": "A", "importance": "high", "suggestion": "B"}],
                "covered_topics": [],
                "missing_topics": ["A"]
            },
            # Clarity with issues
            {
                "score": 70,
                "issues": [{"location": "C", "problem": "D", "suggestion": "E"}]
            }
        ]

        async def mock_generate(*args, **kwargs):
            nonlocal call_count
            response = create_mock_llm_response(responses[call_count % len(responses)])
            call_count += 1
            return response

        with patch("src.services.qa_semantic.LLMClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.generate = mock_generate
            mock_client_class.return_value = mock_client

            result = await analyze_semantics(sample_draft, sample_transcript)

        # Should have issues from all three analyses
        assert len(result.issues) >= 3
        issue_types = {i.issue_type for i in result.issues}
        assert IssueType.faithfulness in issue_types
        assert IssueType.completeness in issue_types
        assert IssueType.clarity in issue_types

    @pytest.mark.asyncio
    async def test_short_transcript_treated_as_no_transcript(self, sample_draft):
        """Transcript shorter than MIN_TRANSCRIPT_LENGTH is treated as absent."""
        short_transcript = "x" * (MIN_TRANSCRIPT_LENGTH - 10)  # Just under threshold

        mock_clarity_response = {"score": 85, "issues": []}

        with patch("src.services.qa_semantic.LLMClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.generate.return_value = create_mock_llm_response(mock_clarity_response)
            mock_client_class.return_value = mock_client

            result = await analyze_semantics(sample_draft, short_transcript)

        # Should only run clarity (faithfulness and completeness skipped)
        assert result.faithfulness_score == 100
        assert result.completeness_score == 100


# ============================================================================
# Edge Cases
# ============================================================================

class TestSemanticEdgeCases:
    """Edge case tests for semantic analysis."""

    @pytest.mark.asyncio
    async def test_empty_draft(self):
        """Empty draft is handled gracefully."""
        result = await analyze_clarity_semantic("")
        assert result.score == 100  # Too short = perfect score
        assert len(result.issues) == 0

    @pytest.mark.asyncio
    async def test_malformed_json_response(self, sample_draft, sample_transcript):
        """Malformed JSON response is handled gracefully."""
        mock_response = MagicMock()
        mock_response.text = "not valid json {"

        with patch("src.services.qa_semantic.LLMClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.generate.return_value = mock_response
            mock_client_class.return_value = mock_client

            # Should not crash, returns neutral score
            result = await analyze_faithfulness(sample_draft, sample_transcript)

        assert result.score == 75  # Neutral fallback
        assert len(result.issues) == 1  # Error issue

    @pytest.mark.asyncio
    async def test_missing_score_in_response(self, sample_draft, sample_transcript):
        """Missing score field uses default."""
        mock_response_data = {
            "issues": [],
            "summary": "No score provided"
            # Missing "score" field
        }

        with patch("src.services.qa_semantic.LLMClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.generate.return_value = create_mock_llm_response(mock_response_data)
            mock_client_class.return_value = mock_client

            result = await analyze_faithfulness(sample_draft, sample_transcript)

        assert result.score == 80  # Default score

    @pytest.mark.asyncio
    async def test_issue_text_truncation(self, sample_draft, sample_transcript):
        """Very long issue text is truncated."""
        long_claim = "x" * 500
        mock_response_data = {
            "score": 50,
            "issues": [
                {
                    "claim": long_claim,
                    "location": "y" * 200,
                    "reason": "z" * 500
                }
            ],
            "summary": "Long text"
        }

        with patch("src.services.qa_semantic.LLMClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.generate.return_value = create_mock_llm_response(mock_response_data)
            mock_client_class.return_value = mock_client

            result = await analyze_faithfulness(sample_draft, sample_transcript)

        assert len(result.issues) == 1
        # Location should be truncated to 100 chars
        assert len(result.issues[0].location) <= 100
        # Message contains claim, limited to 200 chars in message
        assert len(result.issues[0].message) <= 350  # "Potentially unsupported claim: " + 200
