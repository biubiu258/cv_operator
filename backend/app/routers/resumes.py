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
from ..services import polish as polish_svc
from ..services import ats as ats_svc
from ..services import anti_detection as ad_svc
from ..services import cover_letter as cl_svc
from ..services import cover_letter_docx as cl_docx
from ..services import llm_client
from ..services import resume_generator, self_evaluation as se_svc
from ..services import timeline
from ..services.prompting import get_length_budget

router = APIRouter(tags=["resumes"])

_MT_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _set_progress(db: Session, resume, msg: str):
    resume.progress = msg
    db.add(models.ProgressEvent(resume_id=resume.id, message=msg))
    db.commit()
    broker.publish(resume.id, msg)


def _save_fabricate_version(db: Session, resume, experiences, feedback: str = ""):
    """保存杜撰经历版本快照（初稿 feedback 为空），版本号递增。"""
    next_ver = (db.query(models.FabricateVersion)
                  .filter(models.FabricateVersion.resume_id == resume.id)
                  .count()) + 1
    db.add(models.FabricateVersion(
        resume_id=resume.id, version=next_ver,
        feedback=feedback or "", experiences=experiences or []))


def _ensure_resume(db: Session, resume_id: int):
    r = db.get(models.Resume, resume_id)
    if not r:
        raise HTTPException(status_code=404, detail="简历任务不存在")
    return r


def _render_template(db: Session, resume, template: str, force: bool = False) -> str:
    """用已存内容（不含 LLM 调用）生成指定模板的 docx 并写回 output_path。

    force=False 时，若该模板已生成过且文件仍在，则直接复用，不重复生成；
    force=True 时强制重新生成并覆盖缓存。
    """
    paths = resume.output_paths or {}
    if not force:
        cached = paths.get(template)
        if cached and Path(cached).exists():
            resume.output_path = cached
            return cached
    salary = resume.expected_salary or resume.user.expected_salary
    out_path = resume_generator.build_resume_docx(
        resume.user, resume.jd_summary, resume.personal_summary, resume.self_evaluation, OUTPUT_DIR,
        target_position=resume.target_position, sections=resume.sections,
        fabricated=resume.fabricated, skills_curated=resume.skills_curated,
        expected_salary=salary, include_salary=resume.include_salary,
        template=template, length=resume.length, custom_pages=resume.custom_pages,
        polished_experiences=resume.polished_experiences,
        polished_selection=resume.polish_selection or [],
        manual_order=resume.manual_order or {},
        truncate_strategy=resume.truncate_strategy or "time_priority")
    paths[template] = out_path
    resume.output_paths = paths
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
        length=data.length,
        custom_pages=data.custom_pages,
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


@router.put("/resumes/{resume_id}", response_model=schemas.ResumeOut)
def update_resume(resume_id: int, data: schemas.ResumeUpdateIn, db: Session = Depends(get_db)):
    """详情页编辑保存：个人简介/自我评价/包含模块/经历排序。

    仅更新数据库内容；docx 模板需再调 rebuild 重新排版，网页版模板预览实时生效。
    """
    resume = _ensure_resume(db, resume_id)
    if data.personal_summary is not None:
        resume.personal_summary = data.personal_summary
    if data.self_evaluation is not None:
        resume.self_evaluation = data.self_evaluation
    if data.sections is not None:
        resume.sections = data.sections
    if data.fabricated is not None:
        resume.fabricated = data.fabricated
    if data.polished_experiences is not None:
        resume.polished_experiences = data.polished_experiences
    if data.manual_order is not None:
        resume.manual_order = data.manual_order
    db.commit()
    db.refresh(resume)
    return resume


@router.get("/resumes/{resume_id}/review", response_model=schemas.ReviewOut)
def get_review(resume_id: int, db: Session = Depends(get_db)):
    """全流程回顾聚合：简历各阶段产物 + 进度消息记录 + 杜撰版本历史。"""
    resume = _ensure_resume(db, resume_id)
    events = (db.query(models.ProgressEvent)
                .filter(models.ProgressEvent.resume_id == resume_id)
                .order_by(models.ProgressEvent.id).all())
    versions = (db.query(models.FabricateVersion)
                  .filter(models.FabricateVersion.resume_id == resume_id)
                  .order_by(models.FabricateVersion.version).all())
    return schemas.ReviewOut(
        resume=schemas.ResumeOut.model_validate(resume),
        progress_events=events,
        fabricate_versions=versions)


@router.get("/resumes/{resume_id}/render-context")
def get_render_context(resume_id: int, db: Session = Depends(get_db)):
    """返回与 docx render 函数一致的渲染上下文字段，供前端网页模板（kind=vue）取数渲染。

    字段与 resume_generator.build_resume_docx 的入参一一对应，另附篇幅预算 budget
    供前端按相同规则裁剪经历条数。
    """
    resume = _ensure_resume(db, resume_id)
    return {
        "user": profile_svc.user_profile_dict(resume.user),
        "jd_summary": resume.jd_summary or {},
        "personal_summary": resume.personal_summary or "",
        "self_evaluation": resume.self_evaluation or "",
        "target_position": resume.target_position or "",
        "sections": resume.sections or [],
        "fabricated": resume.fabricated or [],
        "polished_experiences": resume.polished_experiences or [],
        "polish_selection": resume.polish_selection or [],
        "timeline_warnings": resume.timeline_warnings,
        "skills_curated": resume.skills_curated or [],
        "expected_salary": resume.expected_salary or resume.user.expected_salary or "",
        "include_salary": resume.include_salary if resume.include_salary is not None else True,
        "length": resume.length or "fresh",
        "custom_pages": resume.custom_pages,
        "template": resume.template or "classic",
        "budget": get_length_budget(resume.length, resume.custom_pages),
        "manual_order": resume.manual_order or {},
    }


@router.post("/resumes/{resume_id}/ats-score")
def ats_score(resume_id: int, db: Session = Depends(get_db)):
    """ATS 关键词定向评分：基于当前 JD 解析结果 + 档案 + 已选经历计算匹配度。

    输出命中率、缺失关键词（按重要性排序）、各板块关键词密度、每个命中关键词所在板块。
    不依赖 LLM，纯字符串匹配 + 同义词归一，毫秒级返回。
    """
    resume = _ensure_resume(db, resume_id)
    if not resume.jd_summary:
        raise HTTPException(status_code=400, detail="请先解析岗位 JD 后再评估 ATS 匹配度")
    return ats_svc.run_ats_score(
        resume.jd_summary,
        profile_svc.user_profile_dict(resume.user),
        polished_experiences=resume.polished_experiences,
        fabricated=resume.fabricated,
        personal_summary=resume.personal_summary or "",
        self_evaluation=resume.self_evaluation or "",
    )


# --------------------------------------------------------------------------- #
# 求职信
# --------------------------------------------------------------------------- #

@router.post("/resumes/{resume_id}/cover-letter/generate")
async def generate_cover_letter(resume_id: int, data: schemas.CoverLetterGenerateIn,
                                db: Session = Depends(get_db)):
    """根据 JD + 档案 + 简历正文生成一封 200–300 字的求职信。

    支持三种风格（professional / enthusiastic / concise），默认 professional。
    会存入 resume.cover_letter 与 resume.cover_letter_tone，后续「换一版」可直接
    再次调用生成接口覆盖。
    """
    ctx = ensure_llm_ready(db)
    resume = _ensure_resume(db, resume_id)
    prof = profile_svc.user_profile_dict(resume.user)
    if not resume.jd_summary:
        raise HTTPException(status_code=400, detail="请先解析岗位 JD 后再生成求职信")

    resume_content = _collect_resume_content(resume, prof)
    content = await cl_svc.generate_cover_letter(
        resume.jd_summary, prof, resume_content,
        ctx["base_url"], ctx["api_key"], ctx["model"],
        target_position=resume.target_position or resume.jd_summary.get("position", ""),
        tone=data.tone,
    )
    resume.cover_letter = content
    resume.cover_letter_tone = data.tone
    db.commit()
    db.refresh(resume)
    return {
        "content": content,
        "word_count": cl_svc.word_count(content),
        "tone": data.tone,
    }


@router.post("/resumes/{resume_id}/cover-letter/save", response_model=schemas.ResumeOut)
def save_cover_letter(resume_id: int, data: schemas.CoverLetterSaveIn,
                      db: Session = Depends(get_db)):
    """手动保存用户编辑后的求职信正文。"""
    resume = _ensure_resume(db, resume_id)
    resume.cover_letter = data.content
    db.commit()
    db.refresh(resume)
    return resume


@router.get("/resumes/{resume_id}/cover-letter/download")
def download_cover_letter(resume_id: int, db: Session = Depends(get_db)):
    """把当前求职信正文渲染为 A4 docx 并返回下载。"""
    resume = _ensure_resume(db, resume_id)
    if not resume.cover_letter:
        raise HTTPException(status_code=400, detail="还没有求职信内容，请先生成或编辑保存")
    prof = profile_svc.user_profile_dict(resume.user)
    path = cl_docx.render_cover_letter(
        content=resume.cover_letter,
        name=prof.get("name", ""),
        email=prof.get("email", ""),
        phone=prof.get("phone", ""),
        location=prof.get("location", ""),
        target_position=resume.target_position or resume.jd_summary.get("position", ""),
        out_dir=OUTPUT_DIR,
    )
    return FileResponse(path, filename=Path(path).name, media_type=_MT_DOCX)


def _collect_resume_content(resume, prof: dict) -> str:
    """把当前简历所有已选板块拼成一段摘要，供求职信生成做上下文。"""
    parts = []
    if resume.personal_summary:
        parts.append(f"个人简介：{resume.personal_summary}")
    if resume.skills_curated:
        parts.append("技能：" + "、".join(s.get("name", "") for s in resume.skills_curated if isinstance(s, dict)))
    exps = (resume.polished_experiences or []) + (resume.fabricated or [])
    for x in exps:
        t = x.get("type")
        if t == "internship":
            head = f"{x.get('company','')} {x.get('position','')}"
        elif t == "project":
            head = f"项目 {x.get('title','')}"
        else:
            head = x.get("title") or x.get("company") or ""
        body = " ".join(filter(None, [x.get("description", ""), x.get("result", "")]))
        if head:
            parts.append(f"{head}：{body}")
    return "\n".join(parts)


# 可回退的步骤及其展示名（回退后保留该步已填内容，清除其后的全部产物）
_ROLLBACK_LABELS = {
    "jd": "解析 JD",
    "fabricate": "经历杜撰",
    "questions": "回答必要问题",
    "se": "自我评价问答",
}


@router.post("/resumes/{resume_id}/rollback", response_model=schemas.ResumeOut)
def rollback(resume_id: int, data: schemas.RollbackIn, db: Session = Depends(get_db)):
    """回退到生成流程中的某一步：该步已填内容保留（便于修改），其后的产物全部清除。

    回退后前端跳转到「继续生成」，ResumeNew 按 status 恢复到对应步骤。
    """
    resume = _ensure_resume(db, resume_id)
    step = data.step
    if step not in _ROLLBACK_LABELS:
        raise HTTPException(status_code=400, detail="不支持的回退步骤")

    # 最终产物在任何回退目标下都需清除
    resume.skills_curated = []
    resume.personal_summary = ""
    resume.self_evaluation = ""
    resume.output_path = ""
    resume.output_paths = {}

    if step == "se":
        resume.status = "answered" if resume.answers else "questioning"
    elif step == "questions":
        resume.se_questions = []
        resume.se_answers = []
        resume.status = "questioning" if resume.questions else "parsed"
    elif step == "fabricate":
        resume.interview_prep = {}
        resume.questions = []
        resume.answers = []
        resume.se_questions = []
        resume.se_answers = []
        resume.status = "parsed" if resume.jd_summary else "draft"
    else:  # jd
        resume.fabricated = []
        resume.polished_experiences = []
        resume.polish_selection = []
        resume.interview_prep = {}
        resume.questions = []
        resume.answers = []
        resume.se_questions = []
        resume.se_answers = []
        resume.status = "parsed" if resume.jd_summary else "draft"

    resume.progress = ""
    db.add(models.ProgressEvent(
        resume_id=resume.id,
        message=f"用户回退到「{_ROLLBACK_LABELS[step]}」步骤，后续内容已重置"))
    db.commit()
    db.refresh(resume)
    return resume


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

    # 三种经历模式互斥：杜撰 / 按 JD 润色真实经历 / 原文使用真实经历。
    # 进入杜撰或原文模式时清空另一模式的产物，避免旧经历残留混入简历。
    resume.polished_experiences = []
    resume.polish_selection = []
    fabricated = []
    if data.fabricate:
        _set_progress(db, resume, "正在生成经历蓝本…")
        fabricated = await fabricate_svc.fabricate_experiences(
            resume.jd_summary, prof, ctx["base_url"], ctx["api_key"], ctx["model"],
            types=data.types, count=data.count, extra_jd=data.extra_jd,
            length=resume.length, custom_pages=resume.custom_pages)
        resume.fabricated = fabricated
        if fabricated:
            _save_fabricate_version(db, resume, fabricated)
    else:
        # 「只使用真实经历原文」：同时清空杜撰与润色产物
        resume.fabricated = []
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
    _save_fabricate_version(db, resume, revised, data.feedback)
    resume.progress = ""
    db.commit()
    db.refresh(resume)
    return resume


@router.post("/resumes/{resume_id}/fabricate/save", response_model=schemas.ResumeOut)
def save_fabricated(resume_id: int, data: schemas.ExperiencesSaveIn,
                    db: Session = Depends(get_db)):
    """保存用户手动编辑后的杜撰经历（不调用 LLM），做日期规范化与类型兜底。"""
    resume = _ensure_resume(db, resume_id)
    valid = set(("project", "internship", "work", "other"))
    experiences = []
    for x in data.experiences:
        if not isinstance(x, dict) or not x.get("type"):
            continue
        if x.get("type") not in valid:
            x["type"] = "project"
        experiences.append(x)
    resume.fabricated = timeline.normalize_experiences(experiences)
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
    # 最终写进简历的经历：杜撰优先，其次按 JD 润色过的真实经历
    final_experiences = resume.fabricated or resume.polished_experiences or []
    resume.interview_prep = await fabricate_svc.generate_interview_prep(
        resume.jd_summary, profile_svc.user_profile_dict(resume.user),
        final_experiences, ctx["base_url"], ctx["api_key"], ctx["model"])
    resume.progress = ""
    db.commit()
    db.refresh(resume)
    return resume


@router.post("/resumes/{resume_id}/polish", response_model=schemas.ResumeOut)
async def polish(resume_id: int, data: schemas.PolishIn = None,
                 db: Session = Depends(get_db)):
    """按 JD 润色档案中的真实经历：只优化表述，公司/岗位/时间等事实保持不变。

    支持选择经历：传入 ref_ids 时只润色勾选条目，未勾选的经历不会写入简历。
    """
    ctx = ensure_llm_ready(db)
    resume = _ensure_resume(db, resume_id)
    prof = profile_svc.user_profile_dict(resume.user)
    if not resume.jd_summary:
        _set_progress(db, resume, "正在解析岗位 JD…")
        resume.jd_summary = await jd_parser.parse_jd(
            resume.jd_text, ctx["base_url"], ctx["api_key"], ctx["model"])

    if not (prof.get("internships") or prof.get("projects")):
        raise HTTPException(status_code=400, detail="档案中还没有实习或项目经历，暂无可润色内容")

    # ref_ids 为 None 表示旧版调用（未启用选择），保持全部经历润色的历史行为
    ref_ids = data.ref_ids if data else None
    available = {x["ref_id"] for x in polish_svc.collect_real_experiences(prof)}
    ref_ids = [r for r in (ref_ids or []) if r in available] if ref_ids is not None else None
    if ref_ids is not None and not ref_ids:
        raise HTTPException(status_code=400, detail="请至少选择一段需要润色的经历")

    _set_progress(db, resume, "正在按 JD 润色勾选的真实经历…")
    polished = await polish_svc.polish_experiences(
        resume.jd_summary, prof, ctx["base_url"], ctx["api_key"], ctx["model"],
        length=resume.length, custom_pages=resume.custom_pages,
        ref_ids=ref_ids)
    # 润色与杜撰互斥，进入润色模式时清空杜撰产物
    resume.fabricated = []
    resume.polished_experiences = polished
    resume.polish_selection = ref_ids or []
    resume.progress = ""
    db.commit()
    db.refresh(resume)
    return resume


@router.post("/resumes/{resume_id}/polish/revise", response_model=schemas.ResumeOut)
async def revise_polish(resume_id: int, data: schemas.FabricateReviseIn,
                        db: Session = Depends(get_db)):
    """基于用户修改意见微调润色稿，事实字段继续锁定。"""
    ctx = ensure_llm_ready(db)
    resume = _ensure_resume(db, resume_id)
    if not resume.jd_summary:
        _set_progress(db, resume, "正在解析岗位 JD…")
        resume.jd_summary = await jd_parser.parse_jd(
            resume.jd_text, ctx["base_url"], ctx["api_key"], ctx["model"])
    _set_progress(db, resume, "正在根据意见调整润色…")
    resume.polished_experiences = await polish_svc.revise_polished(
        resume.jd_summary, data.experiences, data.feedback,
        ctx["base_url"], ctx["api_key"], ctx["model"])
    resume.progress = ""
    db.commit()
    db.refresh(resume)
    return resume


@router.post("/resumes/{resume_id}/polish/save", response_model=schemas.ResumeOut)
def save_polish(resume_id: int, data: schemas.ExperiencesSaveIn, db: Session = Depends(get_db)):
    """保存用户手动编辑后的润色经历（不调用 LLM）。

    服务端再次以档案事实为准锁定公司/岗位/时间等字段，只接受表述层修改，
    并做日期规范化，保证润色模式不会经手动编辑变成虚构经历。
    """
    resume = _ensure_resume(db, resume_id)
    originals = polish_svc.select_experiences(
        polish_svc.collect_real_experiences(profile_svc.user_profile_dict(resume.user)),
        resume.polish_selection or None)
    locked = polish_svc.preserve_identity(originals, data.experiences)
    resume.polished_experiences = timeline.normalize_experiences(locked)
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
    resume.answers = []  # 问题已整体替换，旧答案不再对应
    resume.status = "questioning"
    resume.progress = ""
    db.commit()
    db.refresh(resume)
    return {"questions": questions}


@router.post("/resumes/{resume_id}/questions/regenerate")
async def regenerate_question(resume_id: int, data: schemas.QuestionRegenerateIn,
                              db: Session = Depends(get_db)):
    """换一题：只重新生成指定的一个问题，其余问题与已答内容保持不变。"""
    ctx = ensure_llm_ready(db)
    resume = _ensure_resume(db, resume_id)
    if not resume.questions:
        raise HTTPException(status_code=400, detail="当前还没有必要问题，请先生成问题")
    if data.question_id not in [q.get("id") for q in resume.questions]:
        raise HTTPException(status_code=404, detail="要替换的问题不存在")

    q = await resume_generator.generate_single_question(
        resume.jd_summary or {}, profile_svc.user_profile_dict(resume.user),
        resume.questions, ctx["base_url"], ctx["api_key"], ctx["model"],
        question_id=data.question_id, topic=data.topic)
    if not q:
        raise HTTPException(status_code=400, detail="换题失败，请稍后重试")

    qs = [q if item.get("id") == data.question_id else item for item in resume.questions]
    resume.questions = qs
    # 被替换的问题原答案作废，避免摘要与题目不一致
    resume.answers = [a for a in (resume.answers or [])
                      if a.get("id") != data.question_id]
    db.commit()
    db.refresh(resume)
    return {"questions": qs, "question": q}


@router.post("/resumes/{resume_id}/answers", response_model=schemas.ResumeOut)
def submit_answers(resume_id: int, data: schemas.AnswersIn, db: Session = Depends(get_db)):
    resume = _ensure_resume(db, resume_id)
    resume.answers = [a.model_dump() for a in data.answers]
    # 草稿保存不改变任务状态，避免中途刷新页面被误判为已完成问答
    if not data.draft:
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
        resume.jd_summary, prof, ctx["base_url"], ctx["api_key"], ctx["model"],
        length=resume.length, custom_pages=resume.custom_pages)

    _set_progress(db, resume, "正在生成自我评价…")
    if not resume.self_evaluation:
        resume.self_evaluation = await se_svc.generate_self_evaluation(
            resume.jd_summary, prof, [], "",
            ctx["base_url"], ctx["api_key"], ctx["model"])

    # 技能过多时，AI 精选与 JD 最贴近的技能并按相关度排序（数量受篇幅约束）
    budget = get_length_budget(resume.length, resume.custom_pages)
    skills_raw = [{"category": s.category, "name": s.name, "proficiency": s.proficiency}
                  for s in user.skills]
    if len(skills_raw) > budget["max_skills"]:
        _set_progress(db, resume, "正在筛选与 JD 最匹配的技能…")
        resume.skills_curated = await resume_generator.curate_skills(
            resume.jd_summary, skills_raw,
            ctx["base_url"], ctx["api_key"], ctx["model"], max_count=budget["max_skills"])
    else:
        resume.skills_curated = []

    _set_progress(db, resume, "正在排版生成简历文档…")
    if resume_generator.template_kind(resume.template) != "vue":
        # 网页版模板不生成 docx，由前端渲染预览/打印
        _render_template(db, resume, resume.template)
    resume.status = "generated"
    resume.progress = ""
    db.commit()
    db.refresh(resume)
    return resume


@router.post("/resumes/{resume_id}/rebuild", response_model=schemas.ResumeOut)
def rebuild(resume_id: int, data: schemas.RebuildIn, db: Session = Depends(get_db)):
    """用已存内容重建/复用 docx（不重新调用 LLM），可选切换模板或裁剪策略。

    切换模板时，若该模板已生成过则直接复用，不重复生成；
    「重新生成」按钮（未传 template）则强制重新排版当前模板。
    网页版模板（kind=vue）仅持久化选择，不生成 docx。
    """
    resume = _ensure_resume(db, resume_id)
    if data.truncate_strategy:
        resume.truncate_strategy = data.truncate_strategy
    if data.template:
        if not resume_generator.has_template(data.template):
            raise HTTPException(status_code=400, detail="不支持的模板类型")
        resume.template = data.template
        if resume_generator.template_kind(data.template) == "vue":
            db.commit()
            db.refresh(resume)
            return resume
        if resume.status != "generated":
            raise HTTPException(status_code=400, detail="尚未生成简历文件")
        # 网页版切回 Word 时可能尚无 docx 产物，按已存内容直接渲染
        _set_progress(db, resume, "正在切换模板…")
        _render_template(db, resume, data.template, force=False)
    else:
        if resume.status != "generated":
            raise HTTPException(status_code=400, detail="尚未生成简历文件")
        _set_progress(db, resume, "正在重新排版…")
        _render_template(db, resume, resume.template, force=True)
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


# ---------- T8 反伪造检测 ----------

def _collect_experiences_for_detect(resume) -> list[dict]:
    """收集当前简历里的所有经历（润色稿优先 → 杜撰稿 → 档案原文）。"""
    exps: list[dict] = []
    if resume.polished_experiences:
        exps.extend(resume.polished_experiences)
    if resume.fabricated:
        exps.extend(resume.fabricated)
    if not exps:
        for p in resume.user.projects:
            exps.append({
                "type": "project", "title": getattr(p, "title", "") or "",
                "role": getattr(p, "role", "") or "",
                "start_date": getattr(p, "start_date", "") or "",
                "end_date": getattr(p, "end_date", "") or "",
                "tech_stack": getattr(p, "tech_stack", "") or "",
                "description": getattr(p, "description", "") or "",
                "result": getattr(p, "result", "") or "",
            })
        for i in resume.user.internships:
            exps.append({
                "type": "internship", "title": getattr(i, "company", "") or "",
                "role": getattr(i, "position", "") or "",
                "start_date": getattr(i, "start_date", "") or "",
                "end_date": getattr(i, "end_date", "") or "",
                "tech_stack": "",
                "description": getattr(i, "description", "") or "",
                "result": getattr(i, "achievement", "") or "",
            })
    return exps


@router.post("/resumes/{resume_id}/anti-detect")
def anti_detect(resume_id: int, db: Session = Depends(get_db)):
    """对当前简历跑反伪造检测，返回结构化评分 + 命中规则。纯只读，不改 DB。"""
    resume = _ensure_resume(db, resume_id)
    exps = _collect_experiences_for_detect(resume)
    result = ad_svc.detect_all(exps)
    result["experience_sources"] = {
        "polished": len(resume.polished_experiences or []),
        "fabricated": len(resume.fabricated or []),
    }
    return result


@router.post("/resumes/{resume_id}/anti-detect/optimize", response_model=schemas.ResumeOut)
async def anti_detect_optimize(resume_id: int, db: Session = Depends(get_db)):
    """自动优化：跑检测 → 如果 score >= 0.4，调用 LLM 按 avoid_ai_patterns.md 重写经历。

    重写结果会写回 `polished_experiences`（优先）或 `fabricated`。不调 LLM 时（检测 score < 0.4）直接返回原 resume。
    """
    ctx = ensure_llm_ready(db)
    resume = _ensure_resume(db, resume_id)
    exps = _collect_experiences_for_detect(resume)
    report = ad_svc.detect_all(exps)

    if report["score"] < 0.4:
        resume._anti_detect_result = report
        db.commit()
        db.refresh(resume)
        return resume

    # 构造优化提示词：把检测报告命中的规则作为改写重点
    from ..services.prompting import render_prompt
    import json as _json
    system, prompt = render_prompt(
        "avoid_ai_patterns",
        experiences=_json.dumps(exps, ensure_ascii=False),
        jd_summary=_json.dumps(resume.jd_summary or {}, ensure_ascii=False),
        anti_detect_report=_json.dumps({
            "score": report["score"],
            "verdict": report["verdict"],
            "triggered_rules": report["triggered_rules"],
            "rule_descriptions": {k: v["description"] for k, v in report["rules"].items()
                                  if v["danger"] >= 0.3},
        }, ensure_ascii=False),
    )
    raw = await llm_client.chat(
        ctx["base_url"], ctx["api_key"], ctx["model"],
        [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        temperature=0.6, json_mode=True,
    )
    try:
        data = _json.loads(raw)
        rewritten = data.get("experiences") if isinstance(data, dict) else None
        if not isinstance(rewritten, list) or not rewritten:
            rewritten = exps  # 兜底：保留原样
    except Exception:
        rewritten = exps

    # 回写到 resume（优先 polished → 否则 fabricated）
    if resume.polished_experiences:
        resume.polished_experiences = rewritten
        resume.anti_detect_optimize_target = "polished_experiences"
    elif resume.fabricated:
        resume.fabricated = rewritten
        resume.anti_detect_optimize_target = "fabricated"

    # 再跑一次检测，看优化效果
    new_report = ad_svc.detect_all(rewritten)
    resume.anti_detect_result = {"before": report, "after": new_report}

    db.commit()
    db.refresh(resume)
    return resume
