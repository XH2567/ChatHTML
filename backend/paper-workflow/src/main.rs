use axum::{
    Router,
    body::Body,
    http::{Request, StatusCode},
    middleware::{self, Next},
    response::Response,
    routing::{get, post, delete, put},
};
use std::net::SocketAddr;
use std::path::PathBuf;
use std::sync::{Arc, OnceLock};
use tower_http::cors::{Any, CorsLayer};
use tower_http::services::ServeDir;
use tower_http::trace::TraceLayer;
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

static INDEX_HTML: OnceLock<String> = OnceLock::new();

async fn spa_fallback(
    request: Request<Body>,
    next: Next,
) -> Response {
    let response = next.run(request).await;
    if response.status() == StatusCode::NOT_FOUND {
        if let Some(html) = INDEX_HTML.get() {
            return Response::builder()
                .status(StatusCode::OK)
                .header("Content-Type", "text/html")
                .body(Body::from(html.clone()))
                .unwrap();
        }
    }
    response
}

mod ai;
mod auth;
mod database;
mod models;
mod routes;
mod store;
mod worker;

#[tokio::main]
async fn main() {
    tracing_subscriber::registry()
        .with(tracing_subscriber::fmt::layer())
        .init();

    let base_path = "./jobs";
    let store = Arc::new(store::JobStore::new(base_path));

    let db = Arc::new(
        database::Database::new("./paper_workflow.db")
            .expect("无法初始化数据库"),
    );

    let app_auth = Arc::new(auth::AppAuth::new(db));

    let app_state = Arc::new(routes::AppState { store, auth: app_auth });

    let cors = CorsLayer::new()
        .allow_origin(Any)
        .allow_methods(Any)
        .allow_headers(Any);

    let exe_dir = std::env::current_exe()
        .ok()
        .and_then(|p| p.parent().map(|p| p.to_path_buf()))
        .unwrap_or_else(|| PathBuf::from("."));
    let dist_dir = exe_dir.join("dist");

    let index_path = dist_dir.join("index.html");
    if index_path.exists() {
        let html = std::fs::read_to_string(&index_path)
            .expect("failed to read dist/index.html");
        INDEX_HTML.set(html).ok();
    }

    let app = Router::new()
        .route("/api/auth/register", post(routes::register))
        .route("/api/auth/login", post(routes::login))
        .route("/api/auth/logout", post(routes::logout))
        .route("/api/auth/me", get(routes::get_me))
        .route("/api/auth/api-key", post(routes::set_api_key))
        .route("/api/auth/api-key", get(routes::get_api_key))
        .route("/api/auth/api-key", delete(routes::delete_api_key))
        .route(
            "/api/jobs",
            get(routes::list_jobs)
                .post(routes::create_job)
                .delete(routes::delete_all_jobs),
        )
        .route("/api/jobs/reorder", put(routes::reorder_jobs))
        .route(
            "/api/jobs/:id",
            get(routes::get_job).delete(routes::delete_job),
        )
        .route("/api/chat", post(routes::ai_chat_proxy))
        .route("/api/jobs/:id/out/*path", get(routes::get_out_artifact))
        .route("/api/jobs/:id/html", get(routes::get_html_content))
        .route(
            "/api/jobs/:id/query-history",
            post(routes::save_query_history)
                .get(routes::list_query_histories),
        )
        .route(
            "/api/jobs/:id/query-history/:text_hash",
            get(routes::get_query_history),
        )
        .with_state(app_state)
        .layer(TraceLayer::new_for_http())
        .layer(cors)
        .fallback_service(ServeDir::new(&dist_dir))
        .layer(middleware::from_fn(spa_fallback));

    let addr = SocketAddr::from(([127, 0, 0, 1], 8000));
    let listener = tokio::net::TcpListener::bind(addr).await
        .expect("无法绑定端口 8000，可能已被其他程序占用。请先关闭占用端口的程序，或更换端口。");

    println!("Paper Workflow 后端已启动: http://{}", addr);
    println!("任务存储目录: {}", base_path);

    axum::serve(listener, app).await.unwrap();
}