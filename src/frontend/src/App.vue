<script setup lang="ts">
import { nextTick, onMounted, watch } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'
import { ArrowUpRight, Crown } from 'lucide-vue-next'
import { connect, configured, interview } from './state/interview'
import './state/preferences'
import AmbientSnow from './components/AmbientSnow.vue'
const route = useRoute()
function focusMain() { document.getElementById('main-content')?.focus({ preventScroll: true }) }
let interviewInitialized = false
function ensureInterview() {
  if (route.name !== 'stories' && !interviewInitialized) { interviewInitialized = true; void connect('page') }
}
onMounted(ensureInterview)
watch(() => route.path, async () => {
  ensureInterview()
  await nextTick()
  window.setTimeout(() => document.getElementById('main-content')?.focus({ preventScroll: true }), 280)
})
let toastTimer: ReturnType<typeof setTimeout> | undefined
watch(() => interview.notice, value => {
  if (toastTimer) clearTimeout(toastTimer)
  if (value) toastTimer = setTimeout(() => { interview.notice = '' }, 5000)
})
</script>
<template>
  <div class="app-frame" :class="`scene-${String(route.name || 'home')}`">
    <div class="cathedral-backdrop" aria-hidden="true" />
    <div class="ambient-light" aria-hidden="true" />
    <AmbientSnow v-if="route.name === 'home' || (route.name === 'stories' && !route.params.slug)" />
    <div class="cathedral-leadwork" aria-hidden="true"><span /><span /><span /></div>
    <a class="skip-link" href="#main-content" @click.prevent="focusMain">跳到主要内容</a>
    <header class="site-header">
      <RouterLink to="/" class="brand" aria-label="返回首页"><span class="brand-symbol"><Crown :size="23" :stroke-width="1.2" /></span></RouterLink>
      <nav class="primary-nav" aria-label="主导航">
        <RouterLink to="/" :class="{ selected: route.name === 'home' }"><span class="nav-number">01</span> 序厅</RouterLink>
        <RouterLink to="/settings" :class="{ selected: route.name === 'settings' }"><span class="nav-number">02</span> 面试准备</RouterLink>
        <RouterLink to="/interview" :class="{ selected: route.name === 'interview' }"><span class="nav-number">03</span> 面试室</RouterLink>
        <RouterLink to="/stories" :class="{ selected: route.name === 'stories' }"><span class="nav-number">04</span> 人物志</RouterLink>
      </nav>
      <RouterLink v-if="route.name !== 'stories'" :to="configured && interview.status === 'ready' ? '/interview' : '/settings'" class="header-cta">{{ configured && interview.status === 'ready' ? '继续练习' : '开始练习' }}<ArrowUpRight :size="15" /></RouterLink>
    </header>
    <main id="main-content" tabindex="-1"><RouterView v-slot="{ Component, route: current }"><Transition name="page" mode="out-in" appear><component :is="Component" :key="current.path" /></Transition></RouterView></main>
    <footer v-if="route.name === 'stories'" class="site-footer"><span>THE CHARACTER JOURNAL</span><span>一个人物，一个故事。</span><span class="footer-edition">VOL. 01 / 2026</span></footer>
    <footer v-else class="site-footer"><span>NORTHWIND · A SPACE TO BECOME</span><span>让每一次表达，都更接近自己。</span><span class="footer-edition">VOL. 01 / 2026</span></footer>
    <Transition name="toast"><div v-if="interview.notice && route.name !== 'stories'" class="toast-message" role="status">{{ interview.notice }}</div></Transition>
  </div>
</template>
