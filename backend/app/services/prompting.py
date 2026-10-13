"""提示词集中加载 + 简历篇幅配置。

所有提示词存放在仓库根目录 SKILLS/prompts/*.md，便于日后微调，无需改动代码。
每个 .md 文件使用两个标记段：
  # 系统提示词
  <system 正文>
  # 用户提示词
  <user 模板正文，占位符使用 $变量名>
"""
from pathlib import Path
from string import Template

from ..config import PROMPTS_DIR

_SYS_HDR = "# 系统提示词"
_USR_HDR = "# 用户提示词"


def load_prompt(name: str) -> tuple[str, str]:
    """读取指定提示词，返回 (系统提示词, 用户提示词模板)。"""
    raw = (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
    system, user = "", raw
    if _SYS_HDR in raw:
        _, rest = raw.split(_SYS_HDR, 1)
        if _USR_HDR in rest:
            system, user = rest.split(_USR_HDR, 1)
        else:
            system = rest
    return system.strip(), user.strip()


def render_prompt(name: str, **kwargs) -> tuple[str, str]:
    """读取并用变量替换用户提示词模板，返回 (系统提示词, 渲染后的用户提示词)。"""
    system, user = load_prompt(name)
    return system, Template(user).safe_substitute(**kwargs)


# ---------- 简历篇幅配置 ----------
# length 取值：fresh（应届/一页）、junior（1-5年/两页内）、senior（5年+/三页内）、custom（自定义）
LENGTH_PRESETS = {
    "fresh": {"pages": 1, "summary_max": 2, "max_skills": 8,
              "max_experiences": 2, "fabricate_max": 2,
              "label": "应届（目标一页）"},
    "junior": {"pages": 2, "summary_max": 3, "max_skills": 10,
               "max_experiences": 4, "fabricate_max": 3,
               "label": "1-5年（2页以内）"},
    "senior": {"pages": 3, "summary_max": 3, "max_skills": 14,
               "max_experiences": 6, "fabricate_max": 5,
               "label": "5年及以上（3页以内）"},
}


def get_length_budget(length: str = "fresh", custom_pages=None) -> dict:
    """根据篇幅选项返回内容预算字典。custom 时按自定义页数就近取档。"""
    if length == "custom":
        try:
            pages = max(1, int(custom_pages or 2))
        except (TypeError, ValueError):
            pages = 2
        key = "fresh" if pages <= 1 else ("junior" if pages <= 2 else "senior")
        budget = dict(LENGTH_PRESETS[key])
        budget["pages"] = pages
        budget["label"] = f"自定义（{pages}页）"
        return budget
    return dict(LENGTH_PRESETS.get(length, LENGTH_PRESETS["fresh"]))


def available_lengths() -> list:
    """返回篇幅选项列表，供前端渲染选择器。"""
    opts = [{"key": k, "label": v["label"]} for k, v in LENGTH_PRESETS.items()]
    opts.append({"key": "custom", "label": "自定义篇幅"})
    return opts


def length_hint(budget: dict) -> str:
    """根据篇幅预算生成给 LLM 的篇幅约束描述。"""
    pages = budget.get("pages", 1)
    if pages <= 1:
        return "整体控制在约一页：每段经历描述精炼，description / result 各控制在 2 句以内，避免堆砌无关内容。"
    if pages <= 2:
        return "整体控制在两页以内：每段经历 description / result 各 2~3 句，只突出与 JD 匹配的部分。"
    return "整体控制在三页以内：可适度展开，但每段仍紧扣 JD 匹配点与量化成果，不写无关内容。"