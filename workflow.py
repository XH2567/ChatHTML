from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

USER_PERL_LIB = Path("/home/xings/perl5/lib/perl5")
USER_PERL_ARCH_LIB = USER_PERL_LIB / "x86_64-linux-gnu-thread-multi"
USER_LATEXML_BIN = Path("/home/xings/perl5/bin/latexml")
USER_LATEXMLPOST_BIN = Path("/home/xings/perl5/bin/latexmlpost")
REPO_LATEXML_PACKAGE_DIR = Path("/home/xings/LatexML/LaTeXML/lib/LaTeXML/Package")

DOCCLASS_RE = re.compile(r"\\documentclass(?:\[[^\]]*\])?\{([^}]*)\}")
USEPACKAGE_RE = re.compile(r"\\usepackage(?:\[[^\]]*\])?\{([^}]*)\}")
INPUT_RE = re.compile(r"\\(?:input|include)\{([^}]*)\}")
BIB_RE = re.compile(r"\\bibliography\{([^}]*)\}")
ADD_BIB_RE = re.compile(r"\\addbibresource(?:\[[^\]]*\])?\{([^}]*)\}")
GRAPHICS_RE = re.compile(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]*)\}")
TITLE_RE = re.compile(r"\\title(?:\[[^\]]*\])?\{([^}]*)\}")
AUTHOR_RE = re.compile(r"\\author(?:\[[^\]]*\])?\{([^}]*)\}")

TEXT_EXTENSIONS = {".tex", ".sty", ".cls", ".bst", ".bib", ".ltx", ".def", ".bbx", ".cbx"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".svg", ".eps", ".bmp", ".webp"}
TERMINAL_STATUSES = {"completed", "error"}


def _read_text(path: Path, limit: int = 1_000_000) -> str:
    try:
        data = path.read_bytes()
    except OSError:
        return ""
    return data[:limit].decode("utf-8", errors="replace")


def _split_csv_groups(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _flatten_pattern_matches(pattern: re.Pattern[str], text: str) -> list[str]:
    matches: list[str] = []
    for raw in pattern.findall(text):
        if isinstance(raw, tuple):
            raw = raw[0]
        for value in _split_csv_groups(raw):
            matches.append(value)
    return matches


def _safe_relpath(path: Path, base_dir: Path) -> str:
    return path.relative_to(base_dir).as_posix()


def _existing_tex_candidates(src_dir: Path) -> list[Path]:
    return sorted(p for p in src_dir.rglob("*.tex") if p.is_file())


def _resolve_token(src_dir: Path, token: str) -> Path | None:
    token = token.strip()
    if not token:
        return None
    candidates = [token]
    if not Path(token).suffix:
        candidates.append(token + ".tex")
    for candidate in candidates:
        candidate_path = src_dir / candidate
        if candidate_path.exists():
            return candidate_path
        for path in src_dir.rglob(Path(candidate).name):
            if path.exists() and path.name == Path(candidate).name:
                return path
    return None


def _discover_roots_from_readme(src_dir: Path) -> list[str]:
    readme = src_dir / "00README.json"
    if not readme.exists():
        return []
    try:
        payload = json.loads(readme.read_text(encoding="utf-8"))
    except Exception:
        return []
    roots: list[str] = []
    for source in payload.get("sources", []):
        if source.get("usage") == "toplevel" and source.get("filename"):
            roots.append(str(source["filename"]))
    return roots


def detect_root_tex(src_dir: Path) -> dict[str, Any]:
    tex_files = _existing_tex_candidates(src_dir)
    if not tex_files:
        raise FileNotFoundError("No .tex files found in extracted source tree")

    readme_roots = _discover_roots_from_readme(src_dir)
    incoming_refs: Counter[str] = Counter()
    file_features: dict[str, dict[str, Any]] = {}
    for tex_file in tex_files:
        text = _read_text(tex_file)
        refs = _flatten_pattern_matches(INPUT_RE, text) + _flatten_pattern_matches(re.compile(r"\\(?:input|include)\{([^}]*)\}"), text)
        for ref in refs:
            incoming_refs[ref] += 1
            incoming_refs[Path(ref).stem] += 1
            incoming_refs[Path(ref).name] += 1
        file_features[tex_file.as_posix()] = {
            "documentclass": bool(DOCCLASS_RE.search(text)),
            "begin_document": "\\begin{document}" in text,
            "title": bool(TITLE_RE.search(text)),
            "author": bool(AUTHOR_RE.search(text)),
            "bibliography": bool(BIB_RE.search(text) or ADD_BIB_RE.search(text)),
            "maketitle": "\\maketitle" in text,
            "line_count": text.count("\n") + 1 if text else 0,
            "package_count": len(_flatten_pattern_matches(USEPACKAGE_RE, text)),
            "input_count": len(_flatten_pattern_matches(INPUT_RE, text)),
            "referenced_by_others": 0,
            "contains_root_markers": 0,
        }

    candidates: list[dict[str, Any]] = []
    for tex_file in tex_files:
        text = _read_text(tex_file)
        basename = tex_file.name.lower()
        rel = _safe_relpath(tex_file, src_dir)
        score = 0
        reasons: list[str] = []
        if basename in {"main.tex", "paper.tex", "ms.tex", "root.tex", "arxiv.tex"}:
            score += 30
            reasons.append("common root filename")
        if any(Path(root).name == tex_file.name or Path(root) == Path(rel) for root in readme_roots):
            score += 120
            reasons.append("00README.json toplevel")
        if DOCCLASS_RE.search(text):
            score += 35
            reasons.append("contains documentclass")
        if "\\begin{document}" in text:
            score += 45
            reasons.append("contains begin document")
        if TITLE_RE.search(text):
            score += 8
            reasons.append("contains title")
        if AUTHOR_RE.search(text):
            score += 8
            reasons.append("contains author")
        if BIB_RE.search(text) or ADD_BIB_RE.search(text):
            score += 5
            reasons.append("contains bibliography directive")
        if "\\maketitle" in text:
            score += 5
            reasons.append("contains maketitle")
        if tex_file.parent.name.lower() in {"section", "sections", "appendix", "appendices"}:
            score -= 10
            reasons.append("located under section-like directory")
        if incoming_refs.get(tex_file.name) or incoming_refs.get(tex_file.stem) or incoming_refs.get(rel):
            score -= 15
            reasons.append("referenced from another file")
        if file_features[tex_file.as_posix()]["line_count"] < 12 and not DOCCLASS_RE.search(text):
            score -= 5
            reasons.append("very small non-root file")
        candidates.append({
            "path": rel,
            "score": score,
            "reasons": reasons,
            "line_count": file_features[tex_file.as_posix()]["line_count"],
        })

    candidates.sort(key=lambda item: (-item["score"], item["path"]))
    best = candidates[0]
    root_path = src_dir / best["path"]
    root_reason = ", ".join(best["reasons"]) if best["reasons"] else "heuristic score"
    if readme_roots:
        for root in readme_roots:
            resolved = _resolve_token(src_dir, root)
            if resolved:
                root_path = resolved
                root_reason = "00README.json toplevel"
                break

    return {
        "root_tex": _safe_relpath(root_path, src_dir),
        "root_reason": root_reason,
        "candidates": candidates[:10],
    }


def collect_manifest(src_dir: Path, root_tex: str) -> dict[str, Any]:
    root_path = src_dir / root_tex
    if not root_path.exists():
        root_path = _resolve_token(src_dir, root_tex) or root_path
    tex_files = [p for p in src_dir.rglob("*") if p.is_file() and p.suffix.lower() in TEXT_EXTENSIONS]
    image_files = [p for p in src_dir.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS]
    directories = [p.relative_to(src_dir).as_posix() for p in src_dir.rglob("*") if p.is_dir()]

    packages: set[str] = set()
    bib_files: set[str] = set()
    inputs: set[str] = set()
    graphics: set[str] = set()
    documentclass = None
    documentclass_options = None
    title = None
    author = None
    classes_by_file: dict[str, str] = {}
    package_counts: Counter[str] = Counter()

    for tex_file in tex_files:
        text = _read_text(tex_file)
        rel = _safe_relpath(tex_file, src_dir)
        if tex_file == root_path:
            class_match = DOCCLASS_RE.search(text)
            if class_match:
                documentclass = class_match.group(1).strip()
                classes_by_file[rel] = documentclass
            title_match = TITLE_RE.search(text)
            if title_match:
                title = title_match.group(1).strip()
            author_match = AUTHOR_RE.search(text)
            if author_match:
                author = author_match.group(1).strip()
        for pkg_group in _flatten_pattern_matches(USEPACKAGE_RE, text):
            for pkg in _split_csv_groups(pkg_group):
                packages.add(pkg)
                package_counts[pkg] += 1
        for bib_group in _flatten_pattern_matches(BIB_RE, text):
            for bib in _split_csv_groups(bib_group):
                bib_files.add(bib if bib.endswith(".bib") else f"{bib}.bib")
        for bib_group in _flatten_pattern_matches(ADD_BIB_RE, text):
            bib_files.add(bib_group)
        for input_group in _flatten_pattern_matches(INPUT_RE, text):
            inputs.add(input_group)
        for graphic_group in _flatten_pattern_matches(GRAPHICS_RE, text):
            graphics.add(graphic_group)

    discovered_bibs = sorted(str(p.relative_to(src_dir).as_posix()) for p in src_dir.rglob("*.bib"))
    discovered_styles = sorted(str(p.relative_to(src_dir).as_posix()) for p in src_dir.rglob("*.sty"))
    discovered_classes = sorted(str(p.relative_to(src_dir).as_posix()) for p in src_dir.rglob("*.cls"))

    return {
        "root_tex": root_tex,
        "documentclass": documentclass,
        "documentclass_options": documentclass_options,
        "title": title,
        "author": author,
        "packages": sorted(packages),
        "package_counts": dict(package_counts),
        "bib_files": sorted(bib_files or discovered_bibs),
        "inputs": sorted(inputs),
        "graphics": sorted(graphics),
        "tex_files": [str(p.relative_to(src_dir).as_posix()) for p in tex_files],
        "sty_files": discovered_styles,
        "cls_files": discovered_classes,
        "image_files": sorted(str(p.relative_to(src_dir).as_posix()) for p in image_files),
        "directory_count": len(directories),
        "file_count": len([p for p in src_dir.rglob("*") if p.is_file()]),
        "directories": directories,
    }


def copy_tree(src_dir: Path, normalized_dir: Path) -> None:
    if normalized_dir.exists():
        shutil.rmtree(normalized_dir)
    shutil.copytree(src_dir, normalized_dir)


def run_command(args: list[str], cwd: Path, log_path: Path, env: dict[str, str] | None = None, timeout: int | None = None) -> dict[str, Any]:
    started_at = time.monotonic()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    try:
        completed = subprocess.run(
            args,
            cwd=str(cwd),
            env=merged_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
            check=False,
        )
        output = completed.stdout or ""
        returncode = completed.returncode
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or "") + "\n[timeout]"
        returncode = 124
    log_text = [
        f"$ {' '.join(shlex.quote(str(arg)) for arg in args)}",
        f"cwd: {cwd}",
        f"returncode: {returncode}",
        "",
        output,
    ]
    log_path.write_text("\n".join(log_text), encoding="utf-8", errors="replace")
    return {
        "command": args,
        "returncode": returncode,
        "duration_seconds": round(time.monotonic() - started_at, 4),
        "log_path": str(log_path),
        "output": output,
        "success": returncode == 0,
    }


def run_preflight_tex_build(normalized_dir: Path, root_tex: str, logs_dir: Path) -> dict[str, Any]:
    root_path = normalized_dir / root_tex
    if not root_path.exists():
        root_path = _resolve_token(normalized_dir, root_tex) or root_path
    jobname = root_path.stem
    passes: list[dict[str, Any]] = []
    bibtex_ran = False
    env = {
        "TEXINPUTS": f"{normalized_dir}:{os.environ.get('TEXINPUTS', '')}",
    }
    first = run_command(
        ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "-file-line-error", root_path.name],
        cwd=normalized_dir,
        log_path=logs_dir / f"{jobname}.pdflatex.pass1.log",
        env=env,
    )
    passes.append(first)

    aux_path = normalized_dir / f"{jobname}.aux"
    tex_text = _read_text(root_path)
    need_bibtex = bool(re.search(r"\\bibliography\{", tex_text)) and any(p.suffix.lower() == ".bib" for p in normalized_dir.rglob("*.bib"))
    if aux_path.exists() and "\\bibdata" in _read_text(aux_path):
        need_bibtex = True

    if need_bibtex and shutil.which("bibtex"):
        bibtex_ran = True
        bibtex = run_command(
            ["bibtex", jobname],
            cwd=normalized_dir,
            log_path=logs_dir / f"{jobname}.bibtex.log",
        )
        passes.append(bibtex)

    for index in range(2, 4):
        later = run_command(
            ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "-file-line-error", root_path.name],
            cwd=normalized_dir,
            log_path=logs_dir / f"{jobname}.pdflatex.pass{index}.log",
            env=env,
        )
        passes.append(later)
        if not later["success"]:
            break

    generated = {
        "pdf": str((normalized_dir / f"{jobname}.pdf").relative_to(normalized_dir).as_posix()) if (normalized_dir / f"{jobname}.pdf").exists() else None,
        "aux": str(aux_path.relative_to(normalized_dir).as_posix()) if aux_path.exists() else None,
        "bbl": str((normalized_dir / f"{jobname}.bbl").relative_to(normalized_dir).as_posix()) if (normalized_dir / f"{jobname}.bbl").exists() else None,
        "toc": str((normalized_dir / f"{jobname}.toc").relative_to(normalized_dir).as_posix()) if (normalized_dir / f"{jobname}.toc").exists() else None,
    }
    success = passes[0]["success"] and all(pass_result["success"] for pass_result in passes[1:])
    return {
        "jobname": jobname,
        "root_tex": _safe_relpath(root_path, normalized_dir),
        "passes": passes,
        "bibtex_ran": bibtex_ran,
        "generated": generated,
        "success": success,
    }


def normalize_for_latexml(normalized_dir: Path, root_tex: str) -> dict[str, Any]:
    root_path = normalized_dir / root_tex
    if not root_path.exists():
        root_path = _resolve_token(normalized_dir, root_tex) or root_path
    jobname = root_path.stem
    source_text = _read_text(root_path)
    bbl_path = normalized_dir / f"{jobname}.bbl"
    normalized_root = root_path
    bib_replaced = False
    if bbl_path.exists() and re.search(r"\\bibliography\{[^}]*\}", source_text):
        normalized_root = normalized_dir / f"{root_path.stem}.latexml.tex"
        replacement = f"\\input{{{jobname}.bbl}}"
        patched = re.sub(r"\\bibliography\{[^}]*\}", lambda _match: replacement, source_text)
        normalized_root.write_text(patched, encoding="utf-8")
        bib_replaced = True
    return {
        "root_tex": _safe_relpath(root_path, normalized_dir),
        "latexml_root": _safe_relpath(normalized_root, normalized_dir),
        "bib_replaced": bib_replaced,
        "bbl_exists": bbl_path.exists(),
    }


def build_overlay_assets(overlay_dir: Path, manifest: dict[str, Any], root_tex: str) -> dict[str, Any]:
    overlay_dir.mkdir(parents=True, exist_ok=True)
    root_name = Path(root_tex).name
    root_stem = Path(root_tex).stem
    package_notes: list[dict[str, Any]] = []
    for package in manifest.get("packages", []):
        base_name = re.sub(r"_[0-9]{4,}$", "", package)
        candidate_path = REPO_LATEXML_PACKAGE_DIR / f"{base_name}.sty.ltxml"
        if base_name != package and candidate_path.exists():
            package_notes.append({"package": package, "fallback": base_name, "binding": str(candidate_path)})
    needs_tcolorbox_shim = "tcolorbox" in set(manifest.get("packages", []))
    stub_content = "# Auto-generated document overlay for this job.\n# Add document-specific shims or aliases here.\n1;\n"
    created_files: list[str] = []
    for name in {f"{root_name}.latexml", f"{root_stem}.latexml"}:
        path = overlay_dir / name
        path.write_text(stub_content, encoding="utf-8")
        created_files.append(path.name)
    if needs_tcolorbox_shim:
        tcolorbox_shim = """# -*- mode: Perl -*-
# Auto-generated local shim for papers that use tcolorbox-heavy preambles.
package LaTeXML::Package::Pool;
use strict;
use warnings;
use LaTeXML::Package;

DefMacro('\\tcbuselibrary{}', '');
DefMacro('\\tcbset{}', '');
DefMacro('\\newtcolorbox{}[]{}', '');

DefEnvironment('{configblock}{}', '#1 #body');
DefEnvironment('{promptblock}{}', '#1 #body');
DefEnvironment('{archblock}{}', '#1 #body');

1;
"""
        (overlay_dir / "tcolorbox.sty.ltxml").write_text(tcolorbox_shim, encoding="utf-8")
        created_files.append("tcolorbox.sty.ltxml")
        package_notes.append({"package": "tcolorbox", "fallback": "local overlay shim", "binding": str(overlay_dir / "tcolorbox.sty.ltxml")})
    overlay_manifest = {
        "root_tex": root_tex,
        "packages": manifest.get("packages", []),
        "package_notes": package_notes,
        "created_files": created_files,
    }
    (overlay_dir / "overlay_manifest.json").write_text(json.dumps(overlay_manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return overlay_manifest


def _resolve_latexml_binary(binary_name: str, fallback: Path) -> str | None:
    if fallback.exists():
        return str(fallback)
    return shutil.which(binary_name)


def run_latexml_pipeline(normalized_dir: Path, overlay_dir: Path, root_tex: str, out_dir: Path, logs_dir: Path) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    jobname = Path(root_tex).stem
    source_path = normalized_dir / root_tex
    if not source_path.exists():
        source_path = _resolve_token(normalized_dir, root_tex) or source_path
    xml_path = out_dir / "main.xml"
    html_path = out_dir / "main.html"
    latexml_bin = _resolve_latexml_binary("latexml", USER_LATEXML_BIN)
    latexmlpost_bin = _resolve_latexml_binary("latexmlpost", USER_LATEXMLPOST_BIN)
    perl_libs = [str(USER_PERL_LIB), str(USER_PERL_ARCH_LIB)]
    env = {
        "PERL5LIB": ":".join([lib for lib in perl_libs if Path(lib).exists()]),
    }
    if latexml_bin and latexmlpost_bin:
        env["PATH"] = f"{USER_LATEXML_BIN.parent}:{os.environ.get('PATH', '')}"

    latexml_result: dict[str, Any]
    latexmlpost_result: dict[str, Any]
    if not latexml_bin:
        latexml_result = {
            "success": False,
            "returncode": 127,
            "log_path": str(logs_dir / "main.latexml.log"),
            "output": "latexml executable not found",
        }
        (logs_dir / "main.latexml.log").write_text("latexml executable not found\n", encoding="utf-8")
    else:
        latexml_result = run_command(
            [
                latexml_bin,
                f"--destination={xml_path}",
                f"--path={normalized_dir}",
                f"--path={overlay_dir}",
                "--includestyles",
                "--verbose",
                source_path.name,
            ],
            cwd=normalized_dir,
            log_path=logs_dir / "main.latexml.log",
            env=env,
            timeout=300,
        )

    if not latexmlpost_bin or not xml_path.exists():
        latexmlpost_result = {
            "success": False,
            "returncode": 127,
            "log_path": str(logs_dir / "main.latexmlpost.log"),
            "output": "latexmlpost skipped because XML was not generated",
        }
        (logs_dir / "main.latexmlpost.log").write_text("latexmlpost skipped because XML was not generated\n", encoding="utf-8")
    else:
        latexmlpost_result = run_command(
            [
                latexmlpost_bin,
                f"--destination={html_path}",
                "--format=html5",
                f"--sourcedirectory={normalized_dir}",
                f"--path={overlay_dir}",
                "--verbose",
                str(xml_path),
            ],
            cwd=normalized_dir,
            log_path=logs_dir / "main.latexmlpost.log",
            env=env,
            timeout=120,
        )

    return {
        "latexml": latexml_result,
        "latexmlpost": latexmlpost_result,
        "artifacts": {
            "xml": f"out/{xml_path.name}" if xml_path.exists() else None,
            "xml_abs": str(xml_path),
            "html": f"out/{html_path.name}" if html_path.exists() else None,
            "html_abs": str(html_path),
            "latexml_log": f"logs/{(logs_dir / 'main.latexml.log').name}",
            "latexml_log_abs": str(logs_dir / "main.latexml.log"),
            "latexmlpost_log": f"logs/{(logs_dir / 'main.latexmlpost.log').name}",
            "latexmlpost_log_abs": str(logs_dir / "main.latexmlpost.log"),
        },
        "root_tex": root_tex,
        "jobname": jobname,
        "success": bool(latexml_result.get("success") and latexmlpost_result.get("success") and html_path.exists()),
        "source_path": _safe_relpath(source_path, normalized_dir),
    }


def analyze_latexml_logs(logs_dir: Path) -> dict[str, Any]:
    log_paths = [logs_dir / "main.latexml.log", logs_dir / "main.latexmlpost.log"]
    combined_text = "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in log_paths if path.exists())
    warnings = re.findall(r"^Warning:.*$", combined_text, flags=re.MULTILINE)
    errors = re.findall(r"^Error:.*$", combined_text, flags=re.MULTILINE)
    fallbacks = re.findall(r"^Info:fallback:([^\s]+).*?$", combined_text, flags=re.MULTILINE)
    unsupported_options = re.findall(r"^Info:unexpected:([^\s]+).*?$", combined_text, flags=re.MULTILINE)
    graphics_missing = [line for line in combined_text.splitlines() if "graphics" in line.lower() and "missing" in line.lower()]
    bibliography_issues = [line for line in combined_text.splitlines() if "bib" in line.lower() and ("error" in line.lower() or "expected" in line.lower())]
    repair_suggestions: list[dict[str, Any]] = []
    if fallbacks:
        repair_suggestions.append({"type": "template_fallback", "detail": fallbacks})
    if graphics_missing:
        repair_suggestions.append({"type": "graphics_paths", "detail": graphics_missing[:5]})
    if bibliography_issues:
        repair_suggestions.append({"type": "bibliography", "detail": bibliography_issues[:5]})
    if any("invalid-cctab" in line.lower() for line in combined_text.splitlines()):
        repair_suggestions.append({"type": "tcolorbox_shim", "detail": ["invalid-cctab", "expl3", "tcolorbox"]})
    return {
        "warnings": warnings,
        "errors": errors,
        "fallbacks": fallbacks,
        "unsupported_options": unsupported_options,
        "graphics_missing": graphics_missing,
        "bibliography_issues": bibliography_issues,
        "repair_suggestions": repair_suggestions,
    }


def evaluate_quality(manifest: dict[str, Any], conversion: dict[str, Any], analysis: dict[str, Any]) -> dict[str, Any]:
    html_path = conversion["artifacts"].get("html_abs")
    xml_path = conversion["artifacts"].get("xml_abs")
    score = 0.25
    if html_path:
        score += 0.3
    if xml_path:
        score += 0.2
    if conversion.get("latexml", {}).get("success"):
        score += 0.1
    if conversion.get("latexmlpost", {}).get("success"):
        score += 0.1
    warning_penalty = min(0.2, len(analysis.get("warnings", [])) * 0.02)
    error_penalty = min(0.3, len(analysis.get("errors", [])) * 0.05)
    score = max(0.0, min(1.0, score - warning_penalty - error_penalty))
    return {
        "quality_score": round(score, 3),
        "sections_detected": int((Path(html_path).read_text(encoding="utf-8", errors="replace").count("<section") if html_path and Path(html_path).exists() else 0)),
        "figures_detected": len(manifest.get("image_files", [])),
        "citations_detected": len(manifest.get("bib_files", [])),
        "fatal_errors": len(analysis.get("errors", [])),
        "warnings": len(analysis.get("warnings", [])),
        "output_generated": bool(html_path),
    }


def run_pipeline(src_dir: Path, normalized_dir: Path, overlay_dir: Path, out_dir: Path, logs_dir: Path) -> dict[str, Any]:
    root_info = detect_root_tex(src_dir)
    manifest = collect_manifest(src_dir, root_info["root_tex"])
    manifest["detected_root"] = root_info["root_tex"]
    manifest["root_reason"] = root_info["root_reason"]
    manifest["candidate_roots"] = root_info["candidates"]

    copy_tree(src_dir, normalized_dir)
    preflight = run_preflight_tex_build(normalized_dir, root_info["root_tex"], logs_dir)
    normalized = normalize_for_latexml(normalized_dir, root_info["root_tex"])
    overlay = build_overlay_assets(overlay_dir, manifest, root_info["root_tex"])
    conversion = run_latexml_pipeline(normalized_dir, overlay_dir, normalized["latexml_root"], out_dir, logs_dir)
    analysis = analyze_latexml_logs(logs_dir)
    quality = evaluate_quality({**manifest, "output_html": str(out_dir / "main.html")}, conversion, analysis)

    stage_details = [
        {
            "id": 1,
            "title": "输入与解压",
            "status": "done",
            "detail": "原始包已经保存并安全解压到 src/。",
        },
        {
            "id": 2,
            "title": "主文件识别",
            "status": "done",
            "detail": f"root_tex = {root_info['root_tex']} ({root_info['root_reason']})",
        },
        {
            "id": 3,
            "title": "资源清单",
            "status": "done",
            "detail": f"packages={len(manifest['packages'])}, bib_files={len(manifest['bib_files'])}, images={len(manifest['image_files'])}",
        },
        {
            "id": 4,
            "title": "TeX 预处理",
            "status": "done" if preflight["success"] else "warning",
            "detail": f"pdflatex passes={len(preflight['passes'])}, bibtex={preflight['bibtex_ran']}",
        },
        {
            "id": 5,
            "title": "Bibliography 归一化",
            "status": "done" if normalized["bib_replaced"] else "skipped",
            "detail": f"latexml_root = {normalized['latexml_root']}",
        },
        {
            "id": 6,
            "title": "Overlay 生成",
            "status": "done",
            "detail": f"overlay files={len(overlay['created_files'])}, package notes={len(overlay['package_notes'])}",
        },
        {
            "id": 7,
            "title": "LaTeXML 转换",
            "status": "done" if conversion["latexml"]["success"] else "error",
            "detail": f"XML={bool(conversion['artifacts'].get('xml'))}, HTML={bool(conversion['artifacts'].get('html'))}",
        },
        {
            "id": 8,
            "title": "日志分析",
            "status": "done",
            "detail": f"warnings={len(analysis['warnings'])}, errors={len(analysis['errors'])}",
        },
        {
            "id": 9,
            "title": "质量评估",
            "status": "done",
            "detail": f"quality={quality['quality_score']}",
        },
    ]

    return {
        "root": root_info,
        "manifest": manifest,
        "preflight": preflight,
        "normalized": normalized,
        "overlay": overlay,
        "conversion": conversion,
        "analysis": analysis,
        "quality": quality,
        "stage_details": stage_details,
        "success": bool(conversion["success"]),
    }
