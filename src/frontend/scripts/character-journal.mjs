import { readFile, readdir, mkdir, copyFile, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const frontend = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const json = async p => JSON.parse((await readFile(p, 'utf8')).replace(/^\uFEFF/, ''))
const idPattern = /^[a-z0-9][a-z0-9_-]*$/
function id(value) {
  if (typeof value !== 'string' || !idPattern.test(value)) throw new Error(`Invalid journal id: ${value}`)
  return value
}
function inside(root, relative) {
  const result = path.resolve(root, relative)
  const rel = path.relative(root, result)
  if (rel.startsWith('..') || path.isAbsolute(rel)) throw new Error(`Path outside journal: ${relative}`)
  return result
}
// The publication format uses Markdown headings and paragraphs. Render text through
// Vue interpolation, never raw HTML from generated/source material.
export function parseStory(markdown, subtitle) {
  const chunks = markdown.replace(/^\uFEFF/, '').replace(/\r\n/g, '\n').trim().split(/\n\s*\n/)
  if (chunks[0]?.startsWith('# ')) chunks.shift()
  if (chunks[0]?.trim() === subtitle) chunks.shift()
  return chunks.filter(Boolean).map(text => {
    const heading = /^(#{2,6})\s+([\s\S]+)$/.exec(text)
    return heading ? { type: 'heading', text: heading[2], level: heading[1].length } : { type: 'paragraph', text }
  })
}
export function resolveImage(raw, characterDir, frontendDir = frontend) {
  const normalized = String(raw).replaceAll('\\', '/')
  // Rebase legacy absolute paths onto this checkout; never read arbitrary paths.
  const charMarker = `/characters/${path.basename(characterDir)}/`
  const marker = normalized.lastIndexOf(charMarker)
  if (marker >= 0) return inside(characterDir, normalized.slice(marker + charMarker.length))
  const assetMarker = 'src/frontend/src/assets/'
  const assetIndex = normalized.indexOf(assetMarker)
  if (assetIndex >= 0) return inside(path.join(frontendDir, 'src/assets'), normalized.slice(assetIndex + assetMarker.length))
  if (path.isAbsolute(normalized) || /^[a-z]:/i.test(normalized)) throw new Error(`Unsupported image path: ${raw}`)
  return inside(characterDir, normalized)
}
export async function exportJournal({ sourceRoot = process.env.CHARACTER_JOURNAL_ROOT || path.resolve(frontend, '../data/character-journal/characters'), outputRoot = path.join(frontend, 'public/character-journal'), frontendDir = frontend } = {}) {
  const characters = [], assets = []
  let entries
  try { entries = await readdir(sourceRoot, { withFileTypes: true }) }
  catch (error) { if (error.code !== 'ENOENT') throw error; entries = [] }
  for (const entry of entries.sort((a,b) => a.name.localeCompare(b.name))) {
    if (!entry.isDirectory()) continue
    const characterDir = path.join(sourceRoot, entry.name)
    let plan
    try { plan = await json(path.join(characterDir, 'publication-plan.json')) }
    catch (error) { if (error.code === 'ENOENT') continue; throw error }
    if (plan.status !== 'accepted') continue
    const characterId = id(plan.characterId)
    if (characterId !== entry.name) throw new Error(`Character directory/id mismatch: ${entry.name}`)
    const manifest = await json(path.join(characterDir, 'preview-manifest.json'))
    const units = [], seen = new Set()
    for (const planned of [...plan.units].sort((a,b) => a.displayOrder - b.displayOrder)) {
      const unitId = id(planned.unitId)
      if (seen.has(unitId)) throw new Error(`Duplicate unit: ${unitId}`)
      seen.add(unitId)
      const unitDir = path.join(characterDir, 'units', unitId)
      const profile = await json(path.join(unitDir, 'profile.json'))
      const subtitle = profile.subtitle?.text || planned.subtitle?.text || ''
      const blocks = parseStory(await readFile(path.join(unitDir, 'story.md'), 'utf8'), subtitle)
      const asset = manifest.units.find(u => u.unitId === unitId)
      if (!asset) throw new Error(`Missing image manifest for ${characterId}/${unitId}`)
      const source = resolveImage(asset.imagePath, characterDir, frontendDir)
      const ext = path.extname(source).toLowerCase()
      if (!['.png','.jpg','.jpeg','.webp'].includes(ext)) throw new Error(`Unsupported image: ${source}`)
      const filename = `${characterId}/${unitId}${ext}`
      // Read first so missing assets fail before publishing a new index.
      await readFile(source)
      assets.push({ source, destination: path.join(outputRoot, filename) })
      units.push({ id: unitId, kind: planned.kind, title: profile.title || planned.title, subtitle, sourceLabel: planned.sourceLabel || '', blocks, image: `character-journal/${filename}`, alt: asset.alt || planned.title, caption: asset.caption || '' })
    }
    const overviews = units.filter(u => u.kind === 'overview')
    if (overviews.length !== 1) throw new Error(`${characterId} must have exactly one overview`)
    const overview = overviews[0]
    const intro = overview.blocks.find(b => b.type === 'paragraph')?.text || ''
    characters.push({ id: characterId, name: plan.characterName || overview.title.replace(/人物总览$/, ''), book: plan.bibliography?.title || '', author: plan.bibliography?.author || '', intro, overview, chapters: units.filter(u => u.kind !== 'overview') })
  }
  await mkdir(outputRoot, { recursive: true })
  for (const asset of assets) {
    await mkdir(path.dirname(asset.destination), { recursive: true })
    await copyFile(asset.source, asset.destination)
  }
  await writeFile(path.join(outputRoot, 'index.json'), JSON.stringify({ schemaVersion: 1, characters }, null, 2) + '\n')
  return characters
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const characters = await exportJournal()
  console.log(`Character journal: ${characters.length} characters, ${characters.reduce((n,c) => n+c.chapters.length,0)} chapters`)
}
