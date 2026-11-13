import { createResource } from 'frappe-ui'
//// Neoffice — c1d10eb2 « menu en anglais à la première visite d'un visiteur anonyme ».
//// Upstream only sets `window.translatedMessages` and never says when it landed, so any
//// label computed once (a Vue computed, a prop handed to a non-Vue widget — our cockpit
//// menu) froze in English on a cold visit. `translationsReady` is the missing signal.
//// Worth proposing upstream; until then it is ours.
import { ref } from 'vue'

/**
 * Flips once the translation dictionary has landed.
 *
 * `__()` reads a plain `window` global, so anything that computes a label ONCE —
 * a Vue computed, a prop passed to a non-Vue widget — freezes on whatever was
 * available at that moment. The dictionary is ~3 MB, so on a cold visit it
 * arrives well after the first render and those labels stay in English. Depend
 * on this ref to recompute when it does.
 */
export const translationsReady = ref(Boolean(window.translatedMessages))

export default function translationPlugin(app) {
	app.config.globalProperties.__ = translate
	window.__ = translate
	if (!window.translatedMessages) fetchTranslations()
}

//// Neoffice — backport of upstream develop 3179f026c (15 October 2026): `__` also takes its values the Desk way,
//// __('{0} students', [n]), and returns a string. The version-15 line's bulk-enrollment screens call it so, while its
//// translate() ignored the list and returned the `{ format }` object: the dialog's count and its Enroll button read "{}".
//// Remove when upstream's version-15 line carries the same change.
function fill(message, args) {
	return message.replace(/{(\d+)}/g, function (match, number) {
		return typeof args[number] != 'undefined' ? args[number] : match
	})
}

function translate(message, replace) {
	//// Neoffice — read the ref here, so every render and every computed that translates depends on it and runs again
	//// when the dictionary lands. Without it a cold visit kept the labels of the first render in English (« Courses »,
	//// « New Course » under a page already titled « Cours »), neoffice-maintenance#1250. Harmless outside a render.
	void translationsReady.value
	let translatedMessages = window.translatedMessages || {}
	let translatedMessage = translatedMessages[message] || message

	if (Array.isArray(replace)) return fill(translatedMessage, replace) //// Neoffice — see fill() above

	const hasPlaceholders = /{\d+}/.test(message)
	if (!hasPlaceholders) {
		return translatedMessage
	}
	return {
		format: function (...args) {
			return fill(translatedMessage, args) //// Neoffice — see fill() above
		},
	}
}

function fetchTranslations(lang) {
	createResource({
		url: 'lms.lms.api.get_translations',
		cache: 'translations',
		auto: true,
		transform: (data) => {
			window.translatedMessages = data
			//// Neoffice — c1d10eb2: the other half of `translationsReady` above.
			translationsReady.value = true
		},
	})
}
