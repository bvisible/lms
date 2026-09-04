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
		<!-- //// Neoffice — 36c69d63 / a789500f: the `{{ SecureVideo("…") }}` branch. Upstream
		//// only knows YouTube, a raw <video> and Plyr, all of them fed a URL anyone can
		//// fetch — unusable for a paid course. This branch hands the media id to
		//// SecureVideo.vue, which trades it for a short-lived signed Infomaniak link.
		//// It must stay ABOVE the `{{ Video` branch: `block.includes('{{ Video')` is a
		//// substring test and would swallow `{{ SecureVideo`. -->
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
//// Neoffice — 36c69d63: the player for subscription-gated Infomaniak videos.
import SecureVideo from '@/components/SecureVideo.vue'
import PdfBlock from '@/components/PdfBlock.vue'
import MarkdownIt from 'markdown-it'
import { useScreenSize } from '@/utils/composables'
import { getMacroArg } from '@/utils/lessonMacros'
import { sanitizeRichHTML } from '@/utils/sanitizeRichHTML'

//// Neoffice — a789500f: upstream declares no emit here. The Infomaniak iframe is the
//// only player whose end-of-video the parent cannot observe from the DOM, so it has to
//// be forwarded; Lesson.vue turns it into markProgress() + trackVideoWatchDuration().
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
	//// Neoffice — 36c69d63 / a789500f: two props upstream does not have. `lessonName`
	//// because the server refuses to sign a media the lesson does not cite, and `videos`
	//// (LMS Video Watch Duration rows) so playback resumes where the learner stopped.
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

//// Neoffice — a789500f: the resume position, read from the watch-duration rows.
// The registry stores secure videos under `infomaniak:<media>`.
const watchedSeconds = (media) => {
	const row = props.videos?.find((v) => v.source === `infomaniak:${media}`)
	return row ? Number(row.watch_time) || 0 : 0
}

const getYouTubeVideoSource = (block) => {
	if (block.includes('{{')) {
		block = getId(block)
	}
	//// Neoffice — 36c69d63: upstream embeds `youtube.com`; we embed `youtube-nocookie.com`
	//// so no Google cookie is dropped before the visitor presses play (same change in
	//// lms/plugins.py). At the merge: keep ours, upstream's host is the regression.
	// nocookie: no Google cookie before the visitor presses play.
	return `https://www.youtube-nocookie.com/embed/${block}`
}

const getId = (block) => {
	// Guard the match: a malformed `{{ PDF() }}` / unbalanced-quote macro yields
	// null, and the old unguarded [1] threw and killed the whole lesson render.
	return getMacroArg(block) ?? ''
}
</script>
