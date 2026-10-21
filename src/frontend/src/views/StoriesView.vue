<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { ArrowUpRight, ArrowLeft, Search } from 'lucide-vue-next'
import { loadCharacters, journalAsset, type JournalCharacter } from '../api/characters'
const route = useRoute()
const characters = ref<JournalCharacter[]>([])
const loading = ref(true)
const error = ref('')
const query = ref('')
async function load() {
  loading.value = true
  error.value = ''
  try { characters.value = await loadCharacters() }
  catch (reason) { error.value = reason instanceof Error ? reason.message : '读取失败，请重试。' }
  finally { loading.value = false }
}
onMounted(load)
const current = computed(() => characters.value.find(c => c.id === route.params.slug))
const selected = computed(() => route.params.chapter ? current.value?.chapters.find(c => c.id === route.params.chapter) : current.value?.overview)
const filtered = computed(() => characters.value.filter(c => `${c.name}${c.book}${c.overview.subtitle}`.toLowerCase().includes(query.value.trim().toLowerCase())))
const featured = computed(() => characters.value[0])
const backdrop = computed(() => selected.value?.image || (!route.params.slug ? featured.value?.overview.image : undefined))
const characterUrl = (id: string) => `/stories/${encodeURIComponent(id)}`
</script>

<template>
  <div class="characters-page">
    <Teleport v-if="backdrop" to=".app-frame" defer>
      <div class="journal-acrylic" aria-hidden="true">
        <img :src="journalAsset(backdrop)" alt="" class="journal-acrylic-art" />
        <div class="journal-acrylic-tint" />
        <div class="journal-acrylic-grain" />
      </div>
    </Teleport>
    <div v-if="loading" class="story-empty" role="status">正在翻开人物档案……</div>
    <div v-else-if="error" class="story-empty" role="alert"><p>{{ error }}</p><button class="button secondary" @click="load">重新读取</button></div>
    <template v-else-if="!route.params.slug">
      <header class="characters-heading"><div><p class="eyebrow">THE CHARACTER JOURNAL</p><h1>人物志<span>每一个人，都是一个故事。</span></h1></div><p>读一个人的来路，<br />再走进他生命中的每一章。</p></header>
      <RouterLink v-if="featured" :to="characterUrl(featured.id)" class="story-feature">
        <img :src="journalAsset(featured.overview.image)" :alt="featured.overview.alt" class="cover-image" />
        <div class="feature-copy"><p class="eyebrow">本期人物</p><p class="story-meta">《{{ featured.book }}》</p><h2>{{ featured.name }}</h2><blockquote>{{ featured.overview.subtitle }}</blockquote><p class="story-intro excerpt">{{ featured.intro }}</p><span class="story-read">人物总览 · {{ featured.chapters.length }} 篇故事 <ArrowUpRight :size="18" /></span></div>
      </RouterLink>
      <section class="story-collection" aria-labelledby="collection-title">
        <div class="collection-heading"><h2 id="collection-title">人物档案</h2><span>{{ filtered.length }} 位人物</span></div>
        <label class="story-search"><Search :size="16" /><input v-model="query" type="search" aria-label="搜索人物或作品" placeholder="寻找一个人物、一部作品" /></label>
        <div v-if="filtered.length" class="story-grid"><RouterLink v-for="character in filtered" :key="character.id" :to="characterUrl(character.id)" class="story-card"><img :src="journalAsset(character.overview.image)" :alt="character.overview.alt" class="cover-image" loading="lazy" /><div class="card-copy"><p class="story-meta">《{{ character.book }}》 · {{ character.chapters.length }} 篇故事</p><h3>{{ character.name }} <ArrowUpRight :size="18" /></h3><p>{{ character.overview.subtitle }}</p><p class="story-intro excerpt">{{ character.intro }}</p></div></RouterLink></div>
        <div v-else class="story-empty"><p>{{ characters.length ? '没有找到匹配的人物。' : '人物档案尚未入册。' }}</p><button v-if="query" class="button secondary" @click="query = ''">查看全部人物</button></div>
      </section>
    </template>
    <article v-else-if="current && selected" class="story-article">
      <RouterLink to="/stories" class="back-stories"><ArrowLeft :size="16" />全部人物</RouterLink>
      <div class="article-layout">
        <aside class="article-profile"><h2>{{ current.name }}</h2><p class="story-meta">《{{ current.book }}》</p><nav aria-label="人物章节"><RouterLink :to="characterUrl(current.id)" :aria-current="!route.params.chapter ? 'page' : undefined" :class="{ active: !route.params.chapter }">人物总览<span>{{ current.overview.subtitle }}</span></RouterLink><RouterLink v-for="(chapter, index) in current.chapters" :key="chapter.id" :to="`${characterUrl(current.id)}/${chapter.id}`" :aria-current="route.params.chapter === chapter.id ? 'page' : undefined" :class="{ active: route.params.chapter === chapter.id }"><small>{{ String(index + 1).padStart(2, '0') }}</small>{{ chapter.subtitle || chapter.title }}</RouterLink></nav></aside>
        <div class="article-body"><header><p class="eyebrow">{{ selected.sourceLabel }}</p><h1>{{ selected.title }}</h1><p class="subtitle">{{ selected.subtitle }}</p><p class="story-meta">{{ current.name }} · 原作：{{ current.author }}</p></header>
          <figure><img :key="selected.image" :src="journalAsset(selected.image)" :alt="selected.alt" class="cover-image" /><figcaption>{{ selected.caption }}</figcaption></figure>
          <div class="story-prose"><template v-for="(block, index) in selected.blocks" :key="`${selected.id}-${index}`"><component :is="block.level === 2 ? 'h2' : 'h3'" v-if="block.type === 'heading'">{{ block.text }}</component><p v-else>{{ block.text }}</p></template></div>
          <section v-if="!route.params.chapter && current.chapters.length" class="chapter-list" aria-labelledby="chapter-list-title"><h2 id="chapter-list-title">走进他的故事</h2><RouterLink v-for="chapter in current.chapters" :key="chapter.id" :to="`${characterUrl(current.id)}/${chapter.id}`"><img :src="journalAsset(chapter.image)" :alt="chapter.alt" loading="lazy" /><div><h3>{{ chapter.subtitle || chapter.title }}</h3><p>{{ chapter.title }}</p></div><ArrowUpRight :size="18" /></RouterLink></section>
          <RouterLink v-else-if="route.params.chapter" :to="characterUrl(current.id)" class="back-stories"><ArrowLeft :size="16" />返回人物总览</RouterLink>
        </div>
      </div>
    </article>
    <div v-else class="story-empty"><h1>{{ current ? '这一章尚未入册。' : '这位人物尚未入册。' }}</h1><RouterLink :to="current ? characterUrl(current.id) : '/stories'" class="button secondary">{{ current ? '返回人物总览' : '返回人物志' }}</RouterLink></div>
  </div>
</template>

<style scoped>
/* Teleported outside the route transition: fixed backdrop stays viewport-sized. */
.journal-acrylic { position: fixed; inset: 0; z-index: -2; overflow: hidden; pointer-events: none; background: #0b141e; }
.journal-acrylic-art { position: absolute; inset: -48px; width: calc(100% + 96px); height: calc(100% + 96px); max-width: none; object-fit: cover; filter: blur(28px) saturate(1.15); opacity: .72; }
.journal-acrylic-tint { position: absolute; inset: 0; background: linear-gradient(115deg, #09121bd1, #101a255c 55%, #080f1ac2), linear-gradient(0deg, #080f1aa6, transparent 65%); }
.journal-acrylic-grain { position: absolute; inset: 0; opacity: .045; background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='160'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Cpath fill='%23fff' filter='url(%23n)' d='M0 0h160v160H0z'/%3E%3C/svg%3E"); }

.characters-page{max-width:1280px;margin:auto;padding:48px 0 64px}.characters-heading{display:flex;justify-content:space-between;align-items:end;gap:28px;margin-bottom:32px}.characters-heading h1{font:42px/1.4 var(--serif);margin:12px 0 0}.characters-heading h1 span{display:inline-block;font-size:15px;margin-left:26px;color:#b9b0a0}.characters-heading>p{font-size:12px;line-height:2;color:#a4acb0}.story-feature{display:grid;grid-template-columns:1.15fr 1fr;align-items:center;border:1px solid #71624b;background:#101b23b8}.cover-image{display:block;width:100%;height:auto;object-fit:contain}.feature-copy{padding:32px}.feature-copy h2{font:40px var(--serif);margin:18px 0}.story-meta{font-size:12px;color:#a99b83;line-height:1.8}.feature-copy blockquote{margin:0 0 20px;font:22px/1.9 var(--serif);color:#d9c8a4}.story-intro{font-size:13px;color:#aeb7bd;line-height:2}.excerpt{display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}.story-read{display:flex;gap:16px;align-items:center;margin-top:24px;font-size:13px;color:#d3ba87}.story-collection{margin-top:48px}.collection-heading{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #685b454f;padding-bottom:20px}.collection-heading h2{font:24px var(--serif);margin:0}.collection-heading>span{font-size:12px;color:#a4acb0}.story-search{display:flex;gap:12px;align-items:center;margin:24px 0;max-width:340px;border-bottom:1px solid #635b4a}.story-search input{background:transparent;border:0;padding:12px 0;width:100%;min-width:0;color:inherit}.story-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:22px}.story-card{border:1px solid #6a604640;background:#111c25bf;align-self:start}.story-card:hover{border-color:#b39860}.card-copy{padding:22px}.card-copy h3{display:flex;justify-content:space-between;align-items:center;font:25px var(--serif);margin:12px 0}.story-empty{padding:70px 20px;text-align:center}.back-stories{display:inline-flex;gap:12px;align-items:center;font-size:13px;margin:0 0 30px;color:#c9b58d}.article-layout{display:grid;grid-template-columns:210px minmax(0,900px);justify-content:center;gap:40px}.article-profile{position:sticky;top:24px;align-self:start;max-height:calc(100vh - 48px);overflow:auto}.article-profile h2{font:28px var(--serif)}nav{display:grid;gap:8px;margin-top:24px}nav a{padding:14px 12px;border-left:2px solid transparent;color:#aeb7bd;font-size:14px;line-height:1.8}nav a.active{border-color:#d3ba87;background:#b1955b12;color:#e2cc9e}nav span{display:block;font-size:12px}nav small{margin-right:14px}.article-body{min-width:0;background:#101b24ad;padding:36px;border:1px solid #d8c7a22b;border-top-color:#99805a;box-shadow:inset 0 1px 0 #ffffff0d,0 18px 60px #02071126;backdrop-filter:blur(18px) saturate(1.15);-webkit-backdrop-filter:blur(18px) saturate(1.15)}.article-body h1{font:34px/1.6 var(--serif);margin:12px 0}.subtitle{font:24px/1.6 var(--serif);color:#d9c8a4;margin:0 0 16px}figure{margin:28px 0 36px}figcaption{font-size:12px;line-height:1.8;color:#9ca9af;margin-top:12px}.story-prose{max-width:720px;margin:auto;overflow-wrap:anywhere}.story-prose p{font:17px/2.2 var(--serif);color:#cbd0cf;margin:0 0 26px;white-space:pre-line}.story-prose h2,.story-prose h3{font:25px/1.6 var(--serif);color:#ddc59b;margin:36px 0 20px}.chapter-list{border-top:1px solid #685b454f;margin-top:40px;padding-top:20px}.chapter-list>a{display:grid;grid-template-columns:140px minmax(0,1fr) 18px;gap:20px;align-items:center;border-bottom:1px solid #685b454f;padding:20px 0}.chapter-list img{width:100%;height:auto}.chapter-list h3{font:22px var(--serif);color:#ddc59b}.chapter-list p{font-size:12px;color:#aeb7bd}a:focus-visible,button:focus-visible,input:focus-visible{outline:2px solid #d3ba87;outline-offset:4px}
@media(max-width:1000px){.story-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.characters-heading>p{display:none}.article-layout{grid-template-columns:180px minmax(0,1fr);gap:20px}.article-body{padding:24px}}
@media(max-width:640px){.characters-page{padding-top:28px}.characters-heading h1 span{display:block;margin:12px 0 0}.story-feature{grid-template-columns:1fr}.feature-copy{padding:24px}.story-grid{grid-template-columns:1fr}.article-layout{display:block}.article-profile{position:static;max-height:none;overflow:visible;margin-bottom:24px}nav{display:flex;overflow-x:auto;padding-bottom:8px}nav a{flex-shrink:0;max-width:180px;border-left:0;border-bottom:2px solid transparent}nav a.active{border-bottom-color:#d3ba87}.article-body{padding:20px}.article-body h1{font-size:27px}.story-prose p{font-size:16px}.chapter-list>a{grid-template-columns:85px minmax(0,1fr) 18px;gap:12px}.chapter-list h3{font-size:18px}}
@media(prefers-reduced-transparency:reduce){.journal-acrylic-art{opacity:.25}.article-body,.story-feature,.story-card{background:#101b24}}
</style>
