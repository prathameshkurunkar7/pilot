<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Button, Badge, Dialog, LoadingText, ErrorMessage } from 'frappe-ui'

const route = useRoute()
const router = useRouter()
const taskId = route.params.id

const task = ref(null)
const output = ref([])
const loading = ref(true)
const error = ref('')
const streaming = ref(false)
const showKill = ref(false)
const actionLoading = ref('')
const actionError = ref('')
let es = null
const outputEl = ref(null)

const TASK_COLOR = { success: 'green', failed: 'red', running: 'blue', killed: 'gray' }

function fmtDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' })
}

function fmtDuration(s) {
  if (s == null) return '—'
  if (s < 60) return `${Math.round(s)}s`
  if (s < 3600) return `${Math.round(s / 60)}m`
  return `${Math.round(s / 3600)}h`
}

function scrollBottom() {
  nextTick(() => {
    if (outputEl.value) outputEl.value.scrollTop = outputEl.value.scrollHeight
  })
}

async function load() {
  try {
    const res = await fetch(`/api/tasks/${taskId}`)
    if (!res.ok) throw new Error(`${res.status}`)
    const d = await res.json()
    task.value = d.task
    output.value = d.output
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

function startStream() {
  streaming.value = true
  es = new EventSource(`/api/tasks/${taskId}/stream`)
  es.onmessage = (e) => {
    output.value.push(e.data)
    scrollBottom()
  }
  es.addEventListener('done', () => {
    streaming.value = false
    es.close()
    es = null
    load()
  })
  es.onerror = () => {
    streaming.value = false
    if (es) { es.close(); es = null }
  }
}

async function killTask() {
  showKill.value = false
  actionError.value = ''
  actionLoading.value = 'kill'
  try {
    const res = await fetch(`/api/tasks/${taskId}/kill`, { method: 'POST' })
    const d = await res.json()
    if (!d.ok) actionError.value = d.error
    else load()
  } catch (e) {
    actionError.value = e.message
  } finally {
    actionLoading.value = ''
  }
}

async function rerunTask() {
  actionError.value = ''
  actionLoading.value = 'rerun'
  try {
    const res = await fetch(`/api/tasks/${taskId}/rerun`, { method: 'POST' })
    const d = await res.json()
    if (d.ok) router.push(`/tasks/${d.task_id}`)
    else actionError.value = d.error
  } catch (e) {
    actionError.value = e.message
  } finally {
    actionLoading.value = ''
  }
}

onMounted(async () => {
  await load()
  if (task.value?.status === 'running') startStream()
})
onUnmounted(() => { if (es) { es.close(); es = null } })
</script>

<template>
  <div class="flex flex-col gap-4">
    <LoadingText v-if="loading" />
    <ErrorMessage v-else-if="error" :message="error" />

    <template v-else-if="task">
      <ErrorMessage :message="actionError" />

      <div class="flex flex-wrap items-center gap-4">
        <Badge :label="streaming ? 'running…' : task.status" :theme="TASK_COLOR[task.status] || 'gray'" />
        <code>{{ task.command }}</code>
        <code v-if="Object.keys(task.args).length">
          {{ Object.entries(task.args).map(([k,v]) => `${k}=${v}`).join(' ') }}
        </code>
        <span>{{ fmtDate(task.started_at) }}</span>
        <span v-if="task.duration_seconds != null">{{ fmtDuration(task.duration_seconds) }}</span>
        <Button v-if="task.status === 'running'" variant="outline" theme="red" size="sm"
          :loading="actionLoading === 'kill'" @click="showKill = true">Kill</Button>
        <Button v-else variant="outline" size="sm"
          :loading="actionLoading === 'rerun'" @click="rerunTask">Re-run</Button>
      </div>

      <div ref="outputEl" class="overflow-auto font-mono" style="max-height: 65vh; min-height: 200px;">
        <div v-if="!output.length">No output yet…</div>
        <div v-else>
          <div v-for="(line, i) in output" :key="i" class="whitespace-pre-wrap break-all">{{ line }}</div>
          <div v-if="streaming" class="animate-pulse">█</div>
        </div>
      </div>
    </template>

    <Dialog v-model="showKill" :options="{ title: 'Kill Task', size: 'sm' }">
      <template #body-content>
        <p>Send SIGTERM to the running process?</p>
        <div class="mt-4 flex justify-end gap-2">
          <Button variant="ghost" @click="showKill = false">Cancel</Button>
          <Button variant="solid" theme="red" @click="killTask">Kill</Button>
        </div>
      </template>
    </Dialog>
  </div>
</template>
