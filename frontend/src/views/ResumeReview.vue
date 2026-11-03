<template>
  <div v-loading="loading">
    <div class="page-title">生成回顾</div>
    <div class="page-sub">
      任务 #{{ route.params.id }} · 目标岗位：{{ resume?.target_position || resume?.jd_summary?.position || '未识别' }}
      · 创建于 {{ fmt(resume?.created_at) }}
    </div>

    <div class="card-panel" style="margin-bottom:16px">
      <div class="card-body">
        <el-steps :active="activeStep" finish-status="success" align-center>
          <el-step title="填写信息" />
          <el-step title="解析 JD" />
          <el-step title="经历杜撰" />
          <el-step title="必要问答" />
          <el-step title="自我评价问答" />
          <el-step title="生成简历" />
        </el-steps>
        <div style="margin-top:16px">
          <el-button v-if="resume?.status === 'generated'" type="primary" @click="$router.push(`/resume/${resume.id}`)">
            查看详情 / 下载
          </el-button>
          <el-button v-else-if="resume" type="warning" @click="$router.push(`/resume/${resume.id}/edit`)">
            继续生成
          </el-button>
        </div>
      </div>
    </div>

    <el-row :gutter="16">
      <el-col :span="15">
        <!-- 1 填写信息 -->
        <div class="card-panel" style="margin-bottom:16px">
          <div class="card-head">1. 填写信息</div>
          <div class="card-body">
            <div style="margin-bottom:10px"><b>岗位 JD 原文</b></div>
            <div class="jd-text">{{ resume?.jd_text || '（空）' }}</div>
            <el-descriptions :column="1" border size="small" style="margin-top:12px">
              <el-descriptions-item label="意向岗位">{{ resume?.target_position || '（复用基本信息）' }}</el-descriptions-item>
              <el-descriptions-item label="期望薪资">
                {{ resume?.expected_salary || '（复用基本信息）' }}
                <el-tag v-if="resume?.include_salary === false" size="small" type="info" style="margin-left:6px">不写入简历</el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="简历篇幅">{{ lengthLabel }}</el-descriptions-item>
              <el-descriptions-item label="包含模块">
                <el-tag v-for="m in sectionLabels" :key="m" size="small" style="margin:2px">{{ m }}</el-tag>
              </el-descriptions-item>
            </el-descriptions>
            <div class="text-muted" style="font-size:12px;margin-top:10px">如需修改 JD 原文，请新建定向简历任务。</div>
          </div>
        </div>

        <!-- 2 解析 JD -->
        <div class="card-panel" style="margin-bottom:16px">
          <div class="card-head" style="display:flex;justify-content:space-between;align-items:center">
            <span>2. 解析 JD</span>
            <el-button v-if="reached.jd" size="small" type="warning" plain @click="rollback('jd', '解析 JD')">
              <el-icon><RefreshLeft /></el-icon> 从这里重新生成
            </el-button>
          </div>
          <div class="card-body">
            <template v-if="reached.jd">
              <div style="margin-bottom:10px"><b>识别岗位：</b>{{ resume.jd_summary.position || '未识别' }}</div>
              <div style="margin-bottom:10px"><b>技术栈：</b>
                <el-tag v-for="t in (resume.jd_summary.tech || [])" :key="t" style="margin:2px">{{ t }}</el-tag>
              </div>
              <div style="margin-bottom:10px"><b>软素质：</b>
                <el-tag v-for="t in (resume.jd_summary.soft || [])" :key="t" type="info" style="margin:2px">{{ t }}</el-tag>
              </div>
              <div style="margin-bottom:10px"><b>领域方向：</b>
                <el-tag v-for="t in (resume.jd_summary.domain || [])" :key="t" type="warning" style="margin:2px">{{ t }}</el-tag>
              </div>
              <div v-if="(resume.jd_summary.requirements || []).length"><b>核心要求：</b>
                <div v-for="(r, i) in resume.jd_summary.requirements" :key="i">· {{ r }}</div>
              </div>
            </template>
            <el-empty v-else description="尚未解析" :image-size="50" />
          </div>
        </div>

        <!-- 3 经历优化（杜撰 / 润色真实经历） -->
        <div class="card-panel" style="margin-bottom:16px">
          <div class="card-head" style="display:flex;justify-content:space-between;align-items:center">
            <span>3. 经历优化</span>
            <el-button v-if="reached.jd" size="small" type="warning" plain @click="rollback('fabricate', '经历优化')">
              <el-icon><RefreshLeft /></el-icon> 从这里重新生成
            </el-button>
          </div>
          <div class="card-body">
            <template v-if="(resume?.polished_experiences || []).length">
              <el-tag type="success" size="small" style="margin-bottom:8px">采用模式：按 JD 润色真实经历（事实未改动）</el-tag>
              <div v-for="(e, i) in resume.polished_experiences" :key="i" class="exp-item">
                <b>{{ TYPE_LABELS[e.type] || e.type || '经历' }} · {{ e.title }}</b>
                <span v-if="e.role" class="text-muted" style="margin-left:8px">{{ e.role }}</span>
                <span class="text-muted" style="margin-left:8px">{{ e.start_date }} - {{ e.end_date }}</span>
                <div v-if="e.tech_stack" style="margin-top:4px">技术栈：{{ e.tech_stack }}</div>
                <div v-if="e.description" style="margin-top:4px">{{ e.description }}</div>
                <div v-if="e.result" style="margin-top:4px"><b>成果：</b>{{ e.result }}</div>
              </div>
            </template>
            <template v-else-if="versions.length">
              <div v-for="(v, vi) in versions" :key="v.id" class="version-block">
                <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
                  <b>版本 v{{ v.version }}</b>
                  <el-tag v-if="vi === versions.length - 1 && !finalEdited" size="small" type="success">当前采用</el-tag>
                  <span class="text-muted" style="font-size:12px">{{ fmt(v.created_at) }}</span>
                </div>
                <div class="feedback-quote">
                  {{ v.feedback ? `修改意见：${v.feedback}` : 'AI 初稿' }}
                </div>
                <div v-for="(e, i) in v.experiences" :key="i" class="exp-item">
                  <b>{{ TYPE_LABELS[e.type] || e.type || '经历' }} · {{ e.title }}</b>
                  <span v-if="e.role" class="text-muted" style="margin-left:8px">{{ e.role }}</span>
                  <span class="text-muted" style="margin-left:8px">{{ e.start_date }} - {{ e.end_date }}</span>
                  <div v-if="e.tech_stack" style="margin-top:4px">技术栈：{{ e.tech_stack }}</div>
                  <div v-if="e.description" style="margin-top:4px">{{ e.description }}</div>
                  <div v-if="e.result" style="margin-top:4px"><b>成果：</b>{{ e.result }}</div>
                </div>
              </div>
              <div v-if="finalEdited" class="version-block">
                <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
                  <b>最终采用</b>
                  <el-tag size="small" type="success">当前采用</el-tag>
                  <span class="text-muted" style="font-size:12px">含确认前的手动修改</span>
                </div>
                <div v-for="(e, i) in resume.fabricated" :key="i" class="exp-item">
                  <b>{{ TYPE_LABELS[e.type] || e.type || '经历' }} · {{ e.title }}</b>
                  <span v-if="e.role" class="text-muted" style="margin-left:8px">{{ e.role }}</span>
                  <span class="text-muted" style="margin-left:8px">{{ e.start_date }} - {{ e.end_date }}</span>
                  <div v-if="e.tech_stack" style="margin-top:4px">技术栈：{{ e.tech_stack }}</div>
                  <div v-if="e.description" style="margin-top:4px">{{ e.description }}</div>
                  <div v-if="e.result" style="margin-top:4px"><b>成果：</b>{{ e.result }}</div>
                </div>
              </div>
            </template>
            <template v-else-if="reached.fabricate">
              <div class="text-muted" style="font-size:12px;margin-bottom:8px">旧任务未记录版本历史，以下为最终采用内容：</div>
              <div v-for="(e, i) in resume.fabricated" :key="i" class="exp-item">
                <b>{{ TYPE_LABELS[e.type] || e.type || '经历' }} · {{ e.title }}</b>
                <span v-if="e.role" class="text-muted" style="margin-left:8px">{{ e.role }}</span>
                <span class="text-muted" style="margin-left:8px">{{ e.start_date }} - {{ e.end_date }}</span>
                <div v-if="e.tech_stack" style="margin-top:4px">技术栈：{{ e.tech_stack }}</div>
                <div v-if="e.description" style="margin-top:4px">{{ e.description }}</div>
                <div v-if="e.result" style="margin-top:4px"><b>成果：</b>{{ e.result }}</div>
              </div>
            </template>
            <el-empty v-else description="未进行杜撰（或已选择仅使用真实经历）" :image-size="50" />
          </div>
        </div>

        <!-- 4 必要问答 -->
        <div class="card-panel" style="margin-bottom:16px">
          <div class="card-head" style="display:flex;justify-content:space-between;align-items:center">
            <span>4. 必要问答</span>
            <el-button v-if="reached.questions" size="small" type="warning" plain @click="rollback('questions', '必要问答')">
              <el-icon><RefreshLeft /></el-icon> 从这里重新生成
            </el-button>
          </div>
          <div class="card-body">
            <template v-if="reached.questions">
              <div v-for="q in resume.questions" :key="q.id" class="qa-item">
                <div style="font-weight:600">{{ q.question }}</div>
                <div class="qa-answer">{{ answerOf(q.id) || '（未作答）' }}</div>
              </div>
            </template>
            <el-empty v-else description="尚未生成问题" :image-size="50" />
          </div>
        </div>

        <!-- 5 自我评价问答 -->
        <div class="card-panel" style="margin-bottom:16px">
          <div class="card-head" style="display:flex;justify-content:space-between;align-items:center">
            <span>5. 自我评价问答</span>
            <el-button v-if="reached.se" size="small" type="warning" plain @click="rollback('se', '自我评价问答')">
              <el-icon><RefreshLeft /></el-icon> 从这里重新生成
            </el-button>
          </div>
          <div class="card-body">
            <template v-if="reached.se">
              <div v-for="q in resume.se_questions" :key="q.id" class="qa-item">
                <div style="font-weight:600">{{ q.question }}</div>
                <div class="qa-answer">{{ seAnswerOf(q.id) || '（留空）' }}</div>
              </div>
            </template>
            <el-empty v-else description="尚未进入该步骤" :image-size="50" />
          </div>
        </div>

        <!-- 6 生成结果 -->
        <div class="card-panel" style="margin-bottom:16px">
          <div class="card-head">6. 生成结果</div>
          <div class="card-body">
            <template v-if="resume?.status === 'generated'">
              <div style="margin-bottom:10px"><b>使用模板：</b>{{ resume.template }}</div>
              <div style="margin-bottom:10px"><b>个人简介：</b>
                <div style="white-space:pre-wrap;margin-top:4px">{{ resume.personal_summary || '（空）' }}</div>
              </div>
              <div><b>自我评价：</b>
                <div style="white-space:pre-wrap;margin-top:4px">{{ resume.self_evaluation || '（空）' }}</div>
              </div>
            </template>
            <el-empty v-else description="尚未生成简历" :image-size="50" />
          </div>
        </div>
      </el-col>

      <el-col :span="9">
        <div class="card-panel">
          <div class="card-head">进度消息记录（{{ events.length }}）</div>
          <div class="card-body">
            <el-timeline v-if="events.length" style="padding-left:4px">
              <el-timeline-item v-for="e in events" :key="e.id" :timestamp="fmt(e.created_at)" placement="top">
                {{ e.message }}
              </el-timeline-item>
            </el-timeline>
            <el-empty v-else description="暂无进度记录（旧任务未记录）" :image-size="60" />
          </div>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import http from '@/api'

const route = useRoute()
const router = useRouter()

const resume = ref(null)
const events = ref([])
const versions = ref([])
const loading = ref(false)

const MODULE_LABELS = {
  summary: '个人简介', education: '教育背景', internships: '实习经历', work: '工作经历',
  other: '其他经历', skills: '专业技能', projects: '项目经历', certificates: '证书/获奖',
  self_evaluation: '自我评价'
}
const TYPE_LABELS = { internship: '实习', work: '全职', project: '项目', other: '其他' }
const LENGTH_LABELS = {
  fresh: '应届（目标一页）', junior: '1-5 年（2 页以内）', senior: '5 年及以上（3 页以内）'
}

const fmt = (s) => {
  if (!s) return ''
  const d = new Date(s)
  return isNaN(d) ? s : d.toLocaleString('zh-CN', { hour12: false })
}

const activeStep = computed(() => {
  const r = resume.value
  if (!r) return 0
  if (r.status === 'generated') return 6
  if ((r.se_answers || []).length) return 5
  if ((r.answers || []).length) return 4
  if ((r.questions || []).length || (r.fabricated || []).length
      || (r.polished_experiences || []).length
      || Object.keys(r.interview_prep || {}).length) return 3
  if (Object.keys(r.jd_summary || {}).length) return 2
  return r.jd_text ? 1 : 0
})

const reached = computed(() => {
  const r = resume.value || {}
  return {
    jd: Object.keys(r.jd_summary || {}).length > 0,
    fabricate: (r.fabricated || []).length > 0,
    questions: (r.questions || []).length > 0,
    se: (r.se_questions || []).length > 0
  }
})

const lengthLabel = computed(() => {
  const r = resume.value || {}
  return r.length === 'custom'
    ? `自定义（${r.custom_pages || '-'} 页）`
    : (LENGTH_LABELS[r.length] || r.length || '应届（目标一页）')
})

const sectionLabels = computed(() =>
  (resume.value?.sections || []).map((k) => MODULE_LABELS[k] || k))

// 最终采用内容与最后一版不一致时，说明确认前用户做过手动修改
const finalEdited = computed(() => {
  if (!versions.value.length || !reached.value.fabricate) return false
  const last = versions.value[versions.value.length - 1]
  return JSON.stringify(last.experiences || []) !== JSON.stringify(resume.value.fabricated || [])
})

function answerOf(qid) {
  const a = (resume.value?.answers || []).find((x) => x.id === qid)
  return a ? a.answer : ''
}

function seAnswerOf(qid) {
  const a = (resume.value?.se_answers || []).find((x) => x.id === qid)
  return a ? a.answer : ''
}

async function rollback(step, label) {
  try {
    await ElMessageBox.confirm(
      `回退到「${label}」后，该步骤的已填内容会保留以便修改，但其后的全部生成内容将被清除。是否继续？`,
      '确认回退',
      { confirmButtonText: '回退并重新生成', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }
  try {
    await http.post(`/resumes/${route.params.id}/rollback`, { step })
    ElMessage.success(`已回退到「${label}」，请继续生成`)
    router.push(`/resume/${route.params.id}/edit`)
  } catch (e) {
    ElMessage.error(e.message || '回退失败')
  }
}

onMounted(async () => {
  loading.value = true
  try {
    const data = await http.get(`/resumes/${route.params.id}/review`)
    resume.value = data.resume
    // 进度记录按时间倒序展示（最新在前）
    events.value = (data.progress_events || []).slice().reverse()
    versions.value = data.fabricate_versions || []
  } catch (e) {
    ElMessage.error(e.message || '加载回顾失败')
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.jd-text {
  white-space: pre-wrap;
  max-height: 160px;
  overflow: auto;
  background: #f7f8fa;
  border-radius: 6px;
  padding: 10px 12px;
  font-size: 13px;
  color: #606266;
}
.version-block {
  border: 1px solid #e6e8eb;
  border-radius: 8px;
  padding: 12px 14px;
  margin-bottom: 14px;
}
.feedback-quote {
  font-size: 12px;
  color: #909399;
  border-left: 3px solid #dcdfe6;
  padding-left: 8px;
  margin-bottom: 10px;
}
.exp-item {
  padding: 8px 0;
  border-top: 1px dashed #ebeef5;
}
.qa-item {
  margin-bottom: 14px;
}
.qa-answer {
  margin-top: 4px;
  color: #606266;
  background: #f7f8fa;
  border-radius: 6px;
  padding: 8px 10px;
  font-size: 13px;
}
</style>
