"""AI service for transcript processing and content suggestions.

Provides AI-powered features:
- Transcript cleanup (remove filler words, fix punctuation, organize paragraphs)
- Outline suggestion (extract structure from transcript)
- Resource suggestion (identify relevant resources)
"""

from src.llm import ChatMessage, LLMClient, LLMRequest, ResponseFormat

# Maximum transcript length (enforced at API level too)
MAX_TRANSCRIPT_LENGTH = 50_000

# System prompts per research.md
CLEAN_TRANSCRIPT_PROMPT = """You are a transcript editor. Clean up the following raw transcript by:
- Removing filler words (um, uh, like, you know)
- Fixing punctuation and capitalization
- Organizing into logical paragraphs
- Preserving the speaker's meaning and tone
- Keeping technical terms and proper nouns intact

Return only the cleaned transcript text, no explanations."""


async def clean_transcript(transcript: str) -> str:
    """Clean up a raw transcript using AI.

    Args:
        transcript: The raw transcript text to clean up.

    Returns:
        The cleaned transcript text.

    Raises:
        LLMError: If the AI request fails after retries and fallback.
    """
    client = LLMClient()

    request = LLMRequest(
        messages=[
            ChatMessage(role="system", content=CLEAN_TRANSCRIPT_PROMPT),
            ChatMessage(role="user", content=transcript),
        ],
        model="",  # Use provider default
        temperature=0.3,  # Lower temperature for more consistent cleanup
        max_tokens=16000,  # Allow long output for full transcript
    )

    response = await client.generate(request)

    # Return the cleaned text (or empty string if no text)
    return response.text or ""
