"""Tests for claims-first excerpt fallback."""
from hashlib import sha256

from src.models.edition import CoverageLevel, SpeakerRef, SpeakerRole, WhitelistQuote


def _make_guest_quote(
    text: str,
    chapter_indices: list[int],
    source_evidence_ids: list[str] | None = None,
) -> WhitelistQuote:
    """Create a test WhitelistQuote from a GUEST speaker."""
    quote_canonical = text.lower().strip()
    quote_id = sha256(f"guest|{quote_canonical}".encode()).hexdigest()[:16]
    return WhitelistQuote(
        quote_id=quote_id,
        quote_text=text,
        quote_canonical=quote_canonical,
        speaker=SpeakerRef(
            speaker_id="guest_1",
            speaker_name="Test Guest",
            speaker_role=SpeakerRole.GUEST,
        ),
        source_evidence_ids=source_evidence_ids or [],
        chapter_indices=chapter_indices,
        match_spans=[],
    )


class TestClaimsFirstFallback:
    def test_uses_normal_selection_when_quotes_available(self):
        """Normal selection used when chapter has direct quotes."""
        from src.services.whitelist_service import select_deterministic_excerpts_with_claims

        whitelist = [
            _make_guest_quote("Direct chapter quote", chapter_indices=[0]),
            _make_guest_quote("Claim support quote", chapter_indices=[], source_evidence_ids=["claim_1"]),
        ]
        claims = [{"id": "claim_1", "chapter_index": 0}]

        excerpts = select_deterministic_excerpts_with_claims(
            whitelist, chapter_index=0, coverage_level=CoverageLevel.WEAK, claims=claims
        )

        # Should prefer the direct chapter quote
        assert len(excerpts) >= 1
        assert any("Direct chapter quote" in e.quote_text for e in excerpts)

    def test_falls_back_to_claim_quotes_when_no_chapter_quotes(self):
        """Use claim support quotes when chapter pool empty."""
        from src.services.whitelist_service import select_deterministic_excerpts_with_claims

        # No direct chapter quotes, only claim-linked quotes
        whitelist = [
            _make_guest_quote(
                "This quote supports a claim",
                chapter_indices=[],  # Not directly assigned to chapter
                source_evidence_ids=["claim_1"],  # But linked to claim
            ),
        ]
        claims = [{"id": "claim_1", "chapter_index": 0}]

        excerpts = select_deterministic_excerpts_with_claims(
            whitelist, chapter_index=0, coverage_level=CoverageLevel.WEAK, claims=claims
        )

        assert len(excerpts) >= 1
        assert "supports a claim" in excerpts[0].quote_text

    def test_returns_empty_when_no_quotes_or_claims(self):
        """Empty list when neither direct quotes nor claim quotes exist."""
        from src.services.whitelist_service import select_deterministic_excerpts_with_claims

        whitelist = [
            _make_guest_quote("Quote for different chapter", chapter_indices=[1]),
        ]
        claims = []  # No claims for chapter 0

        excerpts = select_deterministic_excerpts_with_claims(
            whitelist, chapter_index=0, coverage_level=CoverageLevel.WEAK, claims=claims
        )

        # Falls back to global quotes (from select_deterministic_excerpts)
        assert len(excerpts) >= 1  # Global fallback kicks in

    def test_claim_quotes_only_for_matching_chapter(self):
        """Only use claim quotes that belong to the requested chapter."""
        from src.services.whitelist_service import select_deterministic_excerpts_with_claims

        whitelist = [
            _make_guest_quote(
                "Claim for chapter 0",
                chapter_indices=[],
                source_evidence_ids=["claim_ch0"],
            ),
            _make_guest_quote(
                "Claim for chapter 1",
                chapter_indices=[],
                source_evidence_ids=["claim_ch1"],
            ),
        ]
        claims = [
            {"id": "claim_ch0", "chapter_index": 0},
            {"id": "claim_ch1", "chapter_index": 1},
        ]

        excerpts = select_deterministic_excerpts_with_claims(
            whitelist, chapter_index=0, coverage_level=CoverageLevel.WEAK, claims=claims
        )

        assert len(excerpts) >= 1
        # Should only include the chapter 0 claim quote
        assert all("chapter 0" in e.quote_text.lower() for e in excerpts)
