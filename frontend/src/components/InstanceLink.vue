<!-- //// Neoffice — added file (no upstream equivalent).
//// `{{ InstanceLink("/app/item/new", "Open the creation of an item in your Neoffice") }}`: a link that opens, in a NEW tab, the
//// Neoffice of the person who follows the course, on the screen the lesson explains. The base address is asked once to the
//// server (lms.lms.neoffice_instance.get_instance_base): empty when the course lives on the instance itself, the registered instance
//// of the learner on our hub, nothing when the learner is not linked: the lesson then shows its label as a sentence, with no
//// link, and says what to do. Rules of the address: src/utils/instanceLink.ts. At the merge: kept whole. -->
<template>
	<p class="neo-instance-link my-4">
		<a
			v-if="url"
			:href="url"
			target="_blank"
			rel="noopener noreferrer"
			class="inline-flex items-center gap-2 rounded-md border border-outline-gray-3 px-3 py-1.5 text-sm font-medium text-ink-gray-8 hover:bg-surface-gray-2"
		>
			<span>{{ label }}</span>
			<span aria-hidden="true">↗</span>
		</a>
		<span v-else class="text-sm text-ink-gray-7">
			{{ label }}. {{ __('Open your Neoffice to try it yourself.') }}
		</span>
	</p>
</template>

<script setup>
import { call } from 'frappe-ui'
import { computed, ref } from 'vue'
import { buildInstanceUrl } from '@/utils/instanceLink'

const props = defineProps({
	path: { type: String, required: true },
	label: { type: String, required: true },
})

// One request per page: every InstanceLink of a lesson shares the answer.
let baseRequest = null
const askBase = () => {
	if (!baseRequest)
		baseRequest = call('lms.lms.neoffice_instance.get_instance_base').catch(() => ({
			mode: 'none',
			base: '',
		}))
	return baseRequest
}

const base = ref(null)
askBase().then((answer) => {
	base.value = answer
})

// null until the server has answered, then null again when the learner is not linked or the address is refused.
const url = computed(() => {
	if (!base.value || base.value.mode === 'none') return null
	return buildInstanceUrl(base.value.base || '', props.path)
})
</script>
