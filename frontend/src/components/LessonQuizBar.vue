<template>
	<!-- //// Neoffice — added file (no upstream equivalent). A bar at the top of the lesson, so that a learner does not have
	     to scroll to the end of a long lesson to reach its quiz. It opens the quiz window registered by QuizBlock.vue. -->
	<div
		v-if="first"
		class="mt-4 flex flex-wrap items-center justify-between gap-2 rounded-lg bg-surface-blue-2 px-3 py-2 text-ink-blue-6"
	>
		<span class="text-sm">{{ __('This lesson ends with a quiz.') }}</span>
		<Button size="sm" variant="subtle" @click="first.open()">
			{{ __('Take the quiz') }}
		</Button>
	</div>
</template>
<script setup>
import { computed } from 'vue'
import { Button } from 'frappe-ui'
import { lessonQuizzes } from '@/utils/lessonQuizzes'

const first = computed(() => lessonQuizzes.entries[0])
</script>
