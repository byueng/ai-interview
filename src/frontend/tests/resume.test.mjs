import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import ts from 'typescript'

async function loadApi() {
  const stub = `export const apiBaseUrl = ''; export const getActiveSessionId = async () => 'test-session'; export const getErrorMessage = (p, f) => p?.detail || f;`
  const stubUrl = `data:text/javascript;base64,${Buffer.from(stub).toString('base64')}`
  const source = (await readFile(new URL('../src/api/resume.ts', import.meta.url), 'utf8')).replace("'./candidate'", JSON.stringify(stubUrl))
  const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText
  return import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`)
}

test('resume upload sends original PDF as multipart file and returns server path', async () => {
  const { uploadResume } = await loadApi()
  const file = new File(['%PDF-1.7\nsample'], 'resume.pdf', { type: 'application/pdf' })
  const originalFetch = globalThis.fetch
  globalThis.fetch = async (url, options) => {
    assert.equal(url, '/interview/sessions/test-session/resume')
    assert.equal(options.method, 'POST')
    assert.equal(options.headers['Content-Type'], undefined)
    assert.deepEqual([...options.body.keys()], ['file'])
    assert.equal(options.body.get('file').name, file.name)
    assert.equal(await options.body.get('file').text(), await file.text())
    return Response.json({ resume: 'resumes/stored.pdf' })
  }
  try { assert.equal(await uploadResume(file), 'resumes/stored.pdf') }
  finally { globalThis.fetch = originalFetch }
})

test('resume rejects invalid files, missing endpoint and invalid success payloads', async () => {
  const { uploadResume } = await loadApi()
  const originalFetch = globalThis.fetch
  globalThis.fetch = async () => { throw new Error('unexpected network request') }
  try {
    await assert.rejects(uploadResume(new File(['text'], 'resume.docx')), /PDF/)
    await assert.rejects(uploadResume(new File([], 'empty.pdf')), /为空/)
    const file = new File(['%PDF'], 'resume.pdf')
    globalThis.fetch = async () => Response.json({}, { status: 404 })
    await assert.rejects(uploadResume(file), /暂未开放/)
    globalThis.fetch = async () => Response.json({})
    await assert.rejects(uploadResume(file), /响应无效/)
    globalThis.fetch = async () => Response.json({ detail: '文件过大' }, { status: 413 })
    await assert.rejects(uploadResume(file), /文件过大/)
  } finally { globalThis.fetch = originalFetch }
})
