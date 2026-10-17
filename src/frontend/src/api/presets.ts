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

async function requestPresetJson(path: string, signal?: AbortSignal, method: 'GET' | 'POST' = 'GET', sessionId?: string): Promise<unknown> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    method, cache: 'no-store',
    headers: { Accept: 'application/json', ...(sessionId === undefined ? {} : { 'Content-Type': 'application/json' }) },
    body: sessionId === undefined ? undefined : JSON.stringify(sessionId), signal,
  })
  const payload: unknown = await response.json().catch(() => null)
  if (!response.ok) {
    throw new ApiRequestError(response.status, getErrorMessage(payload, `预设请求失败（${response.status}）。`))
  }
  return payload
}

// 后端 os.listdir 返回目录条目，前端只展示有效的 JSON 文件名。
export async function listInterviewPresets(signal?: AbortSignal): Promise<string[]> {
  const payload = await requestPresetJson('/interview/read_preset', signal)
  if (!isRecord(payload) || !Array.isArray(payload.files) || !payload.files.every(value => typeof value === 'string')) {
    throw new Error('预设列表格式错误，应返回 { files: ["文件名.json"] }。')
  }
  return [...new Set(payload.files.filter(isFilename))].sort((a, b) => a.localeCompare(b, 'zh-CN'))
}

export async function deleteInterviewPreset(filename: string, signal?: AbortSignal): Promise<void> {
  if (!isFilename(filename)) throw new Error('预设文件名无效。')
  signal?.throwIfAborted()
  const payload = await requestPresetJson(`/interview/del_preset?filename=${encodeURIComponent(filename)}`, signal, 'POST')
  if (payload !== 200) throw new Error('删除预设接口未返回成功标识 200，请刷新列表确认文件状态。')
}

// filename 为查询参数；单个 Body(UUID) 参数要求整个 JSON body 为 UUID 字符串。
// state 更新由 load_preset 负责，不再二次调用 personal_information_config。
export async function loadInterviewPreset(filename: string, signal?: AbortSignal): Promise<InterviewPreset> {
  if (!isFilename(filename)) throw new Error('预设文件名无效。')
  const sessionId = await getActiveSessionId(signal)
  signal?.throwIfAborted()
  const payload = await requestPresetJson(`/interview/load_preset?filename=${encodeURIComponent(filename)}`, signal, 'POST', sessionId)
  if (!isRecord(payload) || !isRecord(payload.preset_config)) throw new Error('预设响应缺少有效的 preset_config 对象。')
  const candidate = payload.preset_config.candidate_config
  const interviewer = payload.preset_config.interviewer_config
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
  const preset: InterviewPreset = {
    candidate_config: { language, education: candidate.education, position: candidate.position, resume: candidate.resume ?? null },
    interviewer_config: { role_identity: interviewer.role_identity, role_responsibilities: interviewer.role_responsibilities ?? '' },
  }
  signal?.throwIfAborted()
  return preset
}
