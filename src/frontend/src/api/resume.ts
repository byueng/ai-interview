import { apiBaseUrl, getActiveSessionId, getErrorMessage } from './candidate'

// Proposed backend contract: multipart file -> { resume: string } (stored PDF path).
export async function uploadResume(file: File, signal?: AbortSignal): Promise<string> {
  if (!/\.pdf$/i.test(file.name) || (file.type && !['application/pdf', 'application/octet-stream'].includes(file.type))) {
    throw new Error('请选择 PDF 格式的简历。')
  }
  if (!file.size) throw new Error('该文件为空，请重新选择。')
  const sessionId = await getActiveSessionId(signal)
  const body = new FormData()
  body.append('file', file, file.name)
  const response = await fetch(`${apiBaseUrl}/interview/sessions/${encodeURIComponent(sessionId)}/resume`, {
    method: 'POST', headers: { Accept: 'application/json' }, body, signal,
  })
  const payload = await response.json().catch(() => null)
  if (!response.ok) {
    if ([404, 405, 501].includes(response.status)) throw new Error('简历上传服务暂未开放，请稍后重试。')
    throw new Error(getErrorMessage(payload, '上传失败，请稍后重试。'))
  }
  if (typeof payload?.resume !== 'string' || !payload.resume.trim()) throw new Error('上传响应无效，请稍后重试。')
  return payload.resume
}
