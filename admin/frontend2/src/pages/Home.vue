<script setup>
import { useBreadcrumbs } from '@/composables/useBreadcrumbs'

const { setBreadcrumbs } = useBreadcrumbs()

setBreadcrumbs([{ label: 'Sites', route: { name: 'Sites' } }])
</script>

<template>
  <p class="text-ink-gray-6">Sites page</p>
</template>
