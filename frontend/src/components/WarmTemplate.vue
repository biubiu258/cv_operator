<template>
  <div class="resume-page">
    <!-- 装饰星星 -->
    <div class="star star1">★</div>
    <div class="star star2">✦</div>

    <!-- 联系方式悬浮卡片 -->
    <div v-if="user.phone || user.email" class="contact-card">
      <p v-if="user.phone">电话 {{ user.phone }}</p>
      <p v-if="user.email">邮箱 {{ user.email }}</p>
    </div>

    <!-- 顶部区域 -->
    <div class="header-wrap">
      <div class="avatar-box">
        <img :src="avatarSrc" alt="头像" />
      </div>
      <div class="header-info">
        <div class="header-top">
          <h1>{{ user.name || '姓名' }}</h1>
          <span class="sub-title">CURRICULUM VITAE</span>
        </div>
        <p class="sub-title">求职意向：{{ position }}</p>
        <div class="meta-row">
          <span v-for="(m, i) in metaTags" :key="i" class="meta-tag">{{ m }}</span>
        </div>
      </div>
    </div>

    <!-- 各章节：顺序与简历板块约定一致，序号自动生成 -->
    <div v-for="sec in visibleSections" :key="sec.key" class="section">
      <div class="section-title">
        <span class="num-tag">{{ sec.num }}</span>
        <span>{{ sec.title }} <span class="en">{{ sec.en }}</span></span>
      </div>
      <div class="divider-line"></div>

      <!-- 个人简介 -->
      <p v-if="sec.key === 'summary'" class="para">
        <span v-for="(s, i) in segs(ctx.personal_summary)" :key="i" :class="{ hl: s.em }">{{ s.t }}</span>
      </p>

      <!-- 教育背景 -->
      <template v-else-if="sec.key === 'education'">
        <div v-for="(edu, i) in user.educations" :key="i" class="entry">
          <div class="item-header">
            <span class="item-name">{{ [edu.school, edu.major, edu.degree].filter(Boolean).join(' | ') }}</span>
            <span class="item-time">{{ timeRange(edu) }}</span>
          </div>
          <p v-if="edu.gpa || edu.rank" class="para-sm">
            {{ [edu.gpa && `GPA ${edu.gpa}`, edu.rank && `排名 ${edu.rank}`].filter(Boolean).join(' · ') }}
          </p>
          <p v-if="edu.courses" class="para-sm">主修课程：{{ edu.courses }}</p>
        </div>
      </template>

      <!-- 专业技能：进度条 + 熟练度描述词，每行两个条目 -->
      <template v-else-if="sec.key === 'skills'">
        <div v-for="g in skillGroups" :key="g.cat">
          <div v-if="skillGroups.length > 1" class="skill-cat">{{ g.cat }}</div>
          <div class="skill-row">
            <div v-for="(s, i) in g.items" :key="i" class="skill-item">
              <div class="skill-name"><span>{{ s.name }}</span><span>{{ s.proficiency }}</span></div>
              <div class="bar-wrap"><div class="bar" :style="{ width: pct(s.proficiency) + '%' }"></div></div>
            </div>
          </div>
        </div>
      </template>

      <!-- 实习 / 工作 / 其他经历（含杜撰合并） -->
      <template v-else-if="sec.key === 'internships' || sec.key === 'work' || sec.key === 'other'">
        <div v-for="(it, i) in sec.items" :key="i" class="entry">
          <div class="item-header">
            <span class="item-name">{{ [it.company, it.position].filter(Boolean).join(' | ') }}</span>
            <span class="item-time">{{ timeRange(it) }}</span>
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
        <div v-for="(p, i) in sec.items" :key="i" class="entry">
          <div class="item-header">
            <span class="item-name">{{ p.title }}</span>
            <span class="item-time">{{ timeRange(p) }}</span>
          </div>
          <div v-if="p.role" class="item-subinfo">{{ p.role }}</div>
          <div v-if="p.tech_stack" class="tech-line">技术栈 {{ p.tech_stack }}</div>
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
      <ul v-else-if="sec.key === 'certificates'">
        <li v-for="(c, i) in user.certificates" :key="i">{{ c.name }}{{ c.date ? `（${c.date}）` : '' }}</li>
      </ul>

      <!-- 自我评价 -->
      <div v-else-if="sec.key === 'self_evaluation'" class="eval-box">
        <span v-for="(s, i) in segs(ctx.self_evaluation)" :key="i" :class="{ hl: s.em }">{{ s.t }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import {
  segs, profPct as pct, timeRange, positionOf, isEnabled as enabled,
  mergeExperiences, skillGroupsOf, avatarSrcOf
} from './resumeShared'

// ctx 与后端 /resumes/{id}/render-context 返回结构一致，
// 字段同 resume_generator.build_resume_docx 入参（另附 budget 用于篇幅裁剪）
const props = defineProps({
  ctx: { type: Object, required: true }
})

const user = computed(() => props.ctx.user || {})
const avatarSrc = computed(() => avatarSrcOf(user.value))
const position = computed(() => positionOf(props.ctx))

const metaTags = computed(() => {
  const tags = []
  if (user.value.location) tags.push(`城市：${user.value.location}`)
  if (props.ctx.include_salary && props.ctx.expected_salary) {
    tags.push(`期望薪资：${props.ctx.expected_salary}`)
  }
  return tags
})

const merged = computed(() => mergeExperiences(props.ctx))
const internships = computed(() => merged.value.internships)
const works = computed(() => merged.value.works)
const others = computed(() => merged.value.others)
const projects = computed(() => merged.value.projects)

const skillGroups = computed(() => skillGroupsOf(props.ctx))

const visibleSections = computed(() => {
  const defs = [
    { key: 'summary', title: '个人简介', en: 'SUMMARY', show: !!props.ctx.personal_summary },
    { key: 'education', title: '教育背景', en: 'EDUCATION', show: (user.value.educations || []).length > 0 },
    { key: 'skills', title: '专业技能', en: 'SKILLS', show: skillGroups.value.length > 0 },
    { key: 'internships', title: '实习经历', en: 'INTERNSHIP', show: internships.value.length > 0, items: internships.value },
    { key: 'work', title: '工作经历', en: 'WORK', show: works.value.length > 0, items: works.value },
    { key: 'other', title: '其他经历', en: 'OTHER', show: others.value.length > 0, items: others.value },
    { key: 'projects', title: '项目经历', en: 'PROJECTS', show: projects.value.length > 0, items: projects.value },
    { key: 'certificates', title: '证书 / 获奖', en: 'CERTIFICATES', show: (user.value.certificates || []).length > 0 },
    { key: 'self_evaluation', title: '自我评价', en: 'ABOUT ME', show: !!props.ctx.self_evaluation },
  ]
  return defs
    .filter((d) => enabled(d.key) && d.show)
    .map((d, i) => ({ ...d, num: String(i + 1).padStart(2, '0') }))
})
</script>

<style scoped>
* { margin: 0; padding: 0; box-sizing: border-box; font-family: "Microsoft YaHei", sans-serif; }

/* A4 纸张容器 */
.resume-page {
  width: 210mm;
  min-height: 297mm;
  background: #fff;
  margin: 0 auto;
  position: relative;
  overflow: hidden;
  padding: 12mm 14mm;
  color: #333;
}
/* 右上角斜向浅黄色色块 */
.resume-page::after {
  content: "";
  position: absolute;
  top: 0; right: 0;
  width: 65%; height: 110px;
  background: #fff2b8;
  clip-path: polygon(20% 0, 100% 0, 100% 100%, 0% 100%);
  z-index: 1;
}
.header-wrap { display: flex; gap: 16px; position: relative; z-index: 2; margin-bottom: 10px; }
.avatar-box {
  width: 96px; height: 96px; flex: none;
  border: 2px solid #f2d049; border-radius: 6px;
  overflow: hidden; background: #fff;
}
.avatar-box img { width: 100%; height: 100%; object-fit: cover; }
.header-info { flex: 1; }
.header-top { display: flex; align-items: center; gap: 12px; }
.header-top h1 { font-size: 26px; color: #333; letter-spacing: 2px; }
.header-top .sub-title { color: #666; font-size: 12.5px; }
.sub-title { color: #666; font-size: 12.5px; margin-top: 2px; }
.meta-row { display: flex; gap: 8px; margin: 4px 0; }
.meta-tag { background: #f0f0f0; padding: 2px 8px; border-radius: 12px; font-size: 12px; }
.contact-card {
  position: absolute; top: 15px; right: 15px;
  background: #fff; padding: 8px; border: 1px solid #ccc;
  box-shadow: 2px 2px 0 #ddd;
  z-index: 3; font-size: 12px;
}
.contact-card p { margin: 2px 0; }

/* 章节模块通用：板块间距压缩 */
.section { margin-bottom: 10px; }
.section-title {
  display: flex; align-items: center; gap: 8px;
  font-size: 15px; color: #b88629; font-weight: bold; margin-bottom: 5px;
}
.section-title .num-tag {
  width: 22px; height: 22px; background: #d4aa48; color: #fff;
  display: grid; place-items: center; border-radius: 4px; font-size: 13px;
}
.section-title .en { font-size: 12px; color: #666; font-weight: normal; }
.section .divider-line { border-bottom: 1px dashed #ccc; margin-bottom: 6px; }

/* 条目 */
.entry { margin-bottom: 8px; }
.item-header { display: flex; justify-content: space-between; margin-bottom: 3px; }
.item-name { font-weight: bold; font-size: 14px; }
.item-time { color: #666; font-size: 12.5px; }
.item-subinfo { color: #555; font-size: 12.5px; margin-bottom: 3px; }
.para { font-size: 12.5px; line-height: 1.5; }
.para-sm { font-size: 12.5px; line-height: 1.5; margin-bottom: 3px; }
.hl { color: #b88629; font-weight: bold; }
ul { padding-left: 18px; }
li { font-size: 12.5px; line-height: 1.5; margin-bottom: 1px; color: #333; }
.tech-line { font-size: 12px; color: #b88629; font-weight: bold; margin-bottom: 2px; }

/* 技能进度条：每行三个条目 */
.skill-cat { font-size: 12.5px; font-weight: bold; color: #b88629; margin: 4px 0 2px; }
.skill-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 3px 20px; margin-top: 4px; }
.skill-item { min-width: 0; }
.skill-name { display: flex; justify-content: space-between; font-size: 12.5px; margin-bottom: 2px; }
.bar-wrap { height: 5px; background: #eee; border-radius: 3px; overflow: hidden; }
.bar { height: 100%; background: #d4aa48; }

/* 自我评价框 */
.eval-box { border: 1px solid #aaa; padding: 8px; border-radius: 4px; font-size: 12.5px; line-height: 1.5; }

/* 装饰星星 */
.star { position: absolute; color: #ffb300; z-index: 2; font-size: 16px; }
.star1 { top: 12px; right: 220px; }
.star2 { top: 30px; right: 80px; color: #ff7043; }

/* 打印：强制输出背景色（进度条/序号标签/色块），允许内容跨页自然流动 */
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
    /* @page margin 为 0，页边距由容器内边距承担 */
    padding: 12mm 14mm;
  }
  /* 章节与条目尽量避免跨页截断 */
  .section, .entry, .eval-box, .skill-item {
    break-inside: avoid;
  }
}
</style>
