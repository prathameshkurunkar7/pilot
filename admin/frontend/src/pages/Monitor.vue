<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { Badge, ListView, Button, LoadingText, ErrorMessage, Progress, AxisChart } from 'frappe-ui'

const router = useRouter()

// --- Window selection ---
const WINDOWS = [
  { key: 'live', label: 'Live' },
  { key: '30m', label: '30m' },
  { key: '1h', label: '1h' },
  { key: '6h', label: '6h' },
  { key: '12h', label: '12h' },
  { key: '24h', label: '24h' },
  { key: '1w', label: '1w' },
]
const WINDOW_SECONDS = { '30m': 1800, '1h': 3600, '6h': 21600, '12h': 43200, '24h': 86400, '1w': 604800 }
const TIME_GRAIN = { live: 'second', '30m': 'minute', '1h': 'minute', '6h': 'hour', '12h': 'hour', '24h': 'hour', '1w': 'day' }
const PALETTE = ['#2490ef', '#f59e0b', '#10b981', '#8b5cf6', '#ef4444', '#06b6d4', '#ec4899']

const activeWindow = ref('live')
const isHistorical = computed(() => activeWindow.value !== 'live')
const windowLabel = computed(() => WINDOWS.find(w => w.key === activeWindow.value)?.label ?? '')

// --- Live stats ---
const stats = ref(null)
const liveHistory = ref([])
const MAX_LIVE = 60

async function loadStats() {
  if (isHistorical.value) return
  try {
    const res = await fetch('/api/stats')
    if (!res.ok) return
    const s = await res.json()
    stats.value = s
    liveHistory.value = [
      ...liveHistory.value.slice(-(MAX_LIVE - 1)),
      { time: new Date(), CPU: s.cpu_percent, Memory: s.memory_percent },
    ]
  } catch {}
}

// --- Historical data (from monitor log files) ---
const system = ref({ earliest: null, points: [] })
const application = ref({ earliest: null, services: [], cpu: [], memory: [] })
const historyLoading = ref(false)
const historyError = ref('')
const historyNow = ref(Date.now())

async function loadHistory(window) {
  historyLoading.value = true
  historyError.value = ''
  try {
    const res = await fetch(`/api/monitor-history?window=${window}`)
    const d = await res.json()
    if (!res.ok || d.error) throw new Error(d.error || `HTTP ${res.status}`)
    // Server-clock "now" (epoch ms) anchors the axis so windowing is independent
    // of the browser timezone.
    historyNow.value = d.now ?? Date.now()
    system.value = d.system
    application.value = d.application
  } catch (e) {
    historyError.value = e.message
  } finally {
    historyLoading.value = false
  }
}

function setWindow(key) {
  activeWindow.value = key
  if (key === 'live') {
    loadStats()
  } else {
    loadHistory(key)
  }
}

// --- Coverage: detect when data does not span the selected window ---
const axisMin = computed(() => historyNow.value - (WINDOW_SECONDS[activeWindow.value] || 3600) * 1000)
const axisMax = computed(() => historyNow.value)

function isPartial(earliest) {
  return earliest != null && earliest > axisMin.value + 1000
}
function humanizeSince(earliest) {
  if (earliest == null) return ''
  const seconds = Math.floor((historyNow.value - earliest) / 1000)
  if (seconds < 3600) return `${Math.max(1, Math.floor(seconds / 60))}m`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`
  return `${Math.floor(seconds / 86400)}d`
}

const systemEmpty = computed(() => isHistorical.value && !historyLoading.value && !system.value.points.length)
const appEmpty = computed(() => isHistorical.value && !historyLoading.value && !application.value.cpu.length)

// --- Chart configs (Grafana-style: thin lines with gradient area fill) ---
function hexToRgba(hex, alpha) {
  const value = parseInt(hex.slice(1), 16)
  return `rgba(${(value >> 16) & 255}, ${(value >> 8) & 255}, ${value & 255}, ${alpha})`
}
function areaGradient(hex) {
  return {
    type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
    colorStops: [
      { offset: 0, color: hexToRgba(hex, 0.4) },
      { offset: 1, color: hexToRgba(hex, 0.01) },
    ],
  }
}
const GRID_LINE = { show: true, lineStyle: { type: 'dashed', color: 'var(--outline-gray-2)' } }

const fixedXAxis = computed(() => ({
  key: 'time',
  type: 'time',
  timeGrain: TIME_GRAIN[activeWindow.value],
  echartOptions: { min: axisMin.value, max: axisMax.value, splitLine: GRID_LINE },
}))

// One shared builder so every chart renders identically.
function buildChart({ title, subtitle = undefined, data, series, xAxis, yMax = undefined, unit = '' }) {
  return {
    title,
    subtitle,
    data,
    xAxis,
    yAxis: { yMin: 0, yMax, echartOptions: { name: unit, splitLine: GRID_LINE } },
    series: series.map((name, index) => {
      const color = PALETTE[index % PALETTE.length]
      return {
        name,
        type: 'line',
        color,
        echartOptions: {
          symbol: 'none',
          lineStyle: { width: 1.5 },
          areaStyle: { color: areaGradient(color) },
          emphasis: { focus: 'series' },
        },
      }
    }),
  }
}

const liveChartConfig = computed(() => buildChart({
  title: 'CPU & Memory',
  data: liveHistory.value,
  series: ['CPU', 'Memory'],
  xAxis: { key: 'time', type: 'time', timeGrain: 'second', echartOptions: { splitLine: GRID_LINE } },
  yMax: 100,
  unit: '%',
}))

const systemChartConfig = computed(() => buildChart({
  title: 'CPU & Memory',
  data: system.value.points,
  series: ['CPU', 'Memory'],
  xAxis: fixedXAxis.value,
  yMax: 100,
  unit: '%',
}))

const loadPoints = computed(() =>
  system.value.points.map(p => ({ time: p.time, '1m': p.Load1, '5m': p.Load5, '15m': p.Load15 })),
)
const loadChartConfig = computed(() => buildChart({
  title: 'Load Average',
  data: loadPoints.value,
  series: ['1m', '5m', '15m'],
  xAxis: fixedXAxis.value,
}))

const DISK_SERIES = 'Root Disk'
const hasStorage = computed(() => system.value.storage != null)
const storageChartConfig = computed(() => {
  const s = system.value.storage
  const gb = mb => (mb / 1024).toFixed(1)
  const series = [DISK_SERIES]
  const parts = []
  if (s?.disk) parts.push(`${DISK_SERIES} ${gb(s.disk.used_mb)} / ${gb(s.disk.total_mb)} GB`)
  // zfs is optional — only add the pool series when the bench is volume-backed.
  if (s?.zfs) {
    series.push(s.zfs.pool)
    parts.push(`${s.zfs.pool} ${gb(s.zfs.used_mb)} / ${gb(s.zfs.total_mb)} GB`)
  }
  return buildChart({
    title: 'Storage',
    subtitle: parts.join('   ·   '),
    data: system.value.points,
    series,
    xAxis: fixedXAxis.value,
    yMax: 100,
    unit: '%',
  })
})

const appCpuConfig = computed(() => buildChart({
  title: 'Process CPU',
  data: application.value.cpu,
  series: application.value.services,
  xAxis: fixedXAxis.value,
  yMax: 100,
  unit: '%',
}))

const appMemConfig = computed(() => buildChart({
  title: 'Process Memory',
  data: application.value.memory,
  series: application.value.services,
  xAxis: fixedXAxis.value,
  unit: 'MB',
}))

// --- Helpers ---
function formatBytes(bytes) {
  if (bytes < 1024 ** 2) return (bytes / 1024).toFixed(0) + ' KB'
  if (bytes < 1024 ** 3) return (bytes / 1024 ** 2).toFixed(1) + ' MB'
  return (bytes / 1024 ** 3).toFixed(1) + ' GB'
}
function datasetLabel(name) {
  return name.split('/').pop()
}
function datasetPercent(dataset) {
  return dataset.quota_bytes ? (dataset.used_bytes / dataset.quota_bytes) * 100 : 0
}
const POOL_HEALTH_THEME = { ONLINE: 'green', DEGRADED: 'yellow' }
function poolHealthTheme(health) {
  return POOL_HEALTH_THEME[health] ?? 'red'
}
function diskPercent(bytes) {
  return stats.value ? (bytes / stats.value.disk_total) * 100 : 0
}

// --- Processes (live control panel) ---
const processes = ref([])
const production = ref(false)
const processLoading = ref(true)
const processError = ref('')
const controlError = ref('')
const controlLoading = ref('')
const paused = ref(false)
const countdownDisplay = ref(15)
let countdown = 15

const STATUS_COLOR = { running: 'green', stopped: 'red', error: 'red', unknown: 'gray' }
const anyRunning = computed(() => processes.value.some(p => p.status === 'running'))

const columns = [
  { label: 'Name', key: 'name', width: '180px' },
  { label: 'Status', key: 'status', width: '100px' },
  { label: 'PID', key: 'pid', width: '70px' },
  { label: 'CPU', key: 'cpu_percent', width: '70px' },
  { label: 'Memory', key: 'pss_mb', width: '90px' },
  { label: 'Uptime', key: 'uptime', width: '100px' },
  { label: 'Log', key: 'log_filename' },
]

async function loadProcesses() {
  try {
    const res = await fetch('/api/processes/')
    if (!res.ok) throw new Error(`${res.status}`)
    const d = await res.json()
    processes.value = d.processes
    production.value = d.production ?? false
  } catch (e) {
    processError.value = e.message
  } finally {
    processLoading.value = false
  }
}

async function control(action) {
  controlLoading.value = action
  controlError.value = ''
  try {
    const res = await fetch(`/api/processes/${action}`, { method: 'POST' })
    const d = await res.json()
    if (!d.ok) { controlError.value = d.error; return }
    await loadProcesses()
  } catch (e) {
    controlError.value = e.message
  } finally {
    controlLoading.value = ''
  }
}

function openLog(filename) {
  router.push({ path: '/logs', query: { file: filename } })
}

let statsTimer, processTimer

onMounted(() => {
  loadStats()
  loadProcesses()
  statsTimer = setInterval(loadStats, 3000)
  processTimer = setInterval(() => {
    if (paused.value) return
    countdown--
    countdownDisplay.value = countdown
    if (countdown <= 0) { countdown = 15; countdownDisplay.value = 15; loadProcesses() }
  }, 1000)
})
onUnmounted(() => {
  clearInterval(statsTimer)
  clearInterval(processTimer)
})
</script>

<template>
  <div class="flex flex-col gap-4 sm:gap-6">

    <!-- System -->
    <div class="py-1 sm:rounded-lg sm:border sm:border-outline-gray-1 sm:bg-surface-white sm:px-6 sm:py-5 sm:shadow-sm">
      <div class="mb-4 flex flex-wrap items-center justify-between gap-2">
        <h2 class="font-semibold text-ink-gray-9">System</h2>
        <div class="flex items-center gap-3">
          <div class="flex items-center rounded-lg border border-outline-gray-1 bg-surface-gray-1 p-0.5">
            <button
              v-for="w in WINDOWS"
              :key="w.key"
              class="rounded px-2.5 py-1 text-xs font-medium transition-colors"
              :class="activeWindow === w.key ? 'bg-surface-white text-ink-gray-9 shadow-sm' : 'text-ink-gray-5 hover:text-ink-gray-7'"
              @click="setWindow(w.key)"
            >{{ w.label }}</button>
          </div>
          <span v-if="!isHistorical" class="flex items-center gap-1.5 text-xs text-ink-gray-4">
            <span class="h-2 w-2 animate-pulse rounded-full bg-surface-green-3" />
            Live
          </span>
        </div>
      </div>

      <!-- Live snapshot -->
      <div v-if="!isHistorical && stats" class="flex flex-col gap-6">
        <div class="grid grid-cols-1 gap-6 sm:grid-cols-3">
          <div>
            <div class="mb-2 flex items-baseline justify-between">
              <span class="text-sm font-medium text-ink-gray-7">CPU</span>
              <span class="text-sm font-semibold text-ink-gray-9">{{ stats.cpu_percent.toFixed(1) }}%</span>
            </div>
            <Progress :value="stats.cpu_percent" size="md" />
          </div>
          <div>
            <div class="mb-2 flex items-baseline justify-between">
              <span class="text-sm font-medium text-ink-gray-7">Memory</span>
              <span class="text-sm text-ink-gray-5">{{ formatBytes(stats.memory_used) }} / {{ formatBytes(stats.memory_total) }}</span>
            </div>
            <Progress :value="stats.memory_percent" size="md" />
          </div>
          <div v-if="stats.volume?.enabled">
            <div class="mb-2 flex items-baseline justify-between">
              <span class="text-sm font-medium text-ink-gray-7">ZFS Pool</span>
              <Badge :label="stats.volume.pool_health" :theme="poolHealthTheme(stats.volume.pool_health)" />
            </div>
            <p class="font-mono text-xs text-ink-gray-4">{{ stats.volume.pool }}</p>
          </div>
          <div v-else>
            <div class="mb-2 flex items-baseline justify-between">
              <span class="text-sm font-medium text-ink-gray-7">Disk</span>
              <span class="text-sm text-ink-gray-5">{{ formatBytes(stats.disk_used) }} / {{ formatBytes(stats.disk_total) }}</span>
            </div>
            <Progress :value="stats.disk_percent" size="md" />
          </div>
        </div>

        <div v-if="stats.volume?.enabled" class="grid grid-cols-1 gap-6 sm:grid-cols-3">
          <div v-for="dataset in stats.volume.datasets" :key="dataset.name">
            <div class="mb-2 flex items-baseline justify-between">
              <span class="text-sm font-medium capitalize text-ink-gray-7">{{ datasetLabel(dataset.name) }}</span>
              <span class="text-sm text-ink-gray-5">{{ formatBytes(dataset.used_bytes) }} / {{ formatBytes(dataset.quota_bytes) }}</span>
            </div>
            <Progress :value="datasetPercent(dataset)" size="md" />
            <p class="mt-1 text-xs text-ink-gray-4">
              {{ formatBytes(dataset.available_bytes) }} available · {{ formatBytes(dataset.reservation_bytes) }} reserved
            </p>
          </div>
          <div>
            <div class="mb-2 flex items-baseline justify-between">
              <span class="text-sm font-medium text-ink-gray-7">Root Disk</span>
              <span class="text-sm text-ink-gray-5">{{ formatBytes(stats.disk_used) }} / {{ formatBytes(stats.disk_total) }}</span>
            </div>
            <Progress :value="stats.disk_percent" size="md" />
          </div>
        </div>

        <div v-else-if="stats.paths?.length" class="grid grid-cols-1 gap-6 sm:grid-cols-3">
          <div v-for="pathInfo in stats.paths" :key="pathInfo.path">
            <div class="mb-2 flex items-baseline justify-between">
              <span class="text-sm font-medium text-ink-gray-7">{{ pathInfo.label }}</span>
              <span class="text-sm text-ink-gray-5">{{ formatBytes(pathInfo.used_bytes) }}</span>
            </div>
            <Progress :value="diskPercent(pathInfo.used_bytes)" size="md" />
          </div>
        </div>

        <AxisChart v-if="liveHistory.length > 1" :config="liveChartConfig" />
      </div>

      <!-- Historical system -->
      <template v-else-if="isHistorical">
        <LoadingText v-if="historyLoading" />
        <ErrorMessage v-else-if="historyError" :message="historyError" />
        <div v-else-if="systemEmpty" class="flex flex-col items-center justify-center gap-1 rounded-lg border border-dashed border-outline-gray-2 py-10 text-center">
          <p class="text-sm font-medium text-ink-gray-7">No system data for the last {{ windowLabel }}</p>
          <p class="text-xs text-ink-gray-5">Monitoring hasn't collected anything in this range yet.</p>
        </div>
        <div v-else class="flex flex-col gap-6">
          <div
            v-if="isPartial(system.earliest)"
            class="flex items-start gap-2 rounded-md bg-surface-amber-1 px-3 py-2 text-xs text-ink-amber-3"
          >
            <span class="font-medium">Partial data:</span>
            <span>only the last {{ humanizeSince(system.earliest) }} is available — the {{ windowLabel }} window isn't fully covered yet.</span>
          </div>
          <AxisChart :config="systemChartConfig" />
          <AxisChart :config="loadChartConfig" />
          <AxisChart v-if="hasStorage" :config="storageChartConfig" />
        </div>
      </template>
    </div>

    <!-- Application (historical, from per-bench log) -->
    <div v-if="isHistorical" class="py-1 sm:rounded-lg sm:border sm:border-outline-gray-1 sm:bg-surface-white sm:px-6 sm:py-5 sm:shadow-sm">
      <h2 class="mb-4 font-semibold text-ink-gray-9">Application Processes</h2>
      <LoadingText v-if="historyLoading" />
      <div v-else-if="appEmpty" class="flex flex-col items-center justify-center gap-1 rounded-lg border border-dashed border-outline-gray-2 py-10 text-center">
        <p class="text-sm font-medium text-ink-gray-7">No process data for the last {{ windowLabel }}</p>
        <p class="text-xs text-ink-gray-5">Application metrics are recorded only in production.</p>
      </div>
      <div v-else class="flex flex-col gap-6">
        <div
          v-if="isPartial(application.earliest)"
          class="flex items-start gap-2 rounded-md bg-surface-amber-1 px-3 py-2 text-xs text-ink-amber-3"
        >
          <span class="font-medium">Partial data:</span>
          <span>only the last {{ humanizeSince(application.earliest) }} is available — the {{ windowLabel }} window isn't fully covered yet.</span>
        </div>
        <AxisChart :config="appCpuConfig" />
        <AxisChart :config="appMemConfig" />
      </div>
    </div>

    <!-- Processes (live control panel) -->
    <div class="py-1 sm:rounded-lg sm:border sm:border-outline-gray-1 sm:bg-surface-white sm:px-6 sm:py-5 sm:shadow-sm">
      <div class="mb-4 flex items-center justify-between">
        <h2 class="font-semibold text-ink-gray-9">Processes</h2>
        <div class="flex items-center gap-2">
          <span v-if="!paused" class="text-xs text-ink-gray-4">Refreshing in {{ countdownDisplay }}s</span>
          <Button variant="ghost" size="sm" @click="paused = !paused">{{ paused ? 'Resume' : 'Pause' }}</Button>
        </div>
      </div>

      <div v-if="production" class="mb-3 flex items-center gap-2">
        <Button variant="subtle" :loading="controlLoading === 'start'" :disabled="!!controlLoading || anyRunning" @click="control('start')">Start</Button>
        <Button variant="subtle" :loading="controlLoading === 'stop'" :disabled="!!controlLoading || !anyRunning" @click="control('stop')">Stop</Button>
        <Button variant="subtle" :loading="controlLoading === 'restart'" :disabled="!!controlLoading || !anyRunning" @click="control('restart')">Restart</Button>
      </div>

      <ErrorMessage v-if="controlError" :message="controlError" class="mb-3" />

      <LoadingText v-if="processLoading" />
      <ErrorMessage v-else-if="processError" :message="processError" />
      <ListView
        v-else
        :columns="columns"
        :rows="processes"
        row-key="name"
        :options="{ selectable: false, showTooltip: false }"
      >
        <template #cell="{ column, item }">
          <Badge v-if="column.key === 'status'" :label="item" :theme="STATUS_COLOR[item] || 'gray'" />
          <span v-else-if="column.key === 'cpu_percent'">{{ item != null ? item.toFixed(1) + '%' : '—' }}</span>
          <span v-else-if="column.key === 'pss_mb'">{{ item != null ? item.toFixed(0) + ' MB' : '—' }}</span>
          <button v-else-if="column.key === 'log_filename' && item" class="text-ink-blue-2 hover:underline" @click="openLog(item)">{{ item }}</button>
          <span v-else>{{ item || '—' }}</span>
        </template>
      </ListView>
    </div>

  </div>
</template>
