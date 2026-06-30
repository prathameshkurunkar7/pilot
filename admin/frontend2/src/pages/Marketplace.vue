<template>
  <UpdatesAvailableButton />

  <div class="mx-auto max-w-3xl">
    <!-- Header -->
    <div class="flex justify-between items-center">
      <div class="flex flex-col items-start">
        <h1 class="font-semibold text-ink-gray-9 text-xl">Marketplace</h1>
        <p class="mt-1 text-ink-gray-5 text-p-base">
          Apps built by developers worldwide, ready to install on {{ benchName }}'s sites.
        </p>
      </div>
      <div class="h-min" v-if="benchVersionLabel">
        <span
          data-state="closed"
          data-grace-area-trigger=""
          class="inline-flex items-center gap-1.5 bg-surface-gray-1 mt-0.5 px-2.5 py-1 border rounded-full border-outline-gray-2 h-min text-ink-gray-6 text-p-sm shrink-0"
        >
          <span class="size-3.5 lucide-box"></span> {{ benchVersionLabel }}
        </span>
      </div>
    </div>

    <!-- Search -->

    <div class="gap-x-3 grid grid-cols-[8fr_2fr] mt-6">
      <FormControl v-model="search" type="text" placeholder="Search for any app">
        <template #prefix>
          <LucideSearch class="size-4 text-ink-gray-5" />
        </template>
      </FormControl>
      <FormControl v-model="selectedCategory" class="flex-" type="select" :options="categories" />
    </div>

    <!-- Loading -->
    <div v-if="loading || error" class="flex flex-row justify-center items-center w-full h-[250px]">
      <LoadingText v-if="loading" class="mt-8" />
      <ErrorMessage v-else-if="error" :message="error" class="mt-8" />
    </div>

    <!-- Marketplace Apps -->

    <template v-else>
      <section v-if="frappeApps.length" class="mt-6">
        <p class="font-medium text-ink-gray-5 text-xs uppercase tracking-wide">From Frappe</p>
        <div class="gap-x-10 grid grid-cols-1 md:grid-cols-2 mt-2">
          <MarketplaceAppCard
            v-for="app in frappeApps"
            :key="app.name"
            :app="app"
            @install="installApp"
          />
        </div>
      </section>

      <section v-if="communityApps.length" class="mt-8">
        <p class="font-medium text-ink-gray-5 text-xs uppercase tracking-wide">Community</p>
        <div class="gap-x-10 grid grid-cols-1 md:grid-cols-2 mt-2">
          <MarketplaceAppCard
            v-for="app in communityApps"
            :key="app.name"
            :app="app"
            @install="installApp"
          />
        </div>
      </section>

      <p
        v-if="!frappeApps.length && !communityApps.length"
        class="mt-8 text-ink-gray-5 text-sm text-center"
      >
        No apps found.
      </p>

      <p class="mt-10 text-ink-gray-5 text-sm">
        Building your own?
        <Button variant="ghost" class="!px-1 !text-ink-gray-7">Install from GitHub</Button>
      </p>
    </template>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { Button, ErrorMessage, FormControl, LoadingText } from 'frappe-ui'
import LucideBox from '~icons/lucide/box'
import LucideSearch from '~icons/lucide/search'
import MarketplaceAppCard from '@/components/MarketplaceAppCard.vue'
import UpdatesAvailableButton from '@/components/UpdatesAvailableButton.vue'
import { useMarketplace } from '@/composables/useMarketplace'

const {
  loading,
  error,
  search,
  selectedCategory,
  categories,
  benchName,
  benchVersion,
  benchVersionLabel,
  frappeApps,
  communityApps,
  load,
} = useMarketplace()

// Install is a placeholder for now.
function installApp(app) {
  console.log('install', app.name)
}

onMounted(load)
</script>
