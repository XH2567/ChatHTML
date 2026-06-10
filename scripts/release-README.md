# ChatHTML — 点击即用的论文转换与 AI 阅读助手

**ChatHTML** 将学术论文（LaTeX 源码）自动转换为交互式 HTML，内置多提供商 AI 学术助手，支持划词提问、对话历史标记、拖拽排序等特性。

---

## 系统要求

| 依赖 | 说明 | 安装 (Ubuntu/Debian) |
|------|------|----------------------|
| **LaTeXML** | LaTeX → HTML 编译引擎 | `sudo apt install latexml` |
| **pdfTeX + texlive** | LaTeX 预编译与宏包 | `sudo apt install texlive-latex-base texlive-latex-extra texlive-latex-recommended texlive-science` |

验证安装：
```bash
latexml --VERSION && latexmlpost --VERSION
pdflatex --version
```

> 无需安装 Rust、Node.js 或任何编程语言环境。

---

## 使用方法

### Linux / macOS

```bash
chmod +x start.sh
./start.sh
```

或直接双击 `start.sh`（macOS 双击 `start.command`）。

### Windows

双击 `start.bat`。

启动服务后打开浏览器访问 `http://127.0.0.1:8000`。

---

## 首次使用

1. 打开浏览器，点击 **登录 / 注册** 创建账户
2. 登录后点击 **新建任务**，输入 arXiv ID（如 `2401.12345`）或上传 `.tar.gz` 文件
3. 等待任务处理完成，观察实时状态变化
4. 点击任务卡片进入阅读页
5. 在 **用户菜单 → API 密钥设置** 中配置 AI 提供商、模型和 API 密钥（如 DeepSeek、OpenAI、Anthropic 等）
6. 选中论文中的文本，通过 AI 助手提问

---

## 配置

编辑同目录下的 `ai_config.json` 可配置 AI 提供商列表：

```json
{
  "providers": {
    "deepseek": {
      "name": "DeepSeek",
      "base_url": "https://api.deepseek.com",
      "api_path": "/chat/completions",
      "models": ["deepseek-chat"]
    }
  }
}
```

---

## 目录结构

```
chathtml-release/
├── chat-html              # 服务器程序
├── dist/                  # 前端页面（一般无需修改）
├── ai_config.json         # AI 提供商配置
├── start.sh               # Linux 启动脚本
├── start.bat              # Windows 启动脚本
├── start.command          # macOS 启动脚本
└── README.md              # 本文件
```

运行时自动生成：

```
paper_workflow.db          # SQLite 数据库（用户、密钥）
jobs/                      # 论文任务数据
```

---

## 开发模式（热重载）

如果需要修改前端代码并实时查看效果，使用项目根目录的开发版本：

```bash
cd scripts
bash start.sh
```

此命令同时启动 Rust 后端（`cargo run`）和 Vite 前端开发服务器（`npm run dev`），访问 `http://localhost:5173`。

---

## 从源码构建

参见项目根目录的 [README.md](../README.md) 或运行：

```bash
cd scripts
bash build-release.sh
```

---

## 常见问题

**Q: 如何访问？**
A: 启动后打开浏览器访问 `http://127.0.0.1:8000`。

**Q: 提示 "Failed to read dist/index.html"？**
A: 缺少前端文件。运行 `scripts/build-release.sh` 重新构建，或检查 `dist/` 目录是否存在。

**Q: 论文转换失败？**
A: 确认已安装 LaTeXML 和 texlive。查看 `jobs/{uuid}/log/` 下的日志文件。
