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

class JobStore:
    def __init__(self, jobs_dir: Path):
        self.jobs_dir = jobs_dir
        self.jobs_dir.mkdir(parents=True, exist_ok=True)

    def make_job_id(self, arxiv_id: str | None = None) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        suffix = uuid4().hex[:10]
        if arxiv_id:
            prefix = re.sub(r"[^A-Za-z0-9._-]+", "-", arxiv_id).strip(".-_")
            if prefix:
                return f"{prefix}-{timestamp}-{suffix}"
        return f"{timestamp}-{suffix}"

    def create(self, source_mode: str, arxiv_id: str | None = None) -> JobState:
        job_id = self.make_job_id(arxiv_id)
        ctx = ExtractionContext(self.jobs_dir / job_id, job_id)
        ctx.ensure()
        state = JobState(
            job_id=job_id,
            created_at=datetime.now(timezone.utc).isoformat(),
            status="created",
            source_mode=source_mode,
            arxiv_id=arxiv_id,
            errors=[],
            warnings=[],
            extracted_preview=[],
        )
        self.save(state)
        return state

    def load(self, job_id: str) -> JobState | None:
        job_json = self.jobs_dir / job_id / "meta" / "job.json"
        if not job_json.exists():
            return None
        with job_json.open("r", encoding="utf-8") as fh:
            raw = json.load(fh)
        return JobState(**raw)

    def save(self, state: JobState) -> None:
        ctx = ExtractionContext(self.jobs_dir / state.job_id, state.job_id)
        ctx.ensure()
        payload = asdict(state)
        with ctx.job_json_path().open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)

    def list_jobs(self) -> list[JobState]:
        jobs: list[JobState] = []
        for path in sorted(self.jobs_dir.iterdir(), reverse=True):
            if not path.is_dir():
                continue
            job = self.load(path.name)
            if job is not None:
                jobs.append(job)
        return jobs[:JOB_RETENTION_COUNT]


store = JobStore(JOBS_DIR)


