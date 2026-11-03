"""求职信生成：调用 LLM 撰写 200–300 字的岗位定制求职信。"""
from __future__ import annotations

import json

from . import llm_client
from .prompting import render_prompt


async def generate_cover_letter(
    jd_summary: dict,
    user_profile: dict,
    resume_content: str,
    base_url: str,
    api_key: str,
    model: str,
    target_position: str = "",
    tone: str = "professional",
) -> str:
    system, prompt = render_prompt(
        "cover_letter_generate",
        jd_summary=json.dumps(jd_summary, ensure_ascii=False),
        user_profile=json.dumps(user_profile, ensure_ascii=False),
        resume_content=resume_content,
        target_position=target_position or jd_summary.get("position") or "目标岗位",
        tone=("专业严谨" if tone == "professional"
              else "热情积极" if tone == "enthusiastic"
              else "简洁有力"),
        name=user_profile.get("name") or "求职者",
        contact=(user_profile.get("email")
                 or user_profile.get("phone")
                 or ""),
    )
    return await llm_client.chat(
        base_url, api_key, model,
        [{"role": "system", "content": system},
         {"role": "user", "content": prompt}],
        temperature=0.7,
    )


def word_count(text: str) -> int:
    return len(str(text or "").replace("\n", "").replace(" ", "").replace("\t", ""))
