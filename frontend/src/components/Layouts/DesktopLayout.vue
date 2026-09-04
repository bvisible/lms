<template>
	<div class="flex h-screen w-screen">
		<a
			href="#main-content"
			@click.prevent="skipToContent('main-content')"
			class="sr-only focus:not-sr-only focus:absolute focus:start-4 focus:top-4 focus:z-50 focus:rounded focus:bg-surface-base focus:px-4 focus:py-2 focus:text-ink-gray-9 focus:shadow-md focus:outline-none focus:ring-2 focus:ring-outline-gray-3"
		>
			{{ __('Skip to main content') }}
		</a>
		<!-- //// Neoffice — 2c0b294c « NeoCockpit as the LMS sidebar ». Upstream mounts its
		//// own <AppSidebar> (with `border-e bg-surface-sidebar` on the wrapper); we mount the
		//// shared Neoffice chrome instead, so the LMS carries the same navigation as the desk,
		//// Drive, CRM and the rest. NeoCockpitLMSSidebar still falls back to upstream's
		//// AppSidebar when the cockpit bundle fails to load, so this is a swap, not a removal.
		//// At the merge: keep our <div>, and re-check upstream's classes only if the sidebar
		//// gains a new layout contract. -->
		<!-- Neoffice: NeoCockpit replaces upstream's AppSidebar (shared chrome). -->
		<div class="h-full">
			<NeoCockpitLMSSidebar />
		</div>
		<main
			id="main-content"
			tabindex="-1"
			class="flex-1 flex flex-col h-full overflow-auto bg-surface-base focus:outline-none"
		>
			<slot />
		</main>
	</div>
</template>
<script setup>
//// Neoffice — 2c0b294c: this import replaces upstream's
//// `import AppSidebar from '@/components/Sidebar/AppSidebar.vue'` (removed here, still
//// used inside NeoCockpitLMSSidebar.vue as the fallback). At the merge, upstream's line
//// comes back as an addition: drop it here, ours is the one that must stay.
import NeoCockpitLMSSidebar from '@/components/NeoCockpitLMSSidebar.vue'
import { skipToContent } from '@/utils/a11y'
</script>
