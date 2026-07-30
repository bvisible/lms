<template>
	<AppSidebar v-if="failed" />
	<NeoCockpitBridge
		v-else
		:surface-app="surfaceApp"
		:utilities="utilities"
		:context-nav="contextNav"
		:navigate="navigate"
		:on-search="openSearch"
		search-kbd="⌘K"
		@failed="failed = true"
	/>
	<CommandPalette
		v-if="!failed"
		v-model="settingsStore.isCommandPaletteOpen"
	/>
</template>

<script setup>
/**
 * LMS flavor of the shared Neoffice chrome (NeoCockpit).
 *
 * The nav below is declared EXPLICITLY, the way Drive does it — it is not
 * mapped from getSidebarLinks(). Two reasons:
 *
 *  1. A paying learner must see a learner's menu. Upstream's list carries items
 *     that belong to a platform back-office (job board, plaftorm statistics)
 *     and shows them to everyone; on a course a customer paid for, that reads
 *     as having wandered into someone else's admin.
 *  2. Mapping upstream means every upstream merge can silently change our menu.
 *     Declaring it decouples the two — the 513-commit merge of 2026-07-29 got
 *     away with it by luck.
 *
 * Adding an entry is therefore a decision, not an inheritance.
 *
 * The native AppSidebar stays as an automatic fallback (bundle missing,
 * kill-switch, boot failure). Recipe: neoffice ADR-015.
 */
import AppSidebar from '@/components/Sidebar/AppSidebar.vue'
import NeoCockpitBridge from '@/components/NeoCockpitBridge.vue'
import CommandPalette from '@/components/CommandPalette/CommandPalette.vue'

import { translationsReady } from '@/translation'
import { createResource } from 'frappe-ui'
import { usersStore } from '@/stores/user'
import { useSettings } from '@/stores/settings'
import { useRouter, useRoute } from 'vue-router'
import { ref, computed } from 'vue'

const router = useRouter()
const route = useRoute()
const settingsStore = useSettings()
const { userResource } = usersStore()

// Only categories that hold a published course — an entry filtering down to
// nothing is a dead end (a fresh LMS ships seven empty demo categories).
const categories = createResource({
	url: 'lms.lms.neoffice_catalogue.get_course_categories',
	cache: 'lms-course-categories',
	auto: true,
})
const failed = ref(false)

const surfaceApp = {
	name: 'lms',
	title: 'Learning',
	logo: '/assets/lms/frontend/learning.svg',
}

function navigate(r) {
	if (!r) return
	if (r.startsWith('/app') || r.startsWith('http')) window.location.href = r
	else router.push(r)
}

// Whoever runs the platform, as opposed to whoever learns on it.
const isStaff = computed(() => {
	const u = userResource?.data
	return Boolean(u?.is_moderator || u?.is_instructor || u?.is_evaluator)
})

// A learner has no webmail, no NORA and no desk — and the Notes icon navigates
// to /app/notes, which only answers with a permission error. Staff running the
// platform keep the full row.
const utilities = computed(() => (isStaff.value ? null : []))

const item = (label, icon, routeName, activeFor = []) => ({
	label,
	icon: `lucide-${icon}`,
	active: [routeName, ...activeFor].includes(route.name),
	onClick: () => router.push({ name: routeName }),
})

const contextNav = computed(() => {
	// Reading route.name here keeps active states in sync with navigation, and
	// translationsReady so the labels are recomputed when the dictionary lands —
	// __() reads a non-reactive global, so a cold first visit would otherwise
	// keep the English strings captured before the fetch resolved.
	translationsReady.value
	const sections = [
		{
			items: [item(__('Home'), 'home', 'Home')],
		},
		{
			label: __('Learning'),
			items: [
				item(__('My courses'), 'book-open', 'Courses', [
					'CourseDetail',
					'Lesson',
					'SCORMChapter',
				]),
			],
		},
	]

	// The profile route is /user/:username, so this only works once the user
	// resource has resolved.
	const username = userResource?.data?.username
	if (username) {
		sections[1].items.push({
			label: __('My certificates'),
			icon: 'lucide-graduation-cap',
			active: route.name === 'ProfileCertificates',
			onClick: () =>
				router.push({ name: 'ProfileCertificates', params: { username } }),
		})
	}

	const cats = categories.data || []
	if (cats.length) {
		sections.push({
			label: __('Categories'),
			items: cats.map((c) => ({
				label: c.label,
				icon: 'lucide-tag',
				active: route.name === 'Courses' && route.query.category === c.name,
				badge: String(c.total),
				onClick: () =>
					router.push({ name: 'Courses', query: { category: c.name } }),
			})),
		})
	}

	if (isStaff.value) {
		sections.push({
			label: __('Manage'),
			items: [
				item(__('Batches'), 'users', 'Batches', ['BatchDetail']),
				item(__('Quizzes'), 'circle-help', 'Quizzes', [
					'QuizForm',
					'QuizSubmissionList',
				]),
				item(__('Statistics'), 'trending-up', 'Statistics'),
			],
		})
	}

	return sections
})

function openSearch() {
	settingsStore.isCommandPaletteOpen = true
}
</script>
