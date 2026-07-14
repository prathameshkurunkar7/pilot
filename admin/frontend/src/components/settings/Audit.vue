<template>
  <div v-if="loading" class="flex justify-center items-center h-40">
    <span class="size-5 text-ink-gray-4 animate-spin lucide-loader-circle"></span>
  </div>
  <template v-else>
    <!-- Level 1: the event types recorded in the log -->
    <template v-if="!selectedType">
      <div v-if="!types.length"
        class="py-12 border border-dashed rounded-xl border-outline-gray-2 text-ink-gray-5 text-p-sm text-center">
        Nothing has been logged yet.
      </div>
      <ListView v-else :columns="typeColumns" :rows="types" row-key="type"
        :options="{ selectable: false, showTooltip: false }">
        <template #cell="{ column, row, item }">
          <button v-if="column.key === 'type'" class="font-medium text-ink-gray-8 capitalize text-left"
            @click="openType(row.type)">
            {{ row.type }}
          </button>
          <ListRowItem v-else :column="column" :row="row" :item="item" :align="column.align" />
        </template>
      </ListView>
    </template>

    <!-- Level 2: entries for the chosen type, filterable by status and site -->
    <template v-else>
      <div class="flex flex-wrap items-center gap-2 mb-4">
        <Button variant="ghost" icon-left="arrow-left" @click="closeType">Back</Button>
        <span class="font-medium text-ink-gray-8 capitalize">{{ selectedType }}</span>
        <div class="flex flex-1 justify-end gap-2">
          <Select v-model="statusFilter" :options="statusOptions" @update:model-value="reload" />
          <Select v-model="siteFilter" :options="siteOptions" @update:model-value="reload" />
        </div>
      </div>

      <div v-if="entriesLoading" class="flex justify-center py-12"><LoadingText /></div>
      <div v-else-if="!entries.length"
        class="py-12 border border-dashed rounded-xl border-outline-gray-2 text-ink-gray-5 text-p-sm text-center">
        No entries match these filters.
      </div>
      <ListView v-else :columns="entryColumns" :rows="rows" row-key="key"
        :options="{ selectable: false, showTooltip: false }">
        <template #cell="{ column, row, item }">
          <span v-if="column.key === 'status'" class="flex items-center gap-1.5">
            <span class="size-3.5"
              :class="row.status === 'success' ? 'lucide-check text-ink-green-3' : 'lucide-x text-ink-red-3'" />
            <span class="capitalize" :class="row.status === 'success' ? 'text-ink-gray-7' : 'text-ink-red-3'">
              {{ row.status || '—' }}
            </span>
          </span>
          <ListRowItem v-else :column="column" :row="row" :item="item" :align="column.align" />
        </template>
      </ListView>
    </template>
  </template>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { Button, ListView, ListRowItem, LoadingText, Select } from 'frappe-ui'
import { settingsApi } from '@/api/settings'

const loading = ref(true)
const types = ref([])
const selectedType = ref('')

const entriesLoading = ref(false)
const entries = ref([])
const sites = ref([])
const statuses = ref([])
const statusFilter = ref('')
const siteFilter = ref('')

const typeColumns = [
  { label: 'Type', key: 'type', align: 'left', width: 2 },
  { label: 'Entries', key: 'count', align: 'left', width: 1 },
]
const entryColumns = [
  { label: 'Date', key: 'date', align: 'left', width: 2 },
  { label: 'Site', key: 'site', align: 'left', width: 2 },
  { label: 'Status', key: 'status', align: 'left', width: 1 },
  { label: 'Details', key: 'details', align: 'left', width: 2 },
]

const statusOptions = computed(() => [
  { label: 'All statuses', value: '' },
  ...statuses.value.map((s) => ({ label: s, value: s })),
])
const siteOptions = computed(() => [
  { label: 'All sites', value: '' },
  ...sites.value.map((s) => ({ label: s, value: s })),
])

const fmt = (iso) => (iso ? new Date(iso).toLocaleString() : '—')

// Backup entries carry offsite/pruned; other types just show what they have.
const detailsOf = (entry) => {
  const parts = []
  if (entry.offsite !== undefined) parts.push(entry.offsite ? 'Offsite' : 'Local')
  if (entry.pruned?.length) parts.push(`pruned ${entry.pruned.length}`)
  return parts.join(' · ') || '—'
}

const rows = computed(() =>
  entries.value.map((entry) => ({
    // logged_at is stamped per append, so it stays stable across filtering.
    key: `${entry.logged_at}|${entry.type}|${entry.site ?? ''}`,
    date: fmt(entry.finished_at || entry.logged_at),
    site: entry.site || '—',
    status: entry.status || '',
    details: detailsOf(entry),
  })),
)

async function loadTypes() {
  loading.value = true
  try {
    types.value = (await settingsApi.audit.types()).types || []
  } finally {
    loading.value = false
  }
}

async function reload() {
  entriesLoading.value = true
  try {
    const params = { type: selectedType.value }
    if (statusFilter.value) params.status = statusFilter.value
    if (siteFilter.value) params.site = siteFilter.value
    const data = await settingsApi.audit.log(params)
    entries.value = data.entries || []
    sites.value = data.sites || []
    statuses.value = data.statuses || []
  } finally {
    entriesLoading.value = false
  }
}

function openType(type) {
  selectedType.value = type
  statusFilter.value = ''
  siteFilter.value = ''
  reload()
}

function closeType() {
  selectedType.value = ''
}

onMounted(loadTypes)
</script>
