<script setup>
import { ref } from 'vue'
import { FeatherIcon } from 'frappe-ui'

const props = defineProps({
  label: { type: String, required: true },
  accept: { type: String, default: '' },
  file: { type: File, default: null },
  required: { type: Boolean, default: false },
})

const emit = defineEmits(['change'])
const input = ref(null)
const dragging = ref(false)

function openPicker() {
  input.value.click()
}

function onFileChange(event) {
  emit('change', event.target.files[0] ?? null)
}

function onDrop(event) {
  dragging.value = false
  const file = event.dataTransfer.files[0]
  if (file) emit('change', file)
}

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function clear() {
  emit('change', null)
  input.value.value = ''
}
</script>

<template>
  <div>
    <p class="mb-1.5 text-xs font-medium text-ink-gray-6">
      {{ label }}<span v-if="required" class="ml-0.5 text-ink-red-4">*</span>
    </p>

    <!-- Selected state -->
    <div v-if="file"
      class="flex items-center gap-3 rounded-lg border border-outline-gray-2 bg-surface-gray-1 px-3 py-2.5">
      <div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-surface-gray-3">
        <FeatherIcon name="file-text" class="h-4 w-4 text-ink-gray-6" />
      </div>
      <div class="min-w-0 flex-1">
        <p class="truncate text-sm font-medium text-ink-gray-8">{{ file.name }}</p>
        <p class="text-xs text-ink-gray-5">{{ formatSize(file.size) }}</p>
      </div>
      <button type="button"
        class="shrink-0 rounded p-1 text-ink-gray-4 transition hover:bg-surface-gray-3 hover:text-ink-gray-7"
        @click="clear">
        <FeatherIcon name="x" class="h-3.5 w-3.5" />
      </button>
    </div>

    <!-- Empty / drop zone -->
    <button v-else type="button" class="w-full rounded-lg border-2 border-dashed px-4 py-6 text-center transition"
      :class="dragging
        ? 'border-outline-gray-4 bg-surface-gray-2'
        : 'border-outline-gray-2 bg-surface-gray-1 hover:border-outline-gray-3 hover:bg-surface-gray-2'"
      @click="openPicker" @dragover.prevent="dragging = true" @dragleave.prevent="dragging = false"
      @drop.prevent="onDrop">
      <FeatherIcon name="upload-cloud" class="mx-auto mb-2 h-6 w-6 text-ink-gray-4" />
      <p class="text-sm text-ink-gray-6">Drag & drop or <span class="font-medium text-ink-gray-8">click to browse</span>
      </p>
    </button>

    <input ref="input" type="file" :accept="accept" class="hidden" @change="onFileChange" />
  </div>
</template>
