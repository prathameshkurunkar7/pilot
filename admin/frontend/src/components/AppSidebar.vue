<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import LucideLayoutDashboard from '~icons/lucide/layout-dashboard'
import LucidePackage2 from '~icons/lucide/package-2'
import LucideGlobe from '~icons/lucide/globe'
import LucideActivity from '~icons/lucide/activity'
import LucideFileText from '~icons/lucide/file-text'
import LucideDatabase from '~icons/lucide/database'
import LucideListTodo from '~icons/lucide/list-todo'

const route = useRoute()
const router = useRouter()

const navItems = [
  { label: 'Dashboard', to: '/', icon: LucideLayoutDashboard },
  { label: 'Apps', to: '/apps', icon: LucidePackage2 },
  { label: 'Sites', to: '/sites', icon: LucideGlobe },
  { label: 'Processes', to: '/processes', icon: LucideActivity },
  { label: 'Logs', to: '/logs', icon: LucideFileText },
  { label: 'Database', to: '/database/binlogs', icon: LucideDatabase },
  { label: 'Tasks', to: '/tasks', icon: LucideListTodo },
]

function isActive(to) {
  if (to === '/') return route.path === '/'
  return route.path.startsWith(to)
}

const runningCount = ref(0)
let pollTimer = null

async function pollRunning() {
  try {
    const res = await fetch('/api/tasks/?status=running')
    if (res.ok) {
      const tasks = await res.json()
      runningCount.value = Array.isArray(tasks) ? tasks.length : 0
    }
  } catch {}
}

onMounted(() => {
  pollRunning()
  pollTimer = setInterval(pollRunning, 4000)
})
onUnmounted(() => clearInterval(pollTimer))
</script>

<template>
  <div class="inline-flex h-full w-56 flex-shrink-0 flex-col overflow-auto border-r bg-surface-menu-bar">
    <div class="px-3 py-3">
      <div class="px-2 py-1.5">
        <span class="text-base font-semibold text-ink-gray-9">Bench</span>
      </div>
    </div>
    <nav class="flex-1 space-y-0.5 px-2">
      <button
        v-for="item in navItems"
        :key="item.to"
        class="relative flex w-full items-center rounded px-2 py-1.5 text-sm text-ink-gray-8 transition"
        :class="isActive(item.to) ? 'bg-surface-selected shadow-sm' : 'hover:bg-surface-gray-2'"
        @click="router.push(item.to)"
      >
        <span class="grid h-5 w-6 place-items-center">
          <component :is="item.icon" class="h-4 w-4 text-ink-gray-7" />
        </span>
        <span class="ml-2">{{ item.label }}</span>
        <span
          v-if="item.to === '/tasks' && runningCount > 0"
          class="ml-auto flex h-4 min-w-[1rem] items-center justify-center rounded-full bg-blue-500 px-1 text-[10px] font-bold text-white"
        >{{ runningCount }}</span>
      </button>
    </nav>
  </div>
</template>
