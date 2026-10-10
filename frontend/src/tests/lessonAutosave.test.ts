//// Neoffice — added file (no upstream equivalent)
import { describe, expect, it } from 'vitest'
import { shouldMarkDirty } from '@/utils/lessonAutosave'

const base = { fromTitle: false, initialLoadComplete: true, hasSavedContent: false, userTouched: false }

describe('shouldMarkDirty', () => {
	it('does not save a body-only lesson that the editor itself normalised', () => {
		expect(shouldMarkDirty(base)).toBe(false)
	})
	it('saves it once the user has typed, pasted or clicked in the editor', () => {
		expect(shouldMarkDirty({ ...base, userTouched: true })).toBe(true)
	})
	it('keeps saving a lesson that already has its own saved content', () => {
		expect(shouldMarkDirty({ ...base, hasSavedContent: true })).toBe(true)
	})
	it('still waits for the first render to finish', () => {
		expect(shouldMarkDirty({ ...base, initialLoadComplete: false, hasSavedContent: true, userTouched: true })).toBe(false)
	})
	it('saves a change of the title', () => {
		expect(shouldMarkDirty({ ...base, fromTitle: true, initialLoadComplete: false })).toBe(true)
	})
})
