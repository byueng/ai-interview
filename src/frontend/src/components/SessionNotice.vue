<script setup lang="ts">
import { AlertCircle, RotateCcw, Plus } from 'lucide-vue-next'
import { interview, connect, busy } from '../state/interview'
</script>
<template>
  <div v-if="interview.status === 'initializing'" class="session-notice subtle" role="status"><span class="loading-dot" />正在准备你的练习空间…</div>
  <div v-else-if="interview.sessionError" class="session-notice" role="alert"><AlertCircle :size="18" /><div><strong>暂时无法连接会话</strong><p>{{ interview.sessionError }}</p></div><div class="notice-actions"><button class="text-button" :disabled="busy" @click="connect('continue')"><RotateCcw :size="14" />重新连接</button><button class="text-button" :disabled="busy" @click="connect('new')"><Plus :size="14" />新建会话</button></div></div>
</template>
