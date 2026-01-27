import { describe, it, expect } from 'vitest'
import { STYLE_PRESETS, type StylePreset } from '../../src/constants/stylePresets'

describe('Style Presets Completeness', () => {
  /**
   * CRITICAL INVARIANT: All Ideas Edition presets must have content_mode: "essay"
   *
   * Root cause of routing bug (2026-01-25): Backend defaulted content_mode to "interview"
   * when not specified, causing Ideas Edition presets to route through interview pipeline.
   *
   * This test prevents future presets from being added "halfway" without content_mode.
   */
  describe('Ideas Edition presets must have content_mode: essay', () => {
    const ideasPresets = STYLE_PRESETS.filter((preset) =>
      preset.compatibleEditions.includes('ideas')
    )

    it('should have at least one Ideas Edition preset', () => {
      expect(ideasPresets.length).toBeGreaterThan(0)
    })

    ideasPresets.forEach((preset) => {
      it(`${preset.id} must have content_mode: "essay"`, () => {
        const contentMode = preset.value.style.content_mode
        expect(contentMode).toBeDefined()
        expect(contentMode).toBe('essay')
      })

      it(`${preset.id} must NOT have book_format: "interview_qa"`, () => {
        // Ideas Edition presets should never use interview_qa book_format
        const bookFormat = preset.value.style.book_format
        expect(bookFormat).not.toBe('interview_qa')
      })
    })
  })

  /**
   * Q&A Edition (Interview) presets must have content_mode: "interview"
   */
  describe('Q&A Edition presets must have content_mode: interview', () => {
    const qaOnlyPresets = STYLE_PRESETS.filter(
      (preset) =>
        preset.compatibleEditions.includes('qa') &&
        !preset.compatibleEditions.includes('ideas')
    )

    qaOnlyPresets.forEach((preset) => {
      it(`${preset.id} must have content_mode: "interview"`, () => {
        const contentMode = preset.value.style.content_mode
        expect(contentMode).toBeDefined()
        expect(contentMode).toBe('interview')
      })
    })
  })

  /**
   * All presets must have required fields
   */
  describe('All presets have required structure', () => {
    STYLE_PRESETS.forEach((preset) => {
      describe(preset.id, () => {
        it('has valid id and label', () => {
          expect(preset.id).toBeTruthy()
          expect(preset.label).toBeTruthy()
          expect(preset.description).toBeTruthy()
        })

        it('has compatibleEditions array', () => {
          expect(Array.isArray(preset.compatibleEditions)).toBe(true)
          expect(preset.compatibleEditions.length).toBeGreaterThan(0)
        })

        it('has valid style config envelope', () => {
          expect(preset.value.version).toBe(1)
          expect(preset.value.preset_id).toBe(preset.id)
          expect(preset.value.style).toBeDefined()
        })

        it('has book_format defined', () => {
          expect(preset.value.style.book_format).toBeDefined()
        })

        it('has content_mode defined', () => {
          // This is the key invariant - content_mode must always be explicit
          expect(preset.value.style.content_mode).toBeDefined()
        })
      })
    })
  })

  /**
   * Sanity check: preset_id matches id
   */
  describe('Preset ID consistency', () => {
    STYLE_PRESETS.forEach((preset) => {
      it(`${preset.id} has matching preset_id in value`, () => {
        expect(preset.value.preset_id).toBe(preset.id)
      })
    })
  })
})
