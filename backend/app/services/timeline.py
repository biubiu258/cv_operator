"""经历时间线工具：月份序数、时间窗口规划、日期规范化与时间线校验。

设计原则：杜撰经历的时间段不能交给 LLM 自由发挥（容易产生空档 gap、
重叠、全职早于毕业等简历硬伤）。本模块依据求职者的教育期与真实经历，
确定性地为每类待生成经历分配「精确起止月份窗口」，LLM 只负责填充内容；
返回后再用 :func:`enforce_plan` 强制覆盖日期，双重保险。
"""
import re
from datetime import datetime

_PRESENT = ("至今", "现在", "now", "present")
_INTERNSHIP_WINDOW = 6   # 单段实习窗口最长月数（含首尾）
_WORK_WINDOW = 18        # 单段全职窗口最长月数
_PROJECT_WINDOW = 3      # 单段项目窗口最长月数
_GAP_WARN_MONTHS = 3     # 毕业后就业链空档告警阈值（空满月数）


# ---------- 基础工具 ----------
def to_ord(year: int, month: int) -> int:
    """(年, 月) → 连续月份序数。"""
    return year * 12 + (month - 1)


def from_ord(value: int) -> tuple[int, int]:
    """月份序数 → (年, 月)。"""
    year, month = divmod(int(value), 12)
    return year, month + 1


def fmt_ym(value: int) -> str:
    """月份序数 → 'YYYY.MM'。"""
    y, m = from_ord(value)
    return f"{y}.{m:02d}"


def is_present(value: str) -> bool:
    v = (value or "").strip().lower()
    return v in _PRESENT


def parse_ym(value: str):
    """'2024.09' / '2024-9' → 月份序数；'至今' 返回 None（由调用方按当前月处理）；无法解析返回 None。"""
    v = (value or "").strip()
    if not v or is_present(v):
        return None
    m = re.match(r"(\d{4})\D?(\d{1,2})?", v)
    if not m:
        return None
    month = int(m.group(2)) if m.group(2) else 0
    if month and not 1 <= month <= 12:
        return None
    return to_ord(int(m.group(1)), month or 1)


def _interval(start: str, end: str, now_ord: int):
    """把起止字符串转成闭区间 [s, e]（序数）；结束为「至今」按当前月；无效返回 None。"""
    s = parse_ym(start)
    if s is None and not (start or "").strip():
        return None
    if s is None:
        return None
    e = now_ord if is_present(end) else parse_ym(end)
    if e is None:
        e = s
    if e < s:
        s, e = e, s
    return s, min(e, now_ord)


def merge_intervals(intervals: list) -> list:
    """合并互相重叠或首尾相接（允许 1 个月过渡）的区间。"""
    if not intervals:
        return []
    ordered = sorted(intervals)
    merged = [list(ordered[0])]
    for s, e in ordered[1:]:
        if s <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    return [(s, e) for s, e in merged]


def complement(range_s: int, range_e: int, occupied: list) -> list:
    """[range_s, range_e] 内 occupied 的补集（空闲段），按时间升序。"""
    free, cursor = [], range_s
    for s, e in sorted(occupied):
        if e < range_s or s > range_e:
            continue
        s, e = max(s, range_s), min(e, range_e)
        if s - 1 >= cursor:
            free.append((cursor, s - 1))
        cursor = max(cursor, e + 1)
    if cursor <= range_e:
        free.append((cursor, range_e))
    return free


def _carve_windows(free: list, want: int, cap: int) -> list:
    """从空闲段中自新向旧切窗：每段取靠新的一端、长度至多 cap 个月，返回 [(s,e),...]（新→旧）。"""
    segments = sorted(free)
    windows = []
    while want > 0 and segments:
        s, e = segments[-1]
        ws = max(s, e - cap + 1)
        windows.append((ws, e))
        want -= 1
        if ws <= s:
            segments.pop()
        else:
            segments[-1] = (s, ws - 1)
    return windows


def _profile_intervals(profile: dict, key: str, now_ord: int) -> list:
    out = []
    for it in profile.get(key, []) or []:
        iv = _interval(it.get("start_date", ""), it.get("end_date", ""), now_ord)
        if iv:
            out.append(iv)
    return out


# ---------- 时间窗口规划 ----------
def build_timeline_plan(profile: dict, types: list, count: int, today=None) -> dict:
    """为待杜撰经历按类型分配精确时间窗口。

    返回 {"internship": [{"start_date","end_date"}], "work": [...], ...}，
    窗口已避开教育在校期（全职）、真实经历与彼此，保证毕业后就业链连续无空档。
    """
    today = today or datetime.now()
    now_ord = to_ord(today.year, today.month)

    grad = parse_ym(profile.get("graduation_date", ""))
    edu_starts = [parse_ym(e.get("start_date", "")) for e in profile.get("educations", []) or []]
    edu_starts = [x for x in edu_starts if x is not None]
    edu_start = min(edu_starts) if edu_starts else (grad - 47 if grad is not None else now_ord - 47)
    if grad is None:
        grad = edu_start + 47

    real_intern = _profile_intervals(profile, "internships", now_ord)
    real_project = _profile_intervals(profile, "projects", now_ord)

    # 总数量在类型间均匀分配（保持前端选择顺序，余数给靠前的类型）
    types = types or ["project", "internship"]
    base, rem = divmod(max(1, int(count)), len(types))
    quota = {t: base + (1 if i < rem else 0) for i, t in enumerate(types)}

    plan: dict = {t: [] for t in ("internship", "work", "project", "other")}

    # --- 全职：仅毕业之后，填补毕业至今就业链上的空档（最新空档优先，末段收尾于「至今」）---
    work_quota = quota.get("work", 0)
    if work_quota and now_ord >= grad:
        occupied = [iv for iv in real_intern if iv[1] >= grad]
        free = [iv for iv in complement(grad, now_ord, merge_intervals(occupied))
                if iv[1] - iv[0] + 1 >= 2]  # 不足 2 个月的空档属于正常过渡，不硬塞经历
        for s, e in _carve_windows(free, work_quota, _WORK_WINDOW):
            plan["work"].append(_window(s, e, now_ord))

    # --- 实习：只能落在毕业前的空闲期（毕业年优先，不够再向低年级找）---
    intern_quota = quota.get("internship", 0)
    if intern_quota:
        range_e = min(now_ord, grad - 1)
        windows = []  # 每项为窗口 dict（与最终 plan 结构一致）
        for range_s in (max(edu_start, grad - 11), edu_start):
            if len(windows) >= intern_quota or range_e < range_s:
                break
            # 已切窗口也占位，避免不同批次互相重叠
            occupied = list(real_intern)
            for w in windows:
                ws = parse_ym(w["start_date"])
                we = now_ord if is_present(w["end_date"]) else parse_ym(w["end_date"])
                if ws is not None and we is not None:
                    occupied.append((ws, we))
            free = complement(range_s, range_e, merge_intervals(occupied))
            for s, e in _carve_windows(free, intern_quota - len(windows), _INTERNSHIP_WINDOW):
                windows.append(_window(s, e, now_ord))
        plan["internship"] = windows

    # --- 项目：在校期至今均可，避开真实项目与彼此（与实习/工作可并行），新→旧 ---
    project_quota = quota.get("project", 0)
    if project_quota:
        plan["project"] = [
            _window(s, e, now_ord)
            for s, e in _carve_project_windows(edu_start, now_ord, real_project, project_quota)
        ]

    # --- 其他经历：时间上最灵活，避开真实实习与项目，新→旧 ---
    other_quota = quota.get("other", 0)
    if other_quota:
        occupied = merge_intervals(real_intern + real_project)
        free = [iv for iv in complement(edu_start, now_ord, occupied)
                if iv[1] - iv[0] + 1 >= 2]
        plan["other"] = [_window(s, e, now_ord)
                         for s, e in _carve_windows(free, other_quota, _WORK_WINDOW)]

    return plan


def _window(s: int, e: int, now_ord: int) -> dict:
    return {"start_date": fmt_ym(s),
            "end_date": "至今" if e >= now_ord else fmt_ym(e)}


def _carve_project_windows(range_s, range_e, occupied, want):
    occ = merge_intervals(occupied)
    cursor, out = range_e, []
    while want > 0 and cursor >= range_s:
        hit = next((iv for iv in occ if iv[0] <= cursor <= iv[1]), None)
        if hit:
            cursor = hit[0] - 1
            continue
        e = cursor
        s = max(range_s, e - _PROJECT_WINDOW + 1)
        out.append((s, e))
        want -= 1
        cursor = s - 1
    return out


# ---------- LLM 返回结果的日期纠偏 ----------
def normalize_experiences(experiences: list, now_ord: int = None) -> list:
    """规范化每段经历的日期格式，纠正未来时间与起止倒置；不改变内容。"""
    if now_ord is None:
        now_ord = to_ord(datetime.now().year, datetime.now().month)
    for it in experiences or []:
        s_raw, e_raw = (it.get("start_date") or "").strip(), (it.get("end_date") or "").strip()
        s = parse_ym(s_raw)
        if s is not None and s > now_ord:
            s = now_ord
        if is_present(e_raw):
            e = now_ord
            e_text = "至今"
        else:
            e = parse_ym(e_raw)
            if e is not None and e > now_ord:
                e, e_text = now_ord, "至今"
            else:
                e_text = fmt_ym(e) if e is not None else ""
        if s is not None and e is not None and e < s:
            s, e = e, s
            if e == now_ord:
                e_text = "至今"
            else:
                e_text = fmt_ym(e)
        it["start_date"] = fmt_ym(s) if s is not None else ""
        it["end_date"] = e_text
    return experiences or []


def enforce_plan(experiences: list, plan: dict, profile: dict = None, today=None) -> list:
    """按规划窗口强制对齐 LLM 返回经历的日期；超出窗口配额的条目仅做规范化与底线约束。

    同一类型按返回顺序与窗口一一对应（提示词中已要求顺序生成）。
    """
    today = today or datetime.now()
    now_ord = to_ord(today.year, today.month)
    grad = parse_ym((profile or {}).get("graduation_date", ""))
    normalize_experiences(experiences, now_ord)

    buckets: dict = {}
    for it in experiences:
        buckets.setdefault(it.get("type", "project"), []).append(it)

    for t, items in buckets.items():
        windows = (plan or {}).get(t, [])
        for idx, it in enumerate(items):
            if idx < len(windows):
                it["start_date"] = windows[idx]["start_date"]
                it["end_date"] = windows[idx]["end_date"]
            elif t == "work" and grad is not None:
                # 多出来的全职经历也不得早于毕业
                s = parse_ym(it.get("start_date", ""))
                if s is not None and s < grad:
                    it["start_date"] = fmt_ym(grad)
    return experiences


# ---------- 时间线体检（前端展示告警）----------
def validate_timeline(profile: dict, fabricated: list, polished: list = None, today=None) -> list:
    """对最终简历的就业时间线做体检，返回人可读的告警列表（空列表表示无明显问题）。"""
    today = today or datetime.now()
    now_ord = to_ord(today.year, today.month)
    grad = parse_ym(profile.get("graduation_date", ""))
    warnings = []

    generated = [x for x in (fabricated or []) + (polished or []) if isinstance(x, dict)]

    # 1) 单条经历的硬伤
    for x in generated:
        label = x.get("title") or x.get("role") or "未命名经历"
        s_raw, e_raw = (x.get("start_date") or "").strip(), (x.get("end_date") or "").strip()
        if not s_raw:
            warnings.append(f"「{label}」缺少开始时间，建议补全")
            continue
        s = parse_ym(s_raw)
        if s is None:
            warnings.append(f"「{label}」开始时间格式无法识别（应为 YYYY.MM）")
            continue
        if s > now_ord:
            warnings.append(f"「{label}」开始时间晚于当前日期")
        e = now_ord if is_present(e_raw) else parse_ym(e_raw)
        if e_raw and not is_present(e_raw) and e is None:
            warnings.append(f"「{label}」结束时间格式无法识别（应为 YYYY.MM 或「至今」）")
        if e is not None and e < s:
            warnings.append(f"「{label}」结束时间早于开始时间")
        if x.get("type") == "work" and grad is not None and s < grad:
            warnings.append(f"「{label}」为全职经历但早于毕业时间（{fmt_ym(grad)}），不合理")

    # 2) 就业链：重叠 + 毕业后空档（在校期间的间隔属于正常学习，不告警）
    employment = []
    for it in profile.get("internships", []) or []:
        iv = _interval(it.get("start_date", ""), it.get("end_date", ""), now_ord)
        if iv:
            employment.append(iv)
    for x in generated:
        if x.get("type") not in ("internship", "work"):
            continue
        iv = _interval(x.get("start_date", ""), x.get("end_date", ""), now_ord)
        if iv:
            employment.append(iv)
    # 润色经历是档案实习的「替代稿」，时间段完全相同：按区间去重避免误报重叠
    employment = sorted(set(employment))

    # 重叠检测（含真实经历，避免杜撰与真实经历撞车）
    ordered = sorted(employment)
    for (s1, e1), (s2, e2) in zip(ordered, ordered[1:]):
        if s2 <= e1:
            warnings.append("存在两段就业/实习经历时间重叠，面试官极易追问，请调整")
            break

    if grad is not None and now_ord >= grad:
        chain = merge_intervals([(max(s, grad), min(e, now_ord)) for s, e in employment
                                 if e >= grad and s <= now_ord])
        if chain:
            first_s, last_e = chain[0][0], chain[-1][1]
            head_gap = first_s - grad  # 毕业到首份工作的空月数（0 表示毕业当月入职）
            if head_gap > _GAP_WARN_MONTHS:
                warnings.append(f"毕业后有 {head_gap} 个月空窗期，建议补充该时段的实习/工作经历")
            for (_, e1), (s2, _) in zip(chain, chain[1:]):
                gap = s2 - e1 - 1
                if gap >= _GAP_WARN_MONTHS:
                    warnings.append(f"{fmt_ym(e1)} 至 {fmt_ym(s2)} 之间存在 {gap} 个月空档，建议补齐")
            if now_ord - last_e >= _GAP_WARN_MONTHS:
                warnings.append(
                    f"最近一段经历结束于 {fmt_ym(last_e)}，至今已空窗 {now_ord - last_e} 个月，"
                    "建议将其改为「至今」或补充当前经历")

    # 去重保持顺序
    seen, uniq = set(), []
    for w in warnings:
        if w not in seen:
            seen.add(w)
            uniq.append(w)
    return uniq
