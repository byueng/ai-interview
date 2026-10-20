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
const turn = { message: '你好', chat_round: 0 }
const consume = async (stream) => { const events = []; for await (const event of stream) events.push(event); return events }

async function loadInterviewStore() {
  const candidateUrl = await moduleUrl('candidate')
  const sseUrl = await moduleUrl('sse')
  const interviewUrl = await moduleUrl('interview', { './candidate': candidateUrl, './sse': sseUrl })
  const storeUrl = await moduleUrl('../state/interview', {
    vue: import.meta.resolve('vue'), '../api/candidate': candidateUrl, '../api/interview': interviewUrl,
  })
  return import(storeUrl)
}
const storeSnapshot = (overrides = {}) => ({
  session_id: sessionId, status: 'active', chat_round: 0, expires_at: 9999999999,
  candidate_config: { ...candidate, language: 'zh-CN', resume: null }, interviewer_config: interviewer,
  messages: [], ...overrides,
})

test('跨页面共享状态：恢复配置与历史，已有配置不重复提交', async (t) => {
  const store = await loadInterviewStore()
  const requests = mockFetch(t, async (url) => url.endsWith('/begin')
    ? Response.json({ session_id: sessionId })
    : Response.json(storeSnapshot({ chat_round: 1, messages: [{ type: 'human', content: '我的经历' }, { type: 'ai', content: '继续说说' }] })))
  assert.equal(await store.connect('page'), true)
  assert.equal(store.configured.value, true)
  assert.equal(store.interview.messages.length, 2)
  assert.equal(store.interview.round, 1)
  const requestCount = requests.mock.callCount()
  assert.equal(await store.saveConfiguration(), true)
  assert.equal(requests.mock.callCount(), requestCount)
  store.interview.candidate.position = '新的岗位'
  assert.equal(store.configured.value, false)
  assert.equal(store.canSend.value, false)
})

test('共享对话在进行中禁止重复发送和新建，完成后更新轮次并清空草稿', async (t) => {
  const store = await loadInterviewStore()
  let streamController
  const requests = mockFetch(t, async (url) => {
    if (url.endsWith('/begin')) return Response.json({ session_id: sessionId })
    if (url.endsWith('/stream')) return new Response(new ReadableStream({ start(controller) { streamController = controller } }), { headers: { 'Content-Type': 'text/event-stream' } })
    return Response.json(storeSnapshot())
  })
  await store.connect('page')
  store.interview.draft = '我的回答'
  const pending = store.sendMessage()
  await new Promise(resolve => setImmediate(resolve))
  assert.equal(store.busy.value, true)
  assert.equal(store.canSend.value, false)
  const count = requests.mock.callCount()
  await store.sendMessage()
  assert.equal(await store.connect('new'), false)
  assert.equal(requests.mock.callCount(), count)
  streamController.enqueue(new TextEncoder().encode(`event: message\ndata: ${JSON.stringify({ InterviewAgent: { chat_round: 1, messages: [{ type: 'ai', id: 'reply-1', content: '请介绍项目' }] } })}\n\nevent: done\ndata: ${JSON.stringify({ session_id: sessionId })}\n\n`))
  streamController.close()
  await pending
  assert.equal(store.interview.sending, false)
  assert.equal(store.interview.draft, '')
  assert.equal(store.interview.round, 1)
  assert.deepEqual(store.interview.messages.map(m => m.text), ['我的回答', '请介绍项目'])
})

test('连接中断保留不确定回答并阻止回车重发，同步后清除错误', async (t) => {
  const store = await loadInterviewStore()
  const requests = mockFetch(t, async (url) => {
    if (url.endsWith('/begin')) return Response.json({ session_id: sessionId })
    if (url.endsWith('/stream')) return responseStream('event: error\ndata: {"message":"测试中断"}\n\n')
    return Response.json(storeSnapshot())
  })
  await store.connect('page')
  store.interview.draft = '尚未确认的回答'
  await store.sendMessage()
  assert.match(store.interview.streamError, /同步会话/)
  assert.equal(store.interview.messages[0].uncertain, true)
  assert.equal(store.canSend.value, false)
  const count = requests.mock.callCount()
  await store.sendMessage()
  assert.equal(requests.mock.callCount(), count)
  await store.connect('continue')
  assert.equal(store.interview.streamError, '')
  assert.equal(store.interview.messages.length, 0)
})

test('结束失败保留会话和历史，确认成功后才进入结束状态', async (t) => {
  const store = await loadInterviewStore()
  let endSucceeded = false
  mockFetch(t, async (url) => {
    if (url.endsWith('/begin')) return Response.json({ session_id: sessionId })
    if (url.endsWith('/end')) return endSucceeded ? Response.json({ session_id: sessionId, status: 'ended' }) : Response.json({ detail: '暂时不可用' }, { status: 503 })
    return Response.json(storeSnapshot({ messages: [{ type: 'human', content: '保留这条对话' }] }))
  })
  await store.connect('page')
  assert.equal(await store.finishSession(), false)
  assert.equal(store.interview.status, 'ready')
  assert.equal(store.interview.messages.length, 1)
  endSucceeded = true
  assert.equal(await store.finishSession(), true)
  assert.equal(store.interview.status, 'ended')
  assert.equal(store.interview.messages[0].text, '保留这条对话')
})

test('对话导出包含实际配置、轮次、双方内容与未确认标记', async (t) => {
  const store = await loadInterviewStore()
  store.interview.candidate.position = '后端工程师'
  store.interview.round = 2
  store.interview.messages = [{ id: 1, role: 'candidate', text: '我的回答', uncertain: true }, { id: 2, role: 'interviewer', text: '请继续介绍' }]
  let exported
  const link = { href: '', download: '', click: t.mock.fn() }
  const oldDocument = globalThis.document
  globalThis.document = { createElement: name => { assert.equal(name, 'a'); return link } }
  t.after(() => { if (oldDocument === undefined) delete globalThis.document; else globalThis.document = oldDocument })
  t.mock.method(URL, 'createObjectURL', blob => { exported = blob; return 'blob:local-test' })
  store.downloadTranscript()
  assert.equal(link.click.mock.callCount(), 1)
  assert.equal(link.download, '面试对话记录.txt')
  assert.equal(exported.type, 'text/plain;charset=utf-8')
  assert.match(await exported.text(), /后端工程师 · 对话记录\n已完成 2 轮/)
  assert.match(await exported.text(), /我（完成状态待确认）\n我的回答/)
  assert.match(await exported.text(), /面试官\n请继续介绍/)
})

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
  assert.equal(JSON.parse(calls[1].options.body).candidate_config.language, 'zh-CN')
})

test('删除预设通过 POST 查询参数传完整文件名，不创建 session 或提交配置', async (t) => {
  const api = await loadApi()
  const controller = new AbortController()
  const mock = mockFetch(t, async () => Response.json(200))
  await api.deleteInterviewPreset('后端 #1 & 2.json', controller.signal)
  assert.equal(mock.mock.callCount(), 1)
  const [url, options] = mock.mock.calls[0].arguments
  assert.equal(url, `/interview/del_preset?filename=${encodeURIComponent('后端 #1 & 2.json')}`)
  assert.equal(options.method, 'POST')
  assert.equal(options.body, undefined)
  assert.equal(options.signal, controller.signal)
})

test('删除预设拒绝非法路径、错误响应及未确认成功的结果', async (t) => {
  const api = await loadApi()
  const mock = mockFetch(t, async () => Response.json(200))
  for (const filename of ['../secret.json', 'dir/file.json', 'dir\\file.json', 'notes.txt', '']) {
    await assert.rejects(api.deleteInterviewPreset(filename), /文件名无效/)
  }
  assert.equal(mock.mock.callCount(), 0)
  for (const body of [null, {}, '200', false]) {
    mock.mock.mockImplementation(async () => Response.json(body))
    await assert.rejects(api.deleteInterviewPreset('后端.json'), /成功标识/)
  }
  mock.mock.mockImplementation(async () => Response.json({ detail: '删除失败' }, { status: 500 }))
  await assert.rejects(api.deleteInterviewPreset('后端.json'), error => error.status === 500 && error.message === '删除失败')
  const controller = new AbortController()
  controller.abort()
  const before = mock.mock.callCount()
  await assert.rejects(api.deleteInterviewPreset('后端.json', controller.signal), { name: 'AbortError' })
  assert.equal(mock.mock.callCount(), before)
})

test('预设加载使用查询文件名和 begin 的 UUID 字符串请求体，不重复提交配置', async (t) => {
  const api = await loadApi()
  const calls = []
  const controller = new AbortController()
  mockFetch(t, async (url, options) => {
    calls.push({ url, options })
    if (url.endsWith('/begin')) return Response.json({ session_id: sessionId })
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
  assert.equal(calls.length, 3)
  assert.equal(calls[0].url, '/interview/read_preset')
  assert.equal(calls[0].options.method, 'GET')
  assert.equal(calls[0].options.body, undefined)
  assert.equal(calls[2].url, `/interview/load_preset?filename=${encodeURIComponent('后端 #1.json')}`)
  assert.equal(calls[2].options.method, 'POST')
  assert.equal(calls[2].options.headers['Content-Type'], 'application/json')
  assert.equal(calls[2].options.body, JSON.stringify(sessionId))
  assert.equal(calls.filter(call => call.url.endsWith('/begin')).length, 1)
  assert.equal(calls.some(call => call.url.endsWith('/personal_information_config')), false)
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
    assert.equal(mock.mock.callCount(), before + 1, '无效响应不得触发额外配置请求')
  }
  mock.mock.mockImplementation(async () => Response.json({ detail: '预设不存在' }, { status: 404 }))
  await assert.rejects(api.loadInterviewPreset('已删除.json'), error => error.status === 404 && error.message === '预设不存在')
  mock.mock.mockImplementation(async () => new Response('<html>not json</html>'))
  await assert.rejects(api.listInterviewPresets(), /列表格式错误/)
})

test('预设加载等待正在进行的 begin，并复用同一个 session', async (t) => {
  const api = await loadApi()
  const calls = []
  let finish
  mockFetch(t, async (url, options) => {
    calls.push({ url, options })
    if (url.endsWith('/begin')) return new Promise(resolve => { finish = () => resolve(Response.json({ session_id: sessionId })) })
    return Response.json({ preset_config: { candidate_config: candidate, interviewer_config: interviewer } })
  })
  const init = api.initializeSession()
  const loading = api.loadInterviewPreset('后端.json')
  assert.equal(calls.length, 1)
  finish()
  await Promise.all([init, loading])
  assert.equal(calls.length, 2)
  assert.equal(JSON.parse(calls[1].options.body), sessionId)
  await api.loadInterviewPreset('另一个.json')
  assert.equal(calls.length, 3)
  assert.equal(JSON.parse(calls[2].options.body), sessionId)
})

test('预设加载失败或取消时不报告成功，也不回退到个人配置接口', async (t) => {
  const api = await loadApi()
  const payload = { preset_config: { candidate_config: candidate, interviewer_config: interviewer } }
  const mock = mockFetch(t, async url => url.endsWith('/begin')
    ? Response.json({ session_id: sessionId })
    : Response.json({ detail: '配置更新失败' }, { status: 500 }))
  await api.initializeSession()
  await assert.rejects(api.loadInterviewPreset('后端.json'), error => error.status === 500 && error.message === '配置更新失败')
  mock.mock.mockImplementation(async () => Response.json(null))
  await assert.rejects(api.loadInterviewPreset('后端.json'), /preset_config/)
  const controller = new AbortController()
  const before = mock.mock.callCount()
  mock.mock.mockImplementation(async () => {
    controller.abort()
    return Response.json(payload)
  })
  await assert.rejects(api.loadInterviewPreset('后端.json', controller.signal), { name: 'AbortError' })
  assert.equal(mock.mock.callCount(), before + 1)
  await assert.rejects(api.loadInterviewPreset('后端.json', controller.signal), { name: 'AbortError' })
  assert.equal(mock.mock.callCount(), before + 1, '已取消请求不能继续发送')
  assert.equal(mock.mock.calls.some(call => call.arguments[0].endsWith('/personal_information_config')), false)
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
    session_id: sessionId, candidate_config: { ...candidate, language: 'zh-CN', resume: null }, interviewer_config: interviewer,
  })
  await api.postCandidateConfig({ ...candidate, resume: 'resumes/demo.pdf' }, interviewer)
  assert.equal(calls.length, 3)
  assert.equal(JSON.parse(calls[2].options.body).candidate_config.resume, 'resumes/demo.pdf')
})

test('422 校验详情及异常成功响应会抛错', async (t) => {
  const api = await loadApi()
  const mock = mockFetch(t, async () => Response.json({ session_id: sessionId }))
  await api.initializeSession()
  mock.mock.mockImplementation(async () => Response.json({ detail: [{ loc: ['body', 'interviewer_config'], msg: 'Field required' }] }, { status: 422 }))
  await assert.rejects(api.postCandidateConfig(candidate, interviewer), error => error.status === 422 && error.message.includes('body.interviewer_config'))
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

function browserStorage(t, navigationType, initialSession = sessionId) {
  const storage = new Map(initialSession ? [['ai-interview.session-id', initialSession]] : [])
  const originalWindow = Object.getOwnPropertyDescriptor(globalThis, 'window')
  Object.defineProperty(globalThis, 'window', { configurable: true, value: { sessionStorage: {
    getItem: key => storage.get(key) ?? null,
    setItem: (key, value) => storage.set(key, value),
    removeItem: key => storage.delete(key),
  } } })
  t.mock.method(performance, 'getEntriesByType', () => [{ type: navigationType }])
  t.after(() => {
    if (originalWindow) Object.defineProperty(globalThis, 'window', originalWindow)
    else delete globalThis.window
  })
  return storage
}

const snapshot = id => ({ session_id: id, status: 'active', chat_round: 2,
  expires_at: 100000, candidate_config: candidate, interviewer_config: interviewer,
  messages: [{ type: 'human', content: '历史输入' }, { type: 'ai', content: '历史回复' }],
})

test('刷新恢复后端配置、历史和轮次，不调用 begin', async t => {
  browserStorage(t, 'reload')
  const api = await loadApi()
  const mock = mockFetch(t, async () => Response.json(snapshot(sessionId)))
  assert.deepEqual(await api.openPageSession(), snapshot(sessionId))
  assert.equal(mock.mock.callCount(), 1)
  assert.equal(mock.mock.calls[0].arguments[0], `/interview/sessions/${sessionId}`)
})

test('新标签页即使复制了 sessionStorage 仍新建独立会话', async t => {
  const storage = browserStorage(t, 'navigate')
  const api = await loadApi()
  const newId = 'ae57a316-7794-44a5-a038-7278c05547ef'
  const mock = mockFetch(t, async url => Response.json(url.endsWith('/begin') ? { session_id: newId } : snapshot(newId)))
  assert.equal((await api.openPageSession()).session_id, newId)
  assert.equal(storage.get('ai-interview.session-id'), newId)
  assert.equal(mock.mock.callCount(), 2)
})

test('旧会话失效或暂时失败时保留 ID 并提示，不偷偷新建或重发', async t => {
  const storage = browserStorage(t, 'reload')
  const api = await loadApi()
  const mock = mockFetch(t, async () => Response.json({ detail: '会话不可用' }, { status: 404 }))
  for (const status of [404, 410, 409, 500]) {
    mock.mock.mockImplementation(async () => Response.json({ detail: '会话不可用' }, { status }))
    await assert.rejects(api.openPageSession(), error => error.status === status)
  }
  assert.equal(mock.mock.callCount(), 4)
  assert.ok(mock.mock.calls.every(call => !call.arguments[0].endsWith('/begin')))
  assert.equal(storage.get('ai-interview.session-id'), sessionId)
})

test('结束会话确认响应；主动新建成功才替换当前 ID', async t => {
  const storage = browserStorage(t, 'reload')
  const api = await loadApi()
  const mock = mockFetch(t, async () => Response.json({ session_id: sessionId, status: 'ended' }))
  await api.endCurrentSession()
  assert.equal(mock.mock.calls[0].arguments[0], `/interview/sessions/${sessionId}/end`)
  assert.equal(mock.mock.calls[0].arguments[1].method, 'POST')
  mock.mock.mockImplementation(async () => Response.json({ detail: '创建失败' }, { status: 500 }))
  await assert.rejects(api.initializeSession())
  assert.equal(storage.get('ai-interview.session-id'), sessionId)
  const newId = 'ae57a316-7794-44a5-a038-7278c05547ef'
  mock.mock.mockImplementation(async () => Response.json({ session_id: newId }))
  assert.equal(await api.initializeSession(), newId)
  assert.equal(storage.get('ai-interview.session-id'), newId)
})
