from __future__ import annotations

import posixpath
from typing import Any, Dict, List, Optional

from .preview import P1_DEFAULT, P2_RISKY
from ..sftp.connect import sftp_connect


def _normalize_list(x: Any) -> List[str]:
    if not x:
        return []
    if isinstance(x, list):
        return [str(i) for i in x if str(i).strip()]
    return [str(x)]


def dropins_apply_disable(
    host: str,
    port: int,
    username: str,
    password: str,
    wp_root: str,
    disable: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Only decides WHAT to disable + returns full paths.
    The actual "move to quarantine" is done by caller via quarantine_move(),
    so rollback stays consistent.
    """
    wp_root = posixpath.normpath(wp_root)
    wp_content = posixpath.join(wp_root, "wp-content")

    disable_list = _normalize_list(disable)
    if not disable_list:
        disable_list = list(P1_DEFAULT)

    # if risky ones are requested, keep them (explicit allowed)
    requested_p2 = [x for x in disable_list if x in P2_RISKY]

    # build paths
    targets = []
    for name in disable_list:
        if name.endswith(".php"):
            targets.append({"name": name, "path": posixpath.join(wp_content, name)})
        else:
            # accept "object-cache" etc -> normalize
            nn = f"{name}.php"
            targets.append({"name": nn, "path": posixpath.join(wp_content, nn)})

    # existence check (pure info)
    client = sftp_connect(host, port, username, password)
    sftp = client.open_sftp()
    try:
        found = []
        missing = []
        for t in targets:
            try:
                sftp.stat(t["path"])
                found.append(t)
            except Exception:
                missing.append(t)

        return {
            "ok": True,
            "wp_root": wp_root,
            "mode": "disable",
            "requested": disable_list,
            "requested_p2": requested_p2,
            "found": found,
            "missing": missing,
        }
    finally:
        try:
            sftp.close()
        except Exception:
            pass
        try:
            client.close()
        except Exception:
            pass
