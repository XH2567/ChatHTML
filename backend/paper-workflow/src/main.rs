use axum::{
    Router,
    routing::{get, post},
};
use std::net::SocketAddr;
use std::sync::Arc;
use tower_http::cors::{Any, CorsLayer};
use tower_http::trace::TraceLayer;
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

// 1. 声明所有模块，让编译器处理这些文件
mod models;
mod routes;
mod store;
mod worker;

#[tokio::main]
async fn main() {
    // 2. 初始化日志系统（这能让你在终端看到每个请求的详细情况）
    tracing_subscriber::registry()
        .with(tracing_subscriber::fmt::layer())
        .init();

    // 3. 初始化持久化存储（创建 jobs 目录）
    let base_path = "./jobs";
    let store = Arc::new(store::JobStore::new(base_path));

    // 4. 创建共享状态
    // 我们把 store 封装在 Arc（原子引用计数）里，这样多个线程就能安全地共享它
    let app_state = Arc::new(routes::AppState { store });

    // 5. 配置跨域 (CORS)
    let cors = CorsLayer::new()
        .allow_origin(Any) // 开发环境下允许任何来源，生产环境建议缩小范围
        .allow_methods(Any)
        .allow_headers(Any);

    // 6. 组装路由（把 routes.rs 里的函数和 URL 绑定）
    let app = Router::new()
        // 获取列表，创建任务，删除任务
        .route(
            "/api/jobs",
            get(routes::list_jobs)
                .post(routes::create_job)
                .delete(routes::delete_all_jobs),
        )
        // 获取单个详情和删除
        .route(
            "/api/jobs/:id",
            get(routes::get_job).delete(routes::delete_job),
        )
        // AI 聊天代理
        .route("/api/chat", post(routes::ai_chat_proxy))
        // 获取任务产物文件
        .route("/api/jobs/:id/artifacts/*path", get(routes::get_artifact))
        // 绑定共享状态
        .with_state(app_state)
        // 开启日志追踪和跨域支持
        .layer(TraceLayer::new_for_http())
        .layer(cors);

    // 7. 启动服务器
    let addr = SocketAddr::from(([127, 0, 0, 1], 8000));
    let listener = tokio::net::TcpListener::bind(addr).await.unwrap();

    println!("Paper Workflow 后端已启动: http://{}", addr);
    println!("任务存储目录: {}", base_path);

    axum::serve(listener, app).await.unwrap();
}
