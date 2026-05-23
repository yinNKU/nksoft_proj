"""Flask entrypoint for the single-cell ANN search system."""

from __future__ import annotations

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
        return jsonify(service.status())

    @app.route("/api/metadata", methods=["GET"])
    def metadata():
        try:
            return jsonify(service.metadata_columns())
        except SearchServiceError as exc:
            return jsonify({"error": str(exc)}), 400

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
            k = int(payload.get("k", settings.default_top_k))
            index_type = payload.get("index_type", settings.default_index_type)

            if mode == "id":
                result = service.search_by_cell_index(
                    cell_index=int(payload["cell_index"]),
                    k=k,
                    index_type=index_type,
                )
            elif mode == "vector":
                # TODO:
                # - 前端传入自定义向量后，在 service.search_by_vector 中完成维度校验和归一化。
                # - 当前先保留接口，后续补具体实现。
                result = service.search_by_vector(
                    vector=payload.get("vector", []),
                    k=k,
                    index_type=index_type,
                )
            elif mode == "cell_id":
                # TODO:
                # - 支持使用真实 cell_id 查询，而不只是整数编号。
                result = service.search_by_cell_id(
                    cell_id=str(payload["cell_id"]),
                    k=k,
                    index_type=index_type,
                )
            else:
                raise SearchServiceError(f"Unsupported search mode: {mode}")

            return jsonify(result)

        except (KeyError, ValueError, TypeError) as exc:
            return jsonify({"error": f"Invalid request payload: {exc}"}), 400
        except SearchServiceError as exc:
            return jsonify({"error": str(exc)}), 400

    return app


if __name__ == "__main__":
    create_app().run(debug=True, port=5000)
