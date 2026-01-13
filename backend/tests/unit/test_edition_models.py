"""Unit tests for Edition, Fidelity, and Coverage enums.

These tests verify:
1. Enum values are correct string values
2. Enums can be constructed from strings
3. Invalid strings are rejected with ValueError
"""

import pytest

from src.models.edition import Coverage, Edition, Fidelity


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
