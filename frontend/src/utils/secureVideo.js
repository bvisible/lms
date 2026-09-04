//// Neoffice — added file (no upstream equivalent), 36c69d63 / a789500f.
//// The registry of Infomaniak players mounted on the page. Upstream collects watch time
//// by walking the DOM (<video>) and the Plyr instances; a vendor iframe is neither, so
//// it has to announce itself here or the lesson would look like a lesson without video.
//// At the merge: kept whole.
/**
 * Registry of subscription-gated Infomaniak videos mounted on the page.
 *
 * The lesson page already collects watch time from two kinds of source:
 * raw <video> elements and Plyr instances. Infomaniak's player is a
 * cross-origin iframe, so it is neither — it reports its position over
 * postMessage instead. This registry exposes those iframes in the same
 * `{ source, watch_time, currentTime, duration }` shape the lesson page
 * already understands, so wiring it in stays a one-liner.
 */
import { ref } from 'vue'

export const PLAYER_ORIGIN = 'https://player.vod2.infomaniak.com'

export const secureVideoSources = ref([])

export const registerSecureVideo = (entry) => {
	secureVideoSources.value.push(entry)
	return entry
}

export const unregisterSecureVideo = (entry) => {
	const i = secureVideoSources.value.indexOf(entry)
	if (i !== -1) secureVideoSources.value.splice(i, 1)
}

export const clearSecureVideos = () => {
	secureVideoSources.value = []
}

/** Same shape as getVideoDetails() / getPlyrSourceDetails() on the lesson page. */
export const getSecureVideoDetails = () =>
	secureVideoSources.value.map((entry) => ({
		source: entry.source,
		watch_time: entry.currentTime,
	}))

/**
 * Decide whether a postMessage payload represents real viewing.
 *
 * The player emits `play` and a `timeupdate` at currentTime 0 even when the
 * stream is refused (no token → HLS returns 403 → the player pauses again).
 * Counting `play`, or any timeupdate, would record progress on a denied
 * access. Only a position that actually moved forward proves playback.
 */
export const isRealProgress = (previous, next) => {
	const before = Number(previous) || 0
	const after = Number(next) || 0
	return after > before + 0.05
}
