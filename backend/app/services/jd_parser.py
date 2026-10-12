"""岗位 JD 解析。"""
import json

from . import llm_client

_SYSTEM = "你是一名资深技术招聘专家，擅长从岗位 JD 中提取结构化信息。"


async def parse_jd(jd_text: str, base_url: str, api_key: str, model: str) -> dict:
    prompt = (
        "请分析以下岗位 JD，提取关键信息，只返回 JSON（不要 markdown 代码块、不要多余文字），"
        "结构如下：\n"
        '{"position": "岗位名称", "tech": ["技术栈关键词"], "soft": ["软素质要求"], '
        '"domain": ["业务/领域方向"], "requirements": ["核心职责/要求摘要(逐条)"]}\n\n'
        "JD 内容：\n" + jd_text
    )
    raw = await llm_client.chat(
        base_url, api_key, model,
        [{"role": "system", "content": _SYSTEM},
         {"role": "user", "content": prompt}],
        temperature=0.2, json_mode=True,
    )
    try:
        data = json.loads(raw)
    except Exception:
        data = {}
    defaults = {"position": "", "tech": [], "soft": [], "domain": [], "requirements": []}
    for k, v in defaults.items():
        if k not in data or not isinstance(data[k], type(v)):
            data[k] = v
    return data