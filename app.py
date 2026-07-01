"""Flask entrypoint for the single-cell ANN search system."""

from __future__ import annotations

import os
import threading
import time

from flask import Flask, jsonify, render_template, request, session

from config import Settings
from src import db
from src.dataset_manager import DatasetManager, DatasetManagerError
from src.search_service import SearchService, SearchServiceError
from src.user_service import UserService, UserServiceError


def create_app() -> Flask:
    """创建并配置 Flask 应用，注册页面与 API 路由。"""

    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.getenv("NK_SECRET_KEY", "nksoft-dev-secret")
    settings = Settings()
    # 执行当前阶段的关键处理。
    db.init_database()
    # 业务层统一由 Service 管理，数据库访问不直接写在这里。
    service = SearchService(settings)
    # 数据集管理和用户管理都通过封装好的 service 层访问数据库。
    dataset_mgr = DatasetManager()
    user_svc = UserService()

    def initialize_search_service() -> None:
        # 数据文件可能很大，初始化放到后台，避免前端页面被启动阶段阻塞。
        """在后台加载数据并准备默认索引。"""
        service.initialize(allow_missing_data=True)

    if os.getenv("NK_SYNC_INIT") == "1":
        initialize_search_service()
    else:
        # 保存当前步骤需要的数据。
        service.initializing = True
        threading.Thread(target=initialize_search_service, daemon=True).start()

    def require_admin():
        """检查当前会话是否具有管理员权限。"""
        if session.get("role") != "admin":
            return jsonify({"success": False, "error": "administrator login required"}), 403
        return None

    @app.route("/")
    def index():
        """返回系统单页前端。"""
        return render_template("index.html")

    @app.route("/api/status", methods=["GET"])
    def status():
        """返回数据与索引的当前状态。"""
        return jsonify({"success": True, **service.status()})

    @app.route("/api/metadata", methods=["GET"])
    def metadata():
        """返回可用于筛选的元数据字段。"""
        try:
            metadata_payload = service.metadata_columns()
            return jsonify({"success": True, "fields": metadata_payload.get("columns", [])})
        except SearchServiceError as exc:
            # 返回当前步骤的处理结果。
            return jsonify({"success": False, "error": str(exc)}), 400

    @app.route("/api/embedding", methods=["GET"])
    def embedding():
        """返回 PCA 或 UMAP 的二维坐标。"""
        try:
            basis = request.args.get("basis", "umap")
            color_by = request.args.get("color_by", "cell_type")
            return jsonify({"success": True, **service.embedding_points(basis=basis, color_by=color_by)})
        except SearchServiceError as exc:
            # 返回当前步骤的处理结果。
            return jsonify({"success": False, "error": str(exc)}), 400

    @app.route("/api/datasets", methods=["GET"])
    def list_datasets():
        # 数据集列表直接来自数据库，前端用于展示和切换。
        """返回数据库中的数据集记录。"""
        return jsonify({"success": True, "datasets": dataset_mgr.list_datasets()})

    @app.route("/api/datasets", methods=["POST"])
    def add_dataset():
        """校验请求并新增数据集记录。"""
        guard = require_admin()
        if guard:
            return guard
        payload = request.get_json()

        # 根据当前条件执行对应处理。
        if not isinstance(payload, dict):
            return jsonify({"success": False, "error": "invalid json"}), 400

        name = payload.get("name")
        path = payload.get("path")
        # 保存当前步骤需要的数据。
        desc = payload.get("description", "")

        if not name or not path:
            return jsonify({"success": False, "error": "missing name or path"}), 400

        # 执行核心流程并统一处理异常。
        try:
            dataset_mgr.add_dataset(name, path, desc)
            return jsonify({"success": True})
        except DatasetManagerError as exc:
            return jsonify({"success": False, "error": str(exc)}), 400

    @app.route("/api/datasets/<dataset_name>", methods=["DELETE"])
    def delete_dataset(dataset_name: str):
        """删除指定数据集及其索引记录。"""
        guard = require_admin()
        if guard:
            return guard
        try:
            # 删除数据集时会同步清理对应索引记录，避免数据库残留脏数据。
            dataset_mgr.delete_dataset(dataset_name)
            return jsonify({"success": True})
        except DatasetManagerError as exc:
            return jsonify({"success": False, "error": str(exc)}), 400

    @app.route("/api/datasets/select", methods=["POST"])
    def select_dataset():
        """将指定数据集设为激活记录。"""
        guard = require_admin()
        if guard:
            return guard
        payload = request.get_json(silent=True) or {}
        # 执行核心流程并统一处理异常。
        try:
            name = payload["name"]
            # 切换激活数据集时，只更新 is_active 字段，不直接删除旧数据。
            dataset_mgr.select_dataset(name)
            return jsonify({"success": True})
        except (KeyError, DatasetManagerError) as exc:
            return jsonify({"success": False, "error": str(exc)}), 400

    @app.route("/api/register", methods=["POST"])
    def register():
        """校验账号信息并注册新用户。"""
        payload = request.get_json(silent=True) or {}
        try:
            username = payload["username"]
            password = payload["password"]
            # 保存当前步骤需要的数据。
            role = payload.get("role", "user")
            if role == "admin" and session.get("role") != "admin":
                return jsonify({"success": False, "error": "admin role requires administrator login"}), 403
            # 注册逻辑在 service 层完成，密码哈希和用户名查重都在这里处理。
            user_svc.register(username, password, role=role)
            return jsonify({"success": True})
        except (KeyError, UserServiceError) as exc:
            return jsonify({"success": False, "error": str(exc)}), 400

    @app.route("/api/login", methods=["POST"])
    def login():
        """验证账号密码并写入登录会话。"""
        payload = request.get_json(silent=True) or {}
        try:
            username = payload["username"]
            password = payload["password"]
            # 根据当前条件执行对应处理。
            if not username or not password:
                return jsonify({"success": False, "code": "missing_credentials", "error": "username and password required"}), 400
            if not user_svc.user_exists(username):
                return jsonify({"success": False, "code": "account_not_found", "error": "account not found"}), 404
            # 登录只负责把账号密码交给 service 层比对，不在路由里操作数据库。
            user = user_svc.authenticate(username, password)
            if not user:
                return jsonify({"success": False, "code": "invalid_password", "error": "invalid password"}), 401
            session["username"] = user["username"]
            # 保存当前步骤需要的数据。
            session["role"] = user["role"]
            return jsonify({"success": True, "user": user})
        except KeyError as exc:
            return jsonify({"success": False, "error": str(exc)}), 400

    @app.route("/api/logout", methods=["POST"])
    def logout():
        """清空当前登录会话。"""
        session.clear()
        return jsonify({"success": True})

    @app.route("/api/session", methods=["GET"])
    def current_session():
        """返回当前会话对应的用户。"""
        username = session.get("username")
        if not username:
            return jsonify({"success": True, "user": None})
        user = user_svc.get_user(username)
        # 返回当前步骤的处理结果。
        return jsonify({"success": True, "user": user})

    @app.route("/api/users", methods=["GET"])
    def list_users():
        """返回用户列表供管理员查看。"""
        guard = require_admin()
        if guard:
            return guard
        # 用户列表来自 users 表，主要给管理员后台使用。
        return jsonify({"success": True, "users": user_svc.list_users()})

    @app.route("/api/users/<username>", methods=["DELETE"])
    def delete_user(username: str):
        """校验权限并删除指定用户。"""
        guard = require_admin()
        if guard:
            return guard
        try:
            # 删除用户时由 service 统一处理数据库写操作和异常。
            user_svc.delete_user(username)
            return jsonify({"success": True})
        except UserServiceError as exc:
            return jsonify({"success": False, "error": str(exc)}), 400

    @app.route("/api/rebuild-index", methods=["POST"])
    def rebuild_index():
        """按指定类型重建并保存当前索引。"""
        guard = require_admin()
        if guard:
            return guard
        payload = request.get_json(silent=True) or {}
        # 执行核心流程并统一处理异常。
        try:
            # B 负责的动态索引入口：前端或管理员工具可用它切换/重建索引类型。
            # 重建索引时，索引文件和索引记录会在服务层统一维护。
            index_type = payload.get("index_type", settings.default_index_type)
            return jsonify({"success": True, **service.rebuild_index(index_type=index_type)})
        except SearchServiceError as exc:
            return jsonify({"success": False, "error": str(exc)}), 400

    @app.route("/api/search", methods=["POST"])
    def search():
        """校验查询参数并返回 Top-K 检索结果。"""
        payload = request.get_json(silent=True) or {}

        try:
            mode = payload.get("mode", "id")
            # 保存当前步骤需要的数据。
            top_k = int(payload.get("top_k", payload.get("k", settings.default_top_k)))
            index_type = payload.get("index_type")
            filters = payload.get("filters") or {}

            # filters 必须是 dict，避免前端传错类型导致服务层异常。
            if not isinstance(filters, dict):
                raise SearchServiceError("filters must be a dict")

            if index_type:
                # 执行当前阶段的关键处理。
                service.ensure_index_type(str(index_type))

            # 记录查询耗时，便于前端展示和调试。
            started_at = time.perf_counter()
            if mode == "id":
                cell_index = payload.get("cell_index", payload.get("id"))
                if cell_index is None:
                    # 抛出明确异常以终止无效操作。
                    raise SearchServiceError("cell_index is required")
                result = service.search_by_cell_index(
                    cell_index=int(cell_index),
                    top_k=top_k,
                    filters=filters,
                )
            # 根据当前条件执行对应处理。
            elif mode == "cell_id":
                result = service.search_by_cell_id(
                    cell_id=str(payload["cell_id"]),
                    top_k=top_k,
                    filters=filters,
                )
            # 根据当前条件执行对应处理。
            elif mode == "vector":
                result = service.search_by_vector(
                    vector=payload.get("vector", []),
                    top_k=top_k,
                    filters=filters,
                )
            else:
                # 抛出明确异常以终止无效操作。
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
            # 根据当前条件执行对应处理。
            if result.get("warning"):
                response["warning"] = result["warning"]
            if getattr(service, "engine", None) is not None:
                response["index_type"] = service.engine.index_type

            # 返回当前步骤的处理结果。
            return jsonify(response)

        except (KeyError, ValueError, TypeError) as exc:
            return jsonify({"success": False, "error": f"Invalid request payload: {exc}"}), 400
        except SearchServiceError as exc:
            # 返回当前步骤的处理结果。
            return jsonify({"success": False, "error": str(exc)}), 400

    # 返回当前步骤的处理结果。
    return app


if __name__ == "__main__":
    create_app().run(debug=True, port=5000, use_reloader=False)
