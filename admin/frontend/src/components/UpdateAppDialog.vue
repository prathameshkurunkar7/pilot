<script setup>
import { ref, watch } from 'vue'
import { Button, Combobox, Dialog, LoadingText } from 'frappe-ui'

const props = defineProps({
  modelValue: Boolean,
  app: { type: Object, default: null },   // {name, branch, commit, ...}
  siteName: { type: String, required: true },
})
const emit = defineEmits(['update:modelValue'])

const show = ref(props.modelValue)
watch(() => props.modelValue, (v) => { show.value = v })
watch(show, (v) => emit('update:modelValue', v))

const commits = ref([])
const commitsLoading = ref(false)
const selectedCommit = ref('')

watch(() => props.modelValue, async (open) => {
  if (!open || !props.app) return
  commits.value = []
  selectedCommit.value = ''
  commitsLoading.value = true
  try {
    const res = await fetch(`/api/sites/${props.siteName}/apps/${props.app.name}/commits`)
    const d = await res.json()
    commits.value = d.commits || []
    if (commits.value.length) selectedCommit.value = commits.value[0].hash
  } catch { /* non-fatal */ }
  finally { commitsLoading.value = false }
})
</script>

<template>
  <Dialog v-model="show" :options="{ title: `Update ${app?.name || ''}`, size: 'md' }">
    <template #body-content>
      <div class="flex flex-col gap-4">
        <LoadingText v-if="commitsLoading" />
        <template v-else>
          <p v-if="!commits.length" class="text-sm text-ink-gray-5">
            No new commits found in the remote tracking branch.
          </p>
          <template v-else>
            <p class="text-sm text-ink-gray-6">
              {{ commits.length }} new commit{{ commits.length > 1 ? 's' : '' }} available on
              <span class="font-mono text-ink-gray-8">{{ app?.branch }}</span>.
            </p>
            <Combobox
              label="Update to commit"
              v-model="selectedCommit"
              :options="commits.map(c => ({
                label: c.hash,
                value: c.hash,
                description: `${c.message} — ${c.author}, ${c.date}`,
              }))"
              :allowCustomValue="true"
              placeholder="Select a commit or paste a hash…"
            />
            <div class="max-h-52 overflow-y-auto rounded-lg border border-outline-gray-1 divide-y divide-outline-gray-1">
              <div
                v-for="c in commits" :key="c.hash"
                class="flex cursor-pointer items-start gap-3 px-3 py-2 transition-colors hover:bg-surface-gray-1"
                :class="selectedCommit === c.hash && 'bg-surface-gray-1'"
                @click="selectedCommit = c.hash"
              >
                <span class="shrink-0 pt-0.5 font-mono text-xs text-ink-gray-5">{{ c.hash }}</span>
                <div class="min-w-0 flex-1">
                  <p class="truncate text-sm text-ink-gray-8">{{ c.message }}</p>
                  <p class="text-xs text-ink-gray-4">{{ c.author }} · {{ c.date }}</p>
                </div>
              </div>
            </div>
          </template>
          <div class="flex justify-end gap-2">
            <Button variant="ghost" @click="show = false">Cancel</Button>
            <Button variant="solid" :disabled="!selectedCommit">Update</Button>
          </div>
        </template>
      </div>
    </template>
  </Dialog>
</template>
