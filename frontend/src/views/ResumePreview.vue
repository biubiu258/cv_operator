<template>
  <div class="preview-wrap">
    <div class="toolbar no-print">
      <el-button @click="$router.back()"><el-icon><Back /></el-icon> 返回</el-button>
      <span class="text-muted" style="font-size:13px">网页版模板仅支持在线预览与打印导出 PDF；下载 Word 将使用兼容版式</span>
      <el-button :loading="pdfBusy" @click="doDownloadPdf"><el-icon><Download /></el-icon> 下载 PDF</el-button>
      <el-button type="primary" @click="doPrint"><el-icon><Printer /></el-icon> 打印 / 导出 PDF</el-button>
    </div>
    <div v-loading="loading" style="min-height:60vh">
      <component :is="tplComp" v-if="ctx" :ctx="ctx" />
      <el-empty v-else-if="!loading" description="渲染数据加载失败" :image-size="70" />
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import http from '@/api'
import WarmTemplate from '@/components/WarmTemplate.vue'
import NavyTemplate from '@/components/NavyTemplate.vue'

// 网页版模板注册表：新增 vue 模板时在此登记
const VUE_TEMPLATES = {
  warm_vue: WarmTemplate,
  navy_vue: NavyTemplate,
}

const route = useRoute()
const ctx = ref(null)
const loading = ref(false)
const tplComp = computed(() => VUE_TEMPLATES[ctx.value?.template] || WarmTemplate)

function doPrint() {
  window.print()
}

// 前端直接生成 PDF：html2canvas-pro 支持 clip-path（斜切色块/箭头标题条），
// jsPDF 按 A4 分页切片，文件名用规范命名，不依赖浏览器打印对话框是否遵循 document.title
const pdfBusy = ref(false)
async function doDownloadPdf() {
  if (!ctx.value || pdfBusy.value) return
  pdfBusy.value = true
  try {
    const [{ default: html2canvas }, { jsPDF }] = await Promise.all([
      import('html2canvas-pro'),
      import('jspdf'),
    ])
    const el = document.querySelector('.resume-page')
    if (!el) throw new Error('未找到简历渲染区域')
    const canvas = await html2canvas(el, { scale: 2, useCORS: true, backgroundColor: '#ffffff' })
    // 裁掉底部空白行：元素 min-height/内边距/亚像素取整会在尾部留下空白，
    // 直接按画布高度 ceil 分页会多出一张近空白页
    const c2d = canvas.getContext('2d')
    const img = c2d.getImageData(0, 0, canvas.width, canvas.height).data
    let lastRow = 0
    for (let y = canvas.height - 1; y >= 0; y--) {
      let blank = true
      for (let x = 0; x < canvas.width; x++) {
        const i = (y * canvas.width + x) * 4
        if (img[i] < 250 || img[i + 1] < 250 || img[i + 2] < 250) { blank = false; break }
      }
      if (!blank) { lastRow = y; break }
    }
    const contentH = lastRow + 1
    // 切片分页：A4 宽 210mm，按 canvas 宽度换算每页像素高度
    const pxPerMm = canvas.width / 210
    const pageHpx = Math.floor(297 * pxPerMm)
    const pdf = new jsPDF('p', 'mm', 'a4')
    // 减去极小容差，避免刚好整除时因浮点误差多算一页
    const pageCount = Math.max(1, Math.ceil(contentH / pageHpx - 1e-6))
    for (let i = 0; i < pageCount; i++) {
      const sliceH = Math.min(pageHpx, contentH - i * pageHpx)
      const slice = document.createElement('canvas')
      slice.width = canvas.width
      slice.height = sliceH
      slice.getContext('2d').drawImage(canvas, 0, i * pageHpx, canvas.width, sliceH, 0, 0, canvas.width, sliceH)
      if (i) pdf.addPage()
      const hMm = sliceH / pxPerMm
      pdf.addImage(slice.toDataURL('image/jpeg', 0.95), 'JPEG', 0, 0, 210, hMm)
    }
    pdf.save(`${resumeBasename(ctx.value.user)}.pdf`)
  } catch (e) {
    ElMessage.error(e.message || '生成 PDF 失败')
  } finally {
    pdfBusy.value = false
  }
}

// 规范命名：姓名-xx届-求职意向（缺失字段省略），浏览器打印导出 PDF 默认取 document.title 作为文件名，
// 与后端 Word/PDF 产物命名规则保持一致
function resumeBasename(user) {
  const parts = [(user?.name || '').trim() || '简历']
  const grad = (user?.graduation_date || '').trim().match(/(\d{4})/)
  if (grad) parts.push(grad[1].slice(2) + '届') // 2026 -> 26届
  const pos = (user?.target_position || '').trim()
  if (pos) parts.push(pos)
  return parts.join('-').replace(/[\\/:*?"<>|\r\n\t]+/g, '') || '简历'
}

onMounted(async () => {
  loading.value = true
  try {
    ctx.value = await http.get(`/resumes/${route.params.id}/render-context`)
    document.title = resumeBasename(ctx.value.user)
  } catch (e) {
    ElMessage.error(e.message || '加载渲染数据失败')
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.preview-wrap { background: #eee; min-height: 100vh; padding: 20px; }
.toolbar {
  max-width: 210mm; margin: 0 auto 16px;
  display: flex; align-items: center; gap: 12px;
}
.toolbar .el-button:last-child { margin-left: auto; }

@media print {
  .preview-wrap { padding: 0; background: #fff; }
  .no-print { display: none; }
}
</style>

<!-- @page 不能放在 scoped 样式中（会被加上作用域属性而失效），单独非作用域声明。
     margin: 0 使浏览器页眉/页脚（网站名、网址、日期、页码）无处渲染从而消失，
     页边距改由 .resume-page 自身的 padding 承担 -->
<style>
@page { size: A4; margin: 0; }
</style>
