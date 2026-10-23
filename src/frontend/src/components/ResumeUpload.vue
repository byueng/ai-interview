<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { FileText, Upload } from 'lucide-vue-next'
import { uploadResume } from '../api/resume'
import { busy, interview } from '../state/interview'

const selected = ref<File | null>(null)
const error = ref('')
const input = ref<HTMLInputElement | null>(null)
let controller: AbortController | undefined
const disabled = computed(() => busy.value || interview.round > 0 || interview.status !== 'ready')
const attachedName = computed(() => interview.candidate.resume?.split(/[\\/]/).pop() || 'PDF 简历')
function choose(event: Event) {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  target.value = ''
  if (!file) return
  error.value = ''
  selected.value = null
  if (!/\.pdf$/i.test(file.name) || (file.type && !['application/pdf', 'application/octet-stream'].includes(file.type))) {
    error.value = '目前仅支持 PDF 文件。'
  } else if (!file.size) {
    error.value = '该文件为空，请重新选择。'
  } else {
    selected.value = file
  }
}
async function submit() {
  if (!selected.value || disabled.value) return
  controller = new AbortController()
  interview.uploadingResume = true
  error.value = ''
  try {
    interview.candidate.resume = await uploadResume(selected.value, controller.signal)
    selected.value = null
  } catch (cause) {
    if (!controller.signal.aborted) error.value = cause instanceof Error ? cause.message : '上传失败，请检查网络后重试。'
  } finally {
    interview.uploadingResume = false
  }
}
onBeforeUnmount(() => controller?.abort())
</script>

<template>
  <aside class="resume-panel" aria-labelledby="resume-heading" :aria-busy="interview.uploadingResume">
    <p class="eyebrow">YOUR RESUME</p>
    <h2 id="resume-heading">加载简历</h2>
    <p class="resume-intro">让下一场对话，从你的经历开始。</p>
    <div class="resume-file-area">
      <FileText :size="34" aria-hidden="true" />
      <strong>{{ selected ? selected.name : '准备好你的简历' }}</strong>
      <span>{{ selected ? `${(selected.size / 1024).toFixed(1)} KB · PDF` : '仅支持 PDF 格式' }}</span>
      <input ref="input" type="file" accept=".pdf,application/pdf" aria-label="选择 PDF 简历" :disabled="disabled" @change="choose" />
      <button class="button" type="button" :disabled="disabled" @click="input?.click()">{{ selected ? '重新选择' : '选择 PDF' }}</button>
    </div>
    <button v-if="selected" type="button" class="button primary resume-submit" :disabled="disabled" @click="submit"><Upload :size="15" />{{ interview.uploadingResume ? '正在上传…' : '上传简历' }}</button>
    <button v-if="selected && !interview.uploadingResume" type="button" class="text-button" :disabled="disabled" @click="selected = null; error = ''">取消选择</button>
    <p v-if="error" class="error-message" role="alert">{{ error }}</p>
    <div v-if="interview.candidate.resume" class="resume-attached" role="status">
      <span>已关联简历</span><strong>{{ attachedName }}</strong>
      <button type="button" class="text-button" :disabled="disabled" @click="interview.candidate.resume = null">移除关联</button>
    </div>
    <p class="resume-note">简历为选填项。上传后用于面试准备，你也可以直接填写右侧信息。</p>
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
.resume-submit { width: 100%; margin-bottom: 12px; }
.resume-attached { display: flex; flex-direction: column; gap: 12px; border-top: 1px solid #826d4760; margin-top: 20px; padding-top: 20px; font-size: 12px; }
.resume-note { margin-top: 24px; font-size: 12px; }
</style>
