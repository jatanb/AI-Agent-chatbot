from __future__ import annotations

import os
from typing import Any, Optional

from flask import Flask, jsonify, request

from agent import run_agent
from src.database.database import save_scheme, get_saved_schemes

APP_API_KEY_ENV = "API_KEY"


def create_app() -> Flask:
    app = Flask(__name__)

    def require_api_key() -> Optional[dict[str, Any]]:
        expected = os.getenv(APP_API_KEY_ENV, "").strip()
        if not expected:
            return None  # auth disabled

        provided = request.headers.get("X-API-Key", "").strip()
        if not provided or provided != expected:
            return {"ok": False, "error": "Unauthorized. Provide a valid X-API-Key."}
        return None

    @app.get("/health")
    def health():
        return jsonify({"ok": True})

    @app.post("/v1/chat")
    def chat():
        bad = require_api_key()
        if bad is not None:
            return jsonify(bad), 401

        payload = request.get_json(silent=True) or {}
        query = (payload.get("query") or "").strip()
        if not query:
            return jsonify({"ok": False, "error": "'query' is required"}), 400

        thread_id = str(payload.get("thread_id") or "default")
        category = payload.get("category")
        chat_history = payload.get("chat_history") or []

        try:
            result = run_agent(
                query=query,
                category=category,
                chat_history=chat_history,
                thread_id=thread_id,
            )
            return jsonify({"ok": True, "data": result})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500

    @app.post("/v1/schemes")
    def schemes_create():
        bad = require_api_key()
        if bad is not None:
            return jsonify(bad), 401

        payload = request.get_json(silent=True) or {}
        user_id = (payload.get("user_id") or "").strip()
        scheme = payload.get("scheme") or {}
        if not user_id:
            return jsonify({"ok": False, "error": "'user_id' is required"}), 400
        if not isinstance(scheme, dict):
            return jsonify({"ok": False, "error": "'scheme' must be an object"}), 400

        alert_on = bool(payload.get("alert_on", False))
        try:
            scheme_id = save_scheme(user_id=user_id, scheme=scheme, alert_on=alert_on)
            return jsonify({"ok": True, "data": {"scheme_id": scheme_id}})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500

    @app.get("/v1/schemes")
    def schemes_list():
        bad = require_api_key()
        if bad is not None:
            return jsonify(bad), 401

        user_id = (request.args.get("user_id") or "").strip()
        if not user_id:
            return jsonify({"ok": False, "error": "'user_id' query param is required"}), 400

        try:
            schemes = get_saved_schemes(user_id)
            return jsonify({"ok": True, "data": schemes})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500

    return app


app = create_app()


if __name__ == "__main__":
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    debug = os.getenv("ENVIRONMENT", "development") == "development"
    app.run(host=host, port=port, debug=debug)

