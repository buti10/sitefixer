# /var/www/sitefixer/backend/app/modules/wp_repair/modules/plugins/recover.py
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import requests

from .preview import plugins_preview
from .fix import plugins_disable_plan
from ..sftp.connect import sftp_connect

# audit/actions.py liegt bei dir hier:
# app/modules/wp_repair/modules/audit/actions.py
try:
    from ..audit.actions import create_action, action_note, read_text_remote, write_text_remote
except Exception:
    # Fallback (falls action_note/read_* nicht exportiert sind)
    from ..audit.actions import create_action  # type: ignore
    action_note = None  # type: ignore
    read_text_remote = None  # type: ignore
    write_text_remote = None  # type: ignore


DEFAULT_EXCLUDE = {"akismet", "blocksy-companion"}  # später konfigurierbar


# ----------------------------
# HTTP Probe + Marker/Score
# ----------------------------
_BAD_MARKERS = [
    ("critical_error", "There has been a critical error"),
    ("fatal_error", "Fatal error"),
    ("parse_error", "Parse error"),
    ("db_down", "Error establishing a database connection"),
    ("maintenance", "Briefly unavailable for scheduled maintenance"),
    ("wp_debug", "WP_DEBUG"),
    ("permission_denied", "Permission denied"),
]

_USER_AGENT = "Sitefixer-WP-Repair/1.0"


@dataclass
class ProbeResult:
    ok: bool
    status_code: Optional[int]
    elapsed_ms: int
    error: Optional[str] = None
    bad_markers: Optional[List[Dict[str, Any]]] = None


def http_probe(url: str, timeout: int = 10, max_body: int = 200_000) -> ProbeResult:
    """
    ok == True bedeutet: HTTP 2xx/3xx UND keine "bad markers".
    """
    t0 = time.time()
    try:
        r = requests.get(
            url,
            timeout=timeout,
            allow_redirects=True,
            headers={"User-Agent": _USER_AGENT},
        )
        elapsed = int((time.time() - t0) * 1000)
        status_ok = 200 <= (r.status_code or 0) < 400

        text = (r.text or "")[:max_body]
        bad: List[Dict[str, Any]] = []

        # wp-login/wp-admin Marker gilt als alive (auch wenn z.B. 403/401)
        if not status_ok and text and ("wp-login.php" in text or "wp-admin" in text):
            status_ok = True

        low = text.lower()

        for key, needle in _BAD_MARKERS:
            if needle.lower() in low:
                # mini snippet
                idx = low.find(needle.lower())
                start = max(0, idx - 80)
                end = min(len(text), idx + len(needle) + 120)
                bad.append(
                    {
                        "key": key,
                        "needle": needle,
                        "snippet": text[start:end].replace("\n", " ")[:260],
                    }
                )

        ok = bool(status_ok) and (len(bad) == 0)
        return ProbeResult(ok=ok, status_code=r.status_code, elapsed_ms=elapsed, error=None, bad_markers=bad)

    except Exception as e:
        elapsed = int((time.time() - t0) * 1000)
        return ProbeResult(ok=False, status_code=None, elapsed_ms=elapsed, error=str(e), bad_markers=[])


def _probe_score(p: ProbeResult) -> int:
    """
    0..100, höher = besser.
    """
    if p.error:
        return 0

    score = 0
    sc = p.status_code or 0

    # Status Gewichtung
    if 200 <= sc < 300:
        score += 60
    elif 300 <= sc < 400:
        score += 55
    elif 400 <= sc < 500:
        score += 30
    elif 500 <= sc < 600:
        score += 10
    else:
        score += 0

    # Marker Abzug
    bad = p.bad_markers or []
    # harte Marker stärker abziehen
    hard_keys = {"critical_error", "fatal_error", "parse_error", "db_down", "maintenance"}
    for m in bad:
        if m.get("key") in hard_keys:
            score -= 20
        else:
            score -= 8

    # Response time Bonus/Malus (sehr grob)
    if p.elapsed_ms <= 1200:
        score += 10
    elif p.elapsed_ms <= 2500:
        score += 5
    elif p.elapsed_ms >= 8000:
        score -= 10

    return max(0, min(100, score))


# ----------------------------
# Batching + Candidate Selection
# ----------------------------
def _make_batches(slugs: List[str], batch_size: int, max_total: int) -> List[List[str]]:
    batch_size = max(1, int(batch_size or 1))
    max_total = max(1, int(max_total or batch_size))
    slugs = slugs[:max_total]
    return [slugs[i : i + batch_size] for i in range(0, len(slugs), batch_size)]


# Heuristik-Kategorien (für conflict_suspects)
_SUSPECT_CATEGORIES: List[Tuple[str, List[str], int]] = [
    ("builder", ["elementor", "brizy", "wpbakery", "divi", "oxygen", "beaver", "siteorigin"], 2),
    ("forms", ["form", "contact", "gravity", "ninja", "wpforms", "forminator"], 3),
    ("payments", ["stripe", "paypal", "payments", "klarna", "mollie", "checkout"], 6),
    ("analytics/ads", ["tiktok", "pixel", "ads", "analytics", "gtm", "facebook", "meta", "klaviyo", "google-listings"], 7),
    ("cache/optimize", ["cache", "optimiz", "minify", "autoptimize", "litespeed", "wprocket"], 5),
]


def _suspect_score_for_slug(slug: str) -> Tuple[int, str]:
    s = (slug or "").lower()
    for cat, needles, prio in _SUSPECT_CATEGORIES:
        for n in needles:
            if n in s:
                return (50, prio), f"suspect_category={cat}"
    # name-only heuristic: contains typical risky words
    for n in ["optimiz", "security", "firewall", "redirect", "inject", "seo", "smtp"]:
        if n in s:
            return (50, 50), "suspect_category=name_heuristic"
    return (0, 99), "not_suspect"


def recover_preview(
    *,
    host: str,
    port: int,
    username: str,
    password: str,
    wp_root: str,
    domain: str,
    batch_size: int = 2,
    max_disable_total: int = 10,
    exclude: Optional[List[str]] = None,
    mode: str = "risky_only",  # risky_only | conflict_suspects
    include_statuses: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    READ-ONLY:
    - risky_only: nur Plugins mit Status != ok (oder in include_statuses)
    - conflict_suspects: ok-Plugins, die als typische Konfliktquellen gelten (Heuristik)
    """
    exclude_set = set(DEFAULT_EXCLUDE)
    if exclude:
        exclude_set |= set(exclude)

    statuses = set(
        include_statuses
        or ["header_not_found", "missing_main_file", "unreadable", "empty_dir", "unreadable_main_file"]
    )

    inv = plugins_preview(host, port, username, password, wp_root, include_ok=True)
    if not inv.get("ok"):
        return {"ok": False, "error": "preview_failed", "detail": inv}

    plugins = inv.get("plugins", []) or []

    excluded: List[Dict[str, str]] = []
    candidates_detail: List[Dict[str, Any]] = []

    candidates: List[Tuple[str, Tuple[int, int], str, str]] = []
    # (slug, score_tuple, status, why)

    for p in plugins:
        slug = p.get("slug")
        st = p.get("status")
        if not slug:
            continue

        if slug in exclude_set:
            excluded.append({"slug": slug, "reason": "excluded"})
            continue

        if mode == "risky_only":
            if st in statuses:
                # Priorisierung: status-based
                prio = {
                    "header_not_found": (60, 0),
                    "unreadable_main_file": (60, 1),
                    "missing_main_file": (60, 2),
                    "unreadable": (60, 3),
                    "empty_dir": (60, 4),
                }.get(st, (40, 99))
                candidates.append((slug, prio, st, f"status={st}"))
                candidates_detail.append(
                    {"slug": slug, "status": st, "category": "risky", "score": list(prio), "why": f"status={st}"}
                )
            else:
                excluded.append({"slug": slug, "reason": f"status={st}"})
            continue

        if mode == "conflict_suspects":
            # ok-Plugins sind hier relevant, aber nur wenn "suspect"
            if st != "ok":
                # non-ok wird hier auch akzeptiert, aber mit hoher prio
                prio = (80, 0)
                candidates.append((slug, prio, st, f"non_ok_status={st}"))
                candidates_detail.append(
                    {"slug": slug, "status": st, "category": "non_ok", "score": list(prio), "why": f"non_ok_status={st}"}
                )
                continue

            prio, why = _suspect_score_for_slug(slug)
            if prio[0] > 0:
                candidates.append((slug, prio, st, why))
                # extract category
                cat = why.split("=", 1)[1] if "=" in why else "suspect"
                candidates_detail.append(
                    {"slug": slug, "status": st, "category": cat, "score": list(prio), "why": why}
                )
            else:
                excluded.append({"slug": slug, "reason": "ok_not_suspect"})
            continue

        # default fallback
        excluded.append({"slug": slug, "reason": "mode_unknown"})

    # Sort: score_tuple + slug
    candidates.sort(key=lambda x: (x[1][0] * -1, x[1][1], x[0].lower()))
    ordered = [s for s, _prio, _st, _why in candidates]
    batches = _make_batches(ordered, batch_size=batch_size, max_total=max_disable_total)

    probe = http_probe(domain, timeout=10)
    return {
        "ok": True,
        "mode": mode if mode in ("risky_only", "conflict_suspects") else "risky_only",
        "domain": domain,
        "probe_before": probe.__dict__,
        "probe_before_score": _probe_score(probe),
        "excluded": excluded,
        "ordered_candidates": ordered,
        "candidates_detail": candidates_detail,
        "batches": batches,
        "limits": {"batch_size": batch_size, "max_disable_total": max_disable_total},
    }


# ----------------------------
# Disable (rename) with audit meta moved[]
# ----------------------------
def _append_moved_to_action_meta(
    *,
    host: str,
    port: int,
    username: str,
    password: str,
    meta_path: str,
    moved: List[Dict[str, str]],
    note: Optional[str] = None,
) -> None:
    if (read_text_remote is None) or (write_text_remote is None):
        # if not available, we can't write meta here
        return
    raw = read_text_remote(host, port, username, password, meta_path)
    meta = json.loads(raw) if raw else {}
    meta.setdefault("moved", [])
    meta["moved"].extend([{"src": m["src"], "dst": m["dst"]} for m in moved])
    if note:
        meta.setdefault("notes", []).append(note)
    write_text_remote(host, port, username, password, meta_path, json.dumps(meta, ensure_ascii=False, indent=2))


def _note(action_id: str, msg: str) -> None:
    if action_note:
        try:
            action_note(action_id, msg)
            return
        except Exception:
            pass


def _disable_batch(
    *,
    host: str,
    port: int,
    username: str,
    password: str,
    wp_root: str,
    slugs: List[str],
    action_id: str,
    meta_path: str,
    max_disable: int,
) -> Dict[str, Any]:
    """
    Uses plugins_disable_plan() and performs SFTP renames.
    Writes moved[] into action meta.
    """
    plan_res = plugins_disable_plan(wp_root, slugs, action_id=action_id, max_disable=max_disable)
    if not plan_res.get("ok"):
        return {"ok": False, "error": plan_res.get("error") or "plan_failed", "detail": plan_res}

    plan = plan_res.get("plan") or []

    client = sftp_connect(host, port, username, password)
    sftp = client.open_sftp()
    disabled: List[Dict[str, str]] = []
    skipped: List[Dict[str, str]] = []
    errors: List[Dict[str, str]] = []
    try:
        for it in plan:
            slug = it.get("slug")
            src = it.get("src")
            dst = it.get("dst")
            if not slug or not src or not dst:
                continue

            try:
                sftp.stat(src)
            except Exception as e:
                skipped.append({"slug": slug, "src": src, "dst": dst, "reason": f"src_missing: {e}"})
                continue

            try:
                sftp.rename(src, dst)
                disabled.append({"slug": slug, "src": src, "dst": dst})
            except Exception as e:
                errors.append({"slug": slug, "src": src, "dst": dst, "error": str(e)})

        if disabled:
            _append_moved_to_action_meta(
                host=host, port=port, username=username, password=password,
                meta_path=meta_path,
                moved=disabled,
                note=f"batch moved={len(disabled)} skipped={len(skipped)} errors={len(errors)}",
            )

        return {"ok": True, "disabled": disabled, "skipped": skipped, "errors": errors}

    finally:
        try:
            sftp.close()
        except Exception:
            pass
        try:
            client.close()
        except Exception:
            pass


def recover_apply(
    *,
    host: str,
    port: int,
    username: str,
    password: str,
    wp_root: str,
    domain: str,
    batch_size: int = 2,
    max_disable_total: int = 10,
    verify_timeout: int = 10,
    exclude: Optional[List[str]] = None,
    mode: str = "risky_only",
    force: bool = False,
) -> Dict[str, Any]:
    """
    WRITE: disable batches until improved/healthy OR exhausted.
    Adds score_before/after + delta + verdict.
    """
    plan = recover_preview(
        host=host, port=port, username=username, password=password,
        wp_root=wp_root, domain=domain,
        batch_size=batch_size, max_disable_total=max_disable_total,
        exclude=exclude,
        mode=mode,
    )
    if not plan.get("ok"):
        return plan

    probe_before = ProbeResult(**plan["probe_before"])
    score_before = plan.get("probe_before_score", _probe_score(probe_before))

    # If already healthy and not forced, do not change anything
    if (not force) and probe_before.ok:
        return {
            "ok": True,
            "recovered": False,
            "verdict": "already_healthy",
            "score_before": score_before,
            "score_after": score_before,
            "delta": 0,
            "probe_before": plan["probe_before"],
            "probe_after": None,
            "applied_batches": [],
            "plan": {
                "mode": plan.get("mode"),
                "excluded": plan.get("excluded", []),
                "ordered_candidates": plan.get("ordered_candidates", []),
                "batches": plan.get("batches", []),
            },
            "note": "Site looked healthy before apply; use force=true to still run suspect disables.",
        }

    action = create_action(
        host=host, port=port, username=username, password=password,
        wp_root=wp_root,
        fix_id="plugins_recover",
        context={
            "domain": domain,
            "batch_size": batch_size,
            "max_disable_total": max_disable_total,
            "verify_timeout": verify_timeout,
            "exclude": exclude or [],
            "mode": plan.get("mode"),
            "ordered_candidates": plan.get("ordered_candidates", []),
            "batches": plan.get("batches", []),
        },
    )
    action_id = action["action_id"]
    meta_path = action.get("meta_path")

    _note(action_id, f"probe_before: {plan['probe_before']} score={score_before}")

    recovered = False
    probe_after: Optional[Dict[str, Any]] = None
    score_after: Optional[int] = None
    applied_batches: List[Dict[str, Any]] = []

    batches = plan.get("batches") or []
    for idx, batch in enumerate(batches, start=1):
        # disable
        res = _disable_batch(
            host=host, port=port, username=username, password=password,
            wp_root=wp_root,
            slugs=batch,
            action_id=action_id,
            meta_path=meta_path,
            max_disable=len(batch),
        )

        # verify
        probe = http_probe(domain, timeout=int(verify_timeout or 10))
        probe_after = probe.__dict__
        score_after = _probe_score(probe)

        applied_batches.append(
            {
                "batch_index": idx,
                "slugs": batch,
                "result": (res.get("ok") and {"disabled": res.get("disabled", []), "skipped": res.get("skipped", []), "errors": res.get("errors", [])}) or res,
                "probe_after_batch": probe_after,
                "score_after_batch": score_after,
            }
        )

        disabled_count = len((res.get("disabled") or [])) if isinstance(res, dict) else 0
        skipped_count = len((res.get("skipped") or [])) if isinstance(res, dict) else 0
        errors_count = len((res.get("errors") or [])) if isinstance(res, dict) else 0
        _note(action_id, f"batch={idx} disabled={disabled_count} skipped={skipped_count} errors={errors_count} score={score_after}")

        # stop conditions:
        # - becomes ok (healthy)
        # - or score improves significantly
        if probe.ok:
            recovered = True
            break
        if score_after is not None and (score_after - score_before) >= 25:
            recovered = True
            break

    if score_after is None:
        score_after = score_before

    delta = int(score_after - score_before)
    if recovered and delta >= 25:
        verdict = "improved"
    elif recovered and probe_after and probe_after.get("ok"):
        verdict = "healthy"
    elif recovered:
        verdict = "partial"
    else:
        verdict = "unchanged"

    _note(action_id, f"final recovered={recovered} verdict={verdict} score_after={score_after} delta={delta} probe_after={probe_after}")

    return {
        "ok": True,
        "action_id": action_id,
        "recovered": recovered,
        "verdict": verdict,
        "score_before": score_before,
        "score_after": score_after,
        "delta": delta,
        "probe_before": plan["probe_before"],
        "probe_after": probe_after,
        "applied_batches": applied_batches,
        "plan": {
            "mode": plan.get("mode"),
            "excluded": plan.get("excluded", []),
            "ordered_candidates": plan.get("ordered_candidates", []),
            "batches": plan.get("batches", []),
        },
        "next": "Use /api/wp-repair/rollback with action_id to revert the whole recovery run.",
    }
