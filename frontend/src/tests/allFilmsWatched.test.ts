//// Neoffice — added file (no upstream equivalent)
import { describe, expect, it } from 'vitest'
import { allFilmsWatched } from '@/utils/lessonProgress'

describe('allFilmsWatched', () => {
	it('is false without any film', () => {
		expect(allFilmsWatched([])).toBe(false)
	})
	it('is true for one film watched to its end (to one second)', () => {
		expect(allFilmsWatched([{ currentTime: 43, duration: 43.7 }])).toBe(true)
	})
	it('is false when the first film is over but the second one is not', () => {
		expect(allFilmsWatched([{ currentTime: 43.7, duration: 43.7 }, { currentTime: 12, duration: 88 }])).toBe(false)
	})
	it('is true when both films are over', () => {
		expect(allFilmsWatched([{ currentTime: 43.7, duration: 43.7 }, { currentTime: 87.5, duration: 88 }])).toBe(true)
	})
	it('is false for a film whose duration is not known yet', () => {
		expect(allFilmsWatched([{ currentTime: 0, duration: NaN }])).toBe(false)
	})
})
