"""Word budget allocation service.

Distributes word budget across chapters based on available evidence,
replacing the "force to target then delete" approach.
"""

# Default minimum words per chapter (ensures readable content)
DEFAULT_MIN_WORDS_PER_CHAPTER = 150

# Multiplier for quote words to prose words
# Each quote word supports approximately 2.5 prose words
PROSE_PER_QUOTE_WORD = 2.5


def allocate_word_budget(
    chapters: list,
    total_target: int,
    min_words_per_chapter: int = DEFAULT_MIN_WORDS_PER_CHAPTER,
) -> list[int]:
    """Allocate word budget across chapters based on evidence.

    Distributes the total word budget proportionally to the evidence
    available in each chapter, while ensuring each chapter gets at
    least the minimum viable word count.

    Args:
        chapters: List of objects with `chapter_index`, `quote_count`,
                  and `quote_words` attributes.
        total_target: Total target word count for the document.
        min_words_per_chapter: Minimum words each chapter must have.

    Returns:
        List of word budgets, one per chapter, in chapter order.
    """
    if not chapters:
        return []

    n_chapters = len(chapters)

    # Calculate total evidence (quote_words is primary metric)
    total_evidence = sum(ch.quote_words for ch in chapters)

    if total_evidence == 0:
        # No evidence at all - distribute evenly
        per_chapter = max(min_words_per_chapter, total_target // n_chapters)
        return [per_chapter] * n_chapters

    # Reserve minimum for each chapter
    reserved = min_words_per_chapter * n_chapters
    distributable = max(0, total_target - reserved)

    # Distribute proportionally based on evidence
    budget = []
    for chapter in chapters:
        # Base allocation: minimum
        base = min_words_per_chapter

        # Evidence-based allocation
        if total_evidence > 0:
            evidence_ratio = chapter.quote_words / total_evidence
            evidence_allocation = int(distributable * evidence_ratio)
        else:
            evidence_allocation = distributable // n_chapters

        budget.append(base + evidence_allocation)

    # Adjust for rounding errors to hit exact total
    current_total = sum(budget)
    if current_total != total_target:
        diff = total_target - current_total
        # Add/subtract from the chapter with most evidence
        max_idx = max(range(n_chapters), key=lambda i: chapters[i].quote_words)
        budget[max_idx] += diff

    return budget


def estimate_feasible_total(
    chapters: list,
    min_words_per_chapter: int = DEFAULT_MIN_WORDS_PER_CHAPTER,
) -> tuple[int, int]:
    """Estimate feasible word count range based on evidence.

    Args:
        chapters: List of chapter evidence objects.
        min_words_per_chapter: Minimum words per chapter.

    Returns:
        Tuple of (min_feasible, max_feasible) word counts.
    """
    if not chapters:
        return (0, 0)

    n_chapters = len(chapters)
    total_quote_words = sum(ch.quote_words for ch in chapters)

    # Minimum: just the minimums per chapter
    min_feasible = min_words_per_chapter * n_chapters

    # Maximum: quotes + prose expansion
    max_feasible = int(total_quote_words * PROSE_PER_QUOTE_WORD) + min_feasible

    return (min_feasible, max_feasible)
