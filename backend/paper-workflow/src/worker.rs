use crate::models::{JobState, JobStatus, SourceMode, StageDetail, StageStatus};
use crate::store::JobStore;
use anyhow::{Result, anyhow};
use flate2::read::GzDecoder;
use pathdiff::diff_paths;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use tar::Archive;
use tokio::fs;
use tokio::process::Command;
use tokio::time::{Duration, timeout};

/// 整个任务的后台入口
pub async fn process_job(mut job: JobState, store: Arc<JobStore>) {
    // 第一阶段：下载和解压
    let result = match job.source_mode {
        SourceMode::Arxiv => run_arxiv_workflow(&mut job, &store).await,
        SourceMode::Upload => run_upload_workflow(&mut job, &store).await,
    };

    // 如果第一阶段失败，保存错误状态并返回
    if let Err(e) = result {
        job.status = JobStatus::Error;
        job.errors.push(format!("工作流中断: {}", e));
        let _ = store.save_job(&job).await;
        return;
    }

    // 第二阶段：LaTeXML 转换
    let conversion_result = run_latexml_pipeline(&mut job, &store).await;

    if let Err(e) = conversion_result {
        job.status = JobStatus::Error;
        job.errors.push(format!("编译失败: {}", e));
    } else {
        job.status = JobStatus::Completed;
    }

    let _ = store.save_job(&job).await;
}

/// 流程：ArXiv 下载 -> 解压 -> 分析
async fn run_arxiv_workflow(job: &mut JobState, store: &JobStore) -> Result<()> {
    let arxiv_id = job
        .arxiv_id
        .clone()
        .ok_or_else(|| anyhow!("缺少 ArXiv ID"))?;

    // 1. 下载阶段
    update_stage(
        job,
        "下载源码",
        StageStatus::Running,
        "正在从 arXiv 获取...",
    )
    .await;
    job.status = JobStatus::Downloading;
    store.save_job(job).await?;

    let payload = download_from_arxiv(&arxiv_id).await?;
    let file_name = format!("{}.tar.gz", arxiv_id.replace('/', "_"));

    // 保存原始文件
    let original_path = store.get_job_file_path(job.job_id, "original", &file_name);
    fs::write(&original_path, payload).await?;

    update_stage(job, "下载源码", StageStatus::Done, "下载成功").await;

    // 2. 解压阶段
    execute_extraction(job, store, &original_path).await?;

    Ok(())
}

/// 流程：上传验证 -> 解压 -> 分析
async fn run_upload_workflow(job: &mut JobState, store: &JobStore) -> Result<()> {
    // 上传的文件已经在 routes.rs 中保存到了 original 目录
    update_stage(job, "文件验证", StageStatus::Running, "正在扫描上传内容...").await;

    let original_dir = store.get_job_file_path(job.job_id, "original", "");
    let mut entries = fs::read_dir(original_dir).await?;

    if let Some(entry) = entries.next_entry().await? {
        let path = entry.path();
        execute_extraction(job, store, &path).await?;
    } else {
        return Err(anyhow!("找不到上传的文件"));
    }

    Ok(())
}

/// 安全解压
async fn execute_extraction(
    job: &mut JobState,
    store: &JobStore,
    archive_path: &Path,
) -> Result<()> {
    update_stage(
        job,
        "安全解压",
        StageStatus::Running,
        "正在执行路径安全检查...",
    )
    .await;
    job.status = JobStatus::Extracting;
    store.save_job(job).await?;

    let src_dir = store.get_job_file_path(job.job_id, "src", "");
    let archive_path_buf = archive_path.to_path_buf();

    // 在阻塞线程池中执行解压
    tokio::task::spawn_blocking(move || {
        let file = std::fs::File::open(archive_path_buf)?;
        let mut archive = Archive::new(GzDecoder::new(file));

        for entry in archive.entries()? {
            let mut entry = entry?;
            let path = entry.path()?.to_path_buf();

            // 防止路径穿越攻击 (Zip Slip)
            if path.is_absolute()
                || path
                    .components()
                    .any(|c| matches!(c, std::path::Component::ParentDir))
            {
                return Err(anyhow!("检测到非法的路径攻击: {:?}", path));
            }

            entry.unpack_in(&src_dir)?;
        }
        Ok(())
    })
    .await??;

    update_stage(
        job,
        "安全解压",
        StageStatus::Done,
        "解压完成，所有路径均安全",
    )
    .await;
    Ok(())
}

/// 辅助函数：更新步骤详情
async fn update_stage(job: &mut JobState, title: &str, status: StageStatus, detail: &str) {
    if let Some(stage) = job.stage_details.iter_mut().find(|s| s.title == title) {
        stage.status = status;
        stage.detail = detail.to_string();
    } else {
        job.stage_details.push(StageDetail {
            title: title.to_string(),
            status,
            detail: detail.to_string(),
        });
    }
}

/// 辅助函数：HTTP 请求 arXiv
async fn download_from_arxiv(arxiv_id: &str) -> Result<Vec<u8>> {
    let url = format!("https://arxiv.org/src/{}", arxiv_id);
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(60))
        .build()?;

    let resp = client.get(url).send().await?.error_for_status()?;
    Ok(resp.bytes().await?.to_vec())
}

async fn find_root_tex(src_dir: &Path) -> Result<PathBuf> {
    let mut entries = fs::read_dir(src_dir).await?;
    while let Some(entry) = entries.next_entry().await? {
        let path = entry.path();
        if path.extension().and_then(|s| s.to_str()) == Some("tex") {
            let content = fs::read_to_string(&path).await.unwrap_or_default();
            if content.contains("\\documentclass") && content.contains("\\begin{document}") {
                return Ok(path);
            }
        }
    }
    Err(anyhow!("未能在源码中找到主 .tex 文件"))
}

async fn run_latexml_pipeline(job: &mut JobState, store: &JobStore) -> Result<()> {
    let src_dir = store.get_job_file_path(job.job_id, "src", "");
    let out_dir = store.get_job_file_path(job.job_id, "out", "");
    let out_rel_to_src =
        diff_paths(&out_dir, &src_dir).ok_or_else(|| anyhow!("无法计算相对路径"))?;

    // 1. 识别主文件
    update_stage(
        job,
        "解析结构",
        StageStatus::Running,
        "正在识别主 LaTeX 文件...",
    )
    .await;
    let root_tex_path = find_root_tex(&src_dir).await?;
    let root_tex_filename = root_tex_path
        .file_name()
        .and_then(|s| s.to_str())
        .ok_or_else(|| anyhow!("非法的文件名"))?;

    job.status = JobStatus::Processing;
    store.save_job(job).await?;

    let compile_timeout = Duration::from_secs(300);

    // 2. 运行 LaTeXML (生成 XML)
    update_stage(
        job,
        "LaTeXML 编译",
        StageStatus::Running,
        "正在将 TeX 转换为 XML...",
    )
    .await;
    let xml_output = out_rel_to_src.join("main.xml");

    let mut latexml_cmd = Command::new("latexml")
        .arg("--dest")
        .arg(&xml_output)
        .arg("--noparse")
        .arg("--includestyles")
        .arg(&root_tex_filename)
        .current_dir(&src_dir)
        .spawn()?;

    match timeout(compile_timeout, latexml_cmd.wait()).await {
        Ok(Ok(status)) if status.success() => {
            tracing::info!("XML 生成成功");
        }
        Ok(_) => {
            let _ = latexml_cmd.kill().await;
            return Err(anyhow!("LaTeXML 编译失败，请检查 LaTeX 语法或宏包依赖"));
        }
        Err(_) => {
            let _ = latexml_cmd.kill().await;
            return Err(anyhow!("LaTeXML 编译超时，任务已自动终止"));
        }
    }

    // 3. 运行 LaTeXMLPost (生成 HTML)
    update_stage(
        job,
        "HTML 生成",
        StageStatus::Running,
        "正在渲染最终网页...",
    )
    .await;

    let html_output = out_rel_to_src.join("main.html");

    let status = Command::new("latexmlpost")
        .arg("--dest")
        .arg(&html_output)
        .arg(&xml_output)
        .current_dir(&src_dir)
        .status()
        .await?;

    if status.success() {
        job.artifacts
            .insert("html".to_string(), "out/main.html".to_string());
        job.artifacts
            .insert("xml".to_string(), "out/main.xml".to_string());
        update_stage(job, "HTML 生成", StageStatus::Done, "转换成功").await;
    } else {
        return Err(anyhow!("LaTeXMLPost 执行失败"));
    }

    Ok(())
}
