"""岗位 JD 解析。"""
import json

from . import llm_client
from .prompting import render_prompt


async def parse_jd(jd_text: str, base_url: str, api_key: str, model: str) -> dict:
    system, prompt = render_prompt("jd_parse", jd_text=jd_text)
    raw = await llm_client.chat(
        base_url, api_key, model,
        [{"role": "system", "content": system},
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