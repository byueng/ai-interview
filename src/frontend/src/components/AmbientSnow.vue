<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref } from 'vue'
defineProps<{ rightSide?: boolean }>()
const paused = ref(false)
function syncVisibility() { paused.value = document.hidden }
onMounted(() => {
  syncVisibility()
  document.addEventListener('visibilitychange', syncVisibility)
})
onBeforeUnmount(() => document.removeEventListener('visibilitychange', syncVisibility))
// Fixed, evenly spread seeds avoid clumps and give a settled scene on first paint.
const flakes = Array.from({ length: 64 }, (_, i) => ({
  left: `${((i * 37.7) % 135) - 5}%`,
  '--size': `${1.5 + (i % 5) * .8}px`,
  '--duration': `${12 + (i % 7) * 2.5}s`,
  '--delay': `${-((i * 7.3) % 39)}s`,
  '--drift': `${-(100 + (i % 6) * 35)}px`,
  '--alpha': `${.32 + (i % 4) * .13}`,
  '--sway': `${4 + i % 5}s`,
}))
</script>

<template>
  <div class="ambient-snow" :class="{ paused, 'snow-right-side': rightSide }" aria-hidden="true">
    <div class="winter-haze" /><div class="wind-veil" />
    <span v-for="(flake, index) in flakes" :key="index" class="snow-track" :style="flake"><i /></span>
  </div>
</template>

<style scoped>
.ambient-snow { position: fixed; inset: 0; z-index: -1; overflow: hidden; pointer-events: none; mask-image: linear-gradient(90deg,#000, #000b 25%,#0007 50%,#000d 80%,#000); }
/* Scope the mask to the decorative overlay itself, never the page container. */
.ambient-snow.snow-right-side {
  -webkit-mask-image: linear-gradient(90deg, transparent 44%, #0002 54%, #0008 68%, #000 88%);
  mask-image: linear-gradient(90deg, transparent 44%, #0002 54%, #0008 68%, #000 88%);
}
.snow-right-side .winter-haze {
  background: radial-gradient(ellipse at 100% 45%, #81b7de2c, transparent 60%), linear-gradient(180deg, #8abce426, transparent 38%, transparent 62%, #8ebfe032);
}
.snow-right-side .wind-veil {
  background: radial-gradient(ellipse at 75% 35%, #bbd9ef38, transparent 40%), radial-gradient(ellipse at 90% 75%, #b2d5ef2c, transparent 42%);
}
.snow-track { position: absolute; top: -12px; animation: snowfall var(--duration) var(--delay) linear infinite; }
.snow-track i { display: block; width: var(--size); height: var(--size); border-radius: 50%; background: #e2effa; opacity: var(--alpha); box-shadow: 0 0 4px #dfedff3b; animation: snow-sway var(--sway) var(--delay) ease-in-out infinite alternate; }
.snow-track:nth-child(4n) i { filter: blur(.6px); }
.paused *, .paused *::before, .paused *::after { animation-play-state: paused !important; }
@keyframes snowfall { from { transform: translate3d(0,-12px,0); } to { transform: translate3d(var(--drift),calc(100vh + 30px),0); } }
@keyframes snow-sway { from { transform: translateX(-18px); } to { transform: translateX(24px); } }
.winter-haze { position: absolute; inset: 0; background: linear-gradient(180deg,#8abce426,transparent 38%,transparent 62%,#8ebfe032), radial-gradient(ellipse at 0% 50%,#81b7de2c,transparent 48%); }
.wind-veil { position: absolute; inset: -15% -30%; background: radial-gradient(ellipse at 15% 35%,#bbd9ef38,transparent 48%), radial-gradient(ellipse at 65% 75%,#b2d5ef2c,transparent 52%); animation: winter-gust 14s ease-in-out infinite; }
.wind-veil::after { content: ''; position: absolute; inset: 0; background: linear-gradient(168deg,transparent 40%,#cee9ff1c 45%,transparent 50%,transparent 65%,#cee9ff16 68%,transparent 73%); }
@keyframes winter-gust { 0%,100% { opacity: .35; transform: translate3d(8%,-2%,0); } 45% { opacity: 1; } 75% { opacity: .65; transform: translate3d(-9%,2%,0); } }
@media (max-width: 640px) { .snow-track:nth-of-type(n+33) { display: none; } }
@media (prefers-reduced-motion: reduce) { .ambient-snow { display: none; } }
:global(html[data-reduce-motion="true"] .ambient-snow) { display: none; }
</style>
