import { ref, watch } from 'vue'
function readMotion() { try { return localStorage.getItem('northwind.reduce-motion') === 'true' } catch { return false } }
export const reduceMotion = ref(readMotion())
watch(reduceMotion, value => {
  document.documentElement.dataset.reduceMotion = String(value)
  try { localStorage.setItem('northwind.reduce-motion', String(value)) } catch { /* storage is optional */ }
}, { immediate: true })
