import cgi
import html
import io
import json
import os
import mimetypes
import re
import shutil
import tarfile
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, BinaryIO
from uuid import uuid4
from workflow import run_pipeline

BASE_DIR = Path(__file__).resolve().parent
from models import *
from store import store, JobStore

def html_page(title: str, body: str, extra_head: str = "") -> bytes:
    return f"""<!doctype html>
<html lang=\"zh-CN\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>{html.escape(title)}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f4efe7;
      --panel: rgba(255,255,255,0.82);
      --panel-strong: #ffffff;
      --text: #1d1b18;
      --muted: #675d54;
      --accent: #b45309;
      --accent-2: #0f766e;
      --accent-3: #7c3aed;
      --border: rgba(29,27,24,0.12);
      --shadow: 0 24px 80px rgba(30, 22, 10, 0.12);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at top left, rgba(180,83,9,0.14), transparent 28%),
        radial-gradient(circle at top right, rgba(15,118,110,0.16), transparent 24%),
        linear-gradient(180deg, #fbf7f1 0%, #f2ebe0 100%);
      min-height: 100vh;
    }}
    .shell {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 36px 20px 56px;
    }}
    .hero {{
      display: grid;
      grid-template-columns: 1.2fr 0.8fr;
      gap: 20px;
      align-items: stretch;
      margin-bottom: 24px;
    }}
    .card {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 24px;
      box-shadow: var(--shadow);
      backdrop-filter: blur(18px);
    }}
    .hero-main {{ padding: 28px; }}
    .eyebrow {{
      display: inline-flex;
      gap: 8px;
      align-items: center;
      font-size: 12px;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: var(--muted);
      margin-bottom: 18px;
    }}
    .eyebrow::before {{
      content: '';
      width: 10px;
      height: 10px;
      border-radius: 50%;
      background: linear-gradient(135deg, var(--accent), #f59e0b);
      box-shadow: 0 0 0 4px rgba(180,83,9,0.1);
    }}
    h1 {{
      margin: 0 0 12px;
      font-size: clamp(34px, 5vw, 58px);
      line-height: 0.98;
      letter-spacing: -0.05em;
    }}
    .lede {{
      margin: 0;
      color: var(--muted);
      font-size: 16px;
      line-height: 1.7;
      max-width: 62ch;
    }}
    .hero-side {{
      padding: 22px;
      display: grid;
      gap: 14px;
      align-content: start;
    }}
    .metric {{
      background: var(--panel-strong);
      border: 1px solid var(--border);
      border-radius: 18px;
      padding: 16px 18px;
    }}
    .metric-label {{ font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.08em; }}
    .metric-value {{ font-size: 24px; font-weight: 700; margin-top: 6px; }}
    .grid {{
      display: grid;
      grid-template-columns: 1.1fr 0.9fr;
      gap: 20px;
      align-items: start;
    }}
    .panel {{ padding: 24px; }}
    .panel h2 {{ margin: 0 0 14px; font-size: 20px; }}
    .hint {{ margin: -2px 0 20px; color: var(--muted); font-size: 14px; line-height: 1.6; }}
    form {{ display: grid; gap: 14px; }}
    .field {{ display: grid; gap: 8px; }}
    label {{ font-size: 13px; font-weight: 600; color: #3f3a35; }}
    input[type=\"text\"], input[type=\"file\"] {{
      width: 100%;
      border: 1px solid rgba(29,27,24,0.16);
      border-radius: 14px;
      background: rgba(255,255,255,0.94);
      padding: 13px 14px;
      font: inherit;
      color: var(--text);
      outline: none;
    }}
    input[type=\"text\"]:focus {{
      border-color: rgba(180,83,9,0.55);
      box-shadow: 0 0 0 4px rgba(180,83,9,0.12);
    }}
    .switches {{ display: flex; flex-wrap: wrap; gap: 10px; }}
    .switch {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 11px 14px;
      border-radius: 999px;
      background: rgba(255,255,255,0.76);
      border: 1px solid rgba(29,27,24,0.1);
      font-size: 14px;
    }}
    .actions {{ display: flex; flex-wrap: wrap; gap: 12px; align-items: center; margin-top: 8px; }}
    .button {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 10px;
      border: 0;
      border-radius: 16px;
      padding: 13px 18px;
      background: linear-gradient(135deg, var(--accent), #f59e0b);
      color: white;
      font-weight: 700;
      text-decoration: none;
      cursor: pointer;
      box-shadow: 0 14px 34px rgba(180,83,9,0.22);
    }}
    .button.secondary {{ background: linear-gradient(135deg, var(--accent-2), #14b8a6); box-shadow: 0 14px 34px rgba(15,118,110,0.22); }}
    .button.ghost {{
      background: rgba(255,255,255,0.7);
      color: var(--text);
      border: 1px solid rgba(29,27,24,0.14);
      box-shadow: none;
    }}
    .stack {{ display: grid; gap: 12px; }}
    .job {{
      display: grid;
      gap: 10px;
      padding: 16px;
      border-radius: 18px;
      background: rgba(255,255,255,0.8);
      border: 1px solid rgba(29,27,24,0.1);
    }}
    .job-top {{ display: flex; justify-content: space-between; gap: 10px; flex-wrap: wrap; align-items: baseline; }}
    .job-id {{ font-weight: 700; }}
    .status {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 6px 10px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      background: rgba(180,83,9,0.08);
      color: var(--accent);
    }}
    .status.done {{ background: rgba(15,118,110,0.1); color: var(--accent-2); }}
    .status.error {{ background: rgba(185,28,28,0.09); color: #b91c1c; }}
    .status.running {{ background: rgba(124,58,237,0.1); color: var(--accent-3); }}
    .meta-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px 12px; font-size: 13px; color: var(--muted); }}
    .meta-grid strong {{ color: var(--text); }}
    .message {{
      padding: 16px 18px;
      border-radius: 18px;
      background: rgba(15,118,110,0.08);
      border: 1px solid rgba(15,118,110,0.16);
      color: #135e56;
      margin-bottom: 18px;
    }}
    .message.error {{ background: rgba(185,28,28,0.08); border-color: rgba(185,28,28,0.18); color: #991b1b; }}
    .timeline {{ display: grid; gap: 10px; margin-top: 8px; }}
    .step {{
      display: grid;
      grid-template-columns: 24px 1fr;
      gap: 10px;
      align-items: start;
      padding: 12px 14px;
      border-radius: 14px;
      border: 1px solid rgba(29,27,24,0.08);
      background: rgba(255,255,255,0.7);
    }}
    .dot {{
      width: 12px;
      height: 12px;
      margin-top: 4px;
      border-radius: 50%;
      background: #c9b79d;
      box-shadow: 0 0 0 4px rgba(201,183,157,0.16);
    }}
    .step.done .dot {{ background: var(--accent-2); box-shadow: 0 0 0 4px rgba(15,118,110,0.12); }}
    .step.current .dot {{ background: var(--accent); box-shadow: 0 0 0 4px rgba(180,83,9,0.12); }}
    .step-title {{ font-weight: 700; margin-bottom: 3px; }}
    .step-desc {{ color: var(--muted); font-size: 13px; line-height: 1.5; }}
    pre {{
      overflow: auto;
      padding: 16px;
      border-radius: 18px;
      background: #111827;
      color: #e5e7eb;
      font-size: 12px;
      line-height: 1.6;
    }}
    code {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }}
    ul.files {{ margin: 0; padding-left: 18px; color: var(--text); }}
    ul.files li {{ margin: 4px 0; word-break: break-word; }}
    .footer-note {{ color: var(--muted); font-size: 13px; margin-top: 12px; line-height: 1.6; }}
    @media (max-width: 980px) {{
      .hero, .grid {{ grid-template-columns: 1fr; }}
    }}
    @media (max-width: 640px) {{
      .shell {{ padding: 18px 12px 40px; }}
      .hero-main, .hero-side, .panel {{ padding: 18px; }}
      .meta-grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
  {extra_head}
</head>
<body>
  <div class=\"shell\">{body}</div>
</body>
</html>""".encode("utf-8")


def escape(s: Any) -> str:
    return html.escape("" if s is None else str(s))


def render_status_badge(status: str) -> str:
    classes = {"completed": "done", "partial": "running", "extracted": "done", "error": "error", "processing": "running", "queued": "", "downloading": "running", "validating": "running", "analyzing": "running", "normalizing": "running", "converting": "running", "postprocessing": "running", "created": ""}
    return f'<span class="status {classes.get(status, "")}">{escape(status)}</span>'


def render_home(message: str | None = None, error: bool = False) -> bytes:
    jobs = store.list_jobs()
    recent_cards = []
    for job in jobs:
        root_link = f"/jobs/{job.job_id}"
        preview = " / ".join(job.extracted_preview or []) if job.extracted_preview else "暂无解压目录"
        recent_cards.append(f"""
        <div class=\"job\">
          <div class=\"job-top\">
            <div class=\"job-id\">{escape(job.job_id)}</div>
            {render_status_badge(job.status)}
          </div>
          <div class=\"meta-grid\">
            <div><strong>来源</strong><br>{escape(job.source_mode)}</div>
            <div><strong>arXiv</strong><br>{escape(job.arxiv_id or '未提供')}</div>
            <div><strong>Root</strong><br>{escape(job.root_tex or '待识别')}</div>
            <div><strong>创建时间</strong><br>{escape(job.created_at)}</div>
            <div><strong>解压预览</strong><br>{escape(preview)}</div>
          </div>
          <div class=\"actions\"><a class=\"button ghost\" href=\"{escape(root_link)}\">查看任务</a></div>
        </div>
        """)

    body = f"""
    <section class=\"hero\">
      <div class=\"card hero-main\">
        <div class=\"eyebrow\">Automated Paper Reader Workflow</div>
        <h1>arXiv 源码获取与安全解压</h1>
        <p class=\"lede\">这个 Web 应用只实现工作流的前五步：上传 arXiv 源码包或输入 arXiv ID，保存原始包，做安全检查，解压到独立任务目录，并把结果可视化展示出来。后续主文件识别和 LaTeXML 转换暂不执行。</p>
      </div>
      <aside class=\"card hero-side\">
        <div class=\"metric\"><div class=\"metric-label\">可执行入口</div><div class=\"metric-value\">python3 app.py</div></div>
        <div class=\"metric\"><div class=\"metric-label\">当前覆盖</div><div class=\"metric-value\">第 1 - 5 节</div></div>
        <div class=\"metric\"><div class=\"metric-label\">安全策略</div><div class=\"metric-value\">路径 / 体积 / 链接</div></div>
      </aside>
    </section>
    <section class=\"grid\">
      <div class=\"card panel\">
        <h2>创建任务</h2>
        <p class=\"hint\">支持两种入口：上传 `<source.tar.gz>` / `<paper.tar.gz>`，或者输入 arXiv ID 直接从 arXiv 拉取源码。提交后会自动落到独立 `jobs/<job_id>/` 目录。</p>
        {f'<div class="message {"error" if error else ""}">{escape(message)}</div>' if message else ''}
        <form method=\"post\" enctype=\"multipart/form-data\" action=\"/jobs\">
          <div class=\"field\">
            <label for=\"arxiv_id\">arXiv ID</label>
            <input id=\"arxiv_id\" name=\"arxiv_id\" type=\"text\" placeholder=\"2501.12345v2 或 hep-th/9901001\">
          </div>
          <div class=\"field\">
            <label for=\"source_file\">源码包上传</label>
            <input id=\"source_file\" name=\"source_file\" type=\"file\" accept=\".tar.gz,.tgz,.gz\">
          </div>
          <div class=\"switches\">
            <label class=\"switch\"><input type=\"radio\" name=\"source_mode\" value=\"upload\" checked> 上传优先</label>
            <label class=\"switch\"><input type=\"radio\" name=\"source_mode\" value=\"arxiv\"> arXiv 下载</label>
          </div>
          <div class=\"actions\">
            <button class=\"button\" type=\"submit\">创建并执行</button>
            <a class=\"button ghost\" href=\"/\">刷新列表</a>
          </div>
        </form>
        <div class=\"footer-note\">任务目录结构会自动生成：original / src / normalized / overlay / out / logs / meta。当前仅处理到安全解压，后续章节先不执行。</div>
      </div>
      <div class=\"card panel\">
        <h2>最近任务</h2>
        <div class=\"stack\">{''.join(recent_cards) if recent_cards else '<div class="hint">还没有任务。提交一个 arXiv ID 或上传源码包后，这里会显示任务状态和解压结果。</div>'}</div>
      </div>
    </section>
    """
    return html_page("arXiv Paper Workflow", body)


def render_job(job: JobState) -> bytes:
    stage_details = job.stage_details or []
    if not stage_details:
        stage_details = [
            {
                "title": "输入与解压",
                "status": "done" if job.status != "error" else "error",
                "detail": "原始包已保存并解压。",
            },
            {
                "title": "主文件识别",
                "status": "done" if job.root_tex else "skipped",
                "detail": job.root_tex or "未识别。",
            },
        ]

    timeline = []
    for entry in stage_details:
        status = str(entry.get("status", "done"))
        classes = ["step"]
        if status in {"done", "completed"}:
            classes.append("done")
        elif status in {"current", "running", "warning", "partial", "error"}:
            classes.append("current")
        timeline.append(
            f"<div class=\"{' '.join(classes)}\"><div class=\"dot\"></div><div><div class=\"step-title\">{escape(entry.get('title', 'Step'))}</div><div class=\"step-desc\">{escape(entry.get('detail', ''))}</div></div></div>"
        )

    def artifact_link(label: str, rel_path: str | None) -> str:
        if not rel_path:
            return f"<div><strong>{escape(label)}</strong><br>暂无</div>"
        encoded_path = urllib.parse.quote(rel_path)
        return f'<div><strong>{escape(label)}</strong><br><a class="button ghost" href="/jobs/{escape(job.job_id)}/artifact?path={encoded_path}">{escape(rel_path)}</a></div>'

    manifest = job.manifest or {}
    quality = job.quality or {}
    preflight = job.preflight or {}
    conversion = job.conversion or {}
    analysis = job.analysis or {}
    normalized = job.normalized or {}
    artifacts = job.artifacts or {}
    files = job.extracted_preview or []
    candidates = job.root_candidates or []

    file_list = "<li>暂无解压目录</li>" if not files else "".join(f"<li>{escape(item)}</li>" for item in files)
    candidate_list = (
        "".join(
            f"<li>{escape(item.get('path', ''))} · score={escape(item.get('score', 0))} · {escape(', '.join(item.get('reasons', [])) or 'no reasons')}</li>"
            for item in candidates[:6]
        )
        or "<li>暂无候选</li>"
    )
    manifest_summary = f"""
      <div class="meta-grid">
        <div><strong>Root</strong><br>{escape(job.root_tex or manifest.get('root_tex') or '未识别')}</div>
        <div><strong>Root 依据</strong><br>{escape(job.root_reason or manifest.get('root_reason') or 'heuristic')}</div>
        <div><strong>Documentclass</strong><br>{escape(manifest.get('documentclass') or '未知')}</div>
        <div><strong>Packages</strong><br>{escape(len(manifest.get('packages', [])))}</div>
        <div><strong>Bibliography</strong><br>{escape(', '.join(manifest.get('bib_files', [])[:4]) or '无')}</div>
        <div><strong>Images</strong><br>{escape(len(manifest.get('image_files', [])))}</div>
      </div>
    """

    refreshed = job.status not in {"completed", "error", "partial"}
    extra_head = '<meta http-equiv="refresh" content="5">' if refreshed else ''
    normalized_root = normalized.get("latexml_root")
    normalized_link = f"normalized/{normalized_root}" if normalized_root else None
    html_artifact = artifacts.get('html')
    open_html_button = ""
    if html_artifact:
      html_url = f"/jobs/{escape(job.job_id)}/view"
      open_html_button = f'<a class="button" href="{html_url}" target="_blank" rel="noopener">打开 HTML 论文</a>'
    combined_messages = "\n".join(
        (job.errors or [])
        + (job.warnings or [])
        + (analysis.get("warnings", []))
        + (analysis.get("errors", []))
    ) or "无"

    details = f"""
    <section class="hero">
      <div class="card hero-main">
        <div class="eyebrow">Job Detail</div>
        <h1>{escape(job.job_id)}</h1>
        <p class="lede">页面展示 root 识别、manifest、预处理、LaTeXML 输出和修复建议。任务会在后台推进，完成后保留 XML、HTML 和日志。</p>
      </div>
      <aside class="card hero-side">
        <div class="metric"><div class="metric-label">状态</div><div class="metric-value">{escape(job.status)}</div></div>
        <div class="metric"><div class="metric-label">来源</div><div class="metric-value">{escape(job.source_mode)}</div></div>
        <div class="metric"><div class="metric-label">质量分</div><div class="metric-value">{escape(quality.get('quality_score', 'n/a'))}</div></div>
      </aside>
    </section>
    <section class="grid">
      <div class="card panel">
        <h2>工作流可视化</h2>
        <div class="timeline">{''.join(timeline)}</div>
      </div>
      <div class="card panel">
        <h2>任务摘要</h2>
        <div class="meta-grid">
          <div><strong>arXiv ID</strong><br>{escape(job.arxiv_id or '未提供')}</div>
          <div><strong>原始文件</strong><br>{escape(job.original_name or '未上传')}</div>
          <div><strong>原始大小</strong><br>{escape(f'{job.archive_size} bytes' if job.archive_size is not None else '未知')}</div>
          <div><strong>成员数</strong><br>{escape(job.archive_members if job.archive_members is not None else '未知')}</div>
          <div><strong>总大小</strong><br>{escape(f'{job.archive_total_size} bytes' if job.archive_total_size is not None else '未知')}</div>
          <div><strong>提取文件数</strong><br>{escape(job.extract_count if job.extract_count is not None else '未知')}</div>
          <div><strong>预处理</strong><br>{escape('成功' if preflight.get('success') else '未完全成功')}</div>
          <div><strong>LaTeXML</strong><br>{escape('成功' if conversion.get('success') else '未完全成功')}</div>
        </div>
        <div class="actions" style="margin-top:16px;">
          <a class="button ghost" href="/">返回首页</a>
          <a class="button secondary" href="/jobs/{escape(job.job_id)}/meta">查看 JSON</a>
          {open_html_button}
        </div>
      </div>
    </section>
    <section class="grid" style="margin-top:20px;">
      <div class="card panel">
        <h2>Manifest 概览</h2>
        {manifest_summary}
      </div>
      <div class="card panel">
        <h2>候选根文件</h2>
        <ul class="files">{candidate_list}</ul>
      </div>
    </section>
    <section class="grid" style="margin-top:20px;">
      <div class="card panel">
        <h2>解压预览</h2>
        <ul class="files">{file_list}</ul>
      </div>
      <div class="card panel">
        <h2>输出与日志</h2>
        <div class="meta-grid">
          {artifact_link('XML', artifacts.get('xml'))}
          {artifact_link('HTML', artifacts.get('html'))}
          {artifact_link('LaTeXML Log', artifacts.get('latexml_log'))}
          {artifact_link('latexmlpost Log', artifacts.get('latexmlpost_log'))}
          {artifact_link('Normalized Root', normalized_link)}
          {artifact_link('Overlay Manifest', artifacts.get('overlay_manifest'))}
        </div>
      </div>
    </section>
    <section class="grid" style="margin-top:20px;">
      <div class="card panel">
        <h2>错误 / 警告</h2>
        <pre>{escape(combined_messages)}</pre>
      </div>
      <div class="card panel">
        <h2>质量评估</h2>
        <pre>{escape(json.dumps(quality or {}, indent=2, ensure_ascii=False))}</pre>
      </div>
    </section>
    """
    return html_page(f"Job {job.job_id}", details, extra_head=extra_head)


def render_json(job: JobState) -> bytes:
    return json.dumps(asdict(job), indent=2, ensure_ascii=False).encode("utf-8")


def _graphics_id_map_from_xml(xml_text: str) -> dict[str, str]:
  mapping: dict[str, str] = {}
  for match in re.finditer(r'<graphics\b[^>]*/?>', xml_text):
    tag = match.group(0)
    id_match = re.search(r'\bxml:id="([^"]+)"', tag)
    graphic_match = re.search(r'\bgraphic="([^"]+)"', tag)
    if id_match and graphic_match:
      mapping[id_match.group(1)] = graphic_match.group(1)
  return mapping


def _patch_html_empty_images(html_text: str, id_to_graphic: dict[str, str]) -> str:
  if not id_to_graphic:
    return html_text

  def replace_img_tag(match: re.Match[str]) -> str:
    tag = match.group(0)
    src_match = re.search(r'\bsrc="([^"]*)"', tag)
    id_match = re.search(r'\bid="([^"]+)"', tag)
    if not src_match or not id_match:
      return tag
    if src_match.group(1):
      return tag
    graphic_path = id_to_graphic.get(id_match.group(1))
    if not graphic_path:
      return tag
    view_path = f"normalized/{graphic_path}"
    lower_path = graphic_path.lower()
    if lower_path.endswith(".pdf") or lower_path.endswith(".eps"):
      classes = "ltx_graphics ltx_embedded_pdf"
      class_match = re.search(r'\bclass="([^"]+)"', tag)
      if class_match:
        classes = class_match.group(1)
      object_tag = (
        f'<object data="{html.escape(view_path, quote=True)}" '
        f'type="application/pdf" class="{html.escape(classes, quote=True)}" '
        'style="width:100%;min-height:320px;">'
        f'<a href="{html.escape(view_path, quote=True)}" target="_blank" rel="noopener">'
        '打开图像 PDF'
        '</a></object>'
      )
      return object_tag
    return tag.replace('src=""', f'src="{html.escape(view_path, quote=True)}"', 1)

  return re.sub(r'<img\b[^>]*>', replace_img_tag, html_text)


def _inject_view_base(html_text: str, job_id: str) -> str:
  base_href = f"/jobs/{job_id}/view/"
  base_tag = f'<base href="{html.escape(base_href, quote=True)}">'
  if re.search(r'<base\b', html_text, flags=re.IGNORECASE):
    return html_text
  return re.sub(r'(<head\b[^>]*>)', r'\1\n' + base_tag, html_text, count=1, flags=re.IGNORECASE)


def _inject_view_theme(html_text: str) -> str:
  if "data-paper-theme=\"injected\"" in html_text:
    return html_text
  theme_css = """
<style data-paper-theme="injected">
  :root {
    --paper-bg: #f4efe6;
    --paper-panel: #fffdf9;
    --paper-text: #22201c;
    --paper-muted: #5f5851;
    --paper-border: #ddd3c4;
    --paper-accent: #8f4e12;
    --paper-shadow: 0 20px 55px rgba(45, 29, 8, 0.12);
  }
  html, body {
    background: radial-gradient(circle at 8% -5%, #f9f4ea, #f4efe6 36%, #eee5d8 100%);
    color: var(--paper-text);
  }
  body {
    margin: 0;
    padding: 28px 14px 42px;
    font-family: "Microsoft YaHei", "微软雅黑", "Noto Sans CJK SC", "Source Han Sans SC", "PingFang SC", "SimHei", sans-serif;
    line-height: 1.8;
    letter-spacing: 0.01em;
    font-size: 1.08rem;
  }
  .ltx_page_main, .ltx_document {
    max-width: 980px;
    margin: 0 auto;
    background: var(--paper-panel);
    border: 1px solid var(--paper-border);
    border-radius: 20px;
    box-shadow: var(--paper-shadow);
    padding: 28px 34px;
  }
  .ltx_title_document {
    font-size: clamp(2.0rem, 2.6vw, 2.7rem);
    line-height: 1.18;
    margin-bottom: 0.55em;
    letter-spacing: -0.01em;
  }
  .ltx_abstract {
    background: #fcf8f2;
    border-left: 4px solid var(--paper-accent);
    padding: 14px 16px;
    border-radius: 10px;
  }
  .ltx_abstract h6,
  .ltx_abstract .ltx_title {
    margin-top: 0;
    color: var(--paper-accent);
    letter-spacing: 0.04em;
    text-transform: uppercase;
    font-size: 0.82rem;
  }
  .ltx_section > .ltx_title,
  .ltx_subsection > .ltx_title,
  .ltx_subsubsection > .ltx_title {
    color: #2f2a23;
    line-height: 1.28;
    margin-top: 1.45em;
    margin-bottom: 0.5em;
  }
  .ltx_para {
    margin: 0.6em 0 0.8em;
    color: var(--paper-text);
  }
  .ltx_para + .ltx_para {
    margin-top: 0.9em;
  }
  .ltx_p,
  p {
    overflow-wrap: anywhere;
  }
  .ltx_figure,
  .ltx_table {
    background: #fff;
    border: 1px solid #eadfce;
    border-radius: 14px;
    padding: 12px 12px 10px;
    margin: 1.3em auto;
  }
  .ltx_graphics,
  .ltx_figure img,
  .ltx_figure object {
    max-width: 100%;
    height: auto;
    border-radius: 8px;
    background: #f8f2e9;
  }
  .ltx_caption {
    color: var(--paper-muted);
    font-size: 0.95rem;
    margin-top: 0.55em;
  }
  .ltx_tabular table,
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.94rem;
  }
  .ltx_tabular td,
  .ltx_tabular th,
  td,
  th {
    border: 1px solid #e8dbc8;
    padding: 8px 10px;
    vertical-align: top;
  }
  .ltx_table .ltx_text[style*="font-size:70%"],
  .ltx_table .ltx_font_bold[style*="font-size:70%"],
  .ltx_table td,
  .ltx_table th {
    font-size: 0.95rem !important;
    line-height: 1.45;
  }
  .ltx_table .ltx_caption {
    display: block;
    position: relative !important;
    white-space: normal;
    margin-bottom: 0.8em;
    z-index: 3;
  }
  .ltx_transformed_outer {
    width: 100% !important;
    max-width: 100% !important;
    height: auto !important;
    display: block !important;
    overflow-x: auto;
    overflow-y: visible;
    vertical-align: baseline !important;
  }
  .ltx_transformed_inner {
    transform: none !important;
    position: static !important;
    display: inline-block !important;
  }
  .ltx_table .ltx_inline-block {
    max-width: 100%;
  }
  .ltx_td.cellcolor-patched,
  td.cellcolor-patched {
    background: #e8f7e8 !important;
  }
  pre,
  .ltx_verbatim {
    background: #fbf7f0;
    border: 1px solid #e7dac7;
    border-radius: 10px;
    padding: 10px 12px;
    overflow: auto;
    font-size: 0.88rem;
    line-height: 1.55;
  }
  .ltx_bibliography {
    font-size: 0.96rem;
  }
  a {
    color: #8b3f00;
    text-underline-offset: 2px;
  }
  @media (max-width: 900px) {
    body { padding: 10px 8px 22px; }
    .ltx_page_main, .ltx_document { padding: 16px 14px; border-radius: 12px; }
    .ltx_title_document { font-size: 1.7rem; }
  }
</style>
"""
  return re.sub(r'(</head>)', theme_css + r'\n\1', html_text, count=1, flags=re.IGNORECASE)


def _patch_cellcolor_artifacts(html_text: str) -> str:
  def patch_td(match: re.Match[str]) -> str:
    td_html = match.group(0)
    has_cellcolor = ("lightgreen" in td_html or "cellcolor" in td_html)
    if not has_cellcolor:
      return td_html
    open_match = re.match(r'<td\b([^>]*)>', td_html)
    if not open_match:
      return td_html
    cleaned_td = td_html
    cleaned_td = re.sub(r'<span class="ltx_ERROR undefined">\\cellcolor</span>', '', cleaned_td)
    cleaned_td = re.sub(r'(<span class="ltx_text"[^>]*>)\s*lightgreen\s*(</span>)', '', cleaned_td)
    cleaned_td = re.sub(r'(<span class="ltx_text"[^>]*>)\s*lightgreen\s*([-+]?\d+(?:\.\d+)?)\s*(</span>)', r'\1\2\3', cleaned_td)

    attrs = open_match.group(1)
    patched_attrs = attrs
    class_match = re.search(r'\bclass="([^"]*)"', attrs)
    if class_match:
      classes = class_match.group(1)
      if "cellcolor-patched" not in classes.split():
        patched_classes = (classes + " cellcolor-patched").strip()
        patched_attrs = patched_attrs.replace(class_match.group(0), f'class="{patched_classes}"', 1)
    else:
      patched_attrs = patched_attrs + ' class="cellcolor-patched"'
    open_tag = '<td' + patched_attrs + '>'
    return open_tag + cleaned_td[open_match.end():]

  html_text = re.sub(r'<td\b[^>]*>.*?</td>', patch_td, html_text, flags=re.DOTALL)
  html_text = re.sub(r'<span class="ltx_ERROR undefined">\\cellcolor</span>', '', html_text)
  html_text = re.sub(r'(<span class="ltx_text"[^>]*>)\s*lightgreen\s*(</span>)', '', html_text)
  html_text = re.sub(r'(<span class="ltx_text"[^>]*>)\s*lightgreen\s*([-+]?\d+(?:\.\d+)?)\s*(</span>)', r'\1\2\3', html_text)
  return html_text


def _inject_chat_feature(html_text: str) -> str:
  payload = """
<style>
  /* Base styles for the floating button and side panel */
  #ai-fab {
    position: absolute;
    display: none;
    z-index: 10000;
    padding: 8px 12px;
    background: #007bff;
    color: white;
    border-radius: 20px;
    cursor: pointer;
    font-size: 14px;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    border: none;
    font-family: inherit;
    transition: background 0.2s;
  }
  #ai-fab:hover { background: #0056b3; }
  
  #ai-sidebar {
    position: fixed;
    top: 0;
    right: 0;
    transform: translateX(100%);
    width: 380px;
    height: 100%;
    background: white;
    box-shadow: -4px 0 15px rgba(0,0,0,0.1);
    z-index: 10001;
    transition: transform 0.3s ease;
    display: flex;
    flex-direction: column;
    font-family: sans-serif;
  }
  #ai-sidebar.open {
    transform: translateX(0);
  }
  
  #ai-sidebar-resizer {
    position: absolute;
    top: 0;
    bottom: 0;
    left: -3px;
    width: 6px;
    cursor: ew-resize;
    z-index: 10002;
    background: transparent;
  }
  #ai-sidebar-resizer:hover, #ai-sidebar-resizer.dragging {
    background: rgba(0, 123, 255, 0.3);
  }
  
  #ai-sidebar-header {
    padding: 15px;
    background: #f8f9fa;
    border-bottom: 1px solid #ddd;
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-weight: bold;
    font-size: 16px;
  }
  #ai-sidebar-close {
    cursor: pointer;
    border: none;
    background: none;
    font-size: 20px;
    padding: 0;
    color: #555;
  }
  
  #ai-sidebar-settings {
    padding: 10px 15px;
    background: #f1f3f5;
    border-bottom: 1px solid #ddd;
    display: flex;
    flex-direction: column;
    gap: 8px;
    font-size: 13px;
  }
  #ai-sidebar-settings label {
    margin-right: 5px;
  }
  #ai-sidebar-settings input, #ai-sidebar-settings select {
    padding: 5px;
    border: 1px solid #ccc;
    border-radius: 4px;
    width: 100%;
    box-sizing: border-box;
    margin-top: 4px;
  }
  
  #ai-chat-content {
    flex-grow: 1;
    overflow-y: auto;
    padding: 15px;
    display: flex;
    flex-direction: column;
    gap: 15px;
  }
  
  .ai-msg {
    padding: 10px 15px;
    border-radius: 12px;
    max-width: 85%;
    word-wrap: break-word;
    font-size: 14px;
    line-height: 1.5;
  }
  .ai-msg.user {
    background: #007bff;
    color: white;
    align-self: flex-end;
    border-bottom-right-radius: 2px;
  }
  .ai-msg.bot {
    background: #f1f3f5;
    color: #333;
    align-self: flex-start;
    border-bottom-left-radius: 2px;
  }
  
  #ai-chat-input-area {
    padding: 15px;
    border-top: 1px solid #ddd;
    display: flex;
    gap: 10px;
  }
  #ai-chat-input-area input {
    flex-grow: 1;
    padding: 10px;
    border: 1px solid #ccc;
    border-radius: 6px;
    outline: none;
  }
  #ai-chat-input-area button {
    padding: 0 20px;
    background: #007bff;
    color: white;
    border: none;
    border-radius: 6px;
    cursor: pointer;
  }
  
  .ai-marker {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 20px;
    height: 20px;
    background: #007bff;
    color: white;
    border-radius: 50%;
    font-size: 12px;
    margin-left: 5px;
    cursor: pointer;
    vertical-align: middle;
    box-shadow: 0 2px 4px rgba(0,0,0,0.2);
    user-select: none;
  }
  
  /* Markdown elements styling inside chat */
  .ai-msg.bot pre {
    background: #e2e6ea;
    padding: 8px;
    border-radius: 4px;
    overflow-x: auto;
  }
  .ai-msg.bot code {
    background: #e2e6ea;
    padding: 2px 4px;
    border-radius: 3px;
    font-family: monospace;
  }
  .ai-msg.bot p { margin: 0 0 8px 0; }
  .ai-msg.bot p:last-child { margin-bottom: 0; }
  .ai-msg.bot ul, .ai-msg.bot ol { margin: 0 0 8px 0; padding-left: 20px; }
  .ai-msg.bot blockquote { border-left: 3px solid #ccc; margin: 0; padding-left: 10px; color: #555; }
</style>

<script src="https://cdn.jsdelivr.net/npm/marked@4.3.0/marked.min.js"></script>

<button id="ai-fab">💡 询问 AI</button>

<div id="ai-sidebar">
  <div id="ai-sidebar-resizer" title="左右拖动调整宽度"></div>
  <div id="ai-sidebar-header">
    <span>AI 论文助手</span>
    <div>
      <button id="ai-sidebar-settings-toggle" style="border:none;background:none;cursor:pointer;font-size:16px;" title="配置模型/API">⚙️</button>
      <button id="ai-sidebar-close">&times;</button>
    </div>
  </div>
  <div id="ai-sidebar-settings" style="display: none;">
    <div style="display:flex; justify-content:space-between; align-items:center;">
       <b>配置 (API Key仅存本地)</b>
       <span id="ai-settings-saved" style="color: green; display: none;">已保存</span>
    </div>
    <div>
      <label>选择模型:</label>
      <select id="ai-model">
        <option value="gpt-4o">GPT-4o (OpenAI)</option>
        <option value="gpt-4o-mini">GPT-4o-mini (OpenAI)</option>
        <option value="glm-4">GLM-4 (智谱)</option>
        <option value="deepseek-chat">deepseek-chat (DeepSeek)</option>
        <option value="claude-3-5-sonnet-20240620">Claude 3.5 (Anthropic)</option>
      </select>
    </div>
    <div>
      <label>API Key <a href="#" id="ai-api-help" style="color:#007bff; text-decoration:none;">(?)</a>:</label>
      <input type="password" id="ai-apikey" placeholder="sk-..." />
    </div>
  </div>
  <div id="ai-chat-content">
    <div class="ai-msg bot">你好！我是学术 AI 助手，请在左侧划出论文中的文本后向我提问。</div>
  </div>
  <div id="ai-chat-input-area">
    <input type="text" id="ai-chat-input" placeholder="输入你想问的问题..." />
    <button id="ai-chat-send">发送</button>
  </div>
</div>

<script>
(function() {
  const fab = document.getElementById('ai-fab');
  const sidebar = document.getElementById('ai-sidebar');
  const resizer = document.getElementById('ai-sidebar-resizer');
  const chatContent = document.getElementById('ai-chat-content');
  const chatInput = document.getElementById('ai-chat-input');
  const chatSend = document.getElementById('ai-chat-send');
  const sidebarClose = document.getElementById('ai-sidebar-close');
  const settingsToggle = document.getElementById('ai-sidebar-settings-toggle');
  const settingsPanel = document.getElementById('ai-sidebar-settings');
  
  const chatModel = document.getElementById('ai-model');
  const chatApiKey = document.getElementById('ai-apikey');
  const settingsSaved = document.getElementById('ai-settings-saved');

  /* ---------- Resize Logic ---------- */
  let isResizing = false;
  
  const savedWidth = localStorage.getItem('ai-sidebar-width');
  if (savedWidth) {
    sidebar.style.width = savedWidth + 'px';
  }

  resizer.addEventListener('mousedown', function(e) {
    isResizing = true;
    resizer.classList.add('dragging');
    document.body.style.userSelect = 'none';
    document.body.style.cursor = 'ew-resize';
  });

  document.addEventListener('mousemove', function(e) {
    if (!isResizing) return;
    let newWidth = window.innerWidth - e.clientX;
    const minWidth = 280;
    const maxWidth = window.innerWidth * 0.8;
    if (newWidth < minWidth) newWidth = minWidth;
    if (newWidth > maxWidth) newWidth = maxWidth;
    // Disable transition temporarily while dragging
    sidebar.style.transition = 'none';
    sidebar.style.width = newWidth + 'px';
  });

  document.addEventListener('mouseup', function(e) {
    if (isResizing) {
      isResizing = false;
      resizer.classList.remove('dragging');
      document.body.style.userSelect = '';
      document.body.style.cursor = '';
      // Restore transition
      sidebar.style.transition = 'transform 0.3s ease';
      localStorage.setItem('ai-sidebar-width', parseInt(sidebar.style.width, 10));
    }
  });
  /* ---------------------------------- */

  settingsToggle.addEventListener('click', function() {
    if (settingsPanel.style.display === 'none') {
      settingsPanel.style.display = 'flex';
    } else {
      settingsPanel.style.display = 'none';
    }
  });

  chatModel.value = localStorage.getItem('ai-model') || 'gpt-4o';
  chatApiKey.value = localStorage.getItem('ai-apikey') || '';

  function saveSettings() {
    localStorage.setItem('ai-model', chatModel.value);
    localStorage.setItem('ai-apikey', chatApiKey.value.trim());
    settingsSaved.style.display = 'inline';
    setTimeout(() => settingsSaved.style.display = 'none', 1500);
  }
  chatModel.addEventListener('change', saveSettings);
  chatApiKey.addEventListener('change', saveSettings);
  
  let currentSelectionParams = null;
  let activeChatId = null; 
  let chatHistories = {};
  
  // Storage key is based on current URL path
  const basePath = window.location.pathname.replace(new RegExp("/out/main\\\\.html$"), "").replace(new RegExp("/$"), "");
  const storageKey = 'ai-chats-' + basePath;
  const legacyKey = 'ai-chats-' + window.location.pathname;

  function loadChatHistory() {
    try {
      let saved = localStorage.getItem(storageKey);
      if (!saved && storageKey !== legacyKey) {
         saved = localStorage.getItem(legacyKey);
         if (saved) localStorage.setItem(storageKey, saved); // Migrate to the canonical key
      }
      
      if (saved) {
        chatHistories = JSON.parse(saved);
        // Naive re-anchoring of markers
        Object.keys(chatHistories).forEach(chatId => {
          const chatMeta = chatHistories[chatId];
          if (chatMeta && chatMeta.contextText) {
            // Find a text node matching the start of the context text
            const contextSnippet = chatMeta.contextText.substring(0, 15).trim();
            if(!contextSnippet) return;
            
            const marker = document.createElement('span');
            marker.className = 'ai-marker';
            marker.innerHTML = '💬';
            marker.title = '查看与AI的对话';
            marker.dataset.chatid = chatId;
            
            marker.addEventListener('click', function(e) {
              e.stopPropagation();
              activeChatId = this.dataset.chatid;
              chatContent.innerHTML = chatHistories[activeChatId].html;
              currentSelectionParams = null;
              sidebar.classList.add('open');
            });

            // More robust matching: search within block elements instead of strict TextNodes
            // This prevents failures when highlighted text contains inline tags (e.g. math, bold)
            const blocks = document.querySelectorAll('p, li, td, h1, h2, h3, h4, h5, h6, div.ltx_para');
            let placed = false;
            for (let i = 0; i < blocks.length; i++) {
              if (blocks[i].textContent.includes(contextSnippet)) {
                blocks[i].appendChild(marker);
                placed = true;
                break; // place only one
              }
            }
            
            // Fallback: If not found in a specific block, append to body so history isn't lost
            if (!placed) {
               marker.style.position = 'fixed';
               marker.style.bottom = '20px';
               marker.style.left = '20px';
               marker.style.zIndex = '9999';
               marker.title = '未找到原文本位置 - 查看对话';
               document.body.appendChild(marker);
            }
          }
        });
      }
    } catch(e) {
      console.error('载入历史对话失败', e);
    }
  }

  function saveChatHistory() {
    localStorage.setItem(storageKey, JSON.stringify(chatHistories));
  }

  // Load immediately
  if (document.readyState === 'loading') {
    window.addEventListener('DOMContentLoaded', loadChatHistory);
  } else {
    loadChatHistory();
  }

  document.getElementById('ai-api-help').addEventListener('click', function(e) {
    e.preventDefault();
    alert('你的 API Key 只会保存在你本地浏览器的 localStorage 中，并随每次对话请求发送到服务器进行调用，不会泄露给第三方。');
  });

  document.addEventListener('mouseup', function(e) {
    if (sidebar.contains(e.target) || fab.contains(e.target)) {
      return;
    }
    const selection = window.getSelection();
    const text = selection.toString().trim();
    
    if (text.length > 5) {
      const range = selection.getRangeAt(0);
      const rect = range.getBoundingClientRect();
      
      fab.style.top = (rect.top + window.scrollY - 30) + 'px';
      fab.style.left = (rect.left + window.scrollX + (rect.width/2) - 40) + 'px';
      fab.style.display = 'block';
      
      currentSelectionParams = { text: text, range: range.cloneRange() };
    } else {
      fab.style.display = 'none';
    }
  });

  fab.addEventListener('click', function() {
    fab.style.display = 'none';
    activeChatId = null;
    clearChat();
    appendMsg('bot', '你正基于以下原文向我提问：<br><br><i style="color:#666">"' + currentSelectionParams.text.substring(0, 100) + '..."</i><br><br>现在请输入你的问题。');
    sidebar.classList.add('open');
  });

  sidebarClose.addEventListener('click', function() {
    sidebar.classList.remove('open');
  });

  chatSend.addEventListener('click', sendQuestion);
  chatInput.addEventListener('keypress', function(e) {
    if (e.key === 'Enter') sendQuestion();
  });

  function clearChat() {
    chatContent.innerHTML = '';
  }

  function appendMsg(role, contentHTML) {
    const div = document.createElement('div');
    div.className = 'ai-msg ' + role;
    div.innerHTML = contentHTML;
    chatContent.appendChild(div);
    chatContent.scrollTop = chatContent.scrollHeight;
  }

  function sendQuestion() {
    const query = chatInput.value.trim();
    if (!query) return;
    
    chatInput.value = '';
    appendMsg('user', query);
    
    const contextText = currentSelectionParams ? currentSelectionParams.text : "";
    const apiKey = chatApiKey.value.trim();
    const model = chatModel.value;

    if (!apiKey) {
      appendMsg('bot', '<span style="color:#d9534f">⚠️ 请先在上方配置面板填入你的 API Key。</span>');
      return;
    }

    const paperMain = document.querySelector('.ltx_page_main');
    const fullPaperText = paperMain ? paperMain.innerText : document.body.innerText;
    
    fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        query: query, 
        context: contextText,
        full_paper: fullPaperText.substring(0, 100000), 
        apiKey: apiKey,
        model: model
      })
    })
    .then(r => r.json())
    .then(data => {
      // Use marked.js to parse Markdown reply to HTML if it's from bot
      const parsedHTML = marked.parse(data.reply);
      appendMsg('bot', parsedHTML);
      
      if (!activeChatId && currentSelectionParams) {
        activeChatId = 'chat_' + Date.now();
        chatHistories[activeChatId] = {
          html: chatContent.innerHTML,
          contextText: contextText
        };
        saveChatHistory();
        
        const marker = document.createElement('span');
        marker.className = 'ai-marker';
        marker.innerHTML = '💬';
        marker.title = '查看与AI的对话';
        marker.dataset.chatid = activeChatId;
        
        marker.addEventListener('click', function(e) {
          e.stopPropagation();
          activeChatId = this.dataset.chatid;
          chatContent.innerHTML = chatHistories[activeChatId].html;
          currentSelectionParams = null;
          sidebar.classList.add('open');
        });
        
        const range = currentSelectionParams.range;
        const endNode = range.endContainer;
        if(endNode.nodeType === 3) {
          const txt = endNode.splitText(range.endOffset);
          endNode.parentNode.insertBefore(marker, txt);
        } else {
          endNode.appendChild(marker);
        }
      } else if (activeChatId) {
        chatHistories[activeChatId].html = chatContent.innerHTML;
        saveChatHistory();
      }
    })
    .catch(err => {
      appendMsg('bot', '<span style="color:red">请求失败: ' + err.message + '</span>');
    });
  }
})();
</script>
"""
  if "</body>" in html_text:
    return html_text.replace("</body>", payload + "\n</body>")
  else:
    return html_text + payload


def render_view_main_html(job_id: str) -> bytes | None:
  html_path = resolve_job_artifact(job_id, "out/main.html")
  if html_path is None:
    return None
  html_text = html_path.read_text(encoding="utf-8", errors="replace")
  html_text = _inject_view_base(html_text, job_id)
  html_text = _inject_view_theme(html_text)
  xml_path = resolve_job_artifact(job_id, "out/main.xml")
  if xml_path is not None:
    xml_text = xml_path.read_text(encoding="utf-8", errors="replace")
    html_text = _patch_html_empty_images(html_text, _graphics_id_map_from_xml(xml_text))
  html_text = _patch_cellcolor_artifacts(html_text)
  html_text = _inject_chat_feature(html_text)
  return html_text.encode("utf-8")


def artifact_content_type(path: Path) -> str:
  guessed, _ = mimetypes.guess_type(path.name)
  return guessed or "application/octet-stream"


def resolve_job_artifact(job_id: str, relative_path: str) -> Path | None:
  job_root = (JOBS_DIR / job_id).resolve()
  candidate = (job_root / relative_path).resolve()
  if job_root not in candidate.parents and candidate != job_root:
    return None
  if not candidate.exists() or not candidate.is_file():
    return None
  return candidate


