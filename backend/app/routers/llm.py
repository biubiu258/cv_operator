"""LLM 配置路由：保存 base_url/api_key/model，拉取模型列表，测试连接。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import crypto, schemas
from ..database import get_db
from ..deps import llm_context, load_llm_config
from ..services import llm_client

router = APIRouter(prefix="/llm", tags=["llm"])


def _mask(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "****"
    return key[:4] + "****" + key[-4:]


@router.get("/config", response_model=schemas.LLMConfigOut)
def get_config(db: Session = Depends(get_db)):
    cfg = load_llm_config(db)
    return schemas.LLMConfigOut(
        base_url=cfg.base_url,
        api_key_masked=_mask(crypto.decrypt(cfg.api_key)),
        model=cfg.model,
    )


@router.put("/config", response_model=schemas.LLMConfigOut)
def save_config(data: schemas.LLMConfigIn, db: Session = Depends(get_db)):
    cfg = load_llm_config(db)
    cfg.base_url = data.base_url
    cfg.model = data.model
    if data.api_key:  # 为空则保留原 api_key
        cfg.api_key = crypto.encrypt(data.api_key)
    db.commit()
    db.refresh(cfg)
    return schemas.LLMConfigOut(
        base_url=cfg.base_url,
        api_key_masked=_mask(crypto.decrypt(cfg.api_key)),
        model=cfg.model,
    )


@router.post("/models")
async def pull_models(data: schemas.ModelsRequest, db: Session = Depends(get_db)):
    ctx = llm_context(db)
    base_url = data.base_url or ctx["base_url"]
    api_key = data.api_key or ctx["api_key"]
    if not base_url or not api_key:
        return {"models": []}
    models = await llm_client.list_models(base_url, api_key)
    return {"models": models}


@router.post("/test")
async def test_conn(db: Session = Depends(get_db)):
    ctx = llm_context(db)
    ok, msg, models = await llm_client.test_connection(ctx["base_url"], ctx["api_key"])
    return {"ok": ok, "message": msg, "models": models}