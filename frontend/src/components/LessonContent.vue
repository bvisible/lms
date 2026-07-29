<template>
	<div v-if="youtube">
		<iframe
			class="youtube-video"
			:src="getYouTubeVideoSource(youtube.split('/').pop())"
			:title="__('YouTube video')"
			width="100%"
			:height="screenSize.width < 640 ? 200 : 400"
			frameborder="0"
			allowfullscreen
		></iframe>
	</div>
	<div v-for="(block, index) in content?.split('\n\n')" :key="index">
		<div v-if="block.includes('{{ YouTubeVideo')">
			<iframe
				class="youtube-video"
				:src="getYouTubeVideoSource(block)"
				:title="__('YouTube video')"
				width="100%"
				:height="screenSize.width < 640 ? 200 : 400"
				frameborder="0"
				allowfullscreen
			></iframe>
		</div>
		<div v-else-if="block.includes('{{ Quiz')">
			<Quiz :quiz="getId(block)" />
		</div>
		<div v-else-if="block.includes('{{ SecureVideo')">
			<SecureVideo
				:media="getId(block)"
				:lesson="lessonName"
				:startAt="watchedSeconds(getId(block))"
				@ended="emit('video-ended')"
			/>
		</div>
		<div v-else-if="block.includes('{{ Video')">
			<video
				controls
				width="100%"
				controlsList="nodownload"
				oncontextmenu="return false;"
			>
				<source :src="getId(block)" type="video/mp4" />
			</video>
		</div>
		<div v-else-if="block.includes('{{ PDF')">
			<PdfBlock :file="getId(block)" />
		</div>
		<div v-else-if="block.includes('{{ Audio')">
			<audio width="100%" controls controlsList="nodownload">
				<source :src="getId(block)" type="audio/mp3" />
			</audio>
		</div>
		<div v-else-if="block.includes('{{ Embed')">
			<iframe
				width="100%"
				height="400"
				:src="getId(block)"
				:title="__('Embedded content')"
				frameborder="0"
				allowfullscreen
			>
			</iframe>
		</div>
		<div v-else v-html="renderSafe(block)"></div>
	</div>
	<div v-if="quizId">
		<Quiz :quiz="quizId" />
	</div>
</template>
<script setup>
import Quiz from '@/components/QuizBlock.vue'
import SecureVideo from '@/components/SecureVideo.vue'
import PdfBlock from '@/components/PdfBlock.vue'
import MarkdownIt from 'markdown-it'
import { useScreenSize } from '@/utils/composables'
import { getMacroArg } from '@/utils/lessonMacros'
import { sanitizeRichHTML } from '@/utils/sanitizeRichHTML'

const emit = defineEmits(['video-ended'])

const screenSize = useScreenSize()

const markdown = new MarkdownIt({
	html: true,
	linkify: true,
})

// Route markdown output through the shared sanitizer so the anchor-target
// hook (open in new tab) and form-tag blocklist are applied uniformly with
// the rest of the LMS render pipelines. Keeps one source of truth for what
// counts as safe user-authored HTML.
const renderSafe = (block) => sanitizeRichHTML(markdown.render(block))

const props = defineProps({
	content: {
		type: String,
		required: true,
	},
	youtube: {
		type: String,
		required: false,
	},
	quizId: {
		type: String,
		required: false,
	},
	lessonName: {
		type: String,
		required: false,
	},
	// [{ source, watch_time }] from LMS Video Watch Duration, for this member.
	videos: {
		type: Array,
		required: false,
		default: () => [],
	},
})

// The registry stores secure videos under `infomaniak:<media>`.
const watchedSeconds = (media) => {
	const row = props.videos?.find((v) => v.source === `infomaniak:${media}`)
	return row ? Number(row.watch_time) || 0 : 0
}

const getYouTubeVideoSource = (block) => {
	if (block.includes('{{')) {
		block = getId(block)
	}
	// nocookie: no Google cookie before the visitor presses play.
	return `https://www.youtube-nocookie.com/embed/${block}`
}

const getId = (block) => {
	// Guard the match: a malformed `{{ PDF() }}` / unbalanced-quote macro yields
	// null, and the old unguarded [1] threw and killed the whole lesson render.
	return getMacroArg(block) ?? ''
}
</script>
