<template>
	<div class="flex h-screen w-screen">
		<a
			href="#main-content"
			@click.prevent="skipToContent('main-content')"
			class="sr-only focus:not-sr-only focus:absolute focus:start-4 focus:top-4 focus:z-50 focus:rounded focus:bg-surface-base focus:px-4 focus:py-2 focus:text-ink-gray-9 focus:shadow-md focus:outline-none focus:ring-2 focus:ring-outline-gray-3"
		>
			{{ __('Skip to main content') }}
		</a>
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
import NeoCockpitLMSSidebar from '@/components/NeoCockpitLMSSidebar.vue'
import { skipToContent } from '@/utils/a11y'
</script>
