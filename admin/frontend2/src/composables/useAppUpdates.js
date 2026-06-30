import { ref } from 'vue'
import { appsApi } from '@/api/apps'
import { tasksApi } from '@/api/tasks'

const updatesAvailable = ref(false)
const checking = ref(false)
const checked = ref(false)

const POLL_INTERVAL_MS = 1500

export function useAppUpdates() {
  async function check() {
    if (checking.value) return

    checking.value = true
    try {
      const { task_id } = await appsApi.fetchUpdates()
      while (true) {
        await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS))
        const { task, output } = await tasksApi.detail(task_id)

        if (task.status === 'running') continue
        if (task.status === 'success' && output?.length) {
          const result = JSON.parse(output[output.length - 1])
          updatesAvailable.value = Object.values(result).some(Boolean)
        }
        break
      }
    } catch {
      // Best-effort update check; failures should not block the UI.
    } finally {
      checking.value = false
      checked.value = true
    }
  }

  return {
    updatesAvailable,
    checking,
    checked,
    check,
  }
}
