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
    ("se_questions", "ALTER TABLE resumes ADD COLUMN se_questions JSON"),
    ("se_answers", "ALTER TABLE resumes ADD COLUMN se_answers JSON"),
    ("skills_curated", "ALTER TABLE resumes ADD COLUMN skills_curated JSON"),
    ("progress", "ALTER TABLE resumes ADD COLUMN progress VARCHAR(200)"),
    ("expected_salary", "ALTER TABLE resumes ADD COLUMN expected_salary VARCHAR(50)"),
    ("include_salary", "ALTER TABLE resumes ADD COLUMN include_salary BOOLEAN"),
    ("template", "ALTER TABLE resumes ADD COLUMN template VARCHAR(30)"),
    ("length", "ALTER TABLE resumes ADD COLUMN length VARCHAR(20)"),
    ("custom_pages", "ALTER TABLE resumes ADD COLUMN custom_pages INTEGER"),
    ("output_paths", "ALTER TABLE resumes ADD COLUMN output_paths JSON"),
):
    if _col not in _resume_cols:
        with engine.begin() as _conn:
            _conn.execute(text(_ddl))

# 为已存在的 users 表补充新列
_user_cols = {c["name"] for c in inspect(engine).get_columns("users")}
if "hobbies" not in _user_cols:
    with engine.begin() as _conn:
        _conn.execute(text("ALTER TABLE users ADD COLUMN hobbies TEXT"))
if "expected_salary" not in _user_cols:
    with engine.begin() as _conn:
        _conn.execute(text("ALTER TABLE users ADD COLUMN expected_salary VARCHAR(50)"))
if "graduation_date" not in _user_cols:
    with engine.begin() as _conn:
        _conn.execute(text("ALTER TABLE users ADD COLUMN graduation_date VARCHAR(30)"))
if "avatar" not in _user_cols:
    with engine.begin() as _conn:
        _conn.execute(text("ALTER TABLE users ADD COLUMN avatar VARCHAR(300)"))

# 回填历史数据中的 NULL（旧行在 ALTER TABLE 加列后为 NULL，避免响应校验报 string_type 错误）
with engine.begin() as _conn:
    _conn.execute(text("UPDATE users SET hobbies = '' WHERE hobbies IS NULL"))
    _conn.execute(text("UPDATE users SET expected_salary = '' WHERE expected_salary IS NULL"))
    _conn.execute(text("UPDATE users SET graduation_date = '' WHERE graduation_date IS NULL"))
    _conn.execute(text("UPDATE users SET avatar = '' WHERE avatar IS NULL"))
    _conn.execute(text("UPDATE resumes SET progress = '' WHERE progress IS NULL"))
    _conn.execute(text("UPDATE resumes SET expected_salary = '' WHERE expected_salary IS NULL"))
    _conn.execute(text("UPDATE resumes SET include_salary = 1 WHERE include_salary IS NULL"))
    _conn.execute(text("UPDATE resumes SET template = 'classic' WHERE template IS NULL"))
    _conn.execute(text("UPDATE resumes SET length = 'fresh' WHERE length IS NULL"))
    _conn.execute(text("UPDATE resumes SET output_paths = '{}' WHERE output_paths IS NULL"))

app = FastAPI(title="AI 简历生成器", version="0.1.0")

# 头像等上传文件的静态服务
from fastapi.staticfiles import StaticFiles  # noqa: E402

from .config import UPLOAD_DIR  # noqa: E402

app.mount("/static", StaticFiles(directory=str(UPLOAD_DIR)), name="static")

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