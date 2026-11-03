<template>
  <div class="resume-page">
    <!-- 顶部：标题 + 金色徽章，底部蓝色粗分割线 -->
    <div class="resume-header">
      <div class="header-left">
        <h1>个人简历</h1>
        <p>细心从每一个细节开始 &nbsp;&nbsp;Personal resume</p>
      </div>
      <div class="header-right">
        <div class="icon-circle">🎓</div>
        <div class="icon-circle">💼</div>
      </div>
    </div>

    <!-- 各章节：顺序与简历板块约定一致 -->
    <div v-for="sec in visibleSections" :key="sec.key" class="section">
      <div class="section-title">{{ sec.title }}</div>

      <!-- 基本信息：标签值纯文本两列 + 右侧头像（有头像才显示，无头像不占位） -->
      <template v-if="sec.key === 'basics'">
        <div class="info-section" :class="{ 'no-avatar': !avatarSrc }">
          <div class="info-table">
            <div v-for="(b, i) in basicItems" :key="i" class="info-item">
              <span>{{ b.label }}：{{ b.value }}</span>
            </div>
          </div>
          <div v-if="avatarSrc" class="avatar-box">
            <img :src="avatarSrc" alt="头像" />
          </div>
        </div>
      </template>

      <!-- 个人简介 -->
      <p v-else-if="sec.key === 'summary'" class="desc-text">
        <span v-for="(s, i) in segs(ctx.personal_summary)" :key="i" :class="{ hl: s.em }">{{ s.t }}</span>
      </p>

      <!-- 教育背景 -->
      <template v-else-if="sec.key === 'education'">
        <div v-for="(edu, i) in user.educations" :key="i" class="content-block">
          <div class="row-header">
            <span>{{ timeRange(edu) }}</span>
            <span>{{ edu.school }}</span>
            <span>{{ [edu.major, edu.degree].filter(Boolean).join('（') }}{{ edu.major && edu.degree ? '）' : '' }}</span>
          </div>
          <p v-if="edu.gpa || edu.rank" class="desc-text">
            专业成绩：{{ [edu.gpa && `GPA ${edu.gpa}`, edu.rank && `排名 ${edu.rank}`].filter(Boolean).join('，') }}
          </p>
          <p v-if="edu.courses" class="desc-text">主修课程：{{ edu.courses }}</p>
        </div>
      </template>

      <!-- 专业技能：进度条，熟练度描述词在技能名右侧对齐 -->
      <template v-else-if="sec.key === 'skills'">
        <div v-for="g in skillGroups" :key="g.cat" class="content-block">
          <p v-if="skillGroups.length > 1" class="skill-cat">{{ g.cat }}：</p>
          <div class="skill-bar-wrap">
            <div v-for="(s, i) in g.items" :key="i" class="skill-item">
              <div class="skill-name"><span>{{ s.name }}</span><span class="s-level">{{ s.proficiency }}</span></div>
              <div class="bar-bg"><div class="bar-fill" :style="{ width: profPct(s.proficiency) + '%' }"></div></div>
            </div>
          </div>
        </div>
      </template>

      <!-- 实习 / 工作 / 其他经历（含杜撰合并） -->
      <template v-else-if="sec.key === 'internships' || sec.key === 'work' || sec.key === 'other'">
        <div v-for="(it, i) in sec.items" :key="i" class="content-block">
          <div class="row-header">
            <span>{{ timeRange(it) }}</span>
            <span>{{ it.company }}</span>
            <span>{{ it.position }}</span>
          </div>
          <ul>
            <li v-if="it.description">
              <span v-for="(s, j) in segs(it.description)" :key="j" :class="{ hl: s.em }">{{ s.t }}</span>
            </li>
            <li v-if="it.achievement">
              <span v-for="(s, j) in segs(it.achievement)" :key="j" :class="{ hl: s.em }">{{ s.t }}</span>
            </li>
          </ul>
        </div>
      </template>

      <!-- 项目经历（含杜撰合并） -->
      <template v-else-if="sec.key === 'projects'">
        <div v-for="(p, i) in sec.items" :key="i" class="content-block">
          <div class="row-header">
            <span>{{ timeRange(p) }}</span>
            <span>{{ p.title }}</span>
            <span>{{ p.role }}</span>
          </div>
          <p v-if="p.tech_stack" class="desc-text">技术栈：{{ p.tech_stack }}</p>
          <ul>
            <li v-if="p.description">
              <span v-for="(s, j) in segs(p.description)" :key="j" :class="{ hl: s.em }">{{ s.t }}</span>
            </li>
            <li v-if="p.result">
              <span v-for="(s, j) in segs(p.result)" :key="j" :class="{ hl: s.em }">{{ s.t }}</span>
            </li>
          </ul>
        </div>
      </template>

      <!-- 证书 / 获奖 -->
      <ul v-else-if="sec.key === 'certificates'" class="content-block">
        <li v-for="(c, i) in user.certificates" :key="i">{{ c.name }}{{ c.date ? `（${c.date}）` : '' }}</li>
      </ul>

      <!-- 自我评价 -->
      <div v-else-if="sec.key === 'self_evaluation'" class="content-block">
        <p class="desc-text">
          <span v-for="(s, i) in segs(ctx.self_evaluation)" :key="i" :class="{ hl: s.em }">{{ s.t }}</span>
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { fileUrl } from '@/api'
import {
  segs, profPct, timeRange, isEnabled, mergeExperiences, skillGroupsOf
} from './resumeShared'

// ctx 与后端 /resumes/{id}/render-context 返回结构一致
const props = defineProps({
  ctx: { type: Object, required: true }
})

const user = computed(() => props.ctx.user || {})
// 头像引用用户基本信息里上传的头像；未上传时显示占位
const avatarSrc = computed(() => fileUrl(user.value.avatar))

// 基本信息两列网格：仅展示已填写的字段
const basicItems = computed(() => {
  const u = user.value
  const all = [
    { label: '姓　　名', value: u.name },
    { label: '联系电话', value: u.phone },
    { label: '电子邮箱', value: u.email },
    { label: '现居城市', value: u.location },
    { label: '求职岗位', value: props.ctx.target_position || u.target_position },
    { label: '期望薪资', value: props.ctx.include_salary ? props.ctx.expected_salary : '' },
    { label: '毕业时间', value: u.graduation_date },
    { label: '兴趣爱好', value: u.hobbies },
  ]
  return all.filter((x) => (x.value || '').trim())
})

const merged = computed(() => mergeExperiences(props.ctx))
const skillGroups = computed(() => skillGroupsOf(props.ctx))

const visibleSections = computed(() => {
  const defs = [
    { key: 'basics', title: '基本信息', show: true },
    { key: 'summary', title: '个人简介', show: !!props.ctx.personal_summary },
    { key: 'education', title: '教育背景', show: (user.value.educations || []).length > 0 },
    { key: 'skills', title: '技能特长', show: skillGroups.value.length > 0 },
    { key: 'internships', title: '实习经历', show: merged.value.internships.length > 0, items: merged.value.internships },
    { key: 'work', title: '工作经历', show: merged.value.works.length > 0, items: merged.value.works },
    { key: 'other', title: '其他经历', show: merged.value.others.length > 0, items: merged.value.others },
    { key: 'projects', title: '项目经历', show: merged.value.projects.length > 0, items: merged.value.projects },
    { key: 'certificates', title: '荣誉证书', show: (user.value.certificates || []).length > 0 },
    { key: 'self_evaluation', title: '自我评价', show: !!props.ctx.self_evaluation },
  ]
  return defs.filter((d) => isEnabled(props.ctx, d.key) && d.show)
})
</script>

<style scoped>
* { margin: 0; padding: 0; box-sizing: border-box; font-family: "Microsoft Yahei", SimSun, sans-serif; }

:root {
  --primary: #427aa1;
  --gold: #d4af37;
}

/* A4 纸张容器 */
.resume-page {
  width: 210mm;
  min-height: 297mm;
  background: #fff;
  margin: 0 auto;
  padding: 12mm 14mm;
  color: #333;
}

/* 头部标题 */
.resume-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 6px 6px;
  border-bottom: 4px solid #427aa1;
  margin-bottom: 4px;
}
.header-left h1 { font-size: 26px; color: #427aa1; font-weight: bold; letter-spacing: 3px; }
.header-left p { color: #666; font-size: 13px; margin-top: 1px; }
.header-right { display: flex; gap: 12px; }
.icon-circle {
  width: 34px; height: 34px; border-radius: 50%;
  background: #d4af37; color: #fff;
  display: flex; align-items: center; justify-content: center;
  font-size: 16px;
}

/* 通用板块：蓝色箭头形标题条；板块之间不留间距 */
.section { padding: 0; }
.section-title {
  background: #427aa1;
  color: #fff;
  font-size: 15px;
  font-weight: bold;
  letter-spacing: 2px;
  padding: 3px 14px;
  margin-bottom: 5px;
  clip-path: polygon(0 0, calc(100% - 12px) 0, 100% 50%, calc(100% - 12px) 100%, 0 100%);
}

/* 基本信息：信息网格铺满宽度，避免与头像之间出现大片空档 */
.info-section { display: flex; padding: 0 6px 4px; gap: 16px; }
.info-section.no-avatar { gap: 0; }
.info-table { flex: 1; display: grid; grid-template-columns: 1fr 1fr; gap: 4px 20px; align-content: start; }
.info-item span { color: #333; font-size: 12.5px; line-height: 1.4; }
.avatar-box { width: 100px; flex: none; text-align: center; }
.avatar-box img { width: 100px; height: 100px; border: 1px solid #ccc; object-fit: cover; }

/* 内容行：时间 - 主体 - 右侧，加粗 */
.row-header {
  display: flex; justify-content: space-between; gap: 12px;
  font-weight: bold; margin-bottom: 3px; font-size: 14px; color: #222;
}
.content-block { margin-bottom: 6px; }
ul { padding-left: 18px; line-height: 1.45; }
li { font-size: 12.5px; margin-bottom: 0; color: #333; }
li::marker { color: #427aa1; }

/* 技能进度条：三列布局压缩纵向空间，技能名左、熟练度右对齐同行 */
.skill-cat { font-size: 12px; font-weight: bold; color: #427aa1; margin-bottom: 2px; }
.skill-bar-wrap { margin: 2px 0; display: grid; grid-template-columns: repeat(3, 1fr); gap: 3px 20px; }
.skill-item { min-width: 0; }
.skill-name { display: flex; justify-content: space-between; align-items: baseline; font-size: 12px; line-height: 1.3; }
.s-level { font-size: 11px; color: #555; }
.bar-bg { width: 100%; height: 5px; background: #ddd; margin-top: 2px; }
.bar-fill { height: 5px; background: #427aa1; }

/* 评价/正文文本 */
.desc-text { line-height: 1.5; color: #333; font-size: 12.5px; margin-bottom: 1px; }
.hl { color: #427aa1; font-weight: bold; }

/* 打印：强制输出背景色（标题条/进度条/徽章），允许内容跨页自然流动 */
.resume-page,
.resume-page * {
  -webkit-print-color-adjust: exact;
  print-color-adjust: exact;
}

@media print {
  .resume-page {
    width: auto;
    min-height: 0;
    height: auto;
    overflow: visible;
    padding: 12mm 14mm;
  }
  .section, .content-block, .info-section, .skill-item {
    break-inside: avoid;
  }
}
</style>
