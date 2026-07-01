<template>
  <div
    class="hover-scrollbar overflow-auto px-2.5 py-2 max-h-[50vh] font-mono text-sm text-ink-gray-8 bg-surface-gray-3"
    :class="[wrap ? 'whitespace-pre-wrap' : 'whitespace-pre', rounded ? 'rounded-lg' : '']"
  >
    <p v-if="!lines.length" class="text-ink-gray-4">{{ emptyText }}</p>
    <div v-for="(line, index) in lines" :key="index" class="flex gap-3">
      <span v-if="lineNumbers" class="text-ink-gray-4 text-right select-none shrink-0" style="min-width: 1.75rem">
        {{ index + 1 }}
      </span>
      <span class="flex-1" v-html="line || '&nbsp;'" />
    </div>
    <span v-if="streaming" class="inline-block animate-pulse">█</span>
  </div>
</template>

<script setup>
defineProps({
  lines: { type: Array, default: () => [] },
  streaming: { type: Boolean, default: false },
  lineNumbers: { type: Boolean, default: false },
  wrap: { type: Boolean, default: false },
  rounded: { type: Boolean, default: true },
  emptyText: { type: String, default: 'No output.' },
})
</script>

<style scoped>
.hover-scrollbar {
  scrollbar-color: transparent transparent;
}
.hover-scrollbar:hover {
  scrollbar-color: var(--outline-gray-3) transparent;
}
.hover-scrollbar::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}
.hover-scrollbar::-webkit-scrollbar-thumb {
  background-color: transparent;
  border-radius: 9999px;
}
.hover-scrollbar:hover::-webkit-scrollbar-thumb {
  background-color: var(--outline-gray-3);
}
.hover-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
</style>
