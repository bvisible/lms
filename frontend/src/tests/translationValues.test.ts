//// Neoffice — added file (no upstream equivalent): `__` with a list of values returns a string (translation.js).
//// The version-15 line's bulk-enrollment dialog calls it so; it showed "{}" on its count and on its Enroll button.
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('frappe-ui', () => ({ createResource: vi.fn() }))

import translationPlugin from '@/translation'

const install = (messages: Record<string, string>) => {
	;(window as any).translatedMessages = messages
	translationPlugin({ config: { globalProperties: {} } } as any)
	return (window as any).__ as (message: string, replace?: unknown[]) => any
}

afterEach(() => {
	delete (window as any).translatedMessages
})

describe('__ with a list of values', () => {
	it('fills the translated placeholders and returns a string', () => {
		const __ = install({ '{0} students': '{0} étudiants' })
		expect(__('{0} students', [3])).toBe('3 étudiants')
		expect(__('Enroll {0} students', [0])).toBe('Enroll 0 students')
	})

	it('still answers .format() for the calls written the LMS way', () => {
		const __ = install({ 'Question {0} of {1}': 'Question {0} sur {1}' })
		expect(__('Question {0} of {1}').format(1, 2)).toBe('Question 1 sur 2')
	})

	it('returns a plain message untouched', () => {
		const __ = install({ Quiz: 'Quiz' })
		expect(__('Quiz')).toBe('Quiz')
	})
})
