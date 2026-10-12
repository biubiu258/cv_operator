"""经历杜撰 Agent + 面试准备生成。

在「解析 JD」与「回答必要问题」之间提供可选杜撰：
- 杜撰：根据 JD 生成 2~3 段匹配、可自圆其说的项目/实习经历，填充简历空白。
- 不杜撰：使用用户档案中已有经历（本服务直接跳过生成）。
无论是否杜撰，都会生成「面试准备包」（重点记忆知识点 + 高频面试问题）。
"""
import json

from . import llm_client

_SYSTEM = "你是一名资深简历与面试辅导专家，擅长根据岗位 JD 为求职者定制经历蓝本与面试准备。"


async def fabricate_experiences(
    jd_summary: dict,
    user_profile: dict,
    base_url: str,
    api_key: str,
    model: str,
) -> list:
    """生成 2~3 段与 JD 高度匹配的经历（项目/实习），统一字段便于写入简历。"""
    prompt = (
        "请根据岗位 JD 与求职者背景，为其「杜撰」2~3 段高度匹配、可自圆其说的经历（项目/实习），"
        "用于填充简历空白。要求：时间线合理、技术栈与 JD 呼应、成果可量化、内部逻辑自洽。\n"
        "只返回 JSON（不要 markdown 代码块、不要额外文字），结构如下：\n"
        '{"experiences":['
        '{"type":"project|internship","title":"项目名/公司名","role":"角色/职位","tech_stack":"技术栈",'
        '"start_date":"YYYY.MM","end_date":"YYYY.MM","description":"核心工作","result":"量化成果"}'
        "]}\n\n"
        f"岗位 JD 解析：{json.dumps(jd_summary, ensure_ascii=False)}\n"
        f"求职者档案：{json.dumps(user_profile, ensure_ascii=False)}"
    )
    raw = await llm_client.chat(
        base_url, api_key, model,
        [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": prompt}],
        temperature=0.7, json_mode=True,
    )
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
        out.append({
            "type": "internship" if it.get("type") == "internship" else "project",
            "title": it.get("title") or "",
            "role": it.get("role") or "",
            "tech_stack": it.get("tech_stack") or "",
            "start_date": it.get("start_date") or "",
            "end_date": it.get("end_date") or "",
            "description": it.get("description") or "",
            "result": it.get("result") or "",
        })
    return out


async def generate_interview_prep(
    jd_summary: dict,
    user_profile: dict,
    experiences: list,
    base_url: str,
    api_key: str,
    model: str,
) -> dict:
    """生成面试准备包：重点记忆知识点 + 高频面试问题（是否杜撰都会生成）。"""
    prompt = (
        "请为求职者生成「面试准备包」，帮其应对针对该岗位的面试。\n"
        "重点：1) 需要重点记忆/补强的知识点；2) 面试中大概率被问到的高频问题（含简洁答题要点）。\n"
        "只返回 JSON（不要 markdown 代码块、不要额外文字），结构：\n"
        '{"knowledge_points":["知识点及为何重要(一条)..."],'
        '"high_freq_questions":[{"question":"问题","hint":"答题要点/角度"}]}\n\n'
        f"岗位 JD 解析：{json.dumps(jd_summary, ensure_ascii=False)}\n"
        f"求职者档案：{json.dumps(user_profile, ensure_ascii=False)}\n"
        f"简历经历（可能含杜撰经历，请据此设计追问）：{json.dumps(experiences, ensure_ascii=False)}\n\n"
        "要求：知识点 4~6 条；高频问题 5~8 个，覆盖项目细节追问、技术栈原理、行为面试（如经历真实性/角色贡献）。"
    )
    raw = await llm_client.chat(
        base_url, api_key, model,
        [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": prompt}],
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