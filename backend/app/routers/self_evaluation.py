"""自我评价路由：问题集生成 + 按规范生成正文。"""
from fastapi import APIRouter, Depends, HTTPException
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
    # 持久化自我评价问题，供中断后继续
    if resume_id:
        resume = db.get(models.Resume, resume_id)
        if resume:
            resume.se_questions = qs
            db.commit()
    return {"jd_summary": jd_summary, "questions": qs}


@router.post("/generate")
async def generate(
    data: schemas.SelfEvalGenerateIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_active_user),
):
    ctx = ensure_llm_ready(db)
    jd_summary = _jd_summary_of(db, data.resume_id)
    resume = db.get(models.Resume, data.resume_id) if data.resume_id else None
    if resume:
        resume.progress = "正在生成自我评价…"
        db.commit()
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

    # 若绑定简历任务，同步更新简历的自我评价与问答答案
    if data.resume_id:
        resume = db.get(models.Resume, data.resume_id)
        if resume:
            resume.self_evaluation = content
            resume.se_answers = [a.model_dump() for a in data.answers]
            if data.supplement:
                resume.se_answers.append({"id": "supplement", "question": "", "answer": data.supplement})
            resume.progress = ""
            db.commit()

    return {"id": rec.id, "content": content}


# ---------- 自我评价历史记录 CRUD ----------
@router.get("/records", response_model=list[schemas.SelfEvalRecordOut])
def list_records(db: Session = Depends(get_db), user: models.User = Depends(get_active_user)):
    return (db.query(models.SelfEvaluation)
            .filter(models.SelfEvaluation.user_id == user.id)
            .order_by(models.SelfEvaluation.id.desc()).all())


@router.post("/records", response_model=schemas.SelfEvalRecordOut)
def create_record(data: schemas.SelfEvalRecordIn, db: Session = Depends(get_db),
                  user: models.User = Depends(get_active_user)):
    rec = models.SelfEvaluation(
        user_id=user.id,
        resume_id=data.resume_id,
        content=data.content,
        qa=[a.model_dump() for a in data.qa],
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


@router.put("/records/{record_id}", response_model=schemas.SelfEvalRecordOut)
def update_record(record_id: int, data: schemas.SelfEvalRecordUpdate,
                  db: Session = Depends(get_db), user: models.User = Depends(get_active_user)):
    rec = db.get(models.SelfEvaluation, record_id)
    if not rec or rec.user_id != user.id:
        raise HTTPException(status_code=404, detail="记录不存在")
    if data.content is not None:
        rec.content = data.content
    db.commit()
    db.refresh(rec)
    return rec


@router.delete("/records/{record_id}")
def delete_record(record_id: int, db: Session = Depends(get_db),
                  user: models.User = Depends(get_active_user)):
    rec = db.get(models.SelfEvaluation, record_id)
    if not rec or rec.user_id != user.id:
        raise HTTPException(status_code=404, detail="记录不存在")
    db.delete(rec)
    db.commit()
    return {"ok": True}