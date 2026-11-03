"""反伪造检测 & 对抗性调优。

设计原则（来自 ExperienceRecall 的教训）：
1. 所有启发式阈值、命中词表、检测逻辑**全部集中在本文件**，不改 fabricate/polish 调用链
2. 检测是**纯只读**的：输入经历 list → 输出评分 + 命中规则标签，不原地修改经历
3. 自动优化（二次润色）是**单独的 async 函数**，显式接收 experiences 并返回修订后版本
4. 每一条规则都输出结构化证据，方便前端展示（不是黑盒分数）

ROADMAP T8 四条启发式规则：
  R1 AI 高频表达：检测 demonstrated ability / successfully leveraged / resulted in significant 等模板化表达
  R2 精确数字堆砌：检测所有经历都有百分比、QPS、节省时间的"完美量化"模式
  R3 STAR 僵化：检测每段都是 Challenge-Action-Result / 问题-行动-结果 三段式
  R4 时间线完美对齐：检测所有经历时间无间隙无重叠、start_date 与上一段 end_date 完美衔接

每条规则返回 0-1 的危险度 + 命中片段，总 score 为加权平均。
"""
from __future__ import annotations

import re
from typing import Iterable


# ---------- R1: AI 高频表达 ----------
# 英文（LLM 默认输出）+ 中文（如果用户切中文模型）
_AI_PHRASES_EN: list[tuple[str, float]] = [
    # (phrase, weight) —— 越模板化权重越高
    ("demonstrated ability to", 0.9),
    ("demonstrated expertise in", 0.9),
    ("successfully leveraged", 0.85),
    ("resulted in significant improvement", 0.9),
    ("resulted in substantial", 0.85),
    ("instrumental in", 0.8),
    ("spearheaded the development", 0.8),
    ("pivoted the team", 0.75),
    ("across the board", 0.7),
    ("end-to-end solution", 0.7),
    ("full-stack solution", 0.7),
    ("best-in-class", 0.65),
    ("industry-leading", 0.7),
    ("mission-critical", 0.75),
    ("cutting-edge technology", 0.7),
    ("leveraged synergy", 0.8),
    ("actionable insights", 0.7),
    ("key stakeholder", 0.6),
    ("cross-functional collaboration", 0.7),
    ("data-driven approach", 0.7),
]

_AI_PHRASES_CN: list[tuple[str, float]] = [
    ("显著提升", 0.6),
    ("大幅优化", 0.55),
    ("开创性地", 0.85),
    ("里程碑意义", 0.75),
    ("端到端解决方案", 0.7),
    ("一站式解决方案", 0.65),
    ("行业领先水平", 0.8),
    ("业界领先", 0.75),
    ("卓越的", 0.5),
    ("出色完成", 0.55),
    ("牵头负责", 0.6),
    ("统筹协调", 0.55),
    ("跨部门协作", 0.5),
    ("数据驱动", 0.55),
    ("技术攻坚", 0.55),
    ("高效赋能", 0.7),
    ("深度赋能", 0.65),
    ("降本增效", 0.5),
]


def _detect_ai_phrases(text: str) -> tuple[float, list[dict]]:
    """检测一段文本里的 AI 高频表达。返回 (score 0-1, hits)。"""
    hits: list[dict] = []
    score_sum = 0.0
    seen: set[str] = set()
    lower = text.lower()
    for phrase, w in _AI_PHRASES_EN + _AI_PHRASES_CN:
        pnorm = phrase.lower()
        if pnorm in lower and pnorm not in seen:
            seen.add(pnorm)
            score_sum += w
            # 截取命中片段前后各 15 字作为证据
            idx = lower.find(pnorm)
            ctx = text[max(0, idx - 15):idx + len(phrase) + 15]
            hits.append({"phrase": phrase, "weight": w, "context": ctx})
    # 归一：按命中数 + 权重上限 cap
    # 命中 3 个以上模板表达就属于典型 AI 写作模式
    if not hits:
        return 0.0, hits
    # 每多 1 个命中，danger 递增，上限 1.0
    base = min(len(hits) / 3.0, 1.0)
    avg_w = score_sum / max(len(hits), 1)
    danger = base * avg_w
    return min(danger, 1.0), hits


# ---------- R2: 精确数字堆砌 ----------
# 计算一段经历里的数字密度 + 完美量化特征
_PERCENT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:%|％|percent|pp)")
_QPS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:qps|tps|rpm|rps)")
_TIME_SAVE_RE = re.compile(r"节省|缩短|减少|提速|优化了")
_NUMBER_ANY_RE = re.compile(r"\d+(?:\.\d+)?")


def _detect_perfect_numbers(exps: list[dict]) -> tuple[float, list[dict]]:
    """检测整组经历是否"每段都完美量化"。

    启发式：若 ≥80% 经历同时含百分比 + 时间/成本节省 + 绝对数字，视为堆砌。
    """
    if len(exps) < 2:
        return 0.0, []
    flags: list[dict] = []
    perfect_count = 0
    for i, exp in enumerate(exps):
        text = _exp_blob(exp)
        has_pct = bool(_PERCENT_RE.search(text))
        has_time_save = bool(_TIME_SAVE_RE.search(text))
        has_number = bool(_NUMBER_ANY_RE.search(text))
        score_components = sum([has_pct, has_time_save, has_number])
        if score_components >= 3:
            perfect_count += 1
            flags.append({
                "index": i,
                "type": exp.get("type", ""),
                "title": exp.get("title") or exp.get("company") or "",
                "reasons": [
                    "百分比" if has_pct else None,
                    "时间/成本节省动词" if has_time_save else None,
                    "绝对数字" if has_number else None,
                ],
            })
    ratio = perfect_count / len(exps)
    # ≥80% 视为强风险，50-80% 中度
    if ratio >= 0.8:
        danger = min(ratio * 1.5, 1.0)
    elif ratio >= 0.5:
        danger = ratio * 0.8
    else:
        danger = 0.0
    return danger, flags


# ---------- R3: STAR 僵化 ----------
# 检测每段经历是否严格遵循 Challenge-Action-Result 三段式
# 先用中文/英文的 STAR 关键词定位；再检查结构是否过于整齐
_STAR_CHALLENGE_WORDS = [
    "挑战", "问题", "背景", "面临", "遭遇", "痛点",
    "challenge", "problem", "issue", "faced", "background", "situation",
]
_STAR_ACTION_WORDS = [
    "采取", "实施", "通过", "主导", "负责", "设计", "开发", "优化",
    "action", "implemented", "through", "led", "designed", "developed",
]
_STAR_RESULT_WORDS = [
    "结果", "最终", "成功", "从而", "因此", "达成", "实现",
    "result", "最终", "successfully", "achieved", "enabled", "led to",
]


def _star_counts(text: str) -> tuple[int, int, int]:
    lower = text.lower()
    c = sum(1 for w in _STAR_CHALLENGE_WORDS if w in lower)
    a = sum(1 for w in _STAR_ACTION_WORDS if w in lower)
    r = sum(1 for w in _STAR_RESULT_WORDS if w in lower)
    return c, a, r


def _detect_star_rigidity(exps: list[dict]) -> tuple[float, list[dict]]:
    """检测 STAR 模板僵化：若 ≥80% 经历都严格 Challenge(1+)-Action(1+)-Result(1+) 三段式。"""
    if len(exps) < 2:
        return 0.0, []
    rigid_count = 0
    flags: list[dict] = []
    for i, exp in enumerate(exps):
        c, a, r = _star_counts(_exp_blob(exp))
        if c >= 1 and a >= 1 and r >= 1:
            rigid_count += 1
            flags.append({
                "index": i,
                "type": exp.get("type", ""),
                "title": exp.get("title") or exp.get("company") or "",
                "challenge_hit": c,
                "action_hit": a,
                "result_hit": r,
            })
    ratio = rigid_count / len(exps)
    danger = ratio * 0.9  # STAR 本身不是错，但"每段都是"高度可疑
    # 额外惩罚：如果每段 c/a/r 数量几乎一致（说明是机械模板）
    if rigid_count == len(exps):
        danger = min(danger + 0.15, 1.0)
    return min(danger, 1.0), flags


# ---------- R4: 时间线完美对齐 ----------
def _parse_ym(value: str):
    v = (value or "").strip()
    if not v:
        return None
    if v in ("至今", "现在") or v.lower() in ("now", "present", "current"):
        return (9999, 12)
    m = re.match(r"(\d{4})\D?(\d{1,2})?", v)
    if not m:
        return None
    month = int(m.group(2)) if m.group(2) else 1
    if not (1 <= month <= 12):
        month = 1
    return (int(m.group(1)), month)


def _months_between(a, b) -> int:
    """返回 a→b 之间间隔的月数（abs 后）。"""
    if a is None or b is None:
        return -1
    ay, am = a
    by, bm = b
    return abs((by - ay) * 12 + (bm - am))


def _detect_timeline_perfection(exps: list[dict]) -> tuple[float, list[dict]]:
    """检测时间线完美对齐：所有经历 start_date 恰好等于上一段 end_date，无间隙、无重叠。"""
    # 先把所有经历按 start_date 排序
    dated = []
    for i, exp in enumerate(exps):
        s = _parse_ym(exp.get("start_date", ""))
        e = _parse_ym(exp.get("end_date", ""))
        if s is None or e is None:
            continue
        dated.append((i, s, e, exp))
    if len(dated) < 2:
        return 0.0, []

    dated.sort(key=lambda t: t[1])

    perfect_gaps = 0
    total_pairs = len(dated) - 1
    flags: list[dict] = []
    for k in range(len(dated) - 1):
        prev_i, prev_s, prev_e, _ = dated[k]
        cur_i, cur_s, cur_e, cur_exp = dated[k + 1]
        gap = _months_between(prev_e, cur_s)
        flags.append({
            "pair": [prev_i, cur_i],
            "prev_end": f"{prev_e[0]}.{prev_e[1]:02d}",
            "cur_start": f"{cur_s[0]}.{cur_s[1]:02d}",
            "gap_months": gap,
        })
        # gap == 0 → 完美衔接；gap > 0 → 有间隙（真实人生）；gap < 0 实际不会发生（后段 start 更晚）
        if gap == 0:
            perfect_gaps += 1

    perfect_ratio = perfect_gaps / max(total_pairs, 1)
    # 真实人总会有 gap（哪怕 1-2 个月休息/gap），0 gap 高度可疑
    danger = perfect_ratio * 0.8
    # 如果完全无间隙 → 更可疑（真实人生 0 gap 的概率极低）
    if perfect_gaps == total_pairs:
        danger = min(danger + 0.15, 1.0)

    return min(danger, 1.0), flags


# ---------- 工具：拼经历文本 blob ----------
def _exp_blob(exp: dict) -> str:
    parts = []
    for key in ("title", "role", "company", "position",
                "description", "result", "achievement", "tech_stack"):
        v = exp.get(key) if isinstance(exp, dict) else getattr(exp, key, None)
        if v:
            parts.append(str(v))
    return "\n".join(parts)


# ---------- 主入口 ----------

def detect_all(experiences: list[dict]) -> dict:
    """对一组经历跑完整检测，返回结构化结果。

    输出：
      rules: { rule_id: { danger, hits, description } }
      score: float 0-1 综合危险度（越高越可能被 AI 检测器命中）
      verdict: "safe" / "watch" / "danger"
      summary: str 给用户看的简要结论
    """
    exps = experiences or []
    rules: dict = {}

    # R1 AI 高频表达 —— 按段算，取最大值
    r1_max = 0.0
    r1_hits_all: list[dict] = []
    for i, exp in enumerate(exps):
        d, hits = _detect_ai_phrases(_exp_blob(exp))
        if d > r1_max:
            r1_max = d
        for h in hits:
            h["source_exp"] = i
            r1_hits_all.append(h)
    rules["ai_phrases"] = {
        "danger": r1_max,
        "hits": r1_hits_all,
        "description": "AI 高频表达（如 demonstrated ability to / 显著提升 等）",
    }

    # R2 精确数字堆砌
    d2, hits2 = _detect_perfect_numbers(exps)
    rules["number_padding"] = {
        "danger": d2,
        "hits": hits2,
        "description": "精确数字堆砌（每段都有百分比+节省+数字）",
    }

    # R3 STAR 僵化
    d3, hits3 = _detect_star_rigidity(exps)
    rules["star_rigidity"] = {
        "danger": d3,
        "hits": hits3,
        "description": "STAR 模板僵化（每段都是 Challenge-Action-Result）",
    }

    # R4 时间线完美对齐
    d4, hits4 = _detect_timeline_perfection(exps)
    rules["timeline_perfection"] = {
        "danger": d4,
        "hits": hits4,
        "description": "时间线完美对齐（所有经历无间隙无重叠）",
    }

    # 综合分：加权平均 + max（只要一条规则触发就抬升总分）
    weights = {"ai_phrases": 0.35, "number_padding": 0.25,
               "star_rigidity": 0.2, "timeline_perfection": 0.2}
    weighted = sum(rules[k]["danger"] * weights[k] for k in weights)
    peak = max(r["danger"] for r in rules.values()) if rules else 0.0
    score = min(weighted * 0.6 + peak * 0.4, 1.0)

    if score >= 0.7:
        verdict = "danger"
    elif score >= 0.4:
        verdict = "watch"
    else:
        verdict = "safe"

    triggered = [k for k, r in rules.items() if r["danger"] >= 0.3]
    if verdict == "danger":
        summary = (f"⚠️ 反伪造检测综合评分 {score:.0%}，已触发 {len(triggered)} 条规则。"
                   f"建议启用「反伪造优化」让 AI 按建议重写这些经历，降低被 CareerScape 等检测器命中的风险。")
    elif verdict == "watch":
        summary = (f"⚡ 评分 {score:.0%}，触发 {len(triggered)} 条弱风险规则。"
                   f"部分表达偏模板化，可一键优化或手动润色。")
    else:
        summary = f"✅ 评分 {score:.0%}，未触发明显 AI 痕迹规则，经历风格自然。"

    return {
        "score": round(score, 3),
        "verdict": verdict,
        "summary": summary,
        "rules": {
            k: {"danger": round(v["danger"], 3),
                "hits": v["hits"],
                "description": v["description"]}
            for k, v in rules.items()
        },
        "triggered_rules": triggered,
        "total_experiences": len(exps),
    }
