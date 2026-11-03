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

          <div style="margin-top:10px">
            <span class="text-muted" style="font-size:12px">裁剪策略：</span>
            <el-radio-group v-model="truncateStrategy" size="small">
              <el-radio-button value="time_priority">时间优先</el-radio-button>
              <el-radio-button value="keyword_priority">关键词优先</el-radio-button>
              <el-radio-button value="manual">手动排序</el-radio-button>
            </el-radio-group>
            <div class="text-muted" style="font-size:12px;margin-top:4px">
              时间优先：按结束时间倒序，各 type 独立配额；
              关键词优先：所有经历跨 type 按 JD 匹配度统一排名，定向投递首选；
              手动排序：尊重数组原序（润色/杜撰经历手动排过序时自动生效）
            </div>
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

              <div style="font-weight:600;margin:16px 0 6px">选择要润色并写入简历的经历</div>
              <div class="text-muted" style="font-size:12px;margin-bottom:10px">
                档案中当前有 <b>{{ (profile.internships || []).length }}</b> 段实习经历、
                <b>{{ (profile.projects || []).length }}</b> 段项目经历；已选
                <b>{{ polishSelection.length }}</b> 段。未勾选的经历不会被 AI 润色，也不会出现在简历中。
                <el-button size="small" text type="primary" @click="selectAllReal">全选</el-button>
                <el-button size="small" text @click="polishSelection = []">全不选</el-button>
              </div>

              <el-checkbox-group v-if="realOptions.length" v-model="polishSelection">
                <div v-for="o in realOptions" :key="o.ref_id"
                  style="border:1px solid #e6e8eb;border-radius:8px;padding:10px 12px;margin-bottom:8px">
                  <el-checkbox :label="o.ref_id" style="display:flex;align-items:flex-start">
                    <b>{{ o.title }}</b>
                    <span class="text-muted" style="font-size:12px;margin-left:8px">
                      {{ TYPE_LABELS[o.type] }}<span v-if="o.role"> · {{ o.role }}</span>
                      <span v-if="o.time"> · {{ o.time }}</span>
                    </span>
                  </el-checkbox>
                </div>
              </el-checkbox-group>
              <el-empty v-else description="档案中暂无可润色的经历" :image-size="60" />
            </template>

            <template v-else>
              <el-alert type="info" :closable="false" style="margin:16px 0">
                <template #title>简历将直接使用档案中的实习与项目经历原文，不做 AI 加工。</template>
              </el-alert>
            </template>

            <div style="margin-top:20px">
              <el-button @click="step = 1">上一步</el-button>
              <el-button v-if="expMode === 'fabricate'" type="primary" :loading="busy" @click="generateFabricated">生成经历</el-button>
              <el-button v-else-if="expMode === 'polish' && realCount" type="primary"
                :loading="busy" :disabled="!polishSelection.length" @click="startPolish">
                开始 AI 润色{{ polishSelection.length ? `（已选 ${polishSelection.length} 段）` : '' }}
              </el-button>
              <el-button v-else type="primary" :loading="busy" @click="confirmAndContinue">继续（使用真实经历原文）</el-button>
            </div>
          </template>

          <template v-else>
            <div class="page-sub" style="margin-bottom:8px">
              <template v-if="expMode === 'polish'">
                已润色 {{ editingExperiences.length }} 段真实经历（仅这些经历会写入简历），事实字段已锁定，可调整「核心工作 / 量化成果」，或让 AI 按意见继续修改。
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

        <!-- 3 回答必要问题：一题一屏 + 答题摘要 -->
        <div v-else-if="step === 3">
          <div class="qa-progress">
            <div style="font-weight:600">
              必要问答 · 第 {{ Math.min(qIndex + 1, questions.length || 1) }} / {{ questions.length }} 题
            </div>
            <el-progress :percentage="qProgress" :show-text="false" style="flex:1;margin:0 12px" />
            <el-button size="small" text type="primary" :loading="busy"
              @click="regenerateQuestions">重新出题</el-button>
          </div>

          <template v-if="questionPhase === 'answer' && currentQuestion">
            <div class="qa-card">
              <div class="qa-meta">
                <el-tag v-if="currentQuestion.topic" size="small">{{ currentQuestion.topic }}</el-tag>
                <el-tag size="small" effect="plain" :type="currentQuestion.required ? 'danger' : 'info'">
                  {{ currentQuestion.required ? '必答' : '可跳过' }}
                </el-tag>
                <el-button size="small" text type="primary" :loading="busy"
                  @click="regenerateOne">换一题</el-button>
              </div>
              <div class="qa-question">{{ currentQuestion.question }}</div>
              <div v-if="currentQuestion.why" class="qa-why">为什么要问：{{ currentQuestion.why }}</div>

              <div class="qa-input">
                <el-radio-group v-if="currentQuestion.type === 'choice'" v-model="ans[currentQuestion.id]"
                  @change="scheduleSaveAnswers">
                  <el-radio v-for="o in currentQuestion.options" :key="o" :label="o">{{ o }}</el-radio>
                </el-radio-group>
                <el-checkbox-group v-else-if="currentQuestion.type === 'multi'" v-model="ans[currentQuestion.id]"
                  @change="scheduleSaveAnswers">
                  <el-checkbox v-for="o in currentQuestion.options" :key="o" :label="o">{{ o }}</el-checkbox>
                </el-checkbox-group>
                <el-input v-else v-model="ans[currentQuestion.id]" type="textarea" :rows="4"
                  :placeholder="currentQuestion.hint || '尽量写具体事实与数字，会显著提升简历质量'"
                  @blur="scheduleSaveAnswers" />
              </div>

              <div class="qa-actions">
                <el-button :disabled="qIndex === 0" @click="prevQuestion">上一题</el-button>
                <el-button v-if="!currentQuestion.required" @click="skipQuestion">跳过这题</el-button>
                <el-button v-if="qIndex < questions.length - 1" type="primary" @click="nextQuestion">
                  下一题
                </el-button>
                <el-button v-else type="primary" @click="showQuestionSummary">
                  查看答题摘要
                </el-button>
              </div>
            </div>
          </template>

          <template v-else>
            <div class="qa-card">
              <div style="font-weight:600;margin-bottom:8px">答题摘要</div>
              <div class="text-muted" style="font-size:13px;margin-bottom:12px">
                已答 <b>{{ answeredQuestionCount }}</b> / {{ questions.length }} 题
                <el-tag v-if="missingRequiredCount" type="danger" size="small" style="margin-left:8px">
                  还有 {{ missingRequiredCount }} 道必答题未填写
                </el-tag>
                <el-tag v-else type="success" size="small" style="margin-left:8px">必答题已齐全</el-tag>
              </div>
              <div v-for="(q, i) in questions" :key="q.id" class="qa-sum-item">
                <div class="qa-sum-head">
                  <b>{{ i + 1 }}. {{ q.question }}</b>
                  <el-button size="small" text type="primary" @click="editQuestion(i)">修改</el-button>
                </div>
                <div class="qa-sum-answer" :class="{ empty: !answerText(q) }">
                  {{ answerText(q) || '（未填写）' }}
                </div>
              </div>
              <div class="qa-actions">
                <el-button @click="questionPhase = 'answer'">返回继续作答</el-button>
                <el-button type="primary" :loading="busy" @click="submitAnswers">下一步：自我评价</el-button>
              </div>
            </div>
          </template>
        </div>

        <!-- 4 自我评价问答：一题一屏 + 生成预览 -->
        <div v-else-if="step === 4">
          <div class="qa-progress">
            <div style="font-weight:600">
              自我评价 · {{ sePhase === 'preview' ? '生成预览' : `第 ${Math.min(seIndex + 1, seQuestions.length || 1)} / ${seQuestions.length} 题` }}
            </div>
            <el-progress :percentage="seProgress" :show-text="false" style="flex:1;margin:0 12px" />
            <span class="text-muted" style="font-size:12px">答案会自动保存</span>
          </div>

          <template v-if="sePhase === 'answer' && currentSeQuestion">
            <div class="qa-card">
              <div class="qa-meta">
                <el-tag v-if="currentSeQuestion.topic" size="small">{{ currentSeQuestion.topic }}</el-tag>
                <el-tag size="small" effect="plain" :type="currentSeQuestion.required ? 'danger' : 'info'">
                  {{ currentSeQuestion.required ? '必答' : '可留空' }}
                </el-tag>
              </div>
              <div class="qa-question">{{ currentSeQuestion.question }}</div>
              <div v-if="currentSeQuestion.why" class="qa-why">为什么要问：{{ currentSeQuestion.why }}</div>

              <div class="qa-input">
                <el-radio-group v-if="currentSeQuestion.type === 'choice'" v-model="seAns[currentSeQuestion.id]"
                  @change="scheduleSaveSeAnswers">
                  <el-radio v-for="o in currentSeQuestion.options" :key="o" :label="o">{{ o }}</el-radio>
                </el-radio-group>
                <el-checkbox-group v-else-if="currentSeQuestion.type === 'multi'" v-model="seAns[currentSeQuestion.id]"
                  @change="scheduleSaveSeAnswers">
                  <el-checkbox v-for="o in currentSeQuestion.options" :key="o" :label="o">{{ o }}</el-checkbox>
                </el-checkbox-group>
                <el-input v-else v-model="seAns[currentSeQuestion.id]" type="textarea" :rows="4"
                  :placeholder="currentSeQuestion.hint || (currentSeQuestion.required ? '' : '可留空')"
                  @blur="scheduleSaveSeAnswers" />
              </div>

              <div class="qa-actions">
                <el-button :disabled="seIndex === 0" @click="prevSeQuestion">上一题</el-button>
                <el-button v-if="!currentSeQuestion.required" @click="skipSeQuestion">跳过这题</el-button>
                <el-button v-if="seIndex < seQuestions.length - 1" type="primary" @click="nextSeQuestion">
                  下一题
                </el-button>
                <el-button v-else type="primary" :loading="busy" @click="generateSePreview">
                  生成自我评价
                </el-button>
              </div>
            </div>
          </template>

          <template v-else>
            <div class="qa-card">
              <div class="se-preview" v-html="highlightSeText(sePreview)" />
              <div class="se-metrics">
                <el-tag size="small" :type="seMetrics.lengthOk ? 'success' : 'warning'">
                  字数 {{ seMetrics.length }}（建议 100~180）
                </el-tag>
                <el-tag size="small" :type="seMetrics.hitRate >= 60 ? 'success' : 'warning'">
                  JD 关键词命中 {{ seMetrics.hits }} / {{ seMetrics.total }}（{{ seMetrics.hitRate }}%）
                </el-tag>
                <el-tag v-if="seMetrics.cliches.length" size="small" type="danger">
                  套话 {{ seMetrics.cliches.length }} 处：{{ seMetrics.cliches.join('、') }}
                </el-tag>
                <el-tag v-else size="small" type="success">未发现常见套话</el-tag>
              </div>
              <div v-if="seMetrics.missed.length" class="text-muted" style="font-size:12px;margin-top:8px">
                尚未体现的 JD 关键词：{{ seMetrics.missed.join('、') }}；可在「返回修改答案」中补充事实后再生成。
              </div>
              <div class="qa-actions">
                <el-button @click="sePhase = 'answer'">返回修改答案</el-button>
                <el-button :loading="busy" @click="generateSePreview">换一版</el-button>
                <el-button type="primary" :loading="busy" @click="confirmSeAndBuild">
                  确认并生成简历
                </el-button>
              </div>
            </div>
          </template>
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
import { ElMessage, ElMessageBox } from 'element-plus'
import http, { WS_BASE } from '@/api'

const router = useRouter()
const route = useRoute()
const editId = computed(() => route.params.id)

const TYPE_LABELS = {
  project: '项目经历',
  internship: '实习经历',
  work: '全职经历',
  other: '其他经历'
}

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
const polishSelection = ref([]) // 勾选参与润色（并写入简历）的真实经历 ref_id
const timelineWarnings = ref([])
const profile = ref({})
const fabMax = ref(5)
const interviewPrep = ref({})
const questions = ref([])
const ans = reactive({})
const seQuestions = ref([])
const seAns = reactive({})
const qIndex = ref(0)            // 必要问答：当前题序号
const questionPhase = ref('answer') // answer 逐题作答 | summary 答题摘要
const seIndex = ref(0)           // 自我评价：当前题序号
const sePhase = ref('answer')    // answer 逐题作答 | preview 生成预览
const sePreview = ref('')        // 已生成的自我评价正文
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
const truncateStrategy = ref('time_priority')

// 复核阶段当前编辑的经历列表：润色模式用润色稿，其余用杜撰稿
const editingExperiences = computed(() =>
  expMode.value === 'polish' ? polished.value : fabricated.value)
const realCount = computed(() =>
  (profile.value.internships?.length || 0) + (profile.value.projects?.length || 0))

// 档案中可勾选润色的真实经历（ref_id 与后端 collect_real_experiences 编号一致）
const realOptions = computed(() => {
  const out = []
  ;(profile.value.internships || []).forEach((it, i) => out.push({
    ref_id: `internship-${i}`,
    type: 'internship',
    title: it.company || '未命名实习',
    role: it.position || '',
    time: [it.start_date, it.end_date].filter(Boolean).join(' - ')
  }))
  ;(profile.value.projects || []).forEach((it, i) => out.push({
    ref_id: `project-${i}`,
    type: 'project',
    title: it.title || '未命名项目',
    role: it.role || '',
    time: [it.start_date, it.end_date].filter(Boolean).join(' - ')
  }))
  return out
})

function selectAllReal() {
  polishSelection.value = realOptions.value.map((o) => o.ref_id)
}

// ---------- 必要问答：一题一屏 ----------
const currentQuestion = computed(() => questions.value[qIndex.value] || null)
const qProgress = computed(() => {
  if (!questions.value.length) return 0
  return Math.round(((qIndex.value + (questionPhase.value === 'summary' ? 1 : 0)) / questions.value.length) * 100)
})
const answeredQuestionCount = computed(() =>
  questions.value.filter((q) => answerText(q)).length)
const missingRequiredCount = computed(() =>
  questions.value.filter((q) => q.required && !answerText(q)).length)

function answerText(q) {
  if (!q) return ''
  const v = ans[q.id]
  return Array.isArray(v) ? v.filter(Boolean).join('、') : (v || '').trim()
}

function collectAnswers() {
  return questions.value.map((q) => ({
    id: q.id,
    question: q.question,
    answer: answerText(q)
  }))
}

// 自动保存：输入后 800ms 落库，避免频繁请求
let answersTimer = null
function scheduleSaveAnswers() {
  clearTimeout(answersTimer)
  answersTimer = setTimeout(() => { saveAnswersDraft().catch(() => {}) }, 800)
}

async function saveAnswersDraft() {
  if (!resumeId.value || !questions.value.length) return
  await http.post(`/resumes/${resumeId.value}/answers`, {
    answers: collectAnswers(),
    draft: true
  })
}

function prevQuestion() {
  if (qIndex.value > 0) qIndex.value--
}

function nextQuestion() {
  if (currentQuestion.value?.required && !answerText(currentQuestion.value)) {
    ElMessage.warning('这是必答题，请先填写后再进入下一题（也可以点「换一题」换掉它）')
    return
  }
  if (qIndex.value < questions.value.length - 1) {
    qIndex.value++
    scheduleSaveAnswers()
  }
}

function skipQuestion() {
  if (currentQuestion.value?.required) {
    ElMessage.warning('必答题不能跳过，可填写或点「换一题」')
    return
  }
  nextQuestion()
}

function showQuestionSummary() {
  scheduleSaveAnswers()
  questionPhase.value = 'summary'
}

function editQuestion(i) {
  qIndex.value = i
  questionPhase.value = 'answer'
}

async function regenerateQuestions() {
  try {
    await ElMessageBox.confirm(
      '重新出题会替换当前全部问题，已填写的答案将清空。是否继续？',
      '重新出题', { confirmButtonText: '重新出题', cancelButtonText: '取消', type: 'warning' })
  } catch { return }
  busy.value = true
  startProgress()
  try {
    await genQuestions()
    ElMessage.success('已重新生成必要问题')
  } catch (e) {
    ElMessage.error(e.message || '重新出题失败')
  } finally {
    stopProgress()
    busy.value = false
  }
}

async function regenerateOne() {
  if (!currentQuestion.value) return
  busy.value = true
  startProgress()
  try {
    const q = currentQuestion.value
    const r = await http.post(`/resumes/${resumeId.value}/questions/regenerate`, {
      question_id: q.id,
      topic: q.topic || ''
    })
    questions.value = r.questions || questions.value
    ans[q.id] = (r.question?.type === 'multi') ? [] : ''
    ElMessage.success('已换一题，原题答案已清除')
  } catch (e) {
    ElMessage.error(e.message || '换题失败，请稍后再试')
  } finally {
    stopProgress()
    busy.value = false
  }
}

// ---------- 自我评价：一题一屏 + 预览 ----------
const currentSeQuestion = computed(() => seQuestions.value[seIndex.value] || null)
const seProgress = computed(() => {
  if (!seQuestions.value.length) return 0
  if (sePhase.value === 'preview') return 100
  return Math.round((seIndex.value / seQuestions.value.length) * 100)
})

function seAnswerText(q) {
  if (!q) return ''
  const v = seAns[q.id]
  return Array.isArray(v) ? v.filter(Boolean).join('、') : (v || '').trim()
}

let seAnswersTimer = null
function scheduleSaveSeAnswers() {
  clearTimeout(seAnswersTimer)
  seAnswersTimer = setTimeout(() => { saveSeAnswers().catch(() => {}) }, 800)
}

function prevSeQuestion() {
  if (seIndex.value > 0) seIndex.value--
}

function nextSeQuestion() {
  if (currentSeQuestion.value?.required && !seAnswerText(currentSeQuestion.value)) {
    ElMessage.warning('这是必答题，请先填写后再进入下一题')
    return
  }
  if (seIndex.value < seQuestions.value.length - 1) {
    seIndex.value++
    scheduleSaveSeAnswers()
  }
}

function skipSeQuestion() {
  if (currentSeQuestion.value?.required) {
    ElMessage.warning('必答题不能跳过，请填写后再继续')
    return
  }
  nextSeQuestion()
}

const SE_CLICHES = [
  '工作认真负责', '吃苦耐劳', '团队合作精神', '热爱学习', '沟通能力强',
  '学习能力强', '责任心强', '抗压能力强', '积极主动'
]

const seMetrics = computed(() => {
  const text = (sePreview.value || '').replace(/\*\*/g, '')
  const length = text.replace(/\s/g, '').length
  const kws = [...new Set([
    ...(jdSummary.value.tech || []),
    ...(jdSummary.value.soft || []),
    ...(jdSummary.value.domain || [])
  ].map((k) => String(k || '').trim()).filter(Boolean))]
  const lower = text.toLowerCase()
  const hitList = kws.filter((k) => lower.includes(k.toLowerCase()))
  const missed = kws.filter((k) => !lower.includes(k.toLowerCase()))
  return {
    length,
    lengthOk: length >= 100 && length <= 180,
    hits: hitList.length,
    total: kws.length,
    hitRate: kws.length ? Math.round((hitList.length * 100) / kws.length) : 100,
    missed,
    cliches: SE_CLICHES.filter((c) => text.includes(c))
  }
})

function highlightSeText(text) {
  const safe = (text || '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  return safe.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>').replace(/\n/g, '<br>')
}

function supplementValue() {
  return (seAns.supplement || '').trim()
}

async function generateSePreview() {
  const missing = seQuestions.value.filter((q) => q.required && !seAnswerText(q))
  if (missing.length) {
    ElMessage.warning(`还有 ${missing.length} 道必答题未完成，请补全后再生成`)
    return
  }
  busy.value = true
  startProgress()
  try {
    await saveSeAnswers()
    const r = await http.post('/self-evaluation/generate', {
      resume_id: resumeId.value,
      answers: collectSeAnswers().answers,
      supplement: supplementValue(),
      previous: sePreview.value
    })
    sePreview.value = r.content || ''
    sePhase.value = 'preview'
  } catch (e) {
    ElMessage.error(e.message || '生成自我评价失败')
  } finally {
    stopProgress()
    busy.value = false
  }
}

async function confirmSeAndBuild() {
  if (!sePreview.value) {
    ElMessage.warning('请先生成自我评价预览')
    return
  }
  busy.value = true
  step.value = 5
  startProgress()
  try {
    await http.post(`/resumes/${resumeId.value}/generate`)
    ElMessage.success('简历已生成')
    router.push(`/resume/${resumeId.value}`)
  } catch (e) {
    ElMessage.error(e.message || '生成简历失败')
    step.value = 4
  } finally {
    stopProgress()
    busy.value = false
  }
}

// 恢复勾选：优先使用已保存的选择，无历史选择（旧任务）时默认全选
function initPolishSelection(saved) {
  const all = realOptions.value.map((o) => o.ref_id)
  const keep = (saved || []).filter((r) => all.includes(r))
  polishSelection.value = keep.length ? keep : all
}

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
  seIndex.value = 0
  sePhase.value = 'answer'
  sePreview.value = ''
}

async function saveSeAnswers() {
  await http.post(`/resumes/${resumeId.value}/se-answers`, collectSeAnswers())
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
  truncateStrategy.value = r.truncate_strategy || 'time_priority'
  sections.value = (r.sections && r.sections.length) ? r.sections : MODULES.map((m) => m.key)
  jdSummary.value = r.jd_summary || {}
  fabricated.value = r.fabricated || []
  polished.value = r.polished_experiences || []
  initPolishSelection(r.polish_selection)
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
    seIndex.value = 0
    // 已生成过自我评价预览（尚未确认生成简历）时，直接回到预览继续
    if (r.self_evaluation && (r.se_answers || []).length) {
      sePreview.value = r.self_evaluation
      sePhase.value = 'preview'
    }
    return
  }
  if (r.status === 'questioning') {
    step.value = 3
    qIndex.value = 0
    questionPhase.value = 'answer'
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
  if (!editId.value) {
    selectAllReal()
    return
  }
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
      custom_pages: length.value === 'custom' ? customPages.value : null,
      truncate_strategy: truncateStrategy.value
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
  qIndex.value = 0
  questionPhase.value = 'answer'
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
  if (!polishSelection.value.length) {
    ElMessage.warning('请至少勾选一段需要润色的经历')
    return
  }
  busy.value = true
  startProgress()
  try {
    const r = await http.post(`/resumes/${resumeId.value}/polish`, {
      ref_ids: polishSelection.value
    })
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
  if (missingRequiredCount.value) {
    questionPhase.value = 'summary'
    ElMessage.warning(`还有 ${missingRequiredCount.value} 道必答题未填写，请补全后再继续`)
    return
  }
  busy.value = true
  startProgress()
  try {
    await http.post(`/resumes/${resumeId.value}/answers`, {
      answers: collectAnswers(),
      draft: false
    })
    await fetchSeQuestions()
    step.value = 4
  } catch (e) {
    ElMessage.error(e.message || '保存答案失败')
  } finally {
    stopProgress()
    busy.value = false
  }
}
</script>

<style scoped>
.qa-progress {
  display: flex;
  align-items: center;
  margin-bottom: 14px;
  gap: 4px;
}
.qa-card {
  border: 1px solid #e6e8eb;
  border-radius: 10px;
  padding: 20px 22px;
  background: #fff;
}
.qa-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}
.qa-question {
  font-size: 17px;
  font-weight: 600;
  line-height: 1.6;
  margin-bottom: 8px;
  color: #303133;
}
.qa-why {
  font-size: 12px;
  color: #909399;
  margin-bottom: 14px;
}
.qa-input {
  margin-bottom: 16px;
}
.qa-input :deep(.el-radio-group),
.qa-input :deep(.el-checkbox-group) {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.qa-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding-top: 12px;
  border-top: 1px dashed #ebeef5;
}
.qa-sum-item {
  border-top: 1px dashed #ebeef5;
  padding: 10px 0;
}
.qa-sum-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}
.qa-sum-answer {
  font-size: 13px;
  line-height: 1.7;
  color: #606266;
  background: #f7f8fa;
  border-radius: 6px;
  padding: 8px 10px;
  margin-top: 6px;
  white-space: pre-wrap;
}
.qa-sum-answer.empty {
  color: #c0c4cc;
}
.se-preview {
  font-size: 14px;
  line-height: 1.9;
  color: #303133;
  background: #fbfcfd;
  border-left: 3px solid #409eff;
  border-radius: 6px;
  padding: 14px 16px;
  min-height: 80px;
}
.se-metrics {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}
</style>