"""定向简历路由：创建 → 解析 JD → 必要问题 → 作答 → 生成 docx → 下载/转 PDF。"""
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .. import models, schemas
from ..config import OUTPUT_DIR
from ..converters import to_pdf
from ..database import get_db
from ..deps import ensure_llm_ready, get_active_user
from ..services import jd_parser, profile as profile_svc
from ..services import fabricate as fabricate_svc
from ..services import resume_generator, self_evaluation as se_svc

router = APIRouter(tags=["resumes"])

_MT_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _ensure_resume(db: Session, resume_id: int):
    r = db.get(models.Resume, resume_id)
    if not r:
        raise HTTPException(status_code=404, detail="简历任务不存在")
    return r


@router.post("/resumes", response_model=schemas.ResumeOut)
def create_resume(data: schemas.ResumeCreate, db: Session = Depends(get_db)):
    user = get_active_user(db)
    resume = models.Resume(
        user_id=user.id,
        jd_text=data.jd_text,
        target_position=data.target_position,
        sections=data.sections,
        status="draft",
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)
    return resume


@router.get("/resumes", response_model=list[schemas.ResumeOut])
def list_resumes(db: Session = Depends(get_db)):
    return db.query(models.Resume).order_by(models.Resume.id.desc()).all()


@router.get("/resumes/{resume_id}", response_model=schemas.ResumeOut)
def get_resume(resume_id: int, db: Session = Depends(get_db)):
    return _ensure_resume(db, resume_id)


@router.post("/resumes/{resume_id}/parse", response_model=schemas.ResumeOut)
async def parse_jd(resume_id: int, db: Session = Depends(get_db)):
    ctx = ensure_llm_ready(db)
    resume = _ensure_resume(db, resume_id)
    summary = await jd_parser.parse_jd(
        resume.jd_text, ctx["base_url"], ctx["api_key"], ctx["model"])
    resume.jd_summary = summary
    resume.status = "parsed"
    db.commit()
    db.refresh(resume)
    return resume


@router.post("/resumes/{resume_id}/fabricate", response_model=schemas.ResumeOut)
async def fabricate(resume_id: int, data: schemas.FabricateIn, db: Session = Depends(get_db)):
    ctx = ensure_llm_ready(db)
    resume = _ensure_resume(db, resume_id)
    if not resume.jd_summary:
        resume.jd_summary = await jd_parser.parse_jd(
            resume.jd_text, ctx["base_url"], ctx["api_key"], ctx["model"])
    prof = profile_svc.user_profile_dict(resume.user)
    fabricated = []
    if data.fabricate:
        fabricated = await fabricate_svc.fabricate_experiences(
            resume.jd_summary, prof, ctx["base_url"], ctx["api_key"], ctx["model"])
    resume.fabricated = fabricated
    resume.interview_prep = await fabricate_svc.generate_interview_prep(
        resume.jd_summary, prof, fabricated, ctx["base_url"], ctx["api_key"], ctx["model"])
    db.commit()
    db.refresh(resume)
    return resume


@router.post("/resumes/{resume_id}/questions")
async def gen_questions(resume_id: int, db: Session = Depends(get_db)):
    ctx = ensure_llm_ready(db)
    resume = _ensure_resume(db, resume_id)
    if not resume.jd_summary:
        resume.jd_summary = await jd_parser.parse_jd(
            resume.jd_text, ctx["base_url"], ctx["api_key"], ctx["model"])
    questions = await resume_generator.generate_resume_questions(
        resume.jd_summary, profile_svc.user_profile_dict(resume.user),
        ctx["base_url"], ctx["api_key"], ctx["model"])
    resume.questions = questions
    resume.status = "questioning"
    db.commit()
    db.refresh(resume)
    return {"questions": questions}


@router.post("/resumes/{resume_id}/answers", response_model=schemas.ResumeOut)
def submit_answers(resume_id: int, data: schemas.AnswersIn, db: Session = Depends(get_db)):
    resume = _ensure_resume(db, resume_id)
    resume.answers = [a.model_dump() for a in data.answers]
    resume.status = "answered"
    db.commit()
    db.refresh(resume)
    return resume


@router.post("/resumes/{resume_id}/generate", response_model=schemas.ResumeOut)
async def generate(resume_id: int, db: Session = Depends(get_db)):
    ctx = ensure_llm_ready(db)
    resume = _ensure_resume(db, resume_id)
    if not resume.jd_summary:
        resume.jd_summary = await jd_parser.parse_jd(
            resume.jd_text, ctx["base_url"], ctx["api_key"], ctx["model"])

    user = resume.user
    prof = profile_svc.user_profile_dict(user)

    resume.personal_summary = await resume_generator.generate_personal_summary(
        resume.jd_summary, prof, ctx["base_url"], ctx["api_key"], ctx["model"])

    if not resume.self_evaluation:
        resume.self_evaluation = await se_svc.generate_self_evaluation(
            resume.jd_summary, prof, [], "",
            ctx["base_url"], ctx["api_key"], ctx["model"])

    out_path = resume_generator.build_resume_docx(
        user, resume.jd_summary, resume.personal_summary, resume.self_evaluation, OUTPUT_DIR,
        target_position=resume.target_position, sections=resume.sections,
        fabricated=resume.fabricated)
    resume.output_path = out_path
    resume.status = "generated"
    db.commit()
    db.refresh(resume)
    return resume


@router.post("/resumes/{resume_id}/convert")
def convert_pdf(resume_id: int, db: Session = Depends(get_db)):
    resume = _ensure_resume(db, resume_id)
    if not resume.output_path:
        raise HTTPException(status_code=400, detail="尚未生成简历文件")
    pdf_path = to_pdf.convert_docx_to_pdf(resume.output_path)
    return {"pdf_path": pdf_path}


@router.get("/resumes/{resume_id}/download")
def download(resume_id: int, format: str = "docx", db: Session = Depends(get_db)):
    resume = _ensure_resume(db, resume_id)
    if not resume.output_path:
        raise HTTPException(status_code=400, detail="尚未生成简历文件")
    if format == "pdf":
        pdf_path = to_pdf.convert_docx_to_pdf(resume.output_path)
        return FileResponse(pdf_path, filename=Path(pdf_path).name,
                            media_type="application/pdf")
    return FileResponse(resume.output_path, filename=Path(resume.output_path).name,
                        media_type=_MT_DOCX)