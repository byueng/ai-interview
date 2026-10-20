<script setup lang="ts">
import { computed, ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { ArrowUpRight, ArrowLeft, Search } from 'lucide-vue-next'
const route = useRoute()
const query = ref('')
const category = ref('全部人物')
const categories = ['全部人物', '奇幻', '武侠', '都市']
const stories = [
  { id: 'keeper', name: '沈照夜', title: '替遗忘的人，守一盏灯。', book: '《长夜来信》', category: '奇幻', role: '守灯人', glyph: '夜', tone: 'blue', quote: '只要灯还亮着，远行的人就不算迷路。', intro: '城里的每一盏灯，都记得一个名字。他守着最后一座灯塔，等待一封没有署名的信。', paragraphs: ['沈照夜第一次登上灯塔时，城里刚刚废除了夜晚。人们把日光封在玻璃里，挂在街头，连做梦也不愿关灯。只有海边这座旧塔，仍然按照潮汐点亮。', '他的工作很简单：擦拭镜面，添满灯油，在一本厚厚的簿子上写下归航者的名字。可每到冬天，总有几艘船没有回来。那些空着的行，他从来不肯划掉。', '那封信是在一个没有风的夜里送来的。信上只有一句话：“如果你还记得我，请把灯再亮一夜。”他认不出字迹，却在纸的折痕里闻到了故乡的雨。', '第二天，城里的人发现，海上的灯比往常亮得更久。沈照夜没有向任何人解释。他只是把簿子翻到新的一页，在第一行写下了自己的名字。'] },
  { id: 'swordswoman', name: '叶听澜', title: '收剑之后，才是江湖。', book: '《山河旧事》', category: '武侠', role: '归山客', glyph: '澜', tone: 'green', quote: '我不再问谁赢了，我只问谁回来了。', intro: '她曾用一柄剑走过十三座城。如今在山脚开了一间茶铺，只听故事，不问来处。', paragraphs: ['叶听澜把剑挂在了茶铺最暗的墙角。来往的客人以为那是一件装饰，只有下雨的时候，铁锈的气味才会提醒她，旧事还在。', '一个年轻人来讨水喝，说要去北边找天下第一。她给他添了一碗热茶，又包了两块饼。年轻人问她路有多远，她说，走到想回家的时候就知道了。', '后来山路封雪，茶铺很久没有客人。她每天照常开门，把门前的积雪扫到两侧。不是在等谁，只是觉得，总该给赶路的人留一条路。'] },
  { id: 'letter', name: '陈见夏', title: '在平凡的一天，重新出发。', book: '《第七站晴天》', category: '都市', role: '旧书店店主', glyph: '夏', tone: 'amber', quote: '有些答案，要在生活里慢慢翻页。', intro: '三十岁那年，她接手了一家即将关门的旧书店，也接住了许多未曾说出口的告别。', paragraphs: ['书店的钥匙比陈见夏想象中轻。她原以为，接住另一个人的一生，至少应该有一点重量。', '整理书架时，她发现每本书里都夹着一张车票。目的地各不相同，日期却都停在许多年前。她没有丢掉它们，而是做了一面很小的留言墙。', '春天来的时候，第一位客人在墙上留下一句话：“下次，我想坐到终点。”见夏站了很久，然后把营业时间往后延长了一个小时。'] },
  { id: 'cartographer', name: '闻星', title: '地图之外，还有故乡。', book: '《无名群岛》', category: '奇幻', role: '绘图师', glyph: '星', tone: 'violet', quote: '我画下的不是边界，是抵达的可能。', intro: '少年绘图师寻找一座会移动的岛。旅程的尽头，所有航线都指向记忆里的一扇门。', paragraphs: ['闻星画的第一张地图，是从卧室到厨房的路。他在桌角标了一座山，在水盆旁画了一片海，母亲笑着说，这是个很大的世界。', '成年以后，他去了真正的海上。每到一座岛，他都要寻找一扇蓝色的门。同行的人问他为什么，他说，地图总要有一个起点。', '最后一张海图上没有岛屿，只有一条弯弯曲曲的线。线的尽头，他画了一张桌子、一盆水，和一个还没有学会告别的小孩。'] },
]
const current = computed(() => stories.find(s => s.id === route.params.slug))
const filtered = computed(() => stories.filter(s => (category.value === '全部人物' || s.category === category.value) && `${s.name}${s.title}${s.book}${s.role}`.includes(query.value.trim())))
const featured = stories[0]!
</script>

<template>
  <div class="characters-page">
    <template v-if="!route.params.slug">
      <header class="characters-heading"><div><p class="eyebrow">THE CHARACTER JOURNAL / VOL. 01</p><h1>人物志<span>每一个人，都是一个故事。</span></h1></div><p>把书页翻到他们出现的地方。<br />读一个人的来路，也读那些未完的回声。</p></header>
      <RouterLink :to="`/stories/${featured.id}`" class="story-feature">
        <div class="character-art blue"><span class="art-coordinate">CHAPTER 001 / THE LIGHT KEEPER</span><span class="art-glyph">夜</span><span class="art-caption">长夜未尽 · 灯火不息</span></div>
        <div class="feature-copy"><p class="eyebrow">本期人物 / EDITOR'S PICK</p><p class="story-meta">{{ featured.book }} · {{ featured.role }}</p><h2>{{ featured.name }}</h2><blockquote>“{{ featured.quote }}”</blockquote><p class="story-intro">{{ featured.intro }}</p><span class="story-read">读他的故事 <ArrowUpRight :size="18" /></span></div>
      </RouterLink>
      <section class="story-collection" aria-labelledby="collection-title">
        <div class="collection-heading"><h2 id="collection-title">故事档案 <small>THE COLLECTION</small></h2><span>{{ filtered.length.toString().padStart(2, '0') }} 篇故事</span></div>
        <div class="story-toolbar"><div class="story-tabs" aria-label="人物分类"><button v-for="item in categories" :key="item" :aria-pressed="category === item" :class="{ active: category === item }" @click="category = item">{{ item }}</button></div><label class="story-search"><Search :size="15" /><input v-model="query" type="search" aria-label="搜索人物或故事" placeholder="寻找一个人物、一段故事" /></label></div>
        <div v-if="filtered.length" class="story-grid"><RouterLink v-for="(story, index) in filtered" :key="story.id" :to="`/stories/${story.id}`" class="story-card"><div class="character-art" :class="story.tone"><span class="art-coordinate">{{ story.category }} / {{ story.role }}</span><span class="art-glyph">{{ story.glyph }}</span><span class="art-caption">{{ story.book }}</span></div><div class="card-copy"><p class="story-meta">人物档案 / {{ String(index + 1).padStart(2, '0') }}</p><h3>{{ story.name }}<ArrowUpRight :size="18" /></h3><p class="card-title">{{ story.title }}</p><p class="story-intro">{{ story.intro }}</p></div></RouterLink></div>
        <div v-else class="story-empty"><p>暂时没有找到这个人物。</p><button class="button secondary" @click="query = ''; category = '全部人物'">查看全部故事</button></div>
      </section>
      <p class="prototype-note">本期收录为原创示例人物与短篇，用于栏目预览。</p>
    </template>
    <article v-else-if="current" class="story-article">
      <RouterLink to="/stories" class="back-stories"><ArrowLeft :size="16" />返回人物志</RouterLink>
      <div class="article-layout"><aside class="article-profile"><div class="character-art" :class="current.tone"><span class="art-coordinate">{{ current.category }} / {{ current.role }}</span><span class="art-glyph">{{ current.glyph }}</span><span class="art-caption">{{ current.book }}</span></div><p class="eyebrow">CHARACTER NOTES</p><h2>{{ current.name }}</h2><p>{{ current.intro }}</p></aside><div class="article-body"><p class="eyebrow">人物志 / 原创示例短篇</p><h1>{{ current.title }}</h1><p class="story-meta">{{ current.name }} · {{ current.book }}</p><blockquote>{{ current.quote }}</blockquote><p v-for="paragraph in current.paragraphs" :key="paragraph" class="story-paragraph">{{ paragraph }}</p><div class="story-end">FIN / 故事暂歇，余音未尽</div><RouterLink to="/stories" class="button secondary">继续翻阅人物故事 <ArrowUpRight :size="16" /></RouterLink></div></div>
    </article>
    <div v-else class="story-empty"><h1>这位人物还未入册。</h1><RouterLink to="/stories" class="button secondary">返回人物志</RouterLink></div>
  </div>
</template>

<style scoped>
.characters-page { max-width: 1280px; margin: auto; padding: 48px 0 64px; }
.characters-heading { display: flex; justify-content: space-between; align-items: end; gap: 28px; padding-bottom: 32px; }
.characters-heading h1 { font: 42px/1.4 var(--serif); margin: 12px 0 0; }
.characters-heading h1 span { display: inline-block; font-size: 15px; margin-left: 26px; color: #b9b0a0; }
.characters-heading > p { font-size: 12px; line-height: 2; color: #a4acb0; margin: 0; }
.story-feature { display: grid; grid-template-columns: 1.05fr 1fr; border: 1px solid #71624b; background: #101b23ed; }
.character-art { --accent: #668798; position: relative; isolation: isolate; overflow: hidden; min-height: 230px; background: radial-gradient(ellipse at 50% 115%,var(--accent),transparent 65%),linear-gradient(145deg,#1a2b33,#0a111b 70%); display: flex; flex-direction: column; align-items: center; justify-content: center; }
.character-art::before { content: ''; position: absolute; z-index: -1; width: 50%; height: 125%; top: 18%; border: 1px solid #c0a77866; border-radius: 50% 50% 0 0; box-shadow: 0 0 0 15px #060e1722,0 0 0 16px #c0a77822; transform: rotate(22deg); }
.character-art::after { content: ''; position: absolute; inset: 14px; border: 1px solid #dccba329; pointer-events: none; }
.green { --accent: #56796b; background-color: #182c29; }.amber { --accent: #9c7654; }.violet { --accent: #796386; }
.art-coordinate { position: absolute; top: 28px; left: 28px; color: #c2b698; font-size: 8px; letter-spacing: .16em; }
.art-glyph { font: 120px/1.3 var(--serif); color: #e1d3af; opacity: .85; text-shadow: 0 5px 30px #01050a; }
.art-caption { position: absolute; bottom: 28px; font-size: 10px; letter-spacing: .25em; color: #d4c5a9; }
.story-feature .character-art { min-height: 375px; }.story-feature .art-glyph { font-size: 190px; }
.feature-copy { padding: 40px 44px; }.feature-copy h2 { font: 42px var(--serif); margin: 20px 0; }
.story-meta { font-size: 10px; color: #a99b83; letter-spacing: .08em; }
blockquote { margin: 0 0 22px; font: 18px/1.9 var(--serif); color: #d9c8a4; }
.story-intro { font-size: 12px; color: #aeb7bd; line-height: 2; }
.story-read { display: flex; gap: 28px; align-items: center; margin-top: 25px; font-size: 12px; color: #d3ba87; }
.story-collection { margin-top: 48px; }.collection-heading { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #685b454f; padding-bottom: 20px; }
.collection-heading h2 { font: 23px var(--serif); margin: 0; }.collection-heading small { margin-left: 16px; font: 8px sans-serif; letter-spacing: .15em; color: #ac9e84; }.collection-heading > span { font-size: 11px; color: #a4acb0; }
.story-toolbar { display: flex; justify-content: space-between; gap: 24px; margin: 24px 0; }.story-tabs { display: flex; gap: 8px; flex-wrap: wrap; }
.story-tabs button { background: transparent; border: 1px solid transparent; padding: 9px 15px; color: #a8b1b8; font-size: 12px; }.story-tabs button.active { border-color: #8a7450; color: #e2cc9e; background: #b1955b12; }
.story-search { display: flex; align-items: center; gap: 12px; border-bottom: 1px solid #635b4a; color: #a8b1b8; }.story-search input { background: transparent; border: 0; padding: 10px 0; min-width: 0; width: 210px; font-size: 11px; }
.story-grid { display: grid; grid-template-columns: repeat(4,minmax(0,1fr)); gap: 22px; }.story-card { border: 1px solid #6a604640; background: #111c25ed; }.story-card:hover { border-color: #b39860; transform: translateY(-3px); }.card-copy { padding: 22px; }.card-copy h3 { display: flex; justify-content: space-between; align-items: center; font: 25px var(--serif); margin: 12px 0; }.card-title { font-size: 12px; color: #d4c2a1; }.card-copy .story-intro { font-size: 11px; margin-bottom: 0; }
.prototype-note { text-align: center; color: #8f9aa2; font-size: 10px; margin: 36px 0 0; }.story-empty { padding: 70px 20px; text-align: center; }
.back-stories { display: inline-flex; gap: 12px; align-items: center; font-size: 12px; margin-bottom: 36px; color: #c9b58d; }.article-layout { display: grid; grid-template-columns: 280px minmax(0,720px); justify-content: center; gap: 70px; }.article-profile { align-self: start; }.article-profile .character-art { min-height: 330px; margin-bottom: 30px; }.article-profile h2 { font: 28px var(--serif); }.article-profile > p:last-child { font-size: 12px; line-height: 2; color: #aeb7bd; }.article-body { background: #101b24eb; padding: 40px; border-top: 1px solid #99805a; }.article-body h1 { font: 34px/1.6 var(--serif); }.article-body blockquote { padding: 24px 0; margin: 26px 0; border-block: 1px solid #89734b55; }.story-paragraph { font: 17px/2.3 var(--serif); color: #cbd0cf; margin-bottom: 26px; }.story-end { margin: 40px 0; color: #ab9774; font-size: 10px; letter-spacing: .14em; }
@media(max-width:1000px) { .story-grid { grid-template-columns: repeat(2,minmax(0,1fr)); }.characters-heading > p { display: none; }.feature-copy { padding: 30px; }.article-layout { grid-template-columns: 220px minmax(0,1fr); gap: 30px; } }
@media(max-width:640px) { .characters-page { padding-top: 30px; }.characters-heading h1 span { display: block; margin: 12px 0 0; }.story-feature { grid-template-columns: 1fr; }.story-feature .character-art { min-height: 260px; }.story-feature .art-glyph { font-size: 140px; }.story-toolbar { flex-direction: column; }.story-search input { width: 100%; }.story-grid { gap: 12px; }.card-copy { padding: 16px; }.character-art { min-height: 190px; }.art-coordinate { left: 22px; font-size: 7px; }.art-glyph { font-size: 90px; }.collection-heading small { display: none; }.article-layout { grid-template-columns: 1fr; }.article-profile { display: none; }.article-body { padding: 24px; }.article-body h1 { font-size: 28px; } }
@media(prefers-reduced-motion:reduce) { .story-card:hover { transform: none; } }
</style>
