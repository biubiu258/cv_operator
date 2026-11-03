"""已有真实经历按 JD 润色。

与「杜撰」严格区分：不新增/删除经历、不改公司/岗位/时间/技术栈，
仅重写 description / result 的表达（STAR、JD 关键词、合理量化）。
LLM 返回后再由代码强制锁定事实字段，双重保证不变成虚构经历。
"""
import json

from . import llm_client, timeline
from .fabricate import _parse_experiences
from .prompting import get_length_budget, length_hint, render_prompt


def collect_real_experiences(user_profile: dict) -> list:
    """从档案抽取实习/项目经历，统一为杜撰经历同构的字段并编号 ref_id。"""
    items = []
    for i, it in enumerate(user_profile.get("internships", []) or []):
        items.append({
            "type": "internship",
            "ref_id": f"internship-{i}",
            "title": it.get("company") or "",
            "role": it.get("position") or "",
            "tech_stack": "",
            "start_date": it.get("start_date") or "",
            "end_date": it.get("end_date") or "",
            "description": it.get("description") or "",
            "result": it.get("achievement") or "",
        })
    for i, it in enumerate(user_profile.get("projects", []) or []):
        items.append({
            "type": "project",
            "ref_id": f"project-{i}",
            "title": it.get("title") or "",
            "role": it.get("role") or "",
            "tech_stack": it.get("tech_stack") or "",
            "start_date": it.get("start_date") or "",
            "end_date": it.get("end_date") or "",
            "description": it.get("description") or "",
            "result": it.get("result") or "",
        })
    return items


def select_experiences(originals: list, ref_ids: list | None) -> list:
    """按用户勾选的 ref_id 过滤真实经历；未勾选任何条目时返回空列表。

    ref_ids 为空（旧任务未使用选择功能）时保持历史行为：全部经历参与润色。
    """
    if not ref_ids:
        return originals
    wanted = set(ref_ids)
    return [x for x in originals if x.get("ref_id") in wanted]


def preserve_identity(originals: list, polished: list) -> list:
    """以档案事实字段为准逐字段锁定，只接受润色后的 description / result。

    LLM 漏还的条目用原文补齐（保证不丢经历），多还的条目丢弃（保证不虚构）。
    """
    by_ref = {x.get("ref_id"): x for x in polished if x.get("ref_id")}
    # ref_id 匹配失败时，仅「无 ref_id」的条目可按类型+顺序兜底，
    # 已被 ref 匹配的条目不参与兜底，避免一条润色结果被重复使用。
    fallback: dict = {}
    for x in polished:
        if not x.get("ref_id") or x.get("ref_id") not in by_ref:
            fallback.setdefault(x.get("type", "project"), []).append(x)

    out = []
    for orig in originals:
        cand = by_ref.get(orig["ref_id"])
        if cand is None:
            pool = fallback.get(orig["type"], [])
            cand = pool.pop(0) if pool else None
        if cand is None:
            out.append(dict(orig))  # 未润色到：保留原文，不丢经历
            continue
        merged = dict(orig)
        merged["description"] = cand.get("description") or orig["description"]
        merged["result"] = cand.get("result") or orig["result"]
        out.append(merged)
    return out


async def polish_experiences(
    jd_summary: dict,
    user_profile: dict,
    base_url: str,
    api_key: str,
    model: str,
    length: str = "fresh",
    custom_pages: int = None,
    ref_ids: list | None = None,
) -> list:
    """把档案中的真实实习/项目经历逐条对照 JD 润色，事实字段保持不变。

    ref_ids 为用户勾选参与润色的经历标识：只润色勾选条目，
    未勾选的经历既不润色也不写入简历。
    """
    originals = select_experiences(collect_real_experiences(user_profile), ref_ids)
    if not originals:
        return []
    budget = get_length_budget(length, custom_pages)
    system, prompt = render_prompt(
        "polish_experiences",
        length_hint=length_hint(budget),
        jd_summary=json.dumps(jd_summary, ensure_ascii=False),
        experiences=json.dumps(originals, ensure_ascii=False),
    )
    raw = await llm_client.chat(
        base_url, api_key, model,
        [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        temperature=0.5, json_mode=True,
    )
    polished = _parse_experiences(raw)
    return preserve_identity(originals, polished)


async def revise_polished(
    jd_summary: dict,
    experiences: list,
    feedback: str,
    base_url: str,
    api_key: str,
    model: str,
) -> list:
    """按用户意见微调润色结果，事实字段（含日期）以当前编辑稿为准锁定。"""
    if not experiences:
        return []
    system, prompt = render_prompt(
        "revise_polished_experiences",
        experiences=json.dumps(experiences, ensure_ascii=False),
        feedback=feedback or "（无，请进一步贴合 JD、加强量化与专业表达）",
        jd_summary=json.dumps(jd_summary, ensure_ascii=False),
    )
    raw = await llm_client.chat(
        base_url, api_key, model,
        [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        temperature=0.5, json_mode=True,
    )
    revised = _parse_experiences(raw)
    # 润色稿事实不可变：以当前稿为「原件」再锁一次，并规范化日期
    return timeline.normalize_experiences(preserve_identity(experiences, revised))
