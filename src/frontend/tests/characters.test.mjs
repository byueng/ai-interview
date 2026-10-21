import test from 'node:test'
import assert from 'node:assert/strict'
import { mkdtemp, mkdir, writeFile, readFile } from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import { exportJournal, parseStory, resolveImage } from '../scripts/character-journal.mjs'

test('Markdown preserves sections, strips only initial title/subtitle, treats HTML as text', () => {
  const blocks = parseStory('\uFEFF# Title\r\n\r\nSubtitle\r\n\r\n## Heading\r\n\r\n<script>alert(1)</script>\r\n\r\nSubtitle', 'Subtitle')
  assert.deepEqual(blocks, [{type:'heading',text:'Heading',level:2},{type:'paragraph',text:'<script>alert(1)</script>'},{type:'paragraph',text:'Subtitle'}])
})
test('Moved Windows image paths rebase; traversal and unrelated absolute paths fail', () => {
  const root=path.resolve('fixtures/characters/arthas')
  assert.equal(resolveImage('C:\\old\\src\\data\\character-journal\\characters\\arthas\\units\\dream\\images\\v1.png',root),path.join(root,'units/dream/images/v1.png'))
  assert.throws(()=>resolveImage('../../private.png',root))
  assert.throws(()=>resolveImage('C:/private/image.png',root))
})
test('Export supports multiple characters with zero or many ordered chapters and relocatable assets', async () => {
  const temp=await mkdtemp(path.join(os.tmpdir(),'journal-test-'))
  const sourceRoot=path.join(temp,'characters'), outputRoot=path.join(temp,'public')
  for (const [characterId,count] of [['alpha',0],['beta',6]]) {
    const char=path.join(sourceRoot,characterId)
    const units=Array.from({length:count+1},(_,i)=>({unitId:i?`part-${i}`:'overview',kind:i?'section':'overview',displayOrder:i,title:i?`Chapter ${i}`:`${characterId}人物总览`,subtitle:{text:'old'}}))
    const manifest={units:[]}
    for(const unit of units) {
      const dir=path.join(char,'units',unit.unitId)
      await mkdir(dir,{recursive:true})
      await writeFile(path.join(dir,'story.md'),'# Title\n\nApproved\n\n## Heading\n\nContent')
      await writeFile(path.join(dir,'profile.json'),JSON.stringify({title:unit.title,subtitle:{text:'Approved'}}))
      await writeFile(path.join(dir,'image.png'),'image fixture')
      manifest.units.push({unitId:unit.unitId,imagePath:`X:/old/characters/${characterId}/units/${unit.unitId}/image.png`,caption:'Caption'})
    }
    await writeFile(path.join(char,'publication-plan.json'),JSON.stringify({characterId,status:'accepted',bibliography:{title:'Book'},units:units.reverse()}))
    await writeFile(path.join(char,'preview-manifest.json'),JSON.stringify(manifest))
  }
  const result=await exportJournal({sourceRoot,outputRoot})
  assert.deepEqual(result.map(c=>c.chapters.length),[0,6])
  assert.equal(result[1].chapters[0].id,'part-1')
  assert.equal(result[1].overview.subtitle,'Approved')
  const exported=await readFile(path.join(outputRoot,'index.json'),'utf8')
  assert.ok(!exported.includes('X:/old'))
  assert.equal(await readFile(path.join(outputRoot,'beta/part-6.png'),'utf8'),'image fixture')
})
test('Missing data directory exports empty collection rather than mock content', async()=>{
  const temp=await mkdtemp(path.join(os.tmpdir(),'journal-empty-'))
  assert.deepEqual(await exportJournal({sourceRoot:path.join(temp,'missing'),outputRoot:path.join(temp,'public')}),[])
})
