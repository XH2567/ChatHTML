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
from views import *
from worker import *

def decode_form_data(handler: BaseHTTPRequestHandler) -> cgi.FieldStorage:
    content_type = handler.headers.get("Content-Type", "")
    if "multipart/form-data" not in content_type:
        raise JobError("只接受 multipart/form-data 表单提交")
    length = int(handler.headers.get("Content-Length", "0"))
    environ = {
        "REQUEST_METHOD": "POST",
        "CONTENT_TYPE": content_type,
        "CONTENT_LENGTH": str(length),
    }
    return cgi.FieldStorage(fp=handler.rfile, headers=handler.headers, environ=environ, keep_blank_values=True)


class RequestHandler(BaseHTTPRequestHandler):
    server_version = "PaperWorkflow/0.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def send_html(self, status: int, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, status: int, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def redirect(self, location: str) -> None:
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Location", location)
        self.end_headers()

    def do_GET(self) -> None:
        if self.path == "/" or self.path.startswith("/?"):
            self.send_html(HTTPStatus.OK, render_home())
            return
        if self.path.startswith("/jobs/"):
            parsed = urllib.parse.urlparse(self.path)
            suffix = parsed.path[len("/jobs/"):]
            parts = [part for part in suffix.split("/") if part]

            if len(parts) >= 2 and parts[1] == "view":
                job_id = parts[0]
                job = store.load(job_id)
                if job is None:
                    self.send_error(HTTPStatus.NOT_FOUND, "job not found")
                    return
                rel_path = "/".join(parts[2:]) if len(parts) > 2 else "out/main.html"
                rel_path = urllib.parse.unquote(rel_path)
                if rel_path == "out/main.html":
                    body = render_view_main_html(job_id)
                    if body is None:
                        self.send_error(HTTPStatus.NOT_FOUND, "artifact not found")
                        return
                    self.send_response(HTTPStatus.OK)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                artifact = resolve_job_artifact(job_id, rel_path)
                if artifact is None:
                  fallback_candidates = [
                    f"out/{rel_path}",
                    f"normalized/{rel_path}",
                    f"src/{rel_path}",
                  ]
                  for candidate in fallback_candidates:
                    artifact = resolve_job_artifact(job_id, candidate)
                    if artifact is not None:
                      break
                if artifact is None:
                    self.send_error(HTTPStatus.NOT_FOUND, "artifact not found")
                    return
                body = artifact.read_bytes()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", artifact_content_type(artifact))
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            if suffix.endswith("/meta"):
                job_id = suffix[:-len("/meta")].rstrip("/")
                job = store.load(job_id)
                if job is None:
                    self.send_error(HTTPStatus.NOT_FOUND, "job not found")
                    return
                self.send_json(HTTPStatus.OK, render_json(job))
                return

            if suffix.endswith("/artifact"):
                job_id = suffix[:-len("/artifact")].rstrip("/")
                job = store.load(job_id)
                if job is None:
                    self.send_error(HTTPStatus.NOT_FOUND, "job not found")
                    return
                query = urllib.parse.parse_qs(parsed.query)
                rel_path = (query.get("path") or [""])[0]
                if not rel_path:
                    self.send_error(HTTPStatus.BAD_REQUEST, "missing path")
                    return
                artifact = resolve_job_artifact(job_id, rel_path)
                if artifact is None:
                    self.send_error(HTTPStatus.NOT_FOUND, "artifact not found")
                    return
                body = artifact.read_bytes()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", artifact_content_type(artifact))
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            job_id = suffix.rstrip("/")
            job = store.load(job_id)
            if job is None:
                self.send_error(HTTPStatus.NOT_FOUND, "job not found")
                return
            self.send_html(HTTPStatus.OK, render_job(job))
            return

        self.send_error(HTTPStatus.NOT_FOUND, "not found")

    def do_POST(self) -> None:
      if self.path == "/api/chat":
          import json
          content_length = int(self.headers.get("Content-Length", 0))
          post_data = self.rfile.read(content_length)
          try:
              req = json.loads(post_data.decode("utf-8"))
              context_text = req.get("context", "")
              query = req.get("query", "")
              full_paper = req.get("full_paper", "")
              model = req.get("model", "")
              api_key = req.get("apiKey", "")

              if not api_key:
                  raise Exception("未提供 API Key，请在上方设置面板中填入")

              api_url = "https://api.openai.com/v1/chat/completions"
              if "deepseek" in model:
                  api_url = "https://api.deepseek.com/chat/completions"
              elif "glm" in model:
                  api_url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"

              # 限制大小，构建真实请求内容
              system_prompt = f"你是一名为科研人员服务的高级学术 AI 助手。用户正在阅读下面这篇论文，请仔细阅读本文背景：\\n\\n{full_paper[:30000]}\\n\\n----------\\n这篇论文内容由于提取原因可能含有少量格式杂音，但这不影响理解。请根据给出的论文直接回答用户提问。"
              
              user_prompt = query
              if context_text:
                  user_prompt = f"用户当前正在关注并划选了论文里的这段话：\\n{context_text}\\n\\n用户提出的问题是：\\n{query}"

              import urllib.request
              headers = {
                  "Content-Type": "application/json",
                  "Authorization": f"Bearer {api_key}"
              }
              
              payload = {
                  "model": model,
                  "messages": [
                      {"role": "system", "content": system_prompt},
                      {"role": "user", "content": user_prompt}
                  ],
                  "temperature": 0.3
              }

              req_http = urllib.request.Request(
                  api_url, 
                  data=json.dumps(payload).encode("utf-8"), 
                  headers=headers, 
                  method="POST"
              )

              try:
                  with urllib.request.urlopen(req_http, timeout=60) as response:
                      resp_data = json.loads(response.read().decode("utf-8"))
                      ai_message = resp_data["choices"][0]["message"]["content"]
                      # 不再在后端做换行替换，而是直接返回原生的 Markdown 文本给前端
                      mock_reply = ai_message
              except urllib.error.HTTPError as e:
                  err_msg = e.read().decode("utf-8")
                  mock_reply = f"<span style='color:red'>API 调用失败 ({e.code}):<br>{err_msg}</span>"
              except Exception as api_e:
                  mock_reply = f"<span style='color:red'>网络异常或配置错误: {str(api_e)}</span>"
                
              resp = {"reply": mock_reply}
              self.send_response(HTTPStatus.OK)
              self.send_header("Content-Type", "application/json; charset=utf-8")
              self.end_headers()
              self.wfile.write(json.dumps(resp).encode("utf-8"))
          except Exception as e:
              self.send_error(HTTPStatus.BAD_REQUEST, str(e))
          return

      if self.path != "/jobs":
        self.send_error(HTTPStatus.NOT_FOUND, "not found")
        return
      try:
        form = decode_form_data(self)
        source_mode = (form.getfirst("source_mode") or "upload").strip()
        arxiv_id = (form.getfirst("arxiv_id") or "").strip()
        uploaded_data, uploaded_name = read_uploaded_file(form)
        if source_mode not in {"upload", "arxiv"}:
          raise JobError("不支持的 source_mode")
        if source_mode == "arxiv" and not arxiv_id:
          raise JobError("arXiv 下载模式下必须提供 arXiv ID")
        if source_mode == "upload" and uploaded_data is None and not arxiv_id:
          raise JobError("请上传源码包或切换到 arXiv ID 下载模式")
        if source_mode == "upload" and uploaded_data is None and arxiv_id:
          source_mode = "arxiv"
        if source_mode == "arxiv" and not ARXIV_ID_RE.match(arxiv_id):
          raise JobError("arXiv ID 格式不正确")

        state = store.create(source_mode=source_mode, arxiv_id=arxiv_id or None)
        state.status = "queued"
        store.save(state)

        if source_mode == "upload":
          archive_name = uploaded_name or "source.tar.gz"
          if not archive_name.endswith((".tar.gz", ".tgz", ".tar")):
            archive_name = archive_name + ".tar.gz"
          threading.Thread(
            target=process_job,
            args=(state, uploaded_data or b"", archive_name),
            daemon=True,
          ).start()
        else:
          def background_arxiv_job() -> None:
            try:
              state.status = "downloading"
              store.save(state)
              payload, archive_name, url = download_arxiv_source(arxiv_id)
              process_job(state, payload, archive_name, archive_url=url)
            except Exception as exc:
              state.status = "error"
              state.errors = (state.errors or []) + [str(exc)]
              store.save(state)

          threading.Thread(target=background_arxiv_job, daemon=True).start()

        self.redirect(f"/jobs/{state.job_id}")
      except JobError as exc:
        self.send_html(HTTPStatus.BAD_REQUEST, render_home(message=str(exc), error=True))
      except urllib.error.URLError as exc:
        self.send_html(HTTPStatus.BAD_REQUEST, render_home(message=f"arXiv 下载失败: {exc}", error=True))
      except Exception as exc:
        self.send_html(HTTPStatus.INTERNAL_SERVER_ERROR, render_home(message=f"处理失败: {exc}", error=True))


def main() -> None:
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", 8000), RequestHandler)
    print("Paper workflow app running at http://127.0.0.1:8000")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
