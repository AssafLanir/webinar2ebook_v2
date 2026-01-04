"""Semantic QA analysis using LLM.

LLM-based analysis for:
- T013: Faithfulness scoring (compare draft to transcript)
- T014: Clarity assessment (readability, coherence)
- Completeness scoring (topic coverage)

Uses existing LLM abstraction with OpenAI primary, Anthropic fallback.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from src.llm import LLMClient, LLMRequest, ChatMessage
from src.models.qa_report import QAIssue, IssueSeverity, IssueType

logger = logging.getLogger(__name__)


# ============================================================================
# Configuration
# ============================================================================

# Sample size for analysis (to manage token usage)
MAX_DRAFT_SAMPLE_CHARS = 15000
MAX_TRANSCRIPT_SAMPLE_CHARS = 20000

# Minimum transcript length to enable faithfulness check
MIN_TRANSCRIPT_LENGTH = 100


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class SemanticAnalysisResult:
    """Results from semantic analysis."""
    issues: list[QAIssue]
    faithfulness_score: int  # 1-100
    clarity_score: int  # 1-100 (from LLM perspective)
    completeness_score: int  # 1-100


@dataclass
class FaithfulnessResult:
    """Result from faithfulness analysis."""
    score: int
    issues: list[QAIssue]
    summary: str


@dataclass
class ClarityResult:
    """Result from clarity analysis."""
    score: int
    issues: list[QAIssue]


@dataclass
class CompletenessResult:
    """Result from completeness analysis."""
    score: int
    issues: list[QAIssue]
    covered_topics: list[str]
    missing_topics: list[str]


# ============================================================================
# Prompts
# ============================================================================

FAITHFULNESS_SYSTEM_PROMPT = """You are a fact-checking assistant analyzing an ebook draft for faithfulness to a source transcript.

Your task is to identify claims in the draft that are NOT supported by the transcript.
Focus on:
- Factual claims (statistics, dates, names, quotes)
- Assertions about processes or methods
- Conclusions or recommendations

Do NOT flag:
- Reasonable paraphrasing
- Organizational text (introductions, transitions)
- Generic statements (greetings, summaries without new facts)

Respond in JSON format:
{
  "score": <1-100, where 100 means fully faithful>,
  "issues": [
    {
      "claim": "<the problematic claim from draft>",
      "location": "<chapter or section where found>",
      "reason": "<why this might not be in transcript>"
    }
  ],
  "summary": "<1-2 sentence summary>"
}"""

FAITHFULNESS_USER_PROMPT = """## Transcript (source material):
{transcript}

## Draft (to analyze):
{draft}

Analyze the draft for claims not supported by the transcript. Return JSON."""


CLARITY_SYSTEM_PROMPT = """You are a writing quality analyst evaluating ebook draft clarity.

Evaluate:
- Sentence structure (overly complex sentences)
- Jargon usage without explanation
- Logical flow between ideas
- Ambiguous references

Do NOT focus on:
- Grammar/spelling (handled separately)
- Formatting (headings, bullets)
- Length (handled by structural analysis)

Respond in JSON format:
{
  "score": <1-100, where 100 means excellent clarity>,
  "issues": [
    {
      "location": "<where in draft>",
      "problem": "<clarity issue>",
      "suggestion": "<how to improve>"
    }
  ]
}"""

CLARITY_USER_PROMPT = """## Draft to analyze for clarity:
{draft}

Evaluate writing clarity. Return JSON."""


COMPLETENESS_SYSTEM_PROMPT = """You are a content analyst checking if an ebook draft covers all key topics from a transcript.

Extract the main topics/themes from the transcript and check if the draft addresses them.

Respond in JSON format:
{
  "score": <1-100, where 100 means all topics covered>,
  "covered_topics": ["<topic1>", "<topic2>", ...],
  "missing_topics": ["<topic1>", "<topic2>", ...],
  "issues": [
    {
      "topic": "<missing topic>",
      "importance": "<high/medium/low>",
      "suggestion": "<where/how to add>"
    }
  ]
}"""

COMPLETENESS_USER_PROMPT = """## Transcript (source topics):
{transcript}

## Draft (to check coverage):
{draft}

Check topic coverage. Return JSON."""


# ============================================================================
# T013: Faithfulness Scoring
# ============================================================================

async def analyze_faithfulness(
    draft: str,
    transcript: str,
) -> FaithfulnessResult:
    """Analyze draft faithfulness to source transcript.

    Args:
        draft: The ebook draft text
        transcript: The source transcript

    Returns:
        FaithfulnessResult with score and issues
    """
    if len(transcript) < MIN_TRANSCRIPT_LENGTH:
        logger.info("Transcript too short for faithfulness analysis")
        return FaithfulnessResult(
            score=100,  # Assume faithful if no transcript
            issues=[],
            summary="No transcript available for comparison"
        )

    # Sample text to manage token usage
    draft_sample = draft[:MAX_DRAFT_SAMPLE_CHARS]
    transcript_sample = transcript[:MAX_TRANSCRIPT_SAMPLE_CHARS]

    try:
        import json
        client = LLMClient()
        request = LLMRequest(
            model="gpt-4o-mini",
            messages=[
                ChatMessage(role="system", content=FAITHFULNESS_SYSTEM_PROMPT),
                ChatMessage(role="user", content=FAITHFULNESS_USER_PROMPT.format(
                    transcript=transcript_sample,
                    draft=draft_sample
                )),
            ],
            temperature=0.3,  # Low temperature for consistency
            max_tokens=2000,
        )
        response = await client.generate(request)
        data = json.loads(response.text)

        score = max(1, min(100, data.get("score", 80)))
        summary = data.get("summary", "")

        issues: list[QAIssue] = []
        for i, issue_data in enumerate(data.get("issues", [])[:10]):  # Limit issues
            claim = issue_data.get("claim", "Unknown claim")
            location = issue_data.get("location", "")
            reason = issue_data.get("reason", "")

            severity = IssueSeverity.warning
            if "definitely not" in reason.lower() or "fabricated" in reason.lower():
                severity = IssueSeverity.critical

            issues.append(QAIssue(
                id=f"faith-{i}",
                severity=severity,
                issue_type=IssueType.faithfulness,
                location=location[:100] if location else None,
                message=f"Potentially unsupported claim: {claim[:200]}",
                suggestion=f"Verify this claim is in the source material. {reason[:200]}",
                metadata={"claim": claim[:300], "reason": reason[:300]}
            ))

        return FaithfulnessResult(score=score, issues=issues, summary=summary)

    except Exception as e:
        logger.warning(f"Faithfulness analysis failed: {e}")
        # Return neutral score on failure
        return FaithfulnessResult(
            score=75,
            issues=[QAIssue(
                id="faith-error",
                severity=IssueSeverity.info,
                issue_type=IssueType.faithfulness,
                message="Faithfulness analysis could not be completed",
                suggestion="Manual review recommended",
                metadata={"error": str(e)[:200]}
            )],
            summary="Analysis incomplete due to error"
        )


# ============================================================================
# T014: Clarity Assessment
# ============================================================================

async def analyze_clarity_semantic(draft: str) -> ClarityResult:
    """Analyze draft clarity using LLM.

    This complements the structural clarity checks with semantic analysis.

    Args:
        draft: The ebook draft text

    Returns:
        ClarityResult with score and issues
    """
    if len(draft) < 100:
        return ClarityResult(score=100, issues=[])

    # Sample text
    draft_sample = draft[:MAX_DRAFT_SAMPLE_CHARS]

    try:
        import json
        client = LLMClient()
        request = LLMRequest(
            model="gpt-4o-mini",
            messages=[
                ChatMessage(role="system", content=CLARITY_SYSTEM_PROMPT),
                ChatMessage(role="user", content=CLARITY_USER_PROMPT.format(draft=draft_sample)),
            ],
            temperature=0.3,
            max_tokens=2000,
        )
        response = await client.generate(request)
        data = json.loads(response.text)

        score = max(1, min(100, data.get("score", 80)))

        issues: list[QAIssue] = []
        for i, issue_data in enumerate(data.get("issues", [])[:10]):
            location = issue_data.get("location", "")
            problem = issue_data.get("problem", "Clarity issue")
            suggestion = issue_data.get("suggestion", "")

            issues.append(QAIssue(
                id=f"clarity-sem-{i}",
                severity=IssueSeverity.info,
                issue_type=IssueType.clarity,
                location=location[:100] if location else None,
                message=problem[:300],
                suggestion=suggestion[:300] if suggestion else None,
            ))

        return ClarityResult(score=score, issues=issues)

    except Exception as e:
        logger.warning(f"Clarity analysis failed: {e}")
        return ClarityResult(score=75, issues=[])


# ============================================================================
# Completeness Scoring
# ============================================================================

async def analyze_completeness(
    draft: str,
    transcript: str,
) -> CompletenessResult:
    """Analyze topic coverage completeness.

    Args:
        draft: The ebook draft text
        transcript: The source transcript

    Returns:
        CompletenessResult with score and topic lists
    """
    if len(transcript) < MIN_TRANSCRIPT_LENGTH:
        return CompletenessResult(
            score=100,
            issues=[],
            covered_topics=[],
            missing_topics=[]
        )

    draft_sample = draft[:MAX_DRAFT_SAMPLE_CHARS]
    transcript_sample = transcript[:MAX_TRANSCRIPT_SAMPLE_CHARS]

    try:
        import json
        client = LLMClient()
        request = LLMRequest(
            model="gpt-4o-mini",
            messages=[
                ChatMessage(role="system", content=COMPLETENESS_SYSTEM_PROMPT),
                ChatMessage(role="user", content=COMPLETENESS_USER_PROMPT.format(
                    transcript=transcript_sample,
                    draft=draft_sample
                )),
            ],
            temperature=0.3,
            max_tokens=2000,
        )
        response = await client.generate(request)
        data = json.loads(response.text)

        score = max(1, min(100, data.get("score", 80)))
        covered = data.get("covered_topics", [])
        missing = data.get("missing_topics", [])

        issues: list[QAIssue] = []
        for i, issue_data in enumerate(data.get("issues", [])[:5]):
            topic = issue_data.get("topic", "Unknown topic")
            importance = issue_data.get("importance", "medium")
            suggestion = issue_data.get("suggestion", "")

            severity = (
                IssueSeverity.warning if importance == "high"
                else IssueSeverity.info
            )

            issues.append(QAIssue(
                id=f"complete-{i}",
                severity=severity,
                issue_type=IssueType.completeness,
                message=f"Missing topic: {topic}",
                suggestion=suggestion[:300] if suggestion else f"Consider adding coverage of: {topic}",
                metadata={"topic": topic, "importance": importance}
            ))

        return CompletenessResult(
            score=score,
            issues=issues,
            covered_topics=covered[:20],  # Limit lists
            missing_topics=missing[:10]
        )

    except Exception as e:
        logger.warning(f"Completeness analysis failed: {e}")
        return CompletenessResult(
            score=75,
            issues=[],
            covered_topics=[],
            missing_topics=[]
        )


# ============================================================================
# Combined Semantic Analysis
# ============================================================================

async def analyze_semantics(
    draft: str,
    transcript: Optional[str] = None,
) -> SemanticAnalysisResult:
    """Run all semantic analysis checks.

    Args:
        draft: The ebook draft text
        transcript: Optional source transcript for faithfulness/completeness

    Returns:
        SemanticAnalysisResult with issues and scores
    """
    all_issues: list[QAIssue] = []

    # Default scores
    faithfulness_score = 100
    clarity_score = 80
    completeness_score = 100

    # Run analyses
    if transcript and len(transcript) >= MIN_TRANSCRIPT_LENGTH:
        # T013: Faithfulness
        faith_result = await analyze_faithfulness(draft, transcript)
        all_issues.extend(faith_result.issues)
        faithfulness_score = faith_result.score

        # Completeness
        complete_result = await analyze_completeness(draft, transcript)
        all_issues.extend(complete_result.issues)
        completeness_score = complete_result.score

    # T014: Clarity (always run)
    clarity_result = await analyze_clarity_semantic(draft)
    all_issues.extend(clarity_result.issues)
    clarity_score = clarity_result.score

    return SemanticAnalysisResult(
        issues=all_issues,
        faithfulness_score=faithfulness_score,
        clarity_score=clarity_score,
        completeness_score=completeness_score,
    )
