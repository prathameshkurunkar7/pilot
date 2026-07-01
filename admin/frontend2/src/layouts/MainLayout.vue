<script setup>
import { computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { Breadcrumbs } from 'frappe-ui'
import AppSidebar from '@/components/AppSidebar.vue'
import { useBreadcrumbs } from '@/composables/useBreadcrumbs'

const route = useRoute()
const { items, resetBreadcrumbs } = useBreadcrumbs()

watch(() => route.name, resetBreadcrumbs)

const breadcrumbs = computed(() => {
  if (items.value) return items.value
  const { title = '', group } = route.meta
  return group ? [{ label: group }, { label: title }] : [{ label: title }]
})
</script>

<template>
  <div class="flex h-screen overflow-hidden bg-surface-elevation-1">
    <AppSidebar />
    <main class="flex flex-1 flex-col overflow-hidden">
      <header
        class="sticky top-0 z-10 flex shrink-0 items-center gap-2 border-b border-outline-alpha-gray-1 px-5 py-2.5"
      >
        <Breadcrumbs :items="breadcrumbs" />
        <div id="header-actions" class="ml-auto flex items-center gap-2" />
      </header>
      <div class="min-h-0 flex-1 overflow-auto p-4 sm:p-6">
        <slot />
      </div>
    </main>
  </div>
</template>
