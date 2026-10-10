//// Neoffice — added file (no upstream equivalent)
// Enlarged view of the films hosted on the hub (a `<video controls>` in a lesson, in the course card, in the lesson editor preview).
//
// Why. (1) The browser's own full screen gives the film a box the size of the screen: on a very wide screen the 16:9 picture can end up
// scaled to the width of the box and its top and bottom are cut (seen on an ultra-wide screen, 10 October 2026). (2) The browser's control
// bar is drawn OVER the bottom of the picture, with a dark gradient: the bottom of a screen recording is lost under it. (3) A click on the
// picture plays or pauses it, which is of little use on a small player.
//
// What. A film of the page keeps no control bar: it shows its picture, a play mark and a pointer cursor, and a click on it opens a pop-up: a
// centred box (16:9, 1000 px at most, 92 % of the width, never taller than the window) over a dimmed page, with a title and a cross above the
// picture. In the box the whole picture is shown (`object-fit: contain`, black bars on the sides if the film is wider) and the controls are in
// a bar BELOW the picture, never over it. No browser full screen at all (Daniel, 10 October 2026: « un pop-up plutôt que le plein écran »; it is
// the shape of the pop-up of the manual's help panel, which he liked): there is no full screen left to cut the top and the bottom.
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
const HEAD_HEIGHT = 40

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
		// A film `foo.mp4` has its poster `foo.jpg` next to it: shown until the film is played (its first image is often the blank paper of the
		// opening of the series). A missing poster is simply not shown, so a new film only needs its image dropped next to it under the same name.
		if (!video.getAttribute('poster')) {
			const src = video.getAttribute('src') || video.querySelector('source')?.getAttribute('src') || ''
			if (/\.(mp4|webm|mov)$/i.test(src)) video.setAttribute('poster', src.replace(/\.(mp4|webm|mov)$/i, '.jpg'))
		}
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

// A slider drawn by hand (a track, a fill, a round handle): the browser's own range input is nearly invisible on a dark bar in some browsers.
type Slider = { el: HTMLElement; set: (value: number) => void; value: () => number; onInput: (callback: (value: number) => void) => void }

function slider(label: string, size: { grow?: boolean; width?: number }): Slider {
	const root = document.createElement('div')
	root.setAttribute('role', 'slider')
	root.setAttribute('aria-label', label)
	root.setAttribute('aria-valuemin', '0')
	root.setAttribute('aria-valuemax', '100')
	root.setAttribute('aria-valuenow', '0')
	root.tabIndex = 0
	root.style.cssText = `display:flex;align-items:center;height:28px;cursor:pointer;touch-action:none;` +
		(size.grow ? 'flex:1 1 auto;min-width:80px;' : `flex:0 0 ${size.width}px;width:${size.width}px;`)
	const track = document.createElement('div')
	track.style.cssText = 'position:relative;width:100%;height:6px;border-radius:3px;background:rgba(255,255,255,.28);'
	const fill = document.createElement('div')
	fill.style.cssText = 'position:absolute;top:0;bottom:0;left:0;width:0;border-radius:3px;background:#fff;'
	const handle = document.createElement('div')
	handle.style.cssText = 'position:absolute;top:50%;left:0;width:14px;height:14px;margin:-7px 0 0 -7px;border-radius:50%;background:#fff;'
	track.append(fill, handle)
	root.appendChild(track)
	let current = 0
	let listener: (value: number) => void = () => {}
	const clamp = (v: number) => Math.min(1, Math.max(0, v))
	const set = (value: number) => {
		current = clamp(Number.isFinite(value) ? value : 0)
		fill.style.width = `${current * 100}%`
		handle.style.left = `${current * 100}%`
		root.setAttribute('aria-valuenow', String(Math.round(current * 100)))
	}
	const at = (event: PointerEvent) => {
		const rect = track.getBoundingClientRect()
		return rect.width ? clamp((event.clientX - rect.left) / rect.width) : 0
	}
	let dragging = false
	root.addEventListener('pointerdown', (event) => {
		dragging = true
		root.setPointerCapture?.(event.pointerId)
		set(at(event))
		listener(current)
	})
	root.addEventListener('pointermove', (event) => {
		if (!dragging) return
		set(at(event))
		listener(current)
	})
	const stop = () => (dragging = false)
	root.addEventListener('pointerup', stop)
	root.addEventListener('pointercancel', stop)
	root.addEventListener('keydown', (event) => {
		if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return
		event.preventDefault()
		event.stopPropagation()
		set(current + (event.key === 'ArrowRight' ? 0.05 : -0.05))
		listener(current)
	})
	return { el: root, set, value: () => current, onInput: (callback) => (listener = callback) }
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
	// the dimmed page around the pop-up; a click on it closes the pop-up
	overlay.style.cssText = 'position:fixed;inset:0;z-index:2147483000;display:flex;align-items:center;justify-content:center;background:rgba(20,20,20,.62);'
	const opener = document.activeElement as HTMLElement | null

	// the pop-up: 16:9 picture, 1000 px at most, 92 % of the width, and never taller than the window (head and bar included)
	const box = document.createElement('div')
	box.className = 'neo-video-box'
	box.style.cssText =
		`display:flex;flex-direction:column;width:min(1000px,92vw,calc((92vh - ${HEAD_HEIGHT + BAR_HEIGHT}px) * 16 / 9));` +
		'background:#141414;border-radius:14px;overflow:hidden;box-shadow:0 20px 60px rgba(0,0,0,.4);'

	// the head: what is being watched, and the cross
	const head = document.createElement('div')
	head.style.cssText = `flex:0 0 ${HEAD_HEIGHT}px;display:flex;align-items:center;justify-content:space-between;gap:12px;padding:0 6px 0 16px;color:#f6f1e9;font:500 13px/1 system-ui,sans-serif;`
	const title = document.createElement('span')
	title.style.cssText = 'min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;'
	title.textContent = source.getAttribute('aria-label') || source.getAttribute('title') || document.title
	const close = button(translate('Close the enlarged view'), '×')
	close.style.fontSize = '26px'
	head.append(title, close)

	// the stage: the picture, whole, in a 16:9 frame. The film is laid out absolutely with no margin of its own: a content stylesheet that
	// puts a top margin on media would otherwise push it down and cut its bottom.
	const stage = document.createElement('div')
	stage.style.cssText = 'position:relative;width:100%;aspect-ratio:16/9;background:#000;cursor:pointer;'
	const video = document.createElement('video')
	video.src = source.currentSrc || source.getAttribute('src') || source.querySelector('source')?.getAttribute('src') || ''
	video.playsInline = true
	video.preload = 'auto'
	// Never "cover": the picture is scaled to fit inside the frame, whatever its shape.
	video.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;margin:0;display:block;object-fit:contain;background:#000;outline:none;'
	stage.appendChild(video)

	// the control bar: BELOW the picture, never over it
	const bar = document.createElement('div')
	bar.style.cssText = `flex:0 0 ${BAR_HEIGHT}px;display:flex;align-items:center;gap:10px;padding:0 14px;background:#111;color:#fff;`
	const toggle = button(translate('Play'), svg(ICON.play))
	const time = document.createElement('span')
	time.style.cssText = 'min-width:96px;font:500 14px/1 system-ui,sans-serif;font-variant-numeric:tabular-nums;'
	time.textContent = '0:00 / 0:00'
	const seek = slider(translate('Seek'), { grow: true })
	const speed = button(translate('Speed'), '1x')
	const mute = button(translate('Mute'), svg(ICON.volume))
	const volume = slider(translate('Volume'), { width: 80 })
	volume.set(1)
	bar.append(toggle, time, seek.el, speed, mute, volume.el)

	const refresh = () => {
		time.textContent = `${formatTime(video.currentTime)} / ${formatTime(video.duration)}`
		if (Number.isFinite(video.duration) && video.duration > 0) seek.set(video.currentTime / video.duration)
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
	seek.onInput((value) => {
		if (Number.isFinite(video.duration)) video.currentTime = value * video.duration
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
	volume.onInput((value) => {
		video.volume = value
		video.muted = value === 0
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
		overlay.remove()
		if (at) source.currentTime = at
		opener?.focus?.({ preventScroll: true })
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
		} else if (event.key === 'ArrowRight' && target?.getAttribute('role') !== 'slider') {
			video.currentTime = Math.min(video.duration || Infinity, video.currentTime + 5)
		} else if (event.key === 'ArrowLeft' && target?.getAttribute('role') !== 'slider') {
			video.currentTime = Math.max(0, video.currentTime - 5)
		} else if ((event.key === 'm' || event.key === 'M') && target?.getAttribute('role') !== 'slider') {
			video.muted = !video.muted
			refresh()
		}
	}
	close.addEventListener('click', finish)
	overlay.addEventListener('click', (event) => {
		if (event.target === overlay) finish()
	})
	document.addEventListener('keydown', onKey, true)

	box.append(head, stage, bar)
	overlay.appendChild(box)
	document.body.appendChild(overlay)
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
