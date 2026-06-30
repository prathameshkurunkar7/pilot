<template>
  <FrappeUIProvider>
    <ReconnectOverlay />
    <RouterView v-if="isSetupRoute" />
    <MainLayout v-else>
      <RouterView />
    </MainLayout>
  </FrappeUIProvider>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useTheme, FrappeUIProvider } from 'frappe-ui'
import ReconnectOverlay from './components/ReconnectOverlay.vue'
import MainLayout from './layouts/MainLayout.vue'

const route = useRoute()
const isSetupRoute = computed(() => route.name === 'Setup')
const { initializeTheme } = useTheme()

initializeTheme()
</script>
