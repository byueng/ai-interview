import { computed, reactive } from 'vue'
import { endCurrentSession, initializeSession, openPageSession, postCandidateConfig, readCurrentSession, resolveInterviewLanguage } from '../api/candidate'
import type { SessionSnapshot } from '../api/candidate'
import { readInterviewUpdate, streamInterviewTurn } from '../api/interview'
import type { InterviewPreset } from '../api/presets'

export interface ConversationMessage { id: number; role: 'candidate' | 'interviewer'; text: string; uncertain?: boolean }
const blankCandidate = () => ({ position: '', education: '', language: 'zh-CN', resume: null as string | null })
const blankInterviewer = () => ({ role_identity: '技术面试官', role_responsibilities: '围绕岗位要求与项目经历，逐步提问和追问。' })
export const interview = reactive({
  status: 'initializing' as 'initializing' | 'ready' | 'error' | 'ended',
  candidate: blankCandidate(), interviewer: blankInterviewer(),
  savedSignature: '', sessionError: '', configError: '', streamError: '', notice: '',
  saving: false, loadingPreset: false, sending: false, round: 0, draft: '',
  messages: [] as ConversationMessage[],
})
let messageId = 0
let connection: Promise<boolean> | null = null
export const configuration = computed(() => ({
  candidate: { ...interview.candidate, position: interview.candidate.position.trim(), education: interview.candidate.education.trim() },
  interviewer: { role_identity: interview.interviewer.role_identity.trim(), role_responsibilities: interview.interviewer.role_responsibilities.trim() },
}))
export const busy = computed(() => interview.saving || interview.loadingPreset || interview.sending || interview.status === 'initializing')
export const configured = computed(() => !!interview.savedSignature && interview.savedSignature === JSON.stringify(configuration.value))
export const complete = computed(() => !!configuration.value.candidate.position && !!configuration.value.candidate.education && !!configuration.value.interviewer.role_identity && !!configuration.value.interviewer.role_responsibilities)
export const canSend = computed(() => interview.status === 'ready' && configured.value && !busy.value && !interview.streamError && !!interview.draft.trim())
function errorText(error: unknown) { return error instanceof Error ? error.message : '暂时无法完成，请稍后重试。' }

function restore(snapshot: SessionSnapshot) {
  Object.assign(interview.candidate, snapshot.candidate_config ?? blankCandidate())
  interview.candidate.language = resolveInterviewLanguage(interview.candidate.language)
  Object.assign(interview.interviewer, snapshot.interviewer_config ?? blankInterviewer())
  interview.interviewer.role_responsibilities ??= ''
  interview.savedSignature = snapshot.candidate_config && snapshot.interviewer_config ? JSON.stringify(configuration.value) : ''
  interview.round = snapshot.chat_round
  interview.messages = snapshot.messages.filter(message => ['human', 'ai'].includes(message.type)).map(message => ({
    id: ++messageId, role: message.type === 'human' ? 'candidate' : 'interviewer',
    text: typeof message.content === 'string' ? message.content : readInterviewUpdate({ InterviewAgent: { messages: [{ ...message, type: 'ai' }] } }).messages.map(reply => reply.text).join(''),
  }))
  interview.configError = interview.streamError = interview.draft = ''
}

export function connect(mode: 'page' | 'continue' | 'new' = 'continue'): Promise<boolean> {
  if (connection) return connection
  if (interview.sending || interview.saving || interview.loadingPreset) return Promise.resolve(false)
  interview.status = 'initializing'; interview.sessionError = ''
  connection = (async () => {
    try {
      if (mode === 'new') await initializeSession()
      restore(await (mode === 'page' ? openPageSession() : readCurrentSession()))
      interview.status = 'ready'
      if (mode !== 'page') interview.notice = mode === 'new' ? '新的练习空间已准备好。' : '已同步当前会话。'
      return true
    } catch (error) { interview.status = 'error'; interview.sessionError = errorText(error); return false }
    finally { connection = null }
  })()
  return connection
}

export async function saveConfiguration(): Promise<boolean> {
  if (configured.value) return true
  if (busy.value || interview.status !== 'ready' || !complete.value) return false
  interview.saving = true; interview.configError = ''
  const value = configuration.value
  try {
    await postCandidateConfig(value.candidate, value.interviewer)
    interview.savedSignature = JSON.stringify(value)
    interview.notice = '面试配置已保存，也可在预设中再次使用。'
    return true
  } catch (error) { interview.configError = errorText(error); return false }
  finally { interview.saving = false }
}
export function onPresetLoading(value: boolean) {
  interview.loadingPreset = value
  if (value) { interview.savedSignature = ''; interview.configError = '' }
}
export function applyPreset(preset: InterviewPreset, filename: string) {
  Object.assign(interview.candidate, preset.candidate_config)
  interview.candidate.language = resolveInterviewLanguage(interview.candidate.language)
  Object.assign(interview.interviewer, preset.interviewer_config)
  interview.savedSignature = JSON.stringify(configuration.value)
  interview.notice = `已载入「${filename.replace(/\.json$/i, '')}」。`
}
export async function sendMessage() {
  if (!canSend.value) return
  const text = interview.draft.trim(), id = ++messageId
  interview.messages.push({ id, role: 'candidate', text })
  interview.sending = true; interview.streamError = ''
  let receivedReply = false
  const ids = new Set<string>()
  try {
    for await (const event of streamInterviewTurn({ role: 'Human', message: text, chat_round: interview.round, dtime: new Date().toISOString() })) {
      if (event.event === 'message') {
        const update = readInterviewUpdate(event.data)
        if (update.chatRound !== undefined) interview.round = update.chatRound
        for (const reply of update.messages) {
          if (reply.id && ids.has(reply.id)) continue
          if (reply.id) ids.add(reply.id)
          interview.messages.push({ id: ++messageId, role: 'interviewer', text: reply.text }); receivedReply = true
        }
      } else {
        if (!receivedReply) throw new Error('未收到可展示的面试官回复。')
        interview.draft = ''
      }
    }
  } catch (error) {
    interview.streamError = `${errorText(error)} 请先同步会话，确认本轮状态。`
    const message = interview.messages.find(item => item.id === id)
    if (message) message.uncertain = true
  } finally { interview.sending = false }
}
export async function finishSession(): Promise<boolean> {
  if (busy.value || interview.status !== 'ready') return false
  interview.saving = true; interview.sessionError = ''
  try {
    await endCurrentSession(); interview.status = 'ended'
    interview.notice = '本次练习已结束。花一点时间，回看自己的表达。'
    return true
  } catch (error) { interview.sessionError = errorText(error); return false }
  finally { interview.saving = false }
}
export function downloadTranscript() {
  const text = [`${interview.candidate.position || '模拟面试'} · 对话记录`, `已完成 ${interview.round} 轮`, '', ...interview.messages.map(message => `${message.role === 'candidate' ? '我' : '面试官'}${message.uncertain ? '（完成状态待确认）' : ''}\n${message.text}\n`)].join('\n')
  const url = URL.createObjectURL(new Blob([text], { type: 'text/plain;charset=utf-8' }))
  const link = document.createElement('a'); link.href = url; link.download = '面试对话记录.txt'; link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
