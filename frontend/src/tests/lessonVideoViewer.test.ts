//// Neoffice — added file (no upstream equivalent)
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enhanceVideos, installLessonVideoViewer, openViewer, VIEWER_ATTRIBUTE } from '@/utils/lessonVideoViewer'

const filmWithControls = () => {
	const video = document.createElement('video')
	video.setAttribute('controls', '')
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

	it('takes the control bar off a film of the page, so that nothing is drawn over its picture', () => {
		const video = filmWithControls()
		enhanceVideos(document)
		expect(video.getAttribute(VIEWER_ATTRIBUTE)).toBe('1')
		expect(video.hasAttribute('controls')).toBe(false)
		expect(video.style.cursor).toBe('pointer')
		expect(document.querySelectorAll('.neo-video-mark').length).toBe(1) // the play mark
		enhanceVideos(document) // a second pass changes nothing
		expect(document.querySelectorAll('.neo-video-mark').length).toBe(1)
	})

	it('shows the jpg next to a film as its poster, and keeps a poster that is already there', () => {
		const film = filmWithControls()
		const withPoster = document.createElement('video')
		withPoster.setAttribute('controls', '')
		withPoster.setAttribute('src', '/files/other.mp4')
		withPoster.setAttribute('poster', '/files/cover.png')
		const withSource = document.createElement('video')
		withSource.setAttribute('controls', '')
		withSource.innerHTML = '<source src="/files/third.mp4" type="video/mp4">'
		document.body.append(withPoster, withSource)
		enhanceVideos(document)
		expect(film.getAttribute('poster')).toBe('/files/film.jpg')
		expect(withPoster.getAttribute('poster')).toBe('/files/cover.png')
		expect(withSource.getAttribute('poster')).toBe('/files/third.jpg')
	})

	it('leaves a video without controls alone', () => {
		const video = document.createElement('video')
		document.body.appendChild(video)
		enhanceVideos(document)
		expect(video.hasAttribute(VIEWER_ATTRIBUTE)).toBe(false)
	})

	it('opens a pop-up that shows the whole picture, with the controls below it and not over it, and never asks for the browser full screen', () => {
		const requestFullscreen = vi.fn(() => Promise.resolve())
		Element.prototype.requestFullscreen = requestFullscreen
		const source = filmWithControls()
		const overlay = openViewer(source) as HTMLElement
		expect(overlay).toBeTruthy()
		expect(overlay.getAttribute('role')).toBe('dialog')
		const film = overlay.querySelector('video') as HTMLVideoElement
		expect(film.getAttribute('src')).toBe('/files/film.mp4')
		expect(film.style.objectFit).toBe('contain') // never "cover": a very wide screen must not cut the top and the bottom
		expect(film.hasAttribute('controls')).toBe(false) // the browser's own bar would be drawn over the picture
		// the dimmed page holds one centred box, a column: the head (title and cross), the stage (with the picture), then the control bar
		expect(overlay.style.background).toContain('rgba(20, 20, 20, 0.62)')
		expect(overlay.children.length).toBe(1)
		const box = overlay.children[0] as HTMLElement
		expect(box.style.flexDirection).toBe('column')
		// the width (1000 px at most, 92 % of the window, never taller than it) is a CSS min(), which jsdom drops: measured in a real browser instead
		const [head, stage, bar] = Array.from(box.children) as HTMLElement[]
		expect(head.textContent).toContain('×')
		expect(stage.style.aspectRatio).toBe('16/9')
		expect(film.style.margin).toBe('0px') // a content stylesheet that puts a top margin on media must not push the film down
		expect(stage.contains(film)).toBe(true)
		expect(bar.contains(film)).toBe(false)
		expect(requestFullscreen).not.toHaveBeenCalled() // a pop-up, not the full screen: nothing is left to cut the top and the bottom
		expect(bar.querySelectorAll('[role="slider"]').length).toBe(2) // the seek bar and the volume, drawn by hand
		expect(source.pause).toHaveBeenCalled()
		expect(openViewer(source)).toBeNull() // one dialog at a time
		document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
		expect(document.querySelector('.neo-video-viewer')).toBeNull()
	})

	it('plays and pauses from the control bar and from the picture of the dialog', () => {
		const overlay = openViewer(filmWithControls()) as HTMLElement
		const film = overlay.querySelector('video') as HTMLVideoElement
		const [, stage, bar] = Array.from((overlay.children[0] as HTMLElement).children) as HTMLElement[]
		;(bar.querySelector('button') as HTMLButtonElement).click() // first button: play / pause
		expect(film.play).toHaveBeenCalled()
		stage.click()
		expect(film.play).toHaveBeenCalledTimes(2) // the film in jsdom stays paused: a click on the picture asks to play again
	})

	it('opens the dialog when the picture of a film of the page is clicked, and the click never reaches the film', () => {
		installLessonVideoViewer()
		const source = filmWithControls()
		enhanceVideos(document)
		const reachedFilm = vi.fn()
		source.addEventListener('click', reachedFilm)
		source.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, clientX: 100, clientY: 100 }))
		expect(document.querySelector('.neo-video-viewer')).not.toBeNull()
		expect(reachedFilm).not.toHaveBeenCalled()
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

	it('closes with its cross, with Escape and with a click on the dimmed page around the pop-up', () => {
		const source = filmWithControls()
		let overlay = openViewer(source) as HTMLElement
		const close = Array.from(overlay.querySelectorAll('button')).find((b) => b.getAttribute('aria-label') === 'Close the enlarged view') as HTMLButtonElement
		close.click()
		expect(document.querySelector('.neo-video-viewer')).toBeNull()
		overlay = openViewer(source) as HTMLElement
		overlay.click()
		expect(document.querySelector('.neo-video-viewer')).toBeNull()
	})
})
