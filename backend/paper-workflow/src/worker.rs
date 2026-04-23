use crate::models::{JobState, JobStatus, SourceMode, StageDetail, StageStatus};
use crate::store::JobStore;
use anyhow::{Result, anyhow};
use flate2::read::GzDecoder;
use pathdiff::diff_paths;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use tar::Archive;
use tokio::fs::{self, File};
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

async fn run_step_with_timeout(
    name: &str,
    args: &[&str],
    cwd: &Path,
    log_path: &Path,
    limit: Duration,
) -> bool {
    // 准备日志文件
    let log_file = match File::create(log_path).await {
        Ok(f) => f.into_std().await,
        Err(_) => return false,
    };

    let mut cmd = Command::new(name);
    cmd.args(args)
        .current_dir(cwd)
        .stdout(log_file.try_clone().unwrap())
        .stderr(log_file);

    let mut child = match cmd.spawn() {
        Ok(c) => c,
        Err(_) => return false,
    };

    // 使用 tokio 的 timeout 包装 wait()
    match timeout(limit, child.wait()).await {
        Ok(Ok(status)) => status.success(),
        Ok(Err(_)) => false,
        Err(_) => {
            // 超时了，强行杀死子进程
            let _ = child.kill().await;
            tracing::error!("步骤 {} 执行超时 ({:?})，已终止", name, limit);
            false
        }
    }
}

async fn run_latexml_pipeline(job: &mut JobState, store: &JobStore) -> Result<()> {
    let job_dir = store.get_job_path(job.job_id);
    let src_dir = store.get_job_file_path(job.job_id, "src", "");
    let out_dir = store.get_job_file_path(job.job_id, "out", "");

    let log_dir = job_dir.join("log");
    let overlay_dir = job_dir.join("overlay");
    tokio::fs::create_dir_all(&log_dir).await?;
    tokio::fs::create_dir_all(&overlay_dir).await?;

    let rel_overlay_dir =
        diff_paths(&overlay_dir, &src_dir).ok_or_else(|| anyhow!("无法计算相对路径"))?;

    // 识别主文件
    let root_tex_path = find_root_tex(&src_dir).await?;
    let root_stem = root_tex_path.file_stem().unwrap().to_str().unwrap();
    let root_name = root_tex_path.file_name().unwrap().to_str().unwrap();

    // 使用pdfLatex进行预编译
    update_stage(job, "预编译", StageStatus::Running, "生成辅助文件...").await;
    run_step_with_timeout(
        "pdflatex",
        &["-interaction=nonstopmode", "-draftmode", root_name],
        &src_dir,
        &log_dir.join("preflight.log"),
        Duration::from_secs(60),
    )
    .await;

    // 注入.bib，处理参考文献
    let bbl_path = src_dir.join(format!("{}.bbl", root_stem));
    let mut target_tex = root_name.to_string();
    if bbl_path.exists() {
        if let Ok(content) = tokio::fs::read_to_string(&root_tex_path).await {
            if content.contains("\\bibliography") {
                let patched_name = format!("{}.latexml.tex", root_stem);
                let patched_content =
                    content.replace("\\bibliography", &format!("\\input{{{}.bbl}} %", root_stem));
                tokio::fs::write(src_dir.join(&patched_name), patched_content).await?;
                target_tex = patched_name;
            }
        }
    }

    // 创建伪装定义，处理不兼容宏包
    let shim = "package LaTeXML::Package::Pool; use LaTeXML::Package; DefMacro('\\tcbuselibrary{}', ''); 1;";
    tokio::fs::write(overlay_dir.join("tcolorbox.sty.ltxml"), shim).await?;

    // 运行 LaTeXML (生成 XML)
    update_stage(job, "LaTeXML", StageStatus::Running, "正在执行编译...").await;
    let xml_path = out_dir.join("main.xml");
    let rel_xml_path =
        diff_paths(&xml_path, &src_dir).ok_or_else(|| anyhow!("无法计算相对路径"))?;
    let latexml_success = run_step_with_timeout(
        "latexml",
        &[
            &format!("--destination={}", rel_xml_path.display()),
            &format!("--path={}", rel_overlay_dir.display()), // 引入补丁路径
            "--includestyles",
            &target_tex,
        ],
        &src_dir,
        &log_dir.join("latexml.log"),
        Duration::from_secs(300),
    )
    .await;

    if !latexml_success {
        return Err(anyhow!("LaTeXML 编译失败，请检查日志"));
    }

    // 运行 LaTeXMLPost (生成 HTML)
    update_stage(job, "HTML生成", StageStatus::Running, "正在生成网页...").await;
    let html_path = out_dir.join("main.html");
    let rel_html_path =
        diff_paths(&html_path, &src_dir).ok_or_else(|| anyhow!("无法计算相对路径"))?;
    let post_success = run_step_with_timeout(
        "latexmlpost",
        &[
            &format!("--destination={}", rel_html_path.display()),
            "--format=html5",
            &format!("--path={}", rel_overlay_dir.display()),
            rel_xml_path.to_str().unwrap(),
        ],
        &src_dir,
        &log_dir.join("latexmlpost.log"),
        Duration::from_secs(120),
    )
    .await;

    if post_success {
        job.artifacts.insert("html".into(), "out/main.html".into());
        job.artifacts.insert("xml".into(), "out/main.xml".into());
        update_stage(job, "完成", StageStatus::Done, "转换成功").await;
        Ok(())
    } else {
        Err(anyhow!("LaTeXMLPost 渲染失败"))
    }
}
