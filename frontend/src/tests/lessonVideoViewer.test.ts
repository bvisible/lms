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

// jsdom has no media engine: the position of a film is a plain property here
const withPosition = (video: HTMLVideoElement, at = 0) => {
	Object.defineProperty(video, 'currentTime', { value: at, writable: true, configurable: true })
	return video
}

describe('lessonVideoViewer', () => {
	beforeEach(() => {
		window.HTMLMediaElement.prototype.pause = vi.fn()
		window.HTMLMediaElement.prototype.play = vi.fn(() => Promise.resolve())
	})
	afterEach(() => {
		document.body.innerHTML = ''
		document.body.style.overflow = ''
	})

	it('keeps the native controls of a film of the page and takes the browser full screen off it', () => {
		const video = filmWithControls()
		enhanceVideos(document)
		expect(video.getAttribute(VIEWER_ATTRIBUTE)).toBe('1')
		expect(video.hasAttribute('controls')).toBe(true) // Play in the strip of the player plays the film in the page
		expect(video.getAttribute('controlsList')).toContain('nofullscreen') // the pop-up is the enlarged view, not the browser's full screen
		expect(video.style.cursor).toBe('zoom-in')
		enhanceVideos(document) // a second pass changes nothing
		expect(video.getAttribute('controlsList')).toBe('nodownload nofullscreen')
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

	it('opens a pop-up with the film alone, its native controls and a round cross, and never asks for the browser full screen', () => {
		const requestFullscreen = vi.fn(() => Promise.resolve())
		Element.prototype.requestFullscreen = requestFullscreen
		const source = withPosition(filmWithControls())
		const overlay = openViewer(source) as HTMLElement
		expect(overlay).toBeTruthy()
		expect(overlay.getAttribute('role')).toBe('dialog')
		expect(overlay.style.background).toContain('0.78') // the dimmed page (78 % black, as in the manual)
		const [film, cross] = Array.from(overlay.children) as HTMLElement[]
		expect(film.tagName).toBe('VIDEO')
		expect((film as HTMLVideoElement).controls).toBe(true) // the same native controls as the manual's pop-up
		expect(film.getAttribute('src')).toBe('/files/film.mp4')
		expect((film as HTMLVideoElement).style.margin).toBe('0px') // a content stylesheet's top margin on media must not push it down
		expect(cross.tagName).toBe('BUTTON')
		expect(cross.style.borderRadius).toBe('999px')
		expect(source.pause).toHaveBeenCalled()
		expect(document.body.style.overflow).toBe('hidden')
		expect(requestFullscreen).not.toHaveBeenCalled()
		expect(openViewer(source)).toBeNull() // one pop-up at a time
		// the size (92vw, 88vh × the ratio of the film) is a CSS min(): jsdom drops it, so it is measured in a real browser instead
	})

	it('carries the position both ways: the film starts where the small player was, the small player resumes where the pop-up stopped', () => {
		const source = withPosition(filmWithControls(), 12)
		const overlay = openViewer(source) as HTMLElement
		const film = withPosition(overlay.querySelector('video') as HTMLVideoElement, 0)
		film.dispatchEvent(new Event('loadedmetadata'))
		expect(film.currentTime).toBe(12)
		expect(film.play).toHaveBeenCalled() // clicking to enlarge means wanting to watch it
		film.currentTime = 30
		;(overlay.querySelector('button') as HTMLButtonElement).click()
		expect(source.currentTime).toBe(30)
		expect(document.querySelector('.neo-video-viewer')).toBeNull()
		expect(document.body.style.overflow).toBe('')
	})

	// jsdom has no media engine: whether a film is playing is a plain property here
	const setPlaying = (video: HTMLVideoElement, playing: boolean) =>
		Object.defineProperty(video, 'paused', { value: !playing, configurable: true })
	const clickAt = (video: HTMLVideoElement, clientY: number) =>
		video.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, clientX: 100, clientY }))
	const filmOnPage = () => {
		installLessonVideoViewer()
		const source = filmWithControls()
		source.getBoundingClientRect = () => ({ top: 0, bottom: 400, left: 0, right: 700, width: 700, height: 400, x: 0, y: 0, toJSON: () => ({}) })
		enhanceVideos(document)
		return source
	}

	it('starts a film that is not playing in the page when its picture is clicked: the pop-up is the second click', () => {
		const source = filmOnPage()
		const reachedFilm = vi.fn()
		source.addEventListener('click', reachedFilm)
		clickAt(source, 100)
		expect(source.play).toHaveBeenCalledTimes(1) // first click: it plays in the page
		expect(document.querySelector('.neo-video-viewer')).toBeNull()
		expect(reachedFilm).not.toHaveBeenCalled() // the player's own click-to-play never sees it: no double toggle
	})

	it('opens the pop-up when the picture of a film that is playing is clicked, from where the film is', () => {
		const source = filmOnPage()
		setPlaying(source, true)
		clickAt(source, 100)
		expect(document.querySelector('.neo-video-viewer')).not.toBeNull() // second click: the pop-up
		expect(source.pause).toHaveBeenCalled() // the small player stops, the pop-up carries on
		document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
		expect(document.querySelector('.neo-video-viewer')).toBeNull()
	})

	it('starts a film that has ended again in the page, and leaves a click in the strip of native controls to the player', () => {
		const source = filmOnPage()
		Object.defineProperty(source, 'ended', { value: true, configurable: true })
		clickAt(source, 100)
		expect(source.play).toHaveBeenCalledTimes(1)
		setPlaying(source, true)
		const reachedFilm = vi.fn()
		source.addEventListener('click', reachedFilm)
		clickAt(source, 380) // the 52 px at the bottom are the native Play / volume / seek bar, whatever the film is doing
		expect(document.querySelector('.neo-video-viewer')).toBeNull()
		expect(reachedFilm).toHaveBeenCalledTimes(1)
	})

	it('tells the film of the page when the film of the pop-up ends, so that the lesson is still validated', () => {
		const source = withPosition(filmWithControls())
		const onEnded = vi.fn()
		source.addEventListener('ended', onEnded)
		const overlay = openViewer(source) as HTMLElement
		const film = overlay.querySelector('video') as HTMLVideoElement
		film.dispatchEvent(new Event('ended'))
		expect(onEnded).toHaveBeenCalledTimes(1)
	})

	it('closes with its cross, with Escape and with a click on the dimmed page around the film, but not with a click on the film', () => {
		const source = withPosition(filmWithControls())
		let overlay = openViewer(source) as HTMLElement
		;(overlay.querySelector('button') as HTMLButtonElement).click()
		expect(document.querySelector('.neo-video-viewer')).toBeNull()
		overlay = openViewer(source) as HTMLElement
		;(overlay.querySelector('video') as HTMLVideoElement).click()
		expect(document.querySelector('.neo-video-viewer')).not.toBeNull() // a click on the film is the player's own business
		overlay.click()
		expect(document.querySelector('.neo-video-viewer')).toBeNull()
		openViewer(source)
		document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
		expect(document.querySelector('.neo-video-viewer')).toBeNull()
	})
})
