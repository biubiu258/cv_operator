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

        <!-- 0 输入 JD + 意向岗位(可选) + 模块选择 -->
        <div v-if="step === 0">
          <div style="font-weight:600;margin-bottom:8px">岗位 JD</div>
          <el-input v-model="jdText" type="textarea" :rows="9" placeholder="这里粘贴岗位 JD 全文…" />

          <div style="font-weight:600;margin:20px 0 8px">意向岗位（可选，不填则复用基本信息中的目标岗位）</div>
          <el-input v-model="targetPosition" placeholder="如：AI Agent 开发工程师" style="max-width:360px" />

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
            <el-button type="primary" @click="step = 2">下一步：经历杜撰</el-button>
          </div>
        </div>

        <!-- 2 经历杜撰（可选） -->
        <div v-else-if="step === 2">
          <div class="page-sub" style="margin-bottom:16px">
            该步骤可选：是否由 AI 生成与 JD 匹配的经历，填充简历的项目/实习空白？
          </div>
          <el-radio-group v-model="fabricateMode">
            <el-radio :label="true">杜撰经历（AI 生成，便于匹配 JD）</el-radio>
            <el-radio :label="false">只使用我的真实经历</el-radio>
          </el-radio-group>
          <div class="text-muted" style="font-size:12px;margin-top:8px">
            选择「杜撰」会生成 2~3 段经历，并入简历「项目经历 / 实习经历」；同时生成面试准备包（重点知识点 + 高频问题）。
          </div>
          <div style="margin-top:20px">
            <el-button @click="step = 1">上一步</el-button>
            <el-button type="primary" :loading="busy" @click="doFabricate">生成并继续</el-button>
          </div>
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
            <el-button @click="step = 3">上一步</el-button>
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
import { computed, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import http from '@/api'

const router = useRouter()
const route = useRoute()
const editId = computed(() => route.params.id)

const MODULES = [
  { key: 'summary', label: '个人简介' },
  { key: 'education', label: '教育背景' },
  { key: 'internships', label: '实习经历' },
  { key: 'skills', label: '专业技能' },
  { key: 'projects', label: '项目经历' },
  { key: 'certificates', label: '证书 / 获奖' },
  { key: 'self_evaluation', label: '自我评价' }
]

const step = ref(0)
const jdText = ref('')
const targetPosition = ref('')
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
      sections: sections.value
    })
    resumeId.value = r.id
    jdSummary.value = await http.post(`/resumes/${r.id}/parse`)
    step.value = 1
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

async function doFabricate() {
  busy.value = true
  try {
    const r = await http.post(`/resumes/${resumeId.value}/fabricate`, {
      fabricate: fabricateMode.value
    })
    fabricated.value = r.fabricated || []
    interviewPrep.value = r.interview_prep || {}
    await genQuestions()
  } finally {
    busy.value = false
  }
}

async function submitAnswers() {
  busy.value = true
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
    busy.value = false
  }
}

async function submitAndGenerate() {
  busy.value = true
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
    busy.value = false
  }
}
</script>