"""自我评价：问题集生成 + 按规范生成正文。"""
import json

from . import llm_client
from .prompting import render_prompt


async def generate_questions(
    jd_summary: dict,
    user_profile: dict,
    base_url: str,
    api_key: str,
    model: str,
) -> list:
    system, prompt = render_prompt(
        "self_eval_questions",
        jd_summary=json.dumps(jd_summary, ensure_ascii=False),
        user_profile=json.dumps(user_profile, ensure_ascii=False),
    )
    raw = await llm_client.chat(
        base_url, api_key, model,
        [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        temperature=0.4, json_mode=True,
    )

    questions = _parse_questions(raw)
    # 固定第一题：评价侧重方向，保证生成结果有明确主线
    focus = {
        "id": "focus",
        "type": "choice",
        "question": "本次自我评价想突出哪个方向？",
        "options": ["技术深度", "项目成果", "快速学习能力", "综合均衡"],
        "required": True,
        "topic": "评价侧重",
        "why": "决定整段自我评价的主线与篇幅分配",
        "hint": "选择最贴合该岗位要求的一项即可",
    }
    questions = [q for q in questions if (q.get("id") != "focus"
                 and "突出哪个方向" not in q.get("question", ""))]
    questions.insert(0, focus)
    # 程序代码补充"自由补充"题，允许为空
    questions.append({
        "id": "supplement",
        "type": "text",
        "question": "自由补充：还有哪些想强调、但上面没问到的亮点？",
        "options": [],
        "required": False,
        "topic": "自由补充",
        "why": "补充问答未覆盖的个性化亮点",
        "hint": "可留空；有具体成果或经历时再填写",
    })
    return questions


def _parse_questions(raw: str) -> list:
    try:
        data = json.loads(raw)
    except Exception:
        return _fallback_questions()
    if isinstance(data, dict):
        data = data.get("questions") or data.get("data") or []
    if not isinstance(data, list) or not data:
        return _fallback_questions()
    out = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            continue
        out.append({
            "id": str(item.get("id") or f"q{i + 1}"),
            "type": item.get("type") or "text",
            "question": item.get("question") or "",
            "options": item.get("options") or [],
            "required": bool(item.get("required", True)),
            "topic": str(item.get("topic") or ""),
            "why": str(item.get("why") or ""),
            "hint": str(item.get("hint") or ""),
        })
    return out or _fallback_questions()


def _fallback_questions() -> list:
    return [
        {"id": "q1", "type": "choice", "question": "本次自我评价想突出哪个方向？",
         "options": ["技术深度", "项目成果", "快速学习能力", "综合均衡"], "required": True,
         "topic": "评价侧重", "why": "确定自我评价主线",
         "hint": "选择最贴合岗位要求的一项"},
        {"id": "q2", "type": "multi", "question": "JD 中出现的能力要求，你实际具备哪些？",
         "options": ["Agent 开发", "LangChain", "RAG", "Prompt 工程", "后端开发"], "required": True,
         "topic": "能力匹配", "why": "确认与 JD 的关键能力匹配项",
         "hint": "只勾选能在项目或工作中找到事实支撑的项"},
        {"id": "q3", "type": "text", "question": "请用一句话描述你最有代表性的项目及其量化成果（如：校园问答 Agent，准确率 85%）。",
         "options": [], "required": True, "topic": "代表性项目",
         "why": "为自我评价提供最有说服力的成果",
         "hint": "写成「项目名 + 你的角色 + 可量化结果」"},
    ]


async def generate_self_evaluation(
    jd_summary: dict,
    user_profile: dict,
    answers: list,
    supplement: str,
    base_url: str,
    api_key: str,
    model: str,
    previous: str = "",
) -> str:
    system, prompt = render_prompt(
        "self_eval_generate",
        jd_summary=json.dumps(jd_summary, ensure_ascii=False),
        user_profile=json.dumps(user_profile, ensure_ascii=False),
        answers=json.dumps(answers, ensure_ascii=False),
        supplement=supplement or "（无）",
        previous=previous or "（无）",
    )
    return await llm_client.chat(
        base_url, api_key, model,
        [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        temperature=0.75 if previous else 0.6,
    )