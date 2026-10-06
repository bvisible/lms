//// Neoffice — added file (no upstream equivalent).
//// The quiz of a lesson opens in a window (QuizBlock.vue) instead of inline at the end of a long lesson. Each QuizBlock
//// registers itself here so that the bar at the top of the lesson (LessonQuizBar.vue) can open it, wherever the quiz
//// block was mounted: the Markdown renderer and the EditorJS read-only tool each mount QuizBlock as their own Vue app,
//// and a module-level reactive object is the one thing those apps share.
import { reactive } from 'vue'

export const lessonQuizzes = reactive({ entries: [] })

let nextId = 1

/** Registers a quiz of the current lesson. Returns the function that unregisters it. */
export function registerLessonQuiz(entry) {
	const id = nextId++
	lessonQuizzes.entries.push({ ...entry, id })
	return () => {
		const index = lessonQuizzes.entries.findIndex((item) => item.id === id)
		if (index !== -1) lessonQuizzes.entries.splice(index, 1)
	}
}

/**
 * Closing the quiz window asks first only when a quiz is running AND an answer was given: leaving a quiz nobody
 * answered costs nothing, and a quiz already handed in has nothing left to lose.
 */
export function needsLeaveConfirmation({ inProgress, hasAnswers }) {
	return Boolean(inProgress && hasAnswers)
}
