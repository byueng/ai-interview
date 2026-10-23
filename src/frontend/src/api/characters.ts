export interface StoryBlock { type: 'heading' | 'paragraph'; text: string; level?: number }
export interface JournalUnit { id: string; kind: string; title: string; subtitle: string; sourceLabel: string; blocks: StoryBlock[]; image: string; alt: string; caption: string }
export interface JournalCharacter { id: string; name: string; book: string; author: string; intro: string; overview: JournalUnit; chapters: JournalUnit[] }
export const journalAsset = (relative: string) => `${import.meta.env.BASE_URL}${relative}`
export async function loadCharacters(): Promise<JournalCharacter[]> {
  const response = await fetch(journalAsset('character-journal/index.json'))
  if (!response.ok) throw new Error('人物志暂时无法读取，请稍后重试。')
  const data = await response.json()
  if (data.schemaVersion !== 1 || !Array.isArray(data.characters)) throw new Error('人物志数据格式不受支持。')
  return data.characters
}
