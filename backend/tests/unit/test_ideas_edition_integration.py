"""Tests for Ideas Edition integration in draft service."""


class TestIdeasEditionPostProcessing:
    """Tests for Ideas Edition post-processing pipeline."""

    def test_strip_empty_section_headers_imported(self):
        """Verify strip_empty_section_headers is available in draft_service."""
        from src.services.draft_service import strip_empty_section_headers
        assert callable(strip_empty_section_headers)

    def test_compile_key_excerpts_section_imported(self):
        """Verify compile_key_excerpts_section is available."""
        from src.services.draft_service import compile_key_excerpts_section
        assert callable(compile_key_excerpts_section)

    def test_remove_inline_quotes_in_whitelist_service(self):
        """Verify remove_inline_quotes is available."""
        from src.services.whitelist_service import remove_inline_quotes
        assert callable(remove_inline_quotes)

    def test_generate_coverage_report_in_whitelist_service(self):
        """Verify generate_coverage_report is available."""
        from src.services.whitelist_service import generate_coverage_report
        assert callable(generate_coverage_report)


class TestIdeasEditionPipelineSteps:
    """Test the pipeline steps work together."""

    def test_inline_quote_removal_then_empty_strip(self):
        """Pipeline removes inline quotes then strips empty sections."""
        from src.services.draft_service import strip_empty_section_headers
        from src.services.whitelist_service import remove_inline_quotes

        doc = '''## Chapter 1

He said "this is important" to explain the concept.

### Key Excerpts

### Core Claims
'''

        # Step 1: Remove inline quotes
        cleaned, report = remove_inline_quotes(doc)
        assert report["removed_count"] == 1
        assert '"this is important"' not in cleaned

        # Step 2: Strip empty sections
        final = strip_empty_section_headers(cleaned)
        assert "### Key Excerpts" not in final
        assert "### Core Claims" not in final

    def test_coverage_report_before_generation(self):
        """Coverage report can be generated from whitelist."""
        from hashlib import sha256

        from src.models.edition import SpeakerRef, SpeakerRole, WhitelistQuote
        from src.services.whitelist_service import generate_coverage_report

        # Create a simple whitelist
        def make_quote(text, chapters):
            canonical = text.lower()
            qid = sha256(f"test|{canonical}".encode()).hexdigest()[:16]
            return WhitelistQuote(
                quote_id=qid,
                quote_text=text,
                quote_canonical=canonical,
                speaker=SpeakerRef(
                    speaker_id="guest",
                    speaker_name="Test Guest",
                    speaker_role=SpeakerRole.GUEST,
                ),
                source_evidence_ids=[],
                chapter_indices=chapters,
                match_spans=[],
            )

        whitelist = [
            make_quote("Quote one", [0]),
            make_quote("Quote two", [0]),
            make_quote("Quote three", [1]),
        ]

        report = generate_coverage_report(whitelist, chapter_count=2, transcript_hash="test")

        assert report.total_whitelist_quotes == 3
        assert len(report.chapters) == 2
        assert report.chapters[0].valid_quotes == 2
        assert report.chapters[1].valid_quotes == 1
