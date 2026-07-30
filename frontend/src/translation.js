import { createResource } from 'frappe-ui'
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
			translationsReady.value = true
		},
	})
}
