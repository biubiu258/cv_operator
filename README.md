# AI 自动化简历生成器

基于 LLM 的多用户简历生成系统：解析目标岗位 JD → 智能杜撰匹配经历 → 问答补全信息 → 按篇幅约束排版生成 Word/PDF/网页版简历。后端 Python（FastAPI），前端 Vue 3，数据统一存放在 SQLite 单文件数据库中，支持多用户档案切换。

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | FastAPI · SQLAlchemy 2 · SQLite · python-docx · docx2pdf · WebSocket |
| 前端 | Vue 3 · Vite · Element Plus · Pinia · vue-router · html2canvas-pro · jsPDF |
| 大模型 | OpenAI 兼容 API（base_url / api_key / model 均可自行配置） |

## 功能特性

- **用户档案**：多用户信息切换，字段含基本信息、教育经历、技能（熟练度选择框，支持自定义描述）、证书、爱好、毕业日期、期望薪资、个人头像上传。
- **LLM 配置**：在界面中配置 OpenAI 兼容服务的 base_url、api_key、model，配置后可在线拉取对应平台模型列表。
- **六步生成向导**：填写信息 → JD 解析 → 经历杜撰 → 必要问答 → 自我评价问答 → 生成结果。
  - JD 解析未完成时「下一步：经历杜撰」按钮自动置灰；
  - 经历杜撰拆分为「生成初稿 → 提意见让 AI 修改 → 确认」三阶段，保留完整版本历史，支持填写真实岗位 JD 生成实习/全职/项目等经历；
  - AI 感知当前日期与毕业日期，保证经历时间线合理，渲染时经历按时间新→旧排序；
  - 篇幅分级约束：应届 1 页、1-5 年 ≤2 页、5 年以上 ≤3 页，支持自定义。
- **进度推送**：生成过程经 WebSocket 实时推送（非轮询），断线自动重连 3 次并提示。
- **全流程回顾**：独立回顾页展示每一步产物、进度消息记录与杜撰版本历史，支持回退到任意已完成步骤重新生成后续内容。
- **简历详情页**：个人简介/自我评价在线编辑、模块勾选（决定简历包含哪些板块）、`**强调**` 标记统一渲染为蓝色加粗。
- **模板体系**（详见下文），产物规范命名：`姓名-xx届-求职意向`。
- **网页版简历**：独立预览页，支持浏览器打印导出 PDF（去页眉页脚）与前端直出 PDF 下载。

## 简历模板

| 类型 | 模板 | 说明 |
|---|---|---|
| Word | 简洁单栏（classic） | 代码排版，`■` 章节标题 |
| Word | 双栏（split） | 左主栏 + 右侧栏技能/信息 |
| Word | 经典蓝（blue_classic） | 中英双语标题、图形化技能进度条 |
| Word | iOS 工程师（ios_engineer） | 金色主题、中英双语标题 |
| Word | 工程师（docx_engineer） | 基于预制 `assets/engineer.docx` 资产填充槽位 |
| 网页版 | 暖阳卡片（warm_vue） | 黄色主题，仅在线预览/打印，与 Word 独立 |
| 网页版 | 经典蓝人事（navy_vue） | 蓝色主题、箭头章节条、三列技能进度条 |

- 网页版模板（kind=vue）不生成 docx：选择后详情页 Word/PDF 下载置灰，仅通过预览页打印或「下载 PDF」导出。
- 切换模板时已生成过的内容直接复用，仅主动触发才重新排版。
- 所有模板统一执行版式压缩（小字号、紧凑间距），优先保证单页完整展示；核心量化信息蓝色加粗高亮，专业技能进度条 + 熟练度描述词多列对齐。

## 目录结构

```
├── SKILLS/prompts/          # 全部 LLM 提示词（md 文件，便于微调）
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI 入口（自动建表 + 轻量迁移）
│   │   ├── routers/         # users / llm / resumes / self_evaluation
│   │   ├── services/        # jd_parser / fabricate / resume_generator / templates/ ...
│   │   ├── progress.py      # WebSocket 进度推送
│   │   └── models.py        # ORM（SQLite 单文件库）
│   ├── data/resume.db       # 数据库文件
│   ├── output/              # 生成的 docx/pdf 产物
│   ├── uploads/avatars/     # 头像（/static 静态服务）
│   └── tests/               # pytest 接口测试
└── frontend/
    └── src/
        ├── views/           # 向导、详情、回顾、预览等页面
        └── components/      # 网页版模板组件 + 共享渲染逻辑 resumeShared.js
```

## 快速开始

### 1. 启动后端（端口 8000）

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

启动时自动建表并对旧库做轻量迁移（补列 + NULL 回填），无需手动初始化。

### 2. 启动前端（端口 5173）

```powershell
cd frontend
npm install
npm run dev
```

浏览器访问 `http://localhost:5173`。前端直连 `http://127.0.0.1:8000`（后端已开启 CORS），修改地址见 `frontend/src/api/index.js`。

### 3. 配置大模型

进入「模型配置」页填写 base_url、api_key 并选择模型（可先拉取模型列表验证连通性）。全部提示词位于 `SKILLS/prompts/*.md`，可直接编辑微调。

## 测试

```powershell
cd backend
.venv\Scripts\python -m pytest tests -q
```

## 注意事项

- **Word 转 PDF** 使用 docx2pdf，依赖本机安装 Microsoft Word（Windows）。
- 网页版「打印 / 导出 PDF」请在浏览器打印对话框中选择「保存为 PDF」、纸张 A4、边距默认（页面已通过 `@page margin:0` 去除页眉页脚）；「下载 PDF」按钮则由前端直接生成，文件名与 Word 产物命名规则一致。
- 工程师模板（docx_engineer）依赖 `backend/app/services/templates/assets/engineer.docx` 资产文件。
