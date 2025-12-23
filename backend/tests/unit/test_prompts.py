"""Unit tests for prompt generation functions."""

import pytest

from src.services.prompts import build_chapter_system_prompt


class TestBuildChapterSystemPrompt:
    """Tests for build_chapter_system_prompt function."""

    def test_includes_word_target(self):
        """Test that prompt includes word target."""
        prompt = build_chapter_system_prompt(
            book_title="Test Book",
            chapter_number=1,
            style_config={"tone": "professional"},
            words_per_chapter_target=500,
            detail_level="balanced",
        )
        assert "500 words" in prompt

    def test_includes_detail_level_concise(self):
        """Test that prompt includes concise detail level guidance."""
        prompt = build_chapter_system_prompt(
            book_title="Test Book",
            chapter_number=1,
            style_config={"tone": "professional"},
            words_per_chapter_target=500,
            detail_level="concise",
        )
        assert "concise" in prompt.lower()
        assert "fewer examples" in prompt.lower()

    def test_includes_detail_level_detailed(self):
        """Test that prompt includes detailed level guidance."""
        prompt = build_chapter_system_prompt(
            book_title="Test Book",
            chapter_number=1,
            style_config={"tone": "professional"},
            words_per_chapter_target=500,
            detail_level="detailed",
        )
        assert "detailed" in prompt.lower()
        assert "more examples" in prompt.lower()

    def test_includes_no_visual_placeholders_rule(self):
        """Test that prompt forbids visual placeholders."""
        prompt = build_chapter_system_prompt(
            book_title="Test Book",
            chapter_number=1,
            style_config={},
            words_per_chapter_target=500,
            detail_level="balanced",
        )
        assert "DO NOT include visual placeholders" in prompt

    def test_includes_chapter_number(self):
        """Test that prompt includes chapter number."""
        prompt = build_chapter_system_prompt(
            book_title="My Book",
            chapter_number=3,
            style_config={},
            words_per_chapter_target=500,
            detail_level="balanced",
        )
        assert "chapter 3" in prompt.lower()
        assert "My Book" in prompt
