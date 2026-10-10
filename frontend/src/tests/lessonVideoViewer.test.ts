//// Neoffice — added file (no upstream equivalent)
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enhanceVideos, installLessonVideoViewer, openViewer, VIEWER_ATTRIBUTE } from '@/utils/lessonVideoViewer'

const filmWithControls = () => {
	const video = document.createElement('video')
	video.setAttribute('controls', '')
	video.setAttribute('controlslist', 'nodownload')
	video.setAttribute('src', '/files/film.mp4')
	document.body.appendChild(video)
	return video
}

describe('lessonVideoViewer', () => {
	beforeEach(() => {
		window.HTMLMediaElement.prototype.pause = vi.fn()
		window.HTMLMediaElement.prototype.play = vi.fn(() => Promise.resolve())
	})
	afterEach(() => {
		document.body.innerHTML = ''
	})

	it('hides the native full screen of a film with controls, keeping the other controls list entries', () => {
		const video = filmWithControls()
		enhanceVideos(document)
		expect(video.getAttribute(VIEWER_ATTRIBUTE)).toBe('1')
		expect(video.getAttribute('controlslist')).toBe('nodownload nofullscreen')
		enhanceVideos(document) // a second pass changes nothing
		expect(video.getAttribute('controlslist')).toBe('nodownload nofullscreen')
	})

	it('leaves a video without controls alone', () => {
		const video = document.createElement('video')
		document.body.appendChild(video)
		enhanceVideos(document)
		expect(video.hasAttribute(VIEWER_ATTRIBUTE)).toBe(false)
	})

	it('opens a dialog that shows the whole picture, not a cropped one, and closes on Escape', () => {
		const source = filmWithControls()
		const overlay = openViewer(source) as HTMLElement
		expect(overlay).toBeTruthy()
		expect(overlay.getAttribute('role')).toBe('dialog')
		const film = overlay.querySelector('video') as HTMLVideoElement
		expect(film.getAttribute('src')).toBe('/files/film.mp4')
		expect(film.style.objectFit).toBe('contain') // never "cover": a very wide screen must not cut the top and the bottom
		expect(film.style.width).toBe('100%')
		expect(film.style.height).toBe('100%')
		expect(film.getAttribute('controlslist')).toContain('nofullscreen')
		expect(source.pause).toHaveBeenCalled()
		expect(openViewer(source)).toBeNull() // one dialog at a time
		document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
		expect(document.querySelector('.neo-video-viewer')).toBeNull()
	})

	it('tells the film of the page when the enlarged film ends, so that the lesson is still validated', () => {
		const source = filmWithControls()
		const onEnded = vi.fn()
		source.addEventListener('ended', onEnded)
		const overlay = openViewer(source) as HTMLElement
		const film = overlay.querySelector('video') as HTMLVideoElement
		film.dispatchEvent(new Event('ended'))
		expect(onEnded).toHaveBeenCalledTimes(1)
	})

	it('opens the enlarged view when the picture is clicked, and leaves the control bar to the browser', () => {
		installLessonVideoViewer()
		const source = filmWithControls()
		source.getBoundingClientRect = () => ({ top: 0, bottom: 400, left: 0, right: 600, width: 600, height: 400, x: 0, y: 0, toJSON() {} }) as DOMRect
		enhanceVideos(document)
		// the bottom 56 px are the control bar: no dialog, the click goes on to the browser
		source.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, clientX: 100, clientY: 380 }))
		expect(document.querySelector('.neo-video-viewer')).toBeNull()
		// the picture: the dialog opens, and the click does not reach the film (no play / pause)
		const reachedFilm = vi.fn()
		source.addEventListener('click', reachedFilm)
		source.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, clientX: 100, clientY: 100 }))
		expect(document.querySelector('.neo-video-viewer')).not.toBeNull()
		expect(reachedFilm).not.toHaveBeenCalled()
	})

	it('closes with its button and with a click on the black around the film', () => {
		const source = filmWithControls()
		let overlay = openViewer(source) as HTMLElement
		;(overlay.querySelector('button') as HTMLButtonElement).click()
		expect(document.querySelector('.neo-video-viewer')).toBeNull()
		overlay = openViewer(source) as HTMLElement
		overlay.click()
		expect(document.querySelector('.neo-video-viewer')).toBeNull()
	})
})
