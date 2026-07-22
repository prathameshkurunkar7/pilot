<template>
  <div class="bg-surface-white border rounded-lg border-outline-gray-2">
    <div class="flex justify-between items-start gap-3 p-4">
      <div class="min-w-0">
        <div class="flex items-center gap-2">
          <h3 class="font-semibold text-ink-gray-9 text-base">{{ title }}</h3>
          <Badge v-if="badge" :label="badge" theme="gray" size="sm" />
        </div>
        <p v-if="subtitle" class="mt-0.5 text-ink-gray-5 text-sm">{{ subtitle }}</p>
      </div>
      <div class="flex items-center gap-3 shrink-0">
        <Switch v-if="showAutoRefresh" label="Auto Refresh" size="sm" :model-value="autoRefresh"
          @update:model-value="$emit('update:autoRefresh', $event)" />
        <Button variant="subtle" size="sm" iconLeft="lucide-refresh-cw" :loading="loading"
          @click="$emit('refresh')">
          Refresh
        </Button>
      </div>
    </div>
    <div class="border-t border-outline-gray-2">
      <slot />
    </div>
  </div>
</template>

<script setup>
import { Badge, Button, Switch } from 'frappe-ui'

defineProps({
  title: { type: String, required: true },
  subtitle: { type: String, default: '' },
  badge: { type: String, default: '' },
  loading: { type: Boolean, default: false },
  showAutoRefresh: { type: Boolean, default: false },
  autoRefresh: { type: Boolean, default: false },
})

defineEmits(['refresh', 'update:autoRefresh'])
</script>
