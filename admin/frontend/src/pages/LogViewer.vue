<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { Button, FormControl, LoadingText } from 'frappe-ui'

const route = useRoute()
const filename = route.params.filename

const lines = ref([])
const loading = ref(true)
const error = ref('')
const search = ref(route.query.search || '')
const linesCount = ref(Number(route.query.lines) || 200)
const liveMode = ref(false)
let es = null

async function load() {
  loading.value = true
  error.value = ''
  try {
    const params = new URLSearchParams({ lines: linesCount.value })
    if (search.value) params.set('search', search.value)
    const res = await fetch(`/api/logs/${filename}?${params}`)
    if (!res.ok) throw new Error(`${res.status}`)
    const d = await res.json()
    lines.value = d.lines
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

function startLive() {
  liveMode.value = true
  lines.value = []
  es = new EventSource(`/api/logs/${filename}/stream`)
  es.onmessage = (e) => {
    lines.value.push(e.data)
    if (lines.value.length > 2000) lines.value.shift()
  }
  es.onerror = () => { stopLive() }
}

function stopLive() {
  liveMode.value = false
  if (es) { es.close(); es = null }
  load()
}

onMounted(load)
onUnmounted(() => { if (es) es.close() })
</script>

<template>
  <div class="flex flex-col gap-4">
    <div class="flex flex-wrap items-center gap-2">
      <FormControl
        type="text"
        v-model="search"
        placeholder="Search…"
        @keyup.enter="load"
      />
      <FormControl
        type="select"
        v-model="linesCount"
        :options="[
          { label: '100 lines', value: 100 },
          { label: '200 lines', value: 200 },
          { label: '500 lines', value: 500 },
          { label: '1000 lines', value: 1000 },
        ]"
        @change="load"
      />
      <Button variant="outline" @click="load">Search</Button>
      <Button v-if="!liveMode" variant="outline" @click="startLive">Live tail</Button>
      <Button v-else variant="solid" theme="red" @click="stopLive">Stop live</Button>
      <a :href="`/api/logs/${filename}/download`">Download</a>
    </div>

    <LoadingText v-if="loading" />

    <pre v-else class="overflow-auto font-mono" style="max-height: 70vh;">
      <span v-if="!lines.length">{{ search ? 'No lines match your search.' : 'Log file is empty.' }}</span>
      <div v-for="(line, i) in lines" :key="i" class="whitespace-pre-wrap break-all">{{ line }}</div>
    </pre>
    <div v-if="lines.length">{{ lines.length }} lines</div>
  </div>
</template>
