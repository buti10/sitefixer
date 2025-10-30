# app/modules/cms_core/api.py
from flask import Blueprint, jsonify
from .fs import index as _index

bp = Blueprint("cms_core", __name__)

@bp.get("/index")
def index():
    return jsonify({"ok": True, "roots": ["/var/www/sitefixer/core-cache"]})
