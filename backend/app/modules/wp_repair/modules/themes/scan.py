# app/modules/wp_repair/modules/themes/scan.py
from __future__ import annotations

import re
import posixpath
from stat import S_ISDIR
from typing import Any, Dict, Iterator, List, Optional

from app.modules.wp_repair.modules.sftp.connect import sftp_connect
from app.modules.wp_repair.db_audit import add_finding, flush_findings

_SKIP_DIRS = {".git", "node_modules", "vendor", "cache", "storage", ".sitefixer"}

_EXTS = (".php", ".phtml", ".php5", ".js")

# Patterns that often cause fatal errors or indicate compromise / bad loader code
_PATTERNS = [
    # very risky / often malware-ish
    ("eval_usage", "high", re.compile(r"\beval\s*\(", re.I)),
    ("base64_decode", "medium", re.compile(r"\bbase64_decode\s*\(", re.I)),
    ("gzinflate", "medium", re.compile(r"\bgzinflate\s*\(", re.I)),
    ("str_rot13", "low", re.compile(r"\bstr_rot13\s*\(", re.I)),
    ("preg_replace_e", "medium", re.compile(r"preg_replace\s*\(.*/e", re.I)),
    ("shell_exec", "high", re.compile(r"\bshell_exec\s*\(", re.I)),
    ("system_exec", "high", re.compile(r"\b(system|exec|passthru|popen|proc_open)\s*\(", re.I)),

    # remote load / include
    ("remote_url_fopen", "medium", re.compile(r"(file_get_contents|fopen)\s*\(\s*['\"]https?://", re.I)),
    ("curl_exec", "medium", re.compile(r"\bcurl_exec\s*\(", re.I)),
    ("include_url", "medium", re.compile(r"\b(include|require)(_once)?\s*\(\s*['\"]https?://", re.I)),

    # error suppression (can hide fatals)
    ("error_suppression", "low", re.compile(r"@\s*(include|require|file_get_contents|fopen)\b", re.I)),
    ("disable_errors", "low", re.compile(r"(error_reporting\s*\(\s*0\s*\)|ini_set\s*\(\s*['\"]display_errors['\"]\s*,\s*['\"]0['\"]\s*\))", re.I)),
]

def _iter_files(sftp, root: str, *, max_files: int, errors: List[dict]) -> Iterator[str]:
    emitted = 0

    def is_candidate(p: str) -> bool:
        return p.lower().endswith(_EXTS)

    def walk(p: str):
        nonlocal emitted
        if emitted >= max_files:
            return
        try:
            for a in sftp.listdir_attr(p):
                if emitted >= max_files:
                    return
                name = a.filename
                if name in _SKIP_DIRS:
                    continue
                full = posixpath.join(p, name)
                if S_ISDIR(a.st_mode):
                    yield from walk(full)
                else:
                    if is_candidate(full):
                        emitted += 1
                        yield full
        except Exception as e:
            errors.append({"path": p, "error": str(e)})

    try:
        st = sftp.stat(root)
        if S_ISDIR(st.st_mode):
            yield from walk(root)
        else:
            if is_candidate(root):
                emitted += 1
                yield root
    except Exception as e:
        errors.append({"path": root, "error": str(e)})


def theme_code_scan_apply(
    host: str,
    port: int,
    username: str,
    password: str,
    *,
    action_id: str,
    theme_root: str,          # wp-content/themes/<slug> OR a file inside
    max_files: int = 800,
    max_bytes: int = 250_000,
    batch_commit: int = 50,
) -> Dict[str, Any]:
    client = sftp_connect(host, port, username, password)
    sftp = client.open_sftp()

    errors: List[dict] = []
    counts = {
        "scanned": 0,
        "files_with_hits": 0,
        "hits_total": 0,
        "errors": 0,
    }

    pending = 0
    BATCH = max(1, int(batch_commit))

    def log_finding(path: str, severity: str, kind: str, detail: dict):
        nonlocal pending
        add_finding(action_id, path=path, severity=severity, kind=kind, detail_json=detail, commit=False)
        pending += 1
        if pending >= BATCH:
            flush_findings(commit=True)
            pending = 0

    try:
        seen_file_hit = set()

        for path in _iter_files(sftp, theme_root, max_files=max_files, errors=errors):
            try:
                with sftp.file(path, "rb") as f:
                    b = f.read(max_bytes)
                text = b.decode("utf-8", errors="ignore")

                file_hit_count = 0
                for kind, sev, rgx in _PATTERNS:
                    for m in rgx.finditer(text):
                        file_hit_count += 1
                        counts["hits_total"] += 1

                        # small snippet around match
                        s = max(0, m.start() - 80)
                        e = min(len(text), m.start() + 200)
                        snippet = text[s:e].replace("\n", " ")

                        log_finding(
                            path=path,
                            severity=sev,
                            kind=f"theme_{kind}",
                            detail={
                                "engine": "theme_scan",
                                "match": m.group(0)[:200],
                                "snippet": snippet[:400],
                                "max_bytes": max_bytes,
                            },
                        )

                if file_hit_count > 0:
                    seen_file_hit.add(path)

                counts["scanned"] += 1

            except Exception as e:
                counts["errors"] += 1
                log_finding(
                    path=path,
                    severity="low",
                    kind="theme_read_error",
                    detail={"engine": "theme_scan", "error": str(e)},
                )
                counts["scanned"] += 1

        counts["files_with_hits"] = len(seen_file_hit)

        if pending:
            flush_findings(commit=True)
            pending = 0

        return {"ok": True, "counts": counts, "errors": errors[:50]}

    finally:
        try:
            if pending:
                flush_findings(commit=True)
        except Exception:
            pass
        try:
            sftp.close()
        except Exception:
            pass
        try:
            client.close()
        except Exception:
            pass
