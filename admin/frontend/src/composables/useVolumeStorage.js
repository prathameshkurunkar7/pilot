import { ref, computed, watch } from 'vue'

const GIB = 1024 ** 3
const CUSTOM_DEVICE = '__custom__'

function deviceLabel(device) {
  const sizeGiB = Math.floor(device.size_bytes / GIB)
  const note = device.pool ? ', in use' : device.has_signature ? ', has data' : ''
  return `${device.path} (${sizeGiB} GB${note})`
}

export function useVolumeStorage(backing, device, imageSize) {
  const availableDevices = ref([])
  const rootfsFreeBytes = ref(0)
  const customDevice = ref(false)

  const deviceOptions = computed(() => [
    ...availableDevices.value.map((d) => ({ label: deviceLabel(d), value: d.path })),
    { label: 'Other disk…', value: CUSTOM_DEVICE },
  ])
  const showDeviceDropdown = computed(
    () => availableDevices.value.length > 0 && !customDevice.value,
  )

  const freeGiB = computed(() => Math.floor(rootfsFreeBytes.value / GIB))
  const imageSizeMaxGiB = computed(() => Math.max(5, freeGiB.value || 100))
  const imageSizeMinGiB = computed(() => Math.min(5, imageSizeMaxGiB.value))
  const imageSizeGiB = computed(() => parseInt(imageSize.value) || imageSizeMinGiB.value)

  function clamp(value) {
    return Math.min(imageSizeMaxGiB.value, Math.max(imageSizeMinGiB.value, value))
  }

  const imageSliderModel = computed({
    get: () => [clamp(imageSizeGiB.value)],
    set: ([value]) => {
      imageSize.value = `${value}G`
    },
  })

  function clampImageSize() {
    imageSize.value = `${clamp(imageSizeGiB.value)}G`
  }

  // The "Other disk…" sentinel switches the picker to a free-text field.
  watch(device, (value) => {
    if (value !== CUSTOM_DEVICE) return
    customDevice.value = true
    device.value = ''
  })

  return {
    availableDevices,
    rootfsFreeBytes,
    deviceOptions,
    showDeviceDropdown,
    freeGiB,
    imageSizeGiB,
    imageSizeMinGiB,
    imageSizeMaxGiB,
    imageSliderModel,
    clampImageSize,
  }
}
