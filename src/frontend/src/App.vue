<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { PanelLeftClose, SendHorizontal, Sparkles, Sword, Upload, Wind } from 'lucide-vue-next'
import { initializeSession, postCandidateConfig, resolveInterviewLanguage } from './api/candidate'
import { readInterviewUpdate, streamInterviewTurn } from './api/interview'
import PresetPicker from './components/PresetPicker.vue'
import type { InterviewPreset } from './api/presets'

const candidate = reactive({ position: '', education: '', language: resolveInterviewLanguage(), resume: null as string | null })
const presetNotice = ref('')
const interviewer = reactive({ role_identity: '', role_responsibilities: '' })
const sessionState = ref<'initializing' | 'ready' | 'error'>('initializing')
const sessionError = ref('')
const configError = ref('')
const streamError = ref('')
const saving = ref(false)
const loadingPreset = ref(false)
const sending = ref(false)
const savedConfig = ref('')
const draft = ref('')
const chatRound = ref(0)
const conversation = ref<HTMLElement | null>(null)
const messages = ref<Array<{ id: number; role: 'candidate' | 'interviewer'; text: string; state?: string }>>([])
let messageId = 0
let controller: AbortController | undefined
let disposed = false

const config = computed(() => ({
  candidate: { position: candidate.position.trim(), education: candidate.education.trim(), language: candidate.language, resume: candidate.resume },
  interviewer: { role_identity: interviewer.role_identity.trim(), role_responsibilities: interviewer.role_responsibilities.trim() },
}))
const configSignature = computed(() => JSON.stringify(config.value))
const configSaved = computed(() => savedConfig.value === configSignature.value)
const busy = computed(() => saving.value || loadingPreset.value || sending.value)
const configComplete = computed(() => [config.value.candidate.position, config.value.candidate.education, config.value.candidate.language].every(Boolean) && Object.values(config.value.interviewer).every(Boolean))
const canSave = computed(() => sessionState.value === 'ready' && !busy.value && configComplete.value && !configSaved.value)
const canSend = computed(() => sessionState.value === 'ready' && !busy.value && configSaved.value && !!draft.value.trim())
const statusText = computed(() => sessionState.value === 'initializing' ? '正在连接'
  : sessionState.value === 'error' ? '连接失败'
  : sending.value ? '面试官正在回复' : saving.value || loadingPreset.value ? '正在加载配置'
  : configSaved.value ? '可以开始对话' : '请完善并加载配置')

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : '请求失败，请稍后重试。'
}

function onPresetLoading(value: boolean) {
  loadingPreset.value = value
  if (value) {
    savedConfig.value = ''
    configError.value = ''
    presetNotice.value = ''
  }
}

function applyPreset(preset: InterviewPreset, filename: string) {
  if (saving.value || sending.value || disposed) return
  Object.assign(candidate, preset.candidate_config)
  Object.assign(interviewer, preset.interviewer_config)
  savedConfig.value = configSignature.value
  configError.value = ''
  presetNotice.value = `已加载 ${filename.replace(/\.json$/i, '')}，可以开始对话。`
}

async function connect() {
  sessionState.value = 'initializing'
  sessionError.value = ''
  controller = new AbortController()
  try {
    await initializeSession(controller.signal)
    sessionState.value = 'ready'
  } catch (error) {
    if (disposed) return
    sessionState.value = 'error'
    sessionError.value = errorMessage(error)
  }
}

async function saveConfig() {
  if (!canSave.value) return
  saving.value = true
  configError.value = ''
  const signature = configSignature.value
  savedConfig.value = ''
  controller = new AbortController()
  try {
    await postCandidateConfig(config.value.candidate, config.value.interviewer, controller.signal)
    savedConfig.value = signature
    presetNotice.value = ''
  } catch (error) {
    if (!disposed) configError.value = errorMessage(error)
  } finally {
    saving.value = false
  }
}

async function scrollToLatest() {
  await nextTick()
  if (conversation.value) conversation.value.scrollTop = conversation.value.scrollHeight
}

async function submitMessage() {
  if (!canSend.value) return
  const text = draft.value.trim()
  const userMessage = { id: ++messageId, role: 'candidate' as const, text, state: '发送中' }
  messages.value.push(userMessage)
  sending.value = true
  streamError.value = ''
  controller = new AbortController()
  const receivedIds = new Set<string>()
  let receivedReply = false
  await scrollToLatest()
  try {
    for await (const event of streamInterviewTurn({ role: 'Human', message: text, chat_round: chatRound.value, dtime: new Date().toISOString() }, controller.signal)) {
      if (event.event === 'message') {
        const update = readInterviewUpdate(event.data)
        if (update.chatRound !== undefined) chatRound.value = update.chatRound
        for (const reply of update.messages) {
          if (reply.id && receivedIds.has(reply.id)) continue
          if (reply.id) receivedIds.add(reply.id)
          messages.value.push({ id: ++messageId, role: 'interviewer', text: reply.text })
          receivedReply = true
        }
        await scrollToLatest()
      } else {
        if (!receivedReply) throw new Error('本轮已结束，但未收到可展示的面试官回复。')
        draft.value = ''
        const entry = messages.value.find(message => message.id === userMessage.id)
        if (entry) entry.state = ''
      }
    }
  } catch (error) {
    if (!disposed) {
      streamError.value = `${errorMessage(error)} 本轮完成状态未确认，未自动重发。`
      const entry = messages.value.find(message => message.id === userMessage.id)
      if (entry) entry.state = '完成状态未确认'
    }
  } finally {
    sending.value = false
    await scrollToLatest()
  }
}

function handleComposerKey(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing && event.keyCode !== 229) {
    event.preventDefault()
    void submitMessage()
  }
}

onMounted(() => { void connect() })
onBeforeUnmount(() => { disposed = true; controller?.abort() })
</script>

<template>
  <main class="app-shell">
    <div class="frost-haze" aria-hidden="true" />

    <aside class="archive-panel" aria-label="侧栏布局">
      <div class="archive-brand">
        <div class="brand-mark"><Sword :size="17" /></div>
        <div class="brand-copy"><span>INTERVIEW</span><strong>/ 02.0</strong></div>
        <button class="icon-button compact-toggle" type="button" aria-label="侧栏按钮占位" disabled>
          <PanelLeftClose :size="17" />
        </button>
      </div>

      <div class="archive-heading">
        <span>CANDIDATE</span>
        <strong>面试资料</strong>
        <em>INTERVIEW PROFILE</em>
      </div>

      <PresetPicker :disabled="busy || sessionState !== 'ready'" @select="applyPreset" @loading="onPresetLoading" />
      <p v-if="presetNotice && configSaved" class="preset-notice" role="status">{{ presetNotice }}</p>
      <fieldset class="candidate-fields" :disabled="busy">
        <legend class="sr-only">候选人信息</legend>
        <label>面试岗位<input v-model="candidate.position" placeholder="例如：后端工程师" required /></label>
        <label>学历<input v-model="candidate.education" placeholder="例如：本科" required /></label>
        <div class="language-field">
          <span id="language-label">面试语言</span>
          <div class="language-options" role="radiogroup" aria-labelledby="language-label">
            <label class="language-option">
              <input v-model="candidate.language" type="radio" name="language" value="zh-CN" />
              <span>中文</span>
            </label>
            <label class="language-option">
              <input v-model="candidate.language" type="radio" name="language" value="en-US" />
              <span>English</span>
            </label>
          </div>
        </div>
        <p class="field-hint">与面试官信息一同加载。</p>
      </fieldset>

      <section class="archive-empty" aria-label="上传简历区域占位">
        <Upload :size="16" />
        <p>上传简历</p>
        <span>暂未开放上传</span>
      </section>
    </aside>

    <section class="interview-stage">
      <header class="stage-header">
        <div class="eyebrow"><Wind :size="14" /> NORTHWIND / INTERVIEW</div>
        <div class="header-actions">
          <span class="status" :class="{ error: sessionState === 'error', connected: sessionState === 'ready', pending: sessionState === 'initializing' }" role="status"><i /> {{ statusText }}</span>
          <button class="icon-button" type="button" aria-label="工具栏按钮占位" disabled>
            <Sparkles :size="17" />
          </button>
        </div>
      </header>

      <section class="hero-heading">
        <p>INTERVIEW WORKSPACE</p>
        <div class="question-title"><span>—</span><strong>{{ candidate.position || '模拟面试' }}</strong><span v-if="chatRound">第 {{ chatRound }} 轮</span></div>
      </section>

      <section ref="conversation" class="conversation" role="log" aria-label="面试对话" aria-live="polite" :aria-busy="sending">
        <div v-if="!messages.length" class="empty-stage">
          <p>WORKSPACE</p>
          <h2>准备开始面试</h2>
          <span>{{ configSaved ? '配置已就绪，发送第一条消息开始面试。' : '手动加载配置，或从左侧加载预设，即可开始面试。' }}</span>
        </div>
        <article v-for="message in messages" :key="message.id" class="message" :class="{ candidate: message.role === 'candidate' }">
          <div class="message-meta"><span>{{ message.role === 'candidate' ? '你' : '面试官' }}</span><span v-if="message.state">{{ message.state }}</span></div>
          <p>{{ message.text }}</p>
        </article>
        <div v-if="sending" class="thinking" role="status"><span /><span /><span />面试官正在回复…</div>
      </section>

      <div class="composer-area">
        <div v-if="sessionState === 'error'" class="connection-error" role="alert">{{ sessionError }} <button type="button" class="config-button" @click="connect">重新连接</button></div>
        <form class="interviewer-config" aria-label="面试官配置" @submit.prevent="saveConfig">
          <label>面试官身份<input v-model="interviewer.role_identity" placeholder="例如：资深后端面试官" :disabled="busy" required /></label>
          <label>面试要求<input v-model="interviewer.role_responsibilities" placeholder="例如：围绕项目经历逐步追问" :disabled="busy" required /></label>
          <button class="config-button" type="submit" :disabled="!canSave">{{ saving ? '加载中…' : configSaved ? '已加载' : '加载配置' }}</button>
        </form>
        <p v-if="configError" class="composer-error feedback" role="alert">{{ configError }}</p>
        <form class="composer" aria-label="发送面试消息" @submit.prevent="submitMessage">
        <textarea v-model="draft" rows="2" :placeholder="configSaved ? '输入你的回答…' : '请先完善并加载面试配置…'" aria-label="面试消息" :disabled="busy || sessionState !== 'ready'" @keydown="handleComposerKey" />
        <div class="composer-footer">
          <span>{{ sending ? '正在等待回复…' : !configSaved ? '请先加载配置' : 'Enter 发送 · Shift + Enter 换行' }}</span>
          <div class="composer-buttons">
            <button type="submit" :disabled="!canSend">{{ sending ? '回复中…' : '发送' }} <SendHorizontal :size="16" /></button>
          </div>
        </div>
        </form>
        <p v-if="streamError" class="composer-error feedback" role="alert">{{ streamError }}</p>
      </div>
    </section>
  </main>
</template>

<style scoped>
.archive-panel {
  overflow-y: auto;
  margin: 14px 0 14px 14px;
  border: 1px solid rgba(190, 216, 233, .16);
  border-radius: 22px;
  background: linear-gradient(155deg, rgba(30, 47, 61, .85), rgba(9, 18, 28, .86) 65%);
  box-shadow: 0 16px 40px rgba(0, 0, 0, .24), inset 0 1px 0 rgba(222, 239, 250, .08);
  backdrop-filter: blur(14px);
}
.archive-heading { margin: 36px 8px 22px; }
.preset-notice { margin: 0 2px 14px; color: #b6cbd7; font-size: 11px; line-height: 1.6; overflow-wrap: anywhere; }
.candidate-fields {
  display: grid;
  gap: 16px;
  min-width: 0;
  margin: 0;
  padding: 18px 14px;
  border: 1px solid rgba(191, 220, 239, .14);
  border-radius: 16px;
  background: linear-gradient(145deg, rgba(54, 77, 96, .3), rgba(20, 33, 46, .4));
  box-shadow: 0 8px 20px rgba(0, 0, 0, .12), inset 0 1px 0 rgba(222, 239, 250, .05);
}
.archive-empty {
  margin: 16px 0 0;
  padding: 16px 14px;
  border-color: rgba(190, 216, 233, .18);
  border-radius: 16px;
  background: rgba(9, 18, 28, .25);
}
.candidate-fields > label, .language-field, .interviewer-config label { display: grid; gap: 7px; min-width: 0; color: #b6cbd7; font-size: 11px; }
input:not([type="radio"]) {
  min-width: 0;
  width: 100%;
  padding: 10px 12px;
  border: 1px solid rgba(191, 220, 239, .2);
  border-radius: 10px;
  background: rgba(7, 17, 27, .58);
  box-shadow: inset 0 2px 5px rgba(0, 0, 0, .15);
  color: #edf5f8;
  font: inherit;
  font-size: 12px;
  transition: border-color .18s ease, background .18s ease;
}
input:not([type="radio"]):hover:not(:disabled) { border-color: rgba(191, 220, 239, .38); }
input::placeholder { color: #91aab9; }
input:not([type="radio"]):focus-visible { outline: 2px solid rgba(191, 218, 227, .65); outline-offset: 2px; background: rgba(15, 30, 43, .85); }
.language-options {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 4px;
  height: 40px;
  padding: 3px;
  border: 1px solid rgba(191, 220, 239, .2);
  border-radius: 10px;
  background: rgba(7, 17, 27, .58);
  box-shadow: inset 0 2px 5px rgba(0, 0, 0, .15);
}
.language-option { position: relative; min-width: 0; }
.language-option input { position: absolute; inset: 0; width: 100%; height: 100%; margin: 0; opacity: 0; cursor: pointer; }
.language-option span {
  display: grid;
  height: 100%;
  place-items: center;
  border-radius: 7px;
  color: #91aab9;
  font-size: 12px;
  line-height: 20px;
  transition: color .18s ease, background .18s ease;
}
.language-option input:hover:not(:disabled) + span { background: rgba(191, 220, 239, .1); }
.language-option input:checked + span { color: #edf5f8; background: rgba(141, 184, 207, .24); box-shadow: inset 0 0 0 1px rgba(191, 220, 239, .25); }
.language-option input:focus-visible + span { outline: 2px solid rgba(191, 218, 227, .65); outline-offset: 2px; }
.language-option input:disabled { cursor: not-allowed; }
.language-option input:disabled + span { opacity: .45; }
.field-hint { margin: 0; font-size: 11px; line-height: 1.6; color: #91aab9; }
.composer-area { display: grid; gap: 14px; min-width: 0; }
.interviewer-config {
  display: grid;
  grid-template-columns: minmax(140px, 1fr) minmax(180px, 2fr) auto;
  align-items: end;
  gap: 14px;
  padding: 16px 18px;
  border: 1px solid rgba(191, 220, 239, .2);
  border-radius: 16px;
  background: linear-gradient(135deg, rgba(36, 55, 71, .86), rgba(16, 29, 41, .88));
  box-shadow: 0 8px 24px rgba(0, 0, 0, .16), inset 0 1px 0 rgba(222, 239, 250, .07);
  backdrop-filter: blur(12px);
}
.composer {
  padding: 16px 18px 14px;
  border-color: rgba(191, 220, 239, .3);
  border-radius: 20px;
  background: linear-gradient(135deg, rgba(27, 44, 60, .94), rgba(18, 32, 46, .89));
  box-shadow: 0 16px 36px rgba(0, 0, 0, .28), inset 0 1px 0 rgba(222, 239, 250, .1);
  backdrop-filter: blur(14px);
  transition: border-color .18s ease, box-shadow .18s ease;
}
.composer:focus-within { border-color: rgba(196, 229, 242, .6); box-shadow: 0 16px 36px rgba(0, 0, 0, .28), 0 0 0 3px rgba(164, 207, 229, .06); }
.composer textarea { border-radius: 10px; }
.config-button, .composer button {
  border: 1px solid rgba(199, 226, 241, .35);
  border-radius: 10px;
  background: linear-gradient(145deg, rgba(141, 184, 207, .24), rgba(91, 134, 160, .16));
  box-shadow: inset 0 1px 0 rgba(225, 243, 251, .09), 0 3px 8px rgba(0, 0, 0, .12);
}
.config-button { padding: 10px 14px; min-height: 38px; color: #edf5f3; font-size: 11px; cursor: pointer; white-space: nowrap; }
.config-button:hover:not(:disabled) { background: rgba(221, 238, 235, .23); }
.config-button:disabled { opacity: .45; cursor: not-allowed; }
.feedback { margin: 0; font-size: 12px; line-height: 1.6; overflow-wrap: anywhere; }
.connection-error { display: flex; align-items: center; justify-content: space-between; gap: 12px; font-size: 12px; color: #f0b7ae; }
.message { margin-top: 12px; overflow-wrap: anywhere; }
.message p { white-space: pre-wrap; }
.thinking { gap: 8px; }
.sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); }
@media (max-width: 860px) {
  .archive-panel { margin: 12px 12px 0; border-radius: 18px; }
  .candidate-fields { grid-template-columns: repeat(3, minmax(0, 1fr)); padding-top: 18px; }
  .field-hint { grid-column: 1 / -1; }
}
@media (max-width: 580px) {
  .candidate-fields { grid-template-columns: 1fr; gap: 12px; }
  .interviewer-config { grid-template-columns: 1fr; padding: 14px; }
  .composer { padding: 14px; }
  .composer-footer { justify-content: flex-end; }
}
</style>
