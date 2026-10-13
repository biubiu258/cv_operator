"""接口测试：覆盖用户与简历核心端点，重点回归历史数据 NULL 字段的响应校验。"""
from pathlib import Path

from sqlalchemy import text

from app import models


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


# ---------- 用户 ----------
def test_create_and_list_users(client):
    r = client.post("/users", json={"name": "张三", "target_position": "后端开发",
                                    "graduation_date": "2026.07"})
    assert r.status_code == 200
    assert r.json()["hobbies"] == ""
    assert r.json()["graduation_date"] == "2026.07"

    r = client.get("/users")
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["name"] == "张三"


def test_active_user_defaults_to_null_hobbies_as_empty(client, db_session):
    # 模拟旧数据：ALTER TABLE 加列后 hobbies 为 NULL
    db_session.execute(
        text("INSERT INTO users (name, phone, email, location, target_position, hobbies, is_active) "
             "VALUES ('李四', '', '', '', '', NULL, 1)")
    )
    db_session.commit()

    r = client.get("/users/active")
    assert r.status_code == 200
    assert r.json()["name"] == "李四"
    assert r.json()["hobbies"] == ""


def test_active_user_404_when_no_user(client):
    r = client.get("/users/active")
    assert r.status_code == 404


def test_update_user_hobbies(client, db_session):
    db_session.execute(
        text("INSERT INTO users (name, is_active, hobbies) VALUES ('王五', 1, '')")
    )
    db_session.commit()
    uid = db_session.execute(text("SELECT id FROM users")).scalar()

    r = client.put(f"/users/{uid}", json={"hobbies": "跑步、摄影"})
    assert r.status_code == 200
    assert r.json()["hobbies"] == "跑步、摄影"


# ---------- 简历 ----------
def _insert_resume(db_session, user_id, progress=None):
    db_session.execute(
        text("INSERT INTO resumes (user_id, jd_text, jd_summary, target_position, sections, "
             "status, questions, answers, fabricated, interview_prep, se_questions, se_answers, "
             "skills_curated, progress, personal_summary, self_evaluation, output_path) "
             "VALUES (:user_id, 'jd-text', '[]', '', '[]', 'draft', '[]', '[]', '[]', '{}', "
             "'[]', '[]', '[]', :progress, '', '', '')"),
        {"user_id": user_id, "progress": progress},
    )
    db_session.commit()


def test_list_resumes_with_null_progress(client, db_session):
    # 模拟旧数据：progress 列为 NULL
    db_session.execute(
        text("INSERT INTO users (name, is_active, hobbies) VALUES ('赵六', 1, '')")
    )
    db_session.commit()
    uid = db_session.execute(text("SELECT id FROM users")).scalar()
    _insert_resume(db_session, uid, progress=None)

    r = client.get("/resumes")
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["progress"] == ""


def test_get_resume_by_id(client, db_session):
    db_session.execute(
        text("INSERT INTO users (name, is_active, hobbies) VALUES ('钱七', 1, '')")
    )
    db_session.commit()
    uid = db_session.execute(text("SELECT id FROM users")).scalar()
    _insert_resume(db_session, uid, progress="")
    rid = db_session.execute(text("SELECT id FROM resumes")).scalar()

    r = client.get(f"/resumes/{rid}")
    assert r.status_code == 200
    assert r.json()["status"] == "draft"


# ---------- 全流程回顾 / 回退 ----------
def _seed_full_resume(db_session):
    """插入一条已走完全部生成流程的简历，返回其 id。"""
    user = models.User(name="测试", is_active=True)
    db_session.add(user)
    db_session.commit()
    resume = models.Resume(
        user_id=user.id, jd_text="jd", jd_summary={"position": "后端开发"},
        questions=[{"id": "q1", "question": "Q1"}],
        answers=[{"id": "q1", "question": "Q1", "answer": "A1"}],
        fabricated=[{"type": "project", "title": "P1", "name": "P1",
                     "start_date": "2024.01", "end_date": "2024.06",
                     "role": "后端", "description": "做了**后端开发**", "result": "上线"}],
        interview_prep={"knowledge_points": ["k1"]},
        se_questions=[{"id": "s1", "question": "S1"}],
        se_answers=[{"id": "s1", "question": "S1", "answer": "SA"}],
        skills_curated=[{"name": "Python"}],
        personal_summary="简介", self_evaluation="评价",
        output_path="/tmp/x.docx", output_paths={"classic": "/tmp/x.docx"},
        status="generated",
    )
    db_session.add(resume)
    db_session.commit()
    return resume.id


def test_review_aggregates_progress_and_versions(client, db_session):
    rid = _seed_full_resume(db_session)
    db_session.add(models.ProgressEvent(resume_id=rid, message="正在解析岗位 JD…"))
    db_session.add(models.ProgressEvent(resume_id=rid, message="正在排版生成简历文档…"))
    db_session.add(models.FabricateVersion(
        resume_id=rid, version=1, feedback="", experiences=[{"title": "初稿"}]))
    db_session.add(models.FabricateVersion(
        resume_id=rid, version=2, feedback="更正式一些", experiences=[{"title": "二稿"}]))
    db_session.commit()

    r = client.get(f"/resumes/{rid}/review")
    assert r.status_code == 200
    data = r.json()
    assert data["resume"]["id"] == rid
    assert [e["message"] for e in data["progress_events"]] == [
        "正在解析岗位 JD…", "正在排版生成简历文档…"]
    assert [v["version"] for v in data["fabricate_versions"]] == [1, 2]
    assert data["fabricate_versions"][1]["feedback"] == "更正式一些"


def test_rollback_to_se_keeps_qa_clears_outputs(client, db_session):
    rid = _seed_full_resume(db_session)
    r = client.post(f"/resumes/{rid}/rollback", json={"step": "se"})
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "answered"
    assert d["questions"] and d["answers"]
    assert d["se_questions"] and d["se_answers"]
    assert d["personal_summary"] == "" and d["self_evaluation"] == ""
    assert d["output_path"] == "" and d["output_paths"] == {}
    assert d["skills_curated"] == []


def test_rollback_to_questions_clears_se(client, db_session):
    rid = _seed_full_resume(db_session)
    r = client.post(f"/resumes/{rid}/rollback", json={"step": "questions"})
    d = r.json()
    assert d["status"] == "questioning"
    assert d["questions"] and d["answers"]
    assert d["se_questions"] == [] and d["se_answers"] == []


def test_rollback_to_fabricate_keeps_draft(client, db_session):
    rid = _seed_full_resume(db_session)
    r = client.post(f"/resumes/{rid}/rollback", json={"step": "fabricate"})
    d = r.json()
    assert d["status"] == "parsed"
    assert d["fabricated"]
    assert d["interview_prep"] == {}
    assert d["questions"] == [] and d["answers"] == []


def test_rollback_to_jd_clears_all_downstream(client, db_session):
    rid = _seed_full_resume(db_session)
    r = client.post(f"/resumes/{rid}/rollback", json={"step": "jd"})
    d = r.json()
    assert d["status"] == "parsed"
    assert d["jd_summary"]["position"] == "后端开发"
    assert d["fabricated"] == [] and d["questions"] == []
    assert d["output_path"] == ""


def test_rollback_records_event_and_rejects_bad_step(client, db_session):
    rid = _seed_full_resume(db_session)
    r = client.post(f"/resumes/{rid}/rollback", json={"step": "bogus"})
    assert r.status_code == 400

    client.post(f"/resumes/{rid}/rollback", json={"step": "jd"})
    r = client.get(f"/resumes/{rid}/review")
    msgs = [e["message"] for e in r.json()["progress_events"]]
    assert any("回退" in m for m in msgs)


# ---------- 网页模板（kind=vue） ----------
def test_templates_include_vue_kind(client):
    r = client.get("/resumes/templates")
    assert r.status_code == 200
    by_key = {t["key"]: t for t in r.json()}
    assert by_key["warm_vue"]["kind"] == "vue"
    assert by_key["classic"]["kind"] == "docx"


def test_render_context_matches_render_fields(client, db_session):
    rid = _seed_full_resume(db_session)
    r = client.get(f"/resumes/{rid}/render-context")
    assert r.status_code == 200
    d = r.json()
    # 与 build_resume_docx 入参一一对应的字段
    for key in ("user", "jd_summary", "personal_summary", "self_evaluation",
                "target_position", "sections", "fabricated", "skills_curated",
                "expected_salary", "include_salary", "length", "custom_pages",
                "template", "budget"):
        assert key in d
    assert d["user"]["name"] == "测试"
    assert d["jd_summary"]["position"] == "后端开发"
    assert d["fabricated"][0]["title"] == "P1"
    assert d["personal_summary"] == "简介"
    assert d["budget"]["max_experiences"] >= 1


def test_rebuild_vue_template_only_saves_choice(client, db_session):
    """网页版模板：rebuild 仅持久化选择，不生成/改动 docx 文件。"""
    rid = _seed_full_resume(db_session)
    r = client.post(f"/resumes/{rid}/rebuild", json={"template": "warm_vue"})
    assert r.status_code == 200
    d = r.json()
    assert d["template"] == "warm_vue"
    assert d["output_path"] == "/tmp/x.docx"  # 原有 docx 产物保持不变


def test_update_resume_editable_fields(client, db_session):
    """详情页编辑：个人简介/自我评价/包含模块可更新，未传字段保持不变。"""
    rid = _seed_full_resume(db_session)
    r = client.put(f"/resumes/{rid}", json={
        "personal_summary": "改后**简介**",
        "sections": ["summary", "education"],
    })
    assert r.status_code == 200
    d = r.json()
    assert d["personal_summary"] == "改后**简介**"
    assert d["sections"] == ["summary", "education"]
    assert d["self_evaluation"] == "评价"  # 未传字段不变

    r = client.put(f"/resumes/{rid}", json={"self_evaluation": "改后评价"})
    assert r.json()["self_evaluation"] == "改后评价"
    assert r.json()["personal_summary"] == "改后**简介**"


def test_rebuild_vue_to_docx_renders_without_output_path(client, db_session):
    """跨板块切换：网页版（无 docx 产物）切回 Word 模板时应直接渲染成功。"""
    rid = _seed_full_resume(db_session)
    resume = db_session.get(models.Resume, rid)
    resume.template = "warm_vue"
    resume.output_path = ""
    resume.output_paths = {}
    db_session.commit()

    r = client.post(f"/resumes/{rid}/rebuild", json={"template": "classic"})
    assert r.status_code == 200
    d = r.json()
    assert d["template"] == "classic"
    assert d["output_path"].endswith(".docx")


def test_merge_sections_sorted_new_to_old():
    """经历合并后按时间新→旧排序：「至今」最前，无结束时间用开始时间。"""
    from types import SimpleNamespace
    from app.services import resume_generator

    user = SimpleNamespace(
        projects=[SimpleNamespace(title="旧项目", start_date="2022.01", end_date="2022.06")],
        internships=[],
    )
    fabricated = [
        {"type": "project", "title": "新项目", "start_date": "2025.01", "end_date": "至今"},
        {"type": "work", "title": "A厂", "role": "后端", "start_date": "2023.01", "end_date": "2024.06"},
        {"type": "work", "title": "B厂", "role": "后端", "start_date": "2024.07", "end_date": "至今"},
    ]
    projects, _, works, _ = resume_generator._merge_sections(user, fabricated)
    assert projects[0].title == "新项目"
    assert [w.company for w in works] == ["B厂", "A厂"]


def test_resume_basename_naming():
    """产物规范命名：姓名-xx届-求职意向；缺失省略，姓名兜底，非法字符清除。"""
    from types import SimpleNamespace
    from app.services import resume_generator

    base = resume_generator._resume_basename
    # 完整信息：2026 -> 26届
    u = SimpleNamespace(name="张三", graduation_date="2026.07", target_position="")
    assert base(u, "后端开发") == "张三-26届-后端开发"
    # 求职意向回退到档案值
    u2 = SimpleNamespace(name="张三", graduation_date="2026.07", target_position="AI Agent 开发")
    assert base(u2) == "张三-26届-AI Agent 开发"
    # 缺毕业日期/意向 → 省略
    u3 = SimpleNamespace(name="李四", graduation_date="", target_position="")
    assert base(u3, "") == "李四"
    # 无姓名 → 兜底
    u4 = SimpleNamespace(name="", graduation_date="2026.07", target_position="后端")
    assert base(u4) == "简历-26届-后端"
    # 非法文件名字符被清除
    u5 = SimpleNamespace(name="王/五", graduation_date="2026.07", target_position="后:端")
    assert base(u5, "") == "王五-26届-后端"


def test_avatar_upload_and_delete(client, db_session):
    """头像上传：保存文件、返回 /static 相对路径；删除后字段清空、文件移除。"""
    from app.config import AVATAR_DIR

    uid = client.post("/users", json={"name": "头像用户"}).json()["id"]

    png = b"\x89PNG\r\n\x1a\n" + b"0" * 32
    r = client.post(f"/users/{uid}/avatar", files={"file": ("a.png", png, "image/png")})
    assert r.status_code == 200
    avatar = r.json()["avatar"]
    assert avatar.startswith("/static/avatars/avatar_") and avatar.endswith(".png")
    assert (AVATAR_DIR / Path(avatar).name).read_bytes() == png

    # 非图片扩展拒绝
    r = client.post(f"/users/{uid}/avatar", files={"file": ("a.txt", b"x", "text/plain")})
    assert r.status_code == 400

    # 删除
    r = client.delete(f"/users/{uid}/avatar")
    assert r.status_code == 200
    assert r.json()["avatar"] == ""
    assert not (AVATAR_DIR / Path(avatar).name).exists()


def test_template_registry_contains_navy_vue(client):
    r = client.get("/resumes/templates")
    assert r.status_code == 200
    tpl = {t["key"]: t for t in r.json()}
    assert tpl["navy_vue"]["kind"] == "vue"