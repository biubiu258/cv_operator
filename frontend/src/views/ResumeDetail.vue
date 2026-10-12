<template>
  <div>
    <div class="page-title">简历详情</div>
    <div class="page-sub">任务 #{{ resume?.id }} · 目标岗位：{{ resume?.target_position || resume?.jd_summary?.position || '未识别' }}</div>

    <div class="card-panel" style="margin-bottom:16px">
      <div class="card-body">
        <el-space wrap>
          <el-button type="primary" :disabled="!resume?.output_path" @click="download('docx')">
            <el-icon><Download /></el-icon> 下载 Word
          </el-button>
          <el-button type="success" :disabled="!resume?.output_path" :loading="converting" @click="toPdf">
            <el-icon><Download /></el-icon> 下载 PDF
          </el-button>
        </el-space>
      </div>
    </div>

    <el-row :gutter="16">
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
          <div class="card-head">个人简介</div>
          <div class="card-body" style="white-space:pre-wrap">{{ resume?.personal_summary || '尚未生成' }}</div>
        </div>
      </el-col>
    </el-row>

    <div class="card-panel" style="margin-top:16px">
      <div class="card-head">自我评价</div>
      <div class="card-body" style="white-space:pre-wrap">{{ resume?.self_evaluation || '尚未生成' }}</div>
    </div>

    <div class="card-panel" style="margin-top:16px" v-if="(resume?.fabricated || []).length">
      <div class="card-head">杜撰经历（已并入简历，面试需能自圆其说）</div>
      <div class="card-body">
        <div v-for="(e, i) in resume.fabricated" :key="i" style="margin-bottom:14px">
          <b>{{ e.type === 'internship' ? '实习' : '项目' }} · {{ e.title }}</b>
          <span class="text-muted" style="margin-left:8px">{{ e.start_date }} - {{ e.end_date }}</span>
          <div v-if="e.tech_stack" style="margin-top:4px">技术栈：{{ e.tech_stack }}</div>
          <div v-if="e.description" style="margin-top:4px">{{ e.description }}</div>
          <div v-if="e.result" style="margin-top:4px"><b>成果：</b>{{ e.result }}</div>
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
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import http, { downloadUrl } from '@/api'

const route = useRoute()
const resume = ref(null)
const converting = ref(false)

onMounted(async () => {
  resume.value = await http.get(`/resumes/${route.params.id}`)
})

function download(format) {
  window.open(downloadUrl(route.params.id, format), '_blank')
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
</script>