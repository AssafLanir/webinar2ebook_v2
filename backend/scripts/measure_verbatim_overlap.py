#!/usr/bin/env python3
"""Measure verbatim overlap between draft prose and transcript.

This metric indicates "ebook-ness":
- High overlap = too transcript-y (not transformed enough)
- Low overlap = properly synthesized (more ebook-like)

Target: 8-12 word n-gram overlap rate should be LOW (< 15% ideally)
"""

import re
import sys
from collections import Counter
from pathlib import Path


def extract_prose_sections(markdown: str) -> str:
    """Extract prose content (not Key Excerpts, Core Claims, or headers)."""
    lines = markdown.split('\n')
    prose_lines = []
    in_special_section = False

    for line in lines:
        stripped = line.strip()

        # Skip headers
        if stripped.startswith('#'):
            in_special_section = '### Key Excerpts' in stripped or '### Core Claims' in stripped
            continue

        # Skip blockquotes (excerpts)
        if stripped.startswith('>'):
            continue

        # Skip bullet points in Core Claims
        if stripped.startswith('- **'):
            continue

        # Skip empty lines and attribution lines
        if not stripped or stripped.startswith('—'):
            continue

        # In special sections, skip most content
        if in_special_section:
            continue

        prose_lines.append(stripped)

    return ' '.join(prose_lines)


def normalize_text(text: str) -> str:
    """Normalize text for comparison."""
    # Lowercase
    text = text.lower()
    # Remove punctuation except spaces
    text = re.sub(r'[^\w\s]', '', text)
    # Normalize whitespace
    text = ' '.join(text.split())
    return text


def get_ngrams(text: str, n: int) -> list[str]:
    """Extract n-grams from text."""
    words = text.split()
    if len(words) < n:
        return []
    return [' '.join(words[i:i+n]) for i in range(len(words) - n + 1)]


def calculate_overlap(draft_text: str, transcript_text: str, n: int = 8) -> dict:
    """Calculate n-gram overlap between draft and transcript.

    Returns dict with:
    - overlap_ratio: fraction of draft n-grams found in transcript
    - total_ngrams: total n-grams in draft
    - matched_ngrams: n-grams found in transcript
    - sample_matches: example matching n-grams
    """
    draft_normalized = normalize_text(draft_text)
    transcript_normalized = normalize_text(transcript_text)

    draft_ngrams = get_ngrams(draft_normalized, n)
    transcript_ngrams = set(get_ngrams(transcript_normalized, n))

    if not draft_ngrams:
        return {
            'overlap_ratio': 0.0,
            'total_ngrams': 0,
            'matched_ngrams': 0,
            'sample_matches': [],
        }

    matches = [ng for ng in draft_ngrams if ng in transcript_ngrams]

    return {
        'overlap_ratio': len(matches) / len(draft_ngrams),
        'total_ngrams': len(draft_ngrams),
        'matched_ngrams': len(matches),
        'sample_matches': list(set(matches))[:5],
    }


def analyze_file(draft_path: Path, transcript_path: Path) -> dict:
    """Analyze verbatim overlap for a draft file."""
    draft = draft_path.read_text()
    transcript = transcript_path.read_text()

    prose = extract_prose_sections(draft)
    prose_words = len(prose.split())

    # Calculate overlap at different n-gram sizes
    results = {
        'file': draft_path.name,
        'prose_words': prose_words,
    }

    for n in [5, 8, 12]:
        overlap = calculate_overlap(prose, transcript, n)
        results[f'{n}gram_overlap'] = overlap['overlap_ratio']
        results[f'{n}gram_matches'] = overlap['matched_ngrams']
        results[f'{n}gram_total'] = overlap['total_ngrams']
        if n == 8:
            results['sample_8gram_matches'] = overlap['sample_matches']

    return results


def main():
    # Transcript location
    transcript_path = Path("/Users/assaf/Downloads/build-quality-voicevision-ai-sols-w-sensory-cloud--draft--2026-01-25.txt")

    if not transcript_path.exists():
        print(f"ERROR: Transcript not found: {transcript_path}")
        sys.exit(1)

    # Draft files
    drafts = [
        Path("/Users/assaf/PycharmProjects/webinar2ebook_v2/backend/corpora/good_sensory_default.md"),
        Path("/Users/assaf/PycharmProjects/webinar2ebook_v2/backend/corpora/good_sensory_marketing.md"),
    ]

    print("=" * 70)
    print("VERBATIM OVERLAP ANALYSIS (Ebook-ness Metric)")
    print("=" * 70)
    print()
    print("Target: 8-gram overlap < 15% indicates good synthesis")
    print("(Low overlap = more transformation = more ebook-like)")
    print()

    for draft_path in drafts:
        if not draft_path.exists():
            print(f"SKIP: {draft_path.name} not found")
            continue

        results = analyze_file(draft_path, transcript_path)

        print(f"--- {results['file']} ---")
        print(f"  Prose words: {results['prose_words']}")
        print()
        print(f"  5-gram overlap: {results['5gram_overlap']:.1%} ({results['5gram_matches']}/{results['5gram_total']})")
        print(f"  8-gram overlap: {results['8gram_overlap']:.1%} ({results['8gram_matches']}/{results['8gram_total']})")
        print(f"  12-gram overlap: {results['12gram_overlap']:.1%} ({results['12gram_matches']}/{results['12gram_total']})")

        # Verdict
        overlap_8 = results['8gram_overlap']
        if overlap_8 < 0.05:
            verdict = "✓ EXCELLENT - Very well synthesized"
        elif overlap_8 < 0.15:
            verdict = "✓ GOOD - Properly transformed"
        elif overlap_8 < 0.30:
            verdict = "⚠ WARN - Somewhat transcript-y"
        else:
            verdict = "✗ FAIL - Too verbatim"

        print(f"\n  Verdict: {verdict}")

        if results['sample_8gram_matches']:
            print(f"\n  Sample 8-gram matches:")
            for match in results['sample_8gram_matches'][:3]:
                print(f"    - \"{match}\"")

        print()

    print("=" * 70)


if __name__ == "__main__":
    main()
