<template>
	<div class="flex h-screen w-screen">
		<div class="h-full">
			<NeoCockpitLMSSidebar />
		</div>
		<div class="flex-1 flex flex-col h-full overflow-auto bg-surface-white">
			<slot />
		</div>
	</div>
</template>
<script setup>
import NeoCockpitLMSSidebar from '@/components/NeoCockpitLMSSidebar.vue'
</script>
