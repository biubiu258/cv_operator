"""简历：必要问题生成 + 个人简介 + .docx 生成。"""
import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from . import llm_client

PRIMARY = RGBColor(0x1F, 0x4E, 0x79)
_SYSTEM = "你是一名资深技术招聘与简历专家。"


# ---------- AI 生成部分 ----------
async def generate_resume_questions(
    jd_summary: dict,
    user_profile: dict,
    base_url: str,
    api_key: str,
    model: str,
) -> list:
    prompt = (
        "请结合岗位 JD 与求职者现有档案，判断简历中还缺失或不确定的信息，"
        "设计 3~5 个必要问题（用于补齐定向简历所需关键素材）。\n"
        "只返回 JSON 数组（不要 markdown 代码块），每项结构：\n"
        '{"id":"q1","type":"choice|multi|text","question":"问题内容","options":["选项"],"required":true}\n\n'
        f"JD 解析结果：{json.dumps(jd_summary, ensure_ascii=False)}\n"
        f"求职者档案：{json.dumps(user_profile, ensure_ascii=False)}\n\n"
        "问题应聚焦：意向岗位确认、项目真实性与量化数据、JD 匹配的技术点等。"
    )
    raw = await llm_client.chat(
        base_url, api_key, model,
        [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": prompt}],
        temperature=0.4, json_mode=True,
    )
    return _parse_questions(raw)


def _parse_questions(raw: str) -> list:
    try:
        data = json.loads(raw)
    except Exception:
        return []
    if isinstance(data, dict):
        data = data.get("questions") or data.get("data") or []
    if not isinstance(data, list):
        return []
    out = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            continue
        out.append({
            "id": str(item.get("id") or f"q{i + 1}"),
            "type": item.get("type") or "text",
            "question": item.get("question") or "",
            "options": item.get("options") or [],
            "required": bool(item.get("required", True)),
        })
    return out


async def generate_personal_summary(
    jd_summary: dict,
    user_profile: dict,
    base_url: str,
    api_key: str,
    model: str,
) -> str:
    prompt = (
        "请为求职者写一段 2~3 行的个人简介（电梯陈述），3 秒讲清「我是谁 + 为什么匹配该岗位」，"
        "包含技术栈速览。要求口语化、简洁、有针对性。\n\n"
        f"JD 解析结果：{json.dumps(jd_summary, ensure_ascii=False)}\n"
        f"求职者档案：{json.dumps(user_profile, ensure_ascii=False)}\n\n"
        "只输出简介正文，不要标题。"
    )
    return await llm_client.chat(
        base_url, api_key, model,
        [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": prompt}],
        temperature=0.6,
    )


# ---------- DOCX 构建 ----------
def _set_run(run, size=10.5, bold=False, color=None):
    run.font.name = "Arial"
    run.font.size = Pt(size)
    run.font.bold = bold
    if color is not None:
        run.font.color.rgb = color
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.get_or_add_rFonts()
    rfonts.set(qn("w:eastAsia"), "Microsoft YaHei")


def _bottom_border(p):
    ppr = p._p.get_or_add_pPr()
    pbdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "6")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "1F4E79")
    pbdr.append(bottom)
    ppr.append(pbdr)


def _heading(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(3)
    r = p.add_run(text)
    _set_run(r, size=11, bold=True, color=PRIMARY)
    _bottom_border(p)
    return p


def _line_with_time(doc, left, right, left_bold=False):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(1)
    p.paragraph_format.tab_stops.add_tab_stop(Cm(17.3), WD_TAB_ALIGNMENT.RIGHT)
    r = p.add_run(left)
    _set_run(r, size=10.5, bold=left_bold)
    r2 = p.add_run("\t" + right)
    _set_run(r2, size=9.5)
    return p


def _bullet(doc, text, size=10):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(1)
    p.paragraph_format.left_indent = Cm(0.4)
    r = p.add_run("· " + text)
    _set_run(r, size=size)
    return p


def build_resume_docx(user, jd_summary, personal_summary, self_evaluation, out_dir: Path,
                      target_position: str = "", sections=None, fabricated=None) -> str:
    # sections 为空/None 表示包含全部模块；否则仅包含勾选模块
    def enabled(key: str) -> bool:
        return not sections or key in sections

    # 合并杜撰经历（若有）到项目/实习列表
    fake_projects = [SimpleNamespace(**x) for x in (fabricated or []) if x.get("type") == "project"]
    fake_internships = [
        SimpleNamespace(
            company=x.get("title", ""), position=x.get("role", ""),
            start_date=x.get("start_date", ""), end_date=x.get("end_date", ""),
            description=x.get("description", ""), achievement=x.get("result", ""),
        )
        for x in (fabricated or []) if x.get("type") == "internship"
    ]
    projects = list(user.projects) + fake_projects
    internships = list(user.internships) + fake_internships

    doc = Document()
    section = doc.sections[0]
    section.page_width = Cm(21)
    section.page_height = Cm(29.7)
    section.left_margin = Cm(1.8)
    section.right_margin = Cm(1.8)
    section.top_margin = Cm(1.5)
    section.bottom_margin = Cm(1.5)

    # 姓名
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(user.name or "姓名")
    _set_run(r, size=18, bold=True, color=PRIMARY)

    # 目标岗位（定向简历填写 > 基本信息 > JD 解析 > 兜底）
    pos = target_position or user.target_position or jd_summary.get("position") or "软件工程师"
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(pos)
    _set_run(r, size=12)

    # 联系方式
    contact = " · ".join(x for x in (user.phone, user.email, user.location) if x)
    if contact:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(contact)
        _set_run(r, size=9)

    # 个人简介
    if enabled("summary") and personal_summary:
        _heading(doc, "个人简介")
        p = doc.add_paragraph()
        r = p.add_run(personal_summary)
        _set_run(r, size=10)

    # 教育背景
    if enabled("education") and user.educations:
        _heading(doc, "教育背景")
        for edu in user.educations:
            title = " | ".join(x for x in (edu.school, edu.major, edu.degree) if x)
            time = f"{edu.start_date} - {edu.end_date}".strip(" -")
            _line_with_time(doc, title, time, left_bold=True)
            if edu.courses:
                _bullet(doc, "主修课程：" + edu.courses, size=9)
            extra = " · ".join(x for x in (f"GPA {edu.gpa}" if edu.gpa else "", f"排名 {edu.rank}" if edu.rank else "") if x)
            if extra:
                _bullet(doc, extra, size=9)

    # 实习经历
    if enabled("internships") and internships:
        _heading(doc, "实习经历")
        for it in internships:
            title = " | ".join(x for x in (it.company, it.position) if x)
            time = f"{it.start_date} - {it.end_date}".strip(" -")
            _line_with_time(doc, title, time, left_bold=True)
            if it.description:
                _bullet(doc, it.description)
            if it.achievement:
                _bullet(doc, it.achievement)

    # 专业技能
    if enabled("skills") and user.skills:
        _heading(doc, "专业技能")
        grouped = {}
        for s in user.skills:
            grouped.setdefault(s.category, []).append(s)
        for cat, items in grouped.items():
            text = "、".join(f"{s.name}（{s.proficiency}）" if s.proficiency else s.name for s in items)
            _bullet(doc, f"{cat}：{text}")

    # 项目经历
    if enabled("projects") and projects:
        _heading(doc, "项目经历")
        for proj in projects:
            time = f"{proj.start_date} - {proj.end_date}".strip(" -")
            _line_with_time(doc, proj.title, time, left_bold=True)
            if proj.tech_stack:
                _bullet(doc, "技术栈：" + proj.tech_stack, size=9.5)
            if proj.description:
                _bullet(doc, proj.description)
            if proj.result:
                _bullet(doc, proj.result)

    # 证书 / 获奖
    if enabled("certificates") and user.certificates:
        _heading(doc, "证书 / 获奖")
        for c in user.certificates:
            text = c.name + (f"（{c.date}）" if c.date else "")
            _bullet(doc, text)

    # 自我评价（放在简历最下面一栏）
    if enabled("self_evaluation") and self_evaluation:
        _heading(doc, "自我评价")
        p = doc.add_paragraph()
        r = p.add_run(self_evaluation)
        _set_run(r, size=10)

    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"resume_{user.id}_{stamp}.docx"
    out_path = out_dir / fname
    doc.save(str(out_path))
    return str(out_path)