# ChatHTML

> **ChatHTML** 是一个将学术论文（LaTeX 源码）自动转换为交互式 HTML 的 Web 应用，内置基于 DeepSeek API 的学术 AI 助手，支持划词提问。

## 核心功能

| 功能 | 说明 |
|------|------|
| **论文源码 → HTML** | 支持上传 `.tar.gz` 压缩包或直接输入 arXiv ID，后端自动下载、解压、通过 LaTeXML 编译为 HTML |
| **交互式阅读** | 使用 `<iframe>` 嵌入生成的 HTML 论文，提供沉浸式阅读体验 |
| **划词 AI 助手** | 选中论文中的文本，自动弹出侧边栏，调用 DeepSeek API 进行问答 |
| **任务管理** | 创建、查看、删除论文转换任务，实时轮询进度 |

## 技术栈

| 层 | 技术 | 说明 |
|----|------|------|
| 后端框架 | **Axum** (Rust) | 高性能异步 Web 框架 |
| 后端运行时 | **Tokio** | 异步运行时 |
| 序列化 | **Serde** | JSON 序列化/反序列化 |
| 持久化 | **文件系统** | 每个任务一个目录，状态存为 `meta/job.json` |
| 前端框架 | **Vue 3** (Composition API + `<script setup>`) | 响应式 UI |
| 构建工具 | **Vite** | 开发服务器与生产构建 |
| 样式 | **Tailwind CSS 4** | 原子化 CSS |
| AI API | **DeepSeek Chat API** | 学术问答 |

## 环境要求

### 必需依赖

| 依赖 | 版本要求 | 安装命令 (Ubuntu/Debian) |
|------|----------|--------------------------|
| **Rust** | 2024 edition | `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \| sh` |
| **Node.js** | ≥ 18 (推荐 LTS) | `apt install nodejs npm` 或使用 nvm |
| **LaTeXML** | 最新 | `apt install latexml` |
| **pdfTeX** (texlive) | 最新 | `apt install texlive-pdflatex texlive-latex-extra texlive-latex-recommended texlive-science` |
| **BibTeX 工具** | 可选 | `apt install texlive-bibtex-extra` |
| **构建工具** | — | `apt install build-essential pkg-config libssl-dev` |

### 验证安装

```bash
# 验证 Rust
rustc --version && cargo --version

# 验证 Node.js
node --version && npm --version

# 验证 LaTeXML
latexml --version && latexmlpost --version

# 验证 pdfTeX
pdflatex --version
```

## 快速开始

### 1. 启动后端

```bash
cd backend/paper-workflow
cargo run
```

后端将在 `http://127.0.0.1:8000` 启动，`jobs/` 目录自动创建。

### 2. 启动前端（新开一个终端）

```bash
cd frontend/paper-workflow
npm install
npm run dev
```

前端将在 `http://localhost:5173` 启动，Vite 代理自动转发 API 请求到后端。

### 3. 使用

1. 打开浏览器访问 `http://localhost:5173`
2. 点击 **新建任务**，输入 arXiv ID（如 `2401.12345`）或上传 `.tar.gz` 文件
3. 等待任务处理完成（可看到实时状态变化）
4. 点击任务卡片进入阅读页
5. 在 **设置** 中配置 DeepSeek API Key
6. 选中论文中的文本，通过 AI 助手提问

## 项目结构

```
ChatHTML/
├── README.md                     # 本文件
├── API_SPEC.md                   # API 接口说明文档
├── manual.md                     # 详细技术手册
├── backend/
│   └── paper-workflow/           # Rust 后端项目
│       ├── Cargo.toml
│       └── src/
│           ├── main.rs           # 入口：启动服务器
│           ├── models.rs         # 数据模型定义
│           ├── routes.rs         # API 路由处理函数
│           ├── store.rs          # 持久化存储层
│           └── worker.rs         # 后台任务处理流水线
├── frontend/
│   └── paper-workflow/           # Vue 3 前端项目
│       ├── package.json
│       ├── vite.config.ts
│       └── src/
│           ├── main.ts           # Vue 应用挂载
│           ├── App.vue           # 根组件
│           ├── router.ts         # 路由定义
│           ├── style.css         # 全局样式 + Tailwind
│           ├── api/client.ts     # Axios API 客户端
│           ├── types/api.ts      # TypeScript 类型定义
│           ├── views/
│           │   ├── HomeView.vue      # 首页
│           │   └── ReaderView.vue    # 阅读页
│           └── components/
│               ├── JobCard.vue       # 任务卡片
│               ├── NewJobModel.vue   # 新建任务弹窗
│               ├── PaperReader.vue   # 论文阅读器（核心组件）
│               └── SettingsModal.vue # AI 设置弹窗
└── jobs/                          # （运行时生成）任务数据存储目录
```

## 处理流程

```
用户提交 arXiv ID 或上传文件
        │
        ▼
  ┌─ 创建任务 ──────────────────────┐
  │  • 生成 UUID                    │
  │  • 创建目录结构                 │
  │  • 保存初始状态                 │
  └────────────────────────────────┘
        │
        ▼
  ┌─ 获取并解压源码 ────────────────┐
  │  • arXiv 模式：从 arxiv.org 下载 │
  │  • Upload 模式：使用上传文件     │
  │  • 安全解压到 src/ 目录          │
  └────────────────────────────────┘
        │
        ▼
  ┌─ LaTeXML 编译 ─────────────────┐
  │  • pdflatex -draftmode 预编译   │
  │  • 注入 .bbl 参考文献           │
  │  • latexml → main.xml           │
  │  • latexmlpost → main.html      │
  └────────────────────────────────┘
        │
        ▼
  用户可交互阅读 + AI 划词问答
```

## API 概览

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/jobs` | 获取任务列表 |
| POST | `/api/jobs` | 创建任务（上传/arXiv） |
| DELETE | `/api/jobs` | 删除所有任务 |
| GET | `/api/jobs/:id` | 获取单个任务详情 |
| DELETE | `/api/jobs/:id` | 删除单个任务 |
| POST | `/api/chat` | AI 聊天代理 |
| GET | `/api/jobs/:id/artifacts/*path` | 获取产物文件 |
| GET | `/api/jobs/:id/html` | 获取 HTML 内容 |

> 详细 API 文档参见 [API_SPEC.md](./API_SPEC.md)，完整技术手册参见 [manual.md](./manual.md)。

## License

MIT
