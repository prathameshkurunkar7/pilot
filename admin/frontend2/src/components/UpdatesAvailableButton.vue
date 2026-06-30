<template>
  <Teleport v-if="teleport" defer to="#header-actions">
    <Button variant="solid" @click="showDialog = true">
      <template #prefix>
        <span class="lucide-circle-arrow-up size-4" />
      </template>
      Updates available
    </Button>
  </Teleport>
  <Button v-else variant="outline" @click="showDialog = true">
    <template #prefix>
      <span class="lucide-circle-arrow-up size-4" />
    </template>
    Updates available
  </Button>

  <Dialog v-model="showDialog" :options="{ title: 'Bench Update', size: 'md' }">
    <template #body-content>
      <p class="text-sm text-ink-gray-6">
        App updates will be listed here. This is a placeholder for now.
      </p>
      <div class="mt-5 flex justify-end gap-2 border-t border-outline-gray-1 pt-4">
        <Button variant="ghost" @click="showDialog = false">Not Now</Button>
        <Button variant="solid" @click="showDialog = false">Update Now</Button>
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { ref } from 'vue'
import { Button, Dialog } from 'frappe-ui'

defineProps({
  teleport: { type: Boolean, default: true },
})

const showDialog = ref(false)
</script>
