"""ATS 关键词定向评分：从 JD 抽取关键词 → 扫描简历所有板块 → 输出命中/缺失/密度。

这个模块不依赖 LLM，纯字符串匹配 + 启发式打分，1ms 级别返回结果。
如果后续需要语义级匹配（同义技术栈、概念映射），可以加一个 LLM 增强接口，
但当前版本已经覆盖用户最常见的"JD 里写了 Kafka，简历里根本没提"场景。
"""
from __future__ import annotations

import re
from typing import Any


# 常见同义词映射：把"技术缩写"归一到一个 canonical 名字，
# 避免 JD 写"Python"简历写"PYTHON 3.14"被判未命中
_SYNONYM_MAP: dict[str, list[str]] = {
    "python": ["py", "python3", "py3", "python 3"],
    "javascript": ["js", "ecmascript"],
    "typescript": ["ts"],
    "react": ["reactjs", "react.js"],
    "vue": ["vuejs", "vue.js"],
    "node": ["nodejs", "node.js"],
    "fastapi": ["fast api"],
    "docker": ["docker容器"],
    "kubernetes": ["k8s", "k8's"],
    "mysql": ["mariadb"],
    "postgresql": ["postgres", "pg"],
    "redis": ["redis缓存"],
    "kafka": ["apache kafka"],
    "nginx": ["openresty"],
    "git": ["github", "gitlab"],
    "linux": ["centos", "ubuntu", "debian"],
    "微服务": ["微服务架构"],
    "高并发": ["高并发系统"],
    "分布式": ["分布式系统"],
}


def _normalize(text: str) -> str:
    """小写 + 去首尾空白 + 多空白折叠。"""
    text = str(text or "").lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text


def _expand(keyword: str) -> list[str]:
    """把一个关键词展开成所有可匹配形式（含同义词）。"""
    kw = _normalize(keyword)
    variants = {kw}
    for canonical, alts in _SYNONYM_MAP.items():
        if canonical == kw or any(_normalize(a) == kw for a in alts):
            variants.add(canonical)
            variants.update(_normalize(a) for a in alts)
    return list(variants)


def _contains(text: str, keyword: str) -> bool:
    text = _normalize(text)
    return any(v and v in text for v in _expand(keyword))


# --------------------------------------------------------------------------- #
# 抽取关键词
# --------------------------------------------------------------------------- #

def extract_keywords_from_jd(jd_summary: dict) -> list[dict[str, Any]]:
    """从已解析的 JD 里抽取关键词列表，带 importance 权重。

    权重规则（启发式）：tech 关键词高权重，domain 中等，soft 低，requirements
    里出现的原始文本关键词会先做一次轻量清洗（切分、去停用词）再纳入。
    """
    out: list[dict[str, Any]] = []
    seen: set[str] = set()

    def _add(raw: str, importance: str, source: str):
        kw = _normalize(raw)
        if not kw or kw in seen:
            return
        seen.add(kw)
        out.append({"keyword": kw, "importance": importance, "source": source})

    for kw in jd_summary.get("tech", []) or []:
        _add(kw, "high", "tech")
    for kw in jd_summary.get("domain", []) or []:
        _add(kw, "medium", "domain")
    for kw in jd_summary.get("soft", []) or []:
        _add(kw, "low", "soft")
    # requirements 里可能有未结构化的关键词：挑出里面的名词短语（简单处理）
    for req in jd_summary.get("requirements", []) or []:
        text = str(req or "")
        for kw in re.findall(r"[\u4e00-\u9fa5A-Za-z][\u4e00-\u9fa5A-Za-z0-9\-]{1,}", text):
            kw_n = _normalize(kw)
            if len(kw_n) >= 2 and kw_n not in seen and kw_n not in {
                "熟悉", "了解", "掌握", "具备", "以及", "能够", "相关"
            }:
                _add(kw, "low", "requirements")
    return out


# --------------------------------------------------------------------------- #
# 扫描简历内容
# --------------------------------------------------------------------------- #

def _section_text(section: str, items: Any) -> str:
    """把一个 section 的所有条目拼成一个字符串供关键词匹配。"""
    parts: list[str] = [section]
    if isinstance(items, dict):
        items = [items]
    for item in items or []:
        if isinstance(item, str):
            parts.append(item)
            continue
        if not isinstance(item, dict):
            continue
        if section == "summary":
            parts.append(item.get("text") or "")
        elif section == "self_eval":
            parts.append(item.get("text") or "")
        elif section == "skills":
            parts.append(item.get("name") or "")
            parts.append(item.get("category") or "")
        elif section in ("projects", "polished_projects", "fabricated_projects"):
            parts += [item.get("title") or "", item.get("tech_stack") or "",
                      item.get("description") or "", item.get("result") or ""]
        elif section in ("internships", "polished_internships", "fabricated_internships"):
            parts += [item.get("company") or "", item.get("position") or "",
                      item.get("description") or "", item.get("achievement") or ""]
        elif section == "educations":
            parts += [item.get("school") or "", item.get("major") or "",
                      item.get("courses") or ""]
    return " ".join(parts)


def extract_keywords_from_resume(
    user_profile: dict,
    polished_experiences: list | None = None,
    fabricated: list | None = None,
    personal_summary: str = "",
    self_evaluation: str = "",
) -> dict[str, str]:
    """返回 {section_key: 拼好的正文} 字典，供后续打分用。"""
    sections = {
        "summary": personal_summary or "",
        "self_eval": self_evaluation or "",
        "skills": _section_text("skills", user_profile.get("skills")),
        "educations": _section_text("educations", user_profile.get("educations")),
        "internships": _section_text("internships", user_profile.get("internships")),
        "projects": _section_text("projects", user_profile.get("projects")),
        "polished_internships": _section_text("polished_internships", [
            x for x in (polished_experiences or []) if x.get("type") == "internship"]),
        "polished_projects": _section_text("polished_projects", [
            x for x in (polished_experiences or []) if x.get("type") == "project"]),
        "fabricated_internships": _section_text("fabricated_internships", [
            x for x in (fabricated or []) if x.get("type") == "internship"]),
        "fabricated_projects": _section_text("fabricated_projects", [
            x for x in (fabricated or []) if x.get("type") == "project"]),
    }
    # 把同类型 section 合并，匹配时不需要区分 polished/fabricated，只需要知道"有没有出现"
    merged = {
        "summary": sections["summary"],
        "self_eval": sections["self_eval"],
        "skills": sections["skills"],
        "educations": sections["educations"],
        "internships": sections["internships"] + " "
                     + sections["polished_internships"] + " "
                     + sections["fabricated_internships"],
        "projects": sections["projects"] + " "
                    + sections["polished_projects"] + " "
                    + sections["fabricated_projects"],
    }
    return merged


# --------------------------------------------------------------------------- #
# 打分主入口
# --------------------------------------------------------------------------- #

_IMPORTANCE_SCORE = {"high": 3, "medium": 2, "low": 1}

# JD 关键词 → 建议插入板块 的启发式映射
_IMPORTANCE_TO_INSERT = {
    "high": "projects",   # 高权重（技术关键词）优先放进项目经历
    "medium": "internships",
    "low": "self_eval",
}


def score_match(jd_keywords: list[dict], resume_sections: dict[str, str]) -> dict[str, Any]:
    """核心打分函数。

    Returns:
        {
          "hit_rate": 0.72,
          "hit_count": 18,
          "total_count": 25,
          "missing": [{"keyword": "kafka", "importance": "high", "suggest_in": "projects"}],
          "hit_details": [{"keyword": "python", "section": "skills"}],
          "density": {"summary": 0.04, "skills": 0.12, ...}
        }
    """
    # 拼一个全文本用于快速命中判断
    full_text = " ".join(resume_sections.values())

    hit_details: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    density: dict[str, float] = {}

    for entry in jd_keywords:
        kw = entry["keyword"]
        importance = entry["importance"]
        if _contains(full_text, kw):
            # 找出最早出现它的 section（展示给用户看）
            found_section = next(
                (s for s, t in resume_sections.items() if _contains(t, kw)),
                None,
            )
            hit_details.append({"keyword": kw, "section": found_section,
                                "importance": importance})
        else:
            missing.append({
                "keyword": kw,
                "importance": importance,
                "suggest_in": _IMPORTANCE_TO_INSERT.get(importance, "projects"),
            })

    # 按 importance 权重对 missing 排序
    missing.sort(key=lambda m: -_IMPORTANCE_SCORE.get(m["importance"], 0))

    # 密度：每个 section 里命中的 JD 关键词数 / section 总字符数 × 1000
    for sec, text in resume_sections.items():
        if not text.strip():
            density[sec] = 0.0
            continue
        hit_here = sum(1 for kw in jd_keywords if _contains(text, kw["keyword"]))
        density[sec] = round(hit_here / max(len(text), 1) * 1000, 3)

    total = len(jd_keywords)
    hit = len(hit_details)
    weighted_hit = sum(_IMPORTANCE_SCORE.get(k["importance"], 1) for k in hit_details)
    weighted_total = sum(_IMPORTANCE_SCORE.get(k["importance"], 1) for k in jd_keywords)

    return {
        "hit_rate": round(hit / total, 4) if total else 1.0,
        "hit_rate_weighted": round(weighted_hit / weighted_total, 4) if weighted_total else 1.0,
        "hit_count": hit,
        "total_count": total,
        "missing": missing,
        "hit_details": hit_details,
        "density": density,
    }


def run_ats_score(
    jd_summary: dict,
    user_profile: dict,
    polished_experiences: list | None = None,
    fabricated: list | None = None,
    personal_summary: str = "",
    self_evaluation: str = "",
) -> dict[str, Any]:
    """对外主入口：一次调用出完整 ATS 评分。"""
    jd_keywords = extract_keywords_from_jd(jd_summary or {})
    resume_sections = extract_keywords_from_resume(
        user_profile, polished_experiences, fabricated,
        personal_summary, self_evaluation,
    )
    return score_match(jd_keywords, resume_sections)
