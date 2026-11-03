"""求职信 docx 渲染：纯函数式，输入文本 + 用户信息 → A4 Word 文件。"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Pt


def _set_font(run, font_name: str = "微软雅黑", size: int = 11, bold: bool = False) -> None:
    run.font.size = Pt(size)
    run.font.bold = bold
    # 中文字体：微软雅黑；西文字体：Calibri
    run.font.name = "Calibri"
    r = run._element
    rPr = r.find(qn("w:rPr"))
    if rPr is None:
        rPr = r.makeelement(qn("w:rPr"), {})
        r.insert(0, rPr)
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = rPr.makeelement(qn("w:rFonts"), {})
        rPr.insert(0, rFonts)
    rFonts.set(qn("w:eastAsia"), font_name)


def render_cover_letter(
    content: str,
    name: str = "",
    email: str = "",
    phone: str = "",
    location: str = "",
    target_position: str = "",
    out_dir: Path | None = None,
) -> str:
    """渲染一封 A4 求职信并返回生成的 docx 绝对路径。

    版式：
    - 页面：A4，上下边距 2.54cm，左右 2.5cm（接近 Word 默认）
    - 顶部：姓名（14pt 加粗居中） + 联系方式（10.5pt 居中）
    - 正文标题：求职信 + 目标岗位（12pt 加粗左对齐）
    - 正文：11pt，行距 1.5，首行缩进 2 字符
    - 日期：页底右对齐
    """
    doc = Document()

    # --- 页面设置 ---
    section = doc.sections[0]
    section.page_width = Cm(21.0)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(2.54)
    section.bottom_margin = Cm(2.54)
    section.left_margin = Cm(2.5)
    section.right_margin = Cm(2.5)

    # --- 姓名 ---
    if name:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(2)
        run = p.add_run(name)
        _set_font(run, size=14, bold=True)

    # --- 联系方式 ---
    contact_parts = [x for x in (location, phone, email) if x]
    if contact_parts:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(12)
        run = p.add_run("  |  ".join(contact_parts))
        _set_font(run, size=10.5)

    # --- 标题 ---
    title_text = f"求职信：{target_position}" if target_position else "求职信"
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(12)
    run = p.add_run(title_text)
    _set_font(run, size=12, bold=True)

    # --- 正文（按换行符分段）---
    for line in str(content or "").split("\n"):
        line = line.strip()
        if not line:
            continue
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p.paragraph_format.line_spacing = 1.5
        p.paragraph_format.first_line_indent = Cm(0.74)  # 约 2 个 11pt 中文字符
        p.paragraph_format.space_after = Pt(6)
        run = p.add_run(line)
        _set_font(run, size=11)

    # --- 日期 ---
    today = datetime.now().strftime("%Y 年 %m 月 %d 日")
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p.paragraph_format.space_before = Pt(18)
    run = p.add_run(today)
    _set_font(run, size=10.5)

    # --- 保存 ---
    out_dir = Path(out_dir) if out_dir else Path.cwd()
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = f"cover_letter_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
    out_path = out_dir / fname
    doc.save(str(out_path))
    return str(out_path)
