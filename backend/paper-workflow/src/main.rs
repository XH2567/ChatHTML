use axum::{
    Router,
    routing::{get, post, delete},
};
use std::net::SocketAddr;
use std::sync::Arc;
use tower_http::cors::{Any, CorsLayer};
use tower_http::trace::TraceLayer;
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

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
        .route(
            "/api/jobs/:id",
            get(routes::get_job).delete(routes::delete_job),
        )
        .route("/api/chat", post(routes::ai_chat_proxy))
        .route("/api/jobs/:id/out/*path", get(routes::get_out_artifact))
        .route("/api/jobs/:id/html", get(routes::get_html_content))
        .with_state(app_state)
        .layer(TraceLayer::new_for_http())
        .layer(cors);

    let addr = SocketAddr::from(([127, 0, 0, 1], 8000));
    let listener = tokio::net::TcpListener::bind(addr).await.unwrap();

    println!("Paper Workflow 后端已启动: http://{}", addr);
    println!("任务存储目录: {}", base_path);

    axum::serve(listener, app).await.unwrap();
}