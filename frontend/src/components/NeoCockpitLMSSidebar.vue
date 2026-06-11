<template>
	<AppSidebar v-if="failed" />
	<NeoCockpitBridge
		v-else
		:surface-app="surfaceApp"
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
 * LMS flavor of the shared Neoffice chrome (NeoCockpit). Maps the existing
 * getSidebarLinks() output into contextNav; the native AppSidebar stays as
 * an automatic fallback (bundle missing, kill-switch, boot failure).
 * Recipe: neoffice ADR-015.
 */
import AppSidebar from '@/components/Sidebar/AppSidebar.vue'
import NeoCockpitBridge from '@/components/NeoCockpitBridge.vue'
import CommandPalette from '@/components/CommandPalette/CommandPalette.vue'

import { getSidebarLinks } from '@/utils'
import { useSettings } from '@/stores/settings'
import { useRouter, useRoute } from 'vue-router'
import { ref, computed } from 'vue'

const router = useRouter()
const route = useRoute()
const settingsStore = useSettings()
const failed = ref(false)

const surfaceApp = {
	name: 'lms',
	title: 'Learning',
	logo: '/assets/lms/frontend/learning.svg',
}

// LMS icons are PascalCase lucide names; NeoCockpit takes kebab strings
const toKebab = (n) =>
	String(n || '')
		.replace(/([a-z0-9])([A-Z])/g, '$1-$2')
		.toLowerCase()

function navigate(r) {
	if (!r) return
	if (r.startsWith('/app') || r.startsWith('http')) window.location.href = r
	else router.push(r)
}

const contextNav = computed(() => {
	// track the route so active states refresh
	const currentName = route.name
	const links = getSidebarLinks() || []
	return links.map((section) => ({
		label: section.hideLabel ? undefined : section.label,
		items: section.items
			// the cockpit search bar already covers Search
			.filter((item) => item.label !== 'Search')
			.map((item) => {
				const external =
					typeof item.to === 'string' &&
					(item.to.startsWith('http') || item.to.includes('@'))
				return {
					label: item.label,
					icon: 'lucide-' + toKebab(item.icon),
					active:
						currentName === item.to ||
						(item.activeFor || []).includes(currentName),
					onClick: external
						? () =>
								window.open(
									item.to.includes('@') ? `mailto:${item.to}` : item.to,
									'_blank'
								)
						: () => router.push({ name: item.to }),
				}
			}),
	}))
})

function openSearch() {
	settingsStore.isCommandPaletteOpen = true
}
</script>
