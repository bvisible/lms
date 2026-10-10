//// Neoffice — added file (no upstream equivalent)
// Enlarged view of the films hosted on the hub (a `<video controls>` in a lesson, in the course card, in the lesson editor preview).
//
// Why: the browser's own full screen gives the film a box the size of the screen. On a very wide screen the picture can end up scaled to the
// width of the box and its top and bottom are cut (seen on an ultra-wide screen, 10 October 2026). Here the film is shown in a dialog that
// covers the page and keeps the whole picture (`object-fit: contain`, black bars on the sides), and the browser's full screen is asked for the
// dialog, never for the film. The native full-screen button of the small player is hidden (`nofullscreen`) and replaced by a button that
// appears on the film when the pointer is over it.
//
// Plain DOM on purpose: the three places that show a lesson film (the learner page, the course card and the editor preview) draw their `<video>`
// in different ways, none of which we want to fork. Only attributes are touched on the films themselves, never their place in the DOM.
export const VIEWER_ATTRIBUTE = 'data-neo-viewer'

const translate = (message: string): string => {
	const t = (window as unknown as { __?: (m: string) => string }).__
	return t ? t(message) : message
}

const supportsHover = (): boolean =>
	typeof window.matchMedia !== 'function' || window.matchMedia('(hover: hover)').matches

// The bottom of a film with controls belongs to the browser's control bar (play, time, volume…): a click there keeps its own meaning.
const CONTROL_BAR_HEIGHT = 56

let zoomButton: HTMLButtonElement | null = null
let zoomTarget: HTMLVideoElement | null = null

export function enhanceVideos(root: ParentNode = document): void {
	if (!supportsHover()) return // on a touch screen the native full screen stays: there is no pointer to hover with
	root.querySelectorAll<HTMLVideoElement>(`video[controls]:not([${VIEWER_ATTRIBUTE}])`).forEach((video) => {
		if (video.closest('.neo-video-viewer')) return
		video.setAttribute(VIEWER_ATTRIBUTE, '1')
		const list = (video.getAttribute('controlslist') || '').split(/\s+/).filter(Boolean)
		if (!list.includes('nofullscreen')) list.push('nofullscreen')
		video.setAttribute('controlslist', list.join(' '))
	})
}

function ensureButton(): HTMLButtonElement {
	if (zoomButton) return zoomButton
	const button = document.createElement('button')
	button.type = 'button'
	button.className = 'neo-video-zoom'
	button.setAttribute('aria-label', translate('Enlarge the video'))
	button.title = translate('Enlarge the video')
	button.style.cssText =
		'position:fixed;z-index:2147482000;display:none;width:36px;height:36px;border:0;border-radius:8px;padding:0;cursor:pointer;' +
		'align-items:center;justify-content:center;background:rgba(0,0,0,.62);color:#fff;'
	button.innerHTML =
		'<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" ' +
		'stroke-linejoin="round" aria-hidden="true"><path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/></svg>'
	button.addEventListener('click', (event) => {
		event.stopPropagation()
		if (zoomTarget) openViewer(zoomTarget)
	})
	document.body.appendChild(button)
	zoomButton = button
	return button
}

function showButtonOver(video: HTMLVideoElement): void {
	const rect = video.getBoundingClientRect()
	if (rect.width < 160 || rect.height < 90) return hideButton()
	const button = ensureButton()
	zoomTarget = video
	button.style.display = 'flex'
	button.style.top = `${Math.round(rect.top + 10)}px`
	button.style.left = `${Math.round(rect.right - 46)}px`
}

function hideButton(): void {
	if (zoomButton) zoomButton.style.display = 'none'
	zoomTarget = null
}

export function openViewer(source: HTMLVideoElement): HTMLElement | null {
	if (document.querySelector('.neo-video-viewer')) return null
	const startAt = source.currentTime || 0
	source.pause()
	hideButton()

	const overlay = document.createElement('div')
	overlay.className = 'neo-video-viewer'
	overlay.setAttribute('role', 'dialog')
	overlay.setAttribute('aria-modal', 'true')
	overlay.setAttribute('aria-label', translate('Enlarge the video'))
	overlay.style.cssText = 'position:fixed;inset:0;z-index:2147483000;display:flex;align-items:center;justify-content:center;background:#000;'

	const video = document.createElement('video')
	video.src = source.currentSrc || source.getAttribute('src') || source.querySelector('source')?.getAttribute('src') || ''
	video.controls = true
	video.playsInline = true
	video.setAttribute('controlslist', 'nodownload nofullscreen')
	// The whole picture, whatever the shape of the screen: it is scaled to fit inside the box, never to fill it.
	video.style.cssText = 'width:100%;height:100%;object-fit:contain;background:#000;outline:none;'
	video.addEventListener(
		'loadedmetadata',
		() => {
			video.currentTime = startAt
			void video.play().catch(() => {})
		},
		{ once: true }
	)

	// The lesson page counts a film as watched when the `ended` event of ITS film fires, and reads its currentTime when it saves the watch time.
	// What is watched in the dialog is therefore told to the film of the page, or enlarging the film would stop the lesson from being validated.
	const report = () => {
		if (video.currentTime) source.currentTime = video.currentTime
	}
	video.addEventListener('pause', report)
	video.addEventListener('ended', () => {
		report()
		source.dispatchEvent(new Event('ended'))
	})

	const close = document.createElement('button')
	close.type = 'button'
	close.setAttribute('aria-label', translate('Close the enlarged view'))
	close.title = translate('Close the enlarged view')
	close.style.cssText =
		'position:absolute;top:14px;right:14px;z-index:1;width:40px;height:40px;border:0;border-radius:10px;cursor:pointer;' +
		'background:rgba(255,255,255,.18);color:#fff;font-size:26px;line-height:1;'
	close.textContent = '\u00d7'

	const finish = () => {
		const at = video.currentTime
		video.pause()
		document.removeEventListener('keydown', onKey, true)
		if (document.fullscreenElement === overlay) void document.exitFullscreen().catch(() => {})
		overlay.remove()
		if (at) source.currentTime = at
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
	// The browser's full screen is asked for the dialog, not the film: the film stays inside its box and keeps its shape.
	if (typeof overlay.requestFullscreen === 'function') void overlay.requestFullscreen().catch(() => {})
	close.focus({ preventScroll: true })
	return overlay
}

let installed = false

export function installLessonVideoViewer(): void {
	if (installed || typeof document === 'undefined') return
	installed = true
	let queued = false
	const schedule = () => {
		if (queued) return
		queued = true
		requestAnimationFrame(() => {
			queued = false
			enhanceVideos(document)
		})
	}
	new MutationObserver(schedule).observe(document.body, { childList: true, subtree: true })
	document.addEventListener(
		'pointermove',
		(event) => {
			const target = event.target as Element | null
			if (!target || target === zoomButton || zoomButton?.contains(target)) return
			const video = target.closest?.(`video[${VIEWER_ATTRIBUTE}]`) as HTMLVideoElement | null
			if (video) showButtonOver(video)
			else hideButton()
		},
		{ passive: true }
	)
	// A click on the picture of an enhanced film opens the enlarged view instead of playing or pausing it (Daniel, 10 October 2026): the viewer
	// starts the film. The control bar at the bottom keeps its buttons. The listener is in the capture phase so that the browser's own
	// click-to-play, which lives on the film, never sees the click.
	document.addEventListener(
		'click',
		(event) => {
			const target = event.target as Element | null
			if (!target || target === zoomButton || zoomButton?.contains(target)) return
			const video = target.closest?.(`video[${VIEWER_ATTRIBUTE}]`) as HTMLVideoElement | null
			if (!video) return
			const rect = video.getBoundingClientRect()
			if (event.clientY > rect.bottom - CONTROL_BAR_HEIGHT) return
			event.preventDefault()
			event.stopPropagation()
			openViewer(video)
		},
		true
	)
	window.addEventListener('scroll', hideButton, { passive: true, capture: true })
	window.addEventListener('resize', hideButton, { passive: true })
	enhanceVideos(document)
}
