"""把 user_information/ 下的个人资料导入数据库（可重复执行，做幂等更新）。

用法（backend 目录下）：
    .\\.venv\\Scripts\\python.exe seed.py
"""
import re
from pathlib import Path

from app import models
from app.database import SessionLocal

INFO_DIR = Path(__file__).resolve().parent.parent / "user_information"
TARGET_POSITION = "AI Agent 开发工程师"


def _clean(text: str) -> str:
    return text.replace("\\", "").strip()


def _read_basic() -> dict:
    text = _clean((INFO_DIR / "基本信息.md").read_text(encoding="utf-8"))

    def find(pattern: str, default: str = "") -> str:
        m = re.search(pattern, text, re.MULTILINE)
        return m.group(1).strip() if m else default

    # 教育背景行：**学校** | 专业 | 学历
    school = major = degree = ""
    for line in text.splitlines():
        if "|" in line and "本科" in line:
            parts = [p.strip() for p in line.split("|")]
            school = parts[0].strip("*").strip() if parts else ""
            major = parts[1] if len(parts) > 1 else ""
            degree = parts[2] if len(parts) > 2 else ""
            break

    start = end = ""
    m = re.search(r"(\d{4}\.\d{2})\s*-\s*(\d{4}\.\d{2})", text)
    if m:
        start, end = m.group(1), m.group(2)

    certs_raw = find(r"证书[:：]\s*(.+)")
    certs = [c.strip() for c in re.split(r"[、,，\n]", certs_raw) if c.strip()]

    return {
        "name": find(r"姓名[:：]\s*(.+)"),
        "phone": find(r"电话[:：]\s*(\S+)"),
        "email": find(r"邮箱[:：]\s*(\S+)"),
        "location": find(r"所在地[:：]\s*(.+)"),
        "school": school,
        "major": major,
        "degree": degree,
        "start_date": start,
        "end_date": end,
        "courses": find(r"主修课程[:：]\s*(.+)"),
        "certificates": certs,
    }


def main() -> None:
    d = _read_basic()
    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.phone == d["phone"]).first()
        if not user:
            user = db.query(models.User).filter(models.User.name == d["name"]).first()
        if not user:
            user = models.User()
            db.add(user)

        user.name = d["name"]
        user.phone = d["phone"]
        user.email = d["email"]
        user.location = d["location"]
        if not user.target_position:
            user.target_position = TARGET_POSITION
        db.flush()

        if not db.query(models.User).filter(models.User.is_active.is_(True)).first():
            user.is_active = True

        if d["school"]:
            edu = db.query(models.Education).filter(
                models.Education.user_id == user.id,
                models.Education.school == d["school"],
            ).first()
            if not edu:
                edu = models.Education(user_id=user.id)
                db.add(edu)
            edu.school = d["school"]
            edu.major = d["major"]
            edu.degree = d["degree"]
            edu.start_date = d["start_date"]
            edu.end_date = d["end_date"]
            edu.courses = d["courses"]

        for cname in d["certificates"]:
            exists = db.query(models.Certificate).filter(
                models.Certificate.user_id == user.id,
                models.Certificate.name == cname,
            ).first()
            if not exists:
                db.add(models.Certificate(user_id=user.id, name=cname))

        db.commit()
        print(f"OK  用户导入成功：id={user.id}  姓名={user.name}  学校={d['school']}  证书={d['certificates']}")
    finally:
        db.close()


if __name__ == "__main__":
    main()