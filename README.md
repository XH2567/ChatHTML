# ChatHTML

**ChatHTML** 是一个将学术论文（LaTeX 源码）自动转换为交互式 HTML 的 Web 应用，内置多提供商 AI 学术助手，支持划词提问、对话历史标记、拖拽排序等特性。

---

## 功能特性

| 类别 | 功能 | 说明 |
|------|------|------|
| **论文转换** | 源码 → HTML | 上传 `.tar.gz` 或输入 arXiv ID，后端通过 LaTeXML 自动编译为 HTML |
| **论文转换** | 安全流水线 | Zip Slip 防护、超时控制、`.bbl` 参考文献注入、LaTeXML 宏包兼容补丁 |
| **交互阅读** | iframe 嵌入 | 生成的 HTML 论文嵌入 `<iframe>`，自动注入学术风格 CSS |
| **交互阅读** | 滚轮转发 | 侧边栏滚动自动转发给 iframe，实现全局滚动体验 |
| **AI 助手** | 划词问答 | 选中论文文本自动弹出侧边栏，调用 AI API 进行问答 |
| **AI 助手** | 多提供商 | 支持 DeepSeek、OpenAI、Anthropic、Google AI、智谱 AI、自定义 |
| **AI 助手** | 对话标记 | 每次问答在论文中生成橙色标记点，点击可恢复完整对话上下文 |
| **AI 助手** | 继续对话 | 点击历史标记进入继续模式，后续提问携带完整历史上下文 |
| **AI 助手** | 锁定模式 | 可锁定 AI 助手，避免阅读时误触弹出 |
| **密钥管理** | 服务端存储 | API 密钥加密存储在后端 SQLite，无需暴露在浏览器端 |
| **任务管理** | 实时轮询 | 前端每 3 秒轮询进度，可视化各处理阶段状态 |
| **任务管理** | 拖拽排序 | 任务卡片拖拽重新排序，自动持久化顺序 |
| **任务管理** | 拖拽删除 | 拖拽卡片至底部删除区快速删除 |
| **用户系统** | JWT 认证 | 注册/登录、任务与用户绑定隔离、7 天令牌有效期 |
| **用户系统** | Argon2 加密 | 密码使用 Argon2 哈希，API 密钥加密存储 |

---

## 技术栈

### 后端

| 技术 | 用途 |
|------|------|
| **Rust** (2024 edition) | 语言 |
| **Axum** | HTTP 框架 |
| **Tokio** | 异步运行时 |
| **Serde** | JSON 序列化 |
| **rusqlite** (bundled) | SQLite 数据库 |
| **jsonwebtoken** | JWT 签发/验证 |
| **Argon2** | 密码哈希 |
| **reqwest** | AI API HTTP 客户端 |
| **tower-http** | CORS / 日志中间件 |

### 前端

| 技术 | 用途 |
|------|------|
| **Vue 3** (Composition API + `<script setup>`) | UI 框架 |
| **Vite** | 构建工具 |
| **TypeScript** | 语言 |
| **Tailwind CSS 4** | 原子化样式 |
| **Pinia** | 状态管理 |
| **vue-router 4** | 路由 |
| **Axios** | HTTP 客户端 |
| **vuedraggable 4** | 拖拽排序 |
| **lucide-vue-next** | 图标库 |
| **markdown-it** | Markdown 渲染 |

---

## 环境要求

| 依赖 | 版本 | 安装 (Ubuntu/Debian) |
|------|------|-----------------------|
| Rust | 2024 edition | `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \| sh` |
| Node.js | ≥ 18 | `sudo apt install nodejs npm` 或 nvm |
| LaTeXML | 最新 | `sudo apt install latexml` |
| pdfTeX | 最新 | `sudo apt install texlive-latex-base texlive-latex-extra texlive-latex-recommended texlive-science` |
| 构建工具 | — | `sudo apt install build-essential pkg-config libssl-dev` |

```bash
# 验证安装
rustc --version && cargo --version
node --version && npm --version
latexml --VERSION && latexmlpost --VERSION
pdflatex --version
```

---

## 快速开始

### 1. 启动后端

```bash
cd backend/paper-workflow
cargo run
```

启动后 HTTP 服务监听 `http://127.0.0.1:8000`，自动创建 `jobs/` 数据目录和 `paper_workflow.db` 数据库。

### 2. 启动前端

```bash
cd frontend/paper-workflow
npm install
npm run dev
```

启动后 Vite 开发服务器监听 `http://localhost:5173`，自动代理 `/api` 请求到后端。

### 3. 使用

1. 访问 `http://localhost:5173`，点击 **登录 / 注册** 创建账户
2. 登录后点击 **新建任务**，输入 arXiv ID（如 `2401.12345`）或上传 `.tar.gz` 文件
3. 等待任务处理完成，观察实时状态变化
4. 点击任务卡片进入阅读页
5. 在 **用户菜单 → API 密钥设置** 中配置 AI 提供商、模型和 API 密钥
6. 选中论文中的文本，通过 AI 助手提问
7. 历史问答以橙色标记保留在论文中，可随时点击恢复对话

---

## 项目结构

```
ChatHTML/
├── README.md                          # 本文档
├── API_SPEC.md                        # API 接口文档
├── manual.md                          # 详细技术手册
│
├── backend/paper-workflow/            # Rust 后端
│   ├── Cargo.toml
│   ├── ai_config.json                 # AI 提供商配置
│   └── src/
│       ├── main.rs                    # 入口：初始化、组装路由、启动服务
│       ├── models.rs                  # 数据模型
│       ├── routes.rs                  # 20+ API 路由处理函数
│       ├── store.rs                   # 文件系统持久化
│       ├── worker.rs                  # 后台任务流水线
│       ├── database.rs                # SQLite 数据库层
│       ├── ai.rs                      # 多提供商 AI 集成
│       └── auth.rs                    # JWT 认证 + Argon2
│
├── frontend/paper-workflow/           # Vue 3 前端
│   ├── package.json
│   ├── vite.config.ts
│   └── src/
│       ├── main.ts                    # 应用入口（Pinia + Router）
│       ├── App.vue                    # 根组件
│       ├── router.ts                  # 路由 + 导航守卫
│       ├── style.css                  # Tailwind + 全局样式
│       ├── api/client.ts              # Axios 客户端（auth 拦截器）
│       ├── types/api.ts               # TypeScript 类型
│       ├── stores/auth.ts             # Pinia 认证状态
│       ├── views/
│       │   ├── HomeView.vue           # 首页（任务列表 + 拖拽）
│       │   └── ReaderView.vue         # 阅读页（轮询）
│       └── components/
│           ├── JobCard.vue            # 任务卡片
│           ├── NewJobModel.vue        # 新建任务弹窗
│           ├── PaperReader.vue        # 论文阅读器（核心）
│           ├── SettingsModal.vue      # AI 设置弹窗
│           ├── AuthModal.vue          # 登录/注册弹窗
│           └── UserMenu.vue           # 用户菜单
│
└── jobs/                              # （运行时）任务数据存储
```

---

## 处理流程

```
用户
  │
  ├─ 注册/登录 ──→ JWT 令牌 ──→ localStorage
  │
  ├─ 提交 arXiv ID 或上传 .tar.gz
  │     │
  │     ▼
  │   POST /api/jobs (Authorization: Bearer {token})
  │     │
  │     ├─ 创建任务目录 jobs/{uuid}/
  │     ├─ 保存 job.json（含 userId 绑定）
  │     └─ tokio::spawn(process_job)
  │
  ├─ 轮询进度 (每 3s) ──→ GET /api/jobs/{id}
  │     │
  │     ▼
  │   [后台异步流水线]
  │     ├─ 下载/验证源码 （arXiv / Upload）
  │     ├─ 安全解压（Zip Slip 防护）
  │     ├─ pdflatex -draftmode 预编译
  │     ├─ 注入 .bbl 参考文献
  │     ├─ latexml → main.xml    (300s 超时)
  │     └─ latexmlpost → main.html (120s 超时)
  │
  ├─ 阅读论文 ──→ iframe: /api/jobs/{id}/out/main.html?token={jwt}
  │     │
  │     ├─ iframe 加载完成 → 注入学术 CSS
  │     ├─ 从后端加载 query_history → 恢复标记
  │     └─ 选中文本 → 自动弹出 AI 侧边栏
  │
  └─ AI 问答 ──→ POST /api/chat (服务端获取密钥)
        │
        ├─ 新对话 → 保存 query_history → 注入标记
        └─ 点击标记 → 恢复历史 → 继续模式 → 追问
```

---

## 存储结构

```
jobs/{uuid}/
├── original/                    # 原始压缩包
├── src/                         # 解压后的 LaTeX 源码
├── out/
│   ├── main.html                # 最终生成的 HTML 论文
│   └── main.xml                 # LaTeXML 中间产物
├── meta/job.json                # 任务状态（含 sortOrder、userId）
├── log/                         # 编译日志
└── query_history/{hash}.json    # AI 查询历史

paper_workflow.db                # SQLite：用户 / API 密钥
```

---

## API 概览

### 认证

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/register` | 注册 |
| POST | `/api/auth/login` | 登录 |
| POST | `/api/auth/logout` | 登出 |
| GET | `/api/auth/me` | 当前用户信息 |
| POST | `/api/auth/api-key` | 保存 API 密钥（含提供商+模型） |
| GET | `/api/auth/api-key` | 获取密钥状态（掩码） |
| DELETE | `/api/auth/api-key` | 删除密钥 |

### 任务管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/jobs` | 任务列表（仅当前用户） |
| POST | `/api/jobs` | 创建任务 |
| DELETE | `/api/jobs` | 删除所有任务 |
| PUT | `/api/jobs/reorder` | 批量重排 |
| GET | `/api/jobs/:id` | 任务详情（轮询） |
| DELETE | `/api/jobs/:id` | 删除单任务 |

### AI 与产物

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/chat` | AI 聊天（服务端密钥） |
| GET | `/api/jobs/:id/out/*path` | 产物文件（HTML 需 auth） |
| GET | `/api/jobs/:id/html` | HTML 纯文本（srcdoc） |

### 查询历史

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/jobs/:id/query-history` | 保存历史 |
| GET | `/api/jobs/:id/query-history` | 列出历史 |
| GET | `/api/jobs/:id/query-history/:text_hash` | 获取特定历史 |

> 详细 API 文档参见 [API_SPEC.md](./API_SPEC.md)，技术手册参见 [manual.md](./manual.md)。

---

## License

MIT
