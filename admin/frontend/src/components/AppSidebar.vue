<script setup>
import { Sidebar, SidebarItem } from 'frappe-ui'
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import LucideActivity from '~icons/lucide/activity'
import LucideCamera from '~icons/lucide/camera'
import LucideDatabase from '~icons/lucide/database'
import LucideFileText from '~icons/lucide/file-text'
import LucideGlobe from '~icons/lucide/globe'
import LucideListTodo from '~icons/lucide/list-todo'
import LucideLogOut from '~icons/lucide/log-out'
import LucideStore from '~icons/lucide/store'
import LucideSettings from '~icons/lucide/settings'
import LucideRepeat from '~icons/lucide/repeat'

const emit = defineEmits(['logout', 'open-settings', 'change-bench'])

const route = useRoute()

const header = {
  title: 'Bench',
  logo: '/logos/frappe-icon.png',
  menuItems: [
    { label: 'Settings', icon: LucideSettings, onClick: () => emit('open-settings') },
    { label: 'Manage Benches', icon: LucideRepeat, onClick: () => emit('change-bench') },
    { label: 'Logout', icon: LucideLogOut, onClick: () => logout() },
  ],
}

const primaryNavItems = [
  { label: 'Sites', to: '/', icon: LucideGlobe },
  { label: 'Marketplace', to: '/marketplace', icon: LucideStore },
]

const snapshotsEnabled = ref(false)
const runningCount = ref(0)
let pollTimer = null

// The database engine is a bench-wide choice (every site uses it), so show it
// once here rather than per site.
const DB_ENGINES = {
  postgres: { label: 'PostgreSQL', logo: '/logos/postgresql.svg' },
  mariadb: { label: 'MariaDB', logo: '/logos/mariadb.svg' },
}
const dbType = ref('')
const dbEngine = computed(() => DB_ENGINES[dbType.value] || null)

const sections = computed(() => [
  { items: primaryNavItems },
  {
    label: 'System',
    collapsible: true,
    items: [
      { label: 'Monitor', to: '/monitor', icon: LucideActivity },
      { label: 'Logs', to: '/logs', icon: LucideFileText },
      { label: 'Tasks', to: '/tasks', icon: LucideListTodo },
      { label: 'Database', to: '/database', icon: LucideDatabase },
      ...(snapshotsEnabled.value ? [{ label: 'Snapshots', to: '/snapshots', icon: LucideCamera }] : []),
    ],
  },
])

function isActive(to) {
  if (to === '/') return route.path === '/' || route.path.startsWith('/sites')
  return route.path.startsWith(to)
}

async function pollRunning() {
  try {
    const response = await fetch('/api/tasks/?status=running')
    if (response.ok) {
      const tasks = await response.json()
      runningCount.value = Array.isArray(tasks) ? tasks.length : 0
    }
  } catch { }
}

async function loadVolumeConfig() {
  try {
    const response = await fetch('/api/volume/status')
    if (response.ok) {
      const data = await response.json()
      snapshotsEnabled.value = data.enabled === true
    }
  } catch { }
}

async function loadBenchInfo() {
  try {
    const response = await fetch('/api/status')
    if (response.ok) dbType.value = (await response.json()).db_type || ''
  } catch { }
}

async function logout() {
  await fetch('/api/logout', { method: 'POST' })
  emit('logout')
}

onMounted(() => {
  pollRunning()
  loadVolumeConfig()
  loadBenchInfo()
  pollTimer = setInterval(pollRunning, 4000)
})
onUnmounted(() => clearInterval(pollTimer))
</script>

<template>
  <div class="h-full">
    <Sidebar :header="header" :sections="sections" disableCollapse>
      <template #sidebar-item="{ item }">
        <SidebarItem :label="item.label" :icon="item.icon" :to="item.to" :isActive="isActive(item.to)">
          <template v-if="item.to === '/tasks' && runningCount > 0" #suffix>
            <span
              class="flex h-4 min-w-[1rem] items-center justify-center rounded-full bg-ink-gray-8 px-1 text-[10px] font-bold text-surface-white">
              {{ runningCount }}
            </span>
          </template>
        </SidebarItem>
      </template>
      <template #footer-items>
        <div v-if="dbEngine" class="flex items-center gap-2 px-2 py-1.5 text-xs text-ink-gray-6">
          <span class="flex h-5 w-5 shrink-0 items-center justify-center rounded bg-white p-0.5 ring-1 ring-black/5">
            <img :src="dbEngine.logo" :alt="dbEngine.label" class="h-full w-full object-contain" />
          </span>
          <span class="truncate">{{ dbEngine.label }}</span>
        </div>
      </template>
    </Sidebar>
  </div>
</template>
