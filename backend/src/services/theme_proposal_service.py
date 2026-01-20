"""Theme proposal service for Ideas Edition.

Uses LLM to analyze transcript and propose thematic chapters.
Each theme gets supporting segments with proper canonical offsets.
"""

import json
import logging
import re
import uuid
from typing import Any

from src.llm import LLMClient
from src.llm.models import ChatMessage, LLMRequest, ResponseFormat
from src.models.edition import Coverage, SegmentRef, Theme
from src.services.canonical_service import canonicalize, compute_hash, normalize_for_comparison
from src.services.coverage_service import score_coverage

logger = logging.getLogger(__name__)

# Prompt for theme extraction
THEME_PROPOSAL_PROMPT = """You are extracting themes and supporting quotes from an interview transcript.

OUTPUT FORMAT (JSON):
{
  "themes": [
    {
      "title": "Short Theme Title",
      "one_liner": "One sentence summary",
      "keywords": ["keyword1", "keyword2"],
      "supporting_quotes": [
        "Copy-paste exact multi-sentence passage from transcript here",
        "Another copy-paste of exact transcript text - longer passages preferred"
      ]
    }
  ]
}

RULES:
1. Identify 3-7 distinct major themes
2. For supporting_quotes: provide 4-6 quotes per theme
3. Each quote should be a SUBSTANTIAL passage (3-6 sentences, 100-300 words) - longer is better
4. COPY-PASTE directly from the transcript. These must be findable via text search.
5. NO paraphrasing. NO explanations. NO "The speaker says..." - just the raw quote text.
6. Include enough context around key statements

BAD quote (too short): "progress is unlimited"
BAD quote (paraphrased): "The interviewee discusses how progress is unlimited"
GOOD quote (substantial passage): "The scope of both understanding and controlling the world is actually infinite. There's no limit to what we could understand or what we could control. And one day, no doubt, we will become powerful enough that you'll just have to be careful not to injure yourself by your own newfound power."

TRANSCRIPT:
"""


def estimate_token_count(text: str) -> int:
    """Estimate token count for a text segment.

    Uses simple heuristic: ~4 characters per token on average.
    This is a rough estimate for coverage scoring.
    """
    return max(1, len(text) // 4)


def _strip_quotes_for_matching(text: str) -> str:
    """Strip quote marks for fuzzy matching.

    Removes single and double quotes that might differ between
    LLM output and transcript.
    """
    return text.replace("'", "").replace('"', "")


def find_quote_in_transcript(
    quote: str,
    canonical_transcript: str,
    canonical_hash: str,
) -> SegmentRef | None:
    """Find a quote in the canonical transcript and create SegmentRef.

    Args:
        quote: Quote text to find (may not be exactly in transcript)
        canonical_transcript: Flat canonical transcript
        canonical_hash: SHA256 hash of canonical transcript

    Returns:
        SegmentRef if found, None otherwise
    """
    # Use normalize_for_comparison for consistent matching (canonicalize + lowercase)
    normalized_quote = normalize_for_comparison(quote)
    # canonical_transcript is already canonical, just need lowercase
    normalized_transcript = canonical_transcript.lower()

    # Also prepare quote-stripped versions for fuzzy matching
    quote_stripped = _strip_quotes_for_matching(normalized_quote)
    transcript_stripped = _strip_quotes_for_matching(normalized_transcript)

    logger.debug("Searching for quote, first 60 chars: %s", repr(normalized_quote[:60]))

    def find_in_stripped_and_map_back(search_text: str, full_search: bool = True) -> int | None:
        """Find text in stripped transcript and map index back to canonical."""
        stripped_search = _strip_quotes_for_matching(search_text)
        stripped_idx = transcript_stripped.find(stripped_search)

        if stripped_idx == -1:
            return None

        # Map back to canonical position by counting removed quotes
        quotes_before = (
            normalized_transcript[:stripped_idx].count("'") +
            normalized_transcript[:stripped_idx].count('"')
        )
        approx_idx = stripped_idx + quotes_before

        # Search in a small window around the approximate position
        # to find the exact match in the normalized transcript
        search_window = 100
        start_search = max(0, approx_idx - search_window)
        end_search = min(len(normalized_transcript), approx_idx + search_window)

        # Find a small key phrase to anchor the position
        key_len = min(15, len(search_text))
        key_phrase = _strip_quotes_for_matching(search_text[:key_len].lower())

        for pos in range(start_search, end_search):
            window_stripped = _strip_quotes_for_matching(normalized_transcript[pos:pos+key_len+10])
            if window_stripped.startswith(key_phrase):
                return pos

        # Fallback to approximate position
        return approx_idx

    # Try exact match first
    idx = normalized_transcript.find(normalized_quote)

    if idx == -1:
        # Try matching with quote marks stripped (handles ' vs " differences)
        mapped_idx = find_in_stripped_and_map_back(normalized_quote)
        if mapped_idx is not None:
            idx = mapped_idx
            logger.debug("Found match with quote-stripped text at idx %d", idx)
            end_idx = min(idx + len(normalized_quote) + 10, len(canonical_transcript))
        else:
            # Try matching with progressively shorter snippets (quote-stripped)
            for snippet_len in [40, 30, 20, 15]:
                if len(quote_stripped) > snippet_len:
                    start_snippet = quote_stripped[:snippet_len]
                    mapped_idx = find_in_stripped_and_map_back(normalized_quote[:snippet_len])

                    if mapped_idx is not None:
                        idx = mapped_idx
                        logger.debug("Found match with %d-char stripped snippet at idx %d", snippet_len, idx)
                        # Found start, estimate end based on quote length
                        # Cap at reasonable length to avoid huge segments
                        estimated_end = min(idx + len(normalized_quote), idx + 500, len(canonical_transcript))
                        end_idx = estimated_end
                        break
            else:
                # No match found with any snippet length
                return None
    else:
        logger.debug("Found exact match at idx %d", idx)
        end_idx = idx + len(normalized_quote)

    # Create preview (first ~100 chars)
    text_preview = canonical_transcript[idx:min(idx + 100, end_idx)]
    if len(canonical_transcript[idx:end_idx]) > 100:
        text_preview += "..."

    # Estimate token count from actual matched text
    matched_text = canonical_transcript[idx:end_idx]
    token_count = estimate_token_count(matched_text)

    return SegmentRef(
        start_offset=idx,
        end_offset=end_idx,
        token_count=token_count,
        text_preview=text_preview,
        canonical_hash=canonical_hash,
    )


def parse_llm_response(response_text: str) -> list[dict[str, Any]]:
    """Parse LLM response JSON into theme dictionaries.

    Args:
        response_text: Raw LLM response text

    Returns:
        List of theme dictionaries
    """
    # Try to extract JSON from response
    try:
        # First try direct parse
        data = json.loads(response_text)
        return data.get("themes", [])
    except json.JSONDecodeError:
        pass

    # Try to find JSON in response
    json_match = re.search(r'\{[\s\S]*"themes"[\s\S]*\}', response_text)
    if json_match:
        try:
            data = json.loads(json_match.group())
            return data.get("themes", [])
        except json.JSONDecodeError:
            pass

    logger.error("Failed to parse LLM response as JSON: %s", response_text[:500])
    return []


async def propose_themes(
    transcript: str,
    llm_client: LLMClient | None = None,
) -> list[Theme]:
    """Analyze transcript and propose themes for Ideas Edition.

    Args:
        transcript: Raw transcript text
        llm_client: Optional LLM client (creates default if not provided)

    Returns:
        List of Theme objects with supporting segments
    """
    if not transcript or not transcript.strip():
        logger.warning("Empty transcript provided to propose_themes")
        return []

    # Canonicalize transcript for offset references
    canonical_transcript = canonicalize(transcript)
    canonical_hash = compute_hash(canonical_transcript)
    transcript_length = len(canonical_transcript)

    logger.info(
        "Proposing themes for transcript",
        extra={
            "transcript_length": transcript_length,
            "canonical_hash": canonical_hash[:16] + "...",
        }
    )

    # Create LLM client if not provided
    if llm_client is None:
        llm_client = LLMClient()

    # Build prompt
    prompt = THEME_PROPOSAL_PROMPT + transcript[:50000]  # Cap at ~50k chars

    # Create LLM request
    request = LLMRequest(
        messages=[
            ChatMessage(role="user", content=prompt),
        ],
        model="gpt-4o",  # Use GPT-4o for better theme extraction
        temperature=0.3,  # Lower temperature for more deterministic quote extraction
        max_tokens=4000,
        response_format=ResponseFormat(type="json_object"),
    )

    # Call LLM
    response = await llm_client.generate(request)

    if not response.text:
        logger.error("LLM returned empty response for theme proposal")
        return []

    # Parse response
    theme_dicts = parse_llm_response(response.text)

    if not theme_dicts:
        logger.error("No themes parsed from LLM response")
        return []

    logger.info("Parsed %d themes from LLM response", len(theme_dicts))

    # Log a sample of quotes for debugging
    for td in theme_dicts[:2]:
        quotes = td.get("supporting_quotes", [])[:2]
        for q in quotes:
            logger.info("LLM quote sample: %s", q[:100] if q else "(empty)")

    # Convert to Theme objects with proper segment refs
    themes: list[Theme] = []

    for i, theme_dict in enumerate(theme_dicts):
        theme_id = str(uuid.uuid4())[:8]

        # Find supporting segments from quotes
        supporting_segments: list[SegmentRef] = []
        quotes = theme_dict.get("supporting_quotes", [])

        for quote in quotes:
            if not isinstance(quote, str):
                continue

            segment = find_quote_in_transcript(
                quote,
                canonical_transcript,
                canonical_hash,
            )

            if segment:
                supporting_segments.append(segment)
            else:
                logger.warning(
                    "Could not find quote in transcript: %s...",
                    quote[:50] if quote else "(empty)"
                )

        # Calculate coverage
        coverage = score_coverage(supporting_segments, transcript_length)

        theme = Theme(
            id=theme_id,
            title=theme_dict.get("title", f"Theme {i + 1}"),
            one_liner=theme_dict.get("one_liner", ""),
            keywords=theme_dict.get("keywords", []),
            coverage=coverage,
            supporting_segments=supporting_segments,
            include_in_generation=True,
        )

        themes.append(theme)

        logger.info(
            "Created theme: %s with %d segments, coverage=%s",
            theme.title,
            len(supporting_segments),
            coverage.value,
        )

    return themes
