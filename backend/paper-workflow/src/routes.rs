use crate::ai::ChatRequest;
use crate::auth::{AppAuth, Claims};
use crate::models::{QueryHistory, SourceMode};
use crate::store::JobStore;
use axum::{
    Json,
    body::Body,
    extract::{Multipart, Path, Query, State},
    http::{StatusCode, header, HeaderMap, Response},
    response::IntoResponse,
};
use axum::extract::FromRef;
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use uuid::Uuid;

pub struct AppState {
    pub store: Arc<JobStore>,
    pub auth: Arc<AppAuth>,
}

impl FromRef<AppState> for Arc<AppAuth> {
    fn from_ref(state: &AppState) -> Arc<AppAuth> {
        state.auth.clone()
    }
}

impl FromRef<AppState> for Arc<JobStore> {
    fn from_ref(state: &AppState) -> Arc<JobStore> {
        state.store.clone()
    }
}

fn extract_token(headers: &HeaderMap) -> Option<String> {
    let auth_header = headers.get(header::AUTHORIZATION)?.to_str().ok()?;
    if !auth_header.starts_with("Bearer ") {
        return None;
    }
    Some(auth_header[7..].to_string())
}

fn validate_token(state: &Arc<AppState>, token: &str) -> Result<Claims, StatusCode> {
    state
        .auth
        .auth_service
        .validate_token(token)
        .map_err(|_| StatusCode::UNAUTHORIZED)
}

fn require_auth(state: &Arc<AppState>, headers: &HeaderMap) -> Result<Claims, StatusCode> {
    let token = extract_token(headers).ok_or(StatusCode::UNAUTHORIZED)?;
    validate_token(state, &token)
}

fn optional_auth(state: &Arc<AppState>, headers: &HeaderMap) -> Option<Claims> {
    extract_token(headers)
        .and_then(|token| validate_token(state, &token).ok())
}

#[derive(Serialize)]
pub struct AuthResponse {
    pub user_id: String,
    pub username: String,
    pub token: String,
}

#[derive(Deserialize)]
pub struct RegisterRequest {
    pub username: String,
    pub password: String,
}

#[derive(Deserialize)]
pub struct LoginRequest {
    pub username: String,
    pub password: String,
}

#[derive(Deserialize)]
pub struct SetApiKeyRequest {
    pub api_key: String,
    pub provider: String,
    pub model: String,
}

#[derive(Deserialize)]
pub struct TokenQuery {
    pub token: Option<String>,
}

#[derive(Deserialize)]
pub struct ReorderRequest {
    pub order: Vec<Uuid>,
}

pub async fn register(
    State(state): State<Arc<AppState>>,
    Json(req): Json<RegisterRequest>,
) -> impl IntoResponse {
    if req.username.trim().is_empty() {
        return (
            StatusCode::BAD_REQUEST,
            Json(serde_json::json!({"error": "用户名不能为空"})),
        )
            .into_response();
    }

    if req.password.len() < 6 {
        return (
            StatusCode::BAD_REQUEST,
            Json(serde_json::json!({"error": "密码至少需要6个字符"})),
        )
            .into_response();
    }

    if let Ok(Some(_)) = state.auth.auth_service.db.get_user_by_username(&req.username) {
        return (
            StatusCode::CONFLICT,
            Json(serde_json::json!({"error": "用户名已存在"})),
        )
            .into_response();
    }

    let password_hash = match state.auth.auth_service.hash_password(&req.password) {
        Ok(h) => h,
        Err(_) => {
            return StatusCode::INTERNAL_SERVER_ERROR.into_response();
        }
    };

    let user = match state.auth.auth_service.db.create_user(&req.username, &password_hash) {
        Ok(u) => u,
        Err(_) => {
            return StatusCode::INTERNAL_SERVER_ERROR.into_response();
        }
    };

    let token = match state.auth.auth_service.create_token(&user.id) {
        Ok(t) => t,
        Err(_) => {
            return StatusCode::INTERNAL_SERVER_ERROR.into_response();
        }
    };

    Json(AuthResponse {
        user_id: user.id,
        username: user.username,
        token,
    })
    .into_response()
}

pub async fn login(
    State(state): State<Arc<AppState>>,
    Json(req): Json<LoginRequest>,
) -> impl IntoResponse {
    let password_hash = match state.auth.auth_service.db.get_user_password_hash(&req.username) {
        Ok(Some(h)) => h,
        Ok(None) => {
            return (
                StatusCode::UNAUTHORIZED,
                Json(serde_json::json!({"error": "用户名或密码错误"})),
            )
                .into_response();
        }
        Err(_) => {
            return StatusCode::INTERNAL_SERVER_ERROR.into_response();
        }
    };

    let valid = state
        .auth
        .auth_service
        .verify_password(&req.password, &password_hash)
        .unwrap_or(false);

    if !valid {
        return (
            StatusCode::UNAUTHORIZED,
            Json(serde_json::json!({"error": "用户名或密码错误"})),
        )
            .into_response();
    }

    let user = state
        .auth
        .auth_service
        .db
        .get_user_by_username(&req.username)
        .unwrap()
        .unwrap();

    let token = match state.auth.auth_service.create_token(&user.id) {
        Ok(t) => t,
        Err(_) => {
            return StatusCode::INTERNAL_SERVER_ERROR.into_response();
        }
    };

    Json(AuthResponse {
        user_id: user.id,
        username: user.username,
        token,
    })
    .into_response()
}

pub async fn logout(
    State(_state): State<Arc<AppState>>,
    headers: HeaderMap,
) -> impl IntoResponse {
    if let Some(token) = extract_token(&headers) {
        tracing::info!("用户登出: {}", token);
    }
    StatusCode::NO_CONTENT.into_response()
}

#[derive(Serialize)]
pub struct UserInfo {
    pub user_id: String,
    pub username: String,
}

pub async fn get_me(
    State(state): State<Arc<AppState>>,
    headers: HeaderMap,
) -> impl IntoResponse {
    let claims = match require_auth(&state, &headers) {
        Ok(c) => c,
        Err(e) => return e.into_response(),
    };

    let user = state
        .auth
        .auth_service
        .db
        .get_user_by_username(&claims.sub)
        .unwrap()
        .unwrap();

    Json(UserInfo {
        user_id: user.id,
        username: user.username,
    })
    .into_response()
}

pub async fn set_api_key(
    State(state): State<Arc<AppState>>,
    headers: HeaderMap,
    Json(req): Json<SetApiKeyRequest>,
) -> impl IntoResponse {
    let claims = match require_auth(&state, &headers) {
        Ok(c) => c,
        Err(_) => {
            return (
                StatusCode::UNAUTHORIZED,
                Json(serde_json::json!({"error": "请先登录"})),
            )
                .into_response();
        }
    };

    if req.api_key.trim().is_empty() {
        return (
            StatusCode::BAD_REQUEST,
            Json(serde_json::json!({"error": "API密钥不能为空"})),
        )
            .into_response();
    }

    if req.api_key.len() < 8 {
        return (
            StatusCode::BAD_REQUEST,
            Json(serde_json::json!({"error": "API密钥格式无效"})),
        )
            .into_response();
    }

    let encrypted = format!("encrypted:{}", req.api_key);

    if let Err(e) = state.auth.auth_service.db.set_user_api_key(&claims.sub, &encrypted, &req.provider, &req.model) {
        tracing::error!("保存API密钥失败 (user={}): {:?}", claims.sub, e);
        return (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(serde_json::json!({"error": format!("保存API密钥失败: {}", e)})),
        )
            .into_response();
    }

    Json(serde_json::json!({"success": true, "provider": req.provider, "model": req.model})).into_response()
}

#[derive(Serialize)]
pub struct MaskedApiKey {
    pub has_key: bool,
    pub masked: Option<String>,
    pub provider: Option<String>,
    pub model: Option<String>,
}

pub async fn get_api_key(
    State(state): State<Arc<AppState>>,
    headers: HeaderMap,
) -> impl IntoResponse {
    let claims = match require_auth(&state, &headers) {
        Ok(c) => c,
        Err(_) => {
            return (
                StatusCode::UNAUTHORIZED,
                Json(serde_json::json!({"error": "请先登录"})),
            )
                .into_response();
        }
    };

    match state.auth.auth_service.db.get_user_api_key(&claims.sub) {
        Ok(Some(_)) => {
            let provider = state.auth.auth_service.db.get_user_api_provider(&claims.sub).ok().flatten();
            let model = state.auth.auth_service.db.get_user_api_model(&claims.sub).ok().flatten();
            Json(MaskedApiKey {
                has_key: true,
                masked: Some("********".to_string()),
                provider,
                model,
            })
            .into_response()
        }
        Ok(None) => Json(MaskedApiKey {
            has_key: false,
            masked: None,
            provider: None,
            model: None,
        })
        .into_response(),
        Err(_) => StatusCode::INTERNAL_SERVER_ERROR.into_response(),
    }
}

pub async fn delete_api_key(
    State(state): State<Arc<AppState>>,
    headers: HeaderMap,
) -> impl IntoResponse {
    let claims = match require_auth(&state, &headers) {
        Ok(c) => c,
        Err(e) => return e.into_response(),
    };

    if let Err(_) = state.auth.auth_service.db.delete_user_api_key(&claims.sub) {
        return StatusCode::INTERNAL_SERVER_ERROR.into_response();
    }

    StatusCode::NO_CONTENT.into_response()
}

pub async fn list_jobs(
    State(state): State<Arc<AppState>>,
    headers: HeaderMap,
) -> impl IntoResponse {
    let claims = match require_auth(&state, &headers) {
        Ok(c) => c,
        Err(e) => return e.into_response(),
    };

    match state.store.list_jobs_by_user(&claims.sub).await {
        Ok(jobs) => Json(jobs).into_response(),
        Err(_) => StatusCode::INTERNAL_SERVER_ERROR.into_response(),
    }
}

pub async fn get_job(
    State(state): State<Arc<AppState>>,
    headers: HeaderMap,
    Path(job_id): Path<Uuid>,
) -> impl IntoResponse {
    let claims = match require_auth(&state, &headers) {
        Ok(c) => c,
        Err(e) => return e.into_response(),
    };

    match state.store.load_job(job_id).await {
        Ok(Some(job)) => {
            if job.user_id.as_ref() != Some(&claims.sub) {
                return StatusCode::FORBIDDEN.into_response();
            }
            Json(job).into_response()
        }
        Ok(None) => StatusCode::NOT_FOUND.into_response(),
        Err(_) => StatusCode::INTERNAL_SERVER_ERROR.into_response(),
    }
}

pub async fn create_job(
    State(state): State<Arc<AppState>>,
    headers: HeaderMap,
    mut multipart: Multipart,
) -> impl IntoResponse {
    let claims = match require_auth(&state, &headers) {
        Ok(c) => c,
        Err(e) => return e.into_response(),
    };

    let mut arxiv_id = None;
    let mut source_mode = SourceMode::Upload;
    let mut file_data = None;
    let mut file_name = None;

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

    let job = match state.store.create_job_with_user(source_mode, arxiv_id, &claims.sub).await {
        Ok(j) => j,
        Err(_) => return StatusCode::INTERNAL_SERVER_ERROR.into_response(),
    };

    if let (Some(data), Some(name)) = (file_data, file_name) {
        let path = state.store.get_job_file_path(job.job_id, "original", &name);
        let _ = tokio::fs::write(path, data).await;
    }

    tokio::spawn(crate::worker::process_job(job.clone(), state.store.clone()));

    (StatusCode::CREATED, Json(job)).into_response()
}

pub async fn ai_chat_proxy(
    State(state): State<Arc<AppState>>,
    headers: HeaderMap,
    Json(req): Json<ChatRequest>,
) -> impl IntoResponse {
    let claims = match require_auth(&state, &headers) {
        Ok(c) => c,
        Err(e) => return e.into_response(),
    };

    let api_key = match state.auth.auth_service.db.get_user_api_key(&claims.sub) {
        Ok(Some(key)) => {
            if let Some(stripped) = key.strip_prefix("encrypted:") {
                stripped.to_string()
            } else {
                key
            }
        }
        Ok(None) => {
            return (
                StatusCode::UNAUTHORIZED,
                Json(serde_json::json!({
                    "error": "请先在设置中配置AI服务API密钥"
                })),
            )
                .into_response();
        }
        Err(_) => {
            return StatusCode::INTERNAL_SERVER_ERROR.into_response();
        }
    };

    let provider_str = match state.auth.auth_service.db.get_user_api_provider(&claims.sub) {
        Ok(Some(p)) => p,
        Ok(None) => {
            return (
                StatusCode::BAD_REQUEST,
                Json(serde_json::json!({
                    "error": "未配置AI服务提供商"
                })),
            )
                .into_response();
        }
        Err(_) => return StatusCode::INTERNAL_SERVER_ERROR.into_response(),
    };

    let model_str = match state.auth.auth_service.db.get_user_api_model(&claims.sub) {
        Ok(Some(m)) => m,
        Ok(None) => {
            return (
                StatusCode::BAD_REQUEST,
                Json(serde_json::json!({
                    "error": "未配置模型ID"
                })),
            )
                .into_response();
        }
        Err(_) => return StatusCode::INTERNAL_SERVER_ERROR.into_response(),
    };

    let provider = &provider_str;

    let result = crate::ai::call_ai_api(&req, &api_key, provider, &model_str).await;

    match result {
        Ok(reply) => Json(serde_json::json!({
            "reply": reply,
            "model_used": model_str,
            "context_length": req.context.len(),
            "paper_length": req.full_paper.len(),
            "timestamp": chrono::Utc::now().to_rfc3339()
        }))
        .into_response(),
        Err(err_msg) => (
            StatusCode::BAD_GATEWAY,
            Json(serde_json::json!({
                "error": format!("AI服务请求失败: {}", err_msg)
            })),
        )
            .into_response(),
    }
}

pub async fn delete_job(
    State(state): State<Arc<AppState>>,
    headers: HeaderMap,
    Path(job_id): Path<Uuid>,
) -> impl IntoResponse {
    let claims = match require_auth(&state, &headers) {
        Ok(c) => c,
        Err(e) => return e.into_response(),
    };

    match state.store.load_job(job_id).await {
        Ok(Some(job)) => {
            if job.user_id.as_ref() != Some(&claims.sub) {
                return StatusCode::FORBIDDEN.into_response();
            }
        }
        Ok(None) => return StatusCode::NOT_FOUND.into_response(),
        Err(_) => return StatusCode::INTERNAL_SERVER_ERROR.into_response(),
    }

    match state.store.delete_job(job_id).await {
        Ok(_) => StatusCode::NO_CONTENT.into_response(),
        Err(e) => {
            tracing::error!("删除任务失败: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR.into_response()
        }
    }
}

pub async fn delete_all_jobs(
    State(state): State<Arc<AppState>>,
    headers: HeaderMap,
) -> impl IntoResponse {
    let claims = match require_auth(&state, &headers) {
        Ok(c) => c,
        Err(e) => return e.into_response(),
    };

    match state.store.delete_all_jobs_by_user(&claims.sub).await {
        Ok(_) => StatusCode::NO_CONTENT.into_response(),
        Err(e) => {
            tracing::error!("删除所有任务失败: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR.into_response()
        }
    }
}

pub async fn reorder_jobs(
    State(state): State<Arc<AppState>>,
    headers: HeaderMap,
    Json(req): Json<ReorderRequest>,
) -> impl IntoResponse {
    let claims = match require_auth(&state, &headers) {
        Ok(c) => c,
        Err(e) => return e.into_response(),
    };

    // 验证所有 job 属于当前用户
    for job_id in &req.order {
        match state.store.load_job(*job_id).await {
            Ok(Some(job)) => {
                if job.user_id.as_ref() != Some(&claims.sub) {
                    return StatusCode::FORBIDDEN.into_response();
                }
            }
            _ => return StatusCode::NOT_FOUND.into_response(),
        }
    }

    match state.store.reorder_jobs(&req.order).await {
        Ok(_) => StatusCode::NO_CONTENT.into_response(),
        Err(_) => StatusCode::INTERNAL_SERVER_ERROR.into_response(),
    }
}

fn auth_from_query_or_header(state: &Arc<AppState>, headers: &HeaderMap, query: &TokenQuery) -> Result<Claims, StatusCode> {
    if let Some(token) = &query.token {
        validate_token(state, token)
    } else if let Some(c) = optional_auth(state, headers) {
        Ok(c)
    } else {
        Err(StatusCode::UNAUTHORIZED)
    }
}

pub async fn get_out_artifact(
    State(state): State<Arc<AppState>>,
    headers: HeaderMap,
    Query(query): Query<TokenQuery>,
    Path((job_id, file_path)): Path<(Uuid, String)>,
) -> Response<Body> {
    // 对于 HTML 文件，需要验证 token（确保只有认证用户能访问论文内容）
    // 对于其他静态资源（图片、CSS等），直接放行
    let claims = if file_path.ends_with(".html") || file_path.ends_with(".htm") {
        if let Some(token) = extract_token(&headers) {
            match validate_token(&state, &token) {
                Ok(c) => c,
                Err(_) => return StatusCode::UNAUTHORIZED.into_response(),
            }
        } else if let Some(token) = &query.token {
            match validate_token(&state, token) {
                Ok(c) => c,
                Err(_) => return StatusCode::UNAUTHORIZED.into_response(),
            }
        } else {
            return StatusCode::UNAUTHORIZED.into_response();
        }
    } else {
        return serve_file(&state, job_id, &file_path).await;
    };

    match state.store.load_job(job_id).await {
        Ok(Some(job)) => {
            if job.user_id.as_ref() != Some(&claims.sub) {
                return StatusCode::FORBIDDEN.into_response();
            }
        }
        Ok(None) => return StatusCode::NOT_FOUND.into_response(),
        Err(_) => return StatusCode::INTERNAL_SERVER_ERROR.into_response(),
    }

    serve_file(&state, job_id, &file_path).await
}

async fn serve_file(state: &Arc<AppState>, job_id: Uuid, file_path: &str) -> Response<Body> {
    let full_path = state.store.get_job_file_path(job_id, "out", file_path);

    if !full_path.exists() || !full_path.is_file() {
        return StatusCode::NOT_FOUND.into_response();
    }

    let mime = mime_guess::from_path(&full_path).first_or_octet_stream();
    let contents = match std::fs::read(&full_path) {
        Ok(c) => c,
        Err(e) => {
            tracing::error!("读取产物文件失败: {}", e);
            return StatusCode::INTERNAL_SERVER_ERROR.into_response();
        }
    };

    (
        [
            (header::CONTENT_TYPE, mime.as_ref()),
            (header::CACHE_CONTROL, "public, max-age=3600"),
            (header::CONTENT_SECURITY_POLICY, "frame-ancestors 'self' http://localhost:5173 http://127.0.0.1:5173"),
            (header::ACCESS_CONTROL_ALLOW_ORIGIN, "*"),
            (header::ACCESS_CONTROL_ALLOW_HEADERS, "Content-Type"),
            (header::ACCESS_CONTROL_ALLOW_METHODS, "GET, POST, OPTIONS"),
        ],
        Body::from(contents),
    )
        .into_response()
}

pub async fn get_html_content(
    State(state): State<Arc<AppState>>,
    headers: HeaderMap,
    Query(query): Query<TokenQuery>,
    Path(job_id): Path<Uuid>,
) -> impl IntoResponse {
    let claims = match auth_from_query_or_header(&state, &headers, &query) {
        Ok(c) => c,
        Err(e) => return e.into_response(),
    };

    match state.store.load_job(job_id).await {
        Ok(Some(job)) => {
            if job.user_id.as_ref() != Some(&claims.sub) {
                return StatusCode::FORBIDDEN.into_response();
            }
        }
        Ok(None) => return StatusCode::NOT_FOUND.into_response(),
        Err(_) => return StatusCode::INTERNAL_SERVER_ERROR.into_response(),
    }

    let html_path = state.store.get_job_file_path(job_id, "out", "main.html");

    if !html_path.exists() || !html_path.is_file() {
        return StatusCode::NOT_FOUND.into_response();
    }

    match std::fs::read_to_string(&html_path) {
        Ok(html_content) => (
            [
                (header::CONTENT_TYPE, "text/plain; charset=utf-8"),
                (header::ACCESS_CONTROL_ALLOW_ORIGIN, "*"),
                (header::ACCESS_CONTROL_ALLOW_HEADERS, "Content-Type"),
                (header::ACCESS_CONTROL_ALLOW_METHODS, "GET, OPTIONS"),
            ],
            html_content,
        )
            .into_response(),
        Err(e) => {
            tracing::error!("读取HTML文件失败: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR.into_response()
        }
    }
}

#[derive(Deserialize)]
pub struct SaveQueryHistoryRequest {
    pub text_excerpt: String,
    pub text_hash: String,
    pub query: String,
    pub reply: String,
}

pub async fn save_query_history(
    State(state): State<Arc<AppState>>,
    headers: HeaderMap,
    Path(job_id): Path<Uuid>,
    Json(req): Json<SaveQueryHistoryRequest>,
) -> impl IntoResponse {
    let claims = match require_auth(&state, &headers) {
        Ok(c) => c,
        Err(e) => return e.into_response(),
    };

    match state.store.load_job(job_id).await {
        Ok(Some(job)) => {
            if job.user_id.as_ref() != Some(&claims.sub) {
                return StatusCode::FORBIDDEN.into_response();
            }
        }
        Ok(None) => return StatusCode::NOT_FOUND.into_response(),
        Err(_) => return StatusCode::INTERNAL_SERVER_ERROR.into_response(),
    }

    let history = QueryHistory::new(req.text_excerpt, req.text_hash, req.query, req.reply);

    match state.store.save_query_history(job_id, &history).await {
        Ok(_) => StatusCode::CREATED.into_response(),
        Err(e) => {
            tracing::error!("保存查询历史失败: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR.into_response()
        }
    }
}

pub async fn list_query_histories(
    State(state): State<Arc<AppState>>,
    headers: HeaderMap,
    Path(job_id): Path<Uuid>,
) -> impl IntoResponse {
    let claims = match require_auth(&state, &headers) {
        Ok(c) => c,
        Err(e) => return e.into_response(),
    };

    match state.store.load_job(job_id).await {
        Ok(Some(job)) => {
            if job.user_id.as_ref() != Some(&claims.sub) {
                return StatusCode::FORBIDDEN.into_response();
            }
        }
        Ok(None) => return StatusCode::NOT_FOUND.into_response(),
        Err(_) => return StatusCode::INTERNAL_SERVER_ERROR.into_response(),
    }

    match state.store.list_query_histories(job_id).await {
        Ok(histories) => Json(histories).into_response(),
        Err(e) => {
            tracing::error!("列出查询历史失败: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR.into_response()
        }
    }
}

pub async fn get_query_history(
    State(state): State<Arc<AppState>>,
    headers: HeaderMap,
    Path((job_id, text_hash)): Path<(Uuid, String)>,
) -> impl IntoResponse {
    let claims = match require_auth(&state, &headers) {
        Ok(c) => c,
        Err(e) => return e.into_response(),
    };

    match state.store.load_job(job_id).await {
        Ok(Some(job)) => {
            if job.user_id.as_ref() != Some(&claims.sub) {
                return StatusCode::FORBIDDEN.into_response();
            }
        }
        Ok(None) => return StatusCode::NOT_FOUND.into_response(),
        Err(_) => return StatusCode::INTERNAL_SERVER_ERROR.into_response(),
    }

    match state.store.get_query_history(job_id, &text_hash).await {
        Ok(Some(history)) => Json(history).into_response(),
        Ok(None) => StatusCode::NOT_FOUND.into_response(),
        Err(e) => {
            tracing::error!("获取查询历史失败: {}", e);
            StatusCode::INTERNAL_SERVER_ERROR.into_response()
        }
    }
}