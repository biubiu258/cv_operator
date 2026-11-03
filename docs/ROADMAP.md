# cv_operator 功能迭代开发计划

> 基于《AI 简历生成工具市场调研报告》的差异化定位建议，按 **Catch-up → Differentiate → Innovate → Ecosystem** 四阶段组织，每个阶段内按优先级排序。
> 报告原文：[cv_operator_market_research.html](../cv_operator_market_research/cv_operator_market_research.html)

| 项目 | 说明 |
|------|------|
| 技术栈 | 后端 Python 3.14 + FastAPI + SQLAlchemy 2 + SQLite + python-docx · 前端 Vue 3 + Vite + Element Plus + Pinia |
| 代码位置 | `D:\cv_operator` |
| 当前测试覆盖 | 48 个 pytest 用例（全通过） |
| 任务粒度 | 每个编号 ≈ 0.5–3 人日 |
| 里程碑 | M1 = Q4 补全 + 强化 / M2 = Q1 创新 + 生态 |

---

## 0. 现状基线（2026-11-03）

### 已有能力（调研范围内独家或罕见）

| 能力 | 位置 |
|------|------|
| 六步生成向导（JD→经历→问答→自我评价） | `frontend/src/views/ResumeNew.vue` |
| 经历杜撰（fabricate）+ 真实润色（polish）两种可互斥模式 | `routers/resumes.py` · `services/fabricate.py` · `services/polish.py` |
| 经历选择后只润色/展示所选条目 | `resume.polish_selection` 字段 · `services/polish.py:select_experiences()` |
| 篇幅分级约束（应届 1p / 1-5y ≤2p / 5y+ ≤3p） | `services/prompting.py:get_length_budget()` |
| 经历时间线自动校验（防冲突） | `services/timeline.py:validate_timeline()` |
| WebSocket 实时进度推送 + 断线重连 | `services/progress.py` · 前端 WebSocket client |
| 全流程回顾 + 回退到任意步骤重生成 | `GET /resumes/{id}/review` · `POST /resumes/{id}/rollback` |
| 七套 Word 模板 + 两套网页版模板 | `services/templates/` 目录 |
| LLM 自配置（base_url / api_key / model 可自选） | `routers/llm.py` |
| 提示词外置（`SKILLS/prompts/*.md` 可热编辑） | `services/prompting.py:load_prompt()` |
| 自我评价一题一屏 + 可视化预览（字数/关键词命中率/套话检测） | `ResumeNew.vue` step 4 |
| 必要问答一题一屏 + 答题摘要 + 重新出题/单题换题 | `ResumeNew.vue` step 3 · `POST /resumes/{id}/questions/regenerate` |

### 缺失能力（竞品已有、需要补全）

| 缺失项 | 竞品 | 严重度 |
|--------|------|--------|
| ATS 关键词定向评分（缺失关键词清单 + 建议插入位置） | Rezi、超级简历 | 🔴 高 |
| 求职信生成 | Rezi、Kickresume、Resume-Matcher | 🟡 中 |
| 英文简历 pipeline（英文 JD 解析 + 英文模板 + 英文提示词） | 知页（海归版）、Kickresume | 🟡 中 |
| 求职追踪看板（已投递/待面试/Offer 管理） | Rezi、Resume-Matcher | 🟠 可后置 |
| 移动端（响应式） | 超级简历 App | 🟠 可后置 |

---

## 阶段一：Catch-up — 补齐竞品已有但我们缺失的基础功能

**目标**：3 周内完成，让 cv_operator 在"基础 AI 简历能力"上与超级简历/知页/Rezi 站在同一梯队。

### T1. ATS 关键词定向评分 🔴 P0

**问题**：当前 JD 解析只提取 tech/soft/domain 关键词，但没有"缺失关键词清单"和"关键词密度评估"。Rezi 的 Keyword Targeting 是独立付费功能，也是用户最常见的需求反馈点。

**实现**：

1. 新建 `services/ats.py`：
   - `extract_keywords_from_jd(jd_summary) -> set`：从已有的 `jd_summary`（含 tech/soft/domain/requirements）抽取关键词集合
   - `extract_keywords_from_resume(user, polished, fabricated) -> set`：扫描简历所有经历的 description/result/tech_stack 字段
   - `score_match(jd_kws, resume_kws) -> {missing: [...], hit_count, total_count, hit_rate, density_by_section}`：返回缺失关键词清单、命中率、各板块密度

2. 新增接口：
   ```
   POST /resumes/{id}/ats-score
   Request: {}
   Response: {
     "hit_rate": 0.72,        // 命中率百分比
     "hit_count": 18,
     "total_count": 25,
     "missing": [             // 按重要性排序的缺失关键词
       {"keyword": "Kafka", "importance": "high", "suggest_in": "projects"},
       {"keyword": "微服务", "importance": "medium", "suggest_in": "summary"}
     ],
     "density": {
       "summary": {"count": 2, "density": 0.03},
       "skills": {"count": 8, "density": 0.12},
       "internships": {"count": 5, "density": 0.08},
       "projects": {"count": 3, "density": 0.06}
     }
   }
   ```

3. 前端：
   - 在简历详情页（`ResumeDetail.vue`）增加一个"ATS 评估"卡片
   - 缺失关键词用红色标签列出，点击标签自动定位到建议插入的板块并打开编辑态
   - 可选：在润色/杜撰完成后自动跑一次 ATS 评分作为质量门禁

4. 不需要数据库变更——ATS 评分是纯计算服务。

**工作量**：后端 1.5 天（含测试）+ 前端 1 天 = 2.5 人日

---

### T2. 求职信生成 🟡 P1

**问题**：几乎所有竞品都支持求职信（Rezi/Kickresume 是核心功能，Resume-Matcher 也有），cv_operator 完全缺失。

**实现**：

1. 新建 `SKILLS/prompts/cover_letter_generate.md`：
   - 输入：JD 解析结果、用户档案、目标岗位、简历正文
   - 输出：一封 200–300 字的求职信，结构为：开场（渠道+岗位+动机）→ 匹配点（JD 关键词映射到具体经历）→ 期待收尾
   - 温度 0.7，要求不杜撰、不夸张、引用真实项目名称

2. 新建 `services/cover_letter.py`：
   - `generate_cover_letter(jd_summary, user_profile, resume_content, llm_args) -> str`

3. 新增接口：
   ```
   POST /resumes/{id}/cover-letter
   Request: { "tone": "professional" | "enthusiastic" | "concise" }
   Response: { "content": "尊敬的 HR...", "word_count": 268 }
   ```

4. Resume 表新增字段（自动迁移）：
   ```sql
   ALTER TABLE resumes ADD COLUMN cover_letter TEXT DEFAULT '';
   ```

5. 前端：
   - 在简历详情页增加"求职信" Tab
   - 生成后可编辑、换一版（复用 self_evaluation 的 previous 机制）、下载 .docx
   - 生成向导第 5 步（生成简历后）给出"顺便生成求职信"按钮

6. `services/resume_generator.py` 新增 `save_cover_letter_docx()`，复用现有 Word 生成模板。

**工作量**：后端 1 天 + 前端 1 天 + docx 模板 0.5 天 = 2.5 人日

---

### T3. 英文简历 Pipeline 🟡 P1

**问题**：当前所有提示词、JD 解析、模板都是中文，海外求职或外企求职场景完全缺失。知页 2025 年上线海归专属模板 + 英文简历一键生成后，海外用户付费转化率显著提升。

**实现**：

1. 新建英文版提示词（`SKILLS/prompts/en/*.md`），对应中文版同名文件：
   - `jd_parse_en.md` · `polish_experiences_en.md` · `fabricate_experiences_en.md` · `self_eval_generate_en.md` · `cover_letter_generate_en.md`
   - 英文提示词要求：STAR 结构、量化表达优先、避免中式英语、符合北美简历风格（Objective → Experience → Skills → Education）

2. 改造 `services/prompting.py`：
   - `load_prompt(name, lang="zh")` 增加 lang 参数，`en` 时优先加载 `SKILLS/prompts/{name}_en.md`，fallback 到同名 md
   - 新增 `detect_language(text) -> "zh" | "en"` 工具函数（基于 CJK 字符比例）

3. Resume 表新增字段：
   ```sql
   ALTER TABLE resumes ADD COLUMN language VARCHAR(10) DEFAULT 'zh';
   ```

4. JD 解析接口自动检测语言，根据 JD 语言选择对应 prompt：
   ```python
   lang = detect_language(resume.jd_text)
   resume.language = lang
   jd_summary = await jd_parser.parse_jd(resume.jd_text, ..., lang=lang)
   ```

5. 新增英文 Word 模板（`services/templates/engineer_en.py` 或扩展现有模板支持双语言）。

6. 前端向导在 JD 步骤自动检测语言并显示"已切换到英文模式"提示；模板选择过滤出英文友好模板。

**工作量**：提示词 1 天 + 后端改造 1.5 天 + 前端 0.5 天 = 3 人日

---

### T4. 求职追踪看板 🟠 P2（可后置到 M2）

**问题**：Rezi、Resume-Matcher 都有求职追踪功能（看板视图，管理投递状态）。当前 cv_operator 生成完简历就结束了，没有"后续管理"环节。

**实现**：

1. 新建 `models.py` 表：
   ```python
   class Application(Base):
     id, resume_id, company, position, source, status, applied_date,
     interview_date, offer_date, salary, notes, created_at, updated_at
   ```
   - status 枚举：draft → applied → interviewing → offer → rejected

2. 新建 `routers/applications.py`：CRUD + 看板视图聚合接口

3. 前端新建 `views/ApplicationBoard.vue`：看板（待投递 / 已投 / 面试中 / Offer / 拒绝），卡片可拖拽移动状态

**工作量**：后端 2 天 + 前端 2 天 = 4 人日（建议后置）

---

## 阶段二：Differentiate — 把独家能力做强

**目标**：2 周内完成。阶段一结束后，cv_operator 在基础能力上追上了竞品；阶段二要把"只有 cv_operator 有的东西"做得更有壁垒。

### T5. 杜撰 → 追问链联动 🔴 P0（独家差异化）

**问题**：杜撰经历最大的弱点是"面试官追问就穿帮"。当前 cv_operator 虽然在 `fabricate.py` 里有 `generate_interview_prep()`（`POST /resumes/{id}/fabricate/interview-prep`），但它是整个简历一个问答包，没有做到 **"为每段杜撰经历生成 STAR 追问链"** 的粒度。

**实现**：

1. 改造 `generate_interview_prep()` 为两段式：
   - `generate_fabricated_qa_chain(experience, jd_summary, llm_args) -> list[QAItem]`
     - 输入：单段杜撰经历
     - 输出：该经历的 STAR 问答 + 面试官可能追问的 3–5 个问题 + 标准回答 + 反套路提示（"如果被追问 KPI 计算方式…"）

2. 新增接口：
   ```
   POST /resumes/{id}/fabricated/{exp_ref_id}/qa-chain
   Request: {}
   Response: [
     {"q": "这个项目最有挑战的部分是什么？", "a": "...", "type": "behavioral"},
     {"q": "你说的 QPS 提升 5 倍具体怎么测的？", "a": "...", "type": "technical", "anti_trap": "不要说用 JMeter 压测，要说在 xxx 服务器用 yyy 指标在 peak hour 采样..."},
     ...
   ]
   ```

3. Resume 表新增字段：
   ```sql
   ALTER TABLE resumes ADD COLUMN qa_chains JSON DEFAULT '{}';  -- key=experience_ref_id, value=QAItem[]
   ```

4. 前端：
   - 在杜撰经历列表里，每段经历卡片右下角增加"📋 追问链"按钮
   - 点击展开一个抽屉，显示该段经历的 STAR 问答 + 反套路提示
   - 在自我评价问答环节，当用户选择了"杜撰经历"相关回答，自动引用对应追问链内容作为参考

5. 这个功能是 **cv_operator 独有的护城河**——竞品要么不做杜撰（Rezi/超级简历），要么杜撰了但不做追问链（GitHub 开源 resume 工具）。

**工作量**：后端 2 天 + 前端 1.5 天 = 3.5 人日

---

### T6. 多 LLM 并行 A/B 对比 🟡 P1（独家差异化）

**问题**：当前润色/杜撰调用一个 LLM，用户在模型选择上做"一选定终身"。实际上不同模型（DeepSeek / 豆包 / Claude）在经历润色上的风格差异很大——有的更保守，有的更激进。提供 A/B 对比可以让用户在同一岗位下比较两种风格，显著提升体验。

**实现**：

1. LLMConfig 表支持多模型（当前只有一条记录，扩展为多条 + active 标记）：
   ```python
   class LLMConfig(Base):
     id, name, base_url, api_key, model, is_active, is_primary
   ```
   - is_primary=True 的作为默认模型
   - is_active=False 的可以临时拿来跑 A/B，不影响默认行为

2. 新增接口：
   ```
   POST /resumes/{id}/polish/compare
   Request: { "model_b_ids": [2, 3] }   # 与 primary 模型对比
   Response: {
     "model_a": {"id": 1, "name": "DeepSeek-V3", "experiences": [...]},
     "model_b": {"id": 2, "name": "豆包-pro-32k", "experiences": [...]}
   }
   ```
   - 并行调用，返回两组完整润色稿
   - 前端并排展示，用户点选某一组确认

3. 前端：
   - 润色完成后出现"🔄 换另一种模型试试"按钮
   - 并排 diff 视图（类似 GitHub PR 的 before/after）
   - 选中的模型写入 `Resume.polish_model_id`

4. 杜撰同样支持 A/B：`POST /resumes/{id}/fabricate/compare`

**工作量**：后端 2 天 + 前端 2 天 = 4 人日

---

### T7. 篇幅约束智能裁剪 🟡 P1

**问题**：当前篇幅约束是"按 budget 限制最多 N 段经历"，是硬裁剪。实际上好的裁剪应该是：**经历段落数 + 每段 bullet 数 + 总字数** 三者联合约束，同时优先保留与 JD 关键词匹配度高的经历。

**实现**：

1. 改造 `prompting.py:get_length_budget()` 返回更丰富的预算：
   ```python
   {
     "max_pages": 1,
     "max_experiences": 4,
     "max_bullets_per_exp": 3,
     "max_total_chars": 1200,
     "strategy": "keyword_priority"   # 新增：keyword_priority（按 JD 匹配度排序）| time_priority（默认时间倒序）
   }
   ```

2. 新增 `services/compressor.py`：
   - `rank_experiences_by_jd_match(experiences, jd_summary) -> [(score, exp)]`：用 ATS 关键词密度给每段经历打分
   - `compress_to_budget(experiences, budget, strategy) -> list`：按策略裁剪，每段经历 bullet 数按匹配度加权保留

3. `resume_generator._merge_sections()` 改用 compressor 裁剪，替换当前的硬截断。

4. 前端：在"生成简历"步骤增加"篇幅裁剪策略"选择（时间优先 / 关键词优先 / 手动排序）。

**工作量**：后端 1.5 天 + 前端 0.5 天 = 2 人日

---

## 阶段三：Innovate — 竞品完全没有的蓝海

**目标**：灵活排期，建议与阶段一/二并行开发，由 1–2 人独立推进。

### T8. 反伪造检测对抗性调优 🔴 P0（前沿护城河）

**问题**：2026 年已有 CareerScape（arxiv 2509.19677）等专门检测 LLM 生成经历的模型，64% 招聘负责人误聘过 AI 简历。cv_operator 作为"杜撰工具"，要做的不是"放弃杜撰"，而是 **"让杜撰质量跟得上检测质量"**。

**实现**：

1. 引入一个检测 pipeline（可选接入，不是强制）：
   - 用户可选启用"反伪造优化"开关
   - 开启后，杜撰经历生成完自动喂一个"检测器"（CareerScape 模型 / 或自建启发式规则）
   - 如果检测评分超过阈值，自动触发二次润色（prompt 加"避免 LLM 典型模式"）

2. 启发式反伪造规则（不依赖外部模型也能跑）：
   - 检测"AI 高频表达"：`demonstrated ability to` / `successfully leveraged` / `resulted in significant improvement` 等
   - 检测"精确数字堆砌"：每段都有百分比、QPS、节省时间
   - 检测"STAR 模板僵化"：每段都是 Challenge-Action-Result 三段式
   - 检测"时间线完美对齐"：所有经历时间无间隙无重叠（真实人生总有 gap）
   - 触发任一规则时给经历打标 `⚠️ 可能被检测为 AI 生成`，并在 UI 上提示用户手动调整

3. 新建 `services/anti_detection.py` + 独立提示词 `SKILLS/prompts/avoid_ai_patterns.md`

**工作量**：启发式规则 2 天 + 可选 CareerScape 集成 3 天 = 2–5 人日

---

### T9. GitHub / 技术博客自动回填真实经历 🟡 P1

**问题**：当前档案需要用户手动录入项目经历，这个步骤劝退很多开发者用户。GitHub 贡献历史是真实项目经历的天然数据源。

**实现**：

1. 新建 `services/github_ingest.py`：
   - `ingest_github_repos(github_username, access_token=None) -> list[Project]`：从 GitHub API 拉取公开 repos（或授权后的私有 repos），提取 repo description、stars、主要语言、最近 commit 时间，映射为 Project 记录
   - `ingest_github_activity(github_username) -> list[Internship]`：从 contributions 推断活跃时间段，辅助时间线规划

2. 新建 `services/blog_ingest.py`（可选）：RSS feed 解析 + 文章标题/摘要 → Project description

3. 新增接口：
   ```
   POST /users/{id}/ingest/github
   Request: { "username": "xxx", "access_token": "ghp_...", "create_as": "projects" }
   Response: { "created": 5, "skipped": 2, "projects": [...] }
   ```

4. 前端：用户档案页增加"从 GitHub 导入经历"按钮 → 输入用户名 → 预览拉取结果 → 确认导入

5. 安全：GitHub token 加密存储（复用现有 crypto.encrypt），可选 OAuth 流程。

**工作量**：后端 2 天 + 前端 1 天 = 3 人日

---

### T10. HR 反方向部署（防御性蓝海） 🟠 P2

**问题**：同一套 AI 简历工具，求职者用来生成简历，HR 也可以用来审查简历。如果 cv_operator 能提供一个 **HR 审查模式**，就能同时占据供需两端。

**实现**（与 T8 联动）：
- HR 模式读取候选人简历 + 目标岗位 JD → 输出：岗位匹配度评分、可疑杜撰经历清单（反检测 pipeline 反向用）、追问建议
- 独立部署入口（`ROLE=hr` 环境变量），隐藏"杜撰"功能，暴露"审查"功能

**工作量**：架构预留 1 天 + 功能实现 2 天 = 3 人日（放在 Q2）

---

## 阶段四：Ecosystem — 开源社区飞轮

### T11. 模板市场（模板资产上传/分享）

**问题**：当前 7 套模板由开发者硬编码在 `templates/` 里，用户无法自行添加。而 super简历 5000+ 模板的核心优势就是模板生态。

**实现**：
- 扩展 ResumeTemplate 表：支持上传 .docx 模板文件（参照已有的 `engineer.docx` 资产机制）
- 模板 schema 约定：用占位符（`{{name}}` · `{{jd_position}}` · `{{internships}}` 等）作为填充槽位
- 前端模板选择页：系统模板 + 用户自定义模板 + 导入模板

**工作量**：后端 2 天 + 前端 1.5 天 = 3.5 人日

### T12. 提示词独立仓库 + 行业专属提示词包

**问题**：当前提示词在代码仓库里，每个行业（后端、前端、算法、产品、运营、法务、设计）对"好简历"的定义不同。

**实现**：
- 把 `SKILLS/prompts/` 抽到独立 repo `cv_operator-prompts`
- 社区贡献：后端组、算法组、产品组等，每组一套经过验证的提示词
- 在 `llm.py` 增加"行业包"下拉选择，一键切换整套提示词集

**工作量**：仓库拆分 0.5 天 + 5 个行业提示词 3 天 = 3.5 人日

### T13. Docker Compose + 一键部署脚本

**问题**：本地部署门槛——用户需要手动安装 Python 3.14 + npm + Word（docx2pdf 依赖）。一键脚本能大幅降低尝试成本。

**实现**：
- `docker-compose.yml`：后端（FastAPI）+ 前端（Vite build → nginx 静态服务）
- `docker/Dockerfile.backend`：FROM python:3.14-slim，预装 Word 替代方案（如 libreoffice 做 docx→pdf）
- `docker/Dockerfile.frontend`：Node 构建 + Nginx 静态托管
- Windows Installer（可选）：一键安装包

**工作量**：Docker 1.5 天 + Windows 脚本 1 天 = 2.5 人日

---

## 里程碑与排期

| 里程碑 | 时间 | 包含任务 | 核心交付 |
|--------|------|----------|----------|
| **M1a 基础追平** | 2026-11 W4 | T1 ATS 评分 · T2 求职信 | 3 个竞品功能补齐 |
| **M1b 深度追平** | 2026-12 W1 | T3 英文 Pipeline · T7 篇幅智能裁剪 | 英文简历 + 智能排版 |
| **M2a 独家强化** | 2026-12 W2-W3 | T5 追问链联动 · T6 多模型 A/B | 护城河功能上线 |
| **M2b 蓝海探索** | 2026-12 W4 – 2027-01 W1 | T8 反伪造 · T9 GitHub 回填 | 前沿功能验证 |
| **M3 生态飞轮** | 2027 Q1 | T11 模板市场 · T12 提示词仓库 · T13 一键部署 | 开源社区基建 |
| **M4 防御占位** | 2027 Q2 | T10 HR 反方向 | 供需两端同时覆盖 |

---

## 风险与度量

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| AI 反作弊模型快速进化，杜撰质量跟不上 | 用户面试穿帮口碑反噬 | 中 | T8 反伪造先行；追问链联动（T5）降低穿帮概率；逐步把"润色"路径做成主入口 |
| LLM API 价格上涨 | 跑 A/B 的成本翻倍 | 中 | 做多模型 fallback（便宜模型润色 + 贵模型只跑 ATS 评分） |
| 开源社区热度低于预期 | 模板市场/提示词仓库没人贡献 | 中 | 先用内置高质量模板/提示词，再开放贡献渠道；在 README 里明确标注社区贡献者 |
| SaaS 竞品快速复制开源功能 | 差异化被抹平 | 低 | 我们在"开源 + 本地部署 + LLM 自配置"这条赛道上没有 SaaS 竞品能真正复制；SaaS 复制开源功能反而会验证我们的路线正确 |

**成功度量**（6 个月后评估）：
- GitHub Stars ≥ 1000（开源技术产品的及格线）
- 提示词仓库贡献者 ≥ 5 人（M12 目标）
- 反伪造规则识别准确率 ≥ 70%（T8 验收指标）
- 求职信生成的简历投递反馈率 > 无求职信版本（A/B 测试）

---

## 不做清单（明确排除）

| 排除项 | 原因 |
|--------|------|
| 移动端 App（iOS/Android） | 投入大、ROI 低；响应式 Web 已够用 |
| 简历代投（auto-apply） | 法律风险高、各平台反爬严格、且竞品都在做 |
| AI 面试实时代答 | 法律红线 + 道德争议，cv_operator 定位工具而非作弊器 |
| 企业招聘 SaaS 平台 | 与 HR 反方向（T10）不同，是独立赛道，资源不够 |
| 付费商业化 | 先开源积累口碑，商业模式后续验证；提前收费会冷启动失败 |
