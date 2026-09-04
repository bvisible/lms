<!-- //// Neoffice — added file (no upstream equivalent), 36c69d63 « cours vidéo privés
//// adossés à l'abonnement (Infomaniak VOD) », then a789500f (resume where the learner
//// stopped).
//// The player for a `key_restricted` Infomaniak video: it asks the server for a
//// short-lived HMAC link (lms.lms.neoffice_video), plays it in the vendor iframe and
//// reports position over postMessage. Upstream's players (<video>, Plyr, YouTube) all
//// assume a URL anyone can fetch, which is precisely what a paid course must not have.
//// At the merge: kept whole. -->
<template>
	<div class="secure-video">
		<div
			v-if="error"
			class="flex items-center justify-center rounded-md border border-red-200 bg-red-50 p-6 text-center text-sm text-red-700"
			:style="{ minHeight: height + 'px' }"
		>
			{{ error }}
		</div>
		<div
			v-else-if="!src"
			class="flex items-center justify-center rounded-md bg-surface-gray-2 text-sm text-ink-gray-5"
			:style="{ minHeight: height + 'px' }"
		>
			{{ __('Loading video…') }}
		</div>
		<iframe
			v-else
			ref="frame"
			:src="src"
			class="w-full rounded-md bg-black"
			:height="height"
			frameborder="0"
			allowfullscreen
			allow="autoplay; fullscreen; picture-in-picture"
		></iframe>
	</div>
</template>

<script setup>
import { call } from 'frappe-ui'
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useScreenSize } from '@/utils/composables'
import {
	PLAYER_ORIGIN,
	isRealProgress,
	registerSecureVideo,
	unregisterSecureVideo,
} from '@/utils/secureVideo'

const props = defineProps({
	media: { type: String, required: true },
	lesson: { type: String, required: true },
	// Seconds already watched, from LMS Video Watch Duration.
	startAt: { type: Number, required: false, default: 0 },
})

// Below this, resuming is more disorienting than helpful.
const RESUME_THRESHOLD = 5

const emit = defineEmits(['ended'])

const screenSize = useScreenSize()
const height = screenSize.width < 640 ? 220 : 420

const src = ref(null)
const error = ref(null)
const frame = ref(null)

// Registry entry, kept in the shape the lesson page collects watch time from.
const entry = {
	source: `infomaniak:${props.media}`,
	currentTime: 0,
	duration: 0,
}

const onMessage = (event) => {
	if (event.origin !== PLAYER_ORIGIN) return
	// Several lessons can embed several videos; only trust our own frame.
	if (!frame.value || event.source !== frame.value.contentWindow) return

	const data = event.data
	if (!data || typeof data !== 'object') return

	if (data.type === 'timeupdate') {
		if (data.videoDuration) entry.duration = Number(data.videoDuration)
		// Ignore the currentTime 0 the player emits when the stream is refused.
		if (isRealProgress(entry.currentTime, data.currentTime)) {
			entry.currentTime = Number(data.currentTime)
		}
	} else if (data.type === 'ended') {
		// Record 0, not the duration: completion is tracked by markProgress, and
		// storing the end position would make the next visit resume at the very
		// end. Same rule the plain <video> path applies.
		entry.currentTime = 0
		emit('ended')
	}
}

const load = async () => {
	try {
		const result = await call('lms.lms.neoffice_video.get_playback_url', {
			lesson: props.lesson,
			media: props.media,
		})
		// `t` is the only offset the Infomaniak player honours — its postMessage
		// bridge is outbound-only, so there is no way to seek after load.
		const resume = Math.floor(props.startAt || 0)
		src.value =
			resume > RESUME_THRESHOLD ? `${result.url}&t=${resume}` : result.url
	} catch (e) {
		// The server already phrases why (expired subscription, not enrolled…).
		error.value =
			e?.messages?.[0] || e?.message || __('This video is not available.')
	}
}

onMounted(() => {
	registerSecureVideo(entry)
	window.addEventListener('message', onMessage)
	load()
})

onBeforeUnmount(() => {
	window.removeEventListener('message', onMessage)
	unregisterSecureVideo(entry)
})
</script>
