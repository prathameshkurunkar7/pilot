<template>
  <UpdatesAvailableButton />

  <div class="mx-auto max-w-3xl">
    <!-- Header -->
    <div class="flex justify-between items-center">
      <h1 class="font-medium text-ink-gray-8 text-base">
        Your sites <span class="font-normal text-ink-gray-5">({{ filteredSites.length }})</span>
      </h1>
    </div>

    <!-- Bar -->
    <div class="flex items-center gap-2 mt-4">
      <!-- Search text bar -->
      <FormControl v-model="search" type="text" placeholder="Search" class="flex-1">
        <template #prefix>
          <span class="size-4 text-ink-gray-5 lucide-search" />
        </template>
      </FormControl>
      <!-- Status filter -->
      <FormControl v-model="statusFilter" type="select" :options="statusOptions" class="w-32" />
      <!-- List view type -->
      <TabButtons v-model="view" :options="viewOptions" />
    </div>

    <div v-if="loading" class="flex justify-center mt-16">
      <LoadingText />
    </div>
    <div v-else-if="error" class="mt-16">
      <ErrorMessage :message="error" />
    </div>

    <div v-else-if="filteredSites.length" class="mt-4">
      <!-- Grid view -->
      <div v-if="view === 'grid'" class="gap-3 grid grid-cols-1 md:grid-cols-2">
        <!-- Site Card -->
        <div v-for="site in filteredSites" :key="site.name"
          class="flex items-start gap-3 bg-surface-elevation-1 hover:bg-surface-gray-1 p-4 border rounded-xl border-outline-gray-2 hover:border-outline-gray-3 transition-colors">
          <RouterLink :to="{ name: 'SiteDetail', params: { name: site.name } }"
            class="flex flex-1 items-start gap-3 min-w-0 no-underline">
            <!-- Icon -->
            <div
              class="place-items-center grid bg-surface-elevation-1 border rounded-lg border-outline-gray-2 size-8 text-ink-gray-6 shrink-0">
              <span class="size-4 lucide-globe"></span>
            </div>
            <div class="flex-1 min-w-0">
              <!-- First Line -->
              <div class="gap-2 grid grid-cols-[3fr_1fr]">
                <div class="flex items-center gap-1.5 min-w-0">
                  <!-- Site Name -->
                  <span class="font-semibold text-ink-gray-9 text-base truncate">
                    {{ site.name }}
                  </span>

                  <!-- Status -->
                  <span class="rounded-full size-1.5 shrink-0" :class="statusDot(site)" />

                  <span class="text-ink-gray-5 text-p-sm shrink-0">
                    {{ statusLabel(site) }}
                  </span>
                </div>

                <div class="flex justify-end">
                  <!-- Actions Dropdown -->
                  <Dropdown :options="siteMenuOptions(site)" placement="bottom-end">
                    <template #default="{ open }">
                      <Button variant="ghost" size="xs" class="!px-1.5">
                        <span class="size-4 lucide-more-horizontal" />
                      </Button>
                    </template>
                  </Dropdown>
                </div>
              </div>

              <!-- Second Line -->
              <p class="mt-1 text-ink-gray-5 text-p-sm">
                {{ site.installed_apps?.length || 0 }} apps
              </p>
            </div>
          </RouterLink>
        </div>
      </div>

      <!-- List view -->
      <ListView v-else :columns="listColumns" :rows="listRows" row-key="name"
        :options="{ selectable: false, showTooltip: false }">
        <template #cell="{ column, row, item }">
          <div v-if="column.key === 'site'" class="flex items-center gap-3">
            <!-- Icon -->
            <div
              class="place-items-center grid bg-surface-elevation-1 border rounded-lg border-outline-gray-2 size-8 text-ink-gray-6 shrink-0">
              <span class="size-4 lucide-globe" />
            </div>
            <RouterLink :to="{ name: 'SiteDetail', params: { name: row.site.name } }"
              class="font-medium text-ink-gray-9 text-sm no-underline truncate">
              {{ row.site.name }}
            </RouterLink>
          </div>
          <div v-else-if="column.key === 'status'" class="flex items-center gap-2">
            <span class="rounded-full size-1.5" :class="statusDot(row.site)" />
            <span class="text-ink-gray-6 text-sm">{{ statusLabel(row.site) }}</span>
          </div>
          <div v-else-if="column.key === 'apps'" class="text-ink-gray-6 text-sm">
            {{ item }}
          </div>
          <div v-else-if="column.key === 'actions'" class="flex justify-end">
            <Dropdown :options="siteMenuOptions(row.site)" placement="bottom-end">
              <template #default="{ open }">
                <Button variant="ghost" size="sm" :active="open">
                  <span class="size-4 lucide-more-vertical" />
                </Button>
              </template>
            </Dropdown>
          </div>
        </template>
      </ListView>
    </div>

    <!-- No s -->
    <p v-else class="mt-16 text-ink-gray-5 text-sm text-center">No sites found.</p>
  </div>

  <!-- New Site Button -->
  <Teleport defer to="#header-actions">
    <Button variant="solid" @click="showCreate = true">
      <template #prefix>
        <span class="size-4 lucide-plus" />
      </template>
      New site
    </Button>
  </Teleport>

  <NewSiteDialog v-model="showCreate" :sites="sites" @created="(name) => router.push({ name: 'SiteDetail', params: { name } })" />
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  Button,
  Dropdown,
  FormControl,
  ListView,
  LoadingText,
  TabButtons,
} from 'frappe-ui'
import NewSiteDialog from '@/components/NewSiteDialog.vue'
import UpdatesAvailableButton from '@/components/UpdatesAvailableButton.vue'
import { useBreadcrumbs } from '@/composables/useBreadcrumbs'
import { useSites } from '@/composables/useSites'
import { sitesApi } from '@/api/sites'

const router = useRouter()
const { setBreadcrumbs } = useBreadcrumbs()
const { sites, loading, error, load } = useSites()

setBreadcrumbs([{ label: 'Sites', route: { name: 'Sites' } }])

const search = ref('')
const statusFilter = ref('all')
const view = ref('grid')

const viewOptions = [
  { value: 'grid', icon: 'lucide-layout-grid' },
  { value: 'list', icon: 'lucide-list' },
]

const SITE_STATUS = {
  online: { label: 'Active', dot: 'bg-[var(--ink-green-7)]' },
  broken: { label: 'Broken', dot: 'bg-[var(--ink-green-7)]' },
  offline: { label: 'Paused', dot: 'bg-[var(--ink-amber-5)]' },
}

const statusOptions = [
  { label: 'Status', value: 'all' },
  { label: 'Active', value: 'online' },
  { label: 'Broken', value: 'broken' },
  { label: 'Paused', value: 'offline' },
]

function siteStatus(site) {
  if (!site.exists) return 'offline'
  if (site.broken) return 'broken'
  return 'online'
}

const statusLabel = (site) => SITE_STATUS[siteStatus(site)].label
const statusDot = (site) => SITE_STATUS[siteStatus(site)].dot

const filteredSites = computed(() => {
  const query = search.value.toLowerCase().trim()
  return sites.value.filter((site) => {
    const matchesSearch = !query || site.name.toLowerCase().includes(query)
    const matchesStatus = statusFilter.value === 'all' || siteStatus(site) === statusFilter.value
    return matchesSearch && matchesStatus
  })
})

const listColumns = [
  { label: 'Site', key: 'site', align: 'left', width: 3 },
  { label: 'Status', key: 'status', align: 'left', width: 1.5 },
  { label: 'Apps', key: 'apps', align: 'left', width: 1.5 },
  { label: '', key: 'actions', align: 'right', width: '3rem' },
]

const listRows = computed(() =>
  filteredSites.value.map((site) => ({
    name: site.name,
    site,
    apps: `${site.installed_apps?.length || 0} apps`,
  })),
)

function siteMenuOptions(site) {
  return [
    {
      label: 'Open site',
      icon: 'lucide-external-link',
      onClick: async () => {
        const { url } = await sitesApi.login(site.name)
        if (url) window.open(url, '_blank')
      },
    },
    {
      label: 'Back up now',
      icon: 'lucide-database-backup',
      onClick: () => sitesApi.backup(site.name),
    },
  ]
}

const showCreate = ref(false)

onMounted(load)
</script>
