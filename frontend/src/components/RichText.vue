<template>
  <span class="rich-text"><span v-for="(s, i) in segs" :key="i" :class="{ hl: s.em }">{{ s.t }}</span></span>
</template>

<script setup>
import { computed } from 'vue'

// 将 **强调** 标记渲染为蓝色加粗，与简历模板（docx 蓝色加粗高亮）的展示效果一致
const props = defineProps({
  text: { type: String, default: '' }
})

const segs = computed(() =>
  (props.text || '').split(/(\*\*.+?\*\*)/).filter(Boolean).map((s) =>
    s.startsWith('**') && s.endsWith('**') && s.length > 4
      ? { t: s.slice(2, -2), em: true }
      : { t: s, em: false })
)
</script>

<style scoped>
.rich-text { white-space: pre-wrap; }
.hl { color: #0563c1; font-weight: bold; }
</style>
