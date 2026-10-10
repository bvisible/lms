<template>
	<!-- //// Neoffice — a hosted film (a file) shows the course image as its poster until it is played: its first image is often the blank paper of
	     the series' opening, and the card then looks empty. Upstream only uses the image when the film cannot be played. At the merge: keep ours. -->
	<iframe
		v-if="videoPreview.type === 'youtube'"
		:src="videoPreview.src"
		:title="__('Video preview')"
		class="min-h-56 w-full rounded-t-md"
		allowfullscreen
	/>
	<video
		v-else-if="videoPreview.type === 'file' && !videoError"
		:src="videoPreview.src"
		controls
		:poster="fallbackImage || undefined"
		class="min-h-56 w-full rounded-t-md bg-black object-contain"
		@error="videoError = true"
	/>
	<img
		v-else-if="videoPreview.type === 'file' && videoError && fallbackImage"
		:src="fallbackImage"
		:alt="__('Video preview')"
		class="min-h-56 w-full rounded-t-md object-cover"
	/>
</template>
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { getVideoPreview } from '@/utils/video'

// Shared display for a course/batch preview video. A video_link can be a
// YouTube link (render an embed iframe — NOT a <video>, which is what made batch
// cards fail), an uploaded file path (<video>), or unplayable (fall back to the
// poster image). Used by CourseCardOverlay and BatchOverlay.
const props = defineProps<{
	videoLink?: string | null
	fallbackImage?: string | null
}>()

const videoPreview = computed(() => getVideoPreview(props.videoLink))

// Reset the in-browser playback error whenever the source changes.
const videoError = ref(false)
watch(
	() => props.videoLink,
	() => {
		videoError.value = false
	}
)
</script>
