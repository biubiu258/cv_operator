<template>
  <div>
    <div class="page-title">简历详情</div>
    <div class="page-sub">任务 #{{ resume?.id }} · 目标岗位：{{ resume?.target_position || resume?.jd_summary?.position || '未识别' }}</div>

    <div class="card-panel" style="margin-bottom:16px">
      <div class="card-body">
        <el-space wrap>
          <el-button @click="$router.push(`/resume/${route.params.id}/review`)">
            <el-icon><Clock /></el-icon> 生成回顾
          </el-button>
          <el-button v-if="resume && resume.status !== 'generated'" type="warning" @click="$router.push(`/resume/${resume.id}/edit`)">继续生成</el-button>

          <template v-if="resume?.status === 'generated'">
            <span class="text-muted">Word 模板</span>
            <el-select v-model="docxTemplate" size="small" style="width:160px" placeholder="选择 Word 模板">
              <el-option v-for="t in docxTemplates" :key="t.key" :label="t.label" :value="t.key" />
            </el-select>
            <span class="text-muted">网页版模板</span>
            <el-select v-model="vueTemplate" size="small" style="width:180px" placeholder="选择网页版模板">
              <el-option v-for="t in vueTemplates" :key="t.key" :label="t.label" :value="t.key" />
            </el-select>
            <el-button :loading="rebuilding" @click="rebuild">
              <el-icon><RefreshRight /></el-icon> 重新生成
            </el-button>
            <el-button v-if="isVueTemplate" type="primary" plain @click="$router.push(`/resume/${resume.id}/preview`)">
              <el-icon><View /></el-icon> 在线预览
            </el-button>
          </template>

          <el-button type="primary" :disabled="!resume?.output_path || isVueTemplate" @click="download('docx')">
            <el-icon><Download /></el-icon> 下载 Word
          </el-button>
          <el-button type="success" :disabled="!resume?.output_path || isVueTemplate" :loading="converting" @click="toPdf">
            <el-icon><Download /></el-icon> 下载 PDF
          </el-button>
          <span v-if="isVueTemplate" class="text-muted" style="font-size:12px">网页版模板与 Word 相互独立，请通过「在线预览」打印导出 PDF</span>
        </el-space>
      </div>
    </div>

    <div class="card-panel" style="margin-top:16px" v-if="resume">
      <div class="card-head" style="display:flex;justify-content:space-between;align-items:center">
        <span>简历模块</span>
        <el-button size="small" type="primary" :loading="saving" @click="saveSections">保存模块选择</el-button>
      </div>
      <div class="card-body">
        <el-checkbox-group v-model="sectionsSel">
          <el-checkbox v-for="m in MODULES" :key="m.key" :label="m.key">{{ m.label }}</el-checkbox>
        </el-checkbox-group>
        <div class="text-muted" style="font-size:12px;margin-top:8px">决定最终简历包含哪些板块；全部不勾选时默认使用全部模块</div>
      </div>
    </div>

    <el-row :gutter="16" style="margin-top:16px">
      <el-col :span="12">
        <div class="card-panel">
          <div class="card-head">JD 解析</div>
          <div class="card-body">
            <div style="margin-bottom:10px"><b>技术栈：</b>
              <el-tag v-for="t in (resume?.jd_summary?.tech || [])" :key="t" style="margin:2px">{{ t }}</el-tag>
            </div>
            <div style="margin-bottom:10px"><b>软素质：</b>
              <el-tag v-for="t in (resume?.jd_summary?.soft || [])" :key="t" type="info" style="margin:2px">{{ t }}</el-tag>
            </div>
            <div><b>领域方向：</b>
              <el-tag v-for="t in (resume?.jd_summary?.domain || [])" :key="t" type="warning" style="margin:2px">{{ t }}</el-tag>
            </div>
          </div>
        </div>
      </el-col>
      <el-col :span="12">
        <div class="card-panel">
          <div class="card-head" style="display:flex;justify-content:space-between;align-items:center">
            <span>个人简介</span>
            <el-button v-if="editing !== 'summary'" size="small" @click="startEdit('summary')">
              <el-icon><Edit /></el-icon> 编辑
            </el-button>
          </div>
          <div class="card-body">
            <template v-if="editing === 'summary'">
              <el-input v-model="draft" type="textarea" :rows="5" />
              <div style="margin-top:8px">
                <el-button size="small" type="primary" :loading="saving" @click="saveEdit">保存</el-button>
                <el-button size="small" @click="cancelEdit">取消</el-button>
                <span class="text-muted" style="font-size:12px;margin-left:8px">用 **文字** 标记需要加粗高亮的内容</span>
              </div>
            </template>
            <RichText v-else-if="resume?.personal_summary" :text="resume.personal_summary" />
            <span v-else class="text-muted">尚未生成</span>
          </div>
        </div>
      </el-col>
    </el-row>

    <div class="card-panel" style="margin-top:16px">
      <div class="card-head" style="display:flex;justify-content:space-between;align-items:center">
        <span>自我评价</span>
        <el-space v-if="editing !== 'se'">
          <el-button size="small" @click="startEdit('se')">
            <el-icon><Edit /></el-icon> 编辑
          </el-button>
          <el-button v-if="resume?.self_evaluation" size="small" type="primary" plain @click="saveToHistory">
            <el-icon><Star /></el-icon> 保存到历史记录
          </el-button>
        </el-space>
      </div>
      <div class="card-body">
        <template v-if="editing === 'se'">
          <el-input v-model="draft" type="textarea" :rows="6" />
          <div style="margin-top:8px">
            <el-button size="small" type="primary" :loading="saving" @click="saveEdit">保存</el-button>
            <el-button size="small" @click="cancelEdit">取消</el-button>
            <span class="text-muted" style="font-size:12px;margin-left:8px">用 **文字** 标记需要加粗高亮的内容</span>
          </div>
        </template>
        <RichText v-else-if="resume?.self_evaluation" :text="resume.self_evaluation" />
        <span v-else class="text-muted">尚未生成</span>
      </div>
    </div>

    <div class="card-panel" style="margin-top:16px" v-if="(resume?.fabricated || []).length">
      <div class="card-head">杜撰经历（已并入简历，面试需能自圆其说）</div>
      <div class="card-body">
        <div v-for="(e, i) in resume.fabricated" :key="i" style="margin-bottom:14px">
          <b>{{ e.type === 'internship' ? '实习' : '项目' }} · {{ e.title }}</b>
          <span class="text-muted" style="margin-left:8px">{{ e.start_date }} - {{ e.end_date }}</span>
          <div v-if="e.tech_stack" style="margin-top:4px">技术栈：{{ e.tech_stack }}</div>
          <div v-if="e.description" style="margin-top:4px"><RichText :text="e.description" /></div>
          <div v-if="e.result" style="margin-top:4px"><b>成果：</b><RichText :text="e.result" /></div>
        </div>
      </div>
    </div>

    <div class="card-panel" style="margin-top:16px" v-if="resume?.interview_prep?.knowledge_points?.length || resume?.interview_prep?.high_freq_questions?.length">
      <div class="card-head">面试准备</div>
      <div class="card-body">
        <div v-if="(resume.interview_prep.knowledge_points || []).length">
          <div style="font-weight:600;margin-bottom:8px">重点记忆知识点</div>
          <div v-for="(k, i) in resume.interview_prep.knowledge_points" :key="i" style="margin-bottom:4px">· {{ k }}</div>
        </div>
        <el-divider v-if="(resume.interview_prep.knowledge_points || []).length && (resume.interview_prep.high_freq_questions || []).length" />
        <div v-if="(resume.interview_prep.high_freq_questions || []).length">
          <div style="font-weight:600;margin-bottom:8px">高频面试问题</div>
          <div v-for="(q, i) in resume.interview_prep.high_freq_questions" :key="i" style="margin-bottom:12px">
            <div><b>{{ i + 1 }}. {{ q.question }}</b></div>
            <div v-if="q.hint" class="text-muted" style="font-size:13px;margin-top:2px">要点：{{ q.hint }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import http, { downloadUrl } from '@/api'
import RichText from '@/components/RichText.vue'

const MODULES = [
  { key: 'summary', label: '个人简介' },
  { key: 'education', label: '教育背景' },
  { key: 'skills', label: '专业技能' },
  { key: 'internships', label: '实习经历' },
  { key: 'work', label: '工作经历' },
  { key: 'other', label: '其他经历' },
  { key: 'projects', label: '项目经历' },
  { key: 'certificates', label: '证书/获奖' },
  { key: 'self_evaluation', label: '自我评价' }
]

const route = useRoute()
const resume = ref(null)
const converting = ref(false)
const rebuilding = ref(false)
const saving = ref(false)
const template = ref('classic')
const templateList = ref([])
const sectionsSel = ref([])
const editing = ref('') // 'summary' | 'se' | ''
const draft = ref('')

const isVueTemplate = computed(() =>
  templateList.value.find((t) => t.key === template.value)?.kind === 'vue')

// 模板选择器拆分为两个独立选择框：Word 与网页版各选各的，未激活的一方显示占位
const docxTemplates = computed(() => templateList.value.filter((t) => t.kind !== 'vue'))
const vueTemplates = computed(() => templateList.value.filter((t) => t.kind === 'vue'))
const docxTemplate = computed({
  get: () => (isVueTemplate.value ? '' : template.value),
  set: (v) => { if (v) changeTemplate(v) }
})
const vueTemplate = computed({
  get: () => (isVueTemplate.value ? template.value : ''),
  set: (v) => { if (v) changeTemplate(v) }
})

onMounted(async () => {
  resume.value = await http.get(`/resumes/${route.params.id}`)
  template.value = resume.value.template || 'classic'
  sectionsSel.value = resume.value.sections || []
  templateList.value = await http.get('/resumes/templates')
})

async function changeTemplate(val) {
  if (!resume.value?.id) return
  rebuilding.value = true
  try {
    const updated = await http.post(`/resumes/${resume.value.id}/rebuild`, { template: val })
    // 同步本地状态（含跨板块切换后新生成的 output_path），否则需刷新页面才生效
    resume.value = { ...resume.value, ...updated }
    template.value = val
    ElMessage.success('已切换模板')
  } catch (e) {
    template.value = resume.value.template || 'classic'
    ElMessage.error(e.message || '切换模板失败')
  } finally {
    rebuilding.value = false
  }
}

async function rebuild() {
  if (!resume.value?.id) return
  rebuilding.value = true
  try {
    const updated = await http.post(`/resumes/${resume.value.id}/rebuild`, {})
    resume.value = { ...resume.value, ...updated }
    ElMessage.success('已重新生成')
  } catch (e) {
    ElMessage.error(e.message || '重新生成失败')
  } finally {
    rebuilding.value = false
  }
}

function download(format) {
  window.open(downloadUrl(route.params.id, format), '_blank')
}

// 编辑保存：先更新数据库内容，docx 模板再触发重新排版使下载文件同步；
// 网页版模板预览实时读取 render-context，无需重排
async function saveFields(payload) {
  saving.value = true
  try {
    const updated = await http.put(`/resumes/${resume.value.id}`, payload)
    resume.value = { ...resume.value, ...updated }
    if (resume.value.status === 'generated' && !isVueTemplate.value) {
      await http.post(`/resumes/${resume.value.id}/rebuild`, {})
      ElMessage.success('已保存并重新排版')
    } else {
      ElMessage.success('已保存')
    }
    return true
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
    return false
  } finally {
    saving.value = false
  }
}

function startEdit(field) {
  editing.value = field
  draft.value = field === 'summary'
    ? (resume.value.personal_summary || '')
    : (resume.value.self_evaluation || '')
}

function cancelEdit() {
  editing.value = ''
  draft.value = ''
}

async function saveEdit() {
  const payload = editing.value === 'summary'
    ? { personal_summary: draft.value }
    : { self_evaluation: draft.value }
  if (await saveFields(payload)) cancelEdit()
}

async function saveSections() {
  if (await saveFields({ sections: sectionsSel.value })) {
    resume.value.sections = sectionsSel.value
  }
}

async function toPdf() {
  converting.value = true
  try {
    await http.post(`/resumes/${route.params.id}/convert`)
    download('pdf')
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    converting.value = false
  }
}

async function saveToHistory() {
  try {
    await http.post('/self-evaluation/records', {
      content: resume.value.self_evaluation,
      resume_id: resume.value.id
    })
    ElMessage.success('已保存到自我评价历史记录')
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  }
}
</script>