<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { Button, Badge, Card, LoadingText, ErrorMessage, ListView } from 'frappe-ui'

const router = useRouter()
const data = ref(null)
const loading = ref(true)
const error = ref('')
const actionError = ref('')

async function load() {
  try {
    const res = await fetch('/api/dashboard')
    if (!res.ok) throw new Error(`${res.status}`)
    data.value = await res.json()
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

async function runTask(command, args = {}) {
  actionError.value = ''
  try {
    const res = await fetch('/api/tasks/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ command, ...args }),
    })
    const d = await res.json()
    if (d.ok) router.push(`/tasks/${d.task_id}`)
    else actionError.value = d.error
  } catch (e) {
    actionError.value = e.message
  }
}

function fmtDuration(s) {
  if (s == null) return '—'
  if (s < 60) return `${Math.round(s)}s`
  if (s < 3600) return `${Math.round(s / 60)}m`
  return `${Math.round(s / 3600)}h`
}

const TASK_COLOR = { success: 'green', failed: 'red', running: 'blue', killed: 'gray', queued: 'gray' }

const taskColumns = [
  { label: 'Command', key: 'command' },
  { label: 'Status', key: 'status', width: '100px' },
  { label: 'Duration', key: '_duration', width: '80px' },
]

const countdownDisplay = ref(10)
let countdown = 10
let timer

onMounted(() => {
  load()
  timer = setInterval(() => {
    countdown--
    countdownDisplay.value = countdown
    if (countdown <= 0) { countdown = 10; countdownDisplay.value = 10; load() }
  }, 1000)
})
onUnmounted(() => clearInterval(timer))
</script>

<template>
  <div class="flex flex-col gap-4">

    <LoadingText v-if="loading" />
    <ErrorMessage v-else-if="error" :message="error" />

    <template v-else-if="data">
      <div class="grid grid-cols-2 gap-4 md:grid-cols-4">
        <button class="text-left" @click="router.push('/apps')">
          <Card :title="`${data.cloned_count} / ${data.apps.length}`" subtitle="Apps cloned" />
        </button>
        <button class="text-left" @click="router.push('/sites')">
          <Card :title="`${data.online_count} / ${data.sites.length}`" subtitle="Sites online" />
        </button>
        <button class="text-left" @click="router.push('/processes')">
          <Card :title="`${data.running_count} / ${data.processes.length}`" subtitle="Processes running" />
        </button>
        <button class="text-left" @click="router.push('/tasks')">
          <Card :title="String(data.recent_tasks.length)" subtitle="Recent tasks" />
        </button>
      </div>

      <Card title="Quick Actions">
        <div class="flex flex-wrap gap-2">
          <Button variant="outline" @click="runTask('build')">Build Assets</Button>
          <Button variant="outline" @click="runTask('update')">Update Bench</Button>
          <Button variant="outline" @click="runTask('reload-supervisor')">Reload Supervisor</Button>
        </div>
        <ErrorMessage :message="actionError" class="mt-2" />
      </Card>

      <Card title="Recent Tasks">
        <template #actions>
          <Button variant="ghost" size="sm" @click="router.push('/tasks')">View all</Button>
        </template>
        <ListView
          :columns="taskColumns"
          :rows="data.recent_tasks.map(t => ({ ...t, _duration: fmtDuration(t.duration_seconds) }))"
          row-key="task_id"
          :options="{
            getRowRoute: (row) => `/tasks/${row.task_id}`,
            selectable: false,
            showTooltip: false,
          }"
        >
          <template #cell="{ column, item }">
            <Badge v-if="column.key === 'status'" :label="item" :theme="TASK_COLOR[item] || 'gray'" size="sm" />
            <span v-else>{{ item || '—' }}</span>
          </template>
        </ListView>
      </Card>
    </template>
  </div>
</template>
