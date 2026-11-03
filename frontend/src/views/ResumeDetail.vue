<template>
  <div>
    <div class="page-title">简历详情</div>
    <div class="page-sub">任务 #{{ resume?.id }} · 目标岗位：{{ resume?.target_position || resume?.jd_summary?.position || '未识别' }}</div>

    <el-alert
      v-for="(w, i) in (resume?.timeline_warnings || [])" :key="i"
      type="warning" show-icon :closable="false" style="margin-bottom:10px" :title="w" />

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
      <div class="card-head" style="display:flex;justify-content:space-between;align-items:center">
        <span>杜撰经历（已并入简历，面试需能自圆其说）</span>
        <el-button size="small" type="primary" :loading="saving" @click="saveFabricatedOrder">保存排序</el-button>
      </div>
      <div class="card-body">
        <div v-for="(e, i) in resume.fabricated" :key="i" style="margin-bottom:14px;border:1px solid #e6e8eb;border-radius:8px;padding:12px">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
            <b>{{ TYPE_LABELS[e.type] || '经历' }} · {{ e.title }}</b>
            <div>
              <el-button size="small" text :disabled="i === 0" @click="moveArr(resume.fabricated, i, i - 1)">↑ 上移</el-button>
              <el-button size="small" text :disabled="i === resume.fabricated.length - 1" @click="moveArr(resume.fabricated, i, i + 1)">↓ 下移</el-button>
            </div>
          </div>
          <span v-if="e.role" class="text-muted" style="margin-left:6px">{{ e.role }}</span>
          <span class="text-muted" style="margin-left:8px">{{ e.start_date }} - {{ e.end_date }}</span>
          <div v-if="e.tech_stack" style="margin-top:4px">技术栈：{{ e.tech_stack }}</div>
          <div v-if="e.description" style="margin-top:4px"><RichText :text="e.description" /></div>
          <div v-if="e.result" style="margin-top:4px"><b>成果：</b><RichText :text="e.result" /></div>
        </div>
        <div class="text-muted" style="font-size:12px">篇幅预算：每种经历类型最多渲染 {{ expClip }} 条，超出部分将在最终排版时截断</div>
      </div>
    </div>

    <div class="card-panel" style="margin-top:16px" v-if="(resume?.polished_experiences || []).length">
      <div class="card-head" style="display:flex;justify-content:space-between;align-items:center">
        <span>真实经历（已按 JD 润色，公司/岗位/时间保持原样）</span>
        <el-button size="small" type="primary" :loading="saving" @click="savePolishedOrder">保存排序</el-button>
      </div>
      <div class="card-body">
        <div v-for="(e, i) in resume.polished_experiences" :key="i" style="margin-bottom:14px;border:1px solid #e6e8eb;border-radius:8px;padding:12px">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
            <b>{{ TYPE_LABELS[e.type] || '经历' }} · {{ e.title }}</b>
            <div>
              <el-button size="small" text :disabled="i === 0" @click="moveArr(resume.polished_experiences, i, i - 1)">↑ 上移</el-button>
              <el-button size="small" text :disabled="i === resume.polished_experiences.length - 1" @click="moveArr(resume.polished_experiences, i, i + 1)">↓ 下移</el-button>
            </div>
          </div>
          <span v-if="e.role" class="text-muted" style="margin-left:6px">{{ e.role }}</span>
          <span class="text-muted" style="margin-left:8px">{{ e.start_date }} - {{ e.end_date }}</span>
          <div v-if="e.tech_stack" style="margin-top:4px">技术栈：{{ e.tech_stack }}</div>
          <div v-if="e.description" style="margin-top:4px"><RichText :text="e.description" /></div>
          <div v-if="e.result" style="margin-top:4px"><b>成果：</b><RichText :text="e.result" /></div>
        </div>
        <div class="text-muted" style="font-size:12px">篇幅预算：每种经历类型最多渲染 {{ expClip }} 条，超出部分将在最终排版时截断；类型合并后会独立排序</div>
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

    <!-- ATS 关键词定向评分 -->
    <div class="card-panel" style="margin-top:16px">
      <div class="card-head" style="display:flex;justify-content:space-between;align-items:center">
        <span>ATS 匹配度评估</span>
        <el-button size="small" type="primary" :loading="atsLoading" @click="runAtsScore">
          <el-icon><DataAnalysis /></el-icon> {{ atsScore ? '重新评估' : '开始评估' }}
        </el-button>
      </div>
      <div class="card-body" v-if="!resume?.jd_summary?.tech?.length && !resume?.jd_summary?.domain?.length">
        <span class="text-muted">请先解析岗位 JD 后再评估 ATS 匹配度</span>
      </div>
      <div class="card-body" v-else-if="!atsScore">
        <span class="text-muted">点击右上角「开始评估」，系统会扫描你的简历并与 JD 关键词做匹配度计算（毫秒级）</span>
      </div>
      <div class="card-body" v-else>
        <el-row :gutter="16">
          <!-- 命中率圆环 -->
          <el-col :span="8">
            <div style="text-align:center;padding:12px">
              <el-progress type="circle"
                :percentage="Math.round((atsScore.hit_rate_weighted || atsScore.hit_rate) * 100)"
                :width="120" :stroke-width="12"
                :color="atsScore.hit_rate_weighted >= 0.7 ? '#67C23A' : atsScore.hit_rate_weighted >= 0.4 ? '#E6A23C' : '#F56C6C'" />
              <div style="margin-top:10px">
                <b>加权命中率</b>
                <div class="text-muted" style="font-size:12px">
                  {{ atsScore.hit_count }} / {{ atsScore.total_count }} 个 JD 关键词
                </div>
              </div>
            </div>
          </el-col>

          <!-- 缺失关键词 -->
          <el-col :span="16">
            <div style="font-weight:600;margin-bottom:8px">缺失关键词
              <span class="text-muted" style="font-size:12px;font-weight:400">（按重要性排序）</span>
            </div>
            <div v-if="!atsScore.missing?.length" class="text-muted" style="font-size:13px">
              🎉 完美命中！你的简历覆盖了 JD 中全部关键词
            </div>
            <el-tag v-for="m in atsScore.missing" :key="m.keyword"
              :type="atsImportanceTag(m.importance)"
              effect="plain"
              style="margin:3px 6px 3px 0;cursor:pointer"
              :title="'建议加入板块：' + atsSectionLabel(m.suggest_in)">
              {{ m.keyword }}
              <span class="text-muted" style="font-size:11px;margin-left:3px">
                → {{ atsSectionLabel(m.suggest_in) }}
              </span>
            </el-tag>
          </el-col>
        </el-row>

        <!-- 关键词密度 -->
        <div v-if="Object.keys(atsScore.density || {}).length" style="margin-top:14px">
          <div style="font-weight:600;margin-bottom:8px">各板块关键词密度</div>
          <div v-for="(val, key) in atsScore.density" :key="key"
            style="display:flex;align-items:center;margin-bottom:4px">
            <span style="width:110px;font-size:13px">{{ atsSectionLabel(key) }}</span>
            <el-progress :percentage="Math.min(Math.round(val * 50), 100)"
              :show-text="false" :stroke-width="14"
              style="flex:1;margin:0 10px"
              :color="val >= 0.1 ? '#67C23A' : val >= 0.04 ? '#E6A23C' : '#F56C6C'" />
            <span class="text-muted" style="font-size:12px;width:50px;text-align:right">{{ val.toFixed(3) }}</span>
          </div>
        </div>

        <!-- 命中关键词列表（可折叠） -->
        <el-collapsible v-if="atsScore.hit_details?.length" style="margin-top:12px">
          <template #trigger>
            <span style="cursor:pointer;font-size:13px;color:#409EFF">
              已命中 {{ atsScore.hit_details.length }} 个关键词（点击展开）
            </span>
          </template>
          <div style="margin-top:6px">
            <el-tag v-for="h in atsScore.hit_details" :key="h.keyword + h.section"
              size="small" style="margin:2px 4px 2px 0">
              {{ h.keyword }}
              <span class="text-muted" style="font-size:11px;margin-left:2px">
                @{{ atsSectionLabel(h.section) }}
              </span>
            </el-tag>
          </div>
        </el-collapsible>
      </div>
    </div>

    <!-- 求职信 -->
    <div class="card-panel" style="margin-top:16px">
      <div class="card-head" style="display:flex;justify-content:space-between;align-items:center">
        <span>求职信</span>
        <el-space v-if="resume?.cover_letter">
          <el-button size="small" @click="downloadCoverLetter">
            <el-icon><Download /></el-icon> 下载 Word
          </el-button>
        </el-space>
      </div>
      <div class="card-body">
        <div style="display:flex;gap:12px;align-items:center;margin-bottom:12px;flex-wrap:wrap">
          <span class="text-muted">风格：</span>
          <el-radio-group v-model="clTone" size="small">
            <el-radio-button value="professional">专业严谨</el-radio-button>
            <el-radio-button value="enthusiastic">热情积极</el-radio-button>
            <el-radio-button value="concise">简洁有力</el-radio-button>
          </el-radio-group>
          <span class="text-muted" style="font-size:12px">
            生成后字数：{{ clWordCount }} 字
          </span>
        </div>

        <template v-if="!clEditing">
          <el-space style="margin-bottom:10px">
            <el-button type="primary" :loading="clGenerating" @click="generateCoverLetter">
              {{ resume?.cover_letter ? '换一版' : '生成求职信' }}
            </el-button>
            <el-button v-if="resume?.cover_letter" @click="startClEdit">
              <el-icon><Edit /></el-icon> 手动编辑
            </el-button>
          </el-space>
          <div v-if="resume?.cover_letter"
            style="border:1px solid #ebeef5;border-radius:6px;padding:14px 16px;white-space:pre-wrap;line-height:1.8">
            {{ resume.cover_letter }}
          </div>
          <span v-else class="text-muted">尚未生成，点击「生成求职信」基于当前 JD + 简历正文自动撰写</span>
        </template>

        <template v-else>
          <el-input v-model="clDraft" type="textarea" :rows="12" resize="none" />
          <div style="margin-top:10px">
            <el-button type="primary" size="small" :loading="saving" @click="saveClEdit">保存编辑</el-button>
            <el-button size="small" @click="cancelClEdit">取消</el-button>
            <span class="text-muted" style="font-size:12px;margin-left:8px">
              修改内容会保存到数据库并同步用于 docx 下载
            </span>
          </div>
        </template>
      </div>
    </div>

    <!-- 反伪造检测 -->
    <div class="card-panel" style="margin-top:16px">
      <div class="card-head" style="display:flex;justify-content:space-between;align-items:center">
        <span>反伪造检测（CareerScape 友好度）</span>
        <el-space>
          <el-button size="small" :loading="adLoading" @click="runAntiDetect">
            <el-icon><Warning /></el-icon> 开始检测
          </el-button>
          <el-button v-if="adReport && adReport.score >= 0.4" size="small" type="warning"
                     :loading="adOptimizing" @click="runAntiDetectOptimize">
            一键反伪造优化
          </el-button>
        </el-space>
      </div>
      <div class="card-body" v-if="!adReport">
        <span class="text-muted">点击「开始检测」，系统会扫描你的简历里是否有 CareerScape 等 AI 检测器容易识别的典型模式（模板化表达 / 精确数字堆砌 / STAR 僵化 / 时间线完美对齐）</span>
      </div>
      <div class="card-body" v-else>
        <el-alert :title="adReport.summary"
          :type="adReport.verdict === 'danger' ? 'error' : adReport.verdict === 'watch' ? 'warning' : 'success'"
          show-icon :closable="false" style="margin-bottom:12px" />

        <el-row :gutter="16">
          <el-col :span="8">
            <div style="text-align:center;padding:12px">
              <el-progress type="circle"
                :percentage="Math.round(adReport.score * 100)"
                :width="100" :stroke-width="10"
                :color="adReport.score >= 0.7 ? '#F56C6C' : adReport.score >= 0.4 ? '#E6A23C' : '#67C23A'" />
              <div style="margin-top:8px;font-size:13px">
                AI 痕迹风险分<br>
                <span class="text-muted" style="font-size:11px">越高越可能被 HR 检测工具命中</span>
              </div>
            </div>
          </el-col>

          <el-col :span="16">
            <div v-for="(rule, key) in adReport.rules" :key="key" style="margin-bottom:8px">
              <div style="display:flex;justify-content:space-between;align-items:center;font-size:13px">
                <span>
                  {{ rule.description }}
                  <el-tag v-if="rule.danger >= 0.3" size="small"
                    :type="rule.danger >= 0.7 ? 'danger' : 'warning'" style="margin-left:4px">
                    ⚠️ {{ (rule.danger * 100).toFixed(0) }}%
                  </el-tag>
                  <span v-else class="text-muted" style="font-size:11px">无明显风险</span>
                </span>
                <el-progress :percentage="Math.round(rule.danger * 100)"
                  :show-text="false" :stroke-width="8"
                  :color="rule.danger >= 0.7 ? '#F56C6C' : rule.danger >= 0.3 ? '#E6A23C' : '#67C23A'"
                  style="width:100px" />
              </div>
              <div v-if="rule.hits?.length && rule.danger >= 0.3"
                style="font-size:12px;color:#909399;margin-top:3px;padding-left:12px">
                <div v-for="(h, hi) in rule.hits.slice(0, 3)" :key="hi">
                  · {{ h.phrase || `#${h.index}` }}
                  <span v-if="h.context" style="color:#c0c4cc">…{{ h.context }}…</span>
                </div>
                <div v-if="rule.hits.length > 3" class="text-muted">还有 {{ rule.hits.length - 3 }} 处</div>
              </div>
            </div>
          </el-col>
        </el-row>

        <!-- 优化前后对比 -->
        <div v-if="reportBeforeAfter" style="margin-top:12px;padding-top:12px;border-top:1px solid #ebeef5">
          <div style="font-size:13px;font-weight:600;margin-bottom:6px">优化效果：{{ reportBeforeAfter.before.score.toFixed(3) }} → {{ reportBeforeAfter.after.score.toFixed(3) }}</div>
          <el-tag :type="reportBeforeAfter.after.score < reportBeforeAfter.before.score ? 'success' : 'info'" size="small">
            {{ reportBeforeAfter.after.score < reportBeforeAfter.before.score ? '✅ 分数下降' : 'ℹ️ 分数未明显变化' }}
          </el-tag>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import http, { downloadUrl, API_BASE } from '@/api'
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

const TYPE_LABELS = {
  project: '项目经历',
  internship: '实习经历',
  work: '全职经历',
  other: '其他经历'
}

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
const expClip = ref(0) // 篇幅预算：每种经历类型最多渲染条数（0 = 不限制）

// --- ATS ---
const atsLoading = ref(false)
const atsScore = ref(null)

// --- 求职信 ---
const clTone = ref('professional')
const clGenerating = ref(false)
const clEditing = ref(false)
const clDraft = ref('')
const clWordCount = computed(() =>
  (resume.value?.cover_letter || '').replace(/[\s\n\t]/g, '').length)

// --- 反伪造检测 ---
const adLoading = ref(false)
const adOptimizing = ref(false)
const adReport = ref(null)
const reportBeforeAfter = computed(() =>
  resume.value?.anti_detect_result?.before && resume.value?.anti_detect_result?.after
    ? resume.value.anti_detect_result : null
)

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
  clTone.value = resume.value.cover_letter_tone || 'professional'
  templateList.value = await http.get('/resumes/templates')
  // 加载篇幅预算，用于提示每种经历类型最多渲染条数
  try {
    const rc = await http.get(`/resumes/${route.params.id}/render-context`)
    expClip.value = rc.budget?.max_experiences || 0
  } catch (e) { /* 预算获取失败不阻断页面 */ }
})

// 数组内移动（原地修改，触发 Vue 响应式）
function moveArr(arr, from, to) {
  if (!arr) return
  if (to < 0 || to >= arr.length) return
  const [item] = arr.splice(from, 1)
  arr.splice(to, 0, item)
}

// 保存杜撰/润色经历的重排序
async function saveFabricatedOrder() {
  if (!resume.value) return
  const current = resume.value.manual_order || {}
  const payload = {
    fabricated: resume.value.fabricated,
    manual_order: { ...current, fabricated: true }
  }
  await saveFields(payload)
  ElMessage.success('排序已保存')
}
async function savePolishedOrder() {
  if (!resume.value) return
  const current = resume.value.manual_order || {}
  const payload = {
    polished_experiences: resume.value.polished_experiences,
    manual_order: { ...current, polished_experiences: true }
  }
  await saveFields(payload)
  ElMessage.success('排序已保存')
}

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

// ---------- ATS ----------

const _ATS_SECTION_LABELS = {
  summary: '个人简介',
  self_eval: '自我评价',
  skills: '技能',
  educations: '教育背景',
  internships: '实习经历',
  projects: '项目经历',
}
function atsSectionLabel(key) {
  return _ATS_SECTION_LABELS[key] || key || ''
}
function atsImportanceTag(imp) {
  return imp === 'high' ? 'danger' : imp === 'medium' ? 'warning' : 'info'
}

async function runAtsScore() {
  atsLoading.value = true
  try {
    atsScore.value = await http.post(`/resumes/${resume.value.id}/ats-score`)
  } catch (e) {
    ElMessage.error(e.message || 'ATS 评估失败')
  } finally {
    atsLoading.value = false
  }
}

// ---------- 求职信 ----------

async function generateCoverLetter() {
  clGenerating.value = true
  try {
    const data = await http.post(`/resumes/${resume.value.id}/cover-letter/generate`,
      { tone: clTone.value })
    resume.value = { ...resume.value, cover_letter: data.content, cover_letter_tone: data.tone }
    ElMessage.success(`求职信已生成（${data.word_count} 字）`)
  } catch (e) {
    ElMessage.error(e.message || '求职信生成失败')
  } finally {
    clGenerating.value = false
  }
}

function startClEdit() {
  clDraft.value = resume.value.cover_letter || ''
  clEditing.value = true
}
function cancelClEdit() {
  clEditing.value = false
  clDraft.value = ''
}
async function saveClEdit() {
  saving.value = true
  try {
    const updated = await http.post(`/resumes/${resume.value.id}/cover-letter/save`,
      { content: clDraft.value })
    resume.value = { ...resume.value, ...updated }
    ElMessage.success('编辑已保存')
    cancelClEdit()
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    saving.value = false
  }
}
function downloadCoverLetter() {
  window.open(`${API_BASE}/resumes/${resume.value.id}/cover-letter/download`, '_blank')
}

// ---------- 反伪造检测 ----------

async function runAntiDetect() {
  adLoading.value = true
  try {
    adReport.value = await http.post(`/resumes/${resume.value.id}/anti-detect`)
  } catch (e) {
    ElMessage.error(e.message || '检测失败')
  } finally {
    adLoading.value = false
  }
}

async function runAntiDetectOptimize() {
  adOptimizing.value = true
  try {
    const updated = await http.post(`/resumes/${resume.value.id}/anti-detect/optimize`)
    resume.value = updated
    // 再跑一次检测刷新 adReport（不浪费第二次 API 调用）
    adReport.value = await http.post(`/resumes/${resume.value.id}/anti-detect`)
    const before = resume.value.anti_detect_result?.before?.score
    const after = resume.value.anti_detect_result?.after?.score
    if (before != null && after != null) {
      if (after < before) {
        ElMessage.success(`✅ AI 痕迹分数 ${(before * 100).toFixed(0)}% → ${(after * 100).toFixed(0)}%，优化生效`)
      } else {
        ElMessage.info(`分数 ${(before * 100).toFixed(0)}% → ${(after * 100).toFixed(0)}%，AI 认为已较自然`)
      }
    } else {
      ElMessage.success('反伪造优化已完成')
    }
  } catch (e) {
    ElMessage.error(e.message || '优化失败（可能未配置 LLM key）')
  } finally {
    adOptimizing.value = false
  }
}
</script>