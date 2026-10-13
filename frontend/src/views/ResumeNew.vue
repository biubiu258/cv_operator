<template>
  <div>
    <div class="page-title">{{ editId ? '继续生成简历' : '新建定向简历' }}</div>
    <div class="page-sub">粘贴岗位 JD，AI 解析并生成必要问题，随后输出含定制自我评价的定向简历</div>

    <div class="card-panel">
      <div class="card-body">
        <el-steps :active="step" finish-status="success" align-center style="margin-bottom:28px">
          <el-step title="填写信息" />
          <el-step title="解析 JD" />
          <el-step title="经历杜撰(可选)" />
          <el-step title="回答必要问题" />
          <el-step title="自我评价问答" />
          <el-step title="生成简历" />
        </el-steps>

        <el-alert v-if="aiStatus" type="info" :closable="false" style="margin-bottom:20px">
          <template #title>
            <el-icon class="is-loading" style="vertical-align:-2px"><Loading /></el-icon>
            <span style="margin-left:6px">{{ aiStatus }}</span>
          </template>
        </el-alert>

        <!-- 0 输入 JD + 意向岗位(可选) + 模块选择 -->
        <div v-if="step === 0">
          <div style="font-weight:600;margin-bottom:8px">岗位 JD</div>
          <el-input v-model="jdText" type="textarea" :rows="9" placeholder="这里粘贴岗位 JD 全文…" />

          <div style="font-weight:600;margin:20px 0 8px">意向岗位（可选，不填则复用基本信息中的目标岗位）</div>
          <el-input v-model="targetPosition" placeholder="如：AI Agent 开发工程师" style="max-width:360px" />

          <div style="font-weight:600;margin:20px 0 8px">期望薪资（可选，不填则复用基本信息中的期望薪资）</div>
          <el-input v-model="expectedSalary" placeholder="如：15K-20K 或 面议" style="max-width:360px" />
          <div style="margin-top:10px;display:flex;align-items:center;gap:8px">
            <el-switch v-model="includeSalary" />
            <span class="text-muted" style="font-size:12px">简历中包含「期望薪资」条目</span>
          </div>

          <div style="font-weight:600;margin:20px 0 8px">简历包含的模块（默认包含档案中全部信息）</div>
          <el-checkbox-group v-model="sections">
            <el-checkbox v-for="m in MODULES" :key="m.key" :label="m.key">{{ m.label }}</el-checkbox>
          </el-checkbox-group>
          <div class="text-muted" style="font-size:12px;margin-top:8px">已勾选的模块将写入简历；自我评价固定置于简历最下方一栏。</div>

          <div style="margin-top:20px">
            <el-button type="primary" :loading="busy" @click="createTask">创建任务并解析</el-button>
          </div>
        </div>

        <!-- 1 解析结果 -->
        <div v-else-if="step === 1">
          <el-descriptions :column="1" border>
            <el-descriptions-item label="意向岗位">
              {{ targetPosition || jdSummary.position || '未识别（将复用基本信息）' }}
            </el-descriptions-item>
            <el-descriptions-item label="技术栈">
              <el-tag v-for="t in jdSummary.tech" :key="t" style="margin:2px">{{ t }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="软素质">
              <el-tag v-for="t in jdSummary.soft" :key="t" type="info" style="margin:2px">{{ t }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="领域方向">
              <el-tag v-for="t in jdSummary.domain" :key="t" type="warning" style="margin:2px">{{ t }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="核心要求">
              <div v-for="(r, i) in jdSummary.requirements" :key="i">· {{ r }}</div>
            </el-descriptions-item>
          </el-descriptions>
          <div style="margin-top:16px">
            <el-button @click="step = 0">返回修改</el-button>
            <el-button type="primary" :disabled="parsing" :loading="parsing" @click="step = 2">下一步：经历杜撰</el-button>
          </div>
        </div>

        <!-- 2 经历杜撰（可选）：生成 → 编辑/提意见让 AI 改 → 确认 -->
        <div v-else-if="step === 2">
          <template v-if="fabricatePhase === 'config'">
            <div class="page-sub" style="margin-bottom:16px">
              该步骤可选：是否由 AI 生成与 JD 匹配的经历，填充简历空白？
            </div>
            <el-radio-group v-model="fabricateMode">
              <el-radio :label="true">杜撰经历（AI 生成，便于匹配 JD）</el-radio>
              <el-radio :label="false">只使用我的真实经历</el-radio>
            </el-radio-group>

            <template v-if="fabricateMode">
              <div style="font-weight:600;margin:20px 0 8px">其他岗位 JD（可选，用于生成更真实的经历）</div>
              <el-input v-model="fabricateJd" type="textarea" :rows="3" placeholder="粘贴一个真实存在的公司+岗位 JD，AI 将据此生成更贴合、可经得起背调的经历…" />
              <div class="text-muted" style="font-size:12px;margin-top:4px">公司真实存在、岗位真实存在，只是求职者未真实入职。</div>

              <div style="font-weight:600;margin:20px 0 8px">生成方式（可多选混合）</div>
              <el-checkbox-group v-model="fabricateTypes">
                <el-checkbox label="internship">实习</el-checkbox>
                <el-checkbox label="work">全职</el-checkbox>
                <el-checkbox label="project">项目</el-checkbox>
                <el-checkbox label="other">其他</el-checkbox>
              </el-checkbox-group>

              <div style="font-weight:600;margin:20px 0 8px">生成数量（最高 5 段）</div>
              <el-input-number v-model="fabricateCount" :min="1" :max="5" />
            </template>

            <div class="text-muted" style="font-size:12px;margin-top:12px">
              生成后可逐项修改，或对 AI 提出整体修改意见让其调整。
            </div>
            <div style="margin-top:20px">
              <el-button @click="step = 1">上一步</el-button>
              <el-button v-if="fabricateMode" type="primary" :loading="busy" @click="generateFabricated">生成经历</el-button>
              <el-button v-else type="primary" :loading="busy" @click="confirmAndContinue">继续（使用真实经历）</el-button>
            </div>
          </template>

          <template v-else>
            <div class="page-sub" style="margin-bottom:8px">
              已生成 {{ fabricated.length }} 段经历，可逐项修改，或在下方对 AI 提出整体修改意见。
            </div>

            <div v-for="(e, i) in fabricated" :key="i" style="border:1px solid #e6e8eb;border-radius:8px;padding:14px;margin-bottom:14px">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
                <b>第 {{ i + 1 }} 段</b>
                <el-button size="small" type="danger" text @click="removeFabricated(i)">删除</el-button>
              </div>
              <el-row :gutter="10">
                <el-col :span="8">
                  <div class="text-muted" style="font-size:12px;margin-bottom:4px">类型</div>
                  <el-select v-model="e.type" style="width:100%">
                    <el-option value="project" label="项目经历" />
                    <el-option value="internship" label="实习经历" />
                    <el-option value="work" label="全职经历" />
                    <el-option value="other" label="其他经历" />
                  </el-select>
                </el-col>
                <el-col :span="8">
                  <div class="text-muted" style="font-size:12px;margin-bottom:4px">项目/公司名</div>
                  <el-input v-model="e.title" placeholder="项目名 / 公司名" />
                </el-col>
                <el-col :span="8">
                  <div class="text-muted" style="font-size:12px;margin-bottom:4px">角色/职位</div>
                  <el-input v-model="e.role" placeholder="角色 / 职位" />
                </el-col>
              </el-row>
              <el-row :gutter="10" style="margin-top:10px">
                <el-col :span="8">
                  <div class="text-muted" style="font-size:12px;margin-bottom:4px">开始时间</div>
                  <el-input v-model="e.start_date" placeholder="YYYY.MM" />
                </el-col>
                <el-col :span="8">
                  <div class="text-muted" style="font-size:12px;margin-bottom:4px">结束时间</div>
                  <el-input v-model="e.end_date" placeholder="YYYY.MM" />
                </el-col>
                <el-col :span="8">
                  <div class="text-muted" style="font-size:12px;margin-bottom:4px">技术栈</div>
                  <el-input v-model="e.tech_stack" placeholder="如 Python、Vue" />
                </el-col>
              </el-row>
              <div class="text-muted" style="font-size:12px;margin:10px 0 4px">核心工作</div>
              <el-input v-model="e.description" type="textarea" :rows="2" />
              <div class="text-muted" style="font-size:12px;margin:10px 0 4px">量化成果</div>
              <el-input v-model="e.result" type="textarea" :rows="2" />
            </div>

            <div style="font-weight:600;margin:8px 0 6px">给 AI 的修改意见（可选）</div>
            <el-input v-model="userFeedback" type="textarea" :rows="3" placeholder="例如：第一段成果请量化更具体；把实习改成项目经历；整体语气更正式…" />

            <div style="margin-top:16px">
              <el-button @click="fabricatePhase = 'config'">返回设置</el-button>
              <el-button :loading="busy" @click="reviseFabricated">让 AI 按意见修改</el-button>
              <el-button type="primary" :loading="busy" @click="confirmAndContinue">确认并继续</el-button>
            </div>
          </template>
        </div>

        <!-- 3 回答必要问题 -->
        <div v-else-if="step === 3">
          <div v-for="q in questions" :key="q.id" style="margin-bottom:20px">
            <div style="font-weight:600;margin-bottom:10px">{{ q.question }}</div>
            <el-radio-group v-if="q.type === 'choice'" v-model="ans[q.id]">
              <el-radio v-for="o in q.options" :key="o" :label="o">{{ o }}</el-radio>
            </el-radio-group>
            <el-checkbox-group v-else-if="q.type === 'multi'" v-model="ans[q.id]">
              <el-checkbox v-for="o in q.options" :key="o" :label="o">{{ o }}</el-checkbox>
            </el-checkbox-group>
            <el-input v-else v-model="ans[q.id]" type="textarea" :rows="2" />
          </div>
          <div style="margin-top:16px">
            <el-button @click="step = 2">上一步</el-button>
            <el-button type="primary" :loading="busy" @click="submitAnswers">下一步：自我评价</el-button>
          </div>
        </div>

        <!-- 4 自我评价问答 -->
        <div v-else-if="step === 4">
          <div class="page-sub">回答几个问题，AI 依岗位 JD 与你的情况生成定制化自我评价（置于简历最下方）</div>
          <div v-for="q in seQuestions" :key="q.id" style="margin-bottom:20px">
            <div style="font-weight:600;margin-bottom:10px">
              {{ q.question }} <span v-if="!q.required" class="text-muted">（可留空）</span>
            </div>
            <el-radio-group v-if="q.type === 'choice'" v-model="seAns[q.id]">
              <el-radio v-for="o in q.options" :key="o" :label="o">{{ o }}</el-radio>
            </el-radio-group>
            <el-checkbox-group v-else-if="q.type === 'multi'" v-model="seAns[q.id]">
              <el-checkbox v-for="o in q.options" :key="o" :label="o">{{ o }}</el-checkbox>
            </el-checkbox-group>
            <el-input v-else v-model="seAns[q.id]" type="textarea" :rows="2" :placeholder="q.id === 'supplement' ? '可留空' : ''" />
          </div>
          <div style="margin-top:16px">
            <el-button @click="goBackFromSe">上一步</el-button>
            <el-button :loading="busy" @click="saveSeDraft">保存答案</el-button>
            <el-button type="primary" :loading="busy" @click="submitAndGenerate">生成自我评价并生成简历</el-button>
          </div>
        </div>

        <!-- 5 生成中 -->
        <div v-else>
          <el-alert type="success" :closable="false" title="已提交，正在生成定向简历（含自我评价）…" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import http, { WS_BASE } from '@/api'

const router = useRouter()
const route = useRoute()
const editId = computed(() => route.params.id)

const MODULES = [
  { key: 'summary', label: '个人简介' },
  { key: 'education', label: '教育背景' },
  { key: 'internships', label: '实习经历' },
  { key: 'work', label: '工作经历' },
  { key: 'other', label: '其他经历' },
  { key: 'skills', label: '专业技能' },
  { key: 'projects', label: '项目经历' },
  { key: 'certificates', label: '证书 / 获奖' },
  { key: 'self_evaluation', label: '自我评价' }
]

const step = ref(0)
const jdText = ref('')
const targetPosition = ref('')
const expectedSalary = ref('')
const includeSalary = ref(true)
const sections = ref(MODULES.map((m) => m.key))
const fabricateMode = ref(true)
const resumeId = ref(null)
const jdSummary = ref({})
const fabricated = ref([])
const interviewPrep = ref({})
const questions = ref([])
const ans = reactive({})
const seQuestions = ref([])
const seAns = reactive({})
const busy = ref(false)
const parsing = ref(false)
const aiStatus = ref('')
const fabricateTypes = ref(['project', 'internship'])
const fabricateJd = ref('')
const fabricateCount = ref(3)
const fabricatePhase = ref('config')
const userFeedback = ref('')

// 进度推送：WebSocket（替代 HTTP 轮询），断线自动重连（最多 3 次，重连时提示用户）
let progressWs = null
let progressStopped = false
let reconnectAttempts = 0
const MAX_RECONNECT = 3

function startProgress() {
  if (!resumeId.value) return
  // 关闭上一次可能残留的连接，避免串台
  if (progressWs) {
    try { progressWs.close() } catch (e) { /* 忽略 */ }
    progressWs = null
  }
  progressStopped = false
  reconnectAttempts = 0
  connectProgress()
}

function connectProgress() {
  const id = resumeId.value
  if (!id || progressStopped) return
  const ws = new WebSocket(`${WS_BASE}/ws/resumes/${id}/progress`)
  progressWs = ws

  ws.onopen = () => {
    reconnectAttempts = 0
  }

  ws.onmessage = (ev) => {
    if (progressWs !== ws) return
    try {
      const data = JSON.parse(ev.data)
      if (data && typeof data.progress === 'string') {
        aiStatus.value = data.progress
      }
    } catch (e) { /* 忽略非 JSON 消息 */ }
  }

  ws.onclose = () => {
    if (progressWs !== ws || progressStopped) return
    if (reconnectAttempts < MAX_RECONNECT) {
      reconnectAttempts++
      aiStatus.value = `连接已断开，正在重连（${reconnectAttempts}/${MAX_RECONNECT}）…`
      ElMessage.warning(`进度连接已断开，正在重连（${reconnectAttempts}/${MAX_RECONNECT}）`)
      setTimeout(() => {
        if (progressWs === ws && !progressStopped) connectProgress()
      }, 1000 * reconnectAttempts)
    } else {
      aiStatus.value = ''
      ElMessage.error('进度连接失败，请确认后端服务已启动')
    }
  }
}

function stopProgress() {
  progressStopped = true
  reconnectAttempts = MAX_RECONNECT + 1
  if (progressWs) {
    const ws = progressWs
    progressWs = null
    try { ws.close() } catch (e) { /* 已关闭 */ }
  }
  aiStatus.value = ''
}

function collectSeAnswers() {
  const answers = []
  let supplement = ''
  for (const q of seQuestions.value) {
    const val = Array.isArray(seAns[q.id]) ? seAns[q.id].join('、') : (seAns[q.id] || '')
    if (q.id === 'supplement') { supplement = val; continue }
    answers.push({ id: q.id, question: q.question, answer: val })
  }
  return { answers, supplement }
}

async function fetchSeQuestions() {
  const r = await http.post('/self-evaluation/questions', null, {
    params: { resume_id: resumeId.value }
  })
  seQuestions.value = r.questions || []
  seQuestions.value.forEach((q) => {
    seAns[q.id] = q.type === 'multi' ? [] : ''
  })
}

async function saveSeAnswers() {
  await http.post(`/resumes/${resumeId.value}/se-answers`, collectSeAnswers())
}

async function saveSeDraft() {
  try {
    await saveSeAnswers()
    ElMessage.success('答案已保存')
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  }
}

async function goBackFromSe() {
  try {
    await saveSeAnswers()
  } catch (e) { /* 保存失败也允许返回 */ }
  step.value = 3
}

// 继续生成：从已有任务恢复全部中断状态
async function loadResume() {
  const id = editId.value
  const r = await http.get(`/resumes/${id}`)
  resumeId.value = r.id
  jdText.value = r.jd_text || ''
  targetPosition.value = r.target_position || ''
  expectedSalary.value = r.expected_salary || ''
  includeSalary.value = r.include_salary !== false
  sections.value = (r.sections && r.sections.length) ? r.sections : MODULES.map((m) => m.key)
  jdSummary.value = r.jd_summary || {}
  fabricated.value = r.fabricated || []
  interviewPrep.value = r.interview_prep || {}
  questions.value = r.questions || []
  fabricateMode.value = (r.fabricated || []).length > 0
  const fabTypes = [...new Set((r.fabricated || []).map((x) => x.type).filter(Boolean))]
  if (fabTypes.length) fabricateTypes.value = fabTypes
  if ((r.fabricated || []).length) fabricateCount.value = (r.fabricated || []).length

  // 恢复必要问题的已填答案（多选按“、”拆分回数组）
  const answersMap = {}
  for (const a of r.answers || []) answersMap[a.id] = a.answer
  for (const q of questions.value) {
    const v = answersMap[q.id] ?? ''
    if (q.type === 'multi') {
      ans[q.id] = Array.isArray(v) ? v : (v ? String(v).split('、') : [])
    } else {
      ans[q.id] = v || ''
    }
  }

  if (r.status === 'generated') {
    router.replace(`/resume/${id}`)
    return
  }
  if (r.status === 'answered') {
    step.value = 4
    if ((r.se_questions || []).length) {
      seQuestions.value = r.se_questions
      const seMap = {}
      for (const a of r.se_answers || []) seMap[a.id] = a.answer
      seQuestions.value.forEach((q) => {
        const v = seMap[q.id] ?? ''
        seAns[q.id] = q.type === 'multi'
          ? (Array.isArray(v) ? v : (v ? String(v).split('、') : []))
          : (v || '')
      })
    } else {
      await fetchSeQuestions()
    }
    return
  }
  if (r.status === 'questioning') {
    step.value = 3
    return
  }
  if (r.status === 'parsed') {
    // 已执行过杜撰步骤：有杜撰经历回到编辑页，仅有面试准备回到设置页，否则回到解析结果
    const hasFab = (r.fabricated || []).length > 0
    const hasPrep = !!(r.interview_prep && Object.keys(r.interview_prep).length)
    step.value = hasFab || hasPrep ? 2 : 1
    fabricatePhase.value = hasFab ? 'review' : 'config'
    return
  }
  step.value = 0
}

onMounted(async () => {
  if (!editId.value) return
  busy.value = true
  try {
    await loadResume()
  } catch (e) {
    ElMessage.error(e.message || '加载任务失败')
  } finally {
    busy.value = false
  }
})

async function createTask() {
  if (!jdText.value.trim()) {
    ElMessage.warning('请先粘贴 JD')
    return
  }
  busy.value = true
  try {
    const r = await http.post('/resumes', {
      jd_text: jdText.value,
      target_position: targetPosition.value,
      expected_salary: expectedSalary.value,
      include_salary: includeSalary.value,
      sections: sections.value
    })
    resumeId.value = r.id
    step.value = 1
    parsing.value = true
    startProgress()
    // 后台解析 JD，完成后刷新结果并解锁「下一步」
    http.post(`/resumes/${r.id}/parse`).then((res) => {
      jdSummary.value = res.jd_summary || {}
      parsing.value = false
      stopProgress()
    }).catch((e) => {
      parsing.value = false
      stopProgress()
      ElMessage.error(e.message || 'JD 解析失败')
    })
  } catch (e) {
    ElMessage.error(e.message || '创建任务失败')
  } finally {
    busy.value = false
  }
}

async function genQuestions() {
  const r = await http.post(`/resumes/${resumeId.value}/questions`)
  questions.value = r.questions || []
  questions.value.forEach((q) => {
    ans[q.id] = q.type === 'multi' ? [] : ''
  })
  step.value = 3
}

async function generateFabricated() {
  if (fabricateTypes.value.length === 0) {
    ElMessage.warning('请至少选择一种杜撰经历类型')
    return
  }
  busy.value = true
  startProgress()
  try {
    const r = await http.post(`/resumes/${resumeId.value}/fabricate`, {
      fabricate: true,
      types: fabricateTypes.value,
      count: fabricateCount.value,
      extra_jd: fabricateJd.value
    })
    fabricated.value = r.fabricated || []
    userFeedback.value = ''
    fabricatePhase.value = 'review'
  } finally {
    stopProgress()
    busy.value = false
  }
}

async function reviseFabricated() {
  busy.value = true
  startProgress()
  try {
    const r = await http.post(`/resumes/${resumeId.value}/fabricate/revise`, {
      experiences: fabricated.value,
      feedback: userFeedback.value
    })
    fabricated.value = r.fabricated || []
    userFeedback.value = ''
    ElMessage.success('已按意见修改')
  } finally {
    stopProgress()
    busy.value = false
  }
}

async function confirmAndContinue() {
  busy.value = true
  startProgress()
  try {
    await http.post(`/resumes/${resumeId.value}/fabricate/confirm`)
    await genQuestions()
  } finally {
    stopProgress()
    busy.value = false
  }
}

function removeFabricated(i) {
  fabricated.value.splice(i, 1)
}

async function submitAnswers() {
  busy.value = true
  startProgress()
  try {
    const answers = questions.value.map((q) => ({
      id: q.id,
      question: q.question,
      answer: Array.isArray(ans[q.id]) ? ans[q.id].join('、') : (ans[q.id] || '')
    }))
    await http.post(`/resumes/${resumeId.value}/answers`, { answers })
    await fetchSeQuestions()
    step.value = 4
  } finally {
    stopProgress()
    busy.value = false
  }
}

async function submitAndGenerate() {
  busy.value = true
  startProgress()
  try {
    const answers = []
    let supplement = ''
    for (const q of seQuestions.value) {
      const val = Array.isArray(seAns[q.id]) ? seAns[q.id].join('、') : (seAns[q.id] || '')
      if (q.id === 'supplement') {
        supplement = val
        continue
      }
      answers.push({ id: q.id, question: q.question, answer: val })
    }
    await http.post('/self-evaluation/generate', {
      resume_id: resumeId.value,
      answers,
      supplement
    })
    step.value = 5
    await http.post(`/resumes/${resumeId.value}/generate`)
    ElMessage.success('简历已生成')
    router.push(`/resume/${resumeId.value}`)
  } finally {
    stopProgress()
    busy.value = false
  }
}
</script>