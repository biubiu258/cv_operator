"""篇幅约束智能裁剪：把一组经历列表按策略压缩到预算范围内。

三种策略：
- time_priority（默认）：按结束时间倒序，优先保留最近经历
- keyword_priority：按 ATS 关键词匹配度排序，优先保留与 JD 最相关的经历
- manual：尊重数组原序（用户手动排过序的场景）

compressor 完全不依赖 ORM，输入是已合并好的四元组 (projects, internships, works, others)，
每一项都是 SimpleNamespace 列表；输出同样结构。这让它可以被 docx 渲染和网页模板共用。
"""
from __future__ import annotations

import re
from types import SimpleNamespace
from typing import Iterable


# ---------- 复用 ats 的同义词归一 ----------
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


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", str(s or "").lower().strip())


def _expand(kw: str) -> set[str]:
    k = _norm(kw)
    if not k:
        return set()
    out = {k}
    for canonical, alts in _SYNONYM_MAP.items():
        if canonical == k or any(_norm(a) == k for a in alts):
            out.add(canonical)
            out.update(_norm(a) for a in alts)
    return out


def _keywords_from_jd(jd_summary: dict) -> list[dict]:
    """和 ats.py 的 extract_keywords_from_jd 保持一致的抽取逻辑。"""
    out: list[dict] = []
    seen: set[str] = set()

    def _add(raw, importance, source):
        k = _norm(raw)
        if not k or k in seen:
            return
        seen.add(k)
        out.append({"keyword": k, "importance": importance, "source": source})

    for kw in (jd_summary or {}).get("tech", []) or []:
        _add(kw, "high", "tech")
    for kw in (jd_summary or {}).get("domain", []) or []:
        _add(kw, "medium", "domain")
    for kw in (jd_summary or {}).get("soft", []) or []:
        _add(kw, "low", "soft")
    return out


_IMPORTANCE_SCORE = {"high": 3, "medium": 2, "low": 1}


# ---------- 单段经历打分 ----------

def _exp_text(exp: SimpleNamespace) -> str:
    """从 SimpleNamespace 经历里拼一段供关键词匹配的文本。"""
    parts = []
    for attr in ("title", "company", "position", "role",
                 "tech_stack", "description", "result", "achievement"):
        v = getattr(exp, attr, None)
        if v:
            parts.append(str(v))
    return " ".join(parts)


def score_experience(exp: SimpleNamespace, jd_keywords: Iterable[dict]) -> float:
    """单段经历的 JD 匹配度分数（0~10），基于关键词加权命中数 / 文本长度。"""
    text = _norm(_exp_text(exp))
    if not text:
        return 0.0
    hit_weight = 0
    for kw_entry in jd_keywords:
        variants = _expand(kw_entry["keyword"])
        if variants and any(v in text for v in variants):
            hit_weight += _IMPORTANCE_SCORE.get(kw_entry.get("importance"), 1)
    # 密度：命中加权 / 文本长度 × 1000 再归一到 0-10（上限 cap 住避免超长描述碾压）
    density = hit_weight / max(len(text), 1) * 1000
    return min(density * 2.5, 10.0)  # 经验值缩放系数


def score_experience_dict(exp: dict, jd_keywords: Iterable[dict]) -> float:
    """同 score_experience，但输入是 dict 版本（给 ats 打分用）。"""
    parts = []
    for attr in ("title", "company", "position", "role",
                 "tech_stack", "description", "result", "achievement"):
        v = exp.get(attr) if isinstance(exp, dict) else getattr(exp, attr, None)
        if v:
            parts.append(str(v))
    text = _norm(" ".join(parts))
    if not text:
        return 0.0
    hit_weight = 0
    for kw_entry in jd_keywords:
        variants = _expand(kw_entry["keyword"])
        if variants and any(v in text for v in variants):
            hit_weight += _IMPORTANCE_SCORE.get(kw_entry.get("importance"), 1)
    density = hit_weight / max(len(text), 1) * 1000
    return min(density * 2.5, 10.0)


# ---------- 排序 ----------

def _parse_ym(value: str):
    v = (value or "").strip()
    if not v:
        return (0, 0)
    if v in ("至今", "现在") or v.lower() in ("now", "present"):
        return (9999, 12)
    m = re.match(r"(\d{4})\D?(\d{1,2})?", v)
    if not m:
        return (0, 0)
    month = int(m.group(2)) if m.group(2) else 0
    return (int(m.group(1)), month if 1 <= month <= 12 else 0)


def _sort_by_time(items: list[SimpleNamespace], reverse=True) -> list:
    def key(x):
        end = _parse_ym(getattr(x, "end_date", ""))
        return end if end != (0, 0) else _parse_ym(getattr(x, "start_date", ""))
    return sorted(items, key=key, reverse=reverse)


# ---------- 主入口 ----------

_STRATEGY = {"time_priority", "keyword_priority", "manual"}


def compress_to_budget(
    groups: tuple[list, list, list, list],
    budget: dict,
    jd_summary: dict | None = None,
    strategy: str = "time_priority",
) -> tuple[list, list, list, list]:
    """把四组经历按策略裁剪到预算。

    groups: (projects, internships, works, others)，每项都是 SimpleNamespace 列表（可空）
    budget: 含 max_experiences 字段的 dict
    strategy:
      - "time_priority"（默认）：各 type 内按时间倒序，type 间按 projects > internships > works > others
        配额分配；不跨 type 排名（项目和实习的时间线没直接可比性）。
      - "keyword_priority"：把所有经历打平成一个池子，按 JD 关键词匹配度排序后全局截断，
        完全不按 type 配额。适合"我只要最相关的 4 段经历，不管它们是项目还是实习"。
      - "manual"：尊重数组原序 + type 配额（不自动重排，只截断超出预算的尾部）。

    返回：和 groups 同构的四元组。
    """
    if strategy not in _STRATEGY:
        strategy = "time_priority"

    max_total = int(budget.get("max_experiences") or 0)
    if max_total <= 0:
        return ([], [], [], [])

    projects, internships, works, others = groups
    buckets = [list(projects), list(internships), list(works), list(others)]
    total_available = sum(len(b) for b in buckets)
    if total_available <= max_total:
        return tuple(buckets)  # 全部够，不裁剪

    jd_keywords = _keywords_from_jd(jd_summary or {})

    # --- keyword_priority：跨 type 统一排名 ---
    if strategy == "keyword_priority":
        flat: list[tuple[float, int, SimpleNamespace]] = []
        for type_idx, bucket in enumerate(buckets):
            for exp in bucket:
                flat.append((score_experience(exp, jd_keywords), type_idx, exp))
        flat.sort(key=lambda t: -t[0])
        chosen = flat[:max_total]
        out = [[], [], [], []]
        for _, t_idx, exp in chosen:
            out[t_idx].append(exp)
        return tuple(out)

    # --- time_priority / manual：type-aware ---
    if strategy == "time_priority":
        buckets = [_sort_by_time(b) for b in buckets]
    # manual：保留原序

    quotas = _allocate_quotas([len(b) for b in buckets], max_total)
    return tuple(b[:q] for b, q in zip(buckets, quotas))


def _allocate_quotas(counts: list[int], max_total: int) -> list[int]:
    """给 N 个 bucket 分配 max_total 个名额，按 counts 加权但 capped at max_total。

    算法：按剩余名额 / 剩余 bucket 数，先给 top 类型至少 1 个，其余按剩余比例分配。
    这不是优化问题，是启发式：projects 永远至少占一半预算，internships 至少占四分之一。
    """
    total_available = sum(counts)
    if total_available <= max_total:
        return list(counts)

    # 先给 projects 至少 ceil(max_total / 2)，internships 至少 ceil(max_total / 4)
    quotas = [0, 0, 0, 0]
    # projects index 0, internships index 1
    quotas[0] = min(counts[0], max(1, (max_total + 1) // 2))
    remain = max_total - quotas[0]
    quotas[1] = min(counts[1], max(0, (remain + 1) // 2))
    remain -= quotas[1]
    # 剩下的 works + others 平分剩余
    for i in (2, 3):
        quotas[i] = min(counts[i], max(0, remain // 2))
        remain -= quotas[i]
    # 如果还有剩余（projects 本来就不够，internships 不够等），回填 projects
    quotas[0] += remain
    return quotas[:len(counts)]


def describe_compression_before_after(
    original_groups: tuple[list, list, list, list],
    compressed_groups: tuple[list, list, list, list],
    strategy: str,
) -> dict:
    """返回裁剪摘要（供前端 / 日志使用），纯信息函数不参与裁剪决策。"""
    def _sizes(g):
        return [len(x) for x in g]
    return {
        "strategy": strategy,
        "before": _sizes(original_groups),
        "after": _sizes(compressed_groups),
        "type_order": ["projects", "internships", "works", "others"],
    }
