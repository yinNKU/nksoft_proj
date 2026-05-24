"""Flask entrypoint for the single-cell ANN search system."""

from __future__ import annotations

import time

from flask import Flask, jsonify, render_template, request

from config import Settings
from src.search_service import SearchService, SearchServiceError


def create_app() -> Flask:
    """Create and configure Flask app.

    当前版本采用启动时初始化。若 data/sample.h5ad 不存在，项目仍可启动，
    方便先开发前端与 API 框架。

    TODO:
    - 增加 /api/load-data，用于运行时上传或切换数据集。
    - 增加 /api/rebuild-index，用于单独重建索引。
    - 增加统一日志记录。
    """

    app = Flask(__name__)
    settings = Settings()
    service = SearchService(settings)

    # 基础框架阶段：允许数据缺失，便于先跑通 Web 和 API。
    service.initialize(allow_missing_data=True)

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/api/status", methods=["GET"])
    def status():
        return jsonify({"success": True, **service.status()})

    @app.route("/api/metadata", methods=["GET"])
    def metadata():
        try:
            metadata_payload = service.metadata_columns()
            return jsonify({"success": True, "fields": metadata_payload.get("columns", [])})
        except SearchServiceError as exc:
            return jsonify({"success": False, "error": str(exc)}), 400

    @app.route("/api/rebuild-index", methods=["POST"])
    def rebuild_index():
        payload = request.get_json(silent=True) or {}
        try:
            # B 负责的动态索引入口：前端或管理员工具可用它切换/重建索引类型。
            index_type = payload.get("index_type", settings.default_index_type)
            return jsonify({"success": True, **service.rebuild_index(index_type=index_type)})
        except SearchServiceError as exc:
            return jsonify({"success": False, "error": str(exc)}), 400

    @app.route("/api/search", methods=["POST"])
    def search():
        payload = request.get_json(silent=True) or {}

        try:
            mode = payload.get("mode", "id")
            top_k = int(payload.get("top_k", payload.get("k", settings.default_top_k)))
            index_type = payload.get("index_type")
            filters = payload.get("filters") or {}

            if not isinstance(filters, dict):
                raise SearchServiceError("filters must be a dict")

            if index_type:
                service.ensure_index_type(str(index_type))

            started_at = time.perf_counter()
            if mode == "id":
                result = service.search_by_cell_index(
                    cell_index=int(payload["cell_index"]),
                    top_k=top_k,
                    filters=filters,
                )
            elif mode == "cell_id":
                result = service.search_by_cell_id(
                    cell_id=str(payload["cell_id"]),
                    top_k=top_k,
                    filters=filters,
                )
            elif mode == "vector":
                result = service.search_by_vector(
                    vector=payload.get("vector", []),
                    top_k=top_k,
                    filters=filters,
                )
            else:
                raise SearchServiceError(f"Unsupported search mode: {mode}")

            query_time_ms = (time.perf_counter() - started_at) * 1000
            response = {
                "success": True,
                "mode": mode,
                "top_k": top_k,
                "filters": filters,
                "query_time_ms": round(query_time_ms, 2),
                "results": result.get("results", []),
            }
            if result.get("warning"):
                response["warning"] = result["warning"]
            if getattr(service, "engine", None) is not None:
                response["index_type"] = service.engine.index_type

            return jsonify(response)

        except (KeyError, ValueError, TypeError) as exc:
            return jsonify({"success": False, "error": f"Invalid request payload: {exc}"}), 400
        except SearchServiceError as exc:
            return jsonify({"success": False, "error": str(exc)}), 400

    return app


if __name__ == "__main__":
    create_app().run(debug=True, port=5000)
