/**
 * 网页版简历模板共享渲染逻辑。
 * 两个 Vue 模板（WarmTemplate / NavyTemplate）共用的数据加工函数，
 * 规则与后端保持一致：
 * - segs: **强调** 标记拆分（对应 docx 的 _add_rich_runs）
 * - profPct: 熟练度描述词 → 进度条百分比（对应 _PROF_LEVEL）
 * - parseYM / sortByTimeDesc / mergeExperiences: 时间解析与新→旧排序（对应 _parse_ym / _merge_sections）
 */
import { fileUrl } from '@/api'

// **强调** 标记拆分
export function segs(text) {
  return (text || '').split(/(\*\*.+?\*\*)/).filter(Boolean).map((s) =>
    s.startsWith('**') && s.endsWith('**') && s.length > 4
      ? { t: s.slice(2, -2), em: true }
      : { t: s, em: false })
}

// 熟练度描述词 → 进度条百分比（与后端 _PROF_LEVEL 一致）
const PROF_LEVEL = { '熟练': 90, '精通': 95, '掌握': 80, '熟悉': 70, '了解': 50 }
export const profPct = (label) => PROF_LEVEL[(label || '').trim()] ?? 60

// 时间解析：'2024.09' / '2024-9' / '至今' → [年, 月]；空为 [0,0]，至今为极大值
export function parseYM(v) {
  v = (v || '').trim()
  if (!v) return [0, 0]
  if (v === '至今' || v === '现在' || ['now', 'present'].includes(v.toLowerCase())) return [9999, 12]
  const m = v.match(/(\d{4})\D?(\d{1,2})?/)
  if (!m) return [0, 0]
  const mo = m[2] ? parseInt(m[2], 10) : 0
  return [parseInt(m[1], 10), mo >= 1 && mo <= 12 ? mo : 0]
}

// 按结束时间新→旧排序；无结束时间时用开始时间
export function sortByTimeDesc(list) {
  return [...list].sort((a, b) => {
    const ea = parseYM(a.end_date); const ka = (ea[0] || ea[1]) ? ea : parseYM(a.start_date)
    const eb = parseYM(b.end_date); const kb = (eb[0] || eb[1]) ? eb : parseYM(b.start_date)
    return kb[0] - ka[0] || kb[1] - ka[1]
  })
}

// 合并经历（与后端 _merge_sections 一致）：
// 润色稿（polished_experiences）替代同类型档案原文，杜撰经历追加，按时间排序并按篇幅预算裁剪
// 排序策略：默认按时间新→旧自动排；manual_order 标记时尊重数组顺序（用户手动保存过排序）
// 经历选择：polish_selection 非空时只展示用户勾选并润色过的经历，未勾选的档案经历不展示
export function mergeExperiences(ctx) {
  const limit = ctx.budget?.max_experiences || 0
  const user = ctx.user || {}
  const fabricated = ctx.fabricated || []
  const polished = ctx.polished_experiences || []
  const mOrder = ctx.manual_order || {}
  const userSortedFab = !!mOrder.fabricated
  const userSortedPol = !!mOrder.polished_experiences
  const fakeOf = (t) => fabricated.filter((x) => x.type === t)
  const polOf = (t) => polished.filter((x) => x.type === t)
  const asExp = (x) => ({
    company: x.title || '', position: x.role || '',
    start_date: x.start_date || '', end_date: x.end_date || '',
    description: x.description || '', achievement: x.result || '',
  })
  const fakeExp = (t) => fakeOf(t).map(asExp)
  const clip = (list) => (limit ? list.slice(0, limit) : list)
  const polProjects = polOf('project')
  const polInternships = polOf('internship').map(asExp)
  const selectionActive = (ctx.polish_selection || []).length > 0
  const baseProj = selectionActive ? polProjects : (polProjects.length ? polProjects : (user.projects || []))
  const baseIntern = selectionActive ? polInternships : (polInternships.length ? polInternships : (user.internships || []))
  const fakeProj = fakeOf('project')
  const fakeIntern = fakeExp('internship')
  const fakeWorks = fakeExp('work')
  const fakeOthers = fakeExp('other')
  let projects = baseProj.concat(fakeProj)
  let internships = baseIntern.concat(fakeIntern)
  let works = fakeWorks
  let others = fakeOthers
  // 与后端 _merge_sections 排序策略完全对齐
  if (!(userSortedPol || (userSortedFab && !baseProj))) {
    projects = sortByTimeDesc(projects)
  }
  if (!(userSortedPol || (userSortedFab && !baseIntern))) {
    internships = sortByTimeDesc(internships)
  }
  if (!(userSortedFab && fakeWorks.length) && fakeWorks.length) works = sortByTimeDesc(works)
  if (!(userSortedFab && fakeOthers.length) && fakeOthers.length) others = sortByTimeDesc(others)
  return {
    projects: clip(projects),
    internships: clip(internships),
    works: clip(works),
    others: clip(others),
  }
}

// 技能分组：优先使用整理后的 skills_curated，否则按档案技能的 category 分组
export function skillGroupsOf(ctx) {
  const user = ctx.user || {}
  if ((ctx.skills_curated || []).length) {
    return [{ cat: '专业技能', items: ctx.skills_curated }]
  }
  const grouped = {}
  for (const s of user.skills || []) {
    ;(grouped[s.category || '其他'] = grouped[s.category || '其他'] || []).push(s)
  }
  return Object.entries(grouped).map(([cat, items]) => ({ cat, items }))
}

// 板块勾选：空表示全部包含；basics（基本信息/姓名电话等）是必填固定板块，永远显示（与后端 docx 模板行为一致）
export const isEnabled = (ctx, key) =>
  key === 'basics' || !ctx.sections?.length || ctx.sections.includes(key)

// 时间范围文本
export const timeRange = (x) =>
  `${x.start_date || ''} - ${x.end_date || ''}`.replace(/^ - | - $/g, '')

// 求职意向：定向填写 > 档案值 > JD 解析 > 兜底
export const positionOf = (ctx) =>
  ctx.target_position || ctx.user?.target_position
  || ctx.jd_summary?.position || '软件工程师'

// 头像完整地址；无头像返回占位图（扁平人物剪影）
export function avatarSrcOf(user) {
  const own = fileUrl(user?.avatar)
  if (own) return own
  return `https://api.dicebear.com/7.x/avataaars/svg?seed=${encodeURIComponent(user?.name || 'admin')}`
}
