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


