<script setup lang="ts">
import { nextTick, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowRight, ArrowUp, BookOpen, Check, Compass, RotateCcw, SlidersHorizontal } from 'lucide-vue-next'
import { busy, canSend, configured, connect, finishSession, interview, sendMessage, waitingText } from '../state/interview'
import SessionNotice from '../components/SessionNotice.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'
const router = useRouter(), transcript = ref<HTMLElement>(), endDialog = ref(false)
async function scrollLatest() { await nextTick(); if (transcript.value) transcript.value.scrollTop = transcript.value.scrollHeight }
watch(() => [interview.messages.length, interview.sending], scrollLatest)
onMounted(scrollLatest)
function keydown(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing && event.keyCode !== 229) { event.preventDefault(); void sendMessage() }
}
async function end() { if (await finishSession()) { endDialog.value = false; await router.push('/review') } }
</script>
<template>
  <div class="content-page interview-page">
    <header class="room-header"><div><p class="eyebrow">03 / THE CONVERSATION</p><h1>{{ configured ? interview.candidate_config.position : '你的专属面试室' }}</h1></div><div class="room-actions"><RouterLink to="/review" class="text-button"><BookOpen :size="15" />本次回顾</RouterLink><button class="button secondary compact" :disabled="busy || interview.status !== 'ready' || !configured" @click="endDialog = true">结束练习</button></div></header>
    <SessionNotice />
    <div v-if="!configured && interview.status !== 'initializing'" class="room-empty"><Compass :size="38" :stroke-width="1" /><p class="eyebrow">BEFORE WE BEGIN</p><h2>先为这场对话，定一个方向。</h2><p>完成岗位与面试官设置，我们就在这里见。</p><RouterLink to="/settings" class="button primary">前往面试准备<ArrowRight :size="16" /></RouterLink></div>
    <div v-else class="room-layout">
      <aside class="room-sidebar"><div class="glass-rosette compact-rosette" aria-hidden="true"><span>Ⅲ</span></div><div class="room-profile"><p class="eyebrow">YOUR INTERVIEWER</p><h2>{{ interview.interviewer.role_identity }}</h2><p>{{ interview.interviewer.role_responsibilities }}</p><dl><div><dt>语言</dt><dd>{{ interview.candidate_config.language === 'en-US' ? 'English' : '中文' }}</dd></div><div><dt>已完成</dt><dd>{{ String(interview.round).padStart(2, '0') }} 轮对话</dd></div><div><dt>状态</dt><dd><span class="status-dot" :class="{ quiet: interview.status !== 'ready' }" />{{ interview.status === 'ended' ? '已结束' : interview.sending ? waitingText : interview.status === 'ready' ? '已就绪' : '等待连接' }}</dd></div></dl><RouterLink to="/settings" class="quiet-link"><SlidersHorizontal :size="14" />查看面试设置</RouterLink></div><p class="room-tip">不急于回答。<br />清晰，往往从停顿开始。</p></aside>
      <section class="conversation-panel" aria-label="面试对话区域">
        <div class="conversation-top"><span><span class="status-dot" />{{ interview.sending ? waitingText : '专注于此刻的对话' }}</span><span>SESSION / {{ String(interview.round).padStart(2, '0') }}</span></div>
        <div ref="transcript" class="transcript" role="log" aria-label="面试对话" aria-live="polite" :aria-busy="interview.sending">
          <div v-if="!interview.messages.length" class="conversation-welcome"><span class="welcome-emblem"><Compass :size="27" :stroke-width="1" /></span><p class="eyebrow">MAKE YOURSELF COMFORTABLE</p><h2>准备好了，就从一句你好开始。</h2><p>也可以先简单介绍自己，<br />让面试官了解你的背景。</p><button class="starter-chip" :disabled="busy || interview.status !== 'ready'" @click="interview.draft = '你好，我准备好了，请开始面试。'">你好，我准备好了。<ArrowUp :size="13" /></button></div>
          <article v-for="message in interview.messages" :key="message.id" class="chat-message" :class="message.role"><div class="message-label"><span>{{ message.role === 'candidate' ? '你' : '面试官' }}</span><span v-if="message.uncertain" class="uncertain">完成状态待确认</span><Check v-else-if="message.role === 'candidate' && !interview.sending" :size="12" /></div><p>{{ message.text }}</p></article>
          <div v-if="interview.sending" class="thinking" role="status"><span /><span /><span /><em>{{ waitingText }}</em></div>
        </div>
        <div v-if="interview.streamError" class="stream-error" role="alert"><p>{{ interview.streamError }}</p><button class="text-button" :disabled="busy" @click="connect('continue')"><RotateCcw :size="14" />同步会话</button></div>
        <form class="composer" @submit.prevent="sendMessage"><label for="answer" class="sr-only">你的回答</label><textarea id="answer" v-model="interview.draft" rows="3" placeholder="慢慢来，把你的想法说清楚…" :disabled="busy || interview.status !== 'ready'" @keydown="keydown" /><div class="composer-bottom"><span>{{ interview.status === 'ended' ? '本次会话已结束，可前往回顾下载记录' : 'Enter 发送 · Shift + Enter 换行' }}</span><button class="send-button" type="submit" :disabled="!canSend || !!interview.streamError" aria-label="发送回答"><ArrowUp :size="20" /></button></div></form>
      </section>
    </div>
    <ConfirmDialog v-if="endDialog" title="为本次练习，画一个句点？" description="结束后，这场面试将无法继续。你仍可在本次回顾中阅读和下载对话记录。" confirm-label="结束并回顾" :busy="busy" :error="interview.sessionError" @close="endDialog = false" @confirm="end" />
  </div>
</template>
