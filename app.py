"""Flask entrypoint for the single-cell ANN search system."""

from __future__ import annotations

import time

from flask import Flask, jsonify, render_template, request

from config import Settings
from src.dataset_manager import DatasetManager, DatasetManagerError
from src.search_service import SearchService, SearchServiceError
from src.user_service import UserService, UserServiceError


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
    # 业务层统一由 Service 管理，数据库访问不直接写在这里。
    service = SearchService(settings)
    # 数据集管理和用户管理都通过封装好的 service 层访问数据库。
    dataset_mgr = DatasetManager()
    user_svc = UserService()

    # 基础框架阶段：允许数据缺失，便于先跑通 Web 和 API。
    # 启动时允许数据缺失，便于先跑通 Web 和 API；后续可再补数据集。
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

    @app.route("/api/datasets", methods=["GET"])
    def list_datasets():
        # 数据集列表直接来自数据库，前端用于展示和切换。
        return jsonify({"success": True, "datasets": dataset_mgr.list_datasets()})

    @app.route("/api/datasets", methods=["POST"])
    def add_dataset():
        payload = request.get_json()

        if not isinstance(payload, dict):
            return jsonify({"success": False, "error": "invalid json"}), 400

        name = payload.get("name")
        path = payload.get("path")
        desc = payload.get("description", "")

        if not name or not path:
            return jsonify({"success": False, "error": "missing name or path"}), 400

        dataset_mgr.add_dataset(name, path, desc)
        return jsonify({"success": True})

    @app.route("/api/datasets/<dataset_name>", methods=["DELETE"])
    def delete_dataset(dataset_name: str):
        try:
            # 删除数据集时会同步清理对应索引记录，避免数据库残留脏数据。
            dataset_mgr.delete_dataset(dataset_name)
            return jsonify({"success": True})
        except DatasetManagerError as exc:
            return jsonify({"success": False, "error": str(exc)}), 400

    @app.route("/api/datasets/select", methods=["POST"])
    def select_dataset():
        payload = request.get_json(silent=True) or {}
        try:
            name = payload["name"]
            # 切换激活数据集时，只更新 is_active 字段，不直接删除旧数据。
            dataset_mgr.select_dataset(name)
            return jsonify({"success": True})
        except (KeyError, DatasetManagerError) as exc:
            return jsonify({"success": False, "error": str(exc)}), 400

    @app.route("/api/register", methods=["POST"])
    def register():
        payload = request.get_json(silent=True) or {}
        try:
            username = payload["username"]
            password = payload["password"]
            role = payload.get("role", "user")
            # 注册逻辑在 service 层完成，密码哈希和用户名查重都在这里处理。
            user_svc.register(username, password, role=role)
            return jsonify({"success": True})
        except (KeyError, UserServiceError) as exc:
            return jsonify({"success": False, "error": str(exc)}), 400

    @app.route("/api/login", methods=["POST"])
    def login():
        payload = request.get_json(silent=True) or {}
        try:
            username = payload["username"]
            password = payload["password"]
            # 登录只负责把账号密码交给 service 层比对，不在路由里操作数据库。
            ok = user_svc.login(username, password)
            return jsonify({"success": ok})
        except KeyError as exc:
            return jsonify({"success": False, "error": str(exc)}), 400

    @app.route("/api/logout", methods=["POST"])
    def logout():
        return jsonify({"success": True})

    @app.route("/api/users", methods=["GET"])
    def list_users():
        # 用户列表来自 users 表，主要给管理员后台使用。
        return jsonify({"success": True, "users": user_svc.list_users()})

    @app.route("/api/users/<username>", methods=["DELETE"])
    def delete_user(username: str):
        try:
            # 删除用户时由 service 统一处理数据库写操作和异常。
            user_svc.delete_user(username)
            return jsonify({"success": True})
        except UserServiceError as exc:
            return jsonify({"success": False, "error": str(exc)}), 400

    @app.route("/api/rebuild-index", methods=["POST"])
    def rebuild_index():
        payload = request.get_json(silent=True) or {}
        try:
            # B 负责的动态索引入口：前端或管理员工具可用它切换/重建索引类型。
            # 重建索引时，索引文件和索引记录会在服务层统一维护。
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

            # filters 必须是 dict，避免前端传错类型导致服务层异常。
            if not isinstance(filters, dict):
                raise SearchServiceError("filters must be a dict")

            if index_type:
                service.ensure_index_type(str(index_type))

            # 记录查询耗时，便于前端展示和调试。
            started_at = time.perf_counter()
            if mode == "id":
                cell_index = payload.get("cell_index", payload.get("id"))
                if cell_index is None:
                    raise SearchServiceError("cell_index is required")
                result = service.search_by_cell_index(
                    cell_index=int(cell_index),
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
