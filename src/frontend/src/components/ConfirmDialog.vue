<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref } from 'vue'
import { X } from 'lucide-vue-next'
defineProps<{ title: string; description: string; confirmLabel: string; busy?: boolean; error?: string }>()
const emit = defineEmits<{ close: []; confirm: [] }>()
const dialog = ref<HTMLDialogElement>(), cancel = ref<HTMLButtonElement>()
let previous: HTMLElement | null = null
onMounted(async () => { previous = document.activeElement as HTMLElement; dialog.value?.showModal(); await nextTick(); cancel.value?.focus() })
onUnmounted(() => previous?.focus())
</script>
<template>
  <Teleport to="body"><dialog ref="dialog" class="confirm-dialog" aria-labelledby="confirm-title" aria-describedby="confirm-description" @cancel.prevent="!busy && emit('close')" @click.self="!busy && emit('close')"><button class="icon-button dialog-close" aria-label="关闭确认窗口" :disabled="busy" @click="emit('close')"><X :size="18" /></button><p class="eyebrow">A MOMENT TO PAUSE</p><h2 id="confirm-title">{{ title }}</h2><p id="confirm-description">{{ description }}</p><p v-if="error" class="error-message" role="alert">{{ error }}</p><div class="dialog-actions"><button ref="cancel" class="button secondary" :disabled="busy" @click="emit('close')">再想一下</button><button class="button primary" :disabled="busy" @click="emit('confirm')">{{ busy ? '正在处理…' : confirmLabel }}</button></div></dialog></Teleport>
</template>
