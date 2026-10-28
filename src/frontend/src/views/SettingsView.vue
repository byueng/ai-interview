<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowRight, Check, Plus, SlidersHorizontal } from 'lucide-vue-next'
import PresetPicker from '../components/PresetPicker.vue'
import ResumeUpload from '../components/ResumeUpload.vue'
import SessionNotice from '../components/SessionNotice.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import { applyPreset, busy, complete, configured, connect, interview, onPresetLoading, saveConfiguration } from '../state/interview'
import { reduceMotion } from '../state/preferences'
const router = useRouter()
const newDialog = ref(false)
async function enterInterview() { if (await saveConfiguration()) await router.push('/interview') }
async function newSession() { if (await connect('new')) newDialog.value = false }
const positions = ['后端工程师', '前端工程师', 'AI 应用工程师', '产品经理']
</script>
<template>
  <div class="content-page settings-page">
    <header class="page-heading"><div><p class="eyebrow">02 / THE PREPARATION</p><h1>为下一次机会，做好准备。</h1><p>告诉我们你想去的方向。接下来的对话，由你定义。</p></div><span class="heading-ornament" aria-hidden="true">Ⅱ</span></header>
    <SessionNotice />
    <div v-if="interview.status === 'ended' || interview.round > 0" class="info-banner"><p>{{ interview.status === 'ended' ? '上一场练习已结束。新建会话，开始新的准备。' : '当前练习已经开始。可以继续对话，或新建一场练习后调整配置。' }}</p><button class="text-button" :disabled="busy" @click="newDialog = true"><Plus :size="15" />新建练习</button></div>
    <div class="settings-layout">
      <ResumeUpload />
      <form id="preparation-form" class="preparation-form" @submit.prevent="enterInterview">
        <fieldset class="form-section" :disabled="busy || interview.round > 0 || interview.status !== 'ready'">
          <legend><span>01</span> 关于你 <small>YOUR PROFILE</small></legend>
          <div class="field"><label for="position">目标岗位 <span>必填</span></label><input id="position" v-model="interview.candidate_config.position" placeholder="你期待成为怎样的专业人士？" required maxlength="100" /><div class="suggestions"><button v-for="position in positions" :key="position" type="button" :class="{ active: interview.candidate_config.position === position }" @click="interview.candidate_config.position = position">{{ position }}</button></div></div>
          <div class="field-row"><div class="field"><label for="education">学历背景 <span>必填</span></label><input id="education" v-model="interview.candidate_config.education" list="education-options" placeholder="选择或填写学历" required maxlength="100" /><datalist id="education-options"><option>本科</option><option>硕士</option><option>博士</option><option>专科</option></datalist></div><div class="field"><label for="language">面试语言</label><select id="language" v-model="interview.candidate_config.language"><option value="zh-CN">中文 / Chinese</option><option value="en-US">英文 / English</option></select></div></div>
        </fieldset>
        <fieldset class="form-section" :disabled="busy || interview.round > 0 || interview.status !== 'ready'">
          <legend><span>02</span> 你的面试官 <small>THE INTERVIEWER</small></legend>
          <div class="field"><label for="identity">面试官身份</label><input id="identity" v-model="interview.interviewer.role_identity" placeholder="例如：资深后端技术负责人" required maxlength="150" /></div>
          <div class="field"><label for="responsibilities">希望重点聊什么？</label><textarea id="responsibilities" v-model="interview.interviewer.role_responsibilities" rows="3" placeholder="例如：围绕项目经历，重点考察系统设计与问题解决能力。" required maxlength="2000" /><span class="field-note">清晰的面试要求，会让对话更贴近你的目标。</span></div>
        </fieldset>
        <section class="form-section display-section"><h2><SlidersHorizontal :size="17" /> 阅读与动效</h2><label class="switch-row"><span>减少界面动效<small>关闭入场与切页动画，保持安静的阅读节奏。</small></span><input v-model="reduceMotion" type="checkbox" role="switch" /><span class="switch-visual" aria-hidden="true" /></label></section>
        <p v-if="interview.configError" class="error-message" role="alert">{{ interview.configError }}</p>
        <div class="form-bottom"><span><Check v-if="configured" :size="14" />{{ configured ? '当前配置已保存' : '进入前将保存配置，方便下次复用' }}</span><button class="button primary" type="submit" :disabled="!complete || busy || interview.status !== 'ready'">{{ interview.saving ? '准备中…' : '保存并进入面试室' }}<ArrowRight :size="16" /></button></div>
      </form>
      <aside class="settings-aside">
        <div class="glass-rosette" aria-hidden="true"><span>Ⅱ</span></div>
        <div class="aside-copy"><p class="eyebrow">A NOTE BEFORE YOU BEGIN</p><h2>准备充分，<br />也留一点即兴。</h2><p>不必寻找标准答案。<br />把真实的经历、思考与选择，<br />讲成属于自己的故事。</p></div>
        <div class="preset-aside"><span class="eyebrow">PICK UP WHERE YOU LEFT OFF</span><h3>已经有熟悉的配置？</h3><p>从保存的预设中，快速找回状态。</p><PresetPicker :disabled="busy || interview.status !== 'ready' || interview.round > 0" @select="applyPreset" @loading="onPresetLoading" /></div>
      </aside>
    </div>
    <ConfirmDialog v-if="newDialog" title="开始一场新的练习？" description="当前页面将切换到全新的会话。需要留存的对话，可以先到本次回顾中下载。" confirm-label="新建练习" :busy="busy" :error="interview.sessionError" @close="newDialog = false" @confirm="newSession" />
  </div>
</template>
