<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue'
import { FileText, FolderOpen, RefreshCw, X } from 'lucide-vue-next'
import { listInterviewPresets, loadInterviewPreset } from '../api/presets'
import type { InterviewPreset } from '../api/presets'

const props = defineProps<{ disabled: boolean }>()
const emit = defineEmits<{ select: [preset: InterviewPreset, filename: string]; loading: [value: boolean] }>()
const dialog = ref<HTMLDialogElement | null>(null)
const files = ref<string[]>([])
const loading = ref(false)
const reading = ref('')
const error = ref('')
let request: AbortController | undefined
let previousOverflow: string | undefined

function cleanup() {
  request?.abort()
  request = undefined
  loading.value = false
  reading.value = ''
  emit('loading', false)
  if (previousOverflow !== undefined) {
    document.body.style.overflow = previousOverflow
    previousOverflow = undefined
  }
}

function close() {
  // POST 已开始更新后端 state，不能把关闭窗口误当作撤销。
  if (reading.value) return
  cleanup()
  dialog.value?.close()
}

async function refresh() {
  if (reading.value) return
  request?.abort()
  const active = new AbortController()
  request = active
  loading.value = true
  reading.value = ''
  error.value = ''
  files.value = []
  try {
    const result = await listInterviewPresets(active.signal)
    if (request === active) files.value = result
  } catch (cause) {
    if (request === active) error.value = cause instanceof Error ? cause.message : '无法读取预设列表。'
  } finally {
    if (request === active) loading.value = false
  }
}

function open() {
  if (props.disabled || !dialog.value || dialog.value.open) return
  previousOverflow = document.body.style.overflow
  document.body.style.overflow = 'hidden'
  dialog.value.showModal()
  void refresh()
}

async function choose(filename: string) {
  if (props.disabled || reading.value || loading.value) return
  const active = new AbortController()
  request?.abort()
  request = active
  reading.value = filename
  error.value = ''
  emit('loading', true)
  try {
    const preset = await loadInterviewPreset(filename, active.signal)
    if (request !== active || !dialog.value?.open) return
    emit('select', preset, filename)
    reading.value = ''
    close()
  } catch (cause) {
    if (request === active) error.value = `${cause instanceof Error ? cause.message : '无法加载预设。'} 当前配置更新未确认，请重试或手动加载配置。`
  } finally {
    if (request === active) {
      reading.value = ''
      emit('loading', false)
    }
  }
}

onBeforeUnmount(cleanup)
</script>

<template>
  <button class="preset-trigger" type="button" :disabled="disabled" @click="open">
    <FolderOpen :size="17" aria-hidden="true" />读取预设
  </button>
  <Teleport to="body">
    <dialog ref="dialog" class="preset-dialog" aria-labelledby="preset-title" aria-describedby="preset-help" @cancel.prevent="close" @close="cleanup" @click.self="close">
      <div class="preset-content">
        <header>
          <div><p class="eyebrow">INTERVIEW PRESETS</p><h2 id="preset-title">读取面试预设</h2></div>
          <button class="close-button" type="button" aria-label="关闭预设窗口" :disabled="!!reading" autofocus @click="close"><X :size="19" /></button>
        </header>
        <p id="preset-help" class="muted">选择预设将更新当前会话的面试配置，成功后即可开始对话，无需再次点击“加载配置”。当前表单内容将被替换。</p>
        <p v-if="reading" class="muted" role="status">正在更新会话配置，请等待完成；此时关闭窗口不能撤销后端更新。</p>
        <div class="list-heading"><span>预设文件</span><button class="refresh-button" type="button" :disabled="loading || !!reading" @click="refresh"><RefreshCw :size="13" aria-hidden="true" />刷新</button></div>
        <p v-if="error" class="preset-error" role="alert">{{ error }}</p>
        <div class="preset-list" :aria-busy="loading || !!reading">
          <p v-if="loading" class="empty" role="status">正在读取预设列表…</p>
          <p v-else-if="!files.length && !error" class="empty">暂无预设文件</p>
          <ul v-else-if="files.length">
            <li v-for="filename in files" :key="filename">
              <button class="preset-file" type="button" :disabled="!!reading || disabled" @click="choose(filename)">
                <FileText :size="18" aria-hidden="true" /><span>{{ filename.replace(/\.json$/i, '') }}</span><small>{{ reading === filename ? '加载中…' : '加载' }}</small>
              </button>
            </li>
          </ul>
        </div>
        <footer class="muted">来源：<code>src/data/interview_preset</code></footer>
      </div>
    </dialog>
  </Teleport>
</template>

<style scoped>
.preset-trigger { display: flex; align-items: center; justify-content: center; gap: 9px; flex-shrink: 0; width: 100%; margin: 0 0 16px; padding: 12px 14px; border: 1px solid rgba(191, 220, 239, .25); border-radius: 12px; color: #deedf5; background: linear-gradient(145deg, rgba(141, 184, 207, .22), rgba(91, 134, 160, .12)); font-size: 12px; cursor: pointer; }
.preset-trigger:hover:not(:disabled) { background: rgba(141, 184, 207, .28); }
button:disabled { opacity: .45; cursor: not-allowed; }
.preset-dialog { width: min(540px, calc(100vw - 32px)); max-height: calc(100dvh - 40px); margin: auto; padding: 0; border: 1px solid rgba(191, 220, 239, .28); border-radius: 22px; color: #e8f0f5; background: linear-gradient(145deg, #203444, #101e2b); box-shadow: 0 28px 90px rgba(0, 0, 0, .5), inset 0 1px 0 rgba(222, 239, 250, .1); }
.preset-dialog::backdrop { background: rgba(3, 10, 18, .65); backdrop-filter: blur(6px); }
.preset-content { padding: 24px; }
header, .list-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.eyebrow { margin: 0 0 8px; color: #92b4c8; font-size: 10px; letter-spacing: .15em; }
h2 { margin: 0; font-size: 20px; font-weight: 500; }
.close-button, .refresh-button { display: inline-flex; align-items: center; justify-content: center; gap: 6px; border: 1px solid rgba(191, 220, 239, .18); border-radius: 9px; color: #c6dce8; background: rgba(191, 220, 239, .06); cursor: pointer; }
.close-button { width: 34px; height: 34px; flex-shrink: 0; }
.refresh-button { padding: 7px 10px; font-size: 12px; }
.muted { color: #98b2c3; font-size: 12px; line-height: 1.7; overflow-wrap: anywhere; }
#preset-help { margin: 18px 0 22px; }
.list-heading { margin-bottom: 12px; color: #c6dce8; font-size: 12px; }
.preset-list { max-height: 42dvh; overflow-y: auto; }
ul { margin: 0; padding: 0; list-style: none; display: grid; gap: 9px; }
.preset-file { display: flex; align-items: center; gap: 12px; width: 100%; padding: 16px; border: 1px solid rgba(191, 220, 239, .16); border-radius: 12px; color: #e0edf5; background: rgba(7, 17, 27, .35); text-align: left; cursor: pointer; }
.preset-file:hover:not(:disabled) { border-color: rgba(191, 220, 239, .5); background: rgba(141, 184, 207, .13); }
.preset-file span { flex: 1; min-width: 0; overflow-wrap: anywhere; font-size: 13px; }
.preset-file svg, .preset-file small { flex-shrink: 0; color: #98b2c3; }
.empty { padding: 24px 12px; margin: 0; text-align: center; color: #98b2c3; font-size: 13px; }
.preset-error { color: #f0b7ae; font-size: 12px; line-height: 1.6; overflow-wrap: anywhere; }
footer { margin-top: 22px; border-top: 1px solid rgba(191, 220, 239, .12); padding-top: 14px; }
@media (max-width: 580px) { .preset-content { padding: 18px; } }
</style>
