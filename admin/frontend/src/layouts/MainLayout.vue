<script setup lang='ts'>
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import {
  Breadcrumbs,
  BottomSheet,
  DesktopShell,
  MobileShell,
  PageHeader,
  MobileNav,
  MobileNavItem,
} from 'frappe-ui'
import Sidebar from '@/components/navigation/Sidebar.vue'
import PilotLogo from '@/components/common/PilotLogo.vue'
import MigrationStatusButton from '@/components/common/MigrationStatusButton.vue'
import { useBreadcrumbs } from '@/composables/common/useBreadcrumbs'
import { useIsMobile } from '@/composables/common/useIsMobile'

const route = useRoute()
const { items, resetBreadcrumbs } = useBreadcrumbs()
const isMobile = useIsMobile()

const mobileNavDrawer = ref(false)

watch(
  () => route.name,
  () => {
    resetBreadcrumbs()
    mobileNavDrawer.value = false
  },
)

const breadcrumbs = computed(() => {
  const all = items.value || breadcrumbsFromRouteMeta(route.meta)
  return isMobile.value ? all.slice(-1) : all
})

function breadcrumbsFromRouteMeta({ title = '', group }) {
  return group ? [{ label: group }, { label: title }] : [{ label: title }]
}
</script>

<template>
  <MobileShell v-if="isMobile">
    <PageHeader>
      <template v-if="route.name == 'Home'">
        <PilotLogo class="size-6 rounded-sm" />
        <span class="flex-1 text-center text-ink-gray-9">Home</span>
      </template>

      <button v-else class="flex items-center gap-1" @click="mobileNavDrawer = true">
        <Breadcrumbs :items="breadcrumbs" />
        <lucide-chevron-down class="size-4 text-ink-gray-5" />
      </button>

         <div id="header-badge" class="flex items-center" />
        <div id="header-actions" class="flex items-center gap-2 ml-auto">
          <MigrationStatusButton />
        </div>
    </PageHeader>

    <main class="p-3">
      <slot />
    </main>

    <template #nav>
     <MobileNav class='!bg-surface-base'>
      <MobileNavItem label="Home" icon="lucide-house" to="/home" />
      <MobileNavItem label="Search" icon="lucide-search"  />
      <MobileNavItem label="Notifications" icon="lucide-bell"  />
      <MobileNavItem label="Settings" icon="lucide-settings" to="/settings" />
  </MobileNav>

    </template>

    <BottomSheet v-model:open="mobileNavDrawer">
      <div class="px-4 pb-6">
        <Sidebar is-mobile />
      </div>
    </BottomSheet>
  </MobileShell>

  <DesktopShell v-else class="h-screen">
    <template #sidebar>
      <Sidebar />
    </template>

    <PageHeader>
      <div class="flex flex-1 items-center gap-2">
        <Breadcrumbs :items="breadcrumbs" />
        <div id="header-badge" class="flex items-center" />
        <div id="header-actions" class="flex items-center gap-2 ml-auto">
          <MigrationStatusButton />
        </div>
      </div>
    </PageHeader>

    <div class="p-4">
      <slot />
    </div>
  </DesktopShell>

</template>
