<template>
  <div class="bg-surface-white border rounded-lg border-outline-gray-2">
    <button type="button"
      class="flex items-center gap-2.5 hover:bg-surface-gray-1 px-4 py-3 rounded-lg w-full text-left transition-colors"
      @click="open = !open">
      <span class="size-4 text-ink-gray-5 shrink-0" :class="icon" />
      <span class="font-medium text-ink-gray-8 text-base">{{ title }}</span>
      <span v-if="subtitle" class="text-ink-gray-5 text-sm">{{ subtitle }}</span>
      <span class="ml-auto size-4 text-ink-gray-4 shrink-0"
        :class="open ? 'lucide-chevron-up' : 'lucide-chevron-down'" />
    </button>

    <div v-if="open" class="px-4 pb-3 border-t border-outline-gray-2">
      <slot />
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

defineProps({
  title: { type: String, required: true },
  subtitle: { type: String, default: '' },
  icon: { type: String, default: 'lucide-activity' },
})

const open = ref(false)
</script>
