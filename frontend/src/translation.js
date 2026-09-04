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

function translate(message) {
	let translatedMessages = window.translatedMessages || {}
	let translatedMessage = translatedMessages[message] || message

	const hasPlaceholders = /{\d+}/.test(message)
	if (!hasPlaceholders) {
		return translatedMessage
	}
	return {
		format: function (...args) {
			return translatedMessage.replace(
				/{(\d+)}/g,
				function (match, number) {
					return typeof args[number] != 'undefined'
						? args[number]
						: match
				}
			)
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
