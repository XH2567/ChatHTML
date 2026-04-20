# Paper Workflow API v1

## 1. 任务状态 (JobStatus)
枚举值: `Queued`, `Downloading`, `Extracting`, `Processing`, `Completed`, `Failed`

## 2. 接口定义

`GET /api/jobs`
- **功能**: 获取最近 20 条任务
- **响应**: `200 OK`, Body: `JobState[]`

`POST /api/jobs`
- **功能**: 创建任务
- **请求体**: `multipart/form-data`
  - `source_mode`: "upload" | "arxiv"
  - `arxiv_id`: string (可选)
  - `source_file`: file (可选)
- **响应**: `201 Created`, Body: `JobState`

`GET /api/jobs/{id}`
- **功能**: 获取单个任务详情（用于轮询）
- **响应**: `200 OK`, Body: `JobState` | `404 Not Found`

`GET /api/jobs/{id}/artifacts/{path...}`
- **功能**: 获取产物文件
- **响应**: `200 OK`, Body: 原始文件流 (image/png, text/html 等)