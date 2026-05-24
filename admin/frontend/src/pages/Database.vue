<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ListView, TabButtons, LoadingText, ErrorMessage } from 'frappe-ui'

const router = useRouter()
const binlogs = ref([])
const loading = ref(true)
const error = ref('')

function fmtSize(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

const tabs = [
  { label: 'Binary Logs', value: 'binlogs' },
  { label: 'Slow Queries', value: 'slow-queries' },
]

const columns = [
  { label: 'Log Name', key: 'log_name' },
  { label: 'Size', key: '_size', width: '100px' },
]

const rows = computed(() =>
  binlogs.value.map(l => ({ ...l, _size: fmtSize(l.file_size) }))
)

onMounted(async () => {
  try {
    const res = await fetch('/api/database/binlogs')
    if (!res.ok) throw new Error(await res.text())
    binlogs.value = await res.json()
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="flex flex-col gap-4">
    <div>
      <TabButtons
        :buttons="tabs"
        modelValue="binlogs"
        @update:modelValue="v => router.push(v === 'binlogs' ? '/database/binlogs' : '/database/slow-queries')"
      />
    </div>

    <LoadingText v-if="loading" />
    <ErrorMessage v-else-if="error" :message="error" />

    <div v-else>
      <ListView
        :columns="columns"
        :rows="rows"
        row-key="log_name"
        :options="{
          getRowRoute: (row) => `/database/binlogs/${row.log_name}`,
          selectable: false,
          showTooltip: false,
        }"
      />
    </div>
  </div>
</template>
