"""Unit tests for Edition, Fidelity, Coverage enums and SegmentRef, Theme models.

These tests verify:
1. Enum values are correct string values
2. Enums can be constructed from strings
3. Invalid strings are rejected with ValueError
4. SegmentRef model with canonical_hash for offset drift protection
5. Theme model for Ideas Edition
6. Project model edition fields (Task 3)
7. UpdateProjectRequest edition fields (Task 3)
8. SpeakerRole enum and SpeakerRef model for whitelist-based quote generation
"""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from src.models.edition import Coverage, Edition, Fidelity, SegmentRef, SpeakerRef, SpeakerRole, Theme
from src.models.project import Project, UpdateProjectRequest, WebinarType


class TestEditionEnum:
    """Test Edition enum."""

    def test_edition_values(self):
        """Verify Edition.QA.value == 'qa', Edition.IDEAS.value == 'ideas'."""
        assert Edition.QA.value == "qa"
        assert Edition.IDEAS.value == "ideas"

    def test_edition_from_string(self):
        """Verify Edition('qa') == Edition.QA."""
        assert Edition("qa") == Edition.QA
        assert Edition("ideas") == Edition.IDEAS


class TestFidelityEnum:
    """Test Fidelity enum."""

    def test_fidelity_values(self):
        """Verify both Fidelity values."""
        assert Fidelity.FAITHFUL.value == "faithful"
        assert Fidelity.VERBATIM.value == "verbatim"

    def test_fidelity_from_string(self):
        """Verify Fidelity can be constructed from strings."""
        assert Fidelity("faithful") == Fidelity.FAITHFUL
        assert Fidelity("verbatim") == Fidelity.VERBATIM


class TestCoverageEnum:
    """Test Coverage enum."""

    def test_coverage_values(self):
        """Verify all three Coverage values."""
        assert Coverage.STRONG.value == "strong"
        assert Coverage.MEDIUM.value == "medium"
        assert Coverage.WEAK.value == "weak"

    def test_coverage_from_string(self):
        """Verify Coverage can be constructed from strings."""
        assert Coverage("strong") == Coverage.STRONG
        assert Coverage("medium") == Coverage.MEDIUM
        assert Coverage("weak") == Coverage.WEAK


class TestInvalidEnumValues:
    """Test that invalid enum values are rejected."""

    def test_invalid_enum_rejected(self):
        """Verify invalid string raises ValueError."""
        with pytest.raises(ValueError):
            Edition("invalid")

        with pytest.raises(ValueError):
            Fidelity("invalid")

        with pytest.raises(ValueError):
            Coverage("invalid")


class TestSegmentRef:
    """Test SegmentRef model for transcript segment references."""

    def test_segment_ref_creation(self):
        """Verify all fields including canonical_hash are properly set."""
        segment = SegmentRef(
            start_offset=100,
            end_offset=500,
            token_count=85,
            text_preview="This is the first ~100 characters of the segment...",
            canonical_hash="abc123def456"
        )
        assert segment.start_offset == 100
        assert segment.end_offset == 500
        assert segment.token_count == 85
        assert segment.text_preview == "This is the first ~100 characters of the segment..."
        assert segment.canonical_hash == "abc123def456"

    def test_segment_ref_validation_negative_offset(self):
        """Verify start_offset < 0 raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            SegmentRef(
                start_offset=-1,
                end_offset=100,
                token_count=50,
                text_preview="preview",
                canonical_hash="hash123"
            )
        assert "start_offset" in str(exc_info.value)

    def test_segment_ref_validation_negative_end_offset(self):
        """Verify end_offset < 0 raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            SegmentRef(
                start_offset=0,
                end_offset=-1,
                token_count=50,
                text_preview="preview",
                canonical_hash="hash123"
            )
        assert "end_offset" in str(exc_info.value)

    def test_segment_ref_validation_negative_token_count(self):
        """Verify token_count < 0 raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            SegmentRef(
                start_offset=0,
                end_offset=100,
                token_count=-1,
                text_preview="preview",
                canonical_hash="hash123"
            )
        assert "token_count" in str(exc_info.value)

    def test_segment_ref_requires_canonical_hash(self):
        """Verify canonical_hash is required (not optional)."""
        with pytest.raises(ValidationError) as exc_info:
            SegmentRef(
                start_offset=0,
                end_offset=100,
                token_count=50,
                text_preview="preview"
                # canonical_hash intentionally omitted
            )
        assert "canonical_hash" in str(exc_info.value)


class TestTheme:
    """Test Theme model for Ideas Edition."""

    def test_theme_creation(self):
        """Verify theme with all fields is created correctly."""
        theme = Theme(
            id="theme-001",
            title="Introduction to Machine Learning",
            one_liner="A primer on ML fundamentals",
            keywords=["machine learning", "AI", "algorithms"],
            coverage=Coverage.STRONG,
            supporting_segments=[],
            include_in_generation=False
        )
        assert theme.id == "theme-001"
        assert theme.title == "Introduction to Machine Learning"
        assert theme.one_liner == "A primer on ML fundamentals"
        assert theme.keywords == ["machine learning", "AI", "algorithms"]
        assert theme.coverage == Coverage.STRONG
        assert theme.supporting_segments == []
        assert theme.include_in_generation is False

    def test_theme_defaults(self):
        """Verify include_in_generation defaults to True."""
        theme = Theme(
            id="theme-002",
            title="Data Processing",
            one_liner="How to handle data",
            keywords=["data", "processing"],
            coverage=Coverage.MEDIUM,
            supporting_segments=[]
        )
        assert theme.include_in_generation is True

    def test_theme_with_segments(self):
        """Verify theme can hold a list of SegmentRefs."""
        segment1 = SegmentRef(
            start_offset=0,
            end_offset=100,
            token_count=20,
            text_preview="First segment preview...",
            canonical_hash="hash_abc"
        )
        segment2 = SegmentRef(
            start_offset=150,
            end_offset=300,
            token_count=35,
            text_preview="Second segment preview...",
            canonical_hash="hash_abc"
        )
        theme = Theme(
            id="theme-003",
            title="Advanced Topics",
            one_liner="Deep dive into advanced concepts",
            keywords=["advanced", "deep dive"],
            coverage=Coverage.WEAK,
            supporting_segments=[segment1, segment2]
        )
        assert len(theme.supporting_segments) == 2
        assert theme.supporting_segments[0].start_offset == 0
        assert theme.supporting_segments[1].start_offset == 150

    def test_serialization_roundtrip(self):
        """Verify Theme with SegmentRefs serializes/deserializes correctly."""
        segment = SegmentRef(
            start_offset=50,
            end_offset=200,
            token_count=30,
            text_preview="Sample preview text",
            canonical_hash="sha256_hash_value"
        )
        original_theme = Theme(
            id="theme-roundtrip",
            title="Roundtrip Test",
            one_liner="Testing serialization",
            keywords=["test", "serialization"],
            coverage=Coverage.STRONG,
            supporting_segments=[segment],
            include_in_generation=True
        )

        # Serialize to dict/JSON
        serialized = original_theme.model_dump()

        # Deserialize back to model
        restored_theme = Theme.model_validate(serialized)

        # Verify all fields match
        assert restored_theme.id == original_theme.id
        assert restored_theme.title == original_theme.title
        assert restored_theme.one_liner == original_theme.one_liner
        assert restored_theme.keywords == original_theme.keywords
        assert restored_theme.coverage == original_theme.coverage
        assert restored_theme.include_in_generation == original_theme.include_in_generation
        assert len(restored_theme.supporting_segments) == 1

        restored_segment = restored_theme.supporting_segments[0]
        assert restored_segment.start_offset == segment.start_offset
        assert restored_segment.end_offset == segment.end_offset
        assert restored_segment.token_count == segment.token_count
        assert restored_segment.text_preview == segment.text_preview
        assert restored_segment.canonical_hash == segment.canonical_hash


# =============================================================================
# Task 3: Project Model Edition Fields Tests
# =============================================================================


class TestProjectEditionFields:
    """Test Project model edition fields (Task 3)."""

    def test_project_has_edition_defaults(self):
        """Verify new Project has edition=QA, fidelity=FAITHFUL, themes=[]."""
        now = datetime.now(UTC)
        project = Project(
            id="proj-001",
            name="Test Project",
            webinarType=WebinarType.INTERVIEW,
            createdAt=now,
            updatedAt=now,
        )
        # Verify edition defaults
        assert project.edition == Edition.QA
        assert project.fidelity == Fidelity.FAITHFUL
        assert project.themes == []

    def test_project_with_ideas_edition(self):
        """Verify Project can be created with IDEAS edition and themes."""
        now = datetime.now(UTC)
        segment = SegmentRef(
            start_offset=0,
            end_offset=100,
            token_count=25,
            text_preview="Sample transcript text...",
            canonical_hash="abc123"
        )
        theme = Theme(
            id="theme-001",
            title="Key Concept",
            one_liner="An important idea",
            keywords=["concept", "idea"],
            coverage=Coverage.STRONG,
            supporting_segments=[segment]
        )
        project = Project(
            id="proj-002",
            name="Ideas Project",
            webinarType=WebinarType.STANDARD_PRESENTATION,
            createdAt=now,
            updatedAt=now,
            edition=Edition.IDEAS,
            fidelity=Fidelity.VERBATIM,
            themes=[theme]
        )
        assert project.edition == Edition.IDEAS
        assert project.fidelity == Fidelity.VERBATIM
        assert len(project.themes) == 1
        assert project.themes[0].title == "Key Concept"

    def test_project_canonical_transcript_fields(self):
        """Verify canonical_transcript and hash fields work."""
        now = datetime.now(UTC)
        transcript_text = "This is the canonical transcript content."
        transcript_hash = "sha256_abc123def456"

        project = Project(
            id="proj-003",
            name="Canonical Test",
            webinarType=WebinarType.INTERVIEW,
            createdAt=now,
            updatedAt=now,
            canonical_transcript=transcript_text,
            canonical_transcript_hash=transcript_hash
        )
        assert project.canonical_transcript == transcript_text
        assert project.canonical_transcript_hash == transcript_hash

        # Also test None defaults
        project_no_canonical = Project(
            id="proj-004",
            name="No Canonical",
            webinarType=WebinarType.INTERVIEW,
            createdAt=now,
            updatedAt=now,
        )
        assert project_no_canonical.canonical_transcript is None
        assert project_no_canonical.canonical_transcript_hash is None

    def test_existing_projects_get_defaults(self):
        """Verify existing projects (without edition) get QA default (backward compat).

        This simulates loading a project from the database that was created
        before the edition fields were added.
        """
        now = datetime.now(UTC)
        # Simulate data from database without edition fields
        legacy_data = {
            "id": "proj-legacy",
            "name": "Legacy Project",
            "webinarType": "interview",
            "createdAt": now,
            "updatedAt": now,
            "transcriptText": "Some transcript",
            "outlineItems": [],
            "resources": [],
            "visuals": [],
            "draftText": "",
            # Note: no edition, fidelity, themes, canonical_transcript, canonical_transcript_hash
        }
        project = Project.model_validate(legacy_data)

        # Should get defaults
        assert project.edition == Edition.QA
        assert project.fidelity == Fidelity.FAITHFUL
        assert project.themes == []
        assert project.canonical_transcript is None
        assert project.canonical_transcript_hash is None


class TestUpdateProjectRequestEditionFields:
    """Test UpdateProjectRequest accepts edition fields (Task 3)."""

    def test_update_project_request_accepts_edition(self):
        """Verify UpdateProjectRequest accepts edition fields."""
        segment = SegmentRef(
            start_offset=0,
            end_offset=50,
            token_count=10,
            text_preview="Preview...",
            canonical_hash="hash123"
        )
        theme = Theme(
            id="theme-upd",
            title="Update Theme",
            one_liner="A theme for update",
            keywords=["update"],
            coverage=Coverage.MEDIUM,
            supporting_segments=[segment]
        )

        request = UpdateProjectRequest(
            name="Updated Project",
            webinarType=WebinarType.INTERVIEW,
            edition=Edition.IDEAS,
            fidelity=Fidelity.VERBATIM,
            themes=[theme]
        )

        assert request.edition == Edition.IDEAS
        assert request.fidelity == Fidelity.VERBATIM
        assert len(request.themes) == 1
        assert request.themes[0].id == "theme-upd"

    def test_update_project_request_edition_optional(self):
        """Verify edition fields are optional in UpdateProjectRequest."""
        # Create request without edition fields
        request = UpdateProjectRequest(
            name="Minimal Update",
            webinarType=WebinarType.STANDARD_PRESENTATION,
        )

        # All edition fields should be None (not set)
        assert request.edition is None
        assert request.fidelity is None
        assert request.themes is None


# =============================================================================
# Task 1: SpeakerRole Enum and SpeakerRef Model Tests (Whitelist-based Quote Generation)
# =============================================================================


class TestSpeakerModels:
    """Test SpeakerRole enum and SpeakerRef model for whitelist-based quote generation."""

    def test_speaker_role_values(self):
        """Test SpeakerRole enum has expected values."""
        assert SpeakerRole.HOST == "host"
        assert SpeakerRole.GUEST == "guest"
        assert SpeakerRole.CALLER == "caller"
        assert SpeakerRole.CLIP == "clip"
        assert SpeakerRole.UNCLEAR == "unclear"

    def test_speaker_role_from_string(self):
        """Test SpeakerRole can be constructed from strings."""
        assert SpeakerRole("host") == SpeakerRole.HOST
        assert SpeakerRole("guest") == SpeakerRole.GUEST
        assert SpeakerRole("caller") == SpeakerRole.CALLER
        assert SpeakerRole("clip") == SpeakerRole.CLIP
        assert SpeakerRole("unclear") == SpeakerRole.UNCLEAR

    def test_speaker_role_invalid_value_rejected(self):
        """Test invalid SpeakerRole value raises ValueError."""
        with pytest.raises(ValueError):
            SpeakerRole("invalid_role")

    def test_speaker_ref_creation(self):
        """Test SpeakerRef model creation."""
        ref = SpeakerRef(
            speaker_id="david_deutsch",
            speaker_name="David Deutsch",
            speaker_role=SpeakerRole.GUEST,
        )
        assert ref.speaker_id == "david_deutsch"
        assert ref.speaker_name == "David Deutsch"
        assert ref.speaker_role == SpeakerRole.GUEST

    def test_speaker_ref_with_host_role(self):
        """Test SpeakerRef with HOST role."""
        ref = SpeakerRef(
            speaker_id="sam_harris",
            speaker_name="Sam Harris",
            speaker_role=SpeakerRole.HOST,
        )
        assert ref.speaker_id == "sam_harris"
        assert ref.speaker_name == "Sam Harris"
        assert ref.speaker_role == SpeakerRole.HOST

    def test_speaker_ref_requires_all_fields(self):
        """Test SpeakerRef requires speaker_id, speaker_name, and speaker_role."""
        with pytest.raises(ValidationError) as exc_info:
            SpeakerRef(
                speaker_id="test_id",
                speaker_name="Test Name",
                # speaker_role intentionally omitted
            )
        assert "speaker_role" in str(exc_info.value)

    def test_speaker_ref_forbids_extra_fields(self):
        """Test SpeakerRef forbids extra fields."""
        with pytest.raises(ValidationError) as exc_info:
            SpeakerRef(
                speaker_id="test_id",
                speaker_name="Test Name",
                speaker_role=SpeakerRole.GUEST,
                extra_field="not allowed",
            )
        assert "extra_field" in str(exc_info.value).lower() or "extra" in str(exc_info.value).lower()

    def test_speaker_ref_serialization_roundtrip(self):
        """Test SpeakerRef serializes and deserializes correctly."""
        original = SpeakerRef(
            speaker_id="brett_hall",
            speaker_name="Brett Hall",
            speaker_role=SpeakerRole.HOST,
        )
        serialized = original.model_dump()
        restored = SpeakerRef.model_validate(serialized)

        assert restored.speaker_id == original.speaker_id
        assert restored.speaker_name == original.speaker_name
        assert restored.speaker_role == original.speaker_role


# =============================================================================
# Task 2: TranscriptPair and WhitelistQuote Models (Whitelist-based Quote Generation)
# =============================================================================


class TestWhitelistModels:
    """Test TranscriptPair and WhitelistQuote models for whitelist-based quote generation."""

    def test_transcript_pair_creation(self):
        """Test TranscriptPair holds raw and canonical."""
        from src.models.edition import TranscriptPair

        pair = TranscriptPair(
            raw='He said "hello"—goodbye',
            canonical='he said "hello"-goodbye',
        )
        assert pair.raw == 'He said "hello"—goodbye'
        assert pair.canonical == 'he said "hello"-goodbye'

    def test_whitelist_quote_creation(self):
        """Test WhitelistQuote model creation."""
        from src.models.edition import TranscriptPair, WhitelistQuote

        speaker = SpeakerRef(
            speaker_id="david_deutsch",
            speaker_name="David Deutsch",
            speaker_role=SpeakerRole.GUEST,
        )
        quote = WhitelistQuote(
            quote_id="abc123def456",
            quote_text="Wisdom is limitless",
            quote_canonical="wisdom is limitless",
            speaker=speaker,
            source_evidence_ids=["ev1", "ev2"],
            chapter_indices=[0, 1],
            match_spans=[(100, 120)],
        )
        assert quote.quote_id == "abc123def456"
        assert quote.speaker.speaker_role == SpeakerRole.GUEST
        assert 0 in quote.chapter_indices
