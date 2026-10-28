import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import ts from 'typescript'

async function loadApi() {
  const url = code => `data:text/javascript;base64,${Buffer.from(ts.transpileModule(code, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2020 } }).outputText).toString('base64')}`
  const resumeUrl = url(await readFile(new URL('../src/api/resume.ts', import.meta.url), 'utf8'))
  const source = (await readFile(new URL('../src/api/candidate_config.ts', import.meta.url), 'utf8'))
    .replace('import.meta.env.VITE_API_BASE_URL', 'undefined').replace("'./resume'", JSON.stringify(resumeUrl))
  return import(url(source) + '#' + Math.random())
}
const config = { language: 'zh-CN', education: '本科', position: '后端' }
const interviewer = { role_identity: '面试官', role_responsibilities: '技术面试' }

function mockFetch(t, implementation) {
  const original = globalThis.fetch
  globalThis.fetch = t.mock.fn(implementation)
  t.after(() => { globalThis.fetch = original })
}

function setup(t, response) {
  mockFetch(t, async (url, options) => {
    if (url.endsWith('/begin')) return Response.json({ session_id: 'test-session' })
    return response(url, options)
  })
}

test('one multipart request saves configuration and original PDF; browser sets boundary', async t => {
  const api = await loadApi()
  const file = new File(['%PDF-1.7\nsample'], 'resume.pdf', { type: 'application/pdf' })
  let submissions = 0
  setup(t, async (url, options) => {
    submissions++
    assert.equal(url, '/interview/personal_information_config')
    assert.equal(options.method, 'POST')
    assert.equal(options.headers['Content-Type'], undefined)
    assert.deepEqual([...options.body.keys()], ['session_id', 'config', 'file'])
    assert.equal(options.body.get('session_id'), 'test-session')
    assert.deepEqual(JSON.parse(options.body.get('config')), { candidate_config: { ...config, resume: null }, interviewer_config: interviewer })
    assert.equal(await options.body.get('file').text(), await file.text())
    return Response.json({ session_id: 'test-session', resume: '/data/swap/test-session/简历.pdf' })
  })
  await api.initializeSession()
  assert.equal(await api.postCandidateConfig(config, interviewer, file), '/data/swap/test-session/简历.pdf')
  assert.equal(submissions, 1)
})

test('PDF validation fails before any request', async t => {
  const api = await loadApi()
  mockFetch(t, async () => { throw new Error('unexpected request') })
  for (const [file, error] of [
    [new File(['x'], 'resume.docx'), /PDF/],
    [new File([], 'empty.pdf'), /为空/],
    [new File([new Uint8Array(10 * 1024 * 1024 + 1)], 'large.pdf'), /10 MiB/],
  ]) await assert.rejects(api.postCandidateConfig(config, interviewer, file), error)
  assert.equal(fetch.mock.callCount(), 0)
})

test('combined save preserves backend errors and rejects invalid success responses', async t => {
  const api = await loadApi()
  let response
  setup(t, () => response)
  await api.initializeSession()
  for (const status of [400, 409, 410, 500]) {
    response = Response.json({ detail: '保存未完成' }, { status })
    await assert.rejects(api.postCandidateConfig(config, interviewer), e => e.status === status && e.message === '保存未完成')
  }
  for (const payload of [200, {}, { session_id: 'other', resume: null }, { session_id: 'test-session', resume: '' }]) {
    response = Response.json(payload)
    await assert.rejects(api.postCandidateConfig(config, interviewer), /成功标识/)
  }
  response = Response.json({ session_id: 'test-session', resume: null })
  await assert.rejects(api.postCandidateConfig(config, interviewer, new File(['%PDF-'], 'a.pdf')), /成功标识/)
})
