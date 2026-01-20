"""Tests for speaker quota-based excerpt selection."""
from hashlib import sha256

from src.models.edition import SpeakerRef, SpeakerRole, WhitelistQuote


def _make_quote(
    text: str,
    chapter_indices: list[int],
    role: SpeakerRole = SpeakerRole.GUEST,
) -> WhitelistQuote:
    """Create a test WhitelistQuote."""
    quote_canonical = text.lower().strip()
    speaker_id = f"{role.value}_1"
    quote_id = sha256(f"{speaker_id}|{quote_canonical}".encode()).hexdigest()[:16]
    return WhitelistQuote(
        quote_id=quote_id,
        quote_text=text,
        quote_canonical=quote_canonical,
        speaker=SpeakerRef(
            speaker_id=speaker_id,
            speaker_name=f"Test {role.value.title()}",
            speaker_role=role,
        ),
        source_evidence_ids=[],
        chapter_indices=chapter_indices,
        match_spans=[],
    )


class TestSelectExcerptsWithSpeakerQuota:
    def test_prefers_guest_quotes(self):
        """GUEST quotes are preferred over HOST."""
        from src.services.whitelist_service import select_excerpts_with_speaker_quota

        whitelist = [
            _make_quote("Guest quote one", [0], SpeakerRole.GUEST),
            _make_quote("Guest quote two", [0], SpeakerRole.GUEST),
            _make_quote("Host quote one", [0], SpeakerRole.HOST),
        ]

        excerpts = select_excerpts_with_speaker_quota(
            whitelist, chapter_index=0, count=2
        )

        assert len(excerpts) == 2
        # Both should be GUEST since we have enough
        assert all(e.speaker.speaker_role == SpeakerRole.GUEST for e in excerpts)

    def test_fills_with_host_when_guest_insufficient(self):
        """HOST quotes used to meet count when GUEST insufficient."""
        from src.services.whitelist_service import select_excerpts_with_speaker_quota

        whitelist = [
            _make_quote("Guest quote one", [0], SpeakerRole.GUEST),
            _make_quote("Host quote one", [0], SpeakerRole.HOST),
            _make_quote("Host quote two", [0], SpeakerRole.HOST),
        ]

        excerpts = select_excerpts_with_speaker_quota(
            whitelist, chapter_index=0, count=2
        )

        assert len(excerpts) == 2
        # Should have 1 GUEST + 1 HOST
        guest_count = sum(1 for e in excerpts if e.speaker.speaker_role == SpeakerRole.GUEST)
        host_count = sum(1 for e in excerpts if e.speaker.speaker_role == SpeakerRole.HOST)
        assert guest_count == 1
        assert host_count == 1

    def test_uses_host_only_when_no_guest(self):
        """HOST-only quotes used when no GUEST available."""
        from src.services.whitelist_service import select_excerpts_with_speaker_quota

        whitelist = [
            _make_quote("Host quote one", [0], SpeakerRole.HOST),
            _make_quote("Host quote two", [0], SpeakerRole.HOST),
            _make_quote("Host quote three", [0], SpeakerRole.HOST),
        ]

        excerpts = select_excerpts_with_speaker_quota(
            whitelist, chapter_index=0, count=2
        )

        assert len(excerpts) == 2
        # All HOST since no GUEST
        assert all(e.speaker.speaker_role == SpeakerRole.HOST for e in excerpts)

    def test_respects_max_non_guest_quota(self):
        """Non-GUEST quotes limited to 20% of selection."""
        from src.services.whitelist_service import select_excerpts_with_speaker_quota

        # 5 GUEST, 5 HOST - with count=5 and 20% quota, max 1 HOST
        whitelist = [
            _make_quote(f"Guest quote {i}", [0], SpeakerRole.GUEST) for i in range(5)
        ] + [
            _make_quote(f"Host quote {i}", [0], SpeakerRole.HOST) for i in range(5)
        ]

        excerpts = select_excerpts_with_speaker_quota(
            whitelist, chapter_index=0, count=5
        )

        assert len(excerpts) == 5
        host_count = sum(1 for e in excerpts if e.speaker.speaker_role == SpeakerRole.HOST)
        # With 5 total, 20% = 1 max HOST
        assert host_count <= 1

    def test_filters_by_chapter_index(self):
        """Only quotes for specified chapter are considered."""
        from src.services.whitelist_service import select_excerpts_with_speaker_quota

        whitelist = [
            _make_quote("Chapter 0 guest", [0], SpeakerRole.GUEST),
            _make_quote("Chapter 1 guest", [1], SpeakerRole.GUEST),
            _make_quote("Chapter 0 host", [0], SpeakerRole.HOST),
        ]

        excerpts = select_excerpts_with_speaker_quota(
            whitelist, chapter_index=0, count=2
        )

        assert len(excerpts) == 2
        # Only chapter 0 quotes
        assert all(0 in e.chapter_indices for e in excerpts)
        assert not any("Chapter 1" in e.quote_text for e in excerpts)

    def test_deterministic_ordering(self):
        """Results are deterministically ordered."""
        from src.services.whitelist_service import select_excerpts_with_speaker_quota

        whitelist = [
            _make_quote("Short", [0], SpeakerRole.GUEST),
            _make_quote("A longer quote text here", [0], SpeakerRole.GUEST),
            _make_quote("Medium quote", [0], SpeakerRole.GUEST),
        ]

        excerpts1 = select_excerpts_with_speaker_quota(whitelist, 0, 2)
        excerpts2 = select_excerpts_with_speaker_quota(whitelist, 0, 2)

        # Same order each time
        assert [e.quote_id for e in excerpts1] == [e.quote_id for e in excerpts2]
        # Longest first
        assert len(excerpts1[0].quote_text) >= len(excerpts1[1].quote_text)

    def test_returns_empty_when_no_quotes_for_chapter(self):
        """Returns empty list when no quotes for chapter."""
        from src.services.whitelist_service import select_excerpts_with_speaker_quota

        whitelist = [
            _make_quote("Chapter 1 guest", [1], SpeakerRole.GUEST),
        ]

        excerpts = select_excerpts_with_speaker_quota(
            whitelist, chapter_index=0, count=2
        )

        assert len(excerpts) == 0
