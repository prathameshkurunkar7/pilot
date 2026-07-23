<template>
  <div v-if="loading" class="flex justify-center items-center h-40">
    <span class="size-5 text-ink-gray-4 animate-spin lucide-loader-circle"></span>
  </div>
  <div v-else class="space-y-6">
    <Alert v-if="!connected" theme="blue" title="Why connect an AI assistant?" :dismissible="false">
      <template #description>
        <p class="text-ink-gray-6 text-p-sm">
          Connect an AI provider to power assistant features on this bench, like explaining
          migration and task errors from the logs.
        </p>
      </template>
    </Alert>

    <div v-if="connected" class="flex sm:flex-row flex-col sm:justify-between sm:items-center gap-3">
      <div>
        <p class="font-medium text-ink-gray-8 text-sm">Connected to {{ providerLabel }}</p>
        <p class="text-ink-gray-5 text-p-sm">Model {{ model || defaultModel || 'default' }} · API key set</p>
      </div>
      <Button class="flex-1 sm:flex-none" variant="subtle" theme="red" :loading="disconnecting"
        @click="disconnect">Disconnect</Button>
    </div>

    <div class="space-y-4">
      <div class="flex sm:flex-row flex-col gap-4">
        <Select label="Provider" v-model="provider" :options="providerOptions" class="w-full" />
        <FormControl label="Model" type="text" v-model="model" :placeholder="defaultModel || 'default model'"
          class="w-full" />
      </div>
      <FormControl v-if="selfHosted" label="API Base URL" type="text" v-model="apiBase"
        placeholder="http://your-host:8000/v1" />
      <FormControl label="API Key" type="password" v-model="apiKey"
        :placeholder="apiKeySet ? '••••••••' : 'Provider API key'" />
      <FormControl label="Max Tokens" type="number" v-model="maxTokens" placeholder="4096" class="w-full" />
      <FormControl label="System Prompt" type="textarea" v-model="systemPrompt" :rows="6"
        placeholder="Instructions sent with every request" />
      <ErrorMessage v-if="error" :message="error" />
      <div class="flex justify-end">
        <Button variant="solid" :loading="saving" @click="save">
          {{ connected ? 'Update' : 'Connect' }}
        </Button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { Alert, Button, ErrorMessage, FormControl, Select, toast } from 'frappe-ui'
import { apiErrorMessage } from '@/api/client'
import { settingsApi } from '@/api/settings'

const loading = ref(true)
const saving = ref(false)
const disconnecting = ref(false)
const error = ref('')
const provider = ref('')
const apiKey = ref('')
const model = ref('')
const maxTokens = ref(4096)
const systemPrompt = ref('')
const apiBase = ref('')
const apiKeySet = ref(false)
const providers = ref([])

const connected = computed(() => Boolean(provider.value && apiKeySet.value))
const selectedProvider = computed(() => providers.value.find((p) => p.value === provider.value))
const providerLabel = computed(() => selectedProvider.value?.label || provider.value)
const providerOptions = computed(() => providers.value.map((p) => ({ label: p.label, value: p.value })))
const defaultModel = computed(() => selectedProvider.value?.default_model || '')
const selfHosted = computed(() => Boolean(selectedProvider.value?.self_hosted))

async function load() {
  loading.value = true
  try {
    const data = await settingsApi.get()
    providers.value = data.llm_providers || []
    const llm = data.llm || {}
    provider.value = llm.provider || providers.value[0]?.value || ''
    model.value = llm.model || ''
    maxTokens.value = llm.max_tokens || 4096
    systemPrompt.value = llm.system_prompt || ''
    apiBase.value = llm.api_base || ''
    apiKeySet.value = !!llm.api_key_set
  } finally {
    loading.value = false
  }
}

async function save() {
  if (!provider.value) {
    error.value = 'Provider is required.'
    return
  }
  if (selfHosted.value && !apiBase.value.trim()) {
    error.value = 'API base URL is required for a self-hosted provider.'
    return
  }
  if (!apiKeySet.value && !apiKey.value.trim()) {
    error.value = 'API key is required.'
    return
  }
  saving.value = true
  error.value = ''
  try {
    const result = await settingsApi.update({
      llm: {
        provider: provider.value,
        api_key: apiKey.value.trim(),
        model: model.value.trim(),
        max_tokens: Number(maxTokens.value) || 4096,
        api_base: apiBase.value.trim(),
        system_prompt: systemPrompt.value,
      },
    })
    if (!result.error) {
      apiKey.value = ''
      toast.success('AI assistant settings saved')
      await load()
    } else {
      error.value = apiErrorMessage(result, 'Could not save AI assistant settings.')
    }
  } catch (e) {
    error.value = e.message || 'Could not save AI assistant settings.'
  } finally {
    saving.value = false
  }
}

async function disconnect() {
  disconnecting.value = true
  try {
    const result = await settingsApi.update({ llm: { disconnect: true } })
    if (!result.error) {
      apiKey.value = ''
      model.value = ''
      maxTokens.value = 4096
      systemPrompt.value = ''
      apiBase.value = ''
      apiKeySet.value = false
      provider.value = providers.value[0]?.value || ''
      toast.success('AI assistant disconnected')
    } else {
      toast.error(apiErrorMessage(result, 'Could not disconnect the AI assistant.'))
    }
  } catch (e) {
    toast.error(e.message || 'Could not disconnect the AI assistant.')
  } finally {
    disconnecting.value = false
  }
}

onMounted(load)
</script>
