from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


class PatchError(ValueError):
    pass


def _unify_newlines(s: str) -> str:
    return (s or "").replace("\r\n", "\n").replace("\r", "\n")


def _build_unified_diff(old: str, new: str, path: str) -> str:
    old_lines = _unify_newlines(old).splitlines(keepends=True)
    new_lines = _unify_newlines(new).splitlines(keepends=True)
    diff = difflib.unified_diff(
        old_lines, new_lines,
        fromfile=f"a{path}",
        tofile=f"b{path}",
        lineterm=""
    )
    return "\n".join(diff)


def apply_replace_block(
    text: str,
    *,
    start_marker: str,
    end_marker: str,
    replacement: str,
    insert_if_missing: bool = True,
    insert_before_marker: Optional[str] = None,
) -> Tuple[str, Dict[str, Any]]:
    """
    Replace content between start_marker and end_marker (inclusive).
    If markers missing and insert_if_missing:
      - if insert_before_marker exists in text: insert new block before it
      - else append at end
    """
    if not start_marker or not end_marker:
        raise PatchError("Missing start_marker or end_marker")

    src = _unify_newlines(text)
    start = src.find(start_marker)
    end = src.find(end_marker)

    if start != -1 and end != -1 and end >= start:
        end2 = end + len(end_marker)
        new_block = replacement
        if not new_block.endswith("\n"):
            new_block += "\n"
        out = src[:start] + new_block + src[end2:]
        return out, {"mode": "replace_block", "status": "replaced", "found": True}

    if not insert_if_missing:
        raise PatchError("Markers not found and insert_if_missing=false")

    # Insert new block
    block = replacement
    if not block.endswith("\n"):
        block += "\n"

    if insert_before_marker:
        idx = src.find(insert_before_marker)
        if idx != -1:
            out = src[:idx] + block + src[idx:]
            return out, {"mode": "replace_block", "status": "inserted", "found": False, "inserted_before": insert_before_marker}

    # Append
    out = src
    if not out.endswith("\n"):
        out += "\n"
    out += block
    return out, {"mode": "replace_block", "status": "appended", "found": False}


def _parse_unified_diff_paths(diff_text: str) -> Tuple[str, str]:
    """
    Very light parsing; used only for validation/UX.
    """
    lines = _unify_newlines(diff_text).splitlines()
    a = ""
    b = ""
    for ln in lines:
        if ln.startswith("--- "):
            a = ln[4:].strip()
        elif ln.startswith("+++ "):
            b = ln[4:].strip()
        if a and b:
            break
    return a, b


def apply_unified_diff_strict(old_text: str, diff_text: str) -> Tuple[str, Dict[str, Any]]:
    """
    Strict + safe-ish minimal unified diff applier...
    """

    # If the diff came as a single line (e.g. generated with lineterm="")
    # make it parseable by inserting newlines only at known header/hunk boundaries.
    if "\n" not in (diff_text or ""):
        # Insert newline before "+++ " and "@@ " only when they appear as headers
        diff_text = diff_text.replace("+++ ", "\n+++ ")
        diff_text = diff_text.replace("@@ ", "\n@@ ")
    old = _unify_newlines(old_text).splitlines(keepends=True)
    diff_lines = _unify_newlines(diff_text).splitlines(keepends=False)

    # locate hunks
    i = 0
    # skip headers until first hunk
    while i < len(diff_lines) and not diff_lines[i].startswith("@@"):
        i += 1
    if i >= len(diff_lines):
        raise PatchError("No hunks found in diff")

    new: list[str] = []
    old_idx = 0
    applied_hunks = 0

    hunk_re = re.compile(r"^@@\s*-(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?\s*@@")

    while i < len(diff_lines):
        if not diff_lines[i].startswith("@@"):
            i += 1
            continue

        m = hunk_re.match(diff_lines[i])
        if not m:
            raise PatchError(f"Invalid hunk header: {diff_lines[i]}")
        old_start = int(m.group(1))
        # old_count = int(m.group(2) or "1")
        i += 1

        # copy unchanged segment before hunk
        # diff old_start is 1-based line number
        target_old_idx = max(old_start - 1, 0)
        if target_old_idx < old_idx:
            raise PatchError("Overlapping hunks not supported")

        new.extend(old[old_idx:target_old_idx])
        old_idx = target_old_idx

        # apply hunk lines
        while i < len(diff_lines) and not diff_lines[i].startswith("@@"):
            ln = diff_lines[i]
            if ln.startswith("\\ No newline at end of file"):
                i += 1
                continue

            if ln.startswith(" "):
                # context
                expected = ln[1:] + "\n"
                if old_idx >= len(old) or old[old_idx] != expected:
                    # try without trailing newline (last line edge)
                    expected2 = ln[1:]
                    got = old[old_idx].rstrip("\n") if old_idx < len(old) else ""
                    raise PatchError(f"Context mismatch at line {old_idx+1}: expected '{expected2}' got '{got}'")
                new.append(old[old_idx])
                old_idx += 1

            elif ln.startswith("-"):
                # removal
                expected = ln[1:] + "\n"
                if old_idx >= len(old) or old[old_idx] != expected:
                    expected2 = ln[1:]
                    got = old[old_idx].rstrip("\n") if old_idx < len(old) else ""
                    raise PatchError(f"Delete mismatch at line {old_idx+1}: expected '{expected2}' got '{got}'")
                old_idx += 1

            elif ln.startswith("+"):
                # addition
                new.append(ln[1:] + "\n")

            else:
                # end of file or unexpected
                break

            i += 1

        applied_hunks += 1

    # copy rest
    new.extend(old[old_idx:])

    out = "".join(new)
    return out, {
        "mode": "unified_diff",
        "status": "applied",
        "hunks": applied_hunks,
        "headers": {"from_to": _parse_unified_diff_paths(diff_text)},
    }


def choose_mode_by_path(path: str, requested: Optional[str] = None) -> str:
    """
    Default rule:
      - config files => replace_block
      - other php => unified_diff (only if requested)
    """
    p = (path or "").lower()
    if requested in ("replace_block", "unified_diff"):
        return requested

    # defaults
    if p.endswith(("wp-config.php", ".htaccess", "php.ini", "user.ini")):
        return "replace_block"
    return "replace_block"  # safe default
