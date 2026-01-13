"""Edition-related enums for the Editions feature.

These enums define the different edition types, fidelity levels,
and coverage strengths used throughout the system.
"""

from enum import Enum


class Edition(str, Enum):
    """Type of edition to generate.

    QA: Question-and-answer format preserving interview structure
    IDEAS: Key ideas extraction format
    """

    QA = "qa"
    IDEAS = "ideas"


class Fidelity(str, Enum):
    """Fidelity level for content generation.

    FAITHFUL: Maintains meaning while allowing minor rephrasing
    VERBATIM: Exact word-for-word preservation
    """

    FAITHFUL = "faithful"
    VERBATIM = "verbatim"


class Coverage(str, Enum):
    """Coverage strength indicating how well content is supported.

    STRONG: Content is well-supported by evidence
    MEDIUM: Content has moderate support
    WEAK: Content has minimal support
    """

    STRONG = "strong"
    MEDIUM = "medium"
    WEAK = "weak"
