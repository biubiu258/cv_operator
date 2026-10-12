"""FastAPI 应用入口。"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from . import models  # noqa: F401  # 确保模型已注册
from .database import Base, engine
from .routers import llm, resumes, self_evaluation, users

Base.metadata.create_all(bind=engine)

# 轻量迁移：为已存在的 resumes 表补充新列（SQLite create_all 不会自动加列）
_resume_cols = {c["name"] for c in inspect(engine).get_columns("resumes")}
for _col, _ddl in (
    ("sections", "ALTER TABLE resumes ADD COLUMN sections JSON"),
    ("fabricated", "ALTER TABLE resumes ADD COLUMN fabricated JSON"),
    ("interview_prep", "ALTER TABLE resumes ADD COLUMN interview_prep JSON"),
):
    if _col not in _resume_cols:
        with engine.begin() as _conn:
            _conn.execute(text(_ddl))

app = FastAPI(title="AI 简历生成器", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users.router)
app.include_router(llm.router)
app.include_router(resumes.router)
app.include_router(self_evaluation.router)


@app.get("/health")
def health():
    return {"ok": True}