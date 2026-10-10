//// Neoffice — added file (no upstream equivalent)
// Enlarged view of the films hosted on the hub (a `<video controls>` in a lesson, in the course card, in the lesson editor preview).
//
// The same gesture and the same pop-up as the clips of the manual (wiki app, `neoffice-video.js` and `#video-viewer` in `neoffice-wiki.css`;
// Daniel, 10 October 2026: « ce n'est pas le même pop-up », « va regarder comme ça fait de l'autre côté »). The small player of the page stays a
// normal player, with the native strip of controls at the bottom (a click on its Play plays the film in the page). A click on the PICTURE, outside
// that strip, opens a pop-up over a dimmed page: the film alone, with its native controls, as wide as 92 % of the window allows without its height
// passing 88 % of it (so it enlarges a film on a small screen as well as on a big one), a round cross at the top right. Escape, a click outside the
// film and the cross close it. The playing position is carried both ways: the film starts where the small player was, and the small player
// resumes where the pop-up stopped. The browser's own full-screen button is taken off the small player (Chrome honours `controlsList`), which is
// what cut the top and the bottom of a 16:9 film on an ultra-wide screen.
//
// Plain DOM on purpose: the places that show a lesson film (the learner page, the course card and the editor preview) draw their `<video>` in
// different ways, none of which we want to fork. Only attributes are touched on the films themselves, never their place in the DOM.
export const VIEWER_ATTRIBUTE = 'data-neo-viewer'

const translate = (message: string): string => {
	const t = (window as unknown as { __?: (m: string) => string }).__
	return t ? t(message) : message
}

const supportsHover = (): boolean =>
	typeof window.matchMedia !== 'function' || window.matchMedia('(hover: hover)').matches

// px of native controls at the bottom of the small player: a click in that strip (play, volume, seek bar…) is left to the player.
const BAR = 52

export function enhanceVideos(root: ParentNode = document): void {
	root.querySelectorAll<HTMLVideoElement>(`video[controls]:not([${VIEWER_ATTRIBUTE}])`).forEach((video) => {
		if (video.closest('.neo-video-viewer')) return
		video.setAttribute(VIEWER_ATTRIBUTE, '1')
		// A film `foo.mp4` has its poster `foo.jpg` next to it: shown until the film is played (its first image is often the blank paper of the
		// opening of the series). A missing poster is simply not shown, so a new film only needs its image dropped next to it under the same name.
		if (!video.getAttribute('poster')) {
			const src = video.getAttribute('src') || video.querySelector('source')?.getAttribute('src') || ''
			if (/\.(mp4|webm|mov)$/i.test(src)) video.setAttribute('poster', src.replace(/\.(mp4|webm|mov)$/i, '.jpg'))
		}
		// On a touch screen there is no pointer to click the picture with: the native player stays as it is, full screen button included.
		if (!supportsHover()) return
		video.setAttribute('controlsList', 'nodownload nofullscreen')
		video.style.cursor = 'zoom-in'
	})
}

export function openViewer(source: HTMLVideoElement): HTMLElement | null {
	if (document.querySelector('.neo-video-viewer')) return null
	const startAt = source.currentTime || 0
	source.pause()
	const opener = document.activeElement as HTMLElement | null

	// the dimmed page; a click on it (not on the film) closes the pop-up
	const overlay = document.createElement('div')
	overlay.className = 'neo-video-viewer'
	overlay.setAttribute('role', 'dialog')
	overlay.setAttribute('aria-modal', 'true')
	overlay.setAttribute('aria-label', translate('Enlarge the video'))
	overlay.style.cssText =
		'position:fixed;inset:0;z-index:2147483000;display:flex;align-items:center;justify-content:center;background:rgb(0 0 0 / 78%);cursor:zoom-out;'

	// The window, not the clip, sets the size: as wide as 92vw allows without the height passing 88vh (--neo-ratio is the film's width / height, set
	// once its size is known). No margin of its own: a content stylesheet that puts a top margin on media must not push it down.
	const video = document.createElement('video')
	video.controls = true
	video.setAttribute('controlsList', 'nodownload')
	video.playsInline = true
	video.preload = 'auto'
	video.muted = source.muted
	video.src = source.currentSrc || source.getAttribute('src') || source.querySelector('source')?.getAttribute('src') || ''
	video.style.cssText =
		'display:block;margin:0;width:min(92vw,calc(88vh * var(--neo-ratio, 1.7778)));height:auto;background:#000;border-radius:10px;' +
		'box-shadow:0 20px 60px rgb(0 0 0 / 50%);cursor:default;outline:none;'
	video.addEventListener(
		'loadedmetadata',
		() => {
			if (video.videoWidth && video.videoHeight) video.style.setProperty('--neo-ratio', String(video.videoWidth / video.videoHeight))
			video.currentTime = startAt
			// Clicking to enlarge means wanting to watch it: always play, from where the small player was.
			void video.play().catch(() => {})
		},
		{ once: true }
	)

	const close = document.createElement('button')
	close.type = 'button'
	close.textContent = '×'
	close.setAttribute('aria-label', translate('Close the enlarged view'))
	close.title = translate('Close the enlarged view')
	close.style.cssText =
		'position:absolute;top:14px;right:18px;width:40px;height:40px;font-size:28px;line-height:1;color:#fff;background:rgb(255 255 255 / 14%);' +
		'border:0;border-radius:999px;cursor:pointer;'
	close.addEventListener('mouseenter', () => (close.style.background = 'rgb(255 255 255 / 28%)'))
	close.addEventListener('mouseleave', () => (close.style.background = 'rgb(255 255 255 / 14%)'))

	// The lesson page counts a film as watched when the `ended` event of ITS film fires, and reads its currentTime when it saves the watch time.
	// What is watched in the pop-up is therefore told to the film of the page, or enlarging the film would stop the lesson from being validated.
	const report = () => {
		if (video.currentTime) source.currentTime = video.currentTime
	}
	video.addEventListener('pause', report)
	video.addEventListener('ended', () => {
		report()
		source.dispatchEvent(new Event('ended'))
	})

	const previousOverflow = document.body.style.overflow
	const finish = () => {
		const at = video.currentTime
		video.pause()
		document.removeEventListener('keydown', onKey, true)
		overlay.remove()
		document.body.style.overflow = previousOverflow
		if (at) source.currentTime = at
		opener?.focus?.({ preventScroll: true })
	}
	const onKey = (event: KeyboardEvent) => {
		if (event.key !== 'Escape') return
		event.stopPropagation()
		finish()
	}
	close.addEventListener('click', finish)
	overlay.addEventListener('click', (event) => {
		if (event.target === overlay) finish()
	})
	document.addEventListener('keydown', onKey, true)

	overlay.append(video, close)
	document.body.appendChild(overlay)
	document.body.style.overflow = 'hidden'
	// the film has the focus, so that Space, the arrows and M work on it as on any native player
	video.focus({ preventScroll: true })
	return overlay
}

// ---- installation ----

let installed = false

export function installLessonVideoViewer(): void {
	if (installed || typeof document === 'undefined') return
	installed = true
	let queued = false
	const schedule = () => {
		if (queued) return
		queued = true
		// a timer, not requestAnimationFrame: a page opened in a background tab gets no animation frame, and its films would stay as they are
		setTimeout(() => {
			queued = false
			enhanceVideos(document)
		}, 40)
	}
	new MutationObserver(schedule).observe(document.body, { childList: true, subtree: true })
	// A click on the PICTURE of a film of the page opens the pop-up, which starts the film. The listener is in the capture phase so that the
	// browser's own click-to-play, which lives on the film, never sees the click; a click in the strip of native controls is left alone.
	document.addEventListener(
		'click',
		(event) => {
			if (!supportsHover()) return
			const target = event.target as Element | null
			const video = target?.closest?.(`video[${VIEWER_ATTRIBUTE}]`) as HTMLVideoElement | null
			if (!video || video.closest('.neo-video-viewer')) return
			if (event.clientY > video.getBoundingClientRect().bottom - BAR) return
			event.preventDefault()
			event.stopPropagation()
			event.stopImmediatePropagation()
			openViewer(video)
		},
		true
	)
	enhanceVideos(document)
}
