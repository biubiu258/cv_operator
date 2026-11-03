<template>
  <div>
    <div class="page-title">{{ editId ? '继续生成简历' : '新建定向简历' }}</div>
    <div class="page-sub">粘贴岗位 JD，AI 解析并生成必要问题，随后输出含定制自我评价的定向简历</div>

    <div class="card-panel">
      <div class="card-body">
        <el-steps :active="step" finish-status="success" align-center style="margin-bottom:28px">
          <el-step title="填写信息" />
          <el-step title="解析 JD" />
          <el-step title="经历优化(可选)" />
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

          <div style="font-weight:600;margin:20px 0 8px">简历篇幅</div>
          <el-radio-group v-model="length">
            <el-radio label="fresh">应届（目标一页）</el-radio>
            <el-radio label="junior">1-5年（2页以内）</el-radio>
            <el-radio label="senior">5年及以上（3页以内）</el-radio>
            <el-radio label="custom">自定义篇幅</el-radio>
          </el-radio-group>
          <div v-if="length === 'custom'" style="margin-top:10px;display:flex;align-items:center;gap:8px">
            <span class="text-muted" style="font-size:12px">目标页数</span>
            <el-input-number v-model="customPages" :min="1" :max="10" />
          </div>

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
            <el-button type="primary" :disabled="parsing" :loading="parsing" @click="step = 2">下一步：经历优化</el-button>
          </div>
        </div>

        <!-- 2 经历优化（可选）：杜撰 / 按 JD 润色真实经历 / 原文使用 -->
        <div v-else-if="step === 2">
          <template v-if="fabricatePhase === 'config'">
            <div class="page-sub" style="margin-bottom:16px">
              该步骤可选：AI 可以帮你生成与 JD 匹配的经历填充空白，也可以只润色你已有的真实经历。
            </div>
            <el-radio-group v-model="expMode">
              <el-radio label="fabricate">杜撰经历（AI 生成新经历，时间线自动避开空档）</el-radio>
              <el-radio label="polish">润色我的真实经历（按 JD 优化表述，不改变事实）</el-radio>
              <el-radio label="real">直接使用真实经历原文</el-radio>
            </el-radio-group>

            <template v-if="expMode === 'fabricate'">
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

              <div style="font-weight:600;margin:20px 0 8px">生成数量（当前篇幅最多 {{ fabMax }} 段）</div>
              <el-input-number v-model="fabricateCount" :min="1" :max="fabMax" />
              <div class="text-muted" style="font-size:12px;margin-top:6px">
                系统会根据你的入学/毕业时间与真实经历自动分配每段经历的起止月份，保证就业链连续、无空档无重叠。
              </div>
            </template>

            <template v-else-if="expMode === 'polish'">
              <el-alert type="info" :closable="false" style="margin:16px 0">
                <template #title>
                  润色只优化「核心工作 / 量化成果」的表达（STAR、JD 关键词、合理量化），
                  公司、岗位、时间、技术栈等事实保持不变，也不会新增或删除经历。
                </template>
              </el-alert>
              <div class="text-muted" style="font-size:13px">
                档案中当前有
                <b>{{ (profile.internships || []).length }}</b> 段实习经历、
                <b>{{ (profile.projects || []).length }}</b> 段项目经历可润色。
              </div>
              <el-button v-if="!realCount" type="primary" disabled style="margin-top:16px">暂无可润色的经历</el-button>
            </template>

            <template v-else>
              <el-alert type="info" :closable="false" style="margin:16px 0">
                <template #title>简历将直接使用档案中的实习与项目经历原文，不做 AI 加工。</template>
              </el-alert>
            </template>

            <div style="margin-top:20px">
              <el-button @click="step = 1">上一步</el-button>
              <el-button v-if="expMode === 'fabricate'" type="primary" :loading="busy" @click="generateFabricated">生成经历</el-button>
              <el-button v-else-if="expMode === 'polish' && realCount" type="primary" :loading="busy" @click="startPolish">开始 AI 润色</el-button>
              <el-button v-else type="primary" :loading="busy" @click="confirmAndContinue">继续（使用真实经历原文）</el-button>
            </div>
          </template>

          <template v-else>
            <div class="page-sub" style="margin-bottom:8px">
              <template v-if="expMode === 'polish'">
                已润色 {{ editingExperiences.length }} 段真实经历，事实字段已锁定，可调整「核心工作 / 量化成果」，或让 AI 按意见继续修改。
              </template>
              <template v-else>
                已生成 {{ editingExperiences.length }} 段经历，可逐项修改，或在下方对 AI 提出整体修改意见。
              </template>
            </div>

            <el-alert
              v-for="(w, wi) in timelineWarnings" :key="wi"
              type="warning" :closable="false" show-icon style="margin-bottom:8px"
              :title="w" />

            <div v-for="(e, i) in editingExperiences" :key="i" style="border:1px solid #e6e8eb;border-radius:8px;padding:14px;margin-bottom:14px">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
                <b>第 {{ i + 1 }} 段<span v-if="expMode === 'polish'" class="text-muted" style="font-size:12px;font-weight:400">（真实经历）</span></b>
                <div>
                  <el-button size="small" text :disabled="i === 0" @click="moveUp(i)">↑ 上移</el-button>
                  <el-button size="small" text :disabled="i === editingExperiences.length - 1" @click="moveDown(i)">↓ 下移</el-button>
                  <el-button v-if="expMode !== 'polish'" size="small" type="danger" text @click="removeExperience(i)">删除</el-button>
                </div>
              </div>
              <el-row :gutter="10">
                <el-col :span="8">
                  <div class="text-muted" style="font-size:12px;margin-bottom:4px">类型</div>
                  <el-select v-model="e.type" style="width:100%" :disabled="expMode === 'polish'">
                    <el-option value="project" label="项目经历" />
                    <el-option value="internship" label="实习经历" />
                    <el-option value="work" label="全职经历" />
                    <el-option value="other" label="其他经历" />
                  </el-select>
                </el-col>
                <el-col :span="8">
                  <div class="text-muted" style="font-size:12px;margin-bottom:4px">{{ e.type === 'project' ? '项目名' : '公司名' }}</div>
                  <el-input v-model="e.title" :placeholder="e.type === 'project' ? '项目名' : '公司名'" :disabled="expMode === 'polish'" />
                </el-col>
                <el-col :span="8">
                  <div class="text-muted" style="font-size:12px;margin-bottom:4px">{{ e.type === 'project' ? '角色' : '职位' }}</div>
                  <el-input v-model="e.role" :placeholder="e.type === 'project' ? '角色' : '职位'" :disabled="expMode === 'polish'" />
                </el-col>
              </el-row>
              <el-row :gutter="10" style="margin-top:10px">
                <el-col :span="8">
                  <div class="text-muted" style="font-size:12px;margin-bottom:4px">开始时间</div>
                  <el-input v-model="e.start_date" placeholder="YYYY.MM" :disabled="expMode === 'polish'" />
                </el-col>
                <el-col :span="8">
                  <div class="text-muted" style="font-size:12px;margin-bottom:4px">结束时间</div>
                  <el-input v-model="e.end_date" placeholder="YYYY.MM 或 至今" :disabled="expMode === 'polish'" />
                </el-col>
                <el-col :span="8">
                  <div class="text-muted" style="font-size:12px;margin-bottom:4px">技术栈</div>
                  <el-input v-model="e.tech_stack" placeholder="如 Python、Vue" :disabled="expMode === 'polish'" />
                </el-col>
              </el-row>
              <div class="text-muted" style="font-size:12px;margin:10px 0 4px">核心工作</div>
              <el-input v-model="e.description" type="textarea" :rows="2" />
              <div class="text-muted" style="font-size:12px;margin:10px 0 4px">量化成果</div>
              <el-input v-model="e.result" type="textarea" :rows="2" />
            </div>

            <div style="font-weight:600;margin:8px 0 6px">给 AI 的修改意见（可选）</div>
            <el-input v-model="userFeedback" type="textarea" :rows="3"
              :placeholder="expMode === 'polish'
                ? '例如：第二段再突出与大模型相关的工作；成果量化再具体一些…'
                : '例如：第一段成果请量化更具体；整体语气更正式…'" />

            <div style="margin-top:16px">
              <el-button @click="fabricatePhase = 'config'">返回设置</el-button>
              <el-button :loading="busy" @click="reviseCurrent">
                让 AI 按意见{{ expMode === 'polish' ? '润色' : '修改' }}
              </el-button>
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
const expMode = ref('fabricate') // fabricate 杜撰 | polish 润色真实经历 | real 原文使用
const resumeId = ref(null)
const jdSummary = ref({})
const fabricated = ref([])
const polished = ref([])
const timelineWarnings = ref([])
const profile = ref({})
const fabMax = ref(5)
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
const length = ref('fresh')
const customPages = ref(2)

// 复核阶段当前编辑的经历列表：润色模式用润色稿，其余用杜撰稿
const editingExperiences = computed(() =>
  expMode.value === 'polish' ? polished.value : fabricated.value)
const realCount = computed(() =>
  (profile.value.internships?.length || 0) + (profile.value.projects?.length || 0))

async function loadBudget() {
  if (!resumeId.value) return
  try {
    const rc = await http.get(`/resumes/${resumeId.value}/render-context`)
    fabMax.value = rc.budget?.fabricate_max || 5
  } catch (e) { /* 预算获取失败保留默认值 */ }
}

async function loadProfile() {
  try {
    profile.value = await http.get('/users/active')
  } catch (e) { profile.value = {} }
}

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
  length.value = r.length || 'fresh'
  customPages.value = r.custom_pages || 2
  sections.value = (r.sections && r.sections.length) ? r.sections : MODULES.map((m) => m.key)
  jdSummary.value = r.jd_summary || {}
  fabricated.value = r.fabricated || []
  polished.value = r.polished_experiences || []
  timelineWarnings.value = r.timeline_warnings || []
  interviewPrep.value = r.interview_prep || {}
  questions.value = r.questions || []
  if (fabricated.value.length) {
    expMode.value = 'fabricate'
  } else if (polished.value.length) {
    expMode.value = 'polish'
  }
  const fabTypes = [...new Set((r.fabricated || []).map((x) => x.type).filter(Boolean))]
  if (fabTypes.length) fabricateTypes.value = fabTypes
  if ((r.fabricated || []).length) fabricateCount.value = (r.fabricated || []).length
  loadBudget()

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
    // 已执行过经历步骤：有杜撰/润色经历回到编辑页，仅有面试准备回到设置页，否则回到解析结果
    const hasFab = (r.fabricated || []).length > 0
    const hasPol = (r.polished_experiences || []).length > 0
    const hasPrep = !!(r.interview_prep && Object.keys(r.interview_prep).length)
    step.value = hasFab || hasPol || hasPrep ? 2 : 1
    fabricatePhase.value = (hasFab || hasPol) ? 'review' : 'config'
    return
  }
  step.value = 0
}

onMounted(async () => {
  await loadProfile()
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
      sections: sections.value,
      length: length.value,
      custom_pages: length.value === 'custom' ? customPages.value : null
    })
    resumeId.value = r.id
    step.value = 1
    parsing.value = true
    startProgress()
    // 后台解析 JD，完成后刷新结果并解锁「下一步」
    http.post(`/resumes/${r.id}/parse`).then((res) => {
      jdSummary.value = res.jd_summary || {}
      timelineWarnings.value = res.timeline_warnings || []
      parsing.value = false
      stopProgress()
      loadBudget()
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

function applyResumeState(r) {
  fabricated.value = r.fabricated || []
  polished.value = r.polished_experiences || []
  timelineWarnings.value = r.timeline_warnings || []
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
    applyResumeState(r)
    userFeedback.value = ''
    fabricatePhase.value = 'review'
  } catch (e) {
    ElMessage.error(e.message || '生成失败')
  } finally {
    stopProgress()
    busy.value = false
  }
}

async function startPolish() {
  busy.value = true
  startProgress()
  try {
    const r = await http.post(`/resumes/${resumeId.value}/polish`)
    applyResumeState(r)
    userFeedback.value = ''
    fabricatePhase.value = 'review'
  } catch (e) {
    ElMessage.error(e.message || '润色失败')
  } finally {
    stopProgress()
    busy.value = false
  }
}

// 复核页「让 AI 按意见修改」：按当前模式分别调杜撰修改 / 润色修改
async function reviseCurrent() {
  if (!editingExperiences.value.length) return
  busy.value = true
  startProgress()
  try {
    const url = expMode.value === 'polish' ? 'polish/revise' : 'fabricate/revise'
    const r = await http.post(`/resumes/${resumeId.value}/${url}`, {
      experiences: editingExperiences.value,
      feedback: userFeedback.value
    })
    applyResumeState(r)
    userFeedback.value = ''
    ElMessage.success(expMode.value === 'polish' ? '已按意见润色' : '已按意见修改')
  } catch (e) {
    ElMessage.error(e.message || '修改失败')
  } finally {
    stopProgress()
    busy.value = false
  }
}

async function confirmAndContinue() {
  busy.value = true
  startProgress()
  try {
    if (expMode.value === 'polish') {
      // 持久化用户对润色稿的手动修改（仅表述字段）
      const r = await http.post(`/resumes/${resumeId.value}/polish/save`, {
        experiences: polished.value
      })
      applyResumeState(r)
    } else if (expMode.value === 'fabricate') {
      // 持久化用户对杜撰蓝本的手动修改（旧版此处会丢失手改内容）
      const r = await http.post(`/resumes/${resumeId.value}/fabricate/save`, {
        experiences: fabricated.value
      })
      applyResumeState(r)
    } else if (expMode.value === 'real') {
      // 原文模式：清空任何杜撰/润色产物（修复切换模式后旧经历残留问题）
      const r = await http.post(`/resumes/${resumeId.value}/fabricate`, { fabricate: false })
      applyResumeState(r)
    }
    await http.post(`/resumes/${resumeId.value}/fabricate/confirm`)
    await genQuestions()
  } catch (e) {
    ElMessage.error(e.message || '操作失败')
  } finally {
    stopProgress()
    busy.value = false
  }
}

function removeExperience(i) {
  editingExperiences.value.splice(i, 1)
}

// 手动排序：上移/下移经历条目
function moveExperience(from, to) {
  const list = editingExperiences.value
  if (to < 0 || to >= list.length) return
  const [item] = list.splice(from, 1)
  list.splice(to, 0, item)
}
function moveUp(i) { moveExperience(i, i - 1) }
function moveDown(i) { moveExperience(i, i + 1) }

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