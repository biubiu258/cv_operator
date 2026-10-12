"""自我评价路由：问题集生成 + 按规范生成正文。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import ensure_llm_ready, get_active_user
from ..services import profile as profile_svc
from ..services import self_evaluation as se_svc

router = APIRouter(prefix="/self-evaluation", tags=["self-evaluation"])


def _jd_summary_of(db: Session, resume_id) -> dict:
    if resume_id:
        resume = db.get(models.Resume, resume_id)
        if resume:
            return resume.jd_summary or {}
    return {}


@router.post("/questions")
async def questions(
    resume_id: int = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_active_user),
):
    ctx = ensure_llm_ready(db)
    jd_summary = _jd_summary_of(db, resume_id)
    qs = await se_svc.generate_questions(
        jd_summary, profile_svc.user_profile_dict(user),
        ctx["base_url"], ctx["api_key"], ctx["model"])
    return {"jd_summary": jd_summary, "questions": qs}


@router.post("/generate")
async def generate(
    data: schemas.SelfEvalGenerateIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_active_user),
):
    ctx = ensure_llm_ready(db)
    jd_summary = _jd_summary_of(db, data.resume_id)
    content = await se_svc.generate_self_evaluation(
        jd_summary, profile_svc.user_profile_dict(user),
        [a.model_dump() for a in data.answers], data.supplement,
        ctx["base_url"], ctx["api_key"], ctx["model"])

    rec = models.SelfEvaluation(
        user_id=user.id,
        resume_id=data.resume_id,
        content=content,
        qa=[a.model_dump() for a in data.answers],
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)

    # 若绑定简历任务，同步更新简历的自我评价
    if data.resume_id:
        resume = db.get(models.Resume, data.resume_id)
        if resume:
            resume.self_evaluation = content
            db.commit()

    return {"id": rec.id, "content": content}