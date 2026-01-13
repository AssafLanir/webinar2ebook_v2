#!/usr/bin/env python3
"""Validation script for canonical transcript service.

Demonstrates:
1. Hash stability (same input → same hash)
2. Substring slicing (offsets work correctly on canonical text)

Run from backend directory:
    python scripts/validate_canonical.py
"""

import sys
sys.path.insert(0, "src")

from services.canonical_service import canonicalize, freeze_canonical_transcript, compute_hash


def print_section(title: str) -> None:
    print(f"\n{'='*60}")
    print(f" {title}")
    print('='*60)


# Sample transcripts: 2 labeled, 1 unlabeled
TRANSCRIPT_LABELED_1 = """Host: What is the nature of knowledge?

David: Knowledge is fundamentally conjectural. We never prove things true—
we can only refute them. This is Popper's key insight.

Host: How does this apply to everyday thinking?

David: It means we should embrace criticism and error correction. Our best
theories are the ones that have survived the most criticism."""

TRANSCRIPT_LABELED_2 = """Interviewer: Tell me about your research focus.

Dr. Chen:   I've been studying "cognitive flexibility"—the brain's ability
to switch between different concepts and adapt to new information.

Interviewer: What have you discovered?

Dr. Chen: The most surprising finding is that flexibility isn't just
about switching—it's about knowing when NOT to switch."""

TRANSCRIPT_UNLABELED = """So the thing about machine learning is that it's fundamentally
a search problem. You're searching through this massive space of possible
functions, trying to find one that fits your data.

And the surprising thing—the really counterintuitive part—is that
the simplest explanation isn't always the best. Sometimes you need
more complexity to capture the true structure."""


def validate_transcript(name: str, raw: str) -> dict:
    """Validate a single transcript, returning results."""
    print_section(f"Validating: {name}")

    # 1. Canonicalize
    canonical, hash_val = freeze_canonical_transcript(raw)

    print(f"\nRaw length: {len(raw)}")
    print(f"Canonical length: {len(canonical)}")
    print(f"Hash: {hash_val[:16]}...")

    # 2. Hash stability - run 3 times
    print("\n[Hash Stability Test]")
    hashes = [compute_hash(canonicalize(raw)) for _ in range(3)]
    all_same = len(set(hashes)) == 1
    print(f"Run 1: {hashes[0][:16]}...")
    print(f"Run 2: {hashes[1][:16]}...")
    print(f"Run 3: {hashes[2][:16]}...")
    print(f"✓ All identical: {all_same}")

    # 3. Idempotence test
    print("\n[Idempotence Test]")
    once = canonicalize(raw)
    twice = canonicalize(once)
    is_idempotent = once == twice
    print(f"canonicalize(x) == canonicalize(canonicalize(x)): {is_idempotent}")

    # 4. Substring slicing
    print("\n[Substring Slicing Test]")

    # Find some words in canonical text and verify offsets
    test_words = []
    for word in ["knowledge", "research", "machine", "conjectural", "flexibility", "search", "error"]:
        pos = canonical.find(word)
        if pos >= 0:
            test_words.append((word, pos, pos + len(word)))

    if test_words:
        for word, start, end in test_words[:3]:  # Test up to 3 words
            extracted = canonical[start:end]
            matches = extracted == word
            print(f"  '{word}' at [{start}:{end}] = '{extracted}' ✓" if matches else f"  '{word}' MISMATCH!")
    else:
        print("  (No test words found in this transcript)")

    # 5. Show first 200 chars of canonical
    print("\n[Canonical Preview (first 200 chars)]")
    print(f"  \"{canonical[:200]}...\"")

    return {
        "name": name,
        "hash_stable": all_same,
        "idempotent": is_idempotent,
        "canonical_len": len(canonical),
        "hash": hash_val,
    }


def main():
    print_section("CANONICAL TRANSCRIPT VALIDATION")
    print("Testing hash stability and offset slicing on 3 transcripts:")
    print("  - 2 labeled (with speaker tags)")
    print("  - 1 unlabeled (continuous prose)")

    results = []
    results.append(validate_transcript("Labeled #1 (Host/David)", TRANSCRIPT_LABELED_1))
    results.append(validate_transcript("Labeled #2 (Interviewer/Dr. Chen)", TRANSCRIPT_LABELED_2))
    results.append(validate_transcript("Unlabeled (ML lecture)", TRANSCRIPT_UNLABELED))

    print_section("SUMMARY")
    all_pass = True
    for r in results:
        status = "✓ PASS" if (r["hash_stable"] and r["idempotent"]) else "✗ FAIL"
        all_pass = all_pass and r["hash_stable"] and r["idempotent"]
        print(f"  {r['name']}: {status}")
        print(f"    Hash stable: {r['hash_stable']}, Idempotent: {r['idempotent']}")

    print(f"\n{'='*60}")
    if all_pass:
        print(" ALL VALIDATIONS PASSED - Ready to proceed past HARD GATE")
    else:
        print(" VALIDATION FAILED - Fix issues before proceeding")
    print('='*60)

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
