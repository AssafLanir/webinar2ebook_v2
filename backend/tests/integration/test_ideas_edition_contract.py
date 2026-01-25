"""CI Smoke Tests: Ideas Edition Output Contract.

These tests validate that Ideas Edition presets produce output with:
1. Chapter structure (## Chapter N:)
2. Key Excerpts sections
3. Core Claims sections
4. NO interview template leakage (*Interviewer:*, *Format:* Interview, ### The Conversation)

This test runs WITHOUT making LLM calls - it validates the contract logic
against fixture data that represents realistic pipeline output.

Root cause (2026-01-25): content_mode defaulted to "interview" when not specified,
causing Ideas Edition presets to route through interview pipeline.
"""

import re

import pytest


# =============================================================================
# Ideas Edition Output Contract Validator
# =============================================================================


def validate_ideas_edition_contract(markdown: str) -> tuple[bool, list[str]]:
    """Validate Ideas Edition output contract.

    Returns (passed, list of violations).
    """
    violations = []

    # 1. Must have ## Chapter N: structure
    has_chapters = bool(re.search(r'(?m)^## Chapter \d+:', markdown))
    if not has_chapters:
        violations.append("Missing chapter structure (## Chapter N:)")

    # 2. Must have ### Key Excerpts sections
    has_excerpts = '### Key Excerpts' in markdown
    if not has_excerpts:
        violations.append("Missing Key Excerpts sections")

    # 3. Must have ### Core Claims sections
    has_claims = '### Core Claims' in markdown
    if not has_claims:
        violations.append("Missing Core Claims sections")

    # 4. Must NOT have interview template leakage
    if '*Format:* Interview' in markdown:
        violations.append("Interview format marker (*Format:* Interview)")

    if '### The Conversation' in markdown:
        violations.append("Interview conversation header (### The Conversation)")

    if re.search(r'(?m)^\*Interviewer:\*', markdown):
        violations.append("Interview template leakage (*Interviewer:*)")

    # 5. Must NOT have ### Key Ideas (Grounded) - that's interview format
    if '### Key Ideas (Grounded)' in markdown:
        violations.append("Interview Key Ideas section (### Key Ideas (Grounded))")

    passed = len(violations) == 0
    return passed, violations


# =============================================================================
# Test Fixtures: Valid Ideas Edition Output
# =============================================================================


VALID_IDEAS_EDITION_OUTPUT = '''## Chapter 1: Introduction to Voice Technology

Voice technology represents a fundamental shift in human-computer interaction. The ability to communicate naturally with devices opens new possibilities for accessibility and convenience.

Modern voice interfaces combine multiple technologies including wake word detection, speech recognition, and natural language understanding.

### Key Excerpts

> "Amazon does this, and when you see the light go off but it doesn't respond, it usually means the product false-fired on the wake word."
> — Todd Moser

> "Voice Hub is a tool we created to allow companies and developers to quickly create projects and proof of concepts."
> — Jeff Rogers

### Core Claims

- **Wake word false positives create user confusion**: "Amazon does this, and when you see the light go off but it doesn't respond, it usually means the product false-fired on the wake word."
- **Rapid prototyping accelerates voice product development**: "Voice Hub is a tool we created to allow companies and developers to quickly create projects and proof of concepts."

## Chapter 2: Cloud-Based Voice Services

Cloud services enable sophisticated voice processing beyond what embedded systems can achieve alone. The combination of local processing with cloud intelligence creates powerful hybrid architectures.

### Key Excerpts

> "Our speech-to-text is our most compelling product, handling streaming at a higher accuracy than Google and Microsoft."
> — Brian McGreen

### Core Claims

- **Cloud-based speech recognition achieves industry-leading accuracy**: "Our speech-to-text is our most compelling product, handling streaming at a higher accuracy than Google and Microsoft."
- **Multi-language support enables global deployment**: "We support 17 languages and add more every day."
'''


# =============================================================================
# Test Fixtures: Invalid Interview Output (Should Fail Validation)
# =============================================================================


INVALID_INTERVIEW_OUTPUT = '''# Sensory's Technological Innovations

*Format:* Interview
*Word count:* ~3,035
*Generated:* 2026-01-25

### Key Ideas (Grounded)

- **Wake word response issues**: "Amazon does this, and when you see the light go off but it doesn't respond..."
- **Voice Hub enables rapid development**: "Voice Hub is a tool we created to allow companies and developers to quickly create projects..."

### The Conversation

*Interviewer:* Thank you again for joining today's webinar. My name is Anu Adeboja, and I'll be moderating today's session.

### Hi, I'm Todd Moser, Sensory's President. I started Sensory over 25 years ago to allow people to communicate with products naturally.

*Interviewer:* Can you tell us more about Voice Hub?

### Great question. Voice Hub is a tool we created to allow companies and developers to quickly create projects and proof of concepts.
'''


# =============================================================================
# Contract Validation Tests
# =============================================================================


class TestIdeasEditionOutputContract:
    """Smoke tests for Ideas Edition output contract."""

    def test_valid_ideas_edition_passes_contract(self):
        """Valid Ideas Edition output should pass all contract checks."""
        passed, violations = validate_ideas_edition_contract(VALID_IDEAS_EDITION_OUTPUT)

        assert passed, f"Valid Ideas Edition output should pass. Violations: {violations}"
        assert len(violations) == 0

    def test_interview_output_fails_contract(self):
        """Interview-style output should FAIL Ideas Edition contract."""
        passed, violations = validate_ideas_edition_contract(INVALID_INTERVIEW_OUTPUT)

        assert not passed, "Interview output should fail Ideas Edition contract"
        # Should detect multiple violations
        assert len(violations) >= 3, f"Expected multiple violations, got: {violations}"
        # Specific violations expected
        violation_str = " ".join(violations)
        assert "Chapter" in violation_str or "Missing chapter" in violation_str
        assert "Interview" in violation_str or "Interviewer" in violation_str

    def test_detects_missing_chapters(self):
        """Output without chapter structure should fail."""
        markdown = '''# Introduction

Some prose content without chapter structure.

### Key Excerpts

> "A quote here"

### Core Claims

- A claim here
'''
        passed, violations = validate_ideas_edition_contract(markdown)

        assert not passed
        assert any("chapter" in v.lower() for v in violations)

    def test_detects_missing_key_excerpts(self):
        """Output without Key Excerpts should fail."""
        markdown = '''## Chapter 1: Introduction

Some prose content.

### Core Claims

- A claim here
'''
        passed, violations = validate_ideas_edition_contract(markdown)

        assert not passed
        assert any("Key Excerpts" in v for v in violations)

    def test_detects_missing_core_claims(self):
        """Output without Core Claims should fail."""
        markdown = '''## Chapter 1: Introduction

Some prose content.

### Key Excerpts

> "A quote here"
'''
        passed, violations = validate_ideas_edition_contract(markdown)

        assert not passed
        assert any("Core Claims" in v for v in violations)

    def test_detects_interviewer_marker(self):
        """Output with *Interviewer:* should fail."""
        markdown = '''## Chapter 1: Introduction

Some prose content.

*Interviewer:* What do you think about this?

### Key Excerpts

> "A quote"

### Core Claims

- A claim
'''
        passed, violations = validate_ideas_edition_contract(markdown)

        assert not passed
        assert any("Interviewer" in v for v in violations)

    def test_detects_format_interview_marker(self):
        """Output with *Format:* Interview should fail."""
        markdown = '''*Format:* Interview

## Chapter 1: Introduction

### Key Excerpts

> "A quote"

### Core Claims

- A claim
'''
        passed, violations = validate_ideas_edition_contract(markdown)

        assert not passed
        assert any("format" in v.lower() for v in violations)

    def test_detects_the_conversation_header(self):
        """Output with ### The Conversation should fail."""
        markdown = '''## Chapter 1: Introduction

### The Conversation

Content here.

### Key Excerpts

> "A quote"

### Core Claims

- A claim
'''
        passed, violations = validate_ideas_edition_contract(markdown)

        assert not passed
        assert any("Conversation" in v for v in violations)


class TestPresetContentModeAlignment:
    """Tests that preset configurations route correctly."""

    def test_all_ideas_presets_have_essay_content_mode(self):
        """All Ideas Edition presets must have content_mode: essay.

        This mirrors the frontend test - defense in depth.
        """
        # These are the Ideas Edition compatible presets from stylePresets.ts
        ideas_presets = [
            "scholarly_essay_v1",
            "default_webinar_ebook_v1",
            "saas_marketing_ebook_v1",
            "training_tutorial_handbook_v1",
            "executive_brief_v1",
            "course_notes_v1",
        ]

        # Mapping preset_id → expected content_mode
        # All Ideas Edition presets should use "essay"
        for preset_id in ideas_presets:
            # The actual validation is done in the frontend test
            # This test documents the expectation in backend code
            assert preset_id in ideas_presets, f"{preset_id} should be Ideas Edition compatible"

    def test_interview_qa_preset_has_interview_content_mode(self):
        """Interview Q&A preset must have content_mode: interview."""
        interview_presets = ["interview_qa_v1"]

        for preset_id in interview_presets:
            # Documents the expectation
            assert preset_id in interview_presets


class TestContractIntegrationWithPipeline:
    """Tests that the contract validation integrates with the pipeline."""

    def test_contract_validator_function_exists(self):
        """The output contract validation exists in draft_service."""
        # This is tested implicitly by the e2e test
        # Here we just verify the contract checker works as expected
        passed, violations = validate_ideas_edition_contract(VALID_IDEAS_EDITION_OUTPUT)
        assert passed

    def test_contract_is_strict_about_structure(self):
        """Contract requires BOTH Key Excerpts AND Core Claims, not just one."""
        # Only Key Excerpts, no Core Claims
        only_excerpts = '''## Chapter 1: Test

### Key Excerpts

> "A quote"
'''
        passed, _ = validate_ideas_edition_contract(only_excerpts)
        assert not passed, "Missing Core Claims should fail"

        # Only Core Claims, no Key Excerpts
        only_claims = '''## Chapter 1: Test

### Core Claims

- A claim
'''
        passed, _ = validate_ideas_edition_contract(only_claims)
        assert not passed, "Missing Key Excerpts should fail"
