use crate::models::SourceMode;
use crate::store::JobStore;
use axum::{
    Json,
    body::Body,
    extract::{Multipart, Path, State},
    http::{StatusCode, header},
    response::IntoResponse,
};
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
    pub _context: String,
    pub _model: String,
    pub _api_key: String,
    pub _full_paper: String,
}

pub async fn ai_chat_proxy(Json(req): Json<ChatRequest>) -> impl IntoResponse {
    // Todo: 调用 reqwest 请求 OpenAI/DeepSeek
    // 为了演示，先返回一个 mock 数据
    Json(serde_json::json!({
        "reply": format!("AI 收到你的问题：'{}'。正在针对论文背景进行分析...", req.query)
    }))
}

/// 获取任务产物文件（HTML, 图片, 日志等）
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
