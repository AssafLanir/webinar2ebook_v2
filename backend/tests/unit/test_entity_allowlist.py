"""Tests for entity allowlist - org/product vs person name handling."""

import pytest
from src.services.entity_allowlist import (
    build_person_blacklist,
    build_entity_allowlist,
    extract_entity_candidates,
    classify_entity,
    PersonBlacklist,
    EntityAllowlist,
)
from src.services import draft_service


class TestPersonBlacklist:
    """Tests for building person blacklist from speakers."""

    def test_builds_from_speaker_dicts(self):
        """Build blacklist from speaker metadata."""
        speakers = [
            {"speaker_name": "David Deutsch"},
            {"speaker_name": "Lex Fridman"},
        ]

        blacklist = build_person_blacklist(speakers)

        assert "David Deutsch" in blacklist.full_names
        assert "Lex Fridman" in blacklist.full_names
        assert "Deutsch" in blacklist.last_names
        assert "Fridman" in blacklist.last_names

    def test_matches_full_name(self):
        """Blacklist matches full names."""
        blacklist = PersonBlacklist(
            full_names={"David Deutsch"},
            last_names={"Deutsch"},
        )

        assert blacklist.matches("David Deutsch says hello")
        assert blacklist.matches("As David Deutsch noted")

    def test_matches_last_name(self):
        """Blacklist matches last names with word boundaries."""
        blacklist = PersonBlacklist(
            full_names={"David Deutsch"},
            last_names={"Deutsch"},
        )

        assert blacklist.matches("Deutsch argues that")
        assert not blacklist.matches("The German language")  # "Deutsch" means German

    def test_handles_empty_speakers(self):
        """Gracefully handles empty speaker list."""
        blacklist = build_person_blacklist([])

        assert len(blacklist.full_names) == 0
        assert len(blacklist.last_names) == 0


class TestEntityAllowlist:
    """Tests for building entity allowlist from transcript."""

    def test_extracts_org_with_suffix(self):
        """Extracts organizations with standard suffixes."""
        transcript = "We use Amazon Web Services and Acme Corp for hosting."

        allowlist = build_entity_allowlist(transcript)

        assert "Amazon Web Services" in allowlist.org_names or allowlist.contains("Amazon Web Services")
        assert "Acme Corp" in allowlist.org_names or allowlist.contains("Acme Corp")

    def test_extracts_allcaps_acronyms(self):
        """Extracts ALLCAPS acronyms as products."""
        transcript = "AWS and CRM are essential tools. We also use API endpoints."

        allowlist = build_entity_allowlist(transcript)

        assert allowlist.contains("AWS")
        assert allowlist.contains("CRM")
        assert allowlist.contains("API")

    def test_extracts_camelcase_products(self):
        """Extracts CamelCase product names."""
        transcript = "We use GitHub for code and LinkedIn for networking."

        allowlist = build_entity_allowlist(transcript)

        assert allowlist.contains("GitHub")
        assert allowlist.contains("LinkedIn")

    def test_filters_out_person_names(self):
        """Known person names are not added to allowlist."""
        transcript = "David Deutsch and Stephen Hawking discussed AWS."
        person_blacklist = PersonBlacklist(
            full_names={"David Deutsch", "Stephen Hawking"},
            last_names={"Deutsch", "Hawking"},
        )

        allowlist = build_entity_allowlist(transcript, person_blacklist)

        assert not allowlist.contains("David Deutsch")
        assert not allowlist.contains("Stephen Hawking")
        assert allowlist.contains("AWS")  # But AWS is still extracted


class TestClassifyEntity:
    """Tests for entity classification logic."""

    def test_classifies_org_suffix(self):
        """Entities with org suffixes are classified as ORG."""
        blacklist = PersonBlacklist()

        assert classify_entity("Acme Corp", blacklist) == "ORG"
        assert classify_entity("Google Cloud", blacklist) == "ORG"
        assert classify_entity("Microsoft Technologies", blacklist) == "ORG"

    def test_classifies_allcaps_as_product_or_org(self):
        """ALLCAPS tokens are classified as PRODUCT or ORG based on domain tokens."""
        blacklist = PersonBlacklist()

        # Pure acronyms → PRODUCT
        assert classify_entity("AWS", blacklist) == "PRODUCT"
        assert classify_entity("GCP", blacklist) == "PRODUCT"

        # Domain tokens (even if ALLCAPS) → ORG
        assert classify_entity("CRM", blacklist) == "ORG"  # In DOMAIN_TOKENS
        assert classify_entity("API", blacklist) == "ORG"  # In DOMAIN_TOKENS
        assert classify_entity("SDK", blacklist) == "ORG"  # In DOMAIN_TOKENS

    def test_classifies_camelcase_as_product(self):
        """CamelCase tokens are classified as PRODUCT."""
        blacklist = PersonBlacklist()

        assert classify_entity("GitHub", blacklist) == "PRODUCT"
        assert classify_entity("LinkedIn", blacklist) == "PRODUCT"

    def test_classifies_known_person(self):
        """Known speakers are classified as PERSON."""
        blacklist = PersonBlacklist(
            full_names={"David Deutsch"},
            last_names={"Deutsch"},
        )

        assert classify_entity("David Deutsch", blacklist) == "PERSON"
        assert classify_entity("Deutsch", blacklist) == "PERSON"

    def test_classifies_common_first_name_pattern(self):
        """Two-word names starting with common first name are PERSON."""
        blacklist = PersonBlacklist()

        assert classify_entity("John Smith", blacklist) == "PERSON"
        assert classify_entity("Jane Doe", blacklist) == "PERSON"


class TestEnforceNoNamesInProseDynamic:
    """Tests for dynamic person/org handling in prose enforcement."""

    def test_drops_speaker_name_dynamic(self):
        """Speaker names are dropped using dynamic blacklist."""
        text = """## Chapter 1: First

David Deutsch argues that progress is infinite. The idea is transformative.

### Key Excerpts"""

        person_blacklist = PersonBlacklist(
            full_names={"David Deutsch"},
            last_names={"Deutsch"},
        )

        result, report = draft_service.enforce_no_names_in_prose(
            text, person_blacklist=person_blacklist
        )

        assert "David Deutsch" not in result
        assert "The idea is transformative" in result
        assert report["sentences_dropped"] >= 1

    def test_preserves_allowlisted_org(self):
        """Org names in allowlist are preserved in prose."""
        text = """## Chapter 1: First

We use Amazon Web Services for cloud hosting. The platform is robust.

### Key Excerpts"""

        person_blacklist = PersonBlacklist()
        entity_allowlist = EntityAllowlist(
            org_names={"Amazon Web Services"},
        )

        result, report = draft_service.enforce_no_names_in_prose(
            text, person_blacklist=person_blacklist, entity_allowlist=entity_allowlist
        )

        # Sentence with org name should be preserved
        assert "Amazon Web Services" in result
        assert "The platform is robust" in result
        assert report["sentences_dropped"] == 0

    def test_preserves_allowlisted_acronym(self):
        """ALLCAPS acronyms in allowlist are preserved."""
        text = """## Chapter 1: First

AWS provides excellent cloud services. The API is well-documented.

### Key Excerpts"""

        person_blacklist = PersonBlacklist()
        entity_allowlist = EntityAllowlist(
            acronyms={"AWS", "API"},
        )

        result, report = draft_service.enforce_no_names_in_prose(
            text, person_blacklist=person_blacklist, entity_allowlist=entity_allowlist
        )

        assert "AWS" in result
        assert "API" in result
        assert report["sentences_dropped"] == 0

    def test_drops_unknown_person_not_in_allowlist(self):
        """Person-looking names not in allowlist are dropped."""
        text = """## Chapter 1: First

John Smith presented the findings. The results were surprising.

### Key Excerpts"""

        person_blacklist = PersonBlacklist(
            full_names={"John Smith"},
            last_names={"Smith"},
        )
        entity_allowlist = EntityAllowlist()  # Empty allowlist

        result, report = draft_service.enforce_no_names_in_prose(
            text, person_blacklist=person_blacklist, entity_allowlist=entity_allowlist
        )

        assert "John Smith" not in result
        assert "The results were surprising" in result
        assert report["sentences_dropped"] >= 1

    def test_legacy_mode_still_works(self):
        """Without dynamic blacklist, legacy hardcoded names still work."""
        text = """## Chapter 1: First

Deutsch argues that progress is infinite. The idea is transformative.

### Key Excerpts"""

        # No blacklist provided - should use legacy mode
        result, report = draft_service.enforce_no_names_in_prose(text)

        assert "Deutsch" not in result
        assert "The idea is transformative" in result
        assert report["sentences_dropped"] >= 1

    def test_preserves_key_excerpts(self):
        """Key Excerpts are never touched."""
        text = """## Chapter 1: First

Clean prose here.

### Key Excerpts

> "David Deutsch says this is important."
> — David Deutsch (GUEST)"""

        person_blacklist = PersonBlacklist(
            full_names={"David Deutsch"},
            last_names={"Deutsch"},
        )

        result, report = draft_service.enforce_no_names_in_prose(
            text, person_blacklist=person_blacklist
        )

        assert "David Deutsch" in result  # In Key Excerpts
        assert report["sentences_dropped"] == 0

    def test_preserves_core_claims(self):
        """Core Claims are never touched."""
        text = """## Chapter 1: First

Clean prose here.

### Core Claims

- **The claim by Deutsch**: "Progress is infinite."
"""

        person_blacklist = PersonBlacklist(
            full_names={"David Deutsch"},
            last_names={"Deutsch"},
        )

        result, report = draft_service.enforce_no_names_in_prose(
            text, person_blacklist=person_blacklist
        )

        assert "Deutsch" in result  # In Core Claims
        assert report["sentences_dropped"] == 0


class TestEndToEndEntityHandling:
    """End-to-end tests for realistic scenarios."""

    def test_marketing_webinar_preserves_product_names(self):
        """Marketing webinar with product names preserves them."""
        transcript = """
        HOST: Welcome to our webinar on Salesforce CRM.
        GUEST: Thanks for having me. Salesforce CRM has transformed how we work.
        We use it alongside AWS for our infrastructure.
        """

        text = """## Chapter 1: Introduction

Salesforce CRM has transformed business operations. AWS provides the infrastructure backbone.

### Key Excerpts

> "Salesforce CRM has transformed how we work."
> — Guest (GUEST)
"""

        # Build allowlist from transcript
        person_blacklist = PersonBlacklist()  # No speakers to block
        entity_allowlist = build_entity_allowlist(transcript, person_blacklist)

        result, report = draft_service.enforce_no_names_in_prose(
            text, person_blacklist=person_blacklist, entity_allowlist=entity_allowlist
        )

        # Product names should be preserved
        assert "Salesforce" in result or "Salesforce CRM" in result
        assert "AWS" in result
        assert report["sentences_dropped"] == 0

    def test_interview_drops_speaker_keeps_orgs(self):
        """Interview drops speaker names but keeps org names they mention."""
        transcript = """
        HOST: Lex Fridman here with David Deutsch.
        GUEST: Thanks Lex. I work with ideas that Microsoft Research explores.
        """

        text = """## Chapter 1: Ideas

David Deutsch explores infinite progress. Microsoft Research has contributed significantly.

### Key Excerpts

> "I work with ideas that Microsoft Research explores."
> — David Deutsch (GUEST)
"""

        person_blacklist = PersonBlacklist(
            full_names={"David Deutsch", "Lex Fridman"},
            last_names={"Deutsch", "Fridman"},
        )
        entity_allowlist = build_entity_allowlist(transcript, person_blacklist)

        result, report = draft_service.enforce_no_names_in_prose(
            text, person_blacklist=person_blacklist, entity_allowlist=entity_allowlist
        )

        # Speaker name dropped from prose
        assert "David Deutsch explores" not in result
        # Org name preserved
        assert "Microsoft Research" in result
        # Key Excerpts untouched
        assert "David Deutsch (GUEST)" in result
