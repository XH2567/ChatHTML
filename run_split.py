import ast

with open("/home/xings/LatexML/webapp/app.py", "r", encoding="utf-8") as f:
    source = f.read()

# ... same script
import os
os.chdir("/home/xings/LatexML/webapp")
with open("app.py", "r", encoding="utf-8") as f:
    lines = f.readlines()
    
tree = ast.parse(source)

nodes_info = {}
for node in tree.body:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        nodes_info[node.name] = (node.lineno - 1, getattr(node, 'end_lineno'))
    elif isinstance(node, ast.Assign):
        for t in node.targets:
            if isinstance(t, ast.Name):
                nodes_info[t.id] = (node.lineno - 1, getattr(node, 'end_lineno'))

def get_code(names):
    out = []
    for name in names:
        if name in nodes_info:
            start, end = nodes_info[name]
            out.extend(lines[start:end])
            out.append("\n\n")
    return "".join(out)

COMMON_IMPORTS = """import cgi
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

"""

MODS = {
    "models.py": ["JOBS_DIR", "MAX_MEMBERS", "ARXIV_ID_RE", "JobState", "JobError", "ArchiveRejected", "ExtractionContext"],
    "store.py": ["JobStore", "store"],
    "views.py": [
        "html_page", "escape", "render_status_badge", "render_home", "render_job", 
        "render_json", "_graphics_id_map_from_xml", "_patch_html_empty_images", 
        "_inject_view_base", "_inject_view_theme", "_patch_cellcolor_artifacts", 
        "_inject_chat_feature", "render_view_main_html", "artifact_content_type", "resolve_job_artifact"
    ],
    "worker.py": [
        "read_uploaded_file", "download_arxiv_source", "safe_members", "extract_arxiv_source",
        "start_run_job_thread", "run_job_worker"
    ]
}

with open("bak_app.py", "w", encoding="utf-8") as f:
    f.write(source)

for mod, names in MODS.items():
    code = COMMON_IMPORTS
    if mod == "store.py":
        code += "from models import *\n\n"
    elif mod == "views.py":
        code += "from models import *\nfrom store import store, JobStore\n\n"
    elif mod == "worker.py":
        code += "from models import *\nfrom store import store, JobStore\n\n"
        
    code += get_code(names)
    with open(mod, "w", encoding="utf-8") as f:
        f.write(code)

APP_CODE = COMMON_IMPORTS + """
from models import *
from store import store, JobStore
from views import *
from worker import *

""" + get_code(["decode_form_data", "RequestHandler", "main"])

APP_CODE += "if __name__ == '__main__':\n    main()\n"

with open("app.py", "w", encoding="utf-8") as f:
    f.write(APP_CODE)
