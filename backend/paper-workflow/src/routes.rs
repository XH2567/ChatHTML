use crate::models::SourceMode;
use crate::store::JobStore;
use axum::{
    Json,
    body::Body,
    extract::{Multipart, Path, State},
    http::{StatusCode, header},
    response::IntoResponse,
};
use reqwest::Client;
use serde::Deserialize;
use std::sync::Arc;
use uuid::Uuid;

// 定义共享的状态，让所有路由都能访问 JobStore
pub struct AppState {
    pub store: Arc<JobStore>,
}

/// 1. 获取任务列表
pub async fn list_jobs(State(state): State<Arc<AppState>>) -> impl IntoResponse {
    match state.store.list_jobs().await {
        Ok(jobs) => Json(jobs).into_response(),
        Err(_) => StatusCode::INTERNAL_SERVER_ERROR.into_response(),
    }
}

/// 2. 获取单个任务详情
pub async fn get_job(
    State(state): State<Arc<AppState>>,
    Path(job_id): Path<Uuid>,
) -> impl IntoResponse {
    match state.store.load_job(job_id).await {
        Ok(Some(job)) => Json(job).into_response(),
        Ok(None) => StatusCode::NOT_FOUND.into_response(),
        Err(_) => StatusCode::INTERNAL_SERVER_ERROR.into_response(),
    }
}

/// 3. 创建任务 (支持上传文件和 Arxiv ID)
pub async fn create_job(
    State(state): State<Arc<AppState>>,
    mut multipart: Multipart,
) -> impl IntoResponse {
    let mut arxiv_id = None;
    let mut source_mode = SourceMode::Upload;
    let mut file_data = None;
    let mut file_name = None;

    // 循环解析表单字段
    while let Ok(Some(field)) = multipart.next_field().await {
        let name = field.name().unwrap_or("").to_string();

        match name.as_str() {
            "arxiv_id" => {
                let val = field.text().await.unwrap_or_default();
                if !val.is_empty() {
                    arxiv_id = Some(val);
                }
            }
            "source_mode" => {
                let val = field.text().await.unwrap_or_default();
                source_mode = if val == "arxiv" {
                    crate::models::SourceMode::Arxiv
                } else {
                    crate::models::SourceMode::Upload
                };
            }
            "source_file" => {
                file_name = field.file_name().map(|s| s.to_string());
                file_data = Some(field.bytes().await.unwrap_or_default());
            }
            _ => {}
        }
    }

    // 调用 Store 创建任务
    let job = match state.store.create_job(source_mode, arxiv_id).await {
        Ok(j) => j,
        Err(_) => return StatusCode::INTERNAL_SERVER_ERROR.into_response(),
    };

    // 如果是上传模式且有文件，保存文件
    if let (Some(data), Some(name)) = (file_data, file_name) {
        let path = state.store.get_job_file_path(job.job_id, "original", &name);
        let _ = tokio::fs::write(path, data).await;
    }

    tokio::spawn(crate::worker::process_job(job.clone(), state.store.clone()));

    (StatusCode::CREATED, Json(job)).into_response()
}

/// 4. AI 聊天代理
#[derive(Deserialize)]
pub struct ChatRequest {
    pub query: String,
    pub context: String,
    pub model: String,
    pub api_key: String,
    pub full_paper: String,
}

pub async fn ai_chat_proxy(Json(req): Json<ChatRequest>) -> impl IntoResponse {
    // 1. 验证 API 密钥
    if req.api_key.trim().is_empty() {
        return (
            StatusCode::UNAUTHORIZED,
            Json(serde_json::json!({
                "error": "API密钥不能为空，请在设置中配置AI服务API密钥"
            })),
        ).into_response();
    }

    // 2. 简单的API密钥格式验证（示例：至少8个字符）
    if req.api_key.len() < 8 {
        return (
            StatusCode::UNAUTHORIZED,
            Json(serde_json::json!({
                "error": "API密钥格式无效，请检查是否正确配置"
            })),
        ).into_response();
    }

    // 3. 构建AI请求
    let result = call_ai_api(&req).await;

    // 4. 处理响应
    match result {
        Ok(reply) => Json(serde_json::json!({
            "reply": reply,
            "model_used": req.model,
            "context_length": req.context.len(),
            "paper_length": req.full_paper.len(),
            "timestamp": chrono::Utc::now().to_rfc3339()
        })).into_response(),
        Err(err_msg) => (
            StatusCode::BAD_GATEWAY,
            Json(serde_json::json!({
                "error": format!("AI服务请求失败: {}", err_msg)
            })),
        ).into_response(),
    }
}

/// 调用实际的AI API
async fn call_ai_api(req: &ChatRequest) -> Result<String, String> {
    let client = Client::new();
    
    // 只支持DeepSeek API
    let api_url = "https://api.deepseek.com/v1/chat/completions";
    let auth_header = format!("Bearer {}", req.api_key);

    // 构建完整的上下文
    let mut full_context = String::new();
    
    if !req.full_paper.is_empty() {
        // 限制论文内容长度，避免超过token限制
        let paper_excerpt = if req.full_paper.len() > 30000 {
            &req.full_paper[0..30000]
        } else {
            &req.full_paper
        };
        full_context.push_str(&format!("论文内容（摘要）:\n{}\n\n", paper_excerpt));
    }
    
    if !req.context.is_empty() {
        full_context.push_str(&format!("划选内容:\n{}\n\n", req.context));
    }
    
    full_context.push_str(&format!("问题:\n{}", req.query));

    // 构建请求体
    let request_body = serde_json::json!({
        "model": req.model,
        "messages": [
            {
                "role": "system",
                "content": "你是一个专业的学术论文助手，擅长帮助研究人员理解论文内容。请基于提供的论文内容和划选内容，准确、专业地回答用户的问题。"
            },
            {
                "role": "user",
                "content": full_context
            }
        ],
        "temperature": 0.7,
        "max_tokens": 2000
    });

    // 发送请求
    let response = client
        .post(api_url)
        .header("Authorization", auth_header)
        .header("Content-Type", "application/json")
        .json(&request_body)
        .send()
        .await
        .map_err(|e| format!("网络请求失败: {}", e))?;

    // 检查响应状态
    if !response.status().is_success() {
        let status = response.status();
        let error_text = response.text().await.unwrap_or_else(|_| "无法读取错误详情".to_string());
        return Err(format!("AI API返回错误 ({}): {}", status, error_text));
    }

    // 解析响应
    let response_json: serde_json::Value = response
        .json()
        .await
        .map_err(|e| format!("解析响应失败: {}", e))?;

    // 提取回复内容
    let reply = response_json["choices"][0]["message"]["content"]
        .as_str()
        .ok_or_else(|| "AI响应格式无效，缺少回复内容".to_string())?
        .to_string();

    Ok(reply)
}

/// 5. 删除单个任务
pub async fn delete_job(
    State(state): State<Arc<AppState>>,
    Path(job_id): Path<Uuid>,
) -> impl IntoResponse {
    match state.store.delete_job(job_id).await {
        Ok(_) => StatusCode::NO_CONTENT.into_response(),
        Err(e) => {
            tracing::error!("删除任务失败: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR.into_response()
        }
    }
}

/// 6. 删除所有任务
pub async fn delete_all_jobs(
    State(state): State<Arc<AppState>>,
) -> impl IntoResponse {
    match state.store.delete_all_jobs().await {
        Ok(_) => StatusCode::NO_CONTENT.into_response(),
        Err(e) => {
            tracing::error!("删除所有任务失败: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR.into_response()
        }
    }
}

/// 7. 获取任务产物文件（HTML, 图片, 日志等）
/// 路径示例: /api/jobs/uuid/artifacts/out/main.html
pub async fn get_artifact(
    State(state): State<Arc<AppState>>,
    // Path((id, path)) 自动拆解 URL 中的 UUID 和剩余的长路径
    Path((job_id, file_path)): Path<(Uuid, String)>,
) -> impl IntoResponse {
    // 1. 调用 store 获取物理路径
    let full_path = state.store.get_job_file_path(job_id, "", &file_path);

    // 2. 安全检查：确保文件存在且是文件
    if !full_path.exists() || !full_path.is_file() {
        return StatusCode::NOT_FOUND.into_response();
    }

    // 3. 自动识别 MIME 类型
    let mime = mime_guess::from_path(&full_path).first_or_octet_stream();

    // 4. 异步读取文件内容
    match tokio::fs::read(&full_path).await {
        Ok(contents) => {
            // 5. 构造带正确 Header 的响应
            (
                [
                    (header::CONTENT_TYPE, mime.as_ref()),
                    // 允许浏览器缓存这些静态产物以提高性能
                    (header::CACHE_CONTROL, "public, max-age=3600"),
                    // 允许 iframe 嵌入，解决跨域访问问题
                    (header::CONTENT_SECURITY_POLICY, "frame-ancestors 'self' http://localhost:5173 http://127.0.0.1:5173"),
                    // 允许跨域访问
                    (header::ACCESS_CONTROL_ALLOW_ORIGIN, "*"),
                    // 允许跨域请求的头部
                    (header::ACCESS_CONTROL_ALLOW_HEADERS, "Content-Type"),
                    // 允许跨域请求的方法
                    (header::ACCESS_CONTROL_ALLOW_METHODS, "GET, POST, OPTIONS"),
                ],
                Body::from(contents),
            )
                .into_response()
        }
        Err(e) => {
            tracing::error!("读取产物文件失败: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR.into_response()
        }
    }
}

/// 8. 获取HTML文件内容（文本格式，用于前端srcdoc）
pub async fn get_html_content(
    State(state): State<Arc<AppState>>,
    Path(job_id): Path<Uuid>,
) -> impl IntoResponse {
    // 构建HTML文件路径：out/main.html
    let html_path = state.store.get_job_file_path(job_id, "out", "main.html");

    // 安全检查：确保文件存在且是文件
    if !html_path.exists() || !html_path.is_file() {
        return StatusCode::NOT_FOUND.into_response();
    }

    // 异步读取文件内容
    match tokio::fs::read_to_string(&html_path).await {
        Ok(html_content) => {
            // 构造响应，返回纯文本格式的HTML内容
            (
                [
                    (header::CONTENT_TYPE, "text/plain; charset=utf-8"),
                    // 允许跨域访问
                    (header::ACCESS_CONTROL_ALLOW_ORIGIN, "*"),
                    // 允许跨域请求的头部
                    (header::ACCESS_CONTROL_ALLOW_HEADERS, "Content-Type"),
                    // 允许跨域请求的方法
                    (header::ACCESS_CONTROL_ALLOW_METHODS, "GET, OPTIONS"),
                ],
                html_content,
            )
                .into_response()
        }
        Err(e) => {
            tracing::error!("读取HTML文件失败: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR.into_response()
        }
    }
}
