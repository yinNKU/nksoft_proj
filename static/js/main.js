const state = {
    user: null,
    metadataFields: [],
    filters: {},
    lastSearch: null
};

const qs = (selector) => document.querySelector(selector);

const elements = {
    loginPanel: qs("#login-panel"),
    registerPanel: qs("#register-panel"),
    workspace: qs("#workspace"),
    adminPanel: qs("#admin-panel"),
    sessionLabel: qs("#session-label"),
    logoutButton: qs("#logout-button"),
    authMessage: qs("#auth-message"),
    registerMessage: qs("#register-message"),
    registerModal: qs("#register-modal"),
    statusJson: qs("#status-json"),
    statusSummary: qs("#status-summary"),
    errorBox: qs("#error-message"),
    resultMeta: qs("#result-meta"),
    resultsBody: qs("#results-body"),
    metadataFields: qs("#metadata-fields"),
    filterField: qs("#filter-field"),
    filterValue: qs("#filter-value"),
    activeFilters: qs("#active-filters"),
    datasetList: qs("#dataset-list"),
    userList: qs("#user-list"),
    adminMessage: qs("#admin-message")
};

function setMessage(target, message, isError = false) {
    target.textContent = message || "";
    target.classList.toggle("error", Boolean(isError));
}

async function requestJson(url, options = {}) {
    const response = await fetch(url, {
        headers: {"Content-Type": "application/json", ...(options.headers || {})},
        ...options
    });
    const data = await response.json();
    if (!response.ok || data.success === false) {
        const error = new Error(data.error || "请求失败");
        error.code = data.code;
        error.status = response.status;
        throw error;
    }
    return data;
}

function showLoginPanel() {
    elements.loginPanel.classList.remove("hidden");
    elements.registerPanel.classList.add("hidden");
    setMessage(elements.authMessage, "");
    setMessage(elements.registerMessage, "");
}

function showRegisterPanel(prefillUsername = "") {
    elements.loginPanel.classList.add("hidden");
    elements.registerPanel.classList.remove("hidden");
    if (prefillUsername) {
        qs("#register-username").value = prefillUsername;
    }
    setMessage(elements.authMessage, "");
    setMessage(elements.registerMessage, "");
    qs("#register-username").focus();
}

function showRegisterModal() {
    elements.registerModal.classList.remove("hidden");
    qs("#modal-go-register").focus();
}

function hideRegisterModal() {
    elements.registerModal.classList.add("hidden");
}

function applySession(user) {
    state.user = user;
    const isLoggedIn = Boolean(user);
    const isAdmin = user?.role === "admin";

    elements.loginPanel.classList.toggle("hidden", isLoggedIn);
    elements.registerPanel.classList.add("hidden");
    elements.workspace.classList.toggle("hidden", !isLoggedIn);
    elements.adminPanel.classList.toggle("hidden", !isAdmin);
    elements.logoutButton.classList.toggle("hidden", !isLoggedIn);
    elements.sessionLabel.textContent = isLoggedIn
        ? `${user.username} (${user.role === "admin" ? "管理员" : "普通用户"})`
        : "未登录";

    if (isLoggedIn) {
        loadStatus();
        loadMetadata();
        if (isAdmin) {
            loadAdminData();
        }
    }
}

async function loadSession() {
    try {
        const data = await requestJson("/api/session");
        applySession(data.user);
    } catch (error) {
        setMessage(elements.authMessage, error.message, true);
    }
}

async function loadStatus() {
    const data = await requestJson("/api/status");
    elements.statusJson.textContent = JSON.stringify(data, null, 2);

    const cards = [
        ["数据", data.loaded ? "已加载" : "未加载"],
        ["细胞数", data.n_cells ?? 0],
        ["维度", data.n_dims ?? 0],
        ["索引", data.index_type || "-"],
        ["构建耗时", data.build_time_ms == null ? "-" : `${Number(data.build_time_ms).toFixed(2)} ms`],
        ["数据路径", data.data_path || "-"]
    ];

    elements.statusSummary.innerHTML = cards.map(([label, value]) => `
        <div class="status-item">
            <span>${escapeHtml(label)}</span>
            <strong>${escapeHtml(String(value))}</strong>
        </div>
    `).join("");

    if (data.loaded && state.metadataFields.length === 0) {
        await loadMetadata();
    }
    if (data.loaded && window.NKVisualization?.ensureLoaded) {
        window.NKVisualization.ensureLoaded();
    }

    return data;
}

async function loadMetadata() {
    try {
        const data = await requestJson("/api/metadata");
        state.metadataFields = data.fields || [];
        renderMetadataFields();
    } catch (error) {
        state.metadataFields = [];
        elements.metadataFields.textContent = `${error.message}。数据加载完成后点击“刷新”或再次检索会自动重试。`;
        elements.filterField.innerHTML = "";
    }
}

function renderMetadataFields() {
    if (!state.metadataFields.length) {
        elements.metadataFields.textContent = "当前没有可用 metadata 字段。";
        elements.filterField.innerHTML = "";
        return;
    }

    elements.metadataFields.innerHTML = state.metadataFields
        .map((field) => `<span>${escapeHtml(field)}</span>`)
        .join("");
    elements.filterField.innerHTML = state.metadataFields
        .map((field) => `<option value="${escapeHtml(field)}">${escapeHtml(field)}</option>`)
        .join("");
    const vizColor = qs("#viz-color");
    if (vizColor) {
        const current = vizColor.value || "cell_type";
        vizColor.innerHTML = state.metadataFields
            .map((field) => `<option value="${escapeHtml(field)}">${escapeHtml(field)}</option>`)
            .join("");
        vizColor.value = state.metadataFields.includes(current) ? current : state.metadataFields[0];
    }
}

function updateModeInputs() {
    const mode = qs("#mode").value;
    qs("#cell-index-row").classList.toggle("hidden", mode !== "id");
    qs("#cell-id-row").classList.toggle("hidden", mode !== "cell_id");
    qs("#vector-row").classList.toggle("hidden", mode !== "vector");
}

function collectPayload() {
    const mode = qs("#mode").value;
    const payload = {
        mode,
        top_k: Number(qs("#k").value),
        index_type: qs("#index-type").value,
        filters: {...state.filters}
    };

    if (mode === "id") {
        payload.cell_index = Number(qs("#cell-index").value);
    } else if (mode === "cell_id") {
        payload.cell_id = qs("#cell-id").value.trim();
    } else if (mode === "vector") {
        payload.vector = qs("#vector").value
            .split(",")
            .map((item) => Number(item.trim()))
            .filter((item) => !Number.isNaN(item));
    }

    return payload;
}

function renderResults(results) {
    if (!results || results.length === 0) {
        elements.resultsBody.innerHTML = `<tr><td colspan="5" class="empty">暂无结果</td></tr>`;
        return;
    }

    elements.resultsBody.innerHTML = results.map((item) => {
        const metadataText = Object.entries(item.metadata || {})
            .slice(0, 10)
            .map(([key, value]) => `<span><b>${escapeHtml(key)}</b>: ${escapeHtml(String(value))}</span>`)
            .join("");

        return `
            <tr>
                <td>${escapeHtml(String(item.rank))}</td>
                <td>${escapeHtml(String(item.cell_index))}</td>
                <td>${escapeHtml(item.cell_id || "")}</td>
                <td>${Number(item.score).toFixed(6)}</td>
                <td class="metadata-cell">${metadataText}</td>
            </tr>
        `;
    }).join("");
}

async function doSearch() {
    setMessage(elements.errorBox, "");
    try {
        const data = await requestJson("/api/search", {
            method: "POST",
            body: JSON.stringify(collectPayload())
        });
        state.lastSearch = data;
        renderResults(data.results);
        elements.resultMeta.textContent = `检索完成：${data.results.length} 条结果，${data.index_type || "-"}，${data.query_time_ms ?? "-"} ms`;
        window.dispatchEvent(new CustomEvent("nk:search-results", {
            detail: {
                payload: collectPayload(),
                response: data
            }
        }));
        if (data.warning) {
            setMessage(elements.errorBox, data.warning, false);
        }
        await loadStatus();
    } catch (error) {
        setMessage(elements.errorBox, error.message, true);
        renderResults([]);
        elements.resultMeta.textContent = "检索失败。";
    }
}

function renderFilters() {
    const entries = Object.entries(state.filters);
    elements.activeFilters.innerHTML = entries.length
        ? entries.map(([field, value]) => `
            <button type="button" data-filter="${escapeHtml(field)}">
                ${escapeHtml(field)} = ${escapeHtml(String(value))} x
            </button>
        `).join("")
        : `<span class="muted">未添加筛选。</span>`;
}

function addFilter() {
    const field = elements.filterField.value;
    const value = elements.filterValue.value.trim();
    if (!field || !value) {
        return;
    }
    state.filters[field] = value;
    elements.filterValue.value = "";
    renderFilters();
}

async function loadAdminData() {
    await Promise.all([loadDatasets(), loadUsers()]);
}

async function loadDatasets() {
    const data = await requestJson("/api/datasets");
    const datasets = data.datasets || [];
    elements.datasetList.innerHTML = datasets.length
        ? datasets.map((item) => `
            <div class="list-row">
                <div>
                    <strong>${escapeHtml(item.name)}</strong>
                    <span>${escapeHtml(item.path)}</span>
                    <small>${item.is_active ? "当前激活" : "未激活"} ${escapeHtml(item.description || "")}</small>
                </div>
                <div class="row-actions">
                    <button type="button" data-select-dataset="${escapeHtml(item.name)}">选择</button>
                    <button type="button" data-delete-dataset="${escapeHtml(item.name)}">删除</button>
                </div>
            </div>
        `).join("")
        : `<p class="muted">暂无数据集记录。</p>`;
}

async function loadUsers() {
    const data = await requestJson("/api/users");
    const users = data.users || [];
    elements.userList.innerHTML = users.length
        ? users.map((user) => `
            <div class="list-row">
                <div>
                    <strong>${escapeHtml(user.username)}</strong>
                    <span>${escapeHtml(user.role)}</span>
                    <small>${escapeHtml(user.created_at || "")}</small>
                </div>
                <button type="button" data-delete-user="${escapeHtml(user.username)}">删除</button>
            </div>
        `).join("")
        : `<p class="muted">暂无用户。</p>`;
}

async function handleLogin(event) {
    event.preventDefault();
    setMessage(elements.authMessage, "");
    const username = qs("#login-username").value.trim();
    const password = qs("#login-password").value;

    if (!username || !password) {
        setMessage(elements.authMessage, "请输入账号和密码。", true);
        return;
    }

    try {
        const data = await requestJson("/api/login", {
            method: "POST",
            body: JSON.stringify({
                username,
                password
            })
        });
        applySession(data.user);
    } catch (error) {
        if (error.code === "account_not_found") {
            showRegisterModal();
            return;
        }
        if (error.code === "invalid_password") {
            setMessage(elements.authMessage, "密码错误，请重新输入。", true);
            return;
        }
        setMessage(elements.authMessage, error.message, true);
    }
}

async function handleRegister(event) {
    event.preventDefault();
    setMessage(elements.registerMessage, "");
    const username = qs("#register-username").value.trim();
    const password = qs("#register-password").value;

    if (!username || !password) {
        setMessage(elements.registerMessage, "请输入账号和密码。", true);
        return;
    }

    try {
        await requestJson("/api/register", {
            method: "POST",
            body: JSON.stringify({
                username,
                password,
                role: "user"
            })
        });
        qs("#login-username").value = username;
        qs("#login-password").value = "";
        showLoginPanel();
        setMessage(elements.authMessage, "注册成功，可以使用新账号登录。");
        event.target.reset();
    } catch (error) {
        if (error.message === "username already exists") {
            setMessage(elements.registerMessage, "该账号已存在，请返回登录。", true);
            return;
        }
        setMessage(elements.registerMessage, error.message, true);
    }
}

async function handleLogout() {
    await requestJson("/api/logout", {method: "POST", body: "{}"});
    state.filters = {};
    renderFilters();
    applySession(null);
}

async function handleDatasetSubmit(event) {
    event.preventDefault();
    try {
        await requestJson("/api/datasets", {
            method: "POST",
            body: JSON.stringify({
                name: qs("#dataset-name").value.trim(),
                path: qs("#dataset-path").value.trim(),
                description: qs("#dataset-desc").value.trim()
            })
        });
        event.target.reset();
        setMessage(elements.adminMessage, "数据集已写入 SQLite。");
        await loadDatasets();
    } catch (error) {
        setMessage(elements.adminMessage, error.message, true);
    }
}

async function handleAdminUserSubmit(event) {
    event.preventDefault();
    try {
        await requestJson("/api/register", {
            method: "POST",
            body: JSON.stringify({
                username: qs("#admin-new-username").value.trim(),
                password: qs("#admin-new-password").value,
                role: qs("#admin-new-role").value
            })
        });
        event.target.reset();
        setMessage(elements.adminMessage, "用户已创建。");
        await loadUsers();
    } catch (error) {
        setMessage(elements.adminMessage, error.message, true);
    }
}

async function handleAdminListClick(event) {
    const selectDataset = event.target.dataset.selectDataset;
    const deleteDataset = event.target.dataset.deleteDataset;
    const deleteUser = event.target.dataset.deleteUser;

    try {
        if (selectDataset) {
            await requestJson("/api/datasets/select", {
                method: "POST",
                body: JSON.stringify({name: selectDataset})
            });
            setMessage(elements.adminMessage, "已切换激活数据集记录。重启服务或设置 SC_DATA_PATH 后可加载对应数据。");
            await loadDatasets();
        }
        if (deleteDataset) {
            await requestJson(`/api/datasets/${encodeURIComponent(deleteDataset)}`, {method: "DELETE"});
            await loadDatasets();
        }
        if (deleteUser) {
            await requestJson(`/api/users/${encodeURIComponent(deleteUser)}`, {method: "DELETE"});
            await loadUsers();
        }
    } catch (error) {
        setMessage(elements.adminMessage, error.message, true);
    }
}

async function rebuildIndex() {
    try {
        const data = await requestJson("/api/rebuild-index", {
            method: "POST",
            body: JSON.stringify({index_type: qs("#rebuild-index-type").value})
        });
        setMessage(elements.adminMessage, `索引已重建：${data.index_type}，${data.build_time_ms?.toFixed?.(2) ?? data.build_time_ms} ms`);
        await loadStatus();
    } catch (error) {
        setMessage(elements.adminMessage, error.message, true);
    }
}

function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, (char) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#039;"
    }[char]));
}

qs("#login-form").addEventListener("submit", handleLogin);
qs("#register-form").addEventListener("submit", handleRegister);
qs("#show-register").addEventListener("click", () => showRegisterPanel(qs("#login-username").value.trim()));
qs("#back-to-login").addEventListener("click", showLoginPanel);
qs("#modal-go-register").addEventListener("click", () => {
    hideRegisterModal();
    showRegisterPanel(qs("#login-username").value.trim());
});
qs("#modal-cancel").addEventListener("click", hideRegisterModal);
qs("#register-modal").addEventListener("click", (event) => {
    if (event.target === elements.registerModal) {
        hideRegisterModal();
    }
});
document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
        hideRegisterModal();
    }
});
qs("#logout-button").addEventListener("click", handleLogout);
qs("#mode").addEventListener("change", updateModeInputs);
qs("#refresh-status").addEventListener("click", loadStatus);
qs("#search-button").addEventListener("click", doSearch);
qs("#add-filter").addEventListener("click", addFilter);
qs("#active-filters").addEventListener("click", (event) => {
    const field = event.target.dataset.filter;
    if (field) {
        delete state.filters[field];
        renderFilters();
    }
});
qs("#dataset-form").addEventListener("submit", handleDatasetSubmit);
qs("#admin-user-form").addEventListener("submit", handleAdminUserSubmit);
qs("#dataset-list").addEventListener("click", handleAdminListClick);
qs("#user-list").addEventListener("click", handleAdminListClick);
qs("#rebuild-index").addEventListener("click", rebuildIndex);

updateModeInputs();
renderFilters();
loadSession();
