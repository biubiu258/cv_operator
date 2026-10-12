# AI 自动化简历生成器 · 开发文档

> 版本：v0.1（待审阅）
> 日期：2026-10-12
> 状态：需求与设计草案，待用户确认后进入开发

---

## 1. 项目概述

### 1.1 目标
构建一套 **AI 驱动的定向简历生成系统**，实现：

1. **一次建档，长期复用**：用户首次录入完整档案，信息持久化到数据库，支持多用户档案与一键切换。
2. **定向简历生成**：后续只需粘贴岗位 JD，AI 自动解析并针对缺失/关键信息发起少量必要提问，即可生成"回扣 JD"的定制简历。
3. **自我评价智能生成**：基于 JD 关键词 + 用户真实情况 + 问答反馈，按既定规范生成自我评价。
4. **企业级前端体验**：卡片式、分步式、多页面架构，而非单页 demo。

### 1.2 当前用户画像（来自 user_information）
- 姓名：唐杰扬
- 学校：成都理工大学工程技术学院 · 软件工程 · 本科（2023.09 - 2027.06）
- 证书：CET-4
- 求职方向：AI Agent 开发工程师

---

## 2. 技术栈选型

| 层 | 技术 | 说明 |
|---|---|---|
| 后端 | Python 3.11 + FastAPI | 异步 REST API |
| ORM | SQLAlchemy 2.0 + Pydantic v2 | 数据建模与校验 |
| 数据库 | SQLite（默认，零配置） | 单文件数据库，非文件夹；可平滑切换 PostgreSQL/MySQL |
| AI | LLM API（OpenAI 兼容协议） | 用户自设 base_url / api_key / model；填后拉取模型列表 |
| 简历输出 | python-docx | 生成 .docx |
| PDF 转换 | 可插拔转换器 | LibreOffice headless 优先；Windows 下回退 docx2pdf/COM |
| 前端 | Vue 3 + TypeScript + Vite | 企业级 SPA |
| UI 组件 | Element Plus | 卡片、分步表单、对话框、抽屉等 |
| 状态管理 | Pinia | 用户激活态、档案、简历任务流 |
| 请求 | Axios | 前后端通信 |

---

## 3. 系统架构

```
┌─────────────────────────────────────────────────────┐
│                    Vue 3 前端 (SPA)                  │
│  仪表盘 / 建档 / 多用户 / JD问答 / 简历预览 / 自我评价  │
└───────────────────────┬─────────────────────────────┘
                        │ REST /api/*
┌───────────────────────▼─────────────────────────────┐
│                 FastAPI 后端                         │
│  路由层 → 服务层(service) → 数据访问层(repository)     │
│  ├─ 用户与档案服务  ├─ JD解析服务                     │
│  ├─ AI问答服务      ├─ 简历生成服务                   │
│  └─ 自我评价服务    └─ LLM 客户端(可插拔)             │
└───────────────────────┬─────────────────────────────┘
          ┌────────────┴────────────┐
          ▼                         ▼
   SQLite(用户/档案/任务)      LLM API(解析/问答/生成)
```

**设计要点**
- 前后端分离，后端无状态，通过 `/api/users/active` 管理"当前激活用户"。
- LLM 客户端抽象为统一接口，后续更换模型供应商零侵入。
- 简历生成与自我评价生成均遵循 `SKILLS/SKILL.md` 中的流程定义，以"业务规则 + LLM 生成"结合实现。

---

## 4. 数据库设计

> user_information 中的字段全部映射到数据库表；不再使用 md 文件承载数据。

### 4.1 ER 结构

```
users (用户主档)
 ├─ educations        (教育背景，1:N)
 ├─ skills            (专业技能，1:N)
 ├─ projects          (项目经历，1:N)
 ├─ internships       (实习经历，1:N)
 ├─ certificates      (证书/获奖，1:N)
 ├─ resumes           (定向简历任务，1:N)
 └─ self_evaluations  (自我评价记录，1:N)
```

### 4.2 表结构

**users（用户主档）**

| 字段 | 类型 | 说明 | 来源/补充 |
|---|---|---|---|
| id | int PK | 主键 | 系统 |
| name | str | 姓名 | user_information |
| phone | str | 电话 | user_information |
| email | str | 邮箱 | user_information |
| location | str | 所在地 | user_information |
| target_position | str | 意向岗位 | 补充 |
| is_active | bool | 当前激活用户 | 系统（多用户切换） |
| created_at / updated_at | datetime | 时间戳 | 系统 |

**educations（教育背景）**

| 字段 | 类型 | 说明 |
|---|---|---|
| id | int PK | |
| user_id | FK | |
| school / major / degree | str | 学校 / 专业 / 学历 |
| start_date / end_date | str | 就读时间 |
| courses | text(逗号分隔) | 主修课程 |
| gpa / rank | str \| null | 绩点/排名（可空，真实才填） |

**skills（专业技能）**

| 字段 | 类型 | 说明 |
|---|---|---|
| id | int PK | |
| user_id | FK | |
| category | str | 分类：语言/数据库/AI工程/工具/前端/后端 |
| name | str | 技能名（如 LangChain、Python、MySQL） |
| proficiency | str | 熟练度：熟练/熟悉/了解 |

**projects（项目经历）**

| 字段 | 类型 | 说明 |
|---|---|---|
| id | int PK | |
| user_id | FK | |
| title | str | 结果导向标题（可含量化，如"校园问答 Agent —— 准确率 85%"） |
| role | str | 角色 |
| tech_stack | str | 技术栈 |
| start_date / end_date | str | 时间 |
| description | text | STAR 描述 |
| result | text | 量化成果 |

**internships（实习经历）**：company / position / start_date / end_date / description / achievement

**certificates（证书/获奖）**：name / date / description

**resumes（定向简历任务）**

| 字段 | 类型 | 说明 |
|---|---|---|
| id | int PK | |
| user_id | FK | |
| jd_text | text | 原始 JD |
| jd_summary | json | JD 解析结果（岗位名/关键词/软素质要求） |
| target_position | str | 目标岗位 |
| status | str | draft / questioning / answered / generated |
| output_path | str \| null | 生成的 docx 路径 |
| created_at / updated_at | datetime | |

**self_evaluations（自我评价记录）**

| 字段 | 类型 | 说明 |
|---|---|---|
| id | int PK | |
| user_id / resume_id | FK | 归属用户与简历任务 |
| content | text | 生成的自我评价正文 |
| qa | json | 问答过程（题目、题型、答案、用户补充） |
| created_at | datetime | |

---

## 5. 核心模块设计

### 5.1 建档模块（首次）
- 采用 **分步表单**（基本信息 → 教育背景 → 专业技能 → 项目/实习 → 证书/获奖），企业卡片式布局，支持草稿保存。
- 字段以 `user_information` 现有内容为基础，**补充**：意向岗位、技能分级、项目/实习经历、证书/获奖、GPA/排名（可选，真实才填）。
- 提交后写库，成为可复用档案。

### 5.2 多用户档案管理与切换
- 用户列表以卡片呈现，点击切换"激活用户"。
- 全局 `Pinia` 保存激活用户 id，所有下游模块（JD 问答、简历、自我评价）均作用于当前激活用户。
- 支持新增、编辑、删除用户。

### 5.3 JD 输入与必要问答模块
1. 用户粘贴岗位 JD → 后端调用 LLM **解析 JD**（提取：岗位名称、技术栈关键词、软素质要求、加分项）。
2. LLM 结合"用户档案"判断信息缺口，生成 **少量必要问题**（3~5 题，均为真实决策所需：意向确认、项目真实性确认、可量化数据补充等）。
3. 用户作答 → 进入简历生成。

### 5.4 简历生成模块
- 遵循 `SKILLS/SKILL.md` 主流程：文档结构 → STAR+量化 → 关键词回扣 JD → 视觉精修 → docx 输出（含单页校验）。
- 输出 .docx，前端提供预览与下载。

### 5.5 自我评价模块（重点）

**流程**：
1. **输入**：解析后的 JD 关键词 + 当前用户档案（教育/技能/项目/证书）。
2. **AI 生成问题集**（3~5 题，混合题型）：
   - 选择题（单选/多选）：确定自我评价"侧重方向"与"JD 能力命中项"。
   - 描述题：挖掘真实素材。
3. **用户作答 + 自由补充**：程序内置一个"自由补充"文本域，**允许为空**。
4. **生成**：基于《自我评价规范》(见 §7) + JD 关键词 + 用户档案 + 问答结果，产出自我评价。
5. **回显可编辑**：生成后可微调，确认后写库。

### 5.6 LLM 配置模块（OpenAI 兼容协议）
- 提供全局设置页面，用户填写 **base_url / api_key**。
- 保存后调用 `GET {base_url}/models`（`Authorization: Bearer {api_key}`）**拉取该平台支持的模型列表**，前端以下拉展示。
- 用户从列表选择 **model**（或手动输入），作为生成/解析/问答统一模型。
- 配置持久化到数据库；api_key 加密存储（不落明文日志）。
- 前端提供"测试连接"按钮，校验 base_url/api_key 是否可用。

### 5.7 Word → PDF 转换模块
- 简历生成 .docx 后，按需转换为 .pdf。
- 转换器可插拔：优先 **LibreOffice headless**（`soffice --headless --convert-to pdf`，跨平台）；Windows 无 LibreOffice 时回退 **docx2pdf / word COM**。
- 提供下载格式选择（.docx / .pdf）。

---

## 6. SKILL 设计

> 现有 `SKILLS/SKILL.md` 为 `resume-generator` 主技能，保留；新增 `self-evaluation` 子技能。

### 6.1 主技能 resume-generator（已有，扩展点）
- 扩展：增加"多用户档案读取"与"JD 驱动"输入源；替换原有"手动收集信息"为数据库读取。

### 6.2 子技能 self-evaluation（新增）

```
name: self-evaluation
trigger: 用户针对某岗位 JD 生成/优化"自我评价"
input :
  - jd_keywords      # JD 解析结果
  - user_profile     # 当前激活用户完整档案
  - user_answers     # 用户对问题集的作答 + 自由补充(可为空)
flow :
  1. 分析 JD → 提取高频关键词（技术栈/软素质/业务方向）
  2. 读取用户档案 → 识别可支撑的事实素材
  3. 生成问题集（3~5 题，选择+描述混合）
  4. 用户作答，追加自由补充文本
  5. 依《自我评价规范》生成正文
  6. 回显可编辑，确认后入库
output :
  - self_evaluation(text)
```

**问题集示例（针对"AI Agent 开发工程师"JD）**

| # | 题型 | 问题 |
|---|---|---|
| Q1 | 单选 | 本次自我评价想突出哪个方向？（技术深度 / 项目成果 / 快速学习能力 / 综合均衡） |
| Q2 | 多选 | JD 中出现以下能力要求，你实际具备哪些？（Agent 开发 / LangChain / RAG / Prompt 工程 / 大模型应用 / 后端开发） |
| Q3 | 描述 | 请用一句话描述你最有代表性的项目及其量化成果（如"校园问答 Agent，准确率 85%"） |
| Q4 | 描述 | 除简历已写内容外，还有哪些想补充的亮点？（可留空） |

---

## 7. 自我评价规范（生成准则）

生成自我评价时，必须满足以下规范：

1. **篇幅规范**：正文 3~5 句 / 100~180 字，控制在 5 行以内；应届生不宜冗长。
2. **结构规范（四要素）**：
   - 定位：一句话"我是谁 + 目标岗位"；
   - 技术：核心技能栈速览（回扣 JD）；
   - 成果：最有说服力的项目成果（可量化）；
   - 软素质：岗位匹配的软能力，用事实而非空话支撑。
3. **针对性规范（Key-Match）**：抽取 JD 高频关键词（技术栈 + 软素质 + 业务方向），自我评价中至少命中 2~3 个，且每个关键词用具体事实支撑。
4. **真实性规范**：只使用用户档案与问答中确认真实的信息；不虚构绩点/排名/获奖/项目数据；无法背书的表述降级为定性表述。
5. **量化规范**：可量化成果必须带数字（准确率、响应时间、提升 %、日均处理量等）；无数据时用"数量级 + 成果类型"定性表述。
6. **语气规范**：第一人称，自信、客观、克制；不用"我认为/我觉得"，直接事实陈述；不用绝对化词（"精通/最/极致"），用分级词（"熟练/扎实/熟悉"）。
7. **反套话规范（禁用清单）**：禁用"工作认真负责""吃苦耐劳""团队合作精神强""热爱学习"等无事实支撑表述；抽象词必须替换为具体行为/结果。
8. **岗位匹配度表达**：结尾一句表达与岗位的匹配/求职动机，短而自然，不煽情。
9. **一致性规范**：与技术栏、项目栏信息一致，不矛盾；时间线、技术名词准确。
10. **语言规范**：中文书面语；技术名词保留英文原词。

---

## 8. API 接口设计（前缀 /api）

**用户与档案**
- `POST /users` 新建用户
- `GET /users` 用户列表
- `GET /users/{id}` 用户详情（含完整档案）
- `PUT /users/{id}` 更新用户
- `DELETE /users/{id}` 删除用户
- `POST /users/{id}/activate` 切换激活用户
- `GET /users/active` 获取当前激活用户
- 教育/技能/项目/实习/证书：嵌套资源 CRUD（如 `POST /users/{id}/educations`）

**JD 与简历**
- `POST /jd/parse` 解析 JD（返回岗位名/关键词/要求）
- `POST /resumes` 创建定向简历任务（JD + 用户）
- `POST /resumes/{id}/questions` AI 生成必要问题
- `POST /resumes/{id}/answers` 提交答案
- `POST /resumes/{id}/generate` 生成简历 docx
- `GET /resumes` / `GET /resumes/{id}` 列表/详情

**自我评价**
- `POST /self-evaluation/questions` 生成自我评价问题集
- `POST /self-evaluation/generate` 生成自我评价
- `PUT /users/{id}/self-evaluation` 保存/更新自我评价

**LLM 配置**
- `GET /llm/config` 获取当前配置（api_key 脱敏）
- `PUT /llm/config` 保存 base_url / api_key / model
- `POST /llm/models` 拉取该平台支持的模型列表
- `POST /llm/test` 测试连接

**PDF 转换**
- `POST /resumes/{id}/convert` 将当前简历 docx 转为 pdf
- `GET /resumes/{id}/download?format=docx|pdf` 下载简历文件

---

## 9. 前端设计与页面

### 9.1 页面结构（Vue Router）
| 路由 | 页面 | 说明 |
|---|---|---|
| `/` | 仪表盘 | 用户卡片切换、最近简历任务概览 |
| `/profiles` | 多用户管理 | 卡片列表、激活切换、增删改 |
| `/profile/new` · `/profile/:id` | 用户建档/编辑 | 分步表单（卡片式） |
| `/resume/new` | 新建定向简历 | 粘贴 JD → 解析 → 问答流 |
| `/resume/:id` | 简历详情/预览 | 预览 + 下载 docx |
| `/self-evaluation` | 自我评价 | 问答流 → 生成 → 预览编辑 |

### 9.2 企业级卡片设计规范
- **布局**：左侧导航栏 + 顶部栏 + 卡片内容区；非单页平铺。
- **卡片**：圆角、投影、细分隔线、主色为企业深蓝（`#1F4E79`，与 word 输出主色一致）。
- **组件**：Element Plus（`el-card`、`el-steps` 分步、`el-dialog` 问答、`el-descriptions` 档案详情）。
- **交互**：分步表单带进度条；AI 问答以对话式卡片呈现；生成中带 loading 状态。

---

## 10. 开发计划（里程碑）

| 阶段 | 内容 | 交付物 |
|---|---|---|
| M1 数据与后端骨架 | 数据库建模、用户/档案 CRUD、多用户切换 | FastAPI + SQLite 可运行 |
| M2 前端框架与建档 | Vue 骨架、仪表盘、建档分步表单、多用户卡片 | 可建档/切换 |
| M3 JD 解析与问答 | JD 解析、必要问题生成、问答流、简历生成服务 | 可生成定向简历 |
| M4 自我评价模块 | 问题集、自由补充、规范生成、可编辑入库 | 自我评价可用 |
| M5 打磨与联调 | docx 校验、视觉精修、端到端联调 | 完整可交付 |

---

## 11. 待确认事项（请审阅时给出意见）

1. **数据库**：默认 SQLite（单文件、零配置、满足多用户），是否需要直接上 PostgreSQL/MySQL？
2. **LLM 供应商**：✅ 已确认——用户自设 base_url / api_key / model（OpenAI 兼容协议），填后拉取模型列表。
3. **简历输出格式**：✅ 已确认——.docx + 增加 Word→PDF 转换（LibreOffice 优先，Windows 回退 docx2pdf/COM）。
4. **"必要问题"数量与交互**：是否认可"3~5 题 + 自由补充"的幅度？
5. **自由补充字段**：确认放于"自我评价问答"末尾，允许为空。

---

> 文档已确认，进入下一步（数据库与后端骨架搭建）。