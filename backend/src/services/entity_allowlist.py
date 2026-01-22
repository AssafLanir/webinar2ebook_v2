"""Entity allowlist for transcript-attested org/product names.

This module provides deterministic extraction of org/product names from transcripts
to allow them in narrative prose while still blocking person names.

The approach is conservative and doesn't require full NER:
1. Extract proper-nounish spans (Capitalized words, ALLCAPS tokens)
2. Filter using deterministic rules (org suffixes, domain tokens)
3. Build allowlist of transcript-attested entities
"""

import re
from dataclasses import dataclass, field
from typing import Set


# Org suffixes that strongly indicate an organization
ORG_SUFFIXES = {
    "inc", "llc", "ltd", "corp", "co", "gmbh", "ag", "plc",
    "systems", "technologies", "labs", "ai", "cloud", "platform",
    "software", "solutions", "services", "group", "partners",
    "consulting", "analytics", "data", "tech", "digital",
}

# Domain tokens that suggest org/product (not person)
DOMAIN_TOKENS = {
    "cloud", "platform", "suite", "api", "sdk", "crm", "erp", "bi",
    "labs", "technologies", "systems", "studio", "hub", "pro",
    "enterprise", "business", "portal", "dashboard", "analytics",
}

# Common first names to help identify person-like patterns
# (Used to filter OUT, not to build person list)
COMMON_FIRST_NAMES = {
    "john", "jane", "david", "michael", "james", "robert", "william",
    "richard", "joseph", "thomas", "charles", "daniel", "matthew",
    "anthony", "mark", "donald", "steven", "paul", "andrew", "joshua",
    "mary", "patricia", "jennifer", "linda", "elizabeth", "barbara",
    "susan", "jessica", "sarah", "karen", "nancy", "lisa", "betty",
}


@dataclass
class EntityAllowlist:
    """Allowlist of org/product names attested in transcript."""

    org_names: Set[str] = field(default_factory=set)
    product_names: Set[str] = field(default_factory=set)
    acronyms: Set[str] = field(default_factory=set)

    # For debugging/metrics
    all_candidates: Set[str] = field(default_factory=set)
    rejected_as_person: Set[str] = field(default_factory=set)

    def contains(self, text: str) -> bool:
        """Check if text matches any allowlisted entity."""
        text_lower = text.lower()
        text_upper = text.upper()

        # Check exact matches (case-insensitive for orgs)
        if text_lower in {n.lower() for n in self.org_names}:
            return True
        if text_lower in {n.lower() for n in self.product_names}:
            return True

        # Check acronyms (case-sensitive for ALLCAPS)
        if text_upper in self.acronyms:
            return True
        if text in self.acronyms:
            return True

        return False


@dataclass
class PersonBlacklist:
    """Blacklist of person names to block in prose."""

    full_names: Set[str] = field(default_factory=set)
    last_names: Set[str] = field(default_factory=set)
    # We avoid first-name-only unless very confident

    def matches(self, text: str) -> bool:
        """Check if text matches any blacklisted person name."""
        text_lower = text.lower().strip()

        # Check full names
        for name in self.full_names:
            if name.lower() in text_lower:
                return True

        # Check last names (word boundary)
        for last_name in self.last_names:
            # Use word boundary check
            pattern = r'\b' + re.escape(last_name) + r'\b'
            if re.search(pattern, text, re.IGNORECASE):
                return True

        return False


def build_person_blacklist(
    speakers: list[dict],
    additional_names: list[str] | None = None,
) -> PersonBlacklist:
    """Build person blacklist from speaker metadata.

    Args:
        speakers: List of speaker dicts with 'speaker_name' or 'canonical_name'.
        additional_names: Optional additional person names to block.

    Returns:
        PersonBlacklist with full names and last names.
    """
    blacklist = PersonBlacklist()

    for speaker in speakers:
        # Get name from various possible fields
        name = (
            speaker.get("speaker_name") or
            speaker.get("canonical_name") or
            speaker.get("name") or
            ""
        )

        if not name:
            continue

        # Add full name
        blacklist.full_names.add(name)

        # Extract and add last name (if multi-word)
        parts = name.split()
        if len(parts) >= 2:
            last_name = parts[-1]
            # Only add if not too short/common
            if len(last_name) >= 3:
                blacklist.last_names.add(last_name)

    # Add any additional names
    if additional_names:
        for name in additional_names:
            blacklist.full_names.add(name)
            parts = name.split()
            if len(parts) >= 2 and len(parts[-1]) >= 3:
                blacklist.last_names.add(parts[-1])

    return blacklist


def build_person_blacklist_from_whitelist(
    whitelist_quotes: list,
) -> PersonBlacklist:
    """Build person blacklist from WhitelistQuote objects.

    Args:
        whitelist_quotes: List of WhitelistQuote objects with speaker info.

    Returns:
        PersonBlacklist with speaker names.
    """
    blacklist = PersonBlacklist()
    seen_speakers = set()

    for quote in whitelist_quotes:
        speaker = getattr(quote, 'speaker', None)
        if not speaker:
            continue

        speaker_name = getattr(speaker, 'speaker_name', None)
        if not speaker_name or speaker_name in seen_speakers:
            continue

        seen_speakers.add(speaker_name)

        # Add full name
        blacklist.full_names.add(speaker_name)

        # Extract and add last name
        parts = speaker_name.split()
        if len(parts) >= 2:
            last_name = parts[-1]
            if len(last_name) >= 3:
                blacklist.last_names.add(last_name)

    return blacklist


def extract_entity_candidates(transcript_text: str) -> Set[str]:
    """Extract candidate entity names from transcript text.

    Uses conservative regex to find proper-nounish spans:
    - Sequences of Capitalized words
    - ALLCAPS tokens (2-6 chars)
    - Allows internal punctuation: &, ., -, /

    Args:
        transcript_text: Raw transcript text.

    Returns:
        Set of candidate entity strings.
    """
    candidates = set()

    # Pattern 1: Capitalized word sequences (2+ words)
    # E.g., "Amazon Web Services", "Google Cloud", "Acme Corp"
    cap_sequence = re.compile(
        r'\b([A-Z][a-z]+(?:\s+(?:&\s+)?[A-Z][a-z]+)+)\b'
    )
    for match in cap_sequence.finditer(transcript_text):
        candidates.add(match.group(1))

    # Pattern 2: Single Capitalized word followed by org suffix
    # E.g., "Salesforce", "Microsoft"
    cap_with_suffix = re.compile(
        r'\b([A-Z][a-z]+)\s+(Inc|LLC|Ltd|Corp|Co|GmbH|AG|PLC|'
        r'Systems|Technologies|Labs|AI|Cloud|Platform|Software|'
        r'Solutions|Services|Group|Partners)\b',
        re.IGNORECASE
    )
    for match in cap_with_suffix.finditer(transcript_text):
        full = f"{match.group(1)} {match.group(2)}"
        candidates.add(full)
        # Also add just the name part
        candidates.add(match.group(1))

    # Pattern 3: ALLCAPS tokens (2-6 chars) - likely acronyms
    # E.g., "AWS", "CRM", "API", "SOC2"
    allcaps = re.compile(r'\b([A-Z]{2,6}[0-9]?)\b')
    for match in allcaps.finditer(transcript_text):
        token = match.group(1)
        # Filter out common non-entity ALLCAPS
        if token not in {"THE", "AND", "FOR", "BUT", "NOT", "YOU", "ARE", "WAS", "HAS", "HAD", "HIS", "HER", "HIM"}:
            candidates.add(token)

    # Pattern 4: CamelCase product names
    # E.g., "PowerBI", "GitHub", "LinkedIn"
    camel_case = re.compile(r'\b([A-Z][a-z]+[A-Z][a-zA-Z]*)\b')
    for match in camel_case.finditer(transcript_text):
        candidates.add(match.group(1))

    return candidates


def classify_entity(
    candidate: str,
    person_blacklist: PersonBlacklist,
) -> str:
    """Classify an entity candidate as PERSON, ORG, PRODUCT, or AMBIGUOUS.

    Uses deterministic rules without NER.

    Args:
        candidate: Entity candidate string.
        person_blacklist: Known person names to check against.

    Returns:
        Classification: "PERSON", "ORG", "PRODUCT", or "AMBIGUOUS"
    """
    candidate_lower = candidate.lower()
    words = candidate.split()

    # Check 1: Is it a known speaker/person?
    if person_blacklist.matches(candidate):
        return "PERSON"

    # Check 2: Does it have an org suffix?
    if words:
        last_word = words[-1].lower()
        if last_word in ORG_SUFFIXES:
            return "ORG"

    # Check 3: Does it contain domain tokens?
    for word in words:
        if word.lower() in DOMAIN_TOKENS:
            return "ORG"

    # Check 4: Is it ALLCAPS (2-6 chars)?
    if candidate.isupper() and 2 <= len(candidate) <= 6:
        return "PRODUCT"  # Likely acronym/product

    # Check 5: Is it CamelCase?
    if re.match(r'^[A-Z][a-z]+[A-Z]', candidate):
        return "PRODUCT"

    # Check 6: Does it look like a person name? (two Capitalized words, first is common name)
    if len(words) == 2:
        first_word = words[0].lower()
        if first_word in COMMON_FIRST_NAMES:
            return "PERSON"

    # Default: ambiguous
    return "AMBIGUOUS"


def build_entity_allowlist(
    transcript_text: str,
    person_blacklist: PersonBlacklist | None = None,
) -> EntityAllowlist:
    """Build entity allowlist from transcript text.

    Extracts org/product names using conservative heuristics,
    filtering out known person names.

    Args:
        transcript_text: Raw transcript text.
        person_blacklist: Optional person blacklist for filtering.

    Returns:
        EntityAllowlist with transcript-attested entities.
    """
    if person_blacklist is None:
        person_blacklist = PersonBlacklist()

    allowlist = EntityAllowlist()

    # Extract candidates
    candidates = extract_entity_candidates(transcript_text)
    allowlist.all_candidates = candidates.copy()

    # Classify each candidate
    for candidate in candidates:
        classification = classify_entity(candidate, person_blacklist)

        if classification == "PERSON":
            allowlist.rejected_as_person.add(candidate)
        elif classification == "ORG":
            allowlist.org_names.add(candidate)
        elif classification == "PRODUCT":
            allowlist.product_names.add(candidate)
            # Also add to acronyms if ALLCAPS
            if candidate.isupper():
                allowlist.acronyms.add(candidate)
        # AMBIGUOUS: we don't add to allowlist (conservative)

    return allowlist
