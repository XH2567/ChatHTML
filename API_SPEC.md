# Paper Workflow API v1

## 基本信息

- **基础URL**: `http://127.0.0.1:8000/api`
- **数据格式**: JSON（文件上传/下载除外）
- **序列化**: 所有 JSON 字段使用 camelCase 命名
- **认证方式**: JWT Bearer Token（除注册/登录外几乎所有接口均需认证）
- **认证头格式**: `Authorization: Bearer {token}`

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
  jobId: string;                       // UUID v4
  userId: string | null;               // 关联的用户 ID
  createdAt: string;                   // ISO 8601 时间戳
  status: JobStatus;
  sourceMode: SourceMode;
  arxivId: string | null;              // ArXiv ID（仅 ArXiv 模式）
  originalName: string | null;         // 原始文件名（仅上传模式）
  archiveSize: number | null;          // 源文件大小（字节）
  errors: string[];                    // 错误列表
  warnings: string[];                  // 警告列表
  durationSeconds: number | null;      // 处理耗时（秒）
  artifacts: Record<string, string>;   // 产物文件映射，例：{"html": "out/main.html", "xml": "out/main.xml"}
  sortOrder?: number;                  // 排序权重（用于拖拽排序）
  stageDetails: StageDetail[];         // 各处理阶段详情
  manifest: object | null;             // 论文元数据（LaTeXML 解析结果）
}
```

### 1.6 QueryHistory（查询历史）

```typescript
interface QueryHistory {
  textExcerpt: string;  // 划选文本摘录（前 100 字）
  textHash: string;     // 划选文本的 SHA-256 哈希
  query: string;        // 用户提问
  reply: string;        // AI 回复
  timestamp: string;    // ISO 8601 时间戳
}
```

### 1.7 通用错误响应

```typescript
interface ErrorResponse {
  error: string;  // 错误描述
}
```

所有需要认证的接口在 token 无效或过期时返回 `401 Unauthorized`：
```json
{ "error": "请先登录" }
```

---

## 2. 认证接口

### 2.1 用户注册

```
POST /api/auth/register
```

**请求体**: `application/json`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `username` | string | 是 | 用户名（不能为空） |
| `password` | string | 是 | 密码（至少 6 个字符） |

**响应**:

| 状态码 | 说明 | 响应体 |
|--------|------|--------|
| `200 OK` | 注册成功 | `AuthResponse` |
| `400 Bad Request` | 参数不合法 | `ErrorResponse` |
| `409 Conflict` | 用户名已存在 | `ErrorResponse` |

**AuthResponse**:
```typescript
interface AuthResponse {
  userId: string;
  username: string;
  token: string;  // JWT 令牌，有效期 7 天
}
```

---

### 2.2 用户登录

```
POST /api/auth/login
```

**请求体**: `application/json`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `username` | string | 是 | 用户名 |
| `password` | string | 是 | 密码 |

**响应**:

| 状态码 | 说明 | 响应体 |
|--------|------|--------|
| `200 OK` | 登录成功 | `AuthResponse` |
| `401 Unauthorized` | 用户名或密码错误 | `ErrorResponse` |

---

### 2.3 用户登出

```
POST /api/auth/logout
```

**请求头**: `Authorization: Bearer {token}`

**响应**:

| 状态码 | 说明 | 响应体 |
|--------|------|--------|
| `204 No Content` | 登出成功（服务端仅记录日志） | 空 |

---

### 2.4 获取当前用户信息

```
GET /api/auth/me
```

**请求头**: `Authorization: Bearer {token}`

**响应**:

| 状态码 | 说明 | 响应体 |
|--------|------|--------|
| `200 OK` | 成功 | `{ "userId": string, "username": string }` |
| `401 Unauthorized` | 未登录或 token 无效 | `ErrorResponse` |

---

### 2.5 保存 AI API 密钥

```
POST /api/auth/api-key
```

**请求头**: `Authorization: Bearer {token}`

**请求体**: `application/json`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `api_key` | string | 是 | API 密钥（至少 8 个字符） |
| `provider` | string | 是 | 提供商标识，如 `deepseek`, `openai`, `anthropic`, `google`, `zhipu`, `custom` |
| `model` | string | 是 | 模型 ID，如 `deepseek-v4-flash`, `gpt-4`, `claude-3-sonnet` |

**响应**:

| 状态码 | 说明 | 响应体 |
|--------|------|--------|
| `200 OK` | 保存成功 | `{ "success": true, "provider": "...", "model": "..." }` |
| `400 Bad Request` | 参数不合法 | `ErrorResponse` |
| `401 Unauthorized` | 未登录 | `ErrorResponse` |

---

### 2.6 获取 API 密钥状态

```
GET /api/auth/api-key
```

**请求头**: `Authorization: Bearer {token}`

**响应**:

| 状态码 | 说明 | 响应体 |
|--------|------|--------|
| `200 OK` | 成功 | `MaskedApiKey` |

**MaskedApiKey**:
```typescript
interface MaskedApiKey {
  hasKey: boolean;               // 是否已设置密钥
  masked: string | null;         // 掩码后字符串 "********" 或 null
  provider: string | null;       // 已配置的提供商
  model: string | null;          // 已配置的模型
}
```

---

### 2.7 删除 API 密钥

```
DELETE /api/auth/api-key
```

**请求头**: `Authorization: Bearer {token}`

**响应**:

| 状态码 | 说明 | 响应体 |
|--------|------|--------|
| `204 No Content` | 删除成功 | 空 |
| `500 Internal Server Error` | 删除失败 | 空 |

---

## 3. 任务管理接口

### 3.1 获取任务列表

```
GET /api/jobs
```

**请求头**: `Authorization: Bearer {token}`

**功能**: 获取当前用户的所有任务（按排序权重降序，无权重按创建时间降序）

**响应**:

| 状态码 | 说明 | 响应体 |
|--------|------|--------|
| `200 OK` | 成功 | `JobState[]` |
| `401 Unauthorized` | 未登录 | `ErrorResponse` |

---

### 3.2 创建任务

```
POST /api/jobs
```

**请求头**: `Authorization: Bearer {token}`

**请求体**: `multipart/form-data`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `source_mode` | string | 是 | `"upload"` 或 `"arxiv"` |
| `arxiv_id` | string | 否 | ArXiv 论文 ID（当 `source_mode=arxiv` 时必填） |
| `source_file` | file | 否 | 上传的压缩包文件（当 `source_mode=upload` 时必填） |

**响应**:

| 状态码 | 说明 | 响应体 |
|--------|------|--------|
| `201 Created` | 创建成功 | `JobState`（含 `userId` 绑定） |
| `401 Unauthorized` | 未登录 | `ErrorResponse` |
| `500 Internal Server Error` | 服务器内部错误 | 错误信息 |

**注意**: 创建后后端会立即返回并异步执行后台处理流程，前端需要轮询 `GET /api/jobs/{id}` 获取进度更新。

---

### 3.3 获取单个任务详情

```
GET /api/jobs/{id}
```

**请求头**: `Authorization: Bearer {token}`

**功能**: 获取单个任务详情（用于轮询进度）

**路径参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| `id` | UUID v4 | 任务 ID |

**响应**:

| 状态码 | 说明 | 响应体 |
|--------|------|--------|
| `200 OK` | 成功 | `JobState` |
| `401 Unauthorized` | 未登录 | `ErrorResponse` |
| `403 Forbidden` | 无权访问该任务 | 空 |
| `404 Not Found` | 任务不存在 | 空 |
| `500 Internal Server Error` | 服务器内部错误 | 错误信息 |

---

### 3.4 删除单个任务

```
DELETE /api/jobs/{id}
```

**请求头**: `Authorization: Bearer {token}`

**功能**: 删除指定任务及其所有文件（仅限任务所有者）

**路径参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| `id` | UUID v4 | 任务 ID |

**响应**:

| 状态码 | 说明 | 响应体 |
|--------|------|--------|
| `204 No Content` | 删除成功 | 空 |
| `401 Unauthorized` | 未登录 | `ErrorResponse` |
| `403 Forbidden` | 无权删除 | 空 |
| `404 Not Found` | 任务不存在 | 空 |
| `500 Internal Server Error` | 删除失败 | 错误信息 |

---

### 3.5 删除所有任务

```
DELETE /api/jobs
```

**请求头**: `Authorization: Bearer {token}`

**功能**: 删除当前用户的所有任务及其文件

**响应**:

| 状态码 | 说明 | 响应体 |
|--------|------|--------|
| `204 No Content` | 删除成功 | 空 |
| `401 Unauthorized` | 未登录 | `ErrorResponse` |
| `500 Internal Server Error` | 删除失败 | 错误信息 |

---

### 3.6 批量重排任务顺序

```
PUT /api/jobs/reorder
```

**请求头**: `Authorization: Bearer {token}`

**请求体**: `application/json`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `order` | UUID[] | 是 | 按新顺序排列的任务 ID 数组 |

**响应**:

| 状态码 | 说明 | 响应体 |
|--------|------|--------|
| `204 No Content` | 重排成功 | 空 |
| `401 Unauthorized` | 未登录 | `ErrorResponse` |
| `403 Forbidden` | 包含无权操作的任务 | 空 |
| `404 Not Found` | 任务不存在 | 空 |

---

## 4. AI 接口

### 4.1 AI 聊天代理

```
POST /api/chat
```

**请求头**: `Authorization: Bearer {token}`

**功能**: 通过已配置的 AI 服务提供商进行论文对话。API 密钥、提供商和模型从服务端数据库获取，无需客户端传入。

**请求体**: `application/json`

```typescript
interface ChatRequest {
  query: string;          // 用户问题（继续模式时包含历史对话上下文）
  context: string;        // 划选内容
  full_paper: string;     // 论文全文内容（服务端截取前 30000 字符）
}
```

**响应**:

| 状态码 | 说明 | 响应体 |
|--------|------|--------|
| `200 OK` | 成功 | `{ "reply": string, "model_used": string, "context_length": number, "paper_length": number, "timestamp": string }` |
| `400 Bad Request` | 未配置提供商或模型 | `ErrorResponse` |
| `401 Unauthorized` | 未登录或未配置 API 密钥 | `ErrorResponse` |
| `502 Bad Gateway` | AI 服务请求失败 | `ErrorResponse` |

**说明**:
- API 密钥、提供商和模型通过 `POST /api/auth/api-key` 预先设置，服务端解密后使用
- 论文全文超过 30000 字符时自动截断
- 支持多提供商差异化请求/响应格式（DeepSeek/OpenAI 标准格式、Anthropic Messages API、Google AI Gemini API）

---

## 5. 产物与内容接口

### 5.1 获取产物文件

```
GET /api/jobs/{id}/out/{path...}
```

**功能**: 获取任务产物文件（HTML、图片、CSS、日志等）。HTML 文件需要认证，其他静态资源可直接访问。

**路径参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| `id` | UUID v4 | 任务 ID |
| `path` | string | 产物相对路径，例如 `out/main.html`、`out/main.xml`、`out/figures/image.png` |

**查询参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `token` | string | 否 | 用于 HTML 文件认证的 JWT 令牌（也可通过请求头传递） |

**请求头**（用于 HTML 文件）: `Authorization: Bearer {token}`

**响应**:

| 状态码 | 说明 | 响应体 |
|--------|------|--------|
| `200 OK` | 成功 | 文件流（自动识别 MIME 类型） |
| `401 Unauthorized` | HTML 文件未提供认证 | 空 |
| `403 Forbidden` | 无权访问该任务 | 空 |
| `404 Not Found` | 文件不存在 | 空 |
| `500 Internal Server Error` | 读取失败 | 错误信息 |

**响应头**:
- `Content-Type`: 自动推断的 MIME 类型
- `Cache-Control`: `public, max-age=3600`
- `Content-Security-Policy`: `frame-ancestors 'self' http://localhost:5173 http://127.0.0.1:5173`
- `Access-Control-Allow-Origin`: `*`

---

### 5.2 获取 HTML 内容（纯文本）

```
GET /api/jobs/{id}/html
```

**功能**: 获取 HTML 文件内容作为纯文本（用于前端 srcdoc 嵌入）

**路径参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| `id` | UUID v4 | 任务 ID |

**查询参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `token` | string | 否 | JWT 令牌（也可通过请求头传递） |

**请求头**: `Authorization: Bearer {token}`（推荐）

**响应**:

| 状态码 | 说明 | 响应体 |
|--------|------|--------|
| `200 OK` | 成功 | HTML 内容（`text/plain; charset=utf-8`） |
| `401 Unauthorized` | 未提供认证 | 空 |
| `403 Forbidden` | 无权访问 | 空 |
| `404 Not Found` | HTML 文件不存在 | 空 |
| `500 Internal Server Error` | 读取失败 | 错误信息 |

**响应头**:
- `Content-Type`: `text/plain; charset=utf-8`
- `Access-Control-Allow-Origin`: `*`

---

## 6. 查询历史接口

### 6.1 保存查询历史

```
POST /api/jobs/{id}/query-history
```

**请求头**: `Authorization: Bearer {token}`

**功能**: 保存 AI 查询/回复历史到任务目录（与划选文本哈希关联）

**路径参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| `id` | UUID v4 | 任务 ID |

**请求体**: `application/json`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `text_excerpt` | string | 是 | 划选文本摘录 |
| `text_hash` | string | 是 | 划选文本的 SHA-256 哈希值 |
| `query` | string | 是 | 用户提问 |
| `reply` | string | 是 | AI 回复 |

**响应**:

| 状态码 | 说明 | 响应体 |
|--------|------|--------|
| `201 Created` | 保存成功 | 空 |
| `401 Unauthorized` | 未登录 | `ErrorResponse` |
| `403 Forbidden` | 无权操作 | 空 |
| `404 Not Found` | 任务不存在 | 空 |

---

### 6.2 列出查询历史

```
GET /api/jobs/{id}/query-history
```

**请求头**: `Authorization: Bearer {token}`

**功能**: 获取任务的所有查询历史（按时间倒序排列）

**路径参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| `id` | UUID v4 | 任务 ID |

**响应**:

| 状态码 | 说明 | 响应体 |
|--------|------|--------|
| `200 OK` | 成功 | `QueryHistory[]` |
| `401 Unauthorized` | 未登录 | `ErrorResponse` |
| `403 Forbidden` | 无权访问 | 空 |
| `404 Not Found` | 任务不存在 | 空 |

---

### 6.3 获取特定查询历史

```
GET /api/jobs/{id}/query-history/{text_hash}
```

**请求头**: `Authorization: Bearer {token}`

**功能**: 根据文本哈希获取特定的查询历史（用于恢复对话）

**路径参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| `id` | UUID v4 | 任务 ID |
| `text_hash` | string | 划选文本的 SHA-256 哈希 |

**响应**:

| 状态码 | 说明 | 响应体 |
|--------|------|--------|
| `200 OK` | 成功 | `QueryHistory` |
| `401 Unauthorized` | 未登录 | `ErrorResponse` |
| `403 Forbidden` | 无权访问 | 空 |
| `404 Not Found` | 任务或查询历史不存在 | 空 |

---

## 7. 任务处理流程

### 7.1 生命周期

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

### 7.2 处理超时

| 步骤 | 超时时间 |
|------|----------|
| ArXiv 下载 | 60 秒 |
| pdflatex 预编译 | 60 秒 |
| LaTeXML 编译 | 300 秒 |
| LaTeXMLPost 渲染 | 120 秒 |

超时后任务状态将变为 `Error`。

### 7.3 文件存储结构

```
./jobs/
  {jobId}/
    original/           # 原始上传/下载文件
    src/                # 解压后的源码
    normalized/         # 规范化后的文件
    out/                # 产物文件（main.html, main.xml）
    meta/               # 元数据（job.json）
    log/                # 日志文件
    overlay/            # LaTeXML 补丁定义
    query_history/      # AI 查询历史（{text_hash}.json）
```

---

## 8. AI 提供商配置

系统支持通过 `ai_config.json` 配置多个 AI 提供商：

| 提供商 key | 名称 | 示例模型 |
|------------|------|----------|
| `deepseek` | DeepSeek | `deepseek-v4-pro`, `deepseek-v4-flash` |
| `openai` | OpenAI | `gpt-4`, `gpt-4-turbo`, `gpt-3.5-turbo` |
| `anthropic` | Anthropic | `claude-3-5-sonnet`, `claude-3-opus`, `claude-3-haiku` |
| `google` | Google AI | `gemini-pro`, `gemini-1.5-pro` |
| `zhipu` | 智谱AI | `glm-4`, `glm-3-turbo` |

---

## 9. 示例

### 9.1 用户注册

```bash
curl -X POST http://127.0.0.1:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "researcher", "password": "mypassword"}'
```

### 9.2 用户登录

```bash
curl -X POST http://127.0.0.1:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "researcher", "password": "mypassword"}'
```

**返回**:
```json
{
  "userId": "uuid-xxx",
  "username": "researcher",
  "token": "eyJhbGciOiJIUzI1NiIs..."
}
```

### 9.3 保存 API 密钥

```bash
curl -X POST http://127.0.0.1:8000/api/auth/api-key \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{"api_key": "sk-xxx", "provider": "deepseek", "model": "deepseek-v4-flash"}'
```

### 9.4 创建上传任务

```bash
curl -X POST http://127.0.0.1:8000/api/jobs \
  -H "Authorization: Bearer {token}" \
  -F "source_mode=upload" \
  -F "source_file=@paper.tar.gz"
```

### 9.5 创建 ArXiv 任务

```bash
curl -X POST http://127.0.0.1:8000/api/jobs \
  -H "Authorization: Bearer {token}" \
  -F "source_mode=arxiv" \
  -F "arxiv_id=2401.12345"
```

### 9.6 轮询任务进度

```bash
curl http://127.0.0.1:8000/api/jobs/{jobId} \
  -H "Authorization: Bearer {token}"
```

### 9.7 AI 对话

```bash
curl -X POST http://127.0.0.1:8000/api/chat \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "这篇论文的主要贡献是什么？",
    "context": "We propose a novel method...",
    "full_paper": "..."
  }'
```

### 9.8 重排任务顺序

```bash
curl -X PUT http://127.0.0.1:8000/api/jobs/reorder \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{"order": ["uuid-1", "uuid-2", "uuid-3"]}'
```

### 9.9 获取产物文件

```bash
curl http://127.0.0.1:8000/api/jobs/{jobId}/out/main.html?token={jwt_token} -o main.html
```

### 9.10 保存查询历史

```bash
curl -X POST http://127.0.0.1:8000/api/jobs/{jobId}/query-history \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{
    "text_excerpt": "We propose a novel method...",
    "text_hash": "a1b2c3d4...",
    "query": "这个方法的核心思想是什么？",
    "reply": "该方法的核心思想是..."
  }'
```

### 9.11 获取查询历史

```bash
# 列出所有
curl http://127.0.0.1:8000/api/jobs/{jobId}/query-history \
  -H "Authorization: Bearer {token}"

# 获取特定
curl http://127.0.0.1:8000/api/jobs/{jobId}/query-history/{text_hash} \
  -H "Authorization: Bearer {token}"
```
