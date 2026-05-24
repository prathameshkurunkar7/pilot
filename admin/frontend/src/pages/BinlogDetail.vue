<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { Button, ListView, LoadingText, ErrorMessage } from 'frappe-ui'

const route = useRoute()
const logName = route.params.name
const events = ref([])
const loading = ref(true)
const error = ref('')
const limit = ref(200)
const offset = ref(0)

const columns = [
  { label: 'Pos', key: 'pos', width: '80px' },
  { label: 'Type', key: 'event_type', width: '150px' },
  { label: 'End Pos', key: 'end_log_pos', width: '80px' },
  { label: 'Info', key: 'info' },
]

const rows = computed(() => events.value)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const params = new URLSearchParams({ limit: limit.value, offset: offset.value })
    const res = await fetch(`/api/database/binlogs/${logName}?${params}`)
    if (!res.ok) throw new Error(`${res.status}`)
    const d = await res.json()
    events.value = d.events
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

function nextPage() { offset.value += limit.value; load() }
function prevPage() { offset.value = Math.max(0, offset.value - limit.value); load() }

onMounted(load)
</script>

<template>
  <div class="flex flex-col gap-4">
    <LoadingText v-if="loading" />
    <ErrorMessage v-else-if="error" :message="error" />

    <div v-else>
      <ListView
        :columns="columns"
        :rows="rows"
        row-key="pos"
        :options="{ selectable: false, showTooltip: false }"
      />

      <div class="mt-4 flex items-center justify-between">
        <Button variant="outline" :disabled="offset === 0" @click="prevPage">← Previous</Button>
        <span>offset {{ offset }}</span>
        <Button variant="outline" :disabled="events.length < limit" @click="nextPage">Next →</Button>
      </div>
    </div>
  </div>
</template>
