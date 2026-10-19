import { apiBaseUrl, ApiRequestError, getActiveSessionId, getErrorMessage } from './candidate'
import { readServerEvents } from './sse'

export interface AgentRequest {
  session_id: string
  message: string
}

// 会话标识由连接层补入；角色、轮次和时间由服务端管理。
export type InterviewTurnInput = Omit<AgentRequest, 'session_id'>

// /stream 直接返回 Graph updates，当前并未使用 schemas.AgentResponse。
export type GraphUpdate = Record<string, unknown>

export function readInterviewUpdate(data: GraphUpdate): { messages: Array<{ id?: string; text: string }>; chatRound?: number } {
  const update = data.InterviewAgent
  if (!isRecord(update)) return { messages: [] }
  const messages: Array<{ id?: string; text: string }> = []
  if (Array.isArray(update.messages)) {
    for (const message of update.messages) {
      if (!isRecord(message) || message.type !== 'ai') continue
      const text = typeof message.content === 'string' ? message.content
        : Array.isArray(message.content) ? message.content.map((block: unknown) => {
          if (typeof block === 'string') return block
          return isRecord(block) && block.type === 'text' && typeof block.text === 'string' ? block.text : ''
        }).join('') : ''
      if (text) messages.push({ id: typeof message.id === 'string' ? message.id : undefined, text })
    }
  }
  return { messages, chatRound: typeof update.chat_round === 'number' && Number.isInteger(update.chat_round) && update.chat_round >= 0 ? update.chat_round : undefined }
}
export type InterviewStreamEvent =
  | { event: 'message'; data: GraphUpdate }
  | { event: 'done'; data: { session_id: string } }

export class InterviewStreamError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'InterviewStreamError'
  }
}

export async function* streamInterviewTurn(
  input: InterviewTurnInput,
  signal?: AbortSignal,
): AsyncGenerator<InterviewStreamEvent> {
  const sessionId = await getActiveSessionId(signal)
  signal?.throwIfAborted()
  const body: AgentRequest = {
    session_id: sessionId,
    message: input.message,
  }
  const response = await fetch(`${apiBaseUrl}/interview/stream`, {
    method: 'POST',
    headers: { Accept: 'text/event-stream', 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  })
  if (!response.ok) {
    const payload: unknown = await response.json().catch(() => null)
    throw new ApiRequestError(response.status, getErrorMessage(payload, response.statusText))
  }
  if (!response.headers.get('content-type')?.toLowerCase().startsWith('text/event-stream') || !response.body) {
    await response.body?.cancel()
    throw new InterviewStreamError('面试接口未返回 SSE 响应。')
  }

  for await (const item of readServerEvents(response.body)) {
    signal?.throwIfAborted()
    if (!['message', 'error', 'done'].includes(item.event)) continue
    let data: unknown
    try {
      data = JSON.parse(item.data)
    } catch {
      throw new InterviewStreamError('面试事件包含无效 JSON。')
    }
    if (!isRecord(data)) throw new InterviewStreamError('面试事件数据格式错误。')
    if (item.event === 'error') {
      throw new InterviewStreamError(getErrorMessage(data, '面试处理失败。'))
    }
    if (item.event === 'done') {
      if (data.session_id !== sessionId) throw new InterviewStreamError('完成事件的 session_id 与当前请求不一致。')
      yield { event: 'done', data: { session_id: sessionId } }
      return
    }
    yield { event: 'message', data }
  }
  throw new InterviewStreamError('面试连接在收到 done 事件前中断。')
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}
