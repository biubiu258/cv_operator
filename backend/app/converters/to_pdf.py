"""Word -> PDF 转换（可插拔）。"""
import shutil
import subprocess
import traceback
from pathlib import Path


def convert_docx_to_pdf(docx_path: str) -> str:
    """将 .docx 转为同目录 .pdf，返回 pdf 路径。"""
    src = Path(docx_path)
    if not src.exists():
        raise FileNotFoundError(f"文件不存在：{src}")
    out_dir = src.parent

    # 1) LibreOffice headless（跨平台，优先）
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if soffice:
        subprocess.run(
            [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(out_dir), str(src)],
            check=True, capture_output=True, timeout=180,
        )
        pdf = src.with_suffix(".pdf")
        if pdf.exists():
            return str(pdf)

    # 2) Windows Word COM（docx2pdf，需安装 Word）
    try:
        from docx2pdf import convert  # type: ignore
        convert(str(src), str(src.with_suffix(".pdf")))
        pdf = src.with_suffix(".pdf")
        if pdf.exists():
            return str(pdf)
    except Exception:
        traceback.print_exc()

    raise RuntimeError("PDF 转换失败：请安装 LibreOffice，或（Windows）安装 docx2pdf / Microsoft Word。")