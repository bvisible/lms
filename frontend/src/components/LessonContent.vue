<template>
	<div v-if="youtubeEmbedId(youtube)" :key="youtubeEmbedId(youtube)">
		<div
			class="video-player"
			data-plyr-provider="youtube"
			:data-plyr-embed-id="youtubeEmbedId(youtube)"
		></div>
	</div>
	<!-- Keyed on the block text, not just the index: position N of the outgoing
	     lesson and position N of the incoming one share an index, so Vue reuses
	     the instance and hands a <PdfBlock> a new `file`, which it only reads
	     once, at setup. Including the text forces a fresh instance. -->
	<div
		v-for="(block, index) in content?.split('\n\n')"
		:key="`${index}:${block}`"
	>
		<div v-if="block.includes('{{ YouTubeVideo')">
			<div
				v-if="youtubeEmbedId(getId(block))"
				:key="youtubeEmbedId(getId(block))"
				class="video-player"
				data-plyr-provider="youtube"
				:data-plyr-embed-id="youtubeEmbedId(getId(block))"
			></div>
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
		<!-- //// Neoffice — the `{{ InstanceLink("/app/…", "label") }}` branch: a link to the learner's own Neoffice, in a new tab (see InstanceLink.vue
		     and utils/instanceLink.ts). A malformed macro shows nothing rather than its source. -->
		<div v-else-if="block.includes('{{ InstanceLink')">
			<InstanceLink v-if="parseInstanceLink(block)" v-bind="parseInstanceLink(block)" />
		</div>
		<div v-else-if="block.includes('{{ Video')">
			<!-- //// Neoffice — the film has the width of the text above it (the lesson column is centred and capped, see `.neo-lesson-column` in Lesson.vue),
			     with 24px above and below (as the images of the lesson and the clips of the manual) and rounded corners (Daniel, 10 October 2026: « aligner les deux, film et texte »). The pop-up
			     (lessonVideoViewer.ts) is what enlarges it. -->
			<video
				controls
				width="100%"
				controlsList="nodownload"
				oncontextmenu="return false;"
				style="display: block; width: 100%; margin: 24px 0; border-radius: 10px"
			>
				<source :src="safeUrl(getId(block))" type="video/mp4" />
			</video>
		</div>
		<div v-else-if="block.includes('{{ PDF')">
			<PdfBlock v-if="inlinePdf" :file="getId(block)" />
			<iframe
				v-else
				:src="safeUrl(getId(block))"
				:title="__('PDF document')"
				width="100%"
				height="700px"
				class="mb-4"
				type="application/pdf"
			></iframe>
		</div>
		<div v-else-if="block.includes('{{ Audio')">
			<audio width="100%" controls controlsList="nodownload">
				<source :src="safeUrl(getId(block))" type="audio/mp3" />
			</audio>
		</div>
		<div v-else-if="block.includes('{{ Embed')">
			<iframe
				width="100%"
				height="400"
				:src="safeUrl(getId(block))"
				:title="__('Embedded content')"
				frameborder="0"
				allowfullscreen
			>
			</iframe>
		</div>
		<!-- //// Neoffice — the rendered Markdown gets `neo-lesson-md`: upstream's `.lesson-content` rules are applied nowhere, so a
		     capture showed at its natural width, up to the whole column, however small the part of the screen it shows. -->
		<div v-else class="neo-lesson-md" v-safe-html:rich="renderMarkdown(block)"></div>
	</div>
	<div v-if="quizId">
		<Quiz :quiz="quizId" />
	</div>
</template>
<script setup>
import Quiz from '@/components/QuizBlock.vue'
//// Neoffice — 36c69d63: the player for subscription-gated Infomaniak videos.
import SecureVideo from '@/components/SecureVideo.vue'
//// Neoffice — the link of a lesson to the learner's own Neoffice.
import InstanceLink from '@/components/InstanceLink.vue'
import { parseInstanceLink } from '@/utils/instanceLink'
import PdfBlock from '@/components/PdfBlock.vue'
import MarkdownIt from 'markdown-it'
import { extractYoutubeID, getMacroArg } from '@/utils/lessonMacros'
import { usesWebkitPdfViewer } from '@/utils/pdfViewer'
import { safeUrl } from '@/utils/safeUrl'

//// Neoffice — a789500f: upstream declares no emit here. The Infomaniak iframe is the
//// only player whose end-of-video the parent cannot observe from the DOM, so it has to
//// be forwarded; Lesson.vue turns it into markProgress() + trackVideoWatchDuration().
const emit = defineEmits(['video-ended'])

const inlinePdf = usesWebkitPdfViewer()

const markdown = new MarkdownIt({
	html: true,
	linkify: true,
})

// The directive sanitizes at the rich level, which is where the anchor-target
// hook and the form-tag blocklist live. This only does the markdown pass.
const renderMarkdown = (block) => markdown.render(block)

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

const getId = (block) => {
	// Guard the match: a malformed `{{ PDF() }}` / unbalanced-quote macro yields
	// null, and the old unguarded [1] threw and killed the whole lesson render.
	return getMacroArg(block) ?? ''
}

// Both authoring paths (the `youtube` field and the `{{ YouTubeVideo }}` macro)
// must land in the same Plyr-wrapped `.video-player` the EditorJS embed block
// renders. A bare <iframe> is invisible to the watch tracker in Lesson.vue, so
// enforce_video_completion saw "no video" and auto-completed on the dwell timer.
// Falsy id => render nothing rather than a Plyr player with no video, which
// would suppress the dwell timer and leave the lesson uncompletable.
const youtubeEmbedId = (source) => (source ? extractYoutubeID(source) : '')
</script>
