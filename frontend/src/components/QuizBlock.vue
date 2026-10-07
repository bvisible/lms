<template>
	<!-- //// Neoffice — the quiz no longer opens inline at the end of the lesson. A learner had to scroll a long lesson to
	     reach it, and the quiz shared the page with the text it asks about. A card holds its place in the lesson; the quiz
	     itself runs in a window (full screen on a phone). Closing the window never submits: only the page being left does,
	     and only when an answer was given (see Quiz.vue). -->
	<template v-if="user.data">
		<div
			class="my-4 flex items-center justify-between gap-3 rounded-lg border bg-surface-elevation-1 p-4"
		>
			<div class="flex min-w-0 items-center gap-3">
				<span class="lucide-help-circle size-5 shrink-0 text-ink-gray-6" />
				<div class="min-w-0">
					<div class="text-sm text-ink-gray-5">{{ __('Quiz') }}</div>
					<div class="truncate font-medium text-ink-gray-9">
						{{ quizTitle }}
					</div>
				</div>
			</div>
			<Button variant="solid" class="shrink-0" @click="openQuiz">
				{{ __('Take the quiz') }}
			</Button>
		</div>
		<Teleport to="body">
			<div
				v-if="isOpen"
				ref="overlay"
				tabindex="-1"
				role="dialog"
				aria-modal="true"
				:aria-label="quizTitle"
				class="fixed inset-0 z-[60] flex outline-none sm:items-center sm:justify-center"
				@keydown.esc.stop.prevent="requestClose"
			>
				<div
					class="absolute inset-0 hidden bg-black/40 sm:block"
					@click="requestClose"
				/>
				<div
					class="relative flex h-full w-full flex-col bg-surface-elevation-1 sm:h-auto sm:max-h-[90vh] sm:max-w-3xl sm:rounded-xl sm:shadow-2xl"
				>
					<div class="flex items-center justify-between gap-3 border-b px-4 py-3">
						<div class="min-w-0 truncate font-medium text-ink-gray-9">
							{{ quizTitle }}
						</div>
						<Button
							variant="ghost"
							:aria-label="__('Close quiz')"
							@click="requestClose"
						>
							<template #icon>
								<span class="lucide-x size-5" />
							</template>
						</Button>
					</div>
					<div class="flex-1 overflow-y-auto px-4 py-4 sm:px-6">
						<Quiz ref="quizRef" :quizName="quiz" :inWindow="true" />
					</div>
					<div
						v-if="confirmLeave"
						class="absolute inset-0 z-10 flex items-center justify-center bg-surface-elevation-1 p-6 sm:rounded-xl"
					>
						<div class="max-w-sm space-y-4 text-center">
							<div class="text-lg font-semibold text-ink-gray-9">
								{{ __('Leave the quiz?') }}
							</div>
							<p class="text-p-base text-ink-gray-7">
								{{
									__(
										'Your answers will not be saved. You can start the quiz again later.'
									)
								}}
							</p>
							<div class="flex flex-wrap justify-center gap-2">
								<Button variant="solid" @click="confirmLeave = false">
									{{ __('Continue the quiz') }}
								</Button>
								<Button @click="closeQuiz">
									{{ __('Leave quiz') }}
								</Button>
							</div>
						</div>
					</div>
				</div>
			</div>
		</Teleport>
	</template>
	<div v-else class="border rounded-md text-center py-20">
		<div>
			{{ __('Please login to access the quiz.') }}
		</div>
		<Button @click="redirectToLogin()" class="mt-2">
			<span>
				{{ __('Login') }}
			</span>
		</Button>
	</div>
</template>
<script setup>
//// Neoffice — added imports for the quiz window (nextTick, onBeforeUnmount, onMounted) and its confirm-leave check (71dc7a163).
import { computed, inject, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { Button, createResource } from 'frappe-ui'
import Quiz from '@/components/Quiz.vue'
//// Neoffice — added: see lessonQuizzes.js.
import {
	needsLeaveConfirmation,
	registerLessonQuiz,
} from '@/utils/lessonQuizzes'

const user = inject('$user')
const props = defineProps({
	quiz: {
		type: String,
		required: true,
	},
})

//// Neoffice ▼▼▼ — the quiz runs in a window instead of inline in the lesson (71dc7a163): isOpen/confirmLeave/overlay/quizRef
//// hold the window and its close-confirmation state, openQuiz/closeQuiz/requestClose drive it (closing never submits, only
//// leaving the page does — see Quiz.vue), and registerLessonQuiz lets LessonQuizBar open this same quiz from the bar at
//// the top of the lesson.
const isOpen = ref(false)
const confirmLeave = ref(false)
const overlay = ref(null)
const quizRef = ref(null)

const titleResource = createResource({
	url: 'frappe.client.get_value',
	params: {
		doctype: 'LMS Quiz',
		filters: { name: props.quiz },
		fieldname: 'title',
	},
	cache: ['quiz_title', props.quiz],
	auto: Boolean(user.data),
})
const quizTitle = computed(() => titleResource.data?.title || __('Quiz'))

const lockPageScroll = (locked) => {
	document.body.style.overflow = locked ? 'hidden' : ''
}

const openQuiz = async () => {
	isOpen.value = true
	lockPageScroll(true)
	await nextTick()
	overlay.value?.focus()
}

const closeQuiz = () => {
	isOpen.value = false
	confirmLeave.value = false
	lockPageScroll(false)
}

const requestClose = () => {
	if (
		needsLeaveConfirmation({
			inProgress: quizRef.value?.inProgress,
			hasAnswers: quizRef.value?.hasAnswers,
		})
	) {
		confirmLeave.value = true
		return
	}
	closeQuiz()
}

let unregister = () => {}
onMounted(() => {
	if (user.data) unregister = registerLessonQuiz({ name: props.quiz, open: openQuiz })
})
onBeforeUnmount(() => {
	unregister()
	if (isOpen.value) lockPageScroll(false)
})
//// Neoffice ▲▲▲

const redirectToLogin = () => {
	window.location.href = `/login`
}
</script>
