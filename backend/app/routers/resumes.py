"""定向简历路由：创建 → 解析 JD → 必要问题 → 作答 → 生成 docx → 下载/转 PDF。"""
import asyncio
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .. import models, schemas
from ..config import OUTPUT_DIR
from ..converters import to_pdf
from ..database import SessionLocal, get_db
from ..deps import ensure_llm_ready, get_active_user
from ..progress import broker
from ..services import jd_parser, profile as profile_svc
from ..services import fabricate as fabricate_svc
from ..services import resume_generator, self_evaluation as se_svc

router = APIRouter(tags=["resumes"])

_MT_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _set_progress(db: Session, resume, msg: str):
    resume.progress = msg
    db.commit()
    broker.publish(resume.id, msg)


def _ensure_resume(db: Session, resume_id: int):
    r = db.get(models.Resume, resume_id)
    if not r:
        raise HTTPException(status_code=404, detail="简历任务不存在")
    return r


def _build_docx_from_resume(db: Session, resume) -> str:
    """用已存内容（不含 LLM 调用）重建 docx 并写回 output_path。"""
    salary = resume.expected_salary or resume.user.expected_salary
    out_path = resume_generator.build_resume_docx(
        resume.user, resume.jd_summary, resume.personal_summary, resume.self_evaluation, OUTPUT_DIR,
        target_position=resume.target_position, sections=resume.sections,
        fabricated=resume.fabricated, skills_curated=resume.skills_curated,
        expected_salary=salary, include_salary=resume.include_salary,
        template=resume.template)
    resume.output_path = out_path
    return out_path


@router.post("/resumes", response_model=schemas.ResumeOut)
def create_resume(data: schemas.ResumeCreate, db: Session = Depends(get_db)):
    user = get_active_user(db)
    resume = models.Resume(
        user_id=user.id,
        jd_text=data.jd_text,
        target_position=data.target_position,
        expected_salary=data.expected_salary,
        include_salary=data.include_salary,
        sections=data.sections,
        template=data.template,
        status="draft",
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)
    return resume


@router.get("/resumes", response_model=list[schemas.ResumeOut])
def list_resumes(db: Session = Depends(get_db)):
    return db.query(models.Resume).order_by(models.Resume.id.desc()).all()


@router.get("/resumes/templates")
def list_templates():
    """返回简历模板库，供前端渲染选择器。"""
    return resume_generator.available_templates()


@router.get("/resumes/{resume_id}", response_model=schemas.ResumeOut)
def get_resume(resume_id: int, db: Session = Depends(get_db)):
    return _ensure_resume(db, resume_id)


@router.websocket("/ws/resumes/{resume_id}/progress")
async def ws_progress(websocket: WebSocket, resume_id: int):
    """向前端实时推送简历生成进度（替代 HTTP 轮询）。"""
    await websocket.accept()
    q = broker.subscribe(resume_id)
    db = SessionLocal()
    try:
        resume = db.get(models.Resume, resume_id)
        last = resume.progress if resume and resume.progress else ""
        await websocket.send_json({"progress": last})
        while True:
            try:
                msg = await asyncio.wait_for(q.get(), timeout=20.0)
                last = msg
            except asyncio.TimeoutError:
                # 空闲期发送心跳（复用最后进度值），同时探测客户端是否已断开
                msg = last
            await websocket.send_json({"progress": msg})
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        broker.unsubscribe(resume_id, q)
        db.close()


@router.post("/resumes/{resume_id}/parse", response_model=schemas.ResumeOut)
async def parse_jd(resume_id: int, db: Session = Depends(get_db)):
    ctx = ensure_llm_ready(db)
    resume = _ensure_resume(db, resume_id)
    _set_progress(db, resume, "正在解析岗位 JD…")
    summary = await jd_parser.parse_jd(
        resume.jd_text, ctx["base_url"], ctx["api_key"], ctx["model"])
    resume.jd_summary = summary
    resume.status = "parsed"
    resume.progress = ""
    db.commit()
    db.refresh(resume)
    return resume


@router.post("/resumes/{resume_id}/fabricate", response_model=schemas.ResumeOut)
async def fabricate(resume_id: int, data: schemas.FabricateIn, db: Session = Depends(get_db)):
    ctx = ensure_llm_ready(db)
    resume = _ensure_resume(db, resume_id)
    prof = profile_svc.user_profile_dict(resume.user)

    if not resume.jd_summary:
        _set_progress(db, resume, "正在解析岗位 JD…")
        resume.jd_summary = await jd_parser.parse_jd(
            resume.jd_text, ctx["base_url"], ctx["api_key"], ctx["model"])

    fabricated = []
    if data.fabricate:
        _set_progress(db, resume, "正在生成经历蓝本…")
        fabricated = await fabricate_svc.fabricate_experiences(
            resume.jd_summary, prof, ctx["base_url"], ctx["api_key"], ctx["model"],
            types=data.types, count=data.count, extra_jd=data.extra_jd)
    resume.fabricated = fabricated
    resume.progress = ""
    db.commit()
    db.refresh(resume)
    return resume


@router.post("/resumes/{resume_id}/fabricate/revise", response_model=schemas.ResumeOut)
async def revise_fabricate(resume_id: int, data: schemas.FabricateReviseIn,
                           db: Session = Depends(get_db)):
    """基于用户修改后的经历蓝本与意见，让 AI 重新调整。"""
    ctx = ensure_llm_ready(db)
    resume = _ensure_resume(db, resume_id)
    if not resume.jd_summary:
        _set_progress(db, resume, "正在解析岗位 JD…")
        resume.jd_summary = await jd_parser.parse_jd(
            resume.jd_text, ctx["base_url"], ctx["api_key"], ctx["model"])
    _set_progress(db, resume, "正在根据意见修改经历…")
    revised = await fabricate_svc.revise_experiences(
        resume.jd_summary, profile_svc.user_profile_dict(resume.user),
        data.experiences, data.feedback,
        ctx["base_url"], ctx["api_key"], ctx["model"])
    resume.fabricated = revised
    resume.progress = ""
    db.commit()
    db.refresh(resume)
    return resume


@router.post("/resumes/{resume_id}/fabricate/confirm", response_model=schemas.ResumeOut)
async def confirm_fabricate(resume_id: int, db: Session = Depends(get_db)):
    """确认经历后，生成面试准备包。"""
    ctx = ensure_llm_ready(db)
    resume = _ensure_resume(db, resume_id)
    if not resume.jd_summary:
        _set_progress(db, resume, "正在解析岗位 JD…")
        resume.jd_summary = await jd_parser.parse_jd(
            resume.jd_text, ctx["base_url"], ctx["api_key"], ctx["model"])
    _set_progress(db, resume, "正在生成面试准备包…")
    resume.interview_prep = await fabricate_svc.generate_interview_prep(
        resume.jd_summary, profile_svc.user_profile_dict(resume.user),
        resume.fabricated, ctx["base_url"], ctx["api_key"], ctx["model"])
    resume.progress = ""
    db.commit()
    db.refresh(resume)
    return resume


@router.post("/resumes/{resume_id}/questions")
async def gen_questions(resume_id: int, db: Session = Depends(get_db)):
    ctx = ensure_llm_ready(db)
    resume = _ensure_resume(db, resume_id)
    if not resume.jd_summary:
        _set_progress(db, resume, "正在解析岗位 JD…")
        resume.jd_summary = await jd_parser.parse_jd(
            resume.jd_text, ctx["base_url"], ctx["api_key"], ctx["model"])
    _set_progress(db, resume, "正在生成必要问题…")
    questions = await resume_generator.generate_resume_questions(
        resume.jd_summary, profile_svc.user_profile_dict(resume.user),
        ctx["base_url"], ctx["api_key"], ctx["model"])
    resume.questions = questions
    resume.status = "questioning"
    resume.progress = ""
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


@router.post("/resumes/{resume_id}/se-answers", response_model=schemas.ResumeOut)
def submit_se_answers(resume_id: int, data: schemas.SeAnswersIn, db: Session = Depends(get_db)):
    """持久化自我评价问答的答案（供中断后继续）。"""
    resume = _ensure_resume(db, resume_id)
    resume.se_answers = [a.model_dump() for a in data.answers]
    if data.supplement:
        resume.se_answers.append({"id": "supplement", "question": "", "answer": data.supplement})
    db.commit()
    db.refresh(resume)
    return resume


@router.post("/resumes/{resume_id}/generate", response_model=schemas.ResumeOut)
async def generate(resume_id: int, db: Session = Depends(get_db)):
    ctx = ensure_llm_ready(db)
    resume = _ensure_resume(db, resume_id)
    if not resume.jd_summary:
        _set_progress(db, resume, "正在解析岗位 JD…")
        resume.jd_summary = await jd_parser.parse_jd(
            resume.jd_text, ctx["base_url"], ctx["api_key"], ctx["model"])

    user = resume.user
    prof = profile_svc.user_profile_dict(user)

    _set_progress(db, resume, "正在撰写个人简介…")
    resume.personal_summary = await resume_generator.generate_personal_summary(
        resume.jd_summary, prof, ctx["base_url"], ctx["api_key"], ctx["model"])

    _set_progress(db, resume, "正在生成自我评价…")
    if not resume.self_evaluation:
        resume.self_evaluation = await se_svc.generate_self_evaluation(
            resume.jd_summary, prof, [], "",
            ctx["base_url"], ctx["api_key"], ctx["model"])

    # 技能过多时，AI 精选与 JD 最贴近的技能并按相关度排序
    skills_raw = [{"category": s.category, "name": s.name, "proficiency": s.proficiency}
                  for s in user.skills]
    if len(skills_raw) > 10:
        _set_progress(db, resume, "正在筛选与 JD 最匹配的技能…")
        resume.skills_curated = await resume_generator.curate_skills(
            resume.jd_summary, skills_raw,
            ctx["base_url"], ctx["api_key"], ctx["model"], max_count=10)
    else:
        resume.skills_curated = []

    _set_progress(db, resume, "正在排版生成简历文档…")
    _build_docx_from_resume(db, resume)
    resume.status = "generated"
    resume.progress = ""
    db.commit()
    db.refresh(resume)
    return resume


@router.post("/resumes/{resume_id}/rebuild", response_model=schemas.ResumeOut)
def rebuild(resume_id: int, data: schemas.RebuildIn, db: Session = Depends(get_db)):
    """用已存内容重建 docx（不重新调用 LLM），可选切换模板。"""
    resume = _ensure_resume(db, resume_id)
    if not resume.output_path:
        raise HTTPException(status_code=400, detail="尚未生成简历文件")
    if data.template:
        if not resume_generator.has_template(data.template):
            raise HTTPException(status_code=400, detail="不支持的模板类型")
        resume.template = data.template
    _set_progress(db, resume, "正在重新排版…")
    _build_docx_from_resume(db, resume)
    resume.progress = ""
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