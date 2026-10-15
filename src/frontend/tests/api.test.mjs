import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import ts from 'typescript'

let moduleId = 0
async function moduleUrl(name, replacements = {}) {
  let source = await readFile(new URL(`../src/api/${name}.ts`, import.meta.url), 'utf8')
  source = source.replace('import.meta.env.VITE_API_BASE_URL', 'undefined')
  for (const [path, url] of Object.entries(replacements)) source = source.replace(`'${path}'`, JSON.stringify(url))
  const code = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2020 },
  }).outputText
  return `data:text/javascript;base64,${Buffer.from(code).toString('base64')}#${moduleId++}`
}

async function loadApi() {
  const candidateUrl = await moduleUrl('candidate')
  const sseUrl = await moduleUrl('sse')
  const interviewUrl = await moduleUrl('interview', { './candidate': candidateUrl, './sse': sseUrl })
  const presetsUrl = await moduleUrl('presets', { './candidate': candidateUrl })
  return { ...await import(candidateUrl), ...await import(interviewUrl), ...await import(sseUrl), ...await import(presetsUrl) }
}

const sessionId = 'c53208a9-db49-4064-9802-ffb548e9a0f5'
const candidate = { education: '本科', position: '后端', language: 'Chinese' }
const interviewer = { role_identity: '技术面试官', role_responsibilities: '围绕项目提问' }
const turn = { role: 'Human', message: '你好', chat_round: 0, dtime: '2026-10-13T10:00:00+08:00' }
const consume = async (stream) => { const events = []; for await (const event of stream) events.push(event); return events }

function mockFetch(t, implementation) {
  const original = globalThis.fetch
  const mock = t.mock.fn(implementation)
  globalThis.fetch = mock
  t.after(() => { globalThis.fetch = original })
  return mock
}

function responseStream(text, onCancel = () => {}) {
  const bytes = new TextEncoder().encode(text)
  let offset = 0
  return new Response(new ReadableStream({
    // 单字节分块覆盖中文 UTF-8 与 CRLF 被拆开的情况。
    pull(controller) {
      if (offset < bytes.length) controller.enqueue(bytes.slice(offset, ++offset))
      else controller.close()
    },
    cancel: onCancel,
  }), { headers: { 'Content-Type': 'text/event-stream; charset=utf-8' } })
}

test('默认中文不跟随浏览器语言；保留显式语言选择', async (t) => {
  const original = Object.getOwnPropertyDescriptor(globalThis, 'navigator')
  Object.defineProperty(globalThis, 'navigator', { configurable: true, value: { language: 'en-US', languages: ['en-US', 'en'] } })
  t.after(() => {
    if (original) Object.defineProperty(globalThis, 'navigator', original)
    else delete globalThis.navigator
  })
  const api = await loadApi()
  assert.equal(api.resolveInterviewLanguage(), 'zh-CN')
  assert.equal(api.resolveInterviewLanguage('   '), 'zh-CN')
  for (const value of ['zh-CN', 'Chinese', '中文']) assert.equal(api.resolveInterviewLanguage(value), 'zh-CN')
  for (const value of ['en-US', 'English', 'en']) assert.equal(api.resolveInterviewLanguage(value), 'en-US')
  const calls = []
  mockFetch(t, async (url, options) => {
    calls.push({ url, options })
    return url.endsWith('/begin') ? Response.json({ session_id: sessionId }) : Response.json(200)
  })
  await api.postCandidateConfig({ education: '本科', position: '后端' }, interviewer)
  assert.equal(JSON.parse(calls[1].options.body).candidate.language, 'zh-CN')
})

test('预设加载使用查询参数和 preset_config 响应，应用到当前 session 后才成功', async (t) => {
  const api = await loadApi()
  const calls = []
  const controller = new AbortController()
  mockFetch(t, async (url, options) => {
    calls.push({ url, options })
    if (url.endsWith('/begin')) return Response.json({ session_id: sessionId })
    if (url.endsWith('/personal_information_config')) return Response.json(200)
    return Response.json(url.endsWith('/read_preset') ? { files: ['后端 #1.json', '后端 #1.json', '.DS_Store', 'notes.txt', 'subfolder'] } : { preset_config: {
      candidate_config: { ...candidate, resume: 'resumes/demo.pdf' },
      interviewer_config: { ...interviewer, role_responsibilities: null },
    } })
  })
  assert.deepEqual(await api.listInterviewPresets(controller.signal), ['后端 #1.json'])
  await api.initializeSession()
  assert.deepEqual(await api.loadInterviewPreset('后端 #1.json', controller.signal), {
    candidate_config: { ...candidate, language: 'zh-CN', resume: 'resumes/demo.pdf' },
    interviewer_config: { ...interviewer, role_responsibilities: '' },
  })
  assert.equal(calls.length, 4)
  assert.equal(calls[0].url, '/interview/read_preset')
  assert.equal(calls[0].options.method, 'GET')
  assert.equal(calls[0].options.body, undefined)
  assert.equal(calls[2].url, `/interview/load_preset?filename=${encodeURIComponent('后端 #1.json')}`)
  assert.equal(calls[2].options.method, 'POST')
  assert.equal(calls[2].options.body, undefined)
  assert.equal(calls[3].url, '/interview/personal_information_config')
  assert.equal(calls[3].options.method, 'POST')
  assert.equal(calls[3].options.signal, controller.signal)
  assert.deepEqual(JSON.parse(calls[3].options.body), {
    session_id: sessionId,
    candidate: { ...candidate, language: 'zh-CN', resume: 'resumes/demo.pdf' },
    interviewer: { ...interviewer, role_responsibilities: '' },
  })
  for (const { options } of [calls[0], calls[2]]) {
    assert.equal(options.cache, 'no-store')
    assert.equal(options.signal, controller.signal)
  }
})

test('预设空列表、错误响应、错误结构和非法路径不会作为有效配置使用', async (t) => {
  const api = await loadApi()
  const mock = mockFetch(t, async () => Response.json({ session_id: sessionId }))
  await api.initializeSession()
  mock.mock.mockImplementation(async () => Response.json({ files: [] }))
  assert.deepEqual(await api.listInterviewPresets(), [])
  for (const files of [['../private.json'], ['folder/a.json'], ['folder\\a.json'], ['a.txt']]) {
    mock.mock.mockImplementation(async () => Response.json({ files }))
    assert.deepEqual(await api.listInterviewPresets(), [])
  }
  for (const files of [[null], 'not-an-array']) {
    mock.mock.mockImplementation(async () => Response.json({ files }))
    await assert.rejects(api.listInterviewPresets(), /列表格式错误/)
  }
  const count = mock.mock.callCount()
  await assert.rejects(api.loadInterviewPreset('../private.json'), /文件名无效/)
  assert.equal(mock.mock.callCount(), count)
  for (const invalid of [null, 200, {}, { candidate_config: candidate, interviewer_config: interviewer },
    { preset_config: { candidate_config: candidate, interviewer_config: {} } },
    { preset_config: { candidate_config: { ...candidate, language: 'fr' }, interviewer_config: interviewer } },
  ]) {
    const before = mock.mock.callCount()
    mock.mock.mockImplementation(async () => Response.json(invalid))
    await assert.rejects(api.loadInterviewPreset('坏文件.json'), /预设/)
    assert.equal(mock.mock.callCount(), before + 1, '无效预设不得提交到 state')
  }
  mock.mock.mockImplementation(async () => Response.json({ detail: '预设不存在' }, { status: 404 }))
  await assert.rejects(api.loadInterviewPreset('已删除.json'), error => error.status === 404 && error.message === '预设不存在')
  mock.mock.mockImplementation(async () => new Response('<html>not json</html>'))
  await assert.rejects(api.listInterviewPresets(), /列表格式错误/)
})

test('预设读取成功但应用失败时不报告加载成功；取消后不再提交配置', async (t) => {
  const api = await loadApi()
  const payload = { preset_config: { candidate_config: candidate, interviewer_config: interviewer } }
  const mock = mockFetch(t, async url => url.endsWith('/begin')
    ? Response.json({ session_id: sessionId })
    : url.includes('/load_preset?') ? Response.json(payload)
    : Response.json({ detail: '配置更新失败' }, { status: 500 }))
  await api.initializeSession()
  await assert.rejects(api.loadInterviewPreset('后端.json'), error => error.status === 500 && error.message === '配置更新失败')
  mock.mock.mockImplementation(async url => url.includes('/load_preset?') ? Response.json(payload) : Response.json(null))
  await assert.rejects(api.loadInterviewPreset('后端.json'), /成功标识/)
  const controller = new AbortController()
  const before = mock.mock.callCount()
  mock.mock.mockImplementation(async () => {
    controller.abort()
    return Response.json(payload)
  })
  await assert.rejects(api.loadInterviewPreset('后端.json', controller.signal), { name: 'AbortError' })
  assert.equal(mock.mock.callCount(), before + 1)
})

test('初始化并发复用；提交完整 Candidate 和 Interviewer；缓存 session', async (t) => {
  const api = await loadApi()
  const calls = []
  let finish
  mockFetch(t, async (url, options) => {
    calls.push({ url, options })
    if (url.endsWith('/begin')) return new Promise(resolve => { finish = () => resolve(Response.json({ session_id: sessionId })) })
    return Response.json(200)
  })
  const init = api.initializeSession()
  const other = api.initializeSession()
  const submit = api.postCandidateConfig(candidate, interviewer)
  assert.equal(calls.length, 1)
  assert.equal(calls[0].options.method, 'GET')
  finish()
  assert.deepEqual(await Promise.all([init, other]), [sessionId, sessionId])
  await submit
  assert.equal(api.getCachedSessionId(), sessionId)
  assert.equal(calls[1].url, '/interview/personal_information_config')
  assert.deepEqual(JSON.parse(calls[1].options.body), {
    session_id: sessionId, candidate: { ...candidate, language: 'zh-CN', resume: null }, interviewer,
  })
  await api.postCandidateConfig({ ...candidate, resume: 'resumes/demo.pdf' }, interviewer)
  assert.equal(calls.length, 3)
  assert.equal(JSON.parse(calls[2].options.body).candidate.resume, 'resumes/demo.pdf')
})

test('422 校验详情及异常成功响应会抛错', async (t) => {
  const api = await loadApi()
  const mock = mockFetch(t, async () => Response.json({ session_id: sessionId }))
  await api.initializeSession()
  mock.mock.mockImplementation(async () => Response.json({ detail: [{ loc: ['body', 'interviewer'], msg: 'Field required' }] }, { status: 422 }))
  await assert.rejects(api.postCandidateConfig(candidate, interviewer), error => error.status === 422 && error.message.includes('body.interviewer'))
  mock.mock.mockImplementation(async () => Response.json(null))
  await assert.rejects(api.postCandidateConfig(candidate, interviewer), /成功标识/)
})

test('POST stream 保留 Graph updates、正确解析分块与心跳并接收 done', async (t) => {
  const api = await loadApi()
  const calls = []
  const update = { InterviewAgent: { messages: [{ type: 'ai', content: '你好，请介绍项目。' }], chat_round: 1 } }
  const wire = `: ping\r\n\r\nevent: message\r\ndata: ${JSON.stringify(update)}\r\n\r\nevent: done\r\ndata: {"session_id":"${sessionId}"}\r\n\r\n`
  mockFetch(t, async (url, options) => {
    calls.push({ url, options })
    return url.endsWith('/begin') ? Response.json({ session_id: sessionId }) : responseStream(wire)
  })
  const events = await consume(api.streamInterviewTurn(turn))
  assert.deepEqual(events, [{ event: 'message', data: update }, { event: 'done', data: { session_id: sessionId } }])
  assert.equal(calls[1].url, '/interview/stream')
  assert.equal(calls[1].options.method, 'POST')
  assert.deepEqual(JSON.parse(calls[1].options.body), { session_id: sessionId, ...turn })
})

test('SSE 多行 data、CR 换行和忽略未完成事件', async () => {
  const api = await loadApi()
  const events = await consume(api.readServerEvents(responseStream('data: first\rdata: second\r\rdata: incomplete').body))
  assert.deepEqual(events, [{ event: 'message', data: 'first\nsecond' }])
})

test('SSE error、缺失 done、错误 session、无效 JSON 均拒绝成功', async (t) => {
  const api = await loadApi()
  let wire = ''
  mockFetch(t, async url => url.endsWith('/begin') ? Response.json({ session_id: sessionId }) : responseStream(wire))
  for (const [text, pattern] of [
    ['event: error\ndata: {"detail":"模型失败"}\n\n', /模型失败/],
    ['event: message\ndata: {}\n\n', /done/],
    ['event: done\ndata: {"session_id":"other"}\n\n', /不一致/],
    ['event: message\ndata: invalid\n\n', /JSON/],
  ]) {
    wire = text
    await assert.rejects(consume(api.streamInterviewTurn(turn)), pattern)
  }
})

test('取消请求会传递 AbortSignal；HTTP 错误保持状态码', async (t) => {
  const api = await loadApi()
  const controller = new AbortController()
  const mock = mockFetch(t, async (url, options) => {
    if (url.endsWith('/begin')) return Response.json({ session_id: sessionId })
    assert.equal(options.signal, controller.signal)
    controller.abort()
    options.signal.throwIfAborted()
  })
  await assert.rejects(consume(api.streamInterviewTurn(turn, controller.signal)), { name: 'AbortError' })
  mock.mock.mockImplementation(async () => Response.json({ detail: '不可用' }, { status: 503 }))
  await assert.rejects(consume(api.streamInterviewTurn(turn)), error => error.status === 503)
})

test('调用者停止迭代时取消读取流', async (t) => {
  const api = await loadApi()
  let cancelled = false
  mockFetch(t, async url => url.endsWith('/begin') ? Response.json({ session_id: sessionId }) : responseStream('data: {}\n\ndata: {}\n\n', () => { cancelled = true }))
  for await (const event of api.streamInterviewTurn(turn)) {
    assert.equal(event.event, 'message')
    break
  }
  assert.equal(cancelled, true)
})

test('将 InterviewAgent 节点更新转换为回复文本和后端轮次', async () => {
  const api = await loadApi()
  assert.deepEqual(api.readInterviewUpdate({ InterviewAgent: {
    chat_round: 2,
    messages: [{ type: 'ai', id: 'reply-1', content: [{ type: 'text', text: '你好' }, { type: 'image', url: 'ignored' }, { type: 'text', text: '！' }] }],
  } }), { chatRound: 2, messages: [{ id: 'reply-1', text: '你好！' }] })
  assert.deepEqual(api.readInterviewUpdate({ OtherAgent: {} }), { messages: [] })
  assert.deepEqual(api.readInterviewUpdate({ InterviewAgent: { chat_round: -1, messages: [{ type: 'human', content: '用户输入' }] } }), { chatRound: undefined, messages: [] })
})
