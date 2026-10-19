<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref } from 'vue'
import { FileText, FolderOpen, RefreshCw, Trash2, X } from 'lucide-vue-next'
import { deleteInterviewPreset, listInterviewPresets, loadInterviewPreset } from '../api/presets'
import type { InterviewPreset } from '../api/presets'

const props = defineProps<{ disabled: boolean }>()
const emit = defineEmits<{ select: [preset: InterviewPreset, filename: string]; loading: [value: boolean] }>()
const dialog = ref<HTMLDialogElement | null>(null)
const files = ref<string[]>([])
const loading = ref(false)
const reading = ref('')
const error = ref('')
const pendingDelete = ref('')
const deleting = ref(false)
const notice = ref('')
const cancelButton = ref<HTMLButtonElement | null>(null)
const refreshButton = ref<HTMLButtonElement | null>(null)
let deleteTrigger: HTMLButtonElement | undefined
let request: AbortController | undefined
let previousOverflow: string | undefined

function cleanup() {
  request?.abort()
  request = undefined
  loading.value = false
  reading.value = ''
  pendingDelete.value = ''
  deleting.value = false
  notice.value = ''
  emit('loading', false)
  if (previousOverflow !== undefined) {
    document.body.style.overflow = previousOverflow
    previousOverflow = undefined
  }
}

function close() {
  // POST 已开始更新后端 state，不能把关闭窗口误当作撤销。
  if (reading.value || deleting.value) return
  if (pendingDelete.value) { cancelDelete(); return }
  cleanup()
  dialog.value?.close()
}

async function refresh() {
  if (reading.value || deleting.value || pendingDelete.value) return
  request?.abort()
  const active = new AbortController()
  request = active
  loading.value = true
  reading.value = ''
  error.value = ''
  notice.value = ''
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
  if (props.disabled || reading.value || loading.value || pendingDelete.value || deleting.value) return
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

async function askDelete(filename: string, event: MouseEvent) {
  if (props.disabled || loading.value || reading.value || deleting.value || pendingDelete.value) return
  deleteTrigger = event.currentTarget as HTMLButtonElement
  pendingDelete.value = filename
  error.value = ''
  notice.value = ''
  await nextTick()
  cancelButton.value?.focus({ preventScroll: true })
}

function cancelDelete() {
  if (deleting.value) return
  pendingDelete.value = ''
  void nextTick(() => deleteTrigger?.focus({ preventScroll: true }))
}

async function confirmDelete() {
  if (!pendingDelete.value || deleting.value || reading.value || props.disabled) return
  const filename = pendingDelete.value
  const active = new AbortController()
  request?.abort()
  request = active
  deleting.value = true
  error.value = ''
  try {
    await deleteInterviewPreset(filename, active.signal)
    if (request !== active) return
    files.value = files.value.filter(file => file !== filename)
    pendingDelete.value = ''
    notice.value = `已删除 ${filename.replace(/\.json$/i, '')}。此操作无法在页面中撤销。`
  } catch (cause) {
    if (request === active) error.value = `${cause instanceof Error ? cause.message : '删除预设失败。'} 未确认删除成功，请刷新列表核实。`
  } finally {
    if (request === active) {
      deleting.value = false
      await nextTick()
      if (pendingDelete.value) cancelButton.value?.focus({ preventScroll: true })
      else refreshButton.value?.focus({ preventScroll: true })
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
          <button class="close-button" type="button" aria-label="关闭预设窗口" :disabled="!!reading || deleting" autofocus @click="close"><X :size="19" /></button>
        </header>
        <p id="preset-help" class="muted">选择预设将替换当前表单并保存到本次会话。载入后，点击“保存并进入面试室”即可开始练习。</p>
        <p v-if="reading" class="muted" role="status">正在更新会话配置，请等待完成；此时关闭窗口不能撤销后端更新。</p>
        <div class="list-heading"><span>预设文件</span><button ref="refreshButton" class="refresh-button" type="button" :disabled="loading || !!reading || !!pendingDelete || deleting" @click="refresh"><RefreshCw :size="13" aria-hidden="true" />刷新</button></div>
        <section v-if="pendingDelete" class="delete-confirmation" role="group" aria-labelledby="delete-preset-title">
          <p id="delete-preset-title">确认删除“{{ pendingDelete.replace(/\.json$/i, '') }}”？</p>
          <p class="muted">将删除本地预设文件，无法在页面中撤销；当前已加载的面试配置不受影响。</p>
          <div class="delete-actions">
            <button ref="cancelButton" class="refresh-button" type="button" :disabled="deleting" @click="cancelDelete">取消</button>
            <button class="delete-button" type="button" :disabled="deleting" @click="confirmDelete">{{ deleting ? '删除中…' : '确认删除' }}</button>
          </div>
        </section>
        <p v-if="error" class="preset-error" role="alert">{{ error }}</p>
        <p v-if="notice" class="muted" role="status">{{ notice }}</p>
        <div class="preset-list" :aria-busy="loading || !!reading || deleting">
          <p v-if="loading" class="empty" role="status">正在读取预设列表…</p>
          <p v-else-if="!files.length && !error" class="empty">暂无预设文件</p>
          <ul v-else-if="files.length">
            <li v-for="filename in files" :key="filename" class="preset-row">
              <button class="preset-file" type="button" :disabled="!!reading || !!pendingDelete || deleting || disabled" @click="choose(filename)">
                <FileText :size="18" aria-hidden="true" /><span>{{ filename.replace(/\.json$/i, '') }}</span>
              </button>
              <button class="delete-button" type="button" :aria-label="`删除 ${filename.replace(/\.json$/i, '')}`" :disabled="!!reading || !!pendingDelete || deleting || disabled" @click="askDelete(filename, $event)">
                <Trash2 :size="15" aria-hidden="true" />删除
              </button>
            </li>
          </ul>
        </div>
        <footer class="muted">每一份准备，都可以成为下一次练习的起点。</footer>
      </div>
    </dialog>
  </Teleport>
</template>

<style scoped>
.preset-trigger { display: flex; align-items: center; justify-content: center; gap: 9px; width: 100%; padding: 12px 14px; border: 1px solid #8d7954; border-radius: 2px; color: #d3bc92; background: transparent; font-size: 11px; cursor: pointer; }
.preset-trigger:hover:not(:disabled) { background: #21344b; }
button:disabled { opacity: .45; cursor: not-allowed; }
.preset-dialog { width: min(540px, calc(100vw - 32px)); max-height: calc(100dvh - 40px); margin: auto; padding: 0; border: 1px solid #89734d; border-radius: 3px; color: var(--ink); background: var(--paper); box-shadow: 0 28px 90px #17201e50; }
.preset-dialog::backdrop { background: #030a15cc; backdrop-filter: blur(3px); }
.preset-content { padding: 24px; }
header, .list-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.eyebrow { margin: 0 0 8px; color: var(--muted); font-size: 9px; letter-spacing: .15em; }
h2 { margin: 0; font: 400 25px/1.5 var(--serif); }
.close-button, .refresh-button { display: inline-flex; align-items: center; justify-content: center; gap: 6px; border: 1px solid #5b5e58; border-radius: 2px; color: #c5b18f; background: transparent; cursor: pointer; }
.close-button { width: 34px; height: 34px; flex-shrink: 0; }
.refresh-button { padding: 7px 10px; font-size: 12px; }
.muted { color: var(--muted); font-size: 11px; line-height: 1.8; overflow-wrap: anywhere; }
#preset-help { margin: 18px 0 22px; }
.list-heading { margin-bottom: 12px; color: #c5b18f; font-size: 12px; }
.preset-list { max-height: 42dvh; overflow-y: auto; }
ul { margin: 0; padding: 0; list-style: none; display: grid; gap: 9px; }
.preset-row { display: flex; align-items: center; gap: 8px; padding-right: 12px; border: 1px solid #4b5c6f; border-radius: 2px; background: var(--white); }
.preset-file { display: flex; align-items: center; gap: 12px; flex: 1; min-width: 0; padding: 16px; border: 0; border-radius: 2px; color: var(--ink); background: transparent; text-align: left; cursor: pointer; }
.preset-file:hover:not(:disabled) { background: #1d354c; }
.preset-file span { flex: 1; min-width: 0; overflow-wrap: anywhere; font-size: 13px; }
.preset-file svg { flex-shrink: 0; color: #b99c67; }
.delete-button { display: inline-flex; align-items: center; justify-content: center; gap: 5px; flex-shrink: 0; padding: 8px 10px; border: 1px solid #835a50; border-radius: 2px; color: #dfaa9d; background: #342530; font-size: 11px; cursor: pointer; }
.delete-button:hover:not(:disabled) { background: rgba(164, 81, 73, .22); border-color: rgba(235, 165, 155, .5); }
.delete-confirmation { margin: 0 0 14px; padding: 14px; border: 1px solid #835a50; border-radius: 2px; background: #342530; }
.delete-confirmation p { margin: 0 0 10px; font-size: 13px; overflow-wrap: anywhere; }
.delete-actions { display: flex; justify-content: flex-end; gap: 8px; }
.empty { padding: 24px 12px; margin: 0; text-align: center; color: var(--muted); font-size: 12px; }
.preset-error { color: #dfaa9d; font-size: 12px; line-height: 1.6; overflow-wrap: anywhere; }
footer { margin-top: 22px; border-top: 1px solid var(--line); padding-top: 14px; }
@media (max-width: 580px) { .preset-content { padding: 18px; } }
</style>
