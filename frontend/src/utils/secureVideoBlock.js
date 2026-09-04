//// Neoffice — added file (no upstream equivalent), 8aa18a4b « un bloc « Vidéo protégée »
//// dans l'éditeur de leçon ».
//// The EditorJS tool that puts a protected video in a lesson. An EditorJS block lives
//// outside the Vue tree, so it mounts its own app (createApp) and re-installs the
//// translation plugin — neither provide/inject nor the global `__` reach it otherwise.
//// At the merge: kept whole; only its registration in utils/index.js meets upstream.
import { createApp, h } from 'vue'
import { call } from 'frappe-ui'
import { MonitorPlay } from 'lucide-vue-next'
import SecureVideo from '@/components/SecureVideo.vue'
import translationPlugin from '../translation'

/**
 * The « Protected video » block — an Infomaniak VOD video, chosen from a list.
 *
 * 🔑 Jérémy, 2026-08-04: *« on met où dans l'ERP ? pas vu »*. Attaching a video
 * meant typing `{{ SecureVideo("1jijk03umkoek") }}` into the lesson body, with
 * an id readable only in the Infomaniak manager. Nobody invents a thirteen-
 * character string, so in practice nobody attached a video.
 *
 * Built on the same pattern as the Quiz tool: one class serves BOTH sides —
 * EditorJS renders the lesson read-only with the very same tools, so the block
 * that shows a picker to the author shows the player to the learner. Two
 * implementations would drift, and the one nobody tests is the reader's.
 *
 * The block stores the media id, never a playable URL: a leaked lesson body is
 * worthless without `get_playback_url`, which checks the subscription and signs
 * a link that lives five minutes.
 */
export class SecureVideoBlock {
	constructor({ data, api, readOnly, config }) {
		this.data = data && Object.keys(data).length ? data : {}
		this.readOnly = readOnly
		// The player needs the lesson: the server refuses to sign a media the
		// lesson does not reference. Passed through the tool config because an
		// EditorJS block lives outside the app's Vue tree — no provide/inject.
		this.lesson = (config && config.lessonName) || ''
	}

	static get toolbox() {
		const app = createApp({
			render: () => h(MonitorPlay, { size: 5, strokeWidth: 1.5 }),
		})
		const div = document.createElement('div')
		app.mount(div)
		return {
			title: __('Protected video'),
			icon: div.innerHTML,
		}
	}

	static get isReadOnlySupported() {
		return true
	}

	render() {
		this.wrapper = document.createElement('div')
		if (this.data.media) this.renderVideo()
		else this.renderPicker()
		return this.wrapper
	}

	renderVideo() {
		if (this.readOnly) {
			this.app = createApp(SecureVideo, {
				media: this.data.media,
				lesson: this.lesson,
			})
			this.app.use(translationPlugin)
			// Contain a player failure to this block: inline in the lesson's
			// render tree, an uncaught error would blank the whole lesson.
			this.app.config.errorHandler = (err) => {
				console.error('[lms] secure video failed to render', err)
			}
			this.app.mount(this.wrapper)
			return
		}
		// In the editor, a card rather than a player: an author scrolling
		// through a lesson should not start five videos.
		this.wrapper.innerHTML = `
			<div class="border rounded-md p-4 bg-surface-sidebar mb-4">
				<div class="font-medium">${__('Protected video')}: ${
					this.data.name || this.data.media
				}</div>
				<div class="text-sm text-ink-gray-5 mt-1">${this.data.media}</div>
			</div>`
	}

	renderPicker() {
		if (this.readOnly) return
		this.wrapper.innerHTML = `<div class="border rounded-md p-4 text-center bg-surface-sidebar mb-4 text-sm text-ink-gray-5">${__(
			'Loading the videos…'
		)}</div>`

		call('lms.lms.neoffice_video.list_media')
			.then((medias) => {
				if (!medias || !medias.length) {
					this.wrapper.innerHTML = `<div class="border rounded-md p-4 text-center bg-surface-sidebar mb-4 text-sm text-ink-gray-5">${__(
						'No video in the space yet. Upload them in the Infomaniak manager.'
					)}</div>`
					return
				}
				const lignes = medias
					.map(
						(m) => `
						<button type="button" class="nb-pick block w-full text-left px-3 py-2 rounded hover:bg-surface-gray-2"
							data-media="${m.id}" data-name="${(m.name || '').replace(/"/g, '&quot;')}">
							${m.name || m.id}
							${
								m.ready
									? ''
									: `<span class="text-ink-gray-5"> — ${__('still encoding')}</span>`
							}
						</button>`
					)
					.join('')
				this.wrapper.innerHTML = `
					<div class="border rounded-md p-3 bg-surface-sidebar mb-4">
						<div class="text-sm text-ink-gray-5 px-3 pb-2">${__('Choose a video')}</div>
						${lignes}
					</div>`
				this.wrapper.querySelectorAll('.nb-pick').forEach((b) => {
					b.addEventListener('click', () => {
						this.data = {
							media: b.dataset.media,
							name: b.dataset.name,
						}
						this.renderVideo()
					})
				})
			})
			.catch(() => {
				// Say which screen fixes it. « Something went wrong » sends the
				// author looking for the fault in their lesson.
				this.wrapper.innerHTML = `<div class="border rounded-md p-4 text-center bg-surface-sidebar mb-4 text-sm text-ink-gray-5">${__(
					'The video space did not answer. Check Learning › Settings › Videos.'
				)}</div>`
			})
	}

	save() {
		if (!this.data.media) return {}
		return { media: this.data.media, name: this.data.name || '' }
	}

	destroy() {
		this.app?.unmount()
	}
}
