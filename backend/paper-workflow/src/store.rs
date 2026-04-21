use crate::models::JobState;
use anyhow::{Context, Result};
use std::path::{Path, PathBuf};
use tokio::fs;
use uuid::Uuid;

pub struct JobStore {
    base_dir: PathBuf,
}

impl JobStore {
    pub fn new<P: AsRef<Path>>(path: P) -> Self {
        let base_dir = path.as_ref().to_path_buf();
        Self { base_dir }
    }

    pub async fn create_job(
        &self,
        source_mode: crate::models::SourceMode,
        arxiv_id: Option<String>,
    ) -> Result<JobState> {
        let job = JobState::new(source_mode, arxiv_id);
        let job_dir = self.base_dir.join(job.job_id.to_string());

        // 创建目录结构
        let dirs = ["original", "src", "normalized", "out", "meta", "logs"];
        for dir in dirs {
            fs::create_dir_all(job_dir.join(dir))
                .await
                .with_context(|| format!("无法创建目录: {}", dir))?;
        }

        // 保存初始状态
        self.save_job(&job).await?;
        Ok(job)
    }

    /// 将 JobState 序列化为 meta/job.json
    pub async fn save_job(&self, job: &JobState) -> Result<()> {
        let path = self
            .base_dir
            .join(job.job_id.to_string())
            .join("meta")
            .join("job.json");

        let json = serde_json::to_string_pretty(job)?;
        fs::write(path, json).await.context("写入 job.json 失败")?;
        Ok(())
    }

    /// 从磁盘读取特定任务的状态
    pub async fn load_job(&self, job_id: Uuid) -> Result<Option<JobState>> {
        let path = self
            .base_dir
            .join(job_id.to_string())
            .join("meta")
            .join("job.json");

        if !path.exists() {
            return Ok(None);
        }

        let content = fs::read_to_string(path).await?;
        let job: JobState = serde_json::from_str(&content)?;
        Ok(Some(job))
    }

    /// 获取最近的任务列表
    pub async fn list_jobs(&self) -> Result<Vec<JobState>> {
        let mut jobs = Vec::new();
        let mut entries = fs::read_dir(&self.base_dir).await?;

        while let Some(entry) = entries.next_entry().await? {
            if entry.file_type().await?.is_dir() {
                // 尝试解析目录名为 UUID
                if let Ok(job_id) = Uuid::parse_str(&entry.file_name().to_string_lossy()) {
                    if let Ok(Some(job)) = self.load_job(job_id).await {
                        jobs.push(job);
                    }
                }
            }
        }

        // 按创建时间排序
        jobs.sort_by(|a, b| b.created_at.cmp(&a.created_at));
        Ok(jobs)
    }

    /// 获取任务特定文件的物理路径
    pub fn get_job_file_path(&self, job_id: Uuid, sub_dir: &str, filename: &str) -> PathBuf {
        self.base_dir
            .join(job_id.to_string())
            .join(sub_dir)
            .join(filename)
    }
}
