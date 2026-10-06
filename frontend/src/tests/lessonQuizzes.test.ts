//// Neoffice — added file (no upstream equivalent).
import { beforeEach, describe, expect, it } from 'vitest'
import {
	lessonQuizzes,
	needsLeaveConfirmation,
	registerLessonQuiz,
} from '@/utils/lessonQuizzes'

describe('lessonQuizzes registry', () => {
	beforeEach(() => {
		lessonQuizzes.entries.splice(0)
	})

	it('lists a registered quiz and forgets it once unregistered', () => {
		const unregister = registerLessonQuiz({ name: 'quiz-a', open: () => {} })
		expect(lessonQuizzes.entries.map((e) => e.name)).toEqual(['quiz-a'])
		unregister()
		expect(lessonQuizzes.entries).toEqual([])
	})

	it('keeps the other quizzes of the lesson when one unregisters', () => {
		const first = registerLessonQuiz({ name: 'quiz-a', open: () => {} })
		registerLessonQuiz({ name: 'quiz-b', open: () => {} })
		first()
		expect(lessonQuizzes.entries.map((e) => e.name)).toEqual(['quiz-b'])
	})

	it('unregistering twice does not remove another quiz', () => {
		const first = registerLessonQuiz({ name: 'quiz-a', open: () => {} })
		registerLessonQuiz({ name: 'quiz-b', open: () => {} })
		first()
		first()
		expect(lessonQuizzes.entries.map((e) => e.name)).toEqual(['quiz-b'])
	})
})

describe('needsLeaveConfirmation', () => {
	it('asks only when a quiz is running and an answer was given', () => {
		expect(needsLeaveConfirmation({ inProgress: true, hasAnswers: true })).toBe(true)
		expect(needsLeaveConfirmation({ inProgress: true, hasAnswers: false })).toBe(false)
		expect(needsLeaveConfirmation({ inProgress: false, hasAnswers: true })).toBe(false)
		expect(needsLeaveConfirmation({ inProgress: undefined, hasAnswers: undefined })).toBe(false)
	})
})
