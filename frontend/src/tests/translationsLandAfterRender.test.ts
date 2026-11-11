//// Neoffice — added file (no upstream equivalent)
/**
 * translation.js: on a cold visit the ~3 MB dictionary lands after the first render, and
 * `__()` reads a plain window global, so every label rendered before it stayed in English
 * until something else re-rendered its component (neoffice-maintenance#1250: « Courses »,
 * « New Course », the tabs of the catalogue, while the page title already said « Cours »).
 */
import { describe, expect, it, vi } from 'vitest'
import { computed, createApp, defineComponent, h, nextTick } from 'vue'

let landDictionary: ((data: Record<string, string>) => void) | undefined

vi.mock('frappe-ui', () => ({
	createResource: (opts: { transform: (data: Record<string, string>) => void }) => {
		landDictionary = opts.transform
		return {}
	},
}))

describe('labels rendered before the dictionary lands', () => {
	it('are translated once it lands, in a template and in a computed', async () => {
		delete (window as { translatedMessages?: unknown }).translatedMessages
		const { default: translationPlugin } = await import('@/translation')

		const Page = defineComponent({
			setup() {
				const tab = computed(() => window.__('Published'))
				return { tab }
			},
			render() {
				return h('div', [h('h1', this.__('Courses')), h('span', this.tab)])
			},
		})
		const el = document.createElement('div')
		const app = createApp(Page)
		app.use(translationPlugin)
		app.mount(el)
		expect(el.textContent).toBe('CoursesPublished')

		landDictionary?.({ Courses: 'Cours', Published: 'Publié' })
		await nextTick()

		expect(el.textContent).toBe('CoursPublié')
		app.unmount()
	})
})
