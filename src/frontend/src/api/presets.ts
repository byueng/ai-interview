import { apiBaseUrl, ApiRequestError, getActiveSessionId, getErrorMessage, resolveInterviewLanguage } from './candidate'
import type { CandidateConfig, InterviewerConfig } from './candidate'

export interface InterviewPreset {
  candidate_config: CandidateConfig
  interviewer_config: InterviewerConfig
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isFilename(value: unknown): value is string {
  return typeof value === 'string' && value.endsWith('.json') && value.length > 5 && !/[\\/\u0000-\u001f]/.test(value)
}

async function requestPresetJson(path: string, signal?: AbortSignal, body?: unknown): Promise<unknown> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    method: body === undefined ? 'GET' : 'POST', cache: 'no-store',
    headers: { Accept: 'application/json', ...(body === undefined ? {} : { 'Content-Type': 'application/json' }) },
    body: body === undefined ? undefined : JSON.stringify(body), signal,
  })
  const payload: unknown = await response.json().catch(() => null)
  if (!response.ok) {
    throw new ApiRequestError(response.status, getErrorMessage(payload, `读取预设失败（${response.status}），请确认后端预设接口已实现。`))
  }
  return payload
}

// 对齐当前路由；列表响应契约待后端补齐：{ files: string[] }。
export async function listInterviewPresets(signal?: AbortSignal): Promise<string[]> {
  const payload = await requestPresetJson('/interview/read_preset', signal)
  if (!isRecord(payload) || !Array.isArray(payload.files) || !payload.files.every(isFilename)) {
    throw new Error('预设列表格式错误，应返回 { files: ["文件名.json"] }。')
  }
  return [...new Set(payload.files)].sort((a, b) => a.localeCompare(b, 'zh-CN'))
}

// 后端须先更新该 session 的 state，再返回 { session_id, candidate_config, interviewer_config }。
export async function loadInterviewPreset(filename: string, signal?: AbortSignal): Promise<InterviewPreset> {
  if (!isFilename(filename)) throw new Error('预设文件名无效。')
  const sessionId = await getActiveSessionId(signal)
  const payload = await requestPresetJson('/interview/load_preset', signal, { session_id: sessionId, filename })
  if (!isRecord(payload)) throw new Error('预设内容不是有效的配置对象。')
  if (payload.session_id !== sessionId) throw new Error('预设加载响应的 session_id 与当前会话不一致，无法确认配置已加载。')
  const candidate = payload.candidate_config
  const interviewer = payload.interviewer_config
  if (!isRecord(candidate) || !isRecord(interviewer)
    || typeof candidate.language !== 'string' || !candidate.language.trim()
    || typeof candidate.education !== 'string' || typeof candidate.position !== 'string'
    || !(candidate.resume == null || typeof candidate.resume === 'string')
    || typeof interviewer.role_identity !== 'string'
    || !(interviewer.role_responsibilities === null || typeof interviewer.role_responsibilities === 'string')) {
    throw new Error('预设字段不完整或类型错误，需要 candidate_config 和 interviewer_config。')
  }
  const language = resolveInterviewLanguage(candidate.language)
  if (language !== 'zh-CN' && language !== 'en-US') throw new Error('此预设的语言暂不支持，当前可选择中文或 English。')
  return {
    candidate_config: { language, education: candidate.education, position: candidate.position, resume: candidate.resume ?? null },
    interviewer_config: { role_identity: interviewer.role_identity, role_responsibilities: interviewer.role_responsibilities ?? '' },
  }
}
