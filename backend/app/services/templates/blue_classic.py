"""蓝色经典简历模板。

源自「jianli-0046 蓝色好看的简历模板」，尽量还原原版设计：
- 页首/页尾通栏蓝色装饰条（#254665，通过页眉页脚实现，固定在页面上下边缘）
- 每个板块：蓝色菱形 + 「中文（English）」标题（微软雅黑加粗 13pt #254665）+ 蓝色下边框
- 首屏为「个人信息（Personal Info）」双栏字段网格（原版姓名/电话/邮箱/住址/求职目标等字段式排布）
- 正文统一微软雅黑 10.5pt #5B5B5B；条目头一行加粗：时间 + 公司/学校 + 职位/专业
渲染签名与数据约定遵循 docs/模板开发规范.md。
"""
from pathlib import Path

from docx.enum.text import WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from ..resume_generator import (
    _EMPH_RE,
    _add_para,
    _border,
    _enabled,
    _merge_sections,
    _new_doc,
    _no_table_borders,
    _proficiency_level,
    _save_docx,
    _set_run,
    _skill_bar,
)
from ..prompting import get_length_budget

# 原版配色：标题/装饰深蓝 #254665，正文灰蓝 #5B5B5B；高亮仍用项目约定的强调蓝
BLUE = RGBColor(0x25, 0x46, 0x65)
BODY = RGBColor(0x5B, 0x5B, 0x5B)
ACCENT = RGBColor(0x1F, 0x6F, 0xB2)

_BAR_HEX = "254665"


def _mr(run, size=10, bold=False, color=BODY, italic=False):
    """微软雅黑 run（中英文统一雅黑，贴合原版）。"""
    _set_run(run, size=size, bold=bold, color=color, italic=italic)
    run.font.name = "微软雅黑"
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.get_or_add_rFonts()
    rfonts.set(qn("w:ascii"), "微软雅黑")
    rfonts.set(qn("w:hAnsi"), "微软雅黑")


def _rich(p, text, size=10, color=BODY, bold=False):
    """渲染 **重点** 标记为强调蓝加粗，其余为正文色。"""
    for seg in _EMPH_RE.split(text or ""):
        if not seg:
            continue
        if seg.startswith("**") and seg.endswith("**") and len(seg) > 4:
            r = p.add_run(seg[2:-2])
            _mr(r, size=size, bold=True, color=ACCENT)
        else:
            r = p.add_run(seg)
            _mr(r, size=size, bold=bold, color=color)


def _blue_bar(p, height_cm, bleed_cm=1.8):
    """把段落变成通栏蓝色实条（底纹 + 负缩进出血到页面边缘 + 固定行高）。"""
    pf = p.paragraph_format
    pf.space_before = Pt(0)
    pf.space_after = Pt(0)
    pf.line_spacing = Cm(height_cm)
    ppr = p._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), _BAR_HEX)
    ppr.append(shd)
    ind = OxmlElement("w:ind")
    tw = str(int(bleed_cm * 567))  # 1cm ≈ 567 twips
    ind.set(qn("w:left"), f"-{tw}")
    ind.set(qn("w:right"), f"-{tw}")
    ppr.append(ind)


def _title(container, zh, en):
    """板块标题：◆ 中文（English），蓝色加粗 + 蓝色下边框。"""
    p = _add_para(container)
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(3)
    r = p.add_run("◆ ")
    _mr(r, size=9.5, bold=True, color=BLUE)
    r = p.add_run(f"{zh}（{en}）")
    _mr(r, size=12, bold=True, color=BLUE)
    _border(p, color=_BAR_HEX, sz="6", side="bottom", space="2")
    return p


def _entry_head(container, time, mid, right, tab_mid=6.0, tab_right=17.4):
    """加粗一行：时间  公司/学校  职位/专业（原版顺序：时间在前，职位靠右）。"""
    p = _add_para(container)
    p.paragraph_format.space_after = Pt(2)
    pf = p.paragraph_format
    if right:
        pf.tab_stops.add_tab_stop(Cm(tab_mid), WD_TAB_ALIGNMENT.LEFT)
        pf.tab_stops.add_tab_stop(Cm(tab_right), WD_TAB_ALIGNMENT.RIGHT)
    elif mid:
        pf.tab_stops.add_tab_stop(Cm(tab_mid), WD_TAB_ALIGNMENT.LEFT)
    if time:
        r = p.add_run(time)
        _mr(r, size=10, bold=True, color=BODY)
    if mid:
        r = p.add_run("\t" + mid if time else mid)
        _mr(r, size=10, bold=True, color=BODY)
    if right:
        r = p.add_run("\t" + right)
        _mr(r, size=10, bold=True, color=BODY)
    return p


def _item(container, text, size=10):
    """正文圆点条目（支持 ** 高亮）。"""
    p = _add_para(container)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.left_indent = Cm(0.4)
    r = p.add_run("· ")
    _mr(r, size=size, bold=True, color=BLUE)
    _rich(p, text, size=size)
    return p


def _labeled(container, label, text, size=10):
    """「标签  正文」一行，如主修课程/技术栈。"""
    p = _add_para(container)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.left_indent = Cm(0.4)
    r = p.add_run(label + "  ")
    _mr(r, size=size, bold=True, color=BLUE)
    _rich(p, text, size=size)
    return p


def _skill_cell(p, name, proficiency):
    """技能条目：名称 + 图形化进度条（主题蓝）+ 熟练度描述词。"""
    level = _proficiency_level(proficiency)
    r = p.add_run(name)
    _mr(r, size=9.5, bold=True, color=BODY)
    r = p.add_run(" ")
    _mr(r, size=9)
    _skill_bar(p, level, fill="254665", bg="DCE4EC")
    if proficiency:
        r = p.add_run(" " + proficiency)
        _mr(r, size=8.5, color=BODY)


def _cell_width(name, proficiency):
    w = sum(1.0 if ord(ch) > 127 else 0.55 for ch in (name or ""))
    w += 9.0  # 图形化进度条固定宽 3.0cm
    if proficiency:
        w += len(proficiency) * 1.0
    return w


_SKILL_TAB = Cm(8.8)
_SKILL_HALF = 24.0


def _skill_row(container, skills):
    """技能排版：空间允许时每行并列两个（制表位对齐），过长独占一行。"""
    i = 0
    n = len(skills)
    while i < n:
        name, prof = skills[i]
        if (i + 1 < n and _cell_width(name, prof) <= _SKILL_HALF
                and _cell_width(*skills[i + 1]) <= _SKILL_HALF):
            pair = [skills[i], skills[i + 1]]
            i += 2
        else:
            pair = [skills[i]]
            i += 1
        p = _add_para(container)
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.left_indent = Cm(0.4)
        p.paragraph_format.tab_stops.add_tab_stop(_SKILL_TAB, WD_TAB_ALIGNMENT.LEFT)
        _skill_cell(p, pair[0][0], pair[0][1])
        if len(pair) == 2:
            r = p.add_run("\t")
            _mr(r, size=9)
            _skill_cell(p, pair[1][0], pair[1][1])


def _field_line(cell, label, value):
    """个人信息字段行：标签（全角空格补齐）+ 全角冒号 + 值。"""
    p = _add_para(cell)
    p.paragraph_format.space_after = Pt(4)
    if len(label) == 2:
        label = label[0] + "　　" + label[1]
    r = p.add_run(label + "：")
    _mr(r, size=10, color=BODY)
    r2 = p.add_run(value)
    _mr(r2, size=10, color=BODY)


def render(user, jd_summary, personal_summary, self_evaluation, out_dir: Path,
           target_position="", sections=None, fabricated=None,
           skills_curated=None, expected_salary="", include_salary=True,
           length="fresh", custom_pages=None) -> str:
    def enabled(key: str) -> bool:
        return _enabled(sections, key)

    budget = get_length_budget(length, custom_pages)
    projects, internships, works, others = _merge_sections(
        user, fabricated, limit=budget["max_experiences"])
    doc = _new_doc()

    # ===== 页首/页尾蓝色通栏条（页眉页脚固定，仿原版上下蓝条）=====
    sec = doc.sections[0]
    sec.top_margin = Cm(1.6)
    sec.bottom_margin = Cm(1.5)
    sec.header_distance = Cm(0.55)
    sec.footer_distance = Cm(0.4)
    header = sec.header
    header.is_linked_to_previous = False
    _blue_bar(header.paragraphs[0], 0.7)
    footer = sec.footer
    footer.is_linked_to_previous = False
    _blue_bar(footer.paragraphs[0], 0.6)

    pos = target_position or user.target_position or jd_summary.get("position") or "软件工程师"

    # ===== 个人信息（Personal Info）：双栏字段网格 =====
    _title(doc, "个人信息", "Personal Info")
    fields = [
        ("姓名", user.name or ""),
        ("电话", user.phone or ""),
        ("邮箱", user.email or ""),
        ("住址", user.location or ""),
        ("求职目标", pos),
    ]
    if include_salary and expected_salary:
        fields.append(("期望薪资", expected_salary))
    fields = [(k, v) for k, v in fields if v]
    if fields:
        half = (len(fields) + 1) // 2
        table = doc.add_table(rows=1, cols=2)
        table.autofit = False
        _no_table_borders(table)
        left_cell, right_cell = table.cell(0, 0), table.cell(0, 1)
        left_cell.width = Cm(8.7)
        right_cell.width = Cm(8.7)
        for k, v in fields[:half]:
            _field_line(left_cell, k, v)
        for k, v in fields[half:]:
            _field_line(right_cell, k, v)

    # 个人简介
    if enabled("summary") and personal_summary:
        _title(doc, "个人简介", "Personal Summary")
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(2)
        _rich(p, personal_summary, size=10)

    # 教育背景
    if enabled("education") and user.educations:
        _title(doc, "教育背景", "Education")
        for edu in user.educations:
            time = f"{edu.start_date} - {edu.end_date}".strip(" -")
            degree = " ".join(x for x in (edu.major, f"（{edu.degree}）" if edu.degree else "") if x)
            _entry_head(doc, time, edu.school, degree)
            if edu.courses:
                _labeled(doc, "主修课程", edu.courses, size=10)
            extra = " · ".join(x for x in (f"GPA {edu.gpa}" if edu.gpa else "",
                                           f"排名 {edu.rank}" if edu.rank else "") if x)
            if extra:
                _item(doc, extra, size=10)

    # 专业技能（进度条 + 熟练度描述词，空间允许时一行两个）
    if enabled("skills") and (skills_curated or user.skills):
        _title(doc, "专业技能", "Professional Skills")
        if skills_curated:
            items = [
                (s.get("name", "") if isinstance(s, dict) else s.name,
                 s.get("proficiency", "") if isinstance(s, dict) else s.proficiency)
                for s in skills_curated
            ]
            _skill_row(doc, items)
        else:
            grouped = {}
            for s in user.skills:
                grouped.setdefault(s.category or "其他", []).append(s)
            for cat, sks in grouped.items():
                p = doc.add_paragraph()
                p.paragraph_format.space_after = Pt(1)
                p.paragraph_format.left_indent = Cm(0.4)
                r = p.add_run(cat + "  ")
                _mr(r, size=10, bold=True, color=BLUE)
                _skill_row(doc, [(s.name, s.proficiency) for s in sks])

    # 实习经历
    if enabled("internships") and internships:
        _title(doc, "实习经历", "Internship")
        for it in internships:
            time = f"{it.start_date} - {it.end_date}".strip(" -")
            _entry_head(doc, time, it.company, it.position)
            if it.description:
                _item(doc, it.description)
            if it.achievement:
                _item(doc, it.achievement)

    # 工作经历（杜撰）
    if enabled("work") and works:
        _title(doc, "工作经历", "Work Experience")
        for it in works:
            time = f"{it.start_date} - {it.end_date}".strip(" -")
            _entry_head(doc, time, it.company, it.position)
            if it.description:
                _item(doc, it.description)
            if it.achievement:
                _item(doc, it.achievement)

    # 其他经历（杜撰）
    if enabled("other") and others:
        _title(doc, "其他经历", "Other Experience")
        for it in others:
            time = f"{it.start_date} - {it.end_date}".strip(" -")
            _entry_head(doc, time, it.company, it.position)
            if it.description:
                _item(doc, it.description)
            if it.achievement:
                _item(doc, it.achievement)

    # 项目经历
    if enabled("projects") and projects:
        _title(doc, "项目经历", "Project Experience")
        for proj in projects:
            time = f"{proj.start_date} - {proj.end_date}".strip(" -")
            _entry_head(doc, time, proj.title, getattr(proj, "role", ""))
            if proj.tech_stack:
                _labeled(doc, "技术栈", proj.tech_stack, size=10)
            if proj.description:
                _item(doc, proj.description)
            if proj.result:
                _item(doc, proj.result)

    # 证书 / 获奖
    if enabled("certificates") and user.certificates:
        _title(doc, "证书/获奖", "Certificates")
        for c in user.certificates:
            text = c.name + (f"（{c.date}）" if c.date else "")
            _item(doc, text)

    # 自我评价（置于简历最下方）
    if enabled("self_evaluation") and self_evaluation:
        _title(doc, "自我评价", "Self-assessment")
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(2)
        _rich(p, self_evaluation, size=10)

    return _save_docx(doc, user, out_dir, target_position)


# 供 resume_generator.py 登记：key 为模板唯一标识，label 用于前端展示
TEMPLATE = {
    "blue_classic": {"label": "蓝色经典", "render": render},
}