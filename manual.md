# ChatHTML 项目技术手册

> **ChatHTML** 是一个将学术论文（LaTeX 源码）自动转换为交互式 HTML 的 Web 应用，内置多提供商 AI 学术助手，支持划词提问、对话历史标记与继续对话、拖拽排序等高级功能。  
> 后端使用 **Rust + Axum + SQLite**，前端使用 **Vue 3 + Vite + Tailwind CSS**。

---

## 目录

- [ChatHTML 项目技术手册](#chathtml-项目技术手册)
  - [目录](#目录)
  - [1. 项目概述](#1-项目概述)
    - [核心能力](#核心能力)
    - [技术栈](#技术栈)
  - [2. 项目结构](#2-项目结构)
  - [3. 后端详解](#3-后端详解)
    - [3.1 入口文件 —— `main.rs`](#31-入口文件--mainrs)
    - [3.2 数据模型 —— `models.rs`](#32-数据模型--modelsrs)
    - [3.3 API 路由 —— `routes.rs`](#33-api-路由--routesrs)
    - [3.4 持久化存储 —— `store.rs`](#34-持久化存储--storers)
    - [3.5 数据库 —— `database.rs`](#35-数据库--databasers)
    - [3.6 认证模块 —— `auth.rs`](#36-认证模块--authrs)
    - [3.7 AI 集成 —— `ai.rs`](#37-ai-集成--airs)
    - [3.8 后台任务 —— `worker.rs`](#38-后台任务--workerrs)
  - [4. 前端详解](#4-前端详解)
    - [4.1 入口与配置](#41-入口与配置)
    - [4.2 路由 —— `router.ts`](#42-路由--routerts)
    - [4.3 TypeScript 类型 —— `api.ts`](#43-typescript-类型--apits)
    - [4.4 API 客户端 —— `client.ts`](#44-api-客户端--clientts)
    - [4.5 全局样式 —— `style.css`](#45-全局样式--stylecss)
    - [4.6 认证状态管理 —— `stores/auth.ts`](#46-认证状态管理--storesauthts)
    - [4.7 主页 —— `HomeView.vue`](#47-主页--homeviewvue)
    - [4.8 阅读页 —— `ReaderView.vue`](#48-阅读页--readerviewvue)
    - [4.9 任务卡片 —— `JobCard.vue`](#49-任务卡片--jobcardvue)
    - [4.10 新建任务弹窗 —— `NewJobModel.vue`](#410-新建任务弹窗--newjobmodelvue)
    - [4.11 论文阅读器 —— `PaperReader.vue`](#411-论文阅读器--paperreadervue)
    - [4.12 AI 设置弹窗 —— `SettingsModal.vue`](#412-ai-设置弹窗--settingsmodalvue)
    - [4.13 登录/注册弹窗 —— `AuthModal.vue`](#413-登录注册弹窗--authmodalvue)
    - [4.14 用户菜单 —— `UserMenu.vue`](#414-用户菜单--usermenuvue)
  - [5. 数据流与工作流程](#5-数据流与工作流程)
    - [5.1 用户认证流程](#51-用户认证流程)
    - [5.2 创建任务 → 完成阅读](#52-创建任务--完成阅读)
    - [5.3 数据持久化](#53-数据持久化)
  - [6. 部署与运行](#6-部署与运行)
    - [6.1 环境要求](#61-环境要求)
    - [6.2 运行方式](#62-运行方式)

---

## 1. 项目概述

### 核心能力

| 功能 | 说明 |
|------|------|
| **论文源码 → HTML** | 支持上传 `.tar.gz` 压缩包或直接输入 arXiv ID，后端自动下载、解压、通过 LaTeXML 编译为 HTML |
| **交互式阅读** | 使用 `<iframe>` 嵌入生成的 HTML 论文，自动注入学术风格 CSS，提供沉浸式阅读体验 |
| **划词 AI 助手** | 选中论文中的文本，自动弹出侧边栏，调用 AI API 进行问答 |
| **多提供商 AI** | 支持 DeepSeek、OpenAI、Anthropic、Google AI、智谱 AI 等多种大模型服务 |
| **服务端密钥管理** | AI API 密钥保存在后端 SQLite 数据库中，安全可靠 |
| **对话历史标记** | 每次 AI 问答在论文中生成可点击的橙色标记点，左侧面板展示所有历史问答索引 |
| **继续对话模式** | 点击历史标记可恢复完整对话上下文，支持追问 |
| **任务管理** | 创建、查看、删除论文转换任务，实时轮询进度 |
| **拖拽排序与删除** | 任务卡片支持拖拽重新排序，拖至底部删除区可快速删除 |
| **用户认证系统** | 基于 JWT 的用户注册/登录，任务数据与用户绑定隔离 |

### 技术栈

| 层 | 技术 | 说明 |
|----|------|------|
| 后端框架 | **Axum** (Rust) | 高性能异步 Web 框架 |
| 后端运行时 | **Tokio** | 异步运行时，处理并发请求与后台任务 |
| 序列化 | **Serde** | JSON 序列化/反序列化 |
| 持久化 | **文件系统 + SQLite (rusqlite)** | 任务状态存为 `meta/job.json`，用户与密钥存 SQLite |
| 密码学 | **Argon2** | 密码哈希与密钥加密 |
| 认证 | **JWT (jsonwebtoken)** | 无状态用户认证，7 天有效期 |
| AI 集成 | **reqwest + 多提供商适配** | 自定义格式化 DeepSeek/OpenAI/Anthropic/Google/Zhipu 请求 |
| 前端框架 | **Vue 3** (Composition API + `<script setup>`) | 响应式 UI |
| 构建工具 | **Vite** | 开发服务器与生产构建 |
| 样式 | **Tailwind CSS 4** | 原子化 CSS |
| 状态管理 | **Pinia** | 全局状态管理 |
| 拖拽 | **vuedraggable 4** | 任务卡片拖拽排序 |
| 图标 | **lucide-vue-next** | 矢量图标库 |
| Markdown 渲染 | **markdown-it** | AI 回复的 Markdown → HTML 渲染 |

---

## 2. 项目结构

```
ChatHTML/
├── API_SPEC.md                  # API 接口说明文档
├── README.md                    # 项目简介
├── backend/
│   └── paper-workflow/          # Rust 后端项目
│       ├── Cargo.toml           # Rust 依赖配置
│       ├── ai_config.json       # AI 提供商配置（端点、模型列表）
│       └── src/
│           ├── main.rs          # 入口：启动服务器、初始化、组装路由
│           ├── models.rs        # 数据模型（JobState、QueryHistory 等）
│           ├── routes.rs        # API 路由处理函数（20+ 接口）
│           ├── store.rs         # 文件系统持久化层
│           ├── worker.rs        # 后台任务流水线（下载、解压、编译）
│           ├── database.rs      # SQLite 数据库层（用户、API 密钥）
│           ├── ai.rs            # AI 多提供商集成
│           └── auth.rs          # JWT 认证与 Argon2 密码哈希
├── frontend/
│   └── paper-workflow/          # Vue 3 前端项目
│       ├── package.json         # npm 依赖
│       ├── vite.config.ts       # Vite 配置（含代理）
│       ├── index.html           # HTML 入口
│       └── src/
│           ├── main.ts          # Vue 应用挂载（Pinia + Router）
│           ├── App.vue          # 根组件（router-view）
│           ├── router.ts        # 路由定义（含导航守卫）
│           ├── style.css        # 全局样式 + Tailwind 导入
│           ├── api/
│           │   └── client.ts    # Axios API 客户端（含 auth 拦截器）
│           ├── types/
│           │   └── api.ts       # TypeScript 类型定义
│           ├── stores/
│           │   └── auth.ts      # Pinia 认证状态管理
│           ├── views/
│           │   ├── HomeView.vue      # 首页（任务列表 + 拖拽）
│           │   └── ReaderView.vue    # 论文阅读页（轮询等待）
│           └── components/
│               ├── JobCard.vue         # 任务卡片组件
│               ├── NewJobModel.vue     # 新建任务弹窗
│               ├── PaperReader.vue     # 论文阅读器（核心组件）
│               ├── SettingsModal.vue   # AI 设置弹窗（服务端存储）
│               ├── AuthModal.vue       # 登录/注册弹窗
│               └── UserMenu.vue        # 用户下拉菜单
└── jobs/                        # （运行时生成）任务数据存储目录
```

---

## 3. 后端详解

### 3.1 入口文件 —— `main.rs`

**职责**：初始化日志、创建 `JobStore`、`Database`、`AppAuth`、组装路由、启动 HTTP 服务器。

新增模块声明（相比初始版本）：

```rust
mod ai;
mod auth;
mod database;
```

关键初始化流程：

1. **创建 `JobStore`**：指定 `./jobs` 为数据存储根目录，包装在 `Arc` 内。
2. **创建 `Database`**：初始化 SQLite 数据库 `./paper_workflow.db`，自动建表和迁移。
3. **创建 `AppAuth`**：认证服务，包装 `Database`，提供 JWT 签发/验证和密码哈希。
4. **创建共享状态**：`Arc<routes::AppState>` 同时包含 `store` 和 `auth`。
5. **配置 CORS**：开发环境允许任意来源。
6. **组装路由**（全部路由）：

| 方法 | 路径 | 处理函数 | 说明 |
|------|------|---------|------|
| POST | `/api/auth/register` | `register` | 用户注册 |
| POST | `/api/auth/login` | `login` | 用户登录 |
| POST | `/api/auth/logout` | `logout` | 用户登出 |
| GET | `/api/auth/me` | `get_me` | 获取当前用户信息 |
| POST | `/api/auth/api-key` | `set_api_key` | 保存 AI API 密钥 |
| GET | `/api/auth/api-key` | `get_api_key` | 获取 API 密钥状态 |
| DELETE | `/api/auth/api-key` | `delete_api_key` | 删除 API 密钥 |
| GET | `/api/jobs` | `list_jobs` | 获取任务列表 |
| POST | `/api/jobs` | `create_job` | 创建任务 |
| DELETE | `/api/jobs` | `delete_all_jobs` | 删除所有任务 |
| PUT | `/api/jobs/reorder` | `reorder_jobs` | 重排任务顺序 |
| GET | `/api/jobs/:id` | `get_job` | 获取单个任务 |
| DELETE | `/api/jobs/:id` | `delete_job` | 删除单个任务 |
| POST | `/api/chat` | `ai_chat_proxy` | AI 聊天代理 |
| GET | `/api/jobs/:id/out/*path` | `get_out_artifact` | 获取产物文件 |
| GET | `/api/jobs/:id/html` | `get_html_content` | 获取 HTML 文本 |
| POST | `/api/jobs/:id/query-history` | `save_query_history` | 保存查询历史 |
| GET | `/api/jobs/:id/query-history` | `list_query_histories` | 列出查询历史 |
| GET | `/api/jobs/:id/query-history/:text_hash` | `get_query_history` | 获取特定查询历史 |

```rust
// main.rs 核心代码示意
let app_state = Arc::new(routes::AppState { store, auth: app_auth });

let app = Router::new()
    .route("/api/auth/register", post(routes::register))
    .route("/api/auth/login", post(routes::login))
    .route("/api/auth/logout", post(routes::logout))
    .route("/api/auth/me", get(routes::get_me))
    .route("/api/auth/api-key", post(routes::set_api_key))
    .route("/api/auth/api-key", get(routes::get_api_key))
    .route("/api/auth/api-key", delete(routes::delete_api_key))
    .route("/api/jobs", get(routes::list_jobs).post(routes::create_job).delete(routes::delete_all_jobs))
    .route("/api/jobs/reorder", put(routes::reorder_jobs))
    .route("/api/jobs/:id", get(routes::get_job).delete(routes::delete_job))
    .route("/api/chat", post(routes::ai_chat_proxy))
    .route("/api/jobs/:id/out/*path", get(routes::get_out_artifact))
    .route("/api/jobs/:id/html", get(routes::get_html_content))
    .route("/api/jobs/:id/query-history", post(routes::save_query_history).get(routes::list_query_histories))
    .route("/api/jobs/:id/query-history/:text_hash", get(routes::get_query_history))
    .with_state(app_state)
    .layer(TraceLayer::new_for_http())
    .layer(cors);
```

**注意**：`AppState` 使用 `FromRef` 派生宏，允许分别提取 `Arc<JobStore>` 和 `Arc<AppAuth>`。

---

### 3.2 数据模型 —— `models.rs`

**职责**：定义任务生命周期和查询历史的所有数据结构。

#### `JobStatus` —— 任务状态枚举

```rust
pub enum JobStatus {
    Created, Queued, Downloading, Validating,
    Extracting, Analyzing, Processing,
    Completed, Partial, Error,
}
```

使用 `#[serde(rename_all = "camelCase")]` 确保序列化为 JSON 时使用驼峰命名（如 `"downloading"`）。

#### `StageStatus` 与 `StageDetail`

每个任务的处理过程分为多个阶段（Stage）：

```rust
pub struct StageDetail {
    pub title: String,          // 阶段标题，如 "下载源码"
    pub status: StageStatus,    // pending / running / done / error / skipped
    pub detail: String,         // 详细信息
}
```

#### `SourceMode` —— 来源模式

```rust
pub enum SourceMode {
    Upload,  // 用户上传 .tar.gz 文件
    Arxiv,   // 通过 arXiv ID 自动下载
}
```

#### `JobState` —— 核心任务状态

新增字段（相比初始版本）：

| 字段 | 类型 | 说明 |
|------|------|------|
| `user_id` | `Option<String>` | 关联的用户 ID，用于任务隔离 |
| `sort_order` | `Option<i32>` | 排序权重（拖拽排序用） |

完整字段列表：

| 字段 | 类型 | 说明 |
|------|------|------|
| `job_id` | `Uuid` | 全局唯一标识 |
| `user_id` | `Option<String>` | 所有者用户 ID |
| `created_at` | `DateTime<Utc>` | 创建时间 |
| `status` | `JobStatus` | 当前状态 |
| `source_mode` | `SourceMode` | 来源模式 |
| `arxiv_id` | `Option<String>` | arXiv ID（仅 Arxiv 模式） |
| `original_name` | `Option<String>` | 上传文件原名（仅 Upload 模式） |
| `archive_size` | `Option<u64>` | 压缩包大小 |
| `errors` | `Vec<String>` | 错误信息列表 |
| `warnings` | `Vec<String>` | 警告信息列表 |
| `duration_seconds` | `Option<f64>` | 处理耗时 |
| `artifacts` | `HashMap<String, String>` | 产物文件路径映射 |
| `sort_order` | `Option<i32>` | 排序权重（可选） |
| `stage_details` | `Vec<StageDetail>` | 详细阶段列表 |
| `manifest` | `Option<serde_json::Value>` | 论文元数据 |

`JobState::new()` 现在也提供一个 `with_user_id()` 构建器方法用于绑定用户。

#### `QueryHistory` —— 查询历史

```rust
pub struct QueryHistory {
    pub text_excerpt: String,   // 划选文本摘录
    pub text_hash: String,      // SHA-256 哈希
    pub query: String,          // 用户提问
    pub reply: String,          // AI 回复
    pub timestamp: String,      // ISO 8601 时间戳
}
```

---

### 3.3 API 路由 —— `routes.rs`

**职责**：实现全部 20+ HTTP 接口的处理逻辑。

#### 3.3.0 共享状态与认证辅助

```rust
pub struct AppState {
    pub store: Arc<JobStore>,
    pub auth: Arc<AppAuth>,
}
```

认证辅助函数：

- `extract_token(headers)`：从 `Authorization: Bearer {token}` 中提取 token
- `validate_token(state, token)`：调用 AuthService 验证 JWT
- `require_auth(state, headers)`：必需认证，失败返回 401
- `optional_auth(state, headers)`：可选认证，失败返回 None
- `auth_from_query_or_header(state, headers, query)`：从 query 参数或 header 获取认证（用于 /html 端点）

#### 3.3.1 认证接口

**register** (`POST /api/auth/register`)：
- 验证用户名非空、密码 >= 6 字符
- 检查用户名唯一（`get_user_by_username`）
- Argon2 哈希密码，创建用户，签发 JWT
- 返回 `AuthResponse { userId, username, token }`

**login** (`POST /api/auth/login`)：
- 查找用户密码哈希
- 验证密码，签发 JWT
- 返回 `AuthResponse`

**logout** (`POST /api/auth/logout`)：
- 仅记录日志，前端清除本地 token

**get_me** (`GET /api/auth/me`)：
- 从 token 解析用户，返回 `{ userId, username }`

**set_api_key** (`POST /api/auth/api-key`)：
- 接收 `{ api_key, provider, model }`
- 前缀 `"encrypted:"` 存储到 SQLite

**get_api_key** (`GET /api/auth/api-key`)：
- 返回掩码状态 `{ hasKey, masked: "********", provider, model }`

**delete_api_key** (`DELETE /api/auth/api-key`)：
- 从 SQLite 删除用户的 API 密钥和元数据

#### 3.3.2 任务接口（全部需认证 + 用户隔离）

**list_jobs** (`GET /api/jobs`)：
- 调用 `store.list_jobs_by_user(&claims.sub)` 返回当前用户的任务
- 按 `sort_order` 升序（有值在前），无排序的按创建时间降序

**create_job** (`POST /api/jobs`)：
- 解析 multipart/form-data（`source_mode`, `arxiv_id`, `source_file`）
- 调用 `store.create_job_with_user()` 绑定用户 ID
- 保存上传文件到 `original/` 目录
- `tokio::spawn(worker::process_job(...))` 启动后台处理

**get_job** (`GET /api/jobs/:id`)：
- 验证任务所有权（`job.user_id == claims.sub`）
- 用于前端 3 秒轮询

**delete_job** (`DELETE /api/jobs/:id`)：
- 验证所有权后递归删除任务目录

**delete_all_jobs** (`DELETE /api/jobs`)：
- `store.delete_all_jobs_by_user()` 只删除当前用户的任务

**reorder_jobs** (`PUT /api/jobs/reorder`)：
- 接收 `{ order: [uuid1, uuid2, ...] }`
- 验证所有 job 属于当前用户
- 调用 `store.reorder_jobs()` 按数组顺序设置 `sort_order`

#### 3.3.3 AI 聊天代理 (`ai_chat_proxy`)

与初始版本相比的重大变化：

1. **不再接收 client 端传入的 `api_key` 和 `model`**
2. **从 SQLite 数据库获取**：根据用户 ID 获取加密存储的 `api_key`、`provider`、`model`
3. 调用 `ai::call_ai_api()` 进行请求
4. 支持多提供商的差异化处理

```rust
let api_key = state.auth.auth_service.db.get_user_api_key(&claims.sub)?;
let provider = state.auth.auth_service.db.get_user_api_provider(&claims.sub)?;
let model = state.auth.auth_service.db.get_user_api_model(&claims.sub)?;
let result = crate::ai::call_ai_api(&req, &api_key, &provider, &model).await;
```

#### 3.3.4 产物文件接口 (`get_out_artifact`)

路径模式改为 `/api/jobs/:id/out/*path`（而非旧版的 `/api/jobs/:id/artifacts/*path`）。

认证策略：
- **HTML 文件**（`.html` / `.htm`）：必须认证（从 header 或 query `?token=` 获取）
- **其他静态资源**（图片、CSS、JS 等）：直接放行，无需认证

#### 3.3.5 查询历史接口 (`save/List/get_query_history`)

三个新接口实现 AI 对话历史的持久化：

- `save_query_history`：将 `{ text_excerpt, text_hash, query, reply }` 保存到 `query_history/{hash}.json`
- `list_query_histories`：列出 job 下的所有查询历史（按时间倒序）
- `get_query_history`：根据 `text_hash` 获取特定的历史记录

---

### 3.4 持久化存储 —— `store.rs`

**职责**：将 `JobState` 和 `QueryHistory` 序列化为 JSON 文件存储在磁盘上。

#### 目录结构

```
jobs/
└── {uuid}/
    ├── original/          # 原始上传/下载的压缩包
    ├── src/               # 解压后的 LaTeX 源码
    ├── normalized/        # 规范化后的源码（预留）
    ├── out/               # 输出产物（main.html, main.xml）
    ├── meta/
    │   └── job.json       # 任务状态 JSON
    ├── log/               # 编译日志
    ├── overlay/           # LaTeXML 补丁定义
    └── query_history/     # AI 查询历史
        └── {text_hash}.json
```

#### 核心方法

新增方法（相比初始版本）：

| 方法 | 说明 |
|------|------|
| `create_job_with_user(sm, arxiv, user_id)` | 创建任务并绑定用户 ID |
| `list_jobs_by_user(user_id)` | 过滤返回指定用户的任务列表 |
| `reorder_jobs(job_ids)` | 按给定 ID 顺序设置 `sort_order` |
| `delete_all_jobs_by_user(user_id)` | 删除指定用户的所有任务 |
| `save_query_history(job_id, history)` | 保存查询历史到 `query_history/{hash}.json` |
| `list_query_histories(job_id)` | 读取所有 `query_history/*.json` 文件 |
| `get_query_history(job_id, text_hash)` | 读取单个查询历史文件 |

排序逻辑（`list_jobs`）：
```rust
jobs.sort_by(|a, b| {
    match (a.sort_order, b.sort_order) {
        (Some(ao), Some(bo)) => ao.cmp(&bo),     // 都有排序值
        (Some(_), None) => Less,                  // 有排序的在前
        (None, Some(_)) => Greater,               // 无排序的在后
        (None, None) => b.created_at.cmp(&a.created_at), // 都无排序按时间
    }
});
```

---

### 3.5 数据库 —— `database.rs`

**职责**：SQLite 数据库层，管理用户账户和 AI API 密钥。

#### 数据库表结构

```sql
-- 用户表
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);

-- API 密钥表（无外键约束，经迁移移除）
CREATE TABLE IF NOT EXISTS user_api_keys (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    encrypted_api_key TEXT NOT NULL,
    created_at TEXT NOT NULL
);

-- API 密钥元数据（提供商 + 模型）
CREATE TABLE IF NOT EXISTS user_api_keys_meta (
    user_id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    model TEXT NOT NULL
);

-- 任务表（用于未来数据迁移，当前实际使用文件系统）
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    -- ... 与 JobState 对应的字段
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);
```

#### 并发设计

使用 `parking_lot::Mutex<Connection>` 包裹 SQLite 连接，实现线程安全的数据库访问。

#### 核心方法

| 方法 | 说明 |
|------|------|
| `create_user(username, password_hash)` | 创建新用户，返回 User |
| `get_user_by_username(username)` | 按用户名查找用户 |
| `get_user_password_hash(username)` | 获取用户密码哈希 |
| `set_user_api_key(user_id, key, provider, model)` | 保存 API 密钥和元数据（先删后插） |
| `get_user_api_key(user_id)` | 获取加密的 API 密钥 |
| `get_user_api_provider(user_id)` | 获取 AI 提供商 |
| `get_user_api_model(user_id)` | 获取模型 ID |
| `delete_user_api_key(user_id)` | 删除 API 密钥和元数据 |

#### 迁移

`migrate_remove_api_key_fk()` 方法检测旧版本的外键约束并自动移除，确保 `user_api_keys` 表不受 users 表删除影响。

---

### 3.6 认证模块 —— `auth.rs`

**职责**：提供 JWT 签发/验证和 Argon2 密码哈希。

#### JWT 配置

- **密钥**: 硬编码 `paper_workflow_secret_key_change_in_production`（生产环境需更换）
- **有效期**: 7 天
- **Claims**: `sub` (user_id), `exp`, `iat`

```rust
pub struct Claims {
    pub sub: String,  // 用户 ID
    pub exp: i64,     // 过期时间
    pub iat: i64,     // 签发时间
}
```

#### AuthService 方法

| 方法 | 说明 |
|------|------|
| `hash_password(password)` | Argon2 哈希密码 |
| `verify_password(password, hash)` | 验证密码与哈希 |
| `create_token(user_id)` | 签发 JWT（7 天有效） |
| `validate_token(token)` | 验证 JWT，返回 Claims |
| `simple_encrypt(api_key)` | API 密钥简单加密（使用 Argon2 哈希） |

#### AppAuth

```rust
pub struct AppAuth {
    pub auth_service: AuthService,
}
```

包装 `AuthService`，作为共享状态注入路由。

---

### 3.7 AI 集成 —— `ai.rs`

**职责**：多提供商 AI API 集成，统一调用入口。

#### 配置 (`ai_config.json`)

```json
{
  "providers": {
    "deepseek": { "base_url": "https://api.deepseek.com", "api_path": "/chat/completions", "models": [...] },
    "openai": { "base_url": "https://api.openai.com/v1", "api_path": "/chat/completions", "models": [...] },
    "anthropic": { "base_url": "https://api.anthropic.com/v1", "api_path": "/messages", "models": [...], "requires_special_format": true },
    "google": { "base_url": "https://generativelanguage.googleapis.com/v1", "api_path": "/models/{model}:generateContent", "models": [...], "requires_special_format": true },
    "zhipu": { "base_url": "https://open.bigmodel.cn/api/paas/v4", "api_path": "/chat/completions", "models": [...] }
  }
}
```

#### ChatRequest

```rust
pub struct ChatRequest {
    pub query: String,       // 用户问题
    pub context: String,     // 划选内容
    pub full_paper: String,  // 论文全文
}
```

#### `call_ai_api` 函数

核心流程：

1. **加载配置**：从 `ai_config.json` 读取提供商配置
2. **构建上下文**：拼接论文摘要（前 30000 字）、划选内容、用户问题
3. **提供商差异化请求格式**：
   - `anthropic`：使用 Messages API 格式（`messages` + `system` 顶级参数）
   - `google`：使用 Gemini API 格式（`contents` + `system_instruction`）
   - 其他（deepseek/openai/zhipu）：标准 `/chat/completions` 格式
4. **发送请求**：`Authorization: Bearer {api_key}` 头
5. **解析响应**：按提供商路径提取回复文本
6. **返回结果**：纯文本回复

参数配置：
- 温度：0.7
- 最大 tokens：2000
- 系统提示：专业学术论文助手

---

### 3.8 后台任务 —— `worker.rs`

**职责**：异步执行论文转换的完整流水线。

与 documentation 一致，不再重复。关键保持不变：
- 两阶段：获取源码 → LaTeXML 编译
- Zip Slip 防护
- 超时控制（60s/60s/300s/120s）
- `.bbl` 注入
- LaTeXML 补丁（`tcolorbox`, `expl3`, `siunitx`）

---

## 4. 前端详解

### 4.1 入口与配置

#### `main.ts` —— 应用入口

```typescript
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import './style.css'
import App from './App.vue'
import { router } from './router'

createApp(App).use(createPinia()).use(router).mount('#app')
```

新增 `createPinia()` 注册 Pinia 状态管理。

#### `App.vue` —— 根组件

极简设计，仅包含 `<router-view />`。

#### `vite.config.ts` —— 构建配置

代理配置（新增 `/api/auth` 和 `/chat` 路径）：

```typescript
proxy: {
  '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
  '/chat': { target: 'http://127.0.0.1:8000', changeOrigin: true },
  '/artifacts': {
    target: 'http://127.0.0.1:8000/api/jobs',
    changeOrigin: true,
    rewrite: (path) => path.replace(/^\/artifacts\/([^/]+)/, '/$1/artifacts'),
  },
}
```

---

### 4.2 路由 —— `router.ts`

使用 `createWebHistory`（HTML5 History 模式），定义两条路由：

| 路径 | 组件 | 说明 |
|------|------|------|
| `/` | `HomeView` | 首页，任务列表 |
| `/jobs/:id` | `ReaderView` | 论文阅读页 |

**导航守卫**（新增）：

```typescript
router.beforeEach((to, _from, next) => {
  const token = localStorage.getItem('auth_token');
  if (!token && to.path !== '/') {
    next('/');   // 未登录强制跳回首页
  } else {
    next();
  }
});
```

未登录用户无法访问阅读页，自动重定向到首页。

---

### 4.3 TypeScript 类型 —— `api.ts`

新增类型（相比初始版本）：

```typescript
// 认证响应
export interface AuthResponse {
  user_id: string;
  username: string;
  token: string;
}

// API 密钥状态
export interface MaskedApiKey {
  has_key: boolean;
  masked: string | null;
  provider: string | null;
  model: string | null;
}

// AI 提供商类型
export type ApiProvider = 'deepseek' | 'openai' | 'anthropic' | 'google' | 'zhipu' | 'custom';

// 提供商常量列表
export const API_PROVIDERS = [
  { value: 'deepseek', label: 'DeepSeek' },
  { value: 'openai', label: 'OpenAI' },
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'google', label: 'Google AI' },
  { value: 'zhipu', label: '智谱AI' },
  { value: 'custom', label: '自定义' },
];

// 查询历史
export interface QueryHistory {
  text_excerpt: string;
  text_hash: string;
  query: string;
  reply: string;
  timestamp: string;
}
```

`JobState` 接口新增字段：
- `userId: string | null`
- `sortOrder?: number`

---

### 4.4 API 客户端 —— `client.ts`

基于 Axios 封装的 API 客户端，分为 `jobApi` 和 `authApi` 两个对象。

**关键新增**：Auth 拦截器

```typescript
// 请求拦截器：自动注入 auth_token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 响应拦截器：401 自动清除登录状态并跳转首页
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('auth_token');
      localStorage.removeItem('auth_user_id');
      localStorage.removeItem('auth_username');
      if (window.location.pathname !== '/') {
        window.location.href = '/';
      }
    }
    return Promise.reject(error);
  }
);
```

`jobApi` 对象方法：

| 方法 | HTTP 请求 | 说明 |
|------|----------|------|
| `listJobs()` | `GET /api/jobs` | 获取任务列表 |
| `getJob(id)` | `GET /api/jobs/:id` | 获取单个任务（轮询用） |
| `createJob(formData)` | `POST /api/jobs` | 创建任务（FormData） |
| `deleteJob(id)` | `DELETE /api/jobs/:id` | 删除单个任务 |
| `deleteAllJobs()` | `DELETE /api/jobs` | 删除所有任务 |
| `askAi(payload)` | `POST /api/chat` | AI 聊天请求 |
| `reorderJobs(order)` | `PUT /api/jobs/reorder` | 重排任务顺序 |
| `saveQueryHistory(jobId, history)` | `POST /api/jobs/:id/query-history` | 保存查询历史 |
| `getQueryHistory(jobId)` | `GET /api/jobs/:id/query-history` | 列出查询历史 |
| `getQueryHistoryForText(jobId, textHash)` | `GET /api/jobs/:id/query-history/:text_hash` | 获取特定查询历史 |

`authApi` 对象：

| 方法 | HTTP 请求 | 说明 |
|------|----------|------|
| `register(username, password)` | `POST /api/auth/register` | 注册 |
| `login(username, password)` | `POST /api/auth/login` | 登录 |
| `logout()` | `POST /api/auth/logout` | 登出 |
| `getMe()` | `GET /api/auth/me` | 获取用户信息 |
| `getApiKey()` | `GET /api/auth/api-key` | 获取 API 密钥状态 |
| `setApiKey(key, provider, model)` | `POST /api/auth/api-key` | 保存 API 密钥 |
| `deleteApiKey()` | `DELETE /api/auth/api-key` | 删除 API 密钥 |

---

### 4.5 全局样式 —— `style.css`

使用 Tailwind CSS 4 的 `@import "tailwindcss"` 指令引入框架。

自定义属性：
```css
:root {
  --color-accent: #b45309;       /* 琥珀色 - 品牌色 */
  --color-accent-dark: #78350f;
  --color-panel: rgba(255, 255, 255, 0.85);
}
```

全局样式：径向渐变背景、`glass-card` 毛玻璃效果类。

---

### 4.6 认证状态管理 —— `stores/auth.ts`

**职责**：Pinia store，管理用户认证状态和 API 密钥操作。

**状态**：

| 属性 | 类型 | 初始值 | 说明 |
|------|------|--------|------|
| `token` | `string \| null` | localStorage | JWT 令牌 |
| `userId` | `string \| null` | localStorage | 用户 ID |
| `username` | `string \| null` | localStorage | 用户名 |
| `isLoading` | `boolean` | false | 操作进行中 |
| `error` | `string \| null` | null | 错误信息 |

**计算属性**：

| 属性 | 说明 |
|------|------|
| `isAuthenticated` | `!!token.value` 是否有有效 token |

**操作方法**：

| 方法 | 说明 |
|------|------|
| `register(user, pass)` | 注册并自动登录 |
| `login(user, pass)` | 登录，保存 token/userId/username |
| `logout()` | 服务端登出 + 清除本地状态 |
| `getApiKey()` | 获取 API 密钥状态 |
| `setApiKey(key, provider, model)` | 保存 API 密钥和服务商信息 |
| `deleteApiKey()` | 删除 API 密钥 |

**持久化**：token、userId、username 同步到 `localStorage`（键名：`auth_token`、`auth_user_id`、`auth_username`）。

---

### 4.7 主页 —— `HomeView.vue`

**职责**：展示所有论文任务，提供新建、刷新、删除和设置入口。

**组件结构**：

```
HomeView
├── Hero 头部
│   ├── 未登录：登录/注册按钮
│   └── 已登录：
│       ├── 刷新按钮（RefreshCw）
│       ├── 清空所有（Trash2）
│       ├── UserMenu（下拉：API Key设置 + 退出登录）
│       └── 新建任务按钮（Plus）
├── 主体
│   ├── 未登录：提示"请登录后使用"
│   ├── 已登录无任务：空状态提示
│   └── 已登录有任务：draggable 任务网格
│       └── JobCard × N（可拖拽）
├── 拖拽删除栏（拖拽时出现）
├── NewJobModal（新建任务弹窗）
├── SettingsModal（AI 设置弹窗）
└── AuthModal（登录/注册弹窗）
```

**新增关键逻辑**（相比初始版本）：

**拖拽排序**：使用 `vuedraggable` 实现：
- `@start`：开启拖拽模式，显示磨砂背景和底部删除区
- `@end`：结束后调用 `jobApi.reorderJobs()` 按新顺序保存
- **拖拽删除**：将任务卡片拖到底部红色删除区，弹出确认后删除

**认证状态响应**：
- `watch(authStore.userId)`：登录状态变化时刷新任务列表
- 未登录时隐藏操作按钮，显示登录入口

---

### 4.8 阅读页 —— `ReaderView.vue`

**职责**：展示单个论文任务的处理进度，完成后加载 `PaperReader` 组件。

与之前的文档基本一致，核心轮询机制不变。新增对 404 和网络错误的处理。

---

### 4.9 任务卡片 —— `JobCard.vue`

与之前的文档基本一致，展示任务 ID、状态、来源、跳转按钮。

---

### 4.10 新建任务弹窗 —— `NewJobModel.vue`

与之前的文档基本一致，文件上传 / arXiv ID 两种模式切换。

---

### 4.11 论文阅读器 —— `PaperReader.vue`

**职责**：整个项目最核心、最复杂的组件，提供论文阅读和 AI 助手功能。

**组件架构**：

```
PaperReader
├── 悬浮按钮组（右上角）
│   ├── AI 助手按钮（Sparkles）
│   └── 锁定/解锁按钮（Lock / LockOpen）
├── 标记索引面板（左侧，可折叠）
│   └── marker × N（历史查询标记列表）
├── 论文内容区（中间，侧边栏打开时左移）
│   └── <iframe> 嵌入生成的 HTML 论文
└── AI 侧边栏（右侧，滑动开/关）
    ├── Header（标题 + "继续对话" 标签）
    ├── 聊天记录
    │   ├── 当前划选文本（引用高亮）
    │   ├── 用户消息（深色气泡）
    │   └── AI 回复（浅色气泡，Markdown 渲染）
    ├── 加载中动画
    └── 输入区（文本输入 + 发送按钮）
```

#### 关键技术点

**1. iframe 嵌入与认证**

论文 HTML 通过 `/api/jobs/{id}/out/main.html?token={jwt}` 加载，确保仅认证用户可以访问论文内容：

```typescript
const artifactUrl = computed(() => {
  const token = localStorage.getItem('auth_token');
  return `/api/jobs/${props.jobId}/out/main.html?token=${token}`;
});
```

**2. 划词选中监听**

多层事件监听策略：
1. **主窗口**：`mouseup`、`selectionchange`、`click` 事件
2. **iframe 内部**：`mouseup`、`selectionchange` 事件（需同源）
3. **降级处理**：通过 `iframeRef.value.contentWindow.getSelection()` 获取

**手动操作保护**：记录用户手动切换侧边栏的时间戳，1 秒内不自动打开。

**3. 滚轮事件转发**

侧边栏区域的滚轮滚动转发到 iframe 内部：

```typescript
const handleContainerWheel = (event: WheelEvent) => {
  const iframeWin = iframeRef.value?.contentWindow;
  if (!iframeWin) return;
  const target = event.target as Node;
  if (iframeEl.contains(target)) return;  // 避免双重滚动
  event.preventDefault();
  iframeWin.scrollBy({ top: event.deltaY, behavior: 'auto' });
};
```

**4. CSS 注入**

在 iframe 加载完成后，注入完整的学术风格 CSS：
- 使用 Georgia/宋体衬线字体
- 代码块、表格、引用块、图片等元素的样式优化
- 选中色为琥珀色（匹配品牌色）
- `ai-query-marker` 橙色标记点样式
- `ai-query-highlight` 选中文本高亮样式

**5. AI 查询标记（Marker）系统**

这是最核心的新功能：

**标记注入** (`injectMarker`)：
- 每次 AI 查询成功后，在论文中划选文本的末尾位置插入一个 `<span class="ai-query-marker">` 橙色圆点
- 标记使用 data-hash (SHA-256) 与 data-excerpt 属性关联到查询历史
- 点击标记触发 `loadHistoryForMarker()`

**标记恢复** (`restoreMarkers`)：
- iframe 加载完成后，从后端获取该任务的所有查询历史
- 对每条历史，使用 `findTextInDocument()` 在 DOM 中搜索对应的划选文本
- 成功定位后恢复标记，并自动加载最近一条历史到侧边栏

**标记侧边栏**：
- 左侧可折叠面板，列出所有标记
- 每个标记显示文本摘录和橙色圆点
- 点击跳转到论文中对应位置并恢复对话

**6. 继续对话模式**

- **新模式**：用户划选文本 → 侧边栏清空历史，开始新对话
- **继续模式**：用户点击已有标记 → 从后端加载完整对话历史，显示 "继续对话" 标签
- 后续提问时，将完整对话历史注入到 `query` 字段中，让 AI 理解上下文

```typescript
if (isContinuationMode.value) {
  const historyText = messages.value
    .slice(0, -1)
    .map(m => `${m.role === 'user' ? '用户' : 'AI'}: ${m.content}`)
    .join('\n\n');
  queryToSend = `以下是关于这段文本的对话历史：\n${historyText}\n\n---\n\n${userQuery}`;
}
```

**7. 悬浮控制按钮**

右上角两个按钮：
- **AI 助手按钮**：打开/关闭侧边栏
- **锁定/解锁按钮**：锁定后禁止 AI 自动弹出（`isLocked` 状态），需要手动点击才触发

**8. 生命周期管理**

`onMounted`：
- 设置滚轮转发
- 检查 API Key 是否存在
- 尝试恢复标记（最多重试 20 次 × 500ms）

`onUnmounted`：
- 清理全局事件监听器

---

### 4.12 AI 设置弹窗 —— `SettingsModal.vue`

**职责**：管理 AI API 密钥的服务端存储。

**重大变化**（相比初始版本使用 localStorage）：

现在全部操作通过后端 API 完成：

| 操作 | 后端 API | 说明 |
|------|---------|------|
| 加载 | `authStore.getApiKey()` | 获取掩码状态、提供商、模型 |
| 保存 | `authStore.setApiKey(key, provider, model)` | 服务端加密存储 |
| 清除 | `authStore.deleteApiKey()` | 服务端删除 |

**新增字段**：
- **AI 服务提供商**：下拉选择（DeepSeek, OpenAI, Anthropic, Google AI, 智谱AI, 自定义）
- **模型 ID**：文本输入，如 `deepseek-v4-flash`, `gpt-4` 等

**状态管理**：
- `isFetching`：页面加载时获取后端密钥状态
- 已有密钥时显示 `********`，输入框禁用
- 输入新密钥自动覆盖保存

---

### 4.13 登录/注册弹窗 —— `AuthModal.vue`

**职责**：提供用户登录和注册界面。

**功能**：

| 模式 | 接口 | 校验 |
|------|------|------|
| 登录 | `authStore.login(username, password)` | 用户名非空、密码 ≥ 6 字符 |
| 注册 | `authStore.register(username, password)` | 同上 + 两次密码一致 |

**UI 设计**：
- 带 backdrop blur 的背景遮罩
- 登录/注册切换按钮
- 表单验证提示（红色错误框）
- 提交按钮带加载状态

**交互流程**：
1. 用户在首页点击"登录 / 注册"
2. 弹窗显示，默认登录模式
3. 用户可点击底部链接切换到注册模式
4. 提交后调用 authStore 对应方法
5. 成功后自动关闭弹窗并刷新任务列表

---

### 4.14 用户菜单 —— `UserMenu.vue`

**职责**：已登录用户的头像下拉菜单。

**结构**：

```
UserMenu
├── 触发器：用户名 + 用户图标 + 下箭头
└── 下拉菜单（点击展开）
    ├── 「API 密钥设置」（Key 图标）
    └── 「退出登录」（红色，LogOut 图标）
```

**登录退出**：调用 `authStore.logout()` 清除本地状态，跳转首页。

---

## 5. 数据流与工作流程

### 5.1 用户认证流程

```
用户操作               前端                   后端                      SQLite
─────────           ────────              ────────                   ────────
1. 填写用户名密码      │                      │                         │
                      │  POST /auth/register  │                         │
2. 点击注册/登录 ────→│  {username, password} │                         │
                      │  ──────────────────→  │  3. Argon2 哈希密码      │
                      │                      │  4. INSERT INTO users    │
                      │                      │  ──────────────────────────→
                      │                      │  5. 生成 JWT token        │
                      │  200 + AuthResponse  │                         │
                      │  ←────────────────── │                         │
                      │                      │                         │
6. 保存到 localStorage│                      │                         │
   后续请求自动注入    │                      │                         │
   Authorization 头 ──→│  ──── 所有 API ────→ │  7. validate_token()     │
                      │                      │  8. 执行操作并返回        │
```

### 5.2 创建任务 → 完成阅读

```
用户操作               前端                   后端                          文件系统/外部
─────────           ────────              ────────                       ──────────────
1. 填写 arXiv ID      │                      │                              │
   或上传文件         │                      │                              │
                      │  POST /api/jobs      │                              │
2. 点击提交 ────────→ │  (FormData + Auth)   │                              │
                      │  ──────────────────→ │  3. 创建 JobState (with userId) │
                      │                      │  ├─ 生成 UUID                │
                      │                      │  ├─ 创建目录结构             │ ──→ jobs/{uuid}/
                      │                      │  ├─ 保存 job.json            │ ──→ meta/job.json
                      │                      │  └─ 保存上传文件             │ ──→ original/
                      │                      │                              │
                      │  201 + JobState      │  4. tokio::spawn(worker)     │
                      │  ←────────────────── │      │                       │
                      │                      │      │                       │
                      │  跳转 ReaderView     │      ▼                       │                 
5. 显示"处理中" ─────→|  每 3 秒轮询          │  5. ArXiv 下载 / 解压        │
                      │  GET /api/jobs/:id   │  ├─ download_from_arxiv()    │ ──→ https://arxiv.org
                      │  ─────────────────→  │  ├─ execute_extraction()     │ ──→ src/
                      │  ←── JobState ─────  │  └─ save_job()               │
                      │                      │                              │
                      │                      │  6. LaTeXML 编译             │
                      │                      │  ├─ pdflatex -draftmode      │ ──→ 生成 .aux/.bbl
                      │                      │  ├─ latexml → main.xml       │ ──→ out/main.xml
                      │                      │  ├─ latexmlpost → main.html  │ ──→ out/main.html
                      │                      │  └─ save_job(Completed)      │
                      │                      │                              │
6. 状态变为 completed │  ←── JobState ─────   │                              │
    ───────────────→   │  停止轮询             │                              │
                      │  加载 PaperReader     │                              │
7. 阅读论文 ───────→  │ iframe: out/main.html │  GET .../out/main.html       │
                      │  ?token=jwt           │  ├── 验证 token              │
                      │  ──────────────────→  │  ├── serve_file()            │ ──→ out/main.html
                      │                      │  └── CSP + CORS 头           │
                      │                      │                              │
8. 加载标记 ────────→ │  GET query-history    │                              │
                      │  ──────────────────→  │  ──→ query_history/*.json ── │
                      │  findTextInDocument() │                              │
                      │  恢复标记到论文        │                              │
                      │                      │                              │
9. 划选文本提问 ──→  │  POST /api/chat       │                              │
                      │  ──────────────────→  │  10. 从 SQLite 获取 API Key  │
                      │                      │  ├── get_user_api_key()       │ ──→ user_api_keys
                      │                      │  ├── get_user_api_provider()  │ ──→ user_api_keys_meta
                      │                      │  ├── get_user_api_model()     │
                      │                      │  11. call_ai_api()            │
                      │                      │  ├── 构建差异化请求格式        │
                      │                      │  └── 发送请求                 │ ──→ DeepSeek/OpenAI/...
                      │  ←── AI 回复 ───────  │                              │
                      │                      │                              │
12. 注入标记 ───────→ │  POST query-history   │                              │
                      │  injectMarker()       │  ──→ query_history/{hash}.json
                      │                      │                              │
13. 点击已有标记 ──→  │  GET query-history    │  恢复对话历史                 │
    (继续对话模式)     │  :text_hash           │  ──→ query_history/{hash}.json
```

### 5.3 数据持久化

```
jobs/
└── {job-uuid}/
    ├── original/
    │   └── 2401.12345.tar.gz    # 原始压缩包
    ├── src/
    │   ├── main.tex              # 解压后的 LaTeX 源码
    │   ├── figures/              # 论文图片
    │   └── ...
    ├── out/
    │   ├── main.html             # 最终生成的 HTML 论文
    │   └── main.xml              # LaTeXML 中间产物
    ├── meta/
    │   └── job.json              # 任务状态 JSON（含 sortOrder, userId）
    ├── log/
    │   ├── preflight.log         # pdflatex 预编译日志
    │   ├── latexml.log           # latexml 编译日志
    │   └── latexmlpost.log       # latexmlpost 渲染日志
    └── query_history/
        └── {sha256-hash}.json    # AI 查询历史（按文本哈希索引）
```

`paper_workflow.db`（SQLite 数据库）：
- `users`：用户账户（用户名 + Argon2 哈希）
- `user_api_keys`：加密的 API 密钥
- `user_api_keys_meta`：AI 提供商 + 模型配置
- `jobs`：任务记录（预留，实际存储使用文件系统）

---

## 6. 部署与运行

### 6.1 环境要求

| 依赖 | 版本 | 说明 |
|------|------|------|
| Rust | 2024 edition | 使用 `rustup` 安装 |
| Node.js | ≥ 18 | 推荐 LTS 版本 |
| LaTeXML | 最新 | `apt install latexml` |
| pdfTeX | 最新 | `apt install texlive-pdflatex` |
| BibTeX 工具 | 可选 | `apt install texlive-bibtex-extra` |

### 6.2 运行方式

**启动后端**（终端 1）：

```bash
cd backend/paper-workflow
cargo run
```

后端将在 `http://127.0.0.1:8000` 启动，`jobs/` 目录和 `paper_workflow.db` 数据库自动创建。

**启动前端**（终端 2）：

```bash
cd frontend/paper-workflow
npm install
npm run dev
```

前端将在 `http://localhost:5173` 启动，Vite 代理自动转发 API 请求到后端。

**使用**：

1. 打开浏览器访问 `http://localhost:5173`
2. 点击 **登录 / 注册** 创建账户
3. 登录后点击 **新建任务**，输入 arXiv ID 或上传 `.tar.gz` 文件
4. 等待任务处理完成（可看到实时状态变化）
5. 点击任务卡片进入阅读页
6. 在 **用户菜单 → API 密钥设置** 中配置 AI 提供商、模型和 API 密钥
7. 选中论文中的文本，通过 AI 助手提问
8. 历史提问以橙色标记保留在论文中，可随时点击恢复对话

---

> **ChatHTML** 项目采用 Rust + Vue 3 全栈架构，前后端职责分离明确。  
> 后端使用 Rust 保证性能和安全性，前端使用 Vue 3 提供流畅的交互体验。  
> 系统支持用户认证、多提供商 AI 集成、对话历史持久化与标记恢复，  
> 核心流程为：获取源码 → 安全解压 → LaTeXML 编译 → 交互式阅读 + AI 划词问答。
