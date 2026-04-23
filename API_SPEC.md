# Paper Workflow API v1

## 基本信息

- **基础URL**: `http://127.0.0.1:8000/api`
- **数据格式**: JSON（文件上传/下载除外）
- **序列化**: 所有 JSON 字段使用 camelCase 命名

---

## 1. 数据模型

### 1.1 JobStatus（任务状态）

```typescript
enum JobStatus {
  Created,       // 已创建
  Queued,        // 已入队
  Downloading,   // 正在下载（ArXiv 模式）
  Validating,    // 正在验证（上传模式）
  Extracting,    // 正在解压
  Analyzing,     // 正在分析源码
  Processing,    // 正在处理（LaTeXML 编译）
  Completed,     // 完成
  Partial,       // 部分完成
  Error          // 出错
}
```

### 1.2 StageStatus（阶段状态）

```typescript
enum StageStatus {
  Pending,  // 等待中
  Running,  // 运行中
  Done,     // 完成
  Error,    // 出错
  Skipped   // 已跳过
}
```

### 1.3 StageDetail（阶段详情）

```typescript
interface StageDetail {
  title: string;   // 阶段标题
  status: StageStatus;
  detail: string;  // 详细描述
}
```

### 1.4 SourceMode（来源模式）

```typescript
enum SourceMode {
  Upload,  // 手动上传
  Arxiv    // 从 ArXiv 下载
}
```

### 1.5 JobState（任务对象）

```typescript
interface JobState {
  jobId: string;                    // UUID v4
  createdAt: string;                // ISO 8601 时间戳
  status: JobStatus;
  sourceMode: SourceMode;
  arxivId: string | null;           // ArXiv ID（仅 ArXiv 模式）
  originalName: string | null;      // 原始文件名（仅上传模式）
  archiveSize: number | null;       // 源文件大小（字节）
  errors: string[];                 // 错误列表
  warnings: string[];               // 警告列表
  durationSeconds: number | null;   // 处理耗时（秒）
  artifacts: Record<string, string>;// 产物文件映射，例：{"html": "out/main.html", "xml": "out/main.xml"}
  stageDetails: StageDetail[];      // 各处理阶段详情
  manifest: object | null;          // 论文元数据（LaTeXML 解析结果）
}
```

---

## 2. 接口定义

### 2.1 获取任务列表

```
GET /api/jobs
```

**功能**: 获取所有任务（按创建时间降序排列）

**响应**:

| 状态码 | 说明 | 响应体 |
|--------|------|--------|
| `200 OK` | 成功 | `JobState[]` |

---

### 2.2 创建任务

```
POST /api/jobs
```

**功能**: 创建论文处理任务

**请求体**: `multipart/form-data`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `source_mode` | string | 是 | `"upload"` 或 `"arxiv"` |
| `arxiv_id` | string | 否 | ArXiv 论文 ID（当 `source_mode=arxiv` 时必填） |
| `source_file` | file | 否 | 上传的压缩包文件（当 `source_mode=upload` 时必填） |

**响应**:

| 状态码 | 说明 | 响应体 |
|--------|------|--------|
| `201 Created` | 创建成功 | `JobState` |
| `500 Internal Server Error` | 服务器内部错误 | 错误信息 |

**注意**: 创建后后端会立即返回并异步执行后台处理流程，前端需要轮询 `GET /api/jobs/{id}` 获取进度更新。

---

### 2.3 获取单个任务详情

```
GET /api/jobs/{id}
```

**功能**: 获取单个任务详情（用于轮询进度）

**路径参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| `id` | UUID v4 | 任务 ID |

**响应**:

| 状态码 | 说明 | 响应体 |
|--------|------|--------|
| `200 OK` | 成功 | `JobState` |
| `404 Not Found` | 任务不存在 | 空 |
| `500 Internal Server Error` | 服务器内部错误 | 错误信息 |

---

### 2.4 删除单个任务

```
DELETE /api/jobs/{id}
```

**功能**: 删除指定任务及其所有文件

**路径参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| `id` | UUID v4 | 任务 ID |

**响应**:

| 状态码 | 说明 | 响应体 |
|--------|------|--------|
| `204 No Content` | 删除成功 | 空 |
| `500 Internal Server Error` | 删除失败 | 错误信息 |

---

### 2.5 删除所有任务

```
DELETE /api/jobs
```

**功能**: 删除所有任务及其文件

**响应**:

| 状态码 | 说明 | 响应体 |
|--------|------|--------|
| `204 No Content` | 删除成功 | 空 |
| `500 Internal Server Error` | 删除失败 | 错误信息 |

---

### 2.6 AI 聊天代理

```
POST /api/chat
```

**功能**: 通过 AI API（DeepSeek）进行论文对话

**请求体**: `application/json`

```typescript
interface ChatRequest {
  query: string;       // 用户问题
  context: string;     // 划选内容
  model: string;       // AI 模型名称（如 "deepseek-chat"）
  api_key: string;     // DeepSeek API 密钥
  full_paper: string;  // 论文全文内容
}
```

**响应**:

| 状态码 | 说明 | 响应体 |
|--------|------|--------|
| `200 OK` | 成功 | `{ "reply": string, "model_used": string, "context_length": number, "paper_length": number, "timestamp": string }` |
| `400 Bad Request` | 请求参数错误 | 错误信息 |
| `401 Unauthorized` | API 密钥无效 | `{ "error": string }` |
| `502 Bad Gateway` | AI 服务请求失败 | `{ "error": string }` |

---

### 2.7 获取产物文件

```
GET /api/jobs/{id}/artifacts/{path...}
```

**功能**: 获取任务产物文件（HTML、图片、日志等）

**路径参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| `id` | UUID v4 | 任务 ID |
| `path` | string | 产物相对路径，例如 `out/main.html`、`out/main.xml` |

**响应**:

| 状态码 | 说明 | 响应体 |
|--------|------|--------|
| `200 OK` | 成功 | 文件流（自动识别 MIME 类型） |
| `404 Not Found` | 文件不存在 | 空 |
| `500 Internal Server Error` | 读取失败 | 错误信息 |

**响应头**:
- `Content-Type`: 自动推断的 MIME 类型
- `Cache-Control`: `public, max-age=3600`
- `Content-Security-Policy`: `frame-ancestors 'self' http://localhost:5173 http://127.0.0.1:5173`
- `Access-Control-Allow-Origin`: `*`

---

### 2.8 获取 HTML 内容（纯文本）

```
GET /api/jobs/{id}/html
```

**功能**: 获取 HTML 文件内容作为纯文本（用于前端 srcdoc 嵌入）

**路径参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| `id` | UUID v4 | 任务 ID |

**响应**:

| 状态码 | 说明 | 响应体 |
|--------|------|--------|
| `200 OK` | 成功 | HTML 内容（`text/plain; charset=utf-8`） |
| `404 Not Found` | HTML 文件不存在 | 空 |
| `500 Internal Server Error` | 读取失败 | 错误信息 |

**响应头**:
- `Content-Type`: `text/plain; charset=utf-8`
- `Access-Control-Allow-Origin`: `*`

---

## 3. 任务处理流程

### 3.1 生命周期

```
Created → Queued → Downloading/Validating → Extracting → Analyzing → Processing → Completed
                                                                                        ↘ Partial
                                                                                        ↘ Error
```

各阶段对应的 `stageDetails` 步骤：

| 阶段 | 步骤标题 |
|------|----------|
| 下载/验证 | `下载源码` 或 `文件验证` |
| 解压 | `安全解压` |
| 预编译 | `预编译` |
| LaTeXML | `LaTeXML` |
| HTML 生成 | `HTML生成` |
| 完成 | `完成` |

### 3.2 处理超时

| 步骤 | 超时时间 |
|------|----------|
| ArXiv 下载 | 60 秒 |
| pdflatex 预编译 | 60 秒 |
| LaTeXML 编译 | 300 秒 |
| LaTeXMLPost 渲染 | 120 秒 |

超时后任务状态将变为 `Error`。

### 3.3 文件存储结构

```
./jobs/
  {jobId}/
    original/       # 原始上传/下载文件
    src/            # 解压后的源码
    normalized/     # 规范化后的文件
    out/            # 产物文件（main.html, main.xml）
    meta/           # 元数据（job.json）
    log/            # 日志文件
    overlay/        # LaTeXML 补丁定义
```

---

## 4. 示例

### 4.1 创建上传任务

```bash
curl -X POST http://127.0.0.1:8000/api/jobs \
  -F "source_mode=upload" \
  -F "source_file=@paper.tar.gz"
```

### 4.2 创建 ArXiv 任务

```bash
curl -X POST http://127.0.0.1:8000/api/jobs \
  -F "source_mode=arxiv" \
  -F "arxiv_id=2401.12345"
```

### 4.3 轮询任务进度

```bash
curl http://127.0.0.1:8000/api/jobs/{jobId}
```

### 4.4 AI 对话

```bash
curl -X POST http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "query": "这篇论文的主要贡献是什么？",
    "context": "",
    "model": "deepseek-chat",
    "api_key": "sk-xxx",
    "full_paper": "..."
  }'
```

### 4.5 获取产物文件

```bash
curl http://127.0.0.1:8000/api/jobs/{jobId}/artifacts/out/main.html -o main.html
```
