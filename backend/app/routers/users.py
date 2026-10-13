"""用户与档案路由（含多用户切换、子实体 CRUD、头像上传）。"""
import time
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from .. import models, schemas
from ..config import AVATAR_DIR
from ..database import get_db
from ..deps import get_active_user

router = APIRouter(tags=["users"])

_AVATAR_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
_AVATAR_MAX_BYTES = 5 * 1024 * 1024


def _ensure_user(db: Session, user_id: int):
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user


def _remove_avatar_file(avatar: str):
    """删除旧头像文件（仅限本服务 avatars 目录内的相对路径，防路径穿越）。"""
    if avatar and avatar.startswith("/static/avatars/"):
        path = AVATAR_DIR / Path(avatar).name
        path.unlink(missing_ok=True)


@router.post("/users/{user_id}/avatar", response_model=schemas.UserOut)
async def upload_avatar(user_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    """上传个人头像：保存到 uploads/avatars/，数据库存 /static 相对路径。"""
    user = _ensure_user(db, user_id)
    ext = Path(file.filename or "").suffix.lower()
    if ext not in _AVATAR_EXTS:
        raise HTTPException(status_code=400, detail="仅支持图片文件（png/jpg/jpeg/gif/webp/bmp）")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="文件内容为空")
    if len(data) > _AVATAR_MAX_BYTES:
        raise HTTPException(status_code=400, detail="图片不能超过 5MB")
    fname = f"avatar_{user_id}_{int(time.time())}{ext}"
    (AVATAR_DIR / fname).write_bytes(data)
    _remove_avatar_file(user.avatar)
    user.avatar = f"/static/avatars/{fname}"
    db.commit()
    db.refresh(user)
    return user


@router.delete("/users/{user_id}/avatar", response_model=schemas.UserOut)
def remove_avatar(user_id: int, db: Session = Depends(get_db)):
    """移除头像：清空字段并删除对应文件。"""
    user = _ensure_user(db, user_id)
    _remove_avatar_file(user.avatar)
    user.avatar = ""
    db.commit()
    db.refresh(user)
    return user


@router.post("/users", response_model=schemas.UserOut)
def create_user(data: schemas.UserCreate, db: Session = Depends(get_db)):
    user = models.User(**data.model_dump())
    db.add(user)
    db.commit()
    db.refresh(user)
    # 首个用户自动激活
    if not db.query(models.User).filter(models.User.is_active.is_(True)).first():
        user.is_active = True
        db.commit()
        db.refresh(user)
    return user


@router.get("/users/active", response_model=schemas.UserDetail)
def active_user(db: Session = Depends(get_db)):
    return get_active_user(db)


@router.get("/users", response_model=list[schemas.UserOut])
def list_users(db: Session = Depends(get_db)):
    return db.query(models.User).order_by(models.User.id).all()


@router.get("/users/{user_id}", response_model=schemas.UserDetail)
def get_user(user_id: int, db: Session = Depends(get_db)):
    return _ensure_user(db, user_id)


@router.put("/users/{user_id}", response_model=schemas.UserOut)
def update_user(user_id: int, data: schemas.UserUpdate, db: Session = Depends(get_db)):
    user = _ensure_user(db, user_id)
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(user, k, v)
    db.commit()
    db.refresh(user)
    return user


@router.delete("/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db)):
    user = _ensure_user(db, user_id)
    was_active = user.is_active
    db.delete(user)
    db.commit()
    if was_active:
        nxt = db.query(models.User).order_by(models.User.id).first()
        if nxt:
            nxt.is_active = True
            db.commit()
    return {"ok": True}


@router.post("/users/{user_id}/activate", response_model=schemas.UserOut)
def activate_user(user_id: int, db: Session = Depends(get_db)):
    user = _ensure_user(db, user_id)
    db.query(models.User).filter(models.User.is_active.is_(True)).update({"is_active": False})
    user.is_active = True
    db.commit()
    db.refresh(user)
    return user


# 子实体（教育/技能/项目/实习/证书）CRUD
_ENTITY = {
    "educations": (models.Education, schemas.EducationOut, schemas.EducationBase),
    "skills": (models.Skill, schemas.SkillOut, schemas.SkillBase),
    "projects": (models.Project, schemas.ProjectOut, schemas.ProjectBase),
    "internships": (models.Internship, schemas.InternshipOut, schemas.InternshipBase),
    "certificates": (models.Certificate, schemas.CertificateOut, schemas.CertificateBase),
}

for _key, (_Model, _SchemaOut, _SchemaIn) in _ENTITY.items():

    def _make_add(Model=_Model, SchemaIn=_SchemaIn):
        def add(user_id: int, data: SchemaIn, db: Session = Depends(get_db)):
            _ensure_user(db, user_id)
            obj = Model(user_id=user_id, **data.model_dump())
            db.add(obj)
            db.commit()
            db.refresh(obj)
            return obj
        return add

    def _make_update(Model=_Model, SchemaIn=_SchemaIn):
        def update(item_id: int, data: SchemaIn, db: Session = Depends(get_db)):
            obj = db.get(Model, item_id)
            if not obj:
                raise HTTPException(status_code=404, detail="记录不存在")
            for k, v in data.model_dump(exclude_unset=True).items():
                setattr(obj, k, v)
            db.commit()
            db.refresh(obj)
            return obj
        return update

    def _make_delete(Model=_Model):
        def delete(item_id: int, db: Session = Depends(get_db)):
            obj = db.get(Model, item_id)
            if not obj:
                raise HTTPException(status_code=404, detail="记录不存在")
            db.delete(obj)
            db.commit()
            return {"ok": True}
        return delete

    router.add_api_route(
        f"/users/{{user_id}}/{_key}", _make_add(), methods=["POST"],
        response_model=_SchemaOut, name=f"add_{_key}",
    )
    router.add_api_route(
        f"/{_key}/{{item_id}}", _make_update(), methods=["PUT"],
        response_model=_SchemaOut, name=f"update_{_key}",
    )
    router.add_api_route(
        f"/{_key}/{{item_id}}", _make_delete(), methods=["DELETE"], name=f"delete_{_key}",
    )