# ChatHTML 项目技术手册

> **ChatHTML** 是一个将学术论文（LaTeX 源码）自动转换为交互式 HTML 的 Web 应用，内置基于 DeepSeek API 的学术 AI 助手，支持划词提问。  
> 后端使用 **Rust + Axum**，前端使用 **Vue 3 + Vite + Tailwind CSS**。

---

## 目录

1. [项目概述](#1-项目概述)
2. [项目结构](#2-项目结构)
3. [后端详解](#3-后端详解)
   - 3.1 [入口文件 —— main.rs](#31-入口文件--mainrs)
   - 3.2 [数据模型 —— models.rs](#32-数据模型--modelsrs)
   - 3.3 [API 路由 —— routes.rs](#33-api-路由--routesrs)
   - 3.4 [持久化存储 —— store.rs](#34-持久化存储--storers)
   - 3.5 [后台任务 —— worker.rs](#35-后台任务--workerrs)
4. [前端详解](#4-前端详解)
   - 4.1 [入口与配置 —— main.ts / App.vue / vite.config.ts](#41-入口与配置)
   - 4.2 [路由 —— router.ts](#42-路由--routerts)
   - 4.3 [TypeScript 类型 —— api.ts](#43-typescript-类型--apits)
   - 4.4 [API 客户端 —— client.ts](#44-api-客户端--clientts)
   - 4.5 [全局样式 —— style.css](#45-全局样式--stylecss)
   - 4.6 [主页 —— HomeView.vue](#46-主页--homeviewvue)
   - 4.7 [阅读页 —— ReaderView.vue](#47-阅读页--readerviewvue)
   - 4.8 [任务卡片 —— JobCard.vue](#48-任务卡片--jobcardvue)
   - 4.9 [新建任务弹窗 —— NewJobModel.vue](#49-新建任务弹窗--newjobmodelvue)
   - 4.10 [论文阅读器 —— PaperReader.vue](#410-论文阅读器--paperreadervue)
   - 4.11 [AI 设置弹窗 —— SettingsModal.vue](#411-ai-设置弹窗--settingsmodalvue)
5. [数据流与工作流程](#5-数据流与工作流程)
6. [部署与运行](#6-部署与运行)
7. [常见问题与扩展](#7-常见问题与扩展)

---

## 1. 项目概述

### 核心能力

| 功能 | 说明 |
|------|------|
| **论文源码 → HTML** | 支持上传 `.tar.gz` 压缩包或直接输入 arXiv ID，后端自动下载、解压、通过 LaTeXML 编译为 HTML |
| **交互式阅读** | 使用 `<iframe>` 嵌入生成的 HTML 论文，提供沉浸式阅读体验 |
| **划词 AI 助手** | 选中论文中的文本，自动弹出侧边栏，调用 DeepSeek API 进行问答 |
| **任务管理** | 创建、查看、删除论文转换任务，实时轮询进度 |

### 技术栈

| 层 | 技术 | 说明 |
|----|------|------|
| 后端框架 | **Axum** (Rust) | 高性能异步 Web 框架 |
| 后端运行时 | **Tokio** | 异步运行时，处理并发请求与后台任务 |
| 序列化 | **Serde** | JSON 序列化/反序列化 |
| 持久化 | **文件系统** | 每个任务一个目录，状态存为 `meta/job.json` |
| 前端框架 | **Vue 3** (Composition API + `<script setup>`) | 响应式 UI |
| 构建工具 | **Vite** | 开发服务器与生产构建 |
| 样式 | **Tailwind CSS 4** | 原子化 CSS |
| 路由 | **vue-router 4** | 单页应用路由 |
| HTTP 客户端 | **Axios** | 前后端通信 |
| AI API | **DeepSeek Chat API** | 学术问答 |

---

## 2. 项目结构

```
ChatHTML/
├── API_SPEC.md                  # API 接口说明文档
├── backend/
│   └── paper-workflow/          # Rust 后端项目
│       ├── Cargo.toml           # Rust 依赖配置
│       └── src/
│           ├── main.rs          # 入口：启动服务器、声明模块、组装路由
│           ├── models.rs        # 数据模型定义（JobState、JobStatus 等）
│           ├── routes.rs        # API 路由处理函数（8 个接口）
│           ├── store.rs         # 持久化存储层（文件系统读写）
│           └── worker.rs        # 后台任务处理（下载、解压、编译流水线）
├── frontend/
│   └── paper-workflow/          # Vue 3 前端项目
│       ├── package.json         # npm 依赖
│       ├── vite.config.ts       # Vite 配置（含代理）
│       ├── index.html           # HTML 入口
│       └── src/
│           ├── main.ts          # Vue 应用挂载
│           ├── App.vue          # 根组件（router-view）
│           ├── router.ts        # 路由定义
│           ├── style.css        # 全局样式 + Tailwind 导入
│           ├── api/
│           │   └── client.ts    # Axios API 客户端
│           ├── types/
│           │   └── api.ts       # TypeScript 类型定义
│           ├── views/
│           │   ├── HomeView.vue     # 首页（任务列表 + 新建/设置入口）
│           │   └── ReaderView.vue   # 论文阅读页（轮询等待 + 加载 PaperReader）
│           └── components/
│               ├── JobCard.vue         # 任务卡片组件
│               ├── NewJobModel.vue     # 新建任务弹窗
│               ├── PaperReader.vue     # 论文阅读器（核心组件）
│               └── SettingsModal.vue   # AI 设置弹窗
└── jobs/                        # （运行时生成）任务数据存储目录
```

---

## 3. 后端详解

### 3.1 入口文件 —— `main.rs`

**职责**：初始化日志、创建 `JobStore`、组装路由、启动 HTTP 服务器。

关键步骤如下：

1. **模块声明**：`mod models; mod routes; mod store; mod worker;` 告诉 Rust 编译器加载同级目录中的这四个模块文件。

2. **初始化日志**：使用 `tracing_subscriber` 在终端输出每个 HTTP 请求的详细信息，方便调试。

3. **创建 `JobStore`**：指定 `./jobs` 为数据存储根目录，包装在 `Arc`（原子引用计数指针）内，实现多线程安全共享。

4. **创建共享状态**：`Arc<AppState>` 结构体包裹 `JobStore`，注入到所有路由处理函数中。

5. **配置 CORS**：开发环境下允许任意来源（`Any`），生产环境建议收紧。

6. **组装路由**：

   | 方法 | 路径 | 处理函数 | 说明 |
   |------|------|---------|------|
   | GET | `/api/jobs` | `list_jobs` | 获取任务列表 |
   | POST | `/api/jobs` | `create_job` | 创建任务（上传/arXiv） |
   | DELETE | `/api/jobs` | `delete_all_jobs` | 删除所有任务 |
   | GET | `/api/jobs/:id` | `get_job` | 获取单个任务详情 |
   | DELETE | `/api/jobs/:id` | `delete_job` | 删除单个任务 |
   | POST | `/api/chat` | `ai_chat_proxy` | AI 聊天代理 |
   | GET | `/api/jobs/:id/artifacts/*path` | `get_artifact` | 获取产物文件 |
   | GET | `/api/jobs/:id/html` | `get_html_content` | 获取 HTML 文本 |

7. **启动服务器**：绑定 `127.0.0.1:8000`，使用 `axum::serve` 提供 HTTP 服务。

```rust
// main.rs 核心代码示意
let app = Router::new()
    .route("/api/jobs", get(list_jobs).post(create_job).delete(delete_all_jobs))
    .route("/api/jobs/:id", get(get_job).delete(delete_job))
    .route("/api/chat", post(ai_chat_proxy))
    .route("/api/jobs/:id/artifacts/*path", get(get_artifact))
    .route("/api/jobs/:id/html", get(get_html_content))
    .with_state(app_state)
    .layer(TraceLayer::new_for_http())
    .layer(cors);
```

---

### 3.2 数据模型 —— `models.rs`

**职责**：定义任务生命周期的所有数据结构，前后端通过 JSON（camelCase）交换。

#### `JobStatus` —— 任务状态枚举

```rust
pub enum JobStatus {
    Created,        // 刚创建
    Queued,         // 排队中
    Downloading,    // 正在从 arXiv 下载
    Validating,     // 验证上传文件
    Extracting,     // 解压源码
    Analyzing,      // 分析源码结构
    Processing,     // 正在处理
    Completed,      // 成功完成
    Partial,        // 部分成功
    Error,          // 失败
}
```

使用 `#[serde(rename_all = "camelCase")]` 确保序列化为 JSON 时使用驼峰命名（如 `"downloading"`），与前端 TypeScript 类型保持一致。

#### `StageStatus` 与 `StageDetail`

每个任务的处理过程分为多个阶段（Stage），每个阶段包含标题、状态和详细描述。这些信息用于前端的时间轴展示。

```rust
pub struct StageDetail {
    pub title: String,    // 阶段标题，如 "下载源码"
    pub status: StageStatus,  // pending / running / done / error / skipped
    pub detail: String,   // 详细信息，如 "正在从 arXiv 获取..."
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

这是整个系统的中枢数据结构，存储任务的所有信息：

| 字段 | 类型 | 说明 |
|------|------|------|
| `job_id` | `Uuid` | 全局唯一标识 |
| `created_at` | `DateTime<Utc>` | 创建时间 |
| `status` | `JobStatus` | 当前状态 |
| `source_mode` | `SourceMode` | 来源模式 |
| `arxiv_id` | `Option<String>` | arXiv ID（仅 Arxiv 模式） |
| `original_name` | `Option<String>` | 上传文件原名（仅 Upload 模式） |
| `archive_size` | `Option<u64>` | 压缩包大小 |
| `errors` | `Vec<String>` | 错误信息列表 |
| `warnings` | `Vec<String>` | 警告信息列表 |
| `duration_seconds` | `Option<f64>` | 处理耗时 |
| `artifacts` | `HashMap<String, String>` | 产物文件路径映射，如 `{"html": "out/main.html"}` |
| `stage_details` | `Vec<StageDetail>` | 详细阶段列表 |
| `manifest` | `Option<serde_json::Value>` | 论文元数据（LaTeXML 解析结果） |

---

### 3.3 API 路由 —— `routes.rs`

**职责**：实现 8 个 HTTP 接口的处理逻辑。

#### 3.3.1 共享状态

```rust
pub struct AppState {
    pub store: Arc<JobStore>,
}
```

通过 Axum 的 `State` 提取器注入到每个处理函数。

#### 3.3.2 获取任务列表 (`list_jobs`)

调用 `store.list_jobs()` 返回所有任务，按创建时间倒序。内部通过读取 `jobs/` 目录下的所有 UUID 子目录来获取任务列表。

#### 3.3.3 获取单个任务 (`get_job`)

从 URL 路径中提取 `Uuid`，调用 `store.load_job(job_id)`。如果找不到则返回 `404 Not Found`。

此接口被前端用于**轮询**（每 3 秒一次），监控任务处理进度。

#### 3.3.4 创建任务 (`create_job`)

这是最复杂的接口。使用 `Multipart` 提取器解析 multipart/form-data：

- **解析表单字段**：`source_mode`（"upload"/"arxiv"）、`arxiv_id`、`source_file`
- **创建 Job**：调用 `store.create_job()` 创建目录结构并保存初始状态
- **保存文件**：如果是上传模式且有文件，写入 `original/` 目录
- **启动后台任务**：`tokio::spawn(crate::worker::process_job(...))` —— 在后台线程处理整个转换流水线
- **返回**：`201 Created` + 新创建的 `JobState`

#### 3.3.5 AI 聊天代理 (`ai_chat_proxy`)

接收前端发来的 `ChatRequest`：

```rust
pub struct ChatRequest {
    pub query: String,         // 用户问题
    pub context: String,       // 划选的论文文本
    pub model: String,         // 模型名称（如 "deepseek-chat"）
    pub api_key: String,       // API 密钥
    pub full_paper: String,    // 整篇论文的文本内容
}
```

处理流程：

1. **验证 API Key**：非空且长度 >= 8
2. **构建上下文**：将论文全文、划选文本、用户问题拼接
3. **调用 DeepSeek API**：发送 POST 请求到 `https://api.deepseek.com/v1/chat/completions`
4. **返回结果**：包含 AI 回复、使用的模型、上下文长度等元信息

`call_ai_api` 函数是实际的 API 调用逻辑，包含超时处理、错误映射等。

#### 3.3.6 删除任务 (`delete_job` / `delete_all_jobs`)

调用 store 的 `delete_job` / `delete_all_jobs` 方法，递归删除对应的目录树。

#### 3.3.7 获取产物文件 (`get_artifact`)

通用文件服务接口。路径模式 `/api/jobs/:id/artifacts/*path` 中的 `*path` 会捕获剩余路径（如 `out/main.html`）。

关键特性：
- **安全路径检查**：确保文件存在且是普通文件
- **自动 MIME 类型**：使用 `mime_guess` 根据扩展名推断
- **缓存控制**：`Cache-Control: public, max-age=3600`
- **CSP 头**：允许 iframe 嵌入（`frame-ancestors 'self' http://localhost:5173`）
- **跨域支持**：`Access-Control-Allow-Origin: *`

#### 3.3.8 获取 HTML 内容 (`get_html_content`)

专门为前端 `srcdoc` 场景设计，返回 `text/plain` 类型的 HTML 内容（而非直接渲染），避免浏览器的同源策略限制。

---

### 3.4 持久化存储 —— `store.rs`

**职责**：将 `JobState` 序列化为 JSON 文件存储在磁盘上。

#### 目录结构

```
jobs/
└── {uuid}/
    ├── original/       # 原始上传/下载的压缩包
    ├── src/            # 解压后的 LaTeX 源码
    ├── normalized/     # 规范化后的源码（预留）
    ├── out/            # 输出产物（main.html, main.xml）
    ├── meta/
    │   └── job.json    # 任务状态 JSON
    └── log/            # 编译日志
```

#### 核心方法

| 方法 | 说明 |
|------|------|
| `new(path)` | 创建 JobStore，指定根目录 |
| `create_job(source_mode, arxiv_id)` | 生成 UUID、创建目录结构、保存初始 `job.json` |
| `save_job(job)` | 将 `JobState` 序列化写入 `meta/job.json` |
| `load_job(job_id)` | 从磁盘读取 `meta/job.json` 反序列化为 `JobState` |
| `list_jobs()` | 扫描 `jobs/` 下所有 UUID 命名的子目录，加载每个任务并倒序排列 |
| `get_job_file_path(job_id, sub_dir, filename)` | 拼接文件路径 |
| `get_job_path(job_id)` | 获取任务根目录 |
| `delete_job(job_id)` | 递归删除任务目录 |
| `delete_all_jobs()` | 遍历删除所有 UUID 子目录 |

所有文件操作都是异步的（`tokio::fs`），不阻塞主线程。

---

### 3.5 后台任务 —— `worker.rs`

**职责**：异步执行论文转换的完整流水线，是最核心的业务逻辑。

#### 整体流程

```
process_job()
  ├── [阶段一] 获取源码
  │   ├── Arxiv 模式: download_from_arxiv() → execute_extraction()
  │   └── Upload 模式: execute_extraction()
  └── [阶段二] LaTeXML 编译
      └── run_latexml_pipeline()
            ├── 预编译 (pdflatex -draftmode)
            ├── 注入 .bbl 参考文献
            ├── latexml → main.xml
            └── latexmlpost → main.html
```

#### 详细说明

**阶段一：获取并解压源码**

- **ArXiv 模式** (`run_arxiv_workflow`)：
  - 从 `https://arxiv.org/src/{arxiv_id}` 下载 `.tar.gz`
  - 保存到 `original/` 目录
  - 调用 `execute_extraction()` 解压到 `src/` 目录

- **Upload 模式** (`run_upload_workflow`)：
  - 扫描 `original/` 目录找到上传的文件
  - 调用 `execute_extraction()` 解压

- **安全解压** (`execute_extraction`)：
  - 使用 `flate2` + `tar` 库在阻塞线程池中解压
  - **路径穿越保护**：检查每个条目是否包含绝对路径或 `../` 父目录引用（Zip Slip 防护）
  - 解压到 `src/` 目录

**阶段二：LaTeXML 编译** (`run_latexml_pipeline`)

这是将 LaTeX 转换为 HTML 的核心步骤：

1. **找主文件** (`find_root_tex`)：扫描 `src/` 目录，寻找同时包含 `\documentclass` 和 `\begin{document}` 的 `.tex` 文件
2. **预编译**：运行 `pdflatex -draftmode` 生成辅助文件（`.aux`、`.bbl` 等）
3. **注入参考文献**：如果存在 `.bbl` 文件，将 `\bibliography` 替换为 `\input{file.bbl}`，内联参考文献
4. **宏包兼容补丁**：创建 LaTeXML 补丁文件（如 `tcolorbox.sty.ltxml`），处理不兼容的 LaTeX 宏包
5. **LaTeXML**：调用 `latexml` 将 LaTeX 编译为 XML（`out/main.xml`），超时 300 秒
6. **HTML 生成**：调用 `latexmlpost` 将 XML 转换为 HTML5（`out/main.html`），超时 120 秒

`run_step_with_timeout` 是一个通用辅助函数，包装外部命令的执行：
- 将 stdout/stderr 重定向到日志文件
- 使用 `tokio::time::timeout` 实现超时控制
- 超时后强制 `kill` 子进程

**状态更新机制**：

`update_stage()` 函数用于更新阶段详情：
- 如果该标题的阶段已存在，更新其状态和详情
- 否则新建一个 `StageDetail` 添加到列表中

`store.save_job()` 在每个阶段变化时被调用，确保前端轮询能获取最新状态。

---

## 4. 前端详解

### 4.1 入口与配置

#### `main.ts` —— 应用入口

```typescript
import { createApp } from 'vue'
import './style.css'
import App from './App.vue'
import { router } from './router'

createApp(App).use(router).mount('#app')
```

标准 Vue 3 初始化，注册路由插件。

#### `App.vue` —— 根组件

极简设计，仅包含 `<router-view />`，由路由控制显示哪个页面。

#### `vite.config.ts` —— 构建配置

使用 Vite + Vue 插件 + Tailwind CSS Vite 插件。

**代理配置**是关键：将前端的 API 请求转发到后端（`http://127.0.0.1:8000`），避免跨域问题。

```typescript
proxy: {
  '/api/jobs': { target: 'http://127.0.0.1:8000', changeOrigin: true },
  '/api/chat': { target: 'http://127.0.0.1:8000', changeOrigin: true },
  '/artifacts': {                     // 论文资源代理
    target: 'http://127.0.0.1:8000/api/jobs',
    changeOrigin: true,
    rewrite: (path) => path.replace(/^\/artifacts\/([^/]+)/, '/$1/artifacts'),
  },
}
```

`/artifacts` 路径的 rewrite 规则示例：
- 前端请求：`/artifacts/uuid-xxx/out/main.html`
- 代理转发：`/api/jobs/uuid-xxx/artifacts/out/main.html`

---

### 4.2 路由 —— `router.ts`

使用 `createWebHistory`（HTML5 History 模式），定义两条路由：

| 路径 | 组件 | 说明 |
|------|------|------|
| `/` | `HomeView` | 首页，任务列表 |
| `/jobs/:id` | `ReaderView` | 论文阅读页，`:id` 为任务 UUID |

---

### 4.3 TypeScript 类型 —— `api.ts`

与后端 `models.rs` 一一对应的前端类型定义：

```typescript
export type JobStatus = 'created' | 'queued' | 'downloading' | ... | 'error';
export type SourceMode = 'upload' | 'arxiv';
export type StageStatus = 'pending' | 'running' | 'done' | 'error' | 'skipped';

export interface JobState {
  jobId: string;              // 对应 Rust 的 job_id (camelCase)
  createdAt: string;          // ISO 8601
  status: JobStatus;
  sourceMode: SourceMode;
  arxivId: string | null;
  originalName: string | null;
  archiveSize: number | null;
  errors: string[];
  warnings: string[];
  durationSeconds: number | null;
  artifacts: Record<string, string>;
  stageDetails: StageDetail[];
}
```

注意字段名使用 JavaScript 的 camelCase 风格，与后端 `#[serde(rename_all = "camelCase")]` 对应。

---

### 4.4 API 客户端 —— `client.ts`

基于 Axios 封装的 API 客户端，导出一个 `jobApi` 对象，包含 5 个方法：

| 方法 | HTTP 请求 | 说明 |
|------|----------|------|
| `listJobs()` | `GET /api/jobs` | 获取任务列表 |
| `getJob(id)` | `GET /api/jobs/:id` | 获取单个任务（轮询用） |
| `createJob(formData)` | `POST /api/jobs` | 创建任务（FormData） |
| `deleteJob(id)` | `DELETE /api/jobs/:id` | 删除单个任务 |
| `deleteAllJobs()` | `DELETE /api/jobs` | 删除所有任务 |
| `askAi(payload)` | `POST /api/chat` | AI 聊天请求 |

所有方法均为 `async`，返回 Promise。基础 URL 为 `http://127.0.0.1:8000/api`，通过 Vite 代理转发。

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

全局样式设置：
- 背景使用双渐变辐射效果，营造学术/柔和氛围
- `glass-card` 类实现毛玻璃效果（`backdrop-filter: blur(24px)`）

---

### 4.6 主页 —— `HomeView.vue`

**职责**：展示所有论文任务，提供新建、刷新、删除和设置入口。

**组件结构**：

```
HomeView
├── Hero 头部（标题 + 操作按钮）
│   ├── 刷新按钮（RefreshCw）
│   ├── 清空所有（Trash2）
│   ├── 设置（Settings → 打开 SettingsModal）
│   └── 新建任务（Plus → 打开 NewJobModal）
├── 任务网格
│   ├── 空状态提示（无任务时）
│   └── JobCard × N（任务卡片列表）
├── NewJobModal（新建任务弹窗）
└── SettingsModal（AI 设置弹窗）
```

**关键逻辑**：

- `refresh()`：调用 `jobApi.listJobs()` 获取最新任务列表
- `onJobCreated(newJob)`：将新任务插入列表头部（`unshift`），无需刷新
- `deleteJob(jobId)`：调用 API 删除后从本地列表移除
- `deleteAllJobs()`：二次确认后调用 API 清空

`onMounted(refresh)` —— 页面加载时自动拉取任务列表。

---

### 4.7 阅读页 —— `ReaderView.vue`

**职责**：展示单个论文任务的处理进度，完成后加载 `PaperReader` 组件。

**核心机制 —— 轮询**：

```typescript
const checkStatus = async () => {
  job.value = await jobApi.getJob(jobId);
  if (['completed', 'error'].includes(job.value.status)) {
    clearTimeout(pollTimer);    // 到达终态，停止轮询
  } else {
    pollTimer = setTimeout(checkStatus, 3000);  // 每 3 秒查一次
  }
};
```

**三种状态视图**：

| 状态 | 显示内容 |
|------|---------|
| `completed` | 加载 `<PaperReader>` 组件 |
| `error` | 显示错误详情、重试按钮、返回首页按钮 |
| 处理中 | 旋转加载动画 + 当前状态文本 |

顶部状态栏显示返回按钮、任务 ID、当前状态标签。

> **边界情况处理**：如果 API 返回 404（任务被删除），显示"任务不存在"错误；网络错误时显示提示并停止轮询。

---

### 4.8 任务卡片 —— `JobCard.vue`

**职责**：在主页网格中展示单个任务的摘要信息。

**UI 设计**：

- **头部**：显示任务 ID 前 13 位 + 状态标签（颜色编码）
- **主体**：来源类型图标 + 来源标识（arXiv ID / "Manual Upload"）
- **底部**："查看详情"按钮，点击跳转至 `/jobs/:id`
- **悬浮操作**：鼠标悬停时显示右上角的删除按钮

**状态可视化**：

```typescript
const statusUI = {
  completed:   { color: 'text-emerald-600 bg-emerald-50', icon: CheckCircle2, label: '已完成' },
  error:       { color: 'text-rose-600 bg-rose-50', icon: XCircle, label: '失败' },
  processing:  { color: 'text-amber-600 bg-amber-50 animate-pulse', icon: Loader2, label: '处理中' },
  downloading: { color: 'text-blue-600 bg-blue-50 animate-pulse', icon: Loader2, label: '下载中' },
  validating:  { color: 'text-indigo-600 bg-indigo-50 animate-pulse', icon: Loader2, label: '校验中' },
  queued:      { color: 'text-slate-400 bg-slate-100', icon: Clock, label: '排队中' },
};
```

进行中的状态使用 `animate-pulse` 脉冲动画，表示活跃。

---

### 4.9 新建任务弹窗 —— `NewJobModel.vue`

**职责**：提供创建新任务的表单界面。

**两种模式切换**：

| 模式 | 输入 | 说明 |
|------|------|------|
| 文件上传 | 文件选择器（accept `.tar.gz, .tgz`） | 上传本地 LaTeX 源码包 |
| arXiv ID | 文本输入框（placeholder: "2401.12345"） | 自动从 arXiv 下载 |

**提交流程**：

1. 构建 `FormData`
2. 调用 `jobApi.createJob(formData)`
3. 成功后 `emit('success', newJob)` 通知父组件
4. 关闭弹窗

**UI 细节**：
- 带 backdrop blur 的背景遮罩
- 模式切换使用分段选择器（Segmented Control）风格
- 文件上传区域使用虚线边框 + 悬停高亮
- 提交按钮有加载状态

---

### 4.10 论文阅读器 —— `PaperReader.vue`

**职责**：整个项目最核心、最复杂的组件，提供论文阅读和 AI 助手功能。

**组件架构**：

```
PaperReader
├── 悬浮 AI 按钮（右上角，仅在侧边栏关闭时显示）
├── 论文内容区（左侧）
│   └── <iframe> 嵌入生成的 HTML 论文
└── AI 侧边栏（右侧，可滑动开/关）
    ├── Header（标题 + 关闭按钮）
    ├── 聊天记录
    │   ├── 当前划选文本（高亮引用）
    │   ├── 用户消息
    │   └── AI 回复（Markdown 渲染）
    └── 输入区（文本输入 + 发送按钮）
```

#### 关键技术点

**1. iframe 嵌入与跨域处理**

通过 Vite 代理的 `/artifacts/{jobId}/out/main.html` URL 加载生成的 HTML 论文。

```typescript
const artifactUrl = `/artifacts/${props.jobId}/out/main.html`;
```

**2. 划词选中监听**

使用多层事件监听策略：

1. **主窗口**：`mouseup`、`selectionchange`、`click` 事件
2. **iframe 内部**（如可访问）：同上的事件绑定
3. **降级处理**：通过 `iframeRef.value.contentWindow.getSelection()` 获取 iframe 内的选中文本

```typescript
const handleGlobalSelection = () => {
  // 1. 尝试主窗口选中文本
  let text = window.getSelection()?.toString().trim();
  // 2. 如果为空，尝试 iframe 内部
  if (!text && iframeRef.value?.contentWindow) {
    const iframeSelection = iframeRef.value.contentWindow.getSelection();
    text = iframeSelection?.toString().trim();
  }
  // 3. 如果文本有效且用户未手动操作过，自动打开侧边栏
  if (text && text.length > 2) { ... }
};
```

**手动操作保护**：记录用户手动切换侧边栏的时间戳，1 秒内不自动打开，避免与手动操作冲突。

**3. 滚轮事件转发**

论文内容区外部（如侧边栏区域）滚轮滚动时，转发到 iframe 内部，实现"全局滚动"效果：

```typescript
const handleContainerWheel = (event: WheelEvent) => {
  // 如果事件源在 iframe 内部，跳过（避免双重滚动）
  if (iframeEl.contains(target)) return;
  event.preventDefault();
  iframeWin.scrollBy({ top: event.deltaY, behavior: 'auto' });
};
```

**4. CSS 注入**

在 iframe 加载完成后，动态注入样式，防止论文内容超出边界：

```typescript
const style = document.createElement('style');
style.textContent = `
  * { max-width: 100%; box-sizing: border-box; }
  body { overflow-x: hidden !important; word-wrap: break-word !important; }
  img, video, canvas, svg, object, embed { max-width: 100% !important; height: auto !important; }
  table { display: block !important; overflow-x: auto !important; }
`;
iframeDoc.head.appendChild(style);
```

**5. AI 聊天功能**

- 调用 `jobApi.askAi()` 发送请求
- 使用 `markdown-it` 库将 AI 回复的 Markdown 渲染为 HTML
- 对话历史保存在 `messages` 响应式数组中
- 上下文包含：全文（截取前 50000 字符）+ 划选文本 + 用户问题

**6. 生命周期管理**

`onMounted`：检查 API Key 是否存在，设置滚轮转发。  
`onUnmounted`：清理事件监听，防止内存泄漏。

---

### 4.11 AI 设置弹窗 —— `SettingsModal.vue`

**职责**：管理 AI API 密钥的本地存储。

**功能**：

- **加载**：从 `localStorage` 读取已保存的 `ai-api-key`
- **保存**：写入 `localStorage.setItem('ai-api-key', key)`
- **清除**：`localStorage.removeItem('ai-api-key')`
- **安全**：输入框使用 `type="password"` 隐藏密钥

**交互反馈**：
- 保存成功后显示绿色脉冲提示，2 秒后自动关闭
- 清除前有确认弹窗

---

## 5. 数据流与工作流程

### 5.1 创建任务 → 完成阅读

```
用户操作               前端                   后端                          文件系统/外部
─────────           ────────              ────────                       ──────────────
1. 填写 arXiv ID      │                      │                              │
   或上传文件          │                      │                              │
                      │  POST /api/jobs      │                              │
2. 点击提交 ────────→  │  (FormData)          │                              │
                      │  ──────────────────→  │  3. 创建 JobState            │
                      │                      │  ├─ 生成 UUID                │
                      │                      │  ├─ 创建目录结构             │ ──→ jobs/{uuid}/
                      │                      │  ├─ 保存 job.json            │ ──→ meta/job.json
                      │                      │  └─ 保存上传文件             │ ──→ original/
                      │                      │                              │
                      │  201 + JobState      │  4. tokio::spawn(worker)     │
                      │  ←──────────────────  │      │                      │
                      │                      │      │                      │
                      │  跳转 ReaderView      │      ▼                      │
5. 显示"处理中" ──────→  每 3 秒轮询           │  5. ArXiv 下载 / 解压        │
                      │  GET /api/jobs/:id    │  ├─ download_from_arxiv()   │ ──→ https://arxiv.org
                      │  ──────────────────→  │  ├─ execute_extraction()    │ ──→ src/
                      │  ←── JobState ───────  │  └─ save_job()             │
                      │                      │                              │
                      │                      │  6. LaTeXML 编译            │
                      │                      │  ├─ pdflatex -draftmode      │ ──→ 生成 .aux/.bbl
                      │                      │  ├─ latexml → main.xml       │ ──→ out/main.xml
                      │                      │  ├─ latexmlpost → main.html   │ ──→ out/main.html
                      │                      │  └─ save_job(Completed)      │
                      │                      │                              │
6. 状态变为 completed   │  ←── JobState ───────  │                              │
   ────────────────→   │  停止轮询             │                              │
                      │  加载 PaperReader     │                              │
7. 阅读论文 ─────────→  │  iframe: /artifacts/.. │  GET .../artifacts/...     │
                      │  ──────────────────→  │  ──→ 读取 out/main.html ──── │
                      │                      │                              │
8. 划选文本提问 ─────→  │  POST /api/chat      │                              │
                      │  ──────────────────→  │  ──→ DeepSeek API ────────── │
                      │  ←── AI 回复 ────────  │                              │
```

### 5.2 数据持久化

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
    │   └── job.json              # 任务状态 JSON
    └── log/
        ├── preflight.log         # pdflatex 预编译日志
        ├── latexml.log           # latexml 编译日志
        └── latexmlpost.log       # latexmlpost 渲染日志
```

`job.json` 包含了任务从创建到完成的全部状态变化，前端通过轮询读取该文件获取进度。

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

后端将在 `http://127.0.0.1:8000` 启动，`jobs/` 目录自动创建。

**启动前端**（终端 2）：

```bash
cd frontend/paper-workflow
npm install
npm run dev
```

前端将在 `http://localhost:5173` 启动，Vite 代理自动转发 API 请求到后端。

**使用**：

1. 打开浏览器访问 `http://localhost:5173`
2. 点击"新建任务"，输入 arXiv ID 或上传 `.tar.gz` 文件
3. 等待任务处理完成（可看到实时状态变化）
4. 点击任务卡片进入阅读页
5. 在设置中配置 DeepSeek API Key
6. 选中论文中的文本，通过 AI 助手提问

---

## 7. 常见问题与扩展

### Q1: 论文转换失败怎么办？

查看对应任务的日志文件（`jobs/{uuid}/log/` 目录下）：
- `preflight.log` — pdfLaTeX 预编译问题
- `latexml.log` — LaTeXML 转换错误
- `latexmlpost.log` — HTML 渲染问题

常见原因：缺少宏包、LaTeX 语法错误、超大文件超时。

### Q2: 如何支持更多 AI 模型？

修改 `routes.rs` 中的 `call_ai_api` 函数，根据 `req.model` 参数路由到不同的 API 端点。目前仅支持 DeepSeek。

### Q3: 如何扩展新的处理阶段？

1. 在 `models.rs` 中更新 `JobStatus` 枚举
2. 在 `worker.rs` 中添加新的处理函数
3. 在 `process_job` 中串联新阶段
4. 在前端 `api.ts` 的 `JobStatus` 类型中添加对应值

### Q4: 前端跨域问题？

开发环境通过 Vite 代理解决。生产环境应使用 nginx 反向代理或配置后端 CORS。

### Q5: 如何清理任务数据？

直接删除 `jobs/` 目录下的对应 UUID 文件夹即可，或在首页使用"删除所有任务"功能。

---

> **ChatHTML** 项目架构清晰，前后端职责分离明确。  
> 后端使用 Rust 保证性能和安全性，前端使用 Vue 3 提供流畅的交互体验。  
> 核心流程为：获取源码 → 安全解压 → LaTeXML 编译 → 交互式阅读 + AI 问答。
