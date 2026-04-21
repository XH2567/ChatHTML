use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use uuid::Uuid;

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
#[serde(rename_all = "camelCase")]
pub enum JobStatus {
    Created,
    Queued,
    Downloading,
    Validating,
    Extracting,
    Analyzing,
    Processing,
    Completed,
    Partial,
    Error,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
#[serde(rename_all = "camelCase")]
pub enum StageStatus {
    Pending,
    Running,
    Done,
    Error,
    Skipped,
}

#[derive(Serialize, Deserialize, Debug, Clone)]
#[serde(rename_all = "camelCase")]
pub struct StageDetail {
    pub title: String,
    pub status: StageStatus,
    pub detail: String,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
#[serde(rename_all = "camelCase")]
pub enum SourceMode {
    Upload,
    Arxiv,
}

#[derive(Serialize, Deserialize, Debug, Clone)]
#[serde(rename_all = "camelCase")]
pub struct JobState {
    pub job_id: Uuid,
    pub created_at: DateTime<Utc>,
    pub status: JobStatus,
    pub source_mode: SourceMode,
    pub arxiv_id: Option<String>,
    pub original_name: Option<String>,
    pub archive_size: Option<u64>,
    pub errors: Vec<String>,
    pub warnings: Vec<String>,
    pub duration_seconds: Option<f64>,

    // 任务产物，例如 {"html": "out/main.html", "xml": "out/main.xml"}
    pub artifacts: HashMap<String, String>,

    // 详细的处理阶段（用于前端时间轴）
    pub stage_details: Vec<StageDetail>,

    // 论文元数据（LaTeXML 解析结果等）
    pub manifest: Option<serde_json::Value>,
}

impl JobState {
    pub fn new(source_mode: SourceMode, arxiv_id: Option<String>) -> Self {
        Self {
            job_id: Uuid::new_v4(),
            created_at: Utc::now(),
            status: JobStatus::Created,
            source_mode,
            arxiv_id,
            original_name: None,
            archive_size: None,
            errors: Vec::new(),
            warnings: Vec::new(),
            duration_seconds: None,
            artifacts: HashMap::new(),
            stage_details: Vec::new(),
            manifest: None,
        }
    }
}
