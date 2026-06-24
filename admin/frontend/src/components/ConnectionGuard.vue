<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { LoadingIndicator } from 'frappe-ui'


const down = ref(false)
let timer = null
let stopped = false

async function pingOk(url) {
  try {
    const res = await fetch(url, { cache: 'no-store' })
    return res.status === 200
  } catch {
    return false
  }
}

async function tick() {
  if (stopped) return
  if (!down.value) {
    down.value = !(await pingOk(`${window.location.origin}/api/ping`))
  } else {
    const host = window.location.hostname
    const [httpsOk, httpOk] = await Promise.all([
      pingOk(`https://${host}/api/ping`),
      pingOk(`http://${host}/api/ping`),
    ])
    const scheme = httpsOk ? 'https' : httpOk ? 'http' : null
    if (scheme) {
      window.location.href = `${scheme}://${host}${window.location.pathname}${window.location.search}`
      return
    }
  }
  if (!stopped) timer = setTimeout(tick, down.value ? 1500 : 3000)
}

onMounted(tick)
onBeforeUnmount(() => {
  stopped = true
  clearTimeout(timer)
})
</script>

<template>
  <div v-if="down" class="fixed inset-0 z-[9999] flex items-center justify-center gap-3 bg-surface-white">
    <LoadingIndicator class="h-6 w-6 text-ink-gray-5" />
    <p class="text-xl text-ink-gray-7">Reconnecting to bench</p>
  </div>
</template>
