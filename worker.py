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

def read_uploaded_file(form: cgi.FieldStorage) -> tuple[bytes | None, str | None]:
    item = form["source_file"] if "source_file" in form else None
    if item is None or not getattr(item, "filename", None):
        return None, None
    data = item.file.read()
    return data, os.path.basename(item.filename)


def download_arxiv_source(arxiv_id: str) -> tuple[bytes, str, str]:
    encoded = urllib.parse.quote(arxiv_id, safe="")
    url = f"https://arxiv.org/src/{encoded}"
    with urllib.request.urlopen(url, timeout=45) as response:
        payload = response.read()
        content_disposition = response.headers.get("Content-Disposition", "")
        filename = None
        match = re.search(r'filename="?([^";]+)"?', content_disposition)
        if match:
            filename = match.group(1)
        if not filename:
            filename = f"{arxiv_id.replace('/', '_')}.tar.gz"
    return payload, filename, url


def safe_members(tar: tarfile.TarFile) -> list[tarfile.TarInfo]:
    members = tar.getmembers()
    if len(members) > MAX_MEMBERS:
        raise ArchiveRejected(f"压缩包成员数超过限制: {len(members)} > {MAX_MEMBERS}")
    total = 0
    accepted: list[tarfile.TarInfo] = []
    for member in members:
        if member.isdev():
            raise ArchiveRejected(f"拒绝设备文件: {member.name}")
        if member.issym() or member.islnk():
            raise ArchiveRejected(f"拒绝符号链接或硬链接: {member.name}")
        if os.path.isabs(member.name):
            raise ArchiveRejected(f"拒绝绝对路径: {member.name}")
        normalized = Path(member.name)
        if any(part == ".." for part in normalized.parts):
            raise ArchiveRejected(f"拒绝路径穿越: {member.name}")
        if member.size < 0:
            raise ArchiveRejected(f"非法文件大小: {member.name}")
        if member.size > MAX_MEMBER_BYTES:
            raise ArchiveRejected(f"单文件过大: {member.name} ({member.size} bytes)")
        total += member.size
        if total > MAX_TOTAL_BYTES:
            raise ArchiveRejected(f"压缩包总大小超过限制: {total} > {MAX_TOTAL_BYTES}")
        accepted.append(member)
    return accepted


def extract_safely(archive_path: Path, dest_dir: Path) -> tuple[int, list[str], int]:
    start = time.monotonic()
    extracted_preview: list[str] = []
    dest_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive_path, mode="r:gz") as tar:
        members = safe_members(tar)
        count = 0
        for member in members:
            elapsed = time.monotonic() - start
            if elapsed > MAX_EXTRACT_SECONDS:
                raise ArchiveRejected(f"解压超时: {elapsed:.2f}s")
            target = (dest_dir / member.name).resolve()
            if dest_dir.resolve() not in target.parents and target != dest_dir.resolve():
                raise ArchiveRejected(f"目标路径越界: {member.name}")
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            if member.isfile():
                target.parent.mkdir(parents=True, exist_ok=True)
                extracted = tar.extractfile(member)
                if extracted is None:
                    raise ArchiveRejected(f"无法读取文件: {member.name}")
                with target.open("wb") as fh:
                    shutil.copyfileobj(extracted, fh)
                count += 1
                if len(extracted_preview) < 25:
                    extracted_preview.append(member.name)
            else:
                raise ArchiveRejected(f"拒绝未知条目类型: {member.name}")
    return count, extracted_preview, len(members)


def persist_original(payload: bytes, archive_name: str, ctx: ExtractionContext) -> Path:
    ctx.original_dir.mkdir(parents=True, exist_ok=True)
    archive_path = ctx.original_dir / archive_name
    with archive_path.open("wb") as fh:
        fh.write(payload)
    return archive_path


def process_job(state: JobState, payload: bytes, archive_name: str, archive_url: str | None = None) -> JobState:
  ctx = ExtractionContext(JOBS_DIR / state.job_id, state.job_id)
  ctx.ensure()
  started_at = time.monotonic()
  state.status = "processing"
  state.original_name = archive_name
  state.original_path = str(ctx.original_dir / archive_name)
  state.archive_url = archive_url
  state.archive_size = len(payload)
  state.errors = []
  state.warnings = []
  state.stage_details = []
  store.save(state)

  archive_path = persist_original(payload, archive_name, ctx)
  state.status = "validating"
  store.save(state)

  try:
    with tarfile.open(archive_path, mode="r:gz") as tar:
      members = tar.getmembers()
      state.archive_members = len(members)
      state.archive_total_size = sum(max(0, member.size) for member in members)
      store.save(state)

    state.status = "extracting"
    count, preview, _member_count = extract_safely(archive_path, ctx.src_dir)
    state.extract_count = count
    state.extracted_preview = preview
    state.root_dir = str(ctx.src_dir)
    store.save(state)

    state.status = "analyzing"
    store.save(state)
    pipeline = run_pipeline(ctx.src_dir, ctx.normalized_dir, ctx.overlay_dir, ctx.out_dir, ctx.logs_dir)
    state.root_tex = pipeline["root"]["root_tex"]
    state.root_reason = pipeline["root"]["root_reason"]
    state.root_candidates = pipeline["root"]["candidates"]
    state.manifest = pipeline["manifest"]
    state.preflight = pipeline["preflight"]
    state.normalized = pipeline["normalized"]
    state.overlay = pipeline["overlay"]
    state.conversion = pipeline["conversion"]
    state.analysis = pipeline["analysis"]
    state.quality = pipeline["quality"]
    state.stage_details = pipeline["stage_details"]
    state.artifacts = {
      "xml": pipeline["conversion"]["artifacts"].get("xml") or "",
      "html": pipeline["conversion"]["artifacts"].get("html") or "",
      "latexml_log": pipeline["conversion"]["artifacts"].get("latexml_log") or "",
      "latexmlpost_log": pipeline["conversion"]["artifacts"].get("latexmlpost_log") or "",
      "overlay_manifest": "overlay/overlay_manifest.json",
      "normalized_root": f"normalized/{pipeline['normalized']['latexml_root']}",
    }
    (ctx.meta_dir / "manifest.json").write_text(json.dumps(state.manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    (ctx.meta_dir / "pipeline.json").write_text(json.dumps(pipeline, indent=2, ensure_ascii=False), encoding="utf-8")
    state.status = "completed" if pipeline["conversion"]["success"] else "partial"
  except (ArchiveRejected, tarfile.TarError, OSError, UnicodeError) as exc:
    state.status = "error"
    state.errors = (state.errors or []) + [str(exc)]
  except Exception as exc:
    state.status = "error"
    state.errors = (state.errors or []) + [str(exc)]
  finally:
    state.duration_seconds = round(time.monotonic() - started_at, 4)
    store.save(state)
  return state



