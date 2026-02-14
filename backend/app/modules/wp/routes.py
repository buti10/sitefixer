# app/modules/wp/routes.py
from flask import Blueprint, jsonify
from .services import get_wp_products

bp_wp = Blueprint("wp", __name__, url_prefix="/api/wp")

@bp_wp.get("/products")
def api_get_products():
    return jsonify(get_wp_products())
