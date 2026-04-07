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
WORKSPACE_ROOT = BASE_DIR.parent
JOBS_DIR = BASE_DIR / "jobs"
MAX_MEMBERS = 1000
MAX_TOTAL_BYTES = 250 * 1024 * 1024
MAX_MEMBER_BYTES = 100 * 1024 * 1024
MAX_EXTRACT_SECONDS = 20
JOB_RETENTION_COUNT = 20


ARXIV_ID_RE = re.compile(r"^(?:\d{4}\.\d{4,5}(?:v\d+)?|[a-z\-]+(?:\.[A-Z]{2})?\/\d{7}(?:v\d+)?)$", re.IGNORECASE)


@dataclass
class JobState:
    job_id: str
    created_at: str
    status: str
    source_mode: str
    arxiv_id: str | None = None
    original_name: str | None = None
    original_path: str | None = None
    archive_url: str | None = None
    archive_size: int | None = None
    archive_members: int | None = None
    archive_total_size: int | None = None
    extract_count: int | None = None
    extracted_preview: list[str] | None = None
    root_dir: str | None = None
    errors: list[str] | None = None
    warnings: list[str] | None = None
    duration_seconds: float | None = None
    root_tex: str | None = None
    root_reason: str | None = None
    root_candidates: list[dict[str, Any]] | None = None
    manifest: dict[str, Any] | None = None
    preflight: dict[str, Any] | None = None
    normalized: dict[str, Any] | None = None
    overlay: dict[str, Any] | None = None
    conversion: dict[str, Any] | None = None
    analysis: dict[str, Any] | None = None
    quality: dict[str, Any] | None = None
    stage_details: list[dict[str, Any]] | None = None
    artifacts: dict[str, str] | None = None


class JobError(Exception):
    pass


class ArchiveRejected(JobError):
    pass


class ExtractionContext:
    def __init__(self, root: Path, job_id: str):
        self.root = root
        self.job_id = job_id
        self.original_dir = root / "original"
        self.src_dir = root / "src"
        self.normalized_dir = root / "normalized"
        self.overlay_dir = root / "overlay"
        self.out_dir = root / "out"
        self.logs_dir = root / "logs"
        self.meta_dir = root / "meta"
        self.write_dirs = [
            self.original_dir,
            self.src_dir,
            self.normalized_dir,
            self.overlay_dir,
            self.out_dir,
            self.logs_dir,
            self.meta_dir,
        ]

    def ensure(self) -> None:
        for directory in self.write_dirs:
            directory.mkdir(parents=True, exist_ok=True)

    def job_json_path(self) -> Path:
        return self.meta_dir / "job.json"


