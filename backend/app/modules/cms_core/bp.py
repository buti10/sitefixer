from flask import Blueprint, request, jsonify
from .fs import index as cc_index, load_manifest, load_rules

bp_core_cache = Blueprint("core_cache", __name__, url_prefix="/api/core-cache")

@bp_core_cache.get("/index")
def api_index():
    return jsonify({"cms": cc_index()})

@bp_core_cache.get("/manifest")
def api_manifest():
    cms = request.args.get("cms","").lower()
    version = request.args.get("version","")
    if not cms or not version: return jsonify({"error":"cms and version required"}), 400
    try:
        return jsonify(load_manifest(cms, version))
    except FileNotFoundError:
        return jsonify({"error":"not found"}), 404

@bp_core_cache.get("/rules")
def api_rules():
    cms = request.args.get("cms","").lower()
    version = request.args.get("version","")
    if not cms or not version: return jsonify({"error":"cms and version required"}), 400
    try:
        return jsonify(load_rules(cms, version))
    except FileNotFoundError:
        return jsonify({"error":"not found"}), 404
