"""经历杜撰 Agent + 面试准备生成。

在「解析 JD」与「回答必要问题」之间提供可选杜撰：
- 杜撰：根据 JD 生成匹配、可自圆其说的项目/实习经历，填充简历空白。
- 不杜撰：使用用户档案中已有经历（本服务直接跳过生成）。
无论是否杜撰，都会生成「面试准备包」（重点记忆知识点 + 高频面试问题）。
"""
import json
from datetime import datetime

from . import llm_client
from .prompting import get_length_budget, length_hint, render_prompt

_ALLOWED = ("project", "internship", "work", "other")

_TYPE_LABELS = {
    "project": "项目经历",
    "internship": "实习经历",
    "work": "全职经历",
    "other": "其他经历",
}


def _parse_experiences(raw: str) -> list:
    """解析 LLM 返回的经历蓝本 JSON，统一字段并兜底。"""
    try:
        data = json.loads(raw)
    except Exception:
        data = {}
    exps = data.get("experiences") if isinstance(data, dict) else None
    if not isinstance(exps, list):
        return []
    out = []
    for it in exps:
        if not isinstance(it, dict) or not it.get("type"):
            continue
        t = it.get("type")
        if t not in _ALLOWED:
            t = "project"
        out.append({
            "type": t,
            "title": it.get("title") or "",
            "role": it.get("role") or "",
            "tech_stack": it.get("tech_stack") or "",
            "start_date": it.get("start_date") or "",
            "end_date": it.get("end_date") or "",
            "description": it.get("description") or "",
            "result": it.get("result") or "",
        })
    return out


def _skills_experiences(user_profile: dict) -> str:
    """抽取求职者技能（含熟练度）与现有经历，作为杜撰的「真实基础」。"""
    skills = [
        {"category": s.get("category", ""), "name": s.get("name", ""),
         "proficiency": s.get("proficiency", "")}
        for s in user_profile.get("skills", [])
    ]
    return json.dumps({
        "技能及熟练度": skills,
        "现有实习经历": user_profile.get("internships", []),
        "现有项目经历": user_profile.get("projects", []),
    }, ensure_ascii=False)


def _time_context(user_profile: dict) -> dict:
    """杜撰用时间上下文：当前日期 + 用户毕业日期，约束经历时间线的合理性。"""
    return {
        "current_date": datetime.now().strftime("%Y-%m-%d"),
        "graduation_date": user_profile.get("graduation_date") or "（未填写）",
    }


async def fabricate_experiences(
    jd_summary: dict,
    user_profile: dict,
    base_url: str,
    api_key: str,
    model: str,
    types: list | None = None,
    count: int = 3,
    extra_jd: str = "",
    length: str = "fresh",
    custom_pages: int | None = None,
) -> list:
    """按用户选择的类型、数量与篇幅，生成与 JD 高度匹配的经历蓝本。

    types 取值子集：project（项目经历）/ internship（实习经历）/ work（全职经历）/ other（其他经历）。
    extra_jd 为用户填写的「其他岗位 JD」（真实存在的公司与岗位），用于提升经历的真实性。
    length/custom_pages 为简历篇幅选项，用于约束生成经历的数量与篇幅。
    """
    allowed = _ALLOWED
    if not types:
        types = ["project", "internship"]
    types = [t for t in types if t in allowed] or ["project", "internship"]

    budget = get_length_budget(length, custom_pages)
    count = max(1, min(int(count or 3), budget["fabricate_max"]))

    selected = "、".join(_TYPE_LABELS[t] for t in types)

    extra_block = ""
    if extra_jd and extra_jd.strip():
        extra_block = (
            f"参考 JD（其他岗位，公司/岗位真实存在）：{extra_jd.strip()}\n"
            "请优先以该 JD 中的公司与岗位为蓝本生成经历。\n"
        )

    system, prompt = render_prompt(
        "fabricate_experiences",
        count=count,
        types=selected,
        extra_block=extra_block,
        length_hint=length_hint(budget),
        jd_summary=json.dumps(jd_summary, ensure_ascii=False),
        skills_experiences=_skills_experiences(user_profile),
        **_time_context(user_profile),
    )
    raw = await llm_client.chat(
        base_url, api_key, model,
        [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        temperature=0.7, json_mode=True,
    )
    return _parse_experiences(raw)


async def revise_experiences(
    jd_summary: dict,
    user_profile: dict,
    experiences: list,
    feedback: str,
    base_url: str,
    api_key: str,
    model: str,
) -> list:
    """在用户修改后的经历蓝本基础上，根据意见让 AI 调整/重写。"""
    system, prompt = render_prompt(
        "revise_experiences",
        experiences=json.dumps(experiences, ensure_ascii=False),
        feedback=feedback or "（无，请优化措辞与量化成果、增强与 JD 的匹配度）",
        jd_summary=json.dumps(jd_summary, ensure_ascii=False),
        user_profile=json.dumps(user_profile, ensure_ascii=False),
        **_time_context(user_profile),
    )
    raw = await llm_client.chat(
        base_url, api_key, model,
        [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        temperature=0.6, json_mode=True,
    )
    return _parse_experiences(raw)


async def generate_interview_prep(
    jd_summary: dict,
    user_profile: dict,
    experiences: list,
    base_url: str,
    api_key: str,
    model: str,
) -> dict:
    """生成面试准备包：重点记忆知识点 + 高频面试问题（是否杜撰都会生成）。"""
    system, prompt = render_prompt(
        "interview_prep",
        jd_summary=json.dumps(jd_summary, ensure_ascii=False),
        user_profile=json.dumps(user_profile, ensure_ascii=False),
        experiences=json.dumps(experiences, ensure_ascii=False),
    )
    raw = await llm_client.chat(
        base_url, api_key, model,
        [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        temperature=0.5, json_mode=True,
    )
    try:
        data = json.loads(raw)
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}
    kp = data.get("knowledge_points") if isinstance(data.get("knowledge_points"), list) else []
    questions = data.get("high_freq_questions") if isinstance(data.get("high_freq_questions"), list) else []
    return {
        "knowledge_points": kp,
        "high_freq_questions": [
            q if isinstance(q, dict) else {"question": str(q), "hint": ""}
            for q in questions
        ],
    }