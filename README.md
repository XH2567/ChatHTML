# arXiv Paper Workflow & AI Reader

这是一个集成了 LaTeXML 编译与 AI 辅助阅读功能的学术论文 Web 应用。
它能够将 arXiv 上的 LaTeX 源码一键下载并编译为现代、可读性强的 HTML 页面，并在页面中原生注入了浮动的“AI 对话侧边栏”（支持划词提问、Markdown 格式渲染、多种大模型接入、历史对话本地持久化）。

## 环境依赖与安装

### 1. 安装 LaTeXML
本项目依赖 `latexml` 工具链将 LaTeX 编译为 HTML/XML。
你可以通过操作系统的包管理器进行安装：

**Ubuntu / Debian:**
```bash
sudo apt-get update
sudo apt-get install latexml
```

**macOS:**
```bash
brew install latexml
```

### 2. 启动 Web 应用
本项目后端非常轻量，无外部第三方 Python 包依赖（完全基于 Python 内置库）。
确保你已安装 Python 3.10+，执行以下命令即可启动：

```bash
# 进入 webapp 目录
cd ChatHTML
# 启动 HTTP 服务器
python3 app.py
```
启动成功后，在浏览器访问：`http://127.0.0.1:8000`

### 3. 公网分享 (基于 Cloudflare 免费隧道)
如果你想将本地正在运行的 Web 服务通过公网分享给同学协助阅读，可以使用 Cloudflare Quick Tunnels 进行内网穿透：

```bash
# 需提前安装好 cloudflared 命令行工具
cloudflared tunnel --url http://127.0.0.1:8000
```
运行后，终端会输出一个类似 `https://xxxx.trycloudflare.com` 的公网链接。你的同学可以直接通过此链接访问应用并使用。

---

## 核心模块结构说明

为了方便二次开发和多人协作，核心逻辑已按功能单一原则进行了模块化拆分：

- `app.py`: 应用启动入口，包含基础 `HTTP Server` 的启动机制机制和所有的路由分发逻辑（`/jobs`、`/api/chat` 等）。
- `models.py`: 数据模型层，存放全局常量配置（目录、尺寸限制）和核心数据的结构映射（如 `JobState` 任务状态类）。
- `store.py`: 数据持久层，内部封装了基于本地 JSON 文件的状态增删改查方法，用于维持不同任务的流程状态。
- `worker.py`: 异步工作与预处理层，负责拉取 arXiv 源码压缩包、安全检查、防炸弹解压，以及启动后台编译线程。
- `views.py`: 视图渲染与注入层。负责：
  - 各类 HTML 路由页面的模板拼接（主页、任务详情页）。
  - LaTeXML 编译出 HTML 后的后处理（修复 `\cellcolor` 等不支持的 LaTeX 伪像）。
  - 核心功能：向 HTML 后期注入精美的 **流式排版 CSS 主题** 与 **AI 助手侧边栏** 的 JS 交互逻辑。
- `workflow.py`（如有）: 控制底层调用 `latexml` 和 `latexmlpost` 子进程的具体编译工作流。

## 工作区目录
服务运行后会在当前目录下自动生成 `jobs/` 核心工作缓存区，目录规范如下：
- `jobs/<job_id>/original/`: 原始源文件压缩包
- `jobs/<job_id>/src/`: 安全解压后的源码目录
- `jobs/<job_id>/out/`: 编译产出的 HTML 文件、拆分的 XML 及图片静态资源
- `jobs/<job_id>/meta/`: 任务执行期的配置文件（JSON）
