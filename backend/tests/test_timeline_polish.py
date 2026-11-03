"""时间线规划/校验与经历润色的回归测试。"""
from datetime import date
from types import SimpleNamespace

from app import crypto, models
from app.services import polish, resume_generator, timeline

TODAY = date(2026, 10, 1)


def _prof(grad="2024.06", edu_start="2020.09", internships=None, projects=None):
    return {
        "graduation_date": grad,
        "educations": [{"start_date": edu_start, "end_date": grad}] if grad else [],
        "internships": internships or [],
        "projects": projects or [],
    }


# ---------- 时间窗口规划 ----------
def test_plan_graduate_fills_gap_and_ends_present():
    """已毕业：真实实习到 2025.06，之后空窗必须由全职窗口补齐，末段结束于「至今」。"""
    prof = _prof(internships=[
        {"company": "A厂", "start_date": "2024.07", "end_date": "2025.06"}])
    plan = timeline.build_timeline_plan(prof, ["work"], 1, today=TODAY)
    assert len(plan["work"]) == 1
    w = plan["work"][0]
    assert w["start_date"] == "2025.07"
    assert w["end_date"] == "至今"


def test_plan_work_starts_at_graduation_month():
    """毕业即就业：首个全职窗口起点为毕业当月，不制造毕业后空窗。"""
    prof = _prof(internships=[
        {"company": "A厂", "start_date": "2025.09", "end_date": "至今"}])
    plan = timeline.build_timeline_plan(prof, ["work"], 2, today=TODAY)
    assert plan["work"][0]["start_date"] == "2024.06"
    for w in plan["work"]:
        assert timeline.parse_ym(w["start_date"]) >= timeline.parse_ym("2024.06")


def test_plan_student_no_work_before_graduation():
    """应届生（未毕业）：不得规划全职窗口，实习窗口必须在毕业前。"""
    prof = _prof(grad="2027.06", edu_start="2023.09", internships=[
        {"company": "A厂", "start_date": "2026.07", "end_date": "2026.09"}])
    plan = timeline.build_timeline_plan(prof, ["internship", "work"], 3, today=TODAY)
    assert plan["work"] == []
    grad_ord = timeline.parse_ym("2027.06")
    now_ord = timeline.to_ord(2026, 10)
    occupied = [(timeline.parse_ym("2026.07"), timeline.parse_ym("2026.09"))]
    for w in plan["internship"]:
        s = timeline.parse_ym(w["start_date"])
        we = now_ord if timeline.is_present(w["end_date"]) else timeline.parse_ym(w["end_date"])
        assert s < grad_ord
        # 不与真实实习重叠
        assert all(we < os_ or s > oe for os_, oe in occupied)


def test_plan_projects_within_school_years_no_overlap():
    prof = _prof(grad="2027.06", edu_start="2023.09", projects=[
        {"title": "旧项目", "start_date": "2026.03", "end_date": "2026.05"}])
    plan = timeline.build_timeline_plan(prof, ["project"], 3, today=TODAY)
    assert len(plan["project"]) == 3
    edu = timeline.parse_ym("2023.09")
    now_ord = timeline.to_ord(2026, 10)
    intervals = []
    for w in plan["project"]:
        s = timeline.parse_ym(w["start_date"])
        e = now_ord if timeline.is_present(w["end_date"]) else timeline.parse_ym(w["end_date"])
        assert s >= edu and e <= now_ord
        intervals.append((s, e))
    # 项目窗口互不重叠
    intervals.sort()
    for (_, e1), (s2, _) in zip(intervals, intervals[1:]):
        assert s2 > e1


# ---------- 日期纠偏 ----------
def test_normalize_clamps_future_and_reverses():
    out = timeline.normalize_experiences(
        [{"start_date": "2030.01", "end_date": "2023-1"}], now_ord=timeline.to_ord(2026, 10))
    x = out[0]
    assert x["start_date"] == "2023.01"
    assert x["end_date"] == "至今"


def test_enforce_plan_overrides_llm_dates():
    plan = {"internship": [{"start_date": "2026.03", "end_date": "2026.06"}],
            "work": [], "project": [], "other": []}
    exps = [{"type": "internship", "start_date": "2010.01", "end_date": "2011.01",
             "title": "X", "description": "", "result": ""}]
    out = timeline.enforce_plan(exps, plan, _prof(), today=TODAY)
    assert out[0]["start_date"] == "2026.03"
    assert out[0]["end_date"] == "2026.06"


# ---------- 时间线体检 ----------
def test_validate_clean_timeline_no_warning():
    prof = _prof(internships=[
        {"company": "A厂", "start_date": "2024.07", "end_date": "2025.06"}])
    fab = [{"type": "work", "title": "B厂", "role": "工程师",
            "start_date": "2025.07", "end_date": "至今"}]
    assert timeline.validate_timeline(prof, fab, today=TODAY) == []


def test_validate_detects_post_grad_gap():
    prof = _prof(internships=[
        {"company": "A厂", "start_date": "2024.07", "end_date": "2025.06"}])
    fab = [{"type": "work", "title": "B厂",
            "start_date": "2026.02", "end_date": "至今"}]
    warnings = timeline.validate_timeline(prof, fab, today=TODAY)
    assert any("空档" in w for w in warnings)


def test_validate_detects_work_before_graduation():
    fab = [{"type": "work", "title": "X厂",
            "start_date": "2023.09", "end_date": "2024.01"}]
    warnings = timeline.validate_timeline(_prof(), fab, today=TODAY)
    assert any("早于毕业" in w for w in warnings)


def test_validate_detects_overlap():
    prof = _prof(internships=[
        {"company": "A厂", "start_date": "2025.03", "end_date": "2025.12"}])
    fab = [{"type": "work", "title": "B厂",
            "start_date": "2025.09", "end_date": "2026.03"}]
    warnings = timeline.validate_timeline(prof, fab, today=TODAY)
    assert any("重叠" in w for w in warnings)


def test_validate_polished_internships_not_false_overlap():
    """润色稿是档案实习的替代稿，时间段相同，不应误报重叠。"""
    intern = {"company": "A厂", "start_date": "2025.09", "end_date": "至今"}
    prof = _prof(internships=[intern])
    polished = [{"type": "internship", "title": "A厂",
                 "start_date": "2025.09", "end_date": "至今"}]
    warnings = timeline.validate_timeline(prof, [], polished=polished, today=TODAY)
    assert not any("重叠" in w for w in warnings)


# ---------- 润色：事实锁定 ----------
def test_preserve_identity_keeps_facts_takes_wording():
    originals = polish.collect_real_experiences({
        "internships": [{"company": "真实公司", "position": "后端实习",
                         "start_date": "2025.03", "end_date": "2025.09",
                         "description": "写接口", "achievement": ""}],
        "projects": [],
    })
    llm_returned = [{"type": "internship", "ref_id": "internship-0",
                     "title": "AI 编的公司", "role": "架构师",
                     "tech_stack": "Rust", "start_date": "2020.01", "end_date": "2020.08",
                     "description": "负责 **FastAPI** 接口设计", "result": "**响应提速 40%**"}]
    out = polish.preserve_identity(originals, llm_returned)
    assert out[0]["title"] == "真实公司"
    assert out[0]["role"] == "后端实习"
    assert out[0]["start_date"] == "2025.03"
    assert "FastAPI" in out[0]["description"]
    assert "40%" in out[0]["result"]


def test_preserve_identity_keeps_dropped_item():
    originals = polish.collect_real_experiences({
        "internships": [],
        "projects": [
            {"title": "P1", "start_date": "2025.01", "end_date": "2025.03",
             "description": "d1", "result": ""},
            {"title": "P2", "start_date": "2025.04", "end_date": "2025.06",
             "description": "d2", "result": ""},
        ],
    })
    llm_returned = [{"type": "project", "ref_id": "project-0",
                     "title": "P1", "description": "润色1", "result": ""}]
    out = polish.preserve_identity(originals, llm_returned)
    assert [x["title"] for x in out] == ["P1", "P2"]
    assert out[0]["description"] == "润色1"
    assert out[1]["description"] == "d2"  # LLM 漏还：保留原文，不丢经历


# ---------- 渲染合并 ----------
def test_merge_sections_polished_replaces_real_base():
    user = SimpleNamespace(
        projects=[SimpleNamespace(title="真实项目", start_date="2025.01", end_date="2025.03")],
        internships=[SimpleNamespace(company="真实公司", position="实习生",
                                     start_date="2025.04", end_date="2025.09",
                                     description="原文", achievement="")],
    )
    polished = [
        {"type": "internship", "title": "真实公司", "role": "实习生",
         "start_date": "2025.04", "end_date": "2025.09",
         "description": "**润色后**", "result": "成果"},
    ]
    projects, internships, _, _ = resume_generator._merge_sections(
        user, fabricated=[], polished=polished)
    assert internships[0].description == "**润色后**"
    assert projects[0].title == "真实项目"  # 未润色的类型仍用档案原文


# ---------- 接口 ----------
def _client_with_user(client, db_session, with_internship=True):
    client.post("/users", json={"name": "时间线", "graduation_date": "2024.06",
                                "target_position": "后端"})
    user = db_session.query(models.User).filter(models.User.is_active.is_(True)).first()
    if with_internship:
        db_session.add(models.Internship(
            user_id=user.id, company="真实公司", position="后端实习",
            start_date="2025.03", end_date="至今",
            description="写接口", achievement=""))
        db_session.commit()
    r = client.post("/resumes", json={"jd_text": "jd", "jd_summary_unused": True})
    return r.json()["id"]


def test_polish_save_persists_locks_facts_and_context_exposes(client, db_session):
    rid = _client_with_user(client, db_session)
    payload = {"experiences": [
        {"type": "internship", "ref_id": "internship-0",
         # 试图篡改事实字段：公司/时间必须被档案覆盖
         "title": "AI 编的公司", "role": "架构师",
         "start_date": "2020.01", "end_date": "2020.08",
         "description": "润色", "result": "**提效 30%**"}]}
    r = client.post(f"/resumes/{rid}/polish/save", json=payload)
    assert r.status_code == 200
    item = r.json()["polished_experiences"][0]
    assert item["title"] == "真实公司"          # 事实被服务端锁回档案
    assert item["start_date"] == "2025.03"
    assert item["end_date"] == "至今"
    assert item["result"] == "**提效 30%**"    # 只接受表述
    assert "timeline_warnings" in r.json()

    r = client.get(f"/resumes/{rid}/render-context")
    d = r.json()
    assert d["polished_experiences"][0]["result"] == "**提效 30%**"
    assert "polished_experiences" in d and "timeline_warnings" in d


def test_fabricate_save_normalizes_dates(client, db_session):
    rid = _client_with_user(client, db_session, with_internship=False)
    r = client.post(f"/resumes/{rid}/fabricate/save", json={"experiences": [
        {"type": "work", "title": "X厂", "start_date": "2030.05", "end_date": "2024.01"},
        {"bad": True},  # 非法条目丢弃
    ]})
    assert r.status_code == 200
    items = r.json()["fabricated"]
    assert len(items) == 1
    assert items[0]["end_date"] == "至今"
    assert items[0]["start_date"] == "2024.01"


def test_real_mode_clears_fabricated_and_polished(client, db_session):
    rid = _client_with_user(client, db_session)
    client.post(f"/resumes/{rid}/polish/save", json={"experiences": [
        {"type": "internship", "ref_id": "internship-0", "title": "真实公司",
         "role": "后端实习", "start_date": "2025.03", "end_date": "至今",
         "description": "润色稿", "result": ""}]})
    # 确认润色稿确实入库
    assert client.get(f"/resumes/{rid}/render-context").json()["polished_experiences"]
    # 补齐 LLM 配置（fabricate:false 不实际调用 LLM，但依赖守卫要求配置存在）
    db_session.add(models.LLMConfig(base_url="http://x", api_key=crypto.encrypt("k"), model="m"))
    db_session.commit()
    # 标记已解析，避免触发真实 JD 解析调用
    resume = db_session.get(models.Resume, rid)
    resume.jd_summary = {"position": "后端"}
    db_session.commit()

    r = client.post(f"/resumes/{rid}/fabricate", json={"fabricate": False})
    assert r.status_code == 200
    d = r.json()
    assert d["fabricated"] == []
    assert d["polished_experiences"] == []
