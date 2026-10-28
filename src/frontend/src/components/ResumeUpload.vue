<script setup lang="ts">
import { computed, markRaw, ref } from 'vue'
import { FileText } from 'lucide-vue-next'
import { validateResume } from '../api/resume'
import { busy, interview } from '../state/interview'

const selected = computed({
  get: () => interview.pendingResume,
  set: (file: File | null) => { interview.pendingResume = file ? markRaw(file) : null },
})
const error = ref('')
const input = ref<HTMLInputElement | null>(null)
const disabled = computed(() => busy.value || interview.round > 0 || interview.status !== 'ready')
const attachedName = computed(() => interview.uploadedResumePath?.split(/[\\/]/).pop() || '简历.pdf')
function choose(event: Event) {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  target.value = ''
  if (!file) return
  error.value = ''
  try {
    validateResume(file)
    selected.value = file
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '请选择有效的 PDF 简历。'
  }
}
</script>

<template>
  <aside class="resume-panel" aria-labelledby="resume-heading" :aria-busy="interview.uploadingResume">
    <p class="eyebrow">YOUR RESUME</p>
    <h2 id="resume-heading">选择简历</h2>
    <p class="resume-intro">选择 PDF，保存面试配置时一起上传。</p>
    <div class="resume-file-area">
      <FileText :size="34" aria-hidden="true" />
      <strong>{{ selected ? selected.name : '准备好你的简历' }}</strong>
      <span>{{ selected ? `${(selected.size / 1024).toFixed(1)} KB · PDF` : '仅支持 PDF 格式' }}</span>
      <input ref="input" type="file" accept=".pdf,application/pdf" aria-label="选择 PDF 简历" :disabled="disabled" @change="choose" />
      <button class="button" type="button" :disabled="disabled" @click="input?.click()">{{ selected ? '重新选择' : '选择 PDF' }}</button>
    </div>
    <p v-if="selected" role="status">{{ interview.saving ? '正在保存配置和简历…' : '待保存：点击“保存并进入面试室”后上传。' }}</p>
    <button v-if="selected" type="button" class="text-button" :disabled="disabled" @click="selected = null; error = ''">取消选择</button>
    <p v-if="error" class="error-message" role="alert">{{ error }}</p>
    <div v-if="interview.uploadedResumePath" class="resume-attached" role="status">
      <span>已上传</span><strong>{{ attachedName }}</strong>
    </div>
    <p class="resume-note">简历为选填项。保存后，将在开始对话时交给模型分析。重新选择并保存后会替换本次会话的简历。</p>
  </aside>
</template>

<style scoped>
.resume-panel { align-self: start; padding: 27px 22px; border: 1px solid #826d4780; background: linear-gradient(150deg,#142a3bed,#171e2de8); color: var(--text); }
h2 { margin: 14px 0; color: #d8c59c; font-size: 25px; font-weight: 400; }
.resume-intro,.resume-note { color: #a6b0ba; font-size: 13px; line-height: 1.9; }
.resume-file-area { margin: 25px 0 16px; border: 1px dashed #98825d; padding: 24px 12px; display: flex; flex-direction: column; align-items: center; gap: 15px; text-align: center; color: #c5af80; }
.resume-file-area strong,.resume-attached strong { overflow-wrap: anywhere; max-width: 100%; font-size: 13px; font-weight: 400; }
.resume-file-area span { font-size: 11px; color: #a6b0ba; }
.resume-file-area input { display: none; }
.resume-attached { display: flex; flex-direction: column; gap: 12px; border-top: 1px solid #826d4760; margin-top: 20px; padding-top: 20px; font-size: 12px; }
.resume-note { margin-top: 24px; font-size: 12px; }
</style>
