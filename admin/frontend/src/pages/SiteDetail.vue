<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Button, Badge, Dialog, FormControl, LoadingText, ErrorMessage, TabButtons } from 'frappe-ui'
import LucideDatabase from '~icons/lucide/database'
import LucideServer from '~icons/lucide/server'

const route = useRoute()
const router = useRouter()
const siteName = route.params.name

const site = ref(null)
const installable = ref([])
const loading = ref(true)
const error = ref('')

const actionLoading = ref('')
const actionError = ref('')

const showInstall = ref(false)
const selectedInstallApp = ref('')
const installLoading = ref(false)
const installError = ref('')

const showDrop = ref(false)
const showUninstall = ref(false)
const uninstallTarget = ref('')

const activeTab = ref('apps')
const tabs = [
  { label: 'Apps', value: 'apps' },
  { label: 'Config', value: 'config' },
  { label: 'Danger Zone', value: 'danger' },
]

const COLORS = ['#4f46e5', '#0891b2', '#059669', '#d97706', '#dc2626', '#7c3aed']
function hashColor(name) {
  let h = 0
  for (const c of name) h = (h * 31 + c.charCodeAt(0)) | 0
  return COLORS[Math.abs(h) % COLORS.length]
}

async function load() {
  try {
    const res = await fetch(`/api/sites/${siteName}`)
    if (!res.ok) throw new Error(`${res.status}`)
    const d = await res.json()
    site.value = d.site
    installable.value = d.installable_apps
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

async function doAction(path, body = {}) {
  actionError.value = ''
  actionLoading.value = path
  try {
    const res = await fetch(`/api/sites/${siteName}/${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    const d = await res.json()
    if (d.ok) router.push(`/tasks/${d.task_id}`)
    else actionError.value = d.error
  } catch (e) {
    actionError.value = e.message
  } finally {
    actionLoading.value = ''
  }
}

async function installApp() {
  if (!selectedInstallApp.value) return
  installLoading.value = true
  installError.value = ''
  try {
    const res = await fetch(`/api/sites/${siteName}/install-app`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ app: selectedInstallApp.value }),
    })
    const d = await res.json()
    if (d.ok) { showInstall.value = false; router.push(`/tasks/${d.task_id}`) }
    else installError.value = d.error
  } catch (e) {
    installError.value = e.message
  } finally {
    installLoading.value = false
  }
}

function confirmUninstall(app) {
  uninstallTarget.value = app
  showUninstall.value = true
}

onMounted(load)
</script>

<template>
  <div class="flex flex-col gap-6">
    <LoadingText v-if="loading" />
    <ErrorMessage v-else-if="error" :message="error" />

    <template v-else-if="site">
      <!-- Site header -->
      <div class="flex items-start justify-between gap-4">
        <div class="flex flex-col gap-1.5">
          <div class="flex items-center gap-2">
            <h1 class="text-2xl font-semibold text-ink-gray-9">{{ siteName }}</h1>
            <Badge
              :label="site.exists ? 'Online' : 'Offline'"
              :theme="site.exists ? 'green' : 'gray'"
            />
          </div>
          <div class="flex items-center gap-4 text-sm text-ink-gray-5">
            <span v-if="site.db_name" class="flex items-center gap-1.5">
              <LucideDatabase class="h-3.5 w-3.5" />
              {{ site.db_name }}
            </span>
            <span v-if="site.db_host" class="flex items-center gap-1.5">
              <LucideServer class="h-3.5 w-3.5" />
              {{ site.db_host }}
            </span>
          </div>
        </div>
        <div class="flex shrink-0 items-center gap-2">
          <Button variant="outline" :loading="actionLoading === 'backup'" @click="doAction('backup')">
            Backup
          </Button>
          <Button v-if="installable.length" variant="solid" @click="showInstall = true">
            Install App
          </Button>
        </div>
      </div>

      <ErrorMessage :message="actionError" />

      <!-- Tabs -->
      <div class="flex flex-col gap-4">
        <TabButtons :buttons="tabs" v-model="activeTab" />

        <!-- Apps -->
        <div v-if="activeTab === 'apps'">
          <div v-if="!site.installed_apps.length" class="py-10 text-center text-sm text-ink-gray-4">
            No apps installed on this site.
          </div>
          <div v-else class="divide-y rounded border">
            <div
              v-for="app in site.installed_apps"
              :key="app"
              class="flex items-center justify-between px-4 py-3"
            >
              <div class="flex items-center gap-3">
                <div
                  class="flex h-8 w-8 shrink-0 items-center justify-center rounded-md"
                  :style="{ background: hashColor(app) }"
                >
                  <span class="text-sm font-bold text-white">{{ app[0].toUpperCase() }}</span>
                </div>
                <span class="text-sm font-medium text-ink-gray-8">{{ app }}</span>
              </div>
              <Button variant="ghost" theme="red" size="sm" @click="confirmUninstall(app)">
                Uninstall
              </Button>
            </div>
          </div>
        </div>

        <!-- Config -->
        <div v-else-if="activeTab === 'config'">
          <div class="rounded border bg-surface-gray-1 p-4">
            <p class="mb-2 text-xs font-medium text-ink-gray-5">site_config.json</p>
            <pre class="overflow-x-auto font-mono text-sm text-ink-gray-8">{{ JSON.stringify(site.site_config, null, 2) }}</pre>
          </div>
        </div>

        <!-- Danger Zone -->
        <div v-else-if="activeTab === 'danger'">
          <div class="rounded border border-red-200 p-4">
            <div class="flex items-center justify-between gap-4">
              <div>
                <p class="text-sm font-medium text-ink-gray-9">Drop Site</p>
                <p class="mt-0.5 text-sm text-ink-gray-5">
                  Permanently delete <strong>{{ siteName }}</strong> and all its data. This cannot be undone.
                </p>
              </div>
              <Button variant="solid" theme="red" class="shrink-0" @click="showDrop = true">
                Drop Site
              </Button>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- Install App dialog -->
    <Dialog v-model="showInstall" :options="{ title: 'Install App' }">
      <template #body-content>
        <FormControl
          label="App to install"
          type="select"
          v-model="selectedInstallApp"
          :options="[{ label: 'Select an app…', value: '' }, ...installable.map(a => ({ label: a, value: a }))]"
        />
        <ErrorMessage :message="installError" class="mt-2" />
        <div class="mt-4 flex justify-end gap-2">
          <Button variant="ghost" @click="showInstall = false">Cancel</Button>
          <Button variant="solid" :loading="installLoading" :disabled="!selectedInstallApp" @click="installApp">Install</Button>
        </div>
      </template>
    </Dialog>

    <!-- Drop Site dialog -->
    <Dialog v-model="showDrop" :options="{ title: 'Drop Site', size: 'sm' }">
      <template #body-content>
        <p class="text-sm text-ink-gray-7">
          Are you sure you want to permanently drop <strong>{{ siteName }}</strong>?
          All data will be lost and this cannot be undone.
        </p>
        <div class="mt-4 flex justify-end gap-2">
          <Button variant="ghost" @click="showDrop = false">Cancel</Button>
          <Button variant="solid" theme="red" :loading="actionLoading === 'drop'"
            @click="showDrop = false; doAction('drop')">Drop Site</Button>
        </div>
      </template>
    </Dialog>

    <!-- Uninstall App dialog -->
    <Dialog v-model="showUninstall" :options="{ title: 'Uninstall App', size: 'sm' }">
      <template #body-content>
        <p class="text-sm text-ink-gray-7">
          Uninstall <strong>{{ uninstallTarget }}</strong> from <strong>{{ siteName }}</strong>?
        </p>
        <div class="mt-4 flex justify-end gap-2">
          <Button variant="ghost" @click="showUninstall = false">Cancel</Button>
          <Button variant="solid" theme="red"
            @click="showUninstall = false; doAction('uninstall-app', { app: uninstallTarget })">Uninstall</Button>
        </div>
      </template>
    </Dialog>
  </div>
</template>
