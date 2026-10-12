"""公共依赖与配置读取。"""
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from . import crypto
from .database import get_db
from .models import LLMConfig, User


def get_active_user(db: Session = Depends(get_db)) -> User:
    user = db.query(User).filter(User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(status_code=404, detail="尚未建立用户档案，请先建档")
    return user


def load_llm_config(db: Session) -> LLMConfig:
    cfg = db.query(LLMConfig).first()
    if not cfg:
        cfg = LLMConfig()
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return cfg


def llm_context(db: Session) -> dict:
    """读取并解密 LLM 配置，返回 base_url / api_key / model。"""
    cfg = load_llm_config(db)
    return {
        "base_url": cfg.base_url,
        "api_key": crypto.decrypt(cfg.api_key),
        "model": cfg.model,
    }


def ensure_llm_ready(db: Session) -> dict:
    ctx = llm_context(db)
    if not ctx["base_url"] or not ctx["api_key"] or not ctx["model"]:
        raise HTTPException(status_code=400, detail="请先完成 LLM 配置（base_url / api_key / model）")
    return ctx