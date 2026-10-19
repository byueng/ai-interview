<script setup lang="ts">
import { ArrowRight, ArrowUpRight, SlidersHorizontal, MessagesSquare, BookOpen } from 'lucide-vue-next'
import { configured, interview } from '../state/interview'
function showSteps() { document.getElementById('how-it-works')?.scrollIntoView() }
</script>
<template>
  <div class="home-page">
    <section class="hero">
      <div class="hero-copy">
        <p class="eyebrow reveal" style="--delay: 0ms"><span class="small-rule" /> THE ART OF CONVERSATION</p>
        <h1 class="reveal" style="--delay: 90ms">从容表达，<br />始于每一次<br /><em>认真练习。</em></h1>
        <p class="hero-description reveal" style="--delay: 180ms">给思考一点空间，给表达一次预演。<br />在专注的对话里，找到属于你的面试节奏。</p>
        <div class="hero-actions reveal" style="--delay: 270ms"><RouterLink :to="configured && interview.status === 'ready' ? '/interview' : '/settings'" class="button primary">{{ configured && interview.status === 'ready' ? '继续我的练习' : '开启一场练习' }}<ArrowRight :size="17" /></RouterLink><a href="#how-it-works" class="quiet-link" @click.prevent="showSteps">了解如何开始<ArrowUpRight :size="14" /></a></div>
        <div class="hero-footnote reveal" style="--delay: 340ms"><span class="fine-star">✦</span><span>你的岗位，你的节奏。<br /><small>一次只专注于一场对话。</small></span></div>
      </div>
      <div class="mural-caption" aria-label="壁画主题：王与曾经的自己"><span>Ⅰ</span><div>王与曾经的自己<small>THE KING & THE CHILD</small></div></div>
    </section>
    <section id="how-it-works" class="journey" aria-labelledby="journey-heading">
      <div class="journey-intro"><p class="eyebrow">YOUR PRACTICE, CONSIDERED</p><h2 id="journey-heading">好的准备，<br />从三个小步骤开始。</h2></div>
      <RouterLink to="/settings" class="journey-step"><span class="step-number">01 / PREPARE</span><SlidersHorizontal :size="21" :stroke-width="1.3" /><h3>设定你的方向</h3><p>选择目标岗位，定义面试官，<br />让每一次提问更有针对性。</p><ArrowUpRight :size="17" class="step-arrow" /></RouterLink>
      <RouterLink to="/interview" class="journey-step"><span class="step-number">02 / CONVERSE</span><MessagesSquare :size="21" :stroke-width="1.3" /><h3>进入专注的对话</h3><p>在独立的面试空间里，<br />练习把经历讲得清晰、有力。</p><ArrowUpRight :size="17" class="step-arrow" /></RouterLink>
      <RouterLink to="/review" class="journey-step"><span class="step-number">03 / REFLECT</span><BookOpen :size="21" :stroke-width="1.3" /><h3>回看每一次表达</h3><p>留存本次对话，重新梳理，<br />为下一次真实面试积累底气。</p><ArrowUpRight :size="17" class="step-arrow" /></RouterLink>
    </section>
  </div>
</template>
