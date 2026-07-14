<template>
  <div v-if="loading" class="flex justify-center items-center h-40">
    <span class="size-5 text-ink-gray-4 animate-spin lucide-loader-circle"></span>
  </div>
  <div v-else class="space-y-6">
    <Alert theme="blue" title="How retention works" :dismissible="false">
      <template #description>
        <p class="text-ink-gray-6 text-p-sm">
          Old backups are pruned automatically after every backup. FIFO keeps the newest N runs;
          GFS keeps recent daily, weekly, monthly and yearly backups. The most recent backup is always kept.
        </p>
      </template>
    </Alert>

    <div class="space-y-4">
      <Select label="Retention scheme" v-model="scheme" :options="schemeOptions" class="w-full" />

      <FormControl v-if="scheme === 'fifo'" label="Backups to keep" type="number" min="0"
        v-model.number="keepLast" />

      <div v-else class="gap-4 grid grid-cols-2">
        <FormControl label="Daily" type="number" min="0" v-model.number="keepDaily" />
        <FormControl label="Weekly" type="number" min="0" v-model.number="keepWeekly" />
        <FormControl label="Monthly" type="number" min="0" v-model.number="keepMonthly" />
        <FormControl label="Yearly" type="number" min="0" v-model.number="keepYearly" />
      </div>

      <ErrorMessage v-if="error" :message="error" />
      <div class="flex justify-end">
        <Button variant="solid" :loading="saving" @click="save">Save</Button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { Alert, Button, ErrorMessage, FormControl, Select, toast } from 'frappe-ui'
import { settingsApi } from '@/api/settings'

const loading = ref(true)
const saving = ref(false)
const error = ref('')
const scheme = ref('gfs')
const keepLast = ref(7)
const keepDaily = ref(7)
const keepWeekly = ref(4)
const keepMonthly = ref(6)
const keepYearly = ref(1)

const schemeOptions = [
  { label: 'GFS (daily / weekly / monthly / yearly)', value: 'gfs' },
  { label: 'FIFO (keep newest N)', value: 'fifo' },
]

async function load() {
  loading.value = true
  try {
    const data = await settingsApi.get()
    const b = data.backup || {}
    scheme.value = b.scheme || 'gfs'
    keepLast.value = b.keep_last ?? 7
    keepDaily.value = b.keep_daily ?? 7
    keepWeekly.value = b.keep_weekly ?? 4
    keepMonthly.value = b.keep_monthly ?? 6
    keepYearly.value = b.keep_yearly ?? 1
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  error.value = ''
  try {
    const result = await settingsApi.update({
      backup: {
        scheme: scheme.value,
        keep_last: keepLast.value,
        keep_daily: keepDaily.value,
        keep_weekly: keepWeekly.value,
        keep_monthly: keepMonthly.value,
        keep_yearly: keepYearly.value,
      },
    })
    if (result.ok) {
      toast.success('Backup retention saved')
      await load()
    } else {
      error.value = result.error || 'Could not save backup settings.'
    }
  } catch (e) {
    error.value = e.message || 'Could not save backup settings.'
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>
