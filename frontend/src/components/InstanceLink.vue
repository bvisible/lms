<!-- //// Neoffice — added file (no upstream equivalent).
//// `{{ InstanceLink("/app/item/new", "Open the creation of an item in your Neoffice") }}`: a link that opens, in a NEW tab, the
//// Neoffice of the person who follows the course, on the screen the lesson explains. The base address is asked once to the
//// server (lms.lms.neoffice_instance.get_instance_base): empty when the course lives on the instance itself, the registered instance
//// of the learner on our hub, nothing when the learner is not linked: the lesson then shows its label as a sentence, with no
//// link, and says what to do. The staff of an accounting firm has one Neoffice per client: they choose a client (remembered in the
//// browser) and the link goes through the hub, which signs them in. Rules of the address: src/utils/instanceLink.ts.
//// At the merge: kept whole. -->
<template>
	<p v-if="isFiduciary" class="neo-instance-link my-4 flex flex-wrap items-center gap-3">
		<label v-if="options.length > 1" class="flex items-center gap-2 text-sm text-ink-gray-7">
			<span>{{ __('Open in the Neoffice of:') }}</span>
			<select
				v-model="chosen"
				class="rounded-5 border border-outline-gray-3 bg-surface-elevation-1 px-2 py-1 text-sm text-ink-gray-8"
			>
				<option v-for="option in options" :key="option.instance" :value="option.instance">
					{{ option.label }} ({{ option.host }})
				</option>
			</select>
		</label>
		<a
			v-if="url"
			v-external
			:href="safeUrl(url)"
			class="inline-flex items-center gap-2 rounded-5 border border-outline-gray-3 px-3 py-1.5 text-sm font-medium text-ink-gray-8 hover:bg-surface-gray-2"
		>
			<span>{{ label }}</span>
			<span aria-hidden="true">↗</span>
		</a>
		<span v-if="options.length === 1" class="text-sm text-ink-gray-7">{{ options[0].label }}</span>
	</p>
	<p v-else class="neo-instance-link my-4">
		<a
			v-if="url"
			v-external
			:href="safeUrl(url)"
			class="inline-flex items-center gap-2 rounded-5 border border-outline-gray-3 px-3 py-1.5 text-sm font-medium text-ink-gray-8 hover:bg-surface-gray-2"
		>
			<span>{{ label }}</span>
			<span aria-hidden="true">↗</span>
		</a>
		<span v-else class="text-sm text-ink-gray-7">
			{{ label }}. {{ __('Open your Neoffice to try it yourself.') }}
		</span>
	</p>
</template>

<script>
import { ref } from 'vue'

// One choice of client for every InstanceLink of the page, remembered in the browser (it can be unavailable: then the first client).
const CHOICE_KEY = 'neo-instance-link-client'
const chosenClient = ref(null)
const remembered = () => {
	try {
		return window.localStorage.getItem(CHOICE_KEY)
	} catch (e) {
		return null
	}
}
const remember = (instance) => {
	try {
		window.localStorage.setItem(CHOICE_KEY, instance)
	} catch (e) {
		// storage refused: the choice lasts for this page only
	}
}
</script>

<script setup>
import { call } from 'frappe-ui'
import { computed } from 'vue'
import { buildFiduciaryUrl, buildInstanceUrl, pickFiduciaryOption } from '@/utils/instanceLink'
import { safeUrl } from '@/utils/safeUrl'

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

const isFiduciary = computed(() => base.value?.mode === 'fiduciary')
const options = computed(() => (isFiduciary.value ? base.value.options || [] : []))

// The client the staff of a firm opens: the remembered one while it is still offered, the first otherwise.
const chosen = computed({
	get: () => pickFiduciaryOption(options.value, chosenClient.value || remembered())?.instance || '',
	set: (instance) => {
		chosenClient.value = instance
		remember(instance)
	},
})

// null until the server has answered, then null again when the learner is not linked or the address is refused.
const url = computed(() => {
	if (!base.value || base.value.mode === 'none') return null
	if (isFiduciary.value) return buildFiduciaryUrl(chosen.value, props.path)
	return buildInstanceUrl(base.value.base || '', props.path)
})
</script>
