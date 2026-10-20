const SESSION_ID_CACHE_KEY = 'ai-interview.session-id'

let sessionIdInMemory: string | null = null
let sessionInitialization: Promise<string> | null = null

export interface CandidateConfig {
  language: string
  education: string
  position: string
  // 后端 Path 的 JSON 表示；文件上传接口尚未实现。
  resume?: string | null
}

export interface InterviewerConfig {
  role_identity: string
  role_responsibilities: string
}

export type CandidateConfigInput = Omit<CandidateConfig, 'language'> & {
  language?: string
}

// 默认使用中文，不跟随浏览器语言；用户显式选择优先。
export function resolveInterviewLanguage(selectedLanguage?: string): string {
  const selected = selectedLanguage?.trim()
  if (selected) {
    return normalizeSupportedLanguage(selected) ?? selected
  }

  return 'zh-CN'
}

function normalizeSupportedLanguage(value: string): string | undefined {
  const language = value.trim().toLowerCase()
  if (language === 'zh' || language.startsWith('zh-') || language === 'chinese' || language === '中文') {
    return 'zh-CN'
  }
  if (language === 'en' || language.startsWith('en-') || language === 'english' || language === '英文') {
    return 'en-US'
  }
  return undefined
}

export interface CandidateConfigRequest {
  session_id: string
  candidate_config: CandidateConfig
  interviewer_config: InterviewerConfig
}

export interface SessionInitializationResponse {
  session_id: string
}

export interface SessionSnapshot extends SessionInitializationResponse {
  status: 'active'
  chat_round: number
  expires_at: number
  candidate_config: CandidateConfig | null
  interviewer_config: InterviewerConfig | null
  messages: Array<{ type: string; content: unknown }>
}

export class ApiRequestError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message)
    this.name = 'ApiRequestError'
  }
}

export const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')

export async function initializeSession(
  signal?: AbortSignal,
): Promise<string> {
  if (sessionInitialization) {
    return sessionInitialization
  }

  const request = requestSessionInitialization(signal)
  sessionInitialization = request

  void request.then(
    () => {
      if (sessionInitialization === request) {
        sessionInitialization = null
      }
    },
    () => {
      if (sessionInitialization === request) {
        sessionInitialization = null
      }
    },
  )

  return request
}

export async function readCurrentSession(signal?: AbortSignal): Promise<SessionSnapshot> {
  const sessionId = await getActiveSessionId(signal)
  const response = await fetch(`${apiBaseUrl}/interview/sessions/${encodeURIComponent(sessionId)}`, {
    cache: 'no-store', headers: { Accept: 'application/json' }, signal,
  })
  const payload = await response.json().catch(() => null)
  if (!response.ok) throw new ApiRequestError(response.status, getErrorMessage(payload, response.statusText))
  if (!hasSessionId(payload) || payload.session_id !== sessionId
    || !('status' in payload) || payload.status !== 'active'
    || !('chat_round' in payload) || !Number.isInteger(payload.chat_round)
    || !('messages' in payload) || !Array.isArray(payload.messages)) {
    throw new Error('会话恢复响应无效。')
  }
  return payload as SessionSnapshot
}

// 新导航（包括 opener 复制的 sessionStorage）必须新建；刷新/历史恢复才续接。
export async function openPageSession(signal?: AbortSignal): Promise<SessionSnapshot> {
  const navigation = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming | undefined
  const canResume = navigation?.type === 'reload' || navigation?.type === 'back_forward'
  if (!canResume || !getCachedSessionId()) await initializeSession(signal)
  return readCurrentSession(signal)
}

export async function endCurrentSession(signal?: AbortSignal): Promise<void> {
  const sessionId = await getActiveSessionId(signal)
  const response = await fetch(`${apiBaseUrl}/interview/sessions/${encodeURIComponent(sessionId)}/end`, {
    method: 'POST', headers: { Accept: 'application/json' }, signal,
  })
  const payload = await response.json().catch(() => null)
  if (!response.ok) throw new ApiRequestError(response.status, getErrorMessage(payload, response.statusText))
  if (payload?.session_id !== sessionId || payload?.status !== 'ended') throw new Error('结束会话未返回成功标识。')
}

export async function postCandidateConfig(
  candidateConfig: CandidateConfigInput,
  interviewerConfig: InterviewerConfig,
  signal?: AbortSignal,
): Promise<void> {
  const sessionId = await getActiveSessionId(signal)
  const body: CandidateConfigRequest = {
    session_id: sessionId,
    candidate_config: {
      language: resolveInterviewLanguage(candidateConfig.language),
      education: candidateConfig.education,
      position: candidateConfig.position,
      resume: candidateConfig.resume ?? null,
    },
    interviewer_config: {
      role_identity: interviewerConfig.role_identity,
      role_responsibilities: interviewerConfig.role_responsibilities,
    },
  }

  const response = await fetch(`${apiBaseUrl}/interview/personal_information_config`, {
    method: 'POST',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
    signal,
  })

  const payload: unknown = await response.json().catch(() => null)

  if (!response.ok) {
    throw new ApiRequestError(response.status, getErrorMessage(payload, response.statusText))
  }

  // 后端 return HTTP_200_OK 当前返回的 JSON 响应体是数字 200。
  if (payload !== 200) {
    throw new Error('个人信息配置接口未返回成功标识 200。')
  }
}

export function getCachedSessionId(): string | null {
  if (sessionIdInMemory) {
    return sessionIdInMemory
  }

  try {
    sessionIdInMemory = window.sessionStorage.getItem(SESSION_ID_CACHE_KEY)
  } catch {
    // 浏览器禁用存储时，当前页面生命周期内仍可使用内存缓存。
  }

  return sessionIdInMemory
}

export function clearCachedSessionId(): void {
  sessionIdInMemory = null

  try {
    window.sessionStorage.removeItem(SESSION_ID_CACHE_KEY)
  } catch {
    // 存储不可用时无需额外处理。
  }
}

export async function getActiveSessionId(signal?: AbortSignal): Promise<string> {
  if (sessionInitialization) return sessionInitialization
  return getCachedSessionId() ?? initializeSession(signal)
}

async function requestSessionInitialization(signal?: AbortSignal): Promise<string> {
  const response = await fetch(`${apiBaseUrl}/interview/begin`, {
    method: 'GET',
    cache: 'no-store',
    headers: {
      Accept: 'application/json',
    },
    signal,
  })

  const payload: unknown = await response.json().catch(() => null)

  if (!response.ok) {
    throw new ApiRequestError(response.status, getErrorMessage(payload, response.statusText))
  }

  if (!hasSessionId(payload)) {
    throw new Error('会话初始化接口未返回有效的 session_id。')
  }

  const sessionId = payload.session_id
  cacheSessionId(sessionId)
  return sessionId
}

function cacheSessionId(sessionId: string): void {
  sessionIdInMemory = sessionId

  try {
    window.sessionStorage.setItem(SESSION_ID_CACHE_KEY, sessionId)
  } catch {
    // 存储不可用时使用内存缓存，避免阻断已成功的初始化请求。
  }
}

function hasSessionId(value: unknown): value is SessionInitializationResponse {
  return (
    typeof value === 'object'
    && value !== null
    && 'session_id' in value
    && typeof value.session_id === 'string'
    && value.session_id.length > 0
  )
}

export function getErrorMessage(payload: unknown, fallback: string): string {
  if (
    typeof payload === 'object'
    && payload !== null
    && 'detail' in payload
    && typeof payload.detail === 'string'
  ) {
    return payload.detail
  }

  if (typeof payload === 'object' && payload !== null && 'detail' in payload && Array.isArray(payload.detail)) {
    const details = payload.detail.map((item: unknown) => {
      if (typeof item !== 'object' || item === null || !('msg' in item) || typeof item.msg !== 'string') return ''
      const location = 'loc' in item && Array.isArray(item.loc) ? item.loc.join('.') : ''
      return location ? `${location}: ${item.msg}` : item.msg
    }).filter(Boolean)
    if (details.length) return details.join('; ')
  }

  return fallback || '接口请求失败。'
}
