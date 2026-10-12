export interface ServerEvent {
  event: string
  data: string
}

// 按行解析，保留跨网络分块的 UTF-8、CRLF 和多行 data。
export async function* readServerEvents(body: ReadableStream<Uint8Array>): AsyncGenerator<ServerEvent> {
  const reader = body.getReader()
  const decoder = new TextDecoder()
  let line = ''
  let previousCR = false
  let event = 'message'
  let data: string[] = []

  function consumeLine(): ServerEvent | undefined {
    const value = line
    line = ''
    if (value === '') {
      const result = data.length ? { event, data: data.join('\n') } : undefined
      event = 'message'
      data = []
      return result
    }
    if (value.startsWith(':')) return
    const colon = value.indexOf(':')
    const field = colon < 0 ? value : value.slice(0, colon)
    let content = colon < 0 ? '' : value.slice(colon + 1)
    if (content.startsWith(' ')) content = content.slice(1)
    if (field === 'event') event = content || 'message'
    if (field === 'data') data.push(content)
  }

  try {
    while (true) {
      const chunk = await reader.read()
      const text = chunk.done ? decoder.decode() : decoder.decode(chunk.value, { stream: true })
      for (const char of text) {
        if (previousCR && char === '\n') {
          previousCR = false
          continue
        }
        previousCR = char === '\r'
        if (char === '\r' || char === '\n') {
          const result = consumeLine()
          if (result) yield result
        } else {
          line += char
        }
      }
      if (chunk.done) break
    }
    // 未以空行结束的事件不完整，不作为成功消息分发。
  } finally {
    await reader.cancel().catch(() => undefined)
    reader.releaseLock()
  }
}
