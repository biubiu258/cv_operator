"""自我评价：问题集生成 + 按规范生成正文。"""
import json

from . import llm_client

_SYSTEM = "你是一名资深简历优化专家，尤其擅长撰写针对具体岗位定制化的自我评价。"

# 生成自我评价必须遵守的规范
_NORMS = """必须严格遵守以下《自我评价规范》：
1. 篇幅：3~5 句 / 100~180 字，控制在 5 行以内，不宜冗长。
2. 结构四要素：定位（一句话"我是谁 + 目标岗位"）、技术栈速览（回扣 JD）、最有说服力的项目成果（可量化）、软素质（用具体事实支撑，而非空话）。
3. 针对性强匹配：JD 高频关键词（技术栈 + 软素质 + 业务方向）至少命中 2~3 个，且每个关键词都要用具体事实支撑，而非单纯罗列。
4. 真实性：只使用档案与问答中已确认的真实信息，不虚构绩点/排名/获奖/项目数据；无法背书的表述降级为定性描述。
5. 量化：可量化成果必须带数字（准确率、响应时间、提升百分比、日均处理量等）；无数据时用"数量级 + 成果类型"的定性表述。
6. 语气：第一人称，自信、客观、克制；不用"我认为/我觉得"，直接陈述事实；不用绝对化词（精通/最/极致），用分级词（熟练/扎实/熟悉）。
7. 反套话：禁用"工作认真负责""吃苦耐劳""团队合作精神强""热爱学习"等无事实支撑表述；抽象词必须替换为具体行为/结果。
8. 末尾一句表达与岗位的匹配或求职动机，短而自然，不煽情。
9. 一致性：与技术栏、项目栏信息一致，不矛盾，时间线与技术名词准确。
10. 语言：中文书面语，技术名词保留英文原词。"""


async def generate_questions(
    jd_summary: dict,
    user_profile: dict,
    base_url: str,
    api_key: str,
    model: str,
) -> list:
    prompt = (
        "你需要为求职者设计一组用于撰写「自我评价」的问题，目的是挖掘真实素材、"
        "确定评价侧重方向、确认与 JD 的能力匹配项。\n"
        "要求：共 3~5 题，题型混合（单选 choice / 多选 multi / 描述 text）。\n"
        "只返回 JSON 数组（不要 markdown 代码块、不要额外文字），每项结构：\n"
        '{"id":"q1","type":"choice|multi|text","question":"问题内容","options":["选项A","选项B"],"required":true}\n'
        "其中 text 题型的 options 为空数组 []。\n\n"
        f"岗位 JD 解析结果：{json.dumps(jd_summary, ensure_ascii=False)}\n"
        f"求职者档案：{json.dumps(user_profile, ensure_ascii=False)}"
    )
    raw = await llm_client.chat(
        base_url, api_key, model,
        [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": prompt}],
        temperature=0.4, json_mode=True,
    )

    questions = _parse_questions(raw)
    # 程序代码补充"自由补充"题，允许为空
    questions.append({
        "id": "supplement",
        "type": "text",
        "question": "自由补充：还有哪些想强调、但上面没问到的亮点？",
        "options": [],
        "required": False,
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
        })
    return out or _fallback_questions()


def _fallback_questions() -> list:
    return [
        {"id": "q1", "type": "choice", "question": "本次自我评价想突出哪个方向？",
         "options": ["技术深度", "项目成果", "快速学习能力", "综合均衡"], "required": True},
        {"id": "q2", "type": "multi", "question": "JD 中出现的能力要求，你实际具备哪些？",
         "options": ["Agent 开发", "LangChain", "RAG", "Prompt 工程", "后端开发"], "required": True},
        {"id": "q3", "type": "text", "question": "请用一句话描述你最有代表性的项目及其量化成果（如：校园问答 Agent，准确率 85%）。",
         "options": [], "required": True},
    ]


async def generate_self_evaluation(
    jd_summary: dict,
    user_profile: dict,
    answers: list,
    supplement: str,
    base_url: str,
    api_key: str,
    model: str,
) -> str:
    prompt = (
        "请为求职者撰写一段定制化「自我评价」。\n\n"
        f"岗位 JD 解析结果：{json.dumps(jd_summary, ensure_ascii=False)}\n\n"
        f"求职者档案：{json.dumps(user_profile, ensure_ascii=False)}\n\n"
        f"用户对问题的回答：{json.dumps(answers, ensure_ascii=False)}\n\n"
        f"用户自由补充：{supplement or '（无）'}\n\n"
        + _NORMS +
        "\n\n只输出自我评价正文本身，不要标题、不要引号、不要多余说明。"
    )
    return await llm_client.chat(
        base_url, api_key, model,
        [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": prompt}],
        temperature=0.6,
    )