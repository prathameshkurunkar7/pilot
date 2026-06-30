<template>
  <div
    class="grid size-10 shrink-0 place-items-center overflow-hidden rounded-lg"
    :style="logoUrl ? {} : { background: hashColor(name) }"
  >
    <img
      v-if="logoUrl"
      :src="logoUrl"
      :alt="name"
      class="size-full object-contain"
      @error="hasError = true"
    />
    <span v-else class="text-sm font-bold text-white">
      {{ initial }}
    </span>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useAppRegistry } from '@/composables/useAppRegistry'

const props = defineProps({
  name: { type: String, required: true },
})

const { logoMap, hashColor } = useAppRegistry()
const hasError = ref(false)

const logoUrl = computed(() => (hasError.value ? null : logoMap.value[props.name]))
const initial = computed(() => props.name[0]?.toUpperCase() || '')
</script>
