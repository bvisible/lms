//// Neoffice — added file (no upstream equivalent)
// Enlarged view of the films hosted on the hub (a `<video controls>` in a lesson, in the course card, in the lesson editor preview).
//
// Why. (1) The browser's own full screen gives the film a box the size of the screen: on a very wide screen the 16:9 picture can end up
// scaled to the width of the box and its top and bottom are cut (seen on an ultra-wide screen, 10 October 2026). (2) The browser's control
// bar is drawn OVER the bottom of the picture, with a dark gradient: the bottom of a screen recording is lost under it. (3) A click on the
// picture plays or pauses it, which is of little use on a small player.
//
// What. A film of the page keeps no control bar: it shows its picture, a play mark and a pointer cursor, and a click on it opens a dialog that
// covers the page. In the dialog the whole picture is shown (`object-fit: contain`, black bars on the sides if the screen is wider) and the
// controls are in a bar BELOW the picture, never over it. The browser's full screen is asked for the dialog, never for the film.
//
// Plain DOM on purpose: the three places that show a lesson film (the learner page, the course card and the editor preview) draw their
// `<video>` in different ways, none of which we want to fork. Only attributes are touched on the films themselves, never their place in the DOM.
export const VIEWER_ATTRIBUTE = 'data-neo-viewer'

const translate = (message: string): string => {
	const t = (window as unknown as { __?: (m: string) => string }).__
	return t ? t(message) : message
}

const supportsHover = (): boolean =>
	typeof window.matchMedia !== 'function' || window.matchMedia('(hover: hover)').matches

const SPEEDS = [1, 1.25, 1.5, 2, 0.75]
const BAR_HEIGHT = 56

const ICON = {
	play: '<path d="M8 5v14l11-7z" fill="currentColor" stroke="none"/>',
	pause: '<path d="M7 5h4v14H7zM13 5h4v14h-4z" fill="currentColor" stroke="none"/>',
	volume: '<path d="M11 5 6 9H2v6h4l5 4V5zM15.5 8.5a5 5 0 0 1 0 7M18.5 5.5a9 9 0 0 1 0 13"/>',
	muted: '<path d="M11 5 6 9H2v6h4l5 4V5zM22 9l-6 6M16 9l6 6"/>',
}
const svg = (inner: string, size = 22) =>
	`<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${inner}</svg>`

const formatTime = (seconds: number): string => {
	if (!Number.isFinite(seconds) || seconds < 0) seconds = 0
	const s = Math.floor(seconds)
	return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

// ---- the films of the page: no control bar, a play mark, a click opens the dialog ----

const marks = new Map<HTMLVideoElement, HTMLElement>()
let visible = new Set<HTMLVideoElement>()
let observer: IntersectionObserver | null = null
let ticking = false

function makeMark(): HTMLElement {
	const mark = document.createElement('div')
	mark.className = 'neo-video-mark'
	mark.setAttribute('aria-hidden', 'true')
	mark.style.cssText =
		'position:fixed;z-index:2147482000;display:none;width:64px;height:64px;margin:-32px 0 0 -32px;border-radius:50%;pointer-events:none;' +
		'align-items:center;justify-content:center;background:rgba(0,0,0,.55);color:#fff;'
	mark.innerHTML = svg(ICON.play, 30)
	document.body.appendChild(mark)
	return mark
}

function placeMarks(): void {
	ticking = false
	marks.forEach((mark, video) => {
		if (!video.isConnected) {
			mark.remove()
			marks.delete(video)
			visible.delete(video)
			return
		}
		const rect = video.getBoundingClientRect()
		const show = visible.has(video) && rect.width >= 120 && rect.height >= 68 && !document.querySelector('.neo-video-viewer')
		mark.style.display = show ? 'flex' : 'none'
		if (show) {
			mark.style.left = `${Math.round(rect.left + rect.width / 2)}px`
			mark.style.top = `${Math.round(rect.top + rect.height / 2)}px`
		}
	})
	if (visible.size) schedulePlacement()
}

function schedulePlacement(): void {
	if (ticking) return
	ticking = true
	requestAnimationFrame(placeMarks)
}

export function enhanceVideos(root: ParentNode = document): void {
	if (!supportsHover()) return // on a touch screen the native player stays: there is no pointer to click with
	root.querySelectorAll<HTMLVideoElement>(`video[controls]:not([${VIEWER_ATTRIBUTE}])`).forEach((video) => {
		if (video.closest('.neo-video-viewer')) return
		video.setAttribute(VIEWER_ATTRIBUTE, '1')
		video.removeAttribute('controls') // no control bar over the picture: the controls are in the dialog, below it
		video.style.cursor = 'pointer'
		if (typeof IntersectionObserver === 'function') {
			observer = observer || new IntersectionObserver((entries) => {
				entries.forEach((entry) => {
					const target = entry.target as HTMLVideoElement
					if (entry.isIntersecting) visible.add(target)
					else visible.delete(target)
				})
				schedulePlacement()
			})
			observer.observe(video)
		} else {
			visible.add(video)
		}
		marks.set(video, makeMark())
	})
	schedulePlacement()
}

// ---- the dialog ----

function button(label: string, inner: string): HTMLButtonElement {
	const b = document.createElement('button')
	b.type = 'button'
	b.setAttribute('aria-label', label)
	b.title = label
	b.innerHTML = inner
	b.style.cssText =
		'display:inline-flex;align-items:center;justify-content:center;min-width:36px;height:36px;padding:0 8px;border:0;border-radius:8px;' +
		'background:transparent;color:#fff;cursor:pointer;font:600 14px/1 system-ui,sans-serif;'
	return b
}

export function openViewer(source: HTMLVideoElement): HTMLElement | null {
	if (document.querySelector('.neo-video-viewer')) return null
	const startAt = source.currentTime || 0
	source.pause()
	marks.forEach((mark) => (mark.style.display = 'none'))

	const overlay = document.createElement('div')
	overlay.className = 'neo-video-viewer'
	overlay.setAttribute('role', 'dialog')
	overlay.setAttribute('aria-modal', 'true')
	overlay.setAttribute('aria-label', translate('Enlarge the video'))
	overlay.style.cssText = 'position:fixed;inset:0;z-index:2147483000;display:flex;flex-direction:column;background:#000;'

	// the stage: the picture, whole, in all the room left above the control bar
	const stage = document.createElement('div')
	stage.style.cssText = 'position:relative;flex:1 1 auto;min-height:0;display:flex;align-items:center;justify-content:center;cursor:pointer;'
	const video = document.createElement('video')
	video.src = source.currentSrc || source.getAttribute('src') || source.querySelector('source')?.getAttribute('src') || ''
	video.playsInline = true
	video.preload = 'auto'
	// Never "cover": the picture is scaled to fit inside the box, whatever the shape of the screen.
	video.style.cssText = 'width:100%;height:100%;object-fit:contain;background:#000;outline:none;'
	stage.appendChild(video)

	// the control bar: BELOW the picture, never over it
	const bar = document.createElement('div')
	bar.style.cssText = `flex:0 0 ${BAR_HEIGHT}px;display:flex;align-items:center;gap:10px;padding:0 14px;background:#111;color:#fff;`
	const toggle = button(translate('Play'), svg(ICON.play))
	const time = document.createElement('span')
	time.style.cssText = 'min-width:96px;font:500 14px/1 system-ui,sans-serif;font-variant-numeric:tabular-nums;'
	time.textContent = '0:00 / 0:00'
	const seek = document.createElement('input')
	seek.type = 'range'
	seek.min = '0'
	seek.max = '1000'
	seek.value = '0'
	seek.setAttribute('aria-label', translate('Seek'))
	seek.style.cssText = 'flex:1 1 auto;min-width:80px;accent-color:#fff;cursor:pointer;'
	const speed = button(translate('Speed'), '1x')
	const mute = button(translate('Mute'), svg(ICON.volume))
	const volume = document.createElement('input')
	volume.type = 'range'
	volume.min = '0'
	volume.max = '1'
	volume.step = '0.05'
	volume.value = '1'
	volume.setAttribute('aria-label', translate('Volume'))
	volume.style.cssText = 'width:80px;accent-color:#fff;cursor:pointer;'
	const close = button(translate('Close the enlarged view'), '×')
	close.style.fontSize = '26px'
	bar.append(toggle, time, seek, speed, mute, volume, close)

	const refresh = () => {
		time.textContent = `${formatTime(video.currentTime)} / ${formatTime(video.duration)}`
		if (Number.isFinite(video.duration) && video.duration > 0) seek.value = String(Math.round((video.currentTime / video.duration) * 1000))
		toggle.innerHTML = svg(video.paused ? ICON.play : ICON.pause)
		toggle.setAttribute('aria-label', translate(video.paused ? 'Play' : 'Pause'))
		mute.innerHTML = svg(video.muted || video.volume === 0 ? ICON.muted : ICON.volume)
	}
	const playPause = () => {
		if (video.paused) void video.play().catch(() => {})
		else video.pause()
	}
	toggle.addEventListener('click', playPause)
	stage.addEventListener('click', playPause)
	seek.addEventListener('input', () => {
		if (Number.isFinite(video.duration)) video.currentTime = (Number(seek.value) / 1000) * video.duration
	})
	speed.addEventListener('click', () => {
		const next = SPEEDS[(SPEEDS.indexOf(video.playbackRate) + 1) % SPEEDS.length]
		video.playbackRate = next
		speed.textContent = `${next}x`
	})
	mute.addEventListener('click', () => {
		video.muted = !video.muted
		refresh()
	})
	volume.addEventListener('input', () => {
		video.volume = Number(volume.value)
		video.muted = video.volume === 0
		refresh()
	})
	;['timeupdate', 'play', 'pause', 'loadedmetadata', 'volumechange', 'durationchange'].forEach((name) => video.addEventListener(name, refresh))
	video.addEventListener('loadedmetadata', () => {
		video.currentTime = startAt
		void video.play().catch(() => {})
	}, { once: true })

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

	const finish = () => {
		const at = video.currentTime
		video.pause()
		document.removeEventListener('keydown', onKey, true)
		if (document.fullscreenElement === overlay) void document.exitFullscreen().catch(() => {})
		overlay.remove()
		if (at) source.currentTime = at
		schedulePlacement()
	}
	const onKey = (event: KeyboardEvent) => {
		const target = event.target as HTMLElement | null
		if (event.key === 'Escape') {
			event.stopPropagation()
			finish()
		} else if (event.key === ' ' && target?.tagName !== 'BUTTON') {
			event.preventDefault()
			playPause()
		} else if (event.key === 'ArrowRight' && target?.tagName !== 'INPUT') {
			video.currentTime = Math.min(video.duration || Infinity, video.currentTime + 5)
		} else if (event.key === 'ArrowLeft' && target?.tagName !== 'INPUT') {
			video.currentTime = Math.max(0, video.currentTime - 5)
		} else if ((event.key === 'm' || event.key === 'M') && target?.tagName !== 'INPUT') {
			video.muted = !video.muted
			refresh()
		}
	}
	close.addEventListener('click', finish)
	overlay.addEventListener('click', (event) => {
		if (event.target === overlay) finish()
	})
	document.addEventListener('keydown', onKey, true)

	overlay.append(stage, bar)
	document.body.appendChild(overlay)
	// The browser's full screen is asked for the dialog, not the film: the film stays inside its box and keeps its shape.
	if (typeof overlay.requestFullscreen === 'function') void overlay.requestFullscreen().catch(() => {})
	close.focus({ preventScroll: true })
	refresh()
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
	// A click on the picture of a film of the page opens the dialog, which starts the film. The listener is in the capture phase so that the
	// browser's own click-to-play, which lives on the film, never sees the click.
	document.addEventListener(
		'click',
		(event) => {
			const target = event.target as Element | null
			const video = target?.closest?.(`video[${VIEWER_ATTRIBUTE}]`) as HTMLVideoElement | null
			if (!video) return
			event.preventDefault()
			event.stopPropagation()
			openViewer(video)
		},
		true
	)
	enhanceVideos(document)
}
