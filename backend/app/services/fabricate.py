"""经历杜撰 Agent + 面试准备生成。

在「解析 JD」与「回答必要问题」之间提供可选杜撰：
- 杜撰：根据 JD 生成 2~3 段匹配、可自圆其说的项目/实习经历，填充简历空白。
- 不杜撰：使用用户档案中已有经历（本服务直接跳过生成）。
无论是否杜撰，都会生成「面试准备包」（重点记忆知识点 + 高频面试问题）。
"""
import json

from . import llm_client

_SYSTEM = "你是一名资深简历与面试辅导专家，擅长根据岗位 JD 为求职者定制经历蓝本与面试准备。"

_ALLOWED = ("project", "internship", "work", "other")


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


async def fabricate_experiences(
    jd_summary: dict,
    user_profile: dict,
    base_url: str,
    api_key: str,
    model: str,
    types: list | None = None,
    count: int = 3,
    extra_jd: str = "",
) -> list:
    """按用户选择的类型与数量，生成与 JD 高度匹配的经历蓝本。

    types 取值子集：project（项目经历）/ internship（实习经历）/ work（全职经历）/ other（其他经历）。
    extra_jd 为用户填写的「其他岗位 JD」（真实存在的公司与岗位），用于提升经历的真实性。
    """
    allowed = _ALLOWED
    if not types:
        types = ["project", "internship"]
    types = [t for t in types if t in allowed] or ["project", "internship"]
    count = max(1, min(int(count or 3), 5))

    type_labels = {
        "project": "项目经历",
        "internship": "实习经历",
        "work": "全职经历",
        "other": "其他经历",
    }
    selected = "、".join(type_labels[t] for t in types)

    extra_block = ""
    if extra_jd and extra_jd.strip():
        extra_block = (
            f"参考 JD（其他岗位，公司/岗位真实存在）：{extra_jd.strip()}\n"
            "请优先以该 JD 中的公司与岗位为蓝本生成经历。\n"
        )

    prompt = (
        "请根据岗位 JD 与求职者背景，为其「杜撰」经历蓝本，用于填充简历空白。\n"
        f"本次需要生成 {count} 段经历，类型限定为：{selected}（可混合，仅使用这几类）。\n"
        + extra_block +
        "真实性要求：公司名与岗位名应真实存在（可取自 JD），职责与 JD 呼应、技术栈匹配；"
        "求职者并未真实入职，但内容需自洽、可量化、经得起面试追问。\n"
        "量化数据与成果在 description、result 中用 ** 包裹（如 **QPS 提升 50%**），用于加粗高亮，"
        "不要使用其他 markdown 语法。\n"
        "只返回 JSON（不要 markdown 代码块、不要额外文字），结构如下：\n"
        '{"experiences":['
        '{"type":"project|internship|work|other","title":"项目名/公司名","role":"角色/职位","tech_stack":"技术栈",'
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
    prompt = (
        "以下是已生成的经历蓝本（用户可能已做了部分修改）。请根据用户的修改意见，"
        "在现有蓝本基础上调整，尽量保留用户已改好的部分，只针对意见修改，不要无中生有地删改其他部分。\n"
        "量化数据与成果在 description、result 中用 ** 包裹（如 **QPS 提升 50%**），用于加粗高亮，"
        "不要使用其他 markdown 语法。\n"
        "只返回 JSON（不要 markdown 代码块、不要额外文字），结构与输入一致：\n"
        '{"experiences":['
        '{"type":"project|internship|work|other","title":"项目名/公司名","role":"角色/职位","tech_stack":"技术栈",'
        '"start_date":"YYYY.MM","end_date":"YYYY.MM","description":"核心工作","result":"量化成果"}'
        "]}\n\n"
        f"当前经历蓝本：{json.dumps(experiences, ensure_ascii=False)}\n"
        f"用户修改意见：{feedback or '（无，请优化措辞与量化成果、增强与 JD 的匹配度）'}\n"
        f"岗位 JD 解析：{json.dumps(jd_summary, ensure_ascii=False)}\n"
        f"求职者档案：{json.dumps(user_profile, ensure_ascii=False)}"
    )
    raw = await llm_client.chat(
        base_url, api_key, model,
        [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": prompt}],
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