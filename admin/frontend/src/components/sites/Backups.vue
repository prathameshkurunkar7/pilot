<template>
  <div class="space-y-4 mt-5">
    <CronScheduleControl ref="scheduleRef" title="Automatic backups" noun="backups"
      enabled-hint="Taken on a schedule and kept for 30 days." disabled-hint="Automatic backups are disabled."
      disable-body="Automatic backups will stop. Existing backups are kept."
      retention-hint="Kept 30 days. Times shown in your timezone." :fetch-schedule="fetchSchedule"
      :set-schedule="setSchedule" :remove-schedule="removeSchedule">
      <template #actions>
        <Button size="sm" :loading="backingUp" @click="backupNow">
          <template #prefix><span class="size-4 lucide-archive" /></template>
          Back up now
        </Button>
      </template>
    </CronScheduleControl>

    <ErrorMessage v-if="error" :message="error" />

    <div :class="backups.length ? '' : 'rounded-xl border border-dashed border-outline-gray-2'">
      <div v-if="backupsLoading" class="flex justify-center py-12">
        <LoadingText />
      </div>
      <div v-else-if="!backups.length" class="flex flex-col items-center gap-4 py-12 text-center">
        <span class="place-items-center grid bg-surface-gray-2 rounded-full size-10 text-ink-gray-5">
          <span class="size-5 lucide-archive" />
        </span>
        <div>
          <p class="font-medium text-ink-gray-7 text-sm">No backups yet</p>
          <p class="mt-1 max-w-xs text-ink-gray-5 text-p-sm">
            <template v-if="scheduleRef?.disabled">Enable automatic backups to start protecting your site.</template>
            <template v-else>The first automatic backup runs {{ nextHint }}. You can also back up now.</template>
          </p>
        </div>
        <Button size="sm" :loading="backingUp" @click="backupNow">
          <template #prefix><span class="size-4 lucide-archive" /></template>
          Back up now
        </Button>
      </div>
      <ListView v-else :columns="columns" :rows="rows" row-key="name"
        :options="{ selectable: false, showTooltip: false }">
        <template #cell="{ column, row, item }">
          <div v-if="column.key === 'actions'" class="flex justify-end">
            <Dropdown :options="menuOptions(row.set)" placement="left">
              <template #default="{ open }">
                <Button variant="ghost" size="sm" :active="open"><span class="size-4 lucide-ellipsis" /></Button>
              </template>
            </Dropdown>
          </div>
          <div v-else-if="column.key === 'offsite'" class="flex justify-center">
            <span v-if="row.set.is_offsite" class="size-4 text-ink-green-6 lucide-circle-check" title="Backed up offsite" />
            <span v-else class="text-ink-gray-4">—</span>
          </div>
          <ListRowItem v-else :column="column" :row="row" :item="item" :align="column.align" />
        </template>
      </ListView>
      <ListFooter v-if="backups.length" class="mt-2 px-1" :model-value="backupsLimit" :options="footerOptions"
        @update:model-value="setBackupsPageLength" @load-more="loadMoreBackups" />
    </div>
  </div>

  <!-- Delete backup dialog -->
  <Dialog v-model="showDelete" :options="{ title: 'Delete Backup', size: 'sm' }">
    <template #body-content>
      <p class="text-ink-gray-7 text-sm">
        Delete the backup from <strong>{{ deleteTarget ? fmt(deleteTarget.created_at) : '' }}</strong>? This cannot be
        undone.
      </p>
      <ErrorMessage v-if="deleteError" :message="deleteError" class="mt-2" />
      <div class="flex justify-end gap-2 mt-4">
        <Button variant="ghost" @click="showDelete = false">Cancel</Button>
        <Button variant="solid" theme="red" :loading="deleting" @click="confirmDelete">Delete</Button>
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Button, Dialog, Dropdown, ErrorMessage, ListFooter, ListView, ListRowItem, LoadingText } from 'frappe-ui'
import CronScheduleControl from '@/components/CronScheduleControl.vue'
import { sitesApi } from '@/api/sites'
import { useSite } from '@/composables/useSite'
import { openTaskDetailPage } from '@/utils/taskRoute'

const props = defineProps({ siteName: { type: String, required: true } })
const router = useRouter()

const { backups, backupsLoading, backupsHasMore, backupsLimit, loadBackups, loadMoreBackups, setBackupsPageLength } =
  useSite(props.siteName)

const footerOptions = computed(() => ({
  rowCount: backups.value.length,
  // ListFooter shows "Load More" only when rowCount < totalCount; we don't know
  // the true total (S3 metadata is read lazily), so nudge it past rowCount
  // whenever the backend signals there may be another page.
  totalCount: backupsHasMore.value ? backups.value.length + 1 : backups.value.length,
  pageLengthOptions: [20, 50, 100],
}))

const backingUp = ref(false)
const error = ref('')

const scheduleRef = ref(null)
const nextHint = computed(() => scheduleRef.value?.currentScheduleLabel?.toLowerCase() ?? '')

const fetchSchedule = () => sitesApi.backups.schedule.get(props.siteName)
const setSchedule = (cron) => sitesApi.backups.schedule.set(props.siteName, cron)
const removeSchedule = () => sitesApi.backups.schedule.remove(props.siteName)

async function backupNow() {
  backingUp.value = true
  error.value = ''
  try {
    const result = await sitesApi.backups.create(props.siteName)
    if (result.ok) openTaskDetailPage(router, result.task_id)
    else error.value = result.error || 'Backup failed.'
  } catch (e) {
    error.value = e.message || 'Backup failed.'
  } finally {
    backingUp.value = false
  }
}

const columns = [
  { label: 'Date', key: 'timestamp', align: 'left', width: 2 },
  { label: 'Database', key: 'database', align: 'center', width: 1 },
  { label: 'Public', key: 'public', align: 'center', width: 1 },
  { label: 'Private', key: 'private', align: 'center', width: 1 },
  { label: 'Offsite', key: 'offsite', align: 'center', width: 1 },
  { label: '', key: 'actions', align: 'right', width: '3rem' },
]

const fmt = (iso) => new Date(iso).toLocaleString()
const fileOf = (set, kind) => set.files?.find((f) => f.kind === kind) ?? null
const fmtSize = (b) => !b ? '—' : b < 1024 ** 2 ? `${(b / 1024).toFixed(1)} KB` : `${(b / 1024 ** 2).toFixed(1)} MB`

const rows = computed(() => backups.value.map((set) => ({
  name: set.created_at,
  timestamp: fmt(set.created_at),
  database: fmtSize(fileOf(set, 'database')?.size_bytes),
  public: fmtSize(fileOf(set, 'public-file')?.size_bytes),
  private: fmtSize(fileOf(set, 'private-file')?.size_bytes),
  set,
})))

function menuOptions(set) {
  const kinds = [
    ['database', 'Download Database'],
    ['public-file', 'Download Public'],
    ['private-file', 'Download Private'],
    ['site_config', 'Download Config'],
  ]
  return [
    // Remote-only files have no local path; there's nothing to serve for download for now.
    ...kinds.filter(([k]) => fileOf(set, k)?.path).map(([k, label]) => ({
      label, icon: 'lucide-download',
      onClick: () => { window.location.href = sitesApi.backups.download(props.siteName, fileOf(set, k).filename) },
    })),
    { label: 'Delete backup', icon: 'lucide-trash-2', theme: 'red', onClick: () => { deleteTarget.value = set; showDelete.value = true } },
  ]
}

const showDelete = ref(false)
const deleteTarget = ref(null)
const deleting = ref(false)
const deleteError = ref('')

async function confirmDelete() {
  deleting.value = true
  deleteError.value = ''
  try {
    const filenames = deleteTarget.value.files.map((f) => f.filename)
    const res = await fetch('/api/tasks/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ command: 'delete-backup', site: props.siteName, filenames }),
    })
    const data = await res.json()
    if (data.ok) {
      showDelete.value = false
      openTaskDetailPage(router, data.task_id)
    } else deleteError.value = data.error || 'Delete failed.'
  } catch (e) {
    deleteError.value = e.message || 'Delete failed.'
  } finally {
    deleting.value = false
  }
}

onMounted(() => { loadBackups() })
</script>
