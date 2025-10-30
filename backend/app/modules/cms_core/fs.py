# app/modules/cms_core/fs.py
from __future__ import annotations
import os, json
from typing import Dict, List
from flask import current_app

def _store() -> str:
    return current_app.config.get("CMS_CORE_STORE", "/var/www/sitefixer/core-cache")

def index() -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    base = _store()
    if not os.path.isdir(base):
        return out
    for cms in sorted(os.listdir(base)):
        cdir = os.path.join(base, cms)
        if not os.path.isdir(cdir): 
            continue
        vers = [v for v in os.listdir(cdir) if os.path.isdir(os.path.join(cdir, v))]
        out[cms] = sorted(vers, key=lambda s: [int(p) if p.isdigit() else p for p in s.replace('-', '.').split('.')])
    return out

def load_manifest(cms: str, version: str) -> Dict:
    path = os.path.join(_store(), cms, version, "manifest.json")
    return json.load(open(path)) if os.path.isfile(path) else {}

def load_rules(cms: str) -> Dict:
    path = os.path.join(_store(), cms, "rules.json")
    return json.load(open(path)) if os.path.isfile(path) else {}
