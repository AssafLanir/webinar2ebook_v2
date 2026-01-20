"""Coverage analysis API routes.

Provides preflight coverage analysis before draft generation.
"""
import re
from hashlib import sha256

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.models.edition import (
    CoverageReport,
    SpeakerRef,
    SpeakerRole,
    WhitelistQuote,
)
from src.services.whitelist_service import (
    canonicalize_transcript,
    generate_coverage_report,
)

router = APIRouter(prefix="/coverage", tags=["coverage"])


class PreflightRequest(BaseModel):
    """Request for preflight coverage analysis."""

    transcript: str = Field(description="Raw transcript text")
    chapter_count: int = Field(
        default=4, ge=1, le=10, description="Number of chapters planned"
    )
    known_guests: list[str] = Field(
        default_factory=list, description="Known guest speaker names"
    )
    known_hosts: list[str] = Field(
        default_factory=list, description="Known host speaker names"
    )


class PreflightResponse(BaseModel):
    """Response with coverage analysis."""

    report: CoverageReport
    recommendations: list[str] = Field(default_factory=list)


@router.post("/preflight", response_model=PreflightResponse)
async def preflight_coverage(request: PreflightRequest) -> PreflightResponse:
    """Analyze transcript coverage before generation.

    Returns predicted word count ranges and feasibility assessment.
    Use this to determine if the transcript has enough evidence
    for the planned chapter structure.
    """
    try:
        # Canonicalize transcript
        canonical = canonicalize_transcript(request.transcript)
        transcript_hash = sha256(canonical.encode()).hexdigest()[:32]

        # Build whitelist (simplified - full version would need evidence_map)
        # For preflight, we do a simple text scan
        whitelist = build_quote_whitelist_simple(
            raw_transcript=request.transcript,
            canonical_transcript=canonical,
            known_guests=request.known_guests,
            known_hosts=request.known_hosts,
        )

        # Generate coverage report
        report = generate_coverage_report(
            whitelist=whitelist,
            chapter_count=request.chapter_count,
            transcript_hash=transcript_hash,
        )

        # Build recommendations
        recommendations = []
        if not report.is_feasible:
            recommendations.append(
                "Consider reducing chapter count or using a different transcript"
            )

        for note in report.feasibility_notes:
            recommendations.append(note)

        # Add word count guidance
        min_words, max_words = report.predicted_total_range
        if max_words < 2000:
            recommendations.append(
                f"Predicted output is short ({min_words}-{max_words} words). "
                "Consider adding more source material."
            )
        elif min_words > 8000:
            recommendations.append(
                f"Predicted output is long ({min_words}-{max_words} words). "
                "Consider splitting into multiple documents."
            )

        return PreflightResponse(
            report=report,
            recommendations=recommendations,
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Coverage analysis failed: {str(e)}"
        ) from e


def build_quote_whitelist_simple(
    raw_transcript: str,
    canonical_transcript: str,
    known_guests: list[str],
    known_hosts: list[str],
) -> list[WhitelistQuote]:
    """Build a simple whitelist for preflight analysis.

    This is a simplified version that doesn't require an evidence map.
    It extracts potential quotes from the transcript directly.

    Args:
        raw_transcript: Original transcript text.
        canonical_transcript: Normalized transcript.
        known_guests: Known guest names.
        known_hosts: Known host names.

    Returns:
        List of WhitelistQuote objects.
    """
    whitelist = []

    # Simple pattern: look for quoted text or speaker-labeled segments
    # Pattern: "Speaker: text" or "SPEAKER: text"
    speaker_pattern = re.compile(
        r"^([A-Z][A-Za-z\s]+):\s*(.+?)(?=\n[A-Z][A-Za-z\s]+:|$)",
        re.MULTILINE | re.DOTALL,
    )

    for match in speaker_pattern.finditer(raw_transcript):
        speaker_name = match.group(1).strip()
        text = match.group(2).strip()

        # Skip very short segments
        if len(text.split()) < 5:
            continue

        # Determine speaker role
        speaker_lower = speaker_name.lower()
        if any(guest.lower() in speaker_lower for guest in known_guests):
            role = SpeakerRole.GUEST
        elif any(host.lower() in speaker_lower for host in known_hosts):
            role = SpeakerRole.HOST
        else:
            role = SpeakerRole.UNCLEAR

        # Extract sentences as potential quotes
        sentences = re.split(r"[.!?]+", text)
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence.split()) < 5:
                continue

            canonical = sentence.lower()
            quote_id = sha256(f"{speaker_name}|{canonical}".encode()).hexdigest()[:16]

            # Find position in canonical transcript
            start = canonical_transcript.lower().find(canonical[:50])
            spans = [(start, start + len(sentence))] if start >= 0 else []

            whitelist.append(
                WhitelistQuote(
                    quote_id=quote_id,
                    quote_text=sentence,
                    quote_canonical=canonical,
                    speaker=SpeakerRef(
                        speaker_id=speaker_name.lower().replace(" ", "_"),
                        speaker_name=speaker_name,
                        speaker_role=role,
                    ),
                    source_evidence_ids=[],
                    chapter_indices=list(range(4)),  # Assign to all chapters initially
                    match_spans=spans,
                )
            )

    return whitelist
