<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowLeft, ArrowRight, Download, BookOpen } from 'lucide-vue-next'
import { busy, connect, downloadTranscript, interview } from '../state/interview'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import SessionNotice from '../components/SessionNotice.vue'
const router = useRouter(), newDialog = ref(false)
const answers = computed(() => interview.messages.filter(message => message.role === 'candidate'))
const words = computed(() => answers.value.reduce((sum, message) => sum + message.text.replace(/\s/g, '').length, 0))
async function startNew() { if (await connect('new')) { newDialog.value = false; await router.push('/settings') } }
</script>
<template>
  <div class="content-page review-page"><header class="page-heading"><div><p class="eyebrow">04 / THE REFLECTION</p><h1>每一次表达，都值得回看。</h1><p>{{ interview.status === 'ended' ? '本次练习已结束。把新的思考，带到下一场对话。' : '这里记录着本次会话的每一次问答。' }}</p></div><BookOpen :size="36" :stroke-width="1" /></header>
    <SessionNotice />
    <div v-if="!interview.messages.length" class="room-empty"><BookOpen :size="35" :stroke-width="1" /><h2>故事，从第一句回答开始。</h2><p>本页展示当前页面会话的对话记录。还没有对话时，可以先开始一场练习。</p><RouterLink to="/settings" class="button primary">准备一场面试<ArrowRight :size="16" /></RouterLink></div>
    <template v-else><section class="review-stats" aria-label="本次练习统计"><div><span>目标岗位</span><strong class="stat-position">{{ interview.candidate_config.position }}</strong></div><div><span>已完成对话</span><strong>{{ interview.round }}<small>轮</small></strong></div><div><span>我的回答</span><strong>{{ answers.length }}<small>次</small></strong></div><div><span>累计表达</span><strong>{{ words }}<small>字符</small></strong></div></section>
    <div class="review-actions"><h2>对话手记 <small>CONVERSATION NOTES</small></h2><button class="button secondary compact" @click="downloadTranscript"><Download :size="15" />下载对话记录</button></div>
    <p class="field-note">此处是对话回顾，未进行自动评分。结束后的记录请及时下载，刷新页面后将无法重新读取已结束的会话。</p>
    <section class="review-transcript"><article v-for="(message, index) in interview.messages" :key="message.id"><span class="review-index">{{ String(index + 1).padStart(2, '0') }}</span><div><h3>{{ message.role === 'candidate' ? '我的回答' : '面试官' }}<small v-if="message.uncertain">完成状态待确认</small></h3><p>{{ message.text }}</p></div></article></section>
    <div class="review-bottom"><RouterLink v-if="interview.status === 'ready'" to="/interview" class="quiet-link"><ArrowLeft :size="16" />返回面试室</RouterLink><RouterLink v-else to="/" class="quiet-link"><ArrowLeft :size="16" />回到序厅</RouterLink><button class="button primary" :disabled="busy" @click="newDialog = true">准备下一场练习<ArrowRight :size="16" /></button></div></template>
    <ConfirmDialog v-if="newDialog" title="开启新的练习？" description="请先下载需要保留的对话记录。新会话会清空当前页面的配置与手记。" confirm-label="新建练习" :busy="busy" :error="interview.sessionError" @close="newDialog = false" @confirm="startNew" />
  </div>
</template>
