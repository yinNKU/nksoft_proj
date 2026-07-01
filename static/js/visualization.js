const vizState = {
    points: [],
    bounds: null,
    loadedKey: "",
    highlights: new Set(),
    topResults: [],
    overlayMarkers: [],
    queryIndex: null,
    lastEmbeddingMeta: null,
    palette: [
        "#0f6f55",
        "#b7791f",
        "#7c5c35",
        "#47624f",
        "#9b4f2f",
        "#506c7a",
        "#78623b",
        "#5f6d63"
    ]
};

const viz = {
    basis: document.getElementById("viz-basis"),
    color: document.getElementById("viz-color"),
    highlightMode: document.getElementById("viz-highlight-mode"),
    button: document.getElementById("reload-viz"),
    canvas: document.getElementById("embedding-canvas"),
    status: document.getElementById("viz-status"),
    legend: document.getElementById("viz-legend"),
    tooltip: document.getElementById("viz-tooltip")
};

const VIZ_STYLE = {
    backgroundRadius: 1.55,
    backgroundAlpha: 0.3,
    markerRadius: 10,
    queryRadius: 12,
    minMarkerGap: 25,
    anchorOffsetThreshold: 4,
    edgePadding: 16
};

// 设置当前界面状态和提示。
function setVizStatus(message, isError = false) {
    viz.status.textContent = message;
    viz.status.classList.toggle("error", isError);
}

// 根据最新数据更新当前状态。
function updateVizStatus() {
    if (!vizState.lastEmbeddingMeta) {
        return;
    }
    const { basis, nPoints, colorBy } = vizState.lastEmbeddingMeta;
    // 保存当前步骤需要的数据。
    const highlightCount = vizState.topResults.length;
    const modeText = getHighlightMode() === "spread" ? "相对坐标显示" : "真实坐标显示";
    const suffix = highlightCount
        ? `，已高亮 Top-${highlightCount}（${modeText}）`
        : "";
    setVizStatus(`${basis.toUpperCase()} 已按 ${colorBy} 着色${suffix}。`);
}

// 加载数据并更新对应页面状态。
async function loadEmbedding(force = false) {
    if (!viz.canvas) {
        return;
    }
    const basis = viz.basis.value;
    // 保存当前步骤需要的数据。
    const colorBy = viz.color.value || "cell_type";
    const key = `${basis}:${colorBy}`;
    if (!force && vizState.loadedKey === key && vizState.points.length > 0) {
        drawEmbedding();
        updateVizStatus();
        // 返回当前函数的处理结果。
        return;
    }

    setVizStatus("正在加载可视化数据...");
    try {
        // 保存当前步骤需要的数据。
        const response = await fetch(`/api/embedding?basis=${encodeURIComponent(basis)}&color_by=${encodeURIComponent(colorBy)}`);
        const data = await response.json();
        if (!response.ok || data.success === false) {
            throw new Error(data.error || "可视化数据加载失败");
        }
        vizState.points = data.points || [];
        vizState.loadedKey = key;
        vizState.bounds = computeBounds(vizState.points);
        vizState.lastEmbeddingMeta = {
            basis: data.basis || basis,
            nPoints: data.n_points ?? vizState.points.length,
            colorBy: data.color_by || colorBy
        };
        renderLegend(vizState.points);
        drawEmbedding();
        updateVizStatus();
    } catch (error) {
        setVizStatus(`${error.message}。数据加载完成后重试。`, true);
    }
}

// 确保可视化数据已经加载。
function ensureLoaded() {
    if (!vizState.points.length) {
        loadEmbedding(false);
    }
}

// 计算绘制和布局所需的数值。
function computeBounds(points) {
    const xs = points.map((point) => point.x).filter(Number.isFinite);
    const ys = points.map((point) => point.y).filter(Number.isFinite);
    if (!xs.length || !ys.length) {
        return null;
    }
    // 返回当前函数的处理结果。
    return {
        minX: Math.min(...xs),
        maxX: Math.max(...xs),
        minY: Math.min(...ys),
        maxY: Math.max(...ys)
    };
}

// 为分类值选择稳定颜色。
function colorFor(value) {
    const key = String(value || "unknown");
    let hash = 0;
    for (let i = 0; i < key.length; i += 1) {
        hash = ((hash << 5) - hash) + key.charCodeAt(i);
        hash |= 0;
    }
    // 返回当前函数的处理结果。
    return vizState.palette[Math.abs(hash) % vizState.palette.length];
}

// 将数据坐标转换为画布坐标。
function toCanvas(point, width, height) {
    const bounds = vizState.bounds;
    const pad = 28;
    const xRange = bounds.maxX - bounds.minX || 1;
    const yRange = bounds.maxY - bounds.minY || 1;
    // 返回当前函数的处理结果。
    return {
        x: pad + ((point.x - bounds.minX) / xRange) * (width - pad * 2),
        y: height - pad - ((point.y - bounds.minY) / yRange) * (height - pad * 2)
    };
}

// 返回当前选择的状态值。
function getHighlightMode() {
    return viz.highlightMode?.value || "spread";
}

// 按细胞下标建立数据点查找表。
function indexPointsByCellIndex() {
    const map = new Map();
    for (const point of vizState.points) {
        map.set(Number(point.cell_index), point);
    }
    // 返回当前函数的处理结果。
    return map;
}

// 根据当前数据构造绘制对象。
function buildOverlayMarkers(width, height) {
    if (!vizState.topResults.length || !vizState.points.length || !vizState.bounds) {
        return [];
    }

    // 保存当前步骤需要的数据。
    const byIndex = indexPointsByCellIndex();
    const mode = getHighlightMode();
    const occupied = [];
    const markers = [];

    // 逐项处理当前数据。
    for (const result of vizState.topResults) {
        const point = byIndex.get(Number(result.cell_index));
        if (!point) {
            continue;
        }
        // 保存当前步骤需要的数据。
        const anchor = toCanvas(point, width, height);
        const isQuery = Number(result.cell_index) === vizState.queryIndex;
        const radius = isQuery ? VIZ_STYLE.queryRadius : VIZ_STYLE.markerRadius;
        const display = mode === "spread"
            ? findDisplayPosition(anchor, occupied, width, height, radius)
            : clampPosition(anchor, width, height, radius);
        // 保存当前步骤需要的数据。
        const marker = {
            ...result,
            point,
            anchor,
            display,
            radius,
            isQuery
        };
        markers.push(marker);
        occupied.push({
            x: display.x,
            y: display.y,
            minDistance: Math.max(VIZ_STYLE.minMarkerGap, radius * 2 + 4)
        });
    }

    // 返回当前函数的处理结果。
    return markers;
}

// 查找满足显示条件的位置。
function findDisplayPosition(anchor, occupied, width, height, radius) {
    const candidates = [];
    const ringRadii = [0, 26, 38, 52, 68, 86, 108, 132, 158];

    for (let ring = 0; ring < ringRadii.length; ring += 1) {
        // 保存当前步骤需要的数据。
        const distance = ringRadii[ring];
        const angleCount = ring === 0 ? 1 : ring < 3 ? 8 : 16;
        for (let step = 0; step < angleCount; step += 1) {
            const angle = ring === 0 ? 0 : (Math.PI * 2 * step) / angleCount;
            const raw = {
                x: anchor.x + Math.cos(angle) * distance,
                y: anchor.y + Math.sin(angle) * distance
            };
            // 保存当前步骤需要的数据。
            const candidate = clampPosition(raw, width, height, radius);
            candidates.push({
                ...candidate,
                score: scoreCandidate(candidate, anchor, occupied, radius)
            });
        }
    }

    candidates.sort((a, b) => a.score - b.score);
    // 返回当前函数的处理结果。
    return candidates[0] || clampPosition(anchor, width, height, radius);
}

// 将标记位置限制在画布范围内。
function clampPosition(position, width, height, radius) {
    const pad = Math.max(VIZ_STYLE.edgePadding, radius + 3);
    return {
        x: Math.min(Math.max(position.x, pad), Math.max(pad, width - pad)),
        y: Math.min(Math.max(position.y, pad), Math.max(pad, height - pad))
    };
}

// 计算候选标记位置的布局得分。
function scoreCandidate(candidate, anchor, occupied, radius) {
    const anchorDistance = Math.hypot(candidate.x - anchor.x, candidate.y - anchor.y);
    let overlapPenalty = 0;
    for (const item of occupied) {
        const distance = Math.hypot(candidate.x - item.x, candidate.y - item.y);
        // 保存当前步骤需要的数据。
        const minDistance = Math.max(item.minDistance, VIZ_STYLE.minMarkerGap, radius * 2 + 4);
        if (distance < minDistance) {
            overlapPenalty += (minDistance - distance) * 1200;
        }
    }
    // 返回当前函数的处理结果。
    return anchorDistance + overlapPenalty;
}

// 在画布上绘制对应图形。
function drawEmbedding() {
    const canvas = viz.canvas;
    const ctx = canvas.getContext("2d");
    const rect = canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.max(320, Math.floor(rect.width * dpr));
    canvas.height = Math.max(260, Math.floor(rect.height * dpr));
    // 绘制当前可视化元素。
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    const width = rect.width;
    const height = rect.height;
    ctx.clearRect(0, 0, width, height);
    // 绘制当前可视化元素。
    ctx.fillStyle = "#fffdf7";
    ctx.fillRect(0, 0, width, height);

    if (!vizState.points.length || !vizState.bounds) {
        ctx.fillStyle = "#5f6d63";
        // 绘制当前可视化元素。
        ctx.font = "14px Segoe UI";
        ctx.fillText("暂无可视化数据", 24, 32);
        return;
    }

    drawBackgroundPoints(ctx, width, height);
    vizState.overlayMarkers = buildOverlayMarkers(width, height);
    drawOverlayGuides(ctx, vizState.overlayMarkers);
    drawQueryTarget(ctx, width, height, vizState.overlayMarkers);
    drawOverlayMarkers(ctx, vizState.overlayMarkers);
}

// 在画布上绘制对应图形。
function drawBackgroundPoints(ctx, width, height) {
    ctx.globalAlpha = VIZ_STYLE.backgroundAlpha;
    for (const point of vizState.points) {
        const pos = toCanvas(point, width, height);
        ctx.beginPath();
        // 绘制当前可视化元素。
        ctx.fillStyle = colorFor(point.color);
        ctx.arc(pos.x, pos.y, VIZ_STYLE.backgroundRadius, 0, Math.PI * 2);
        ctx.fill();
    }
    ctx.globalAlpha = 1;
}

// 在画布上绘制对应图形。
function drawOverlayGuides(ctx, markers) {
    if (getHighlightMode() !== "spread") {
        return;
    }
    ctx.save();
    // 绘制当前可视化元素。
    ctx.lineWidth = 1.1;
    ctx.strokeStyle = "rgba(80, 69, 47, 0.42)";
    ctx.fillStyle = "rgba(80, 69, 47, 0.46)";
    for (const marker of markers) {
        if (distanceBetween(marker.anchor, marker.display) <= VIZ_STYLE.anchorOffsetThreshold) {
            continue;
        }
        // 绘制当前可视化元素。
        ctx.beginPath();
        ctx.moveTo(marker.anchor.x, marker.anchor.y);
        ctx.lineTo(marker.display.x, marker.display.y);
        ctx.stroke();
        ctx.beginPath();
        // 绘制当前可视化元素。
        ctx.arc(marker.anchor.x, marker.anchor.y, 2.2, 0, Math.PI * 2);
        ctx.fill();
    }
    ctx.restore();
}

// 在画布上绘制对应图形。
function drawOverlayMarkers(ctx, markers) {
    ctx.save();
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    for (const marker of markers) {
        // 保存当前步骤需要的数据。
        const { x, y } = marker.display;
        const radius = marker.radius;

        ctx.beginPath();
        ctx.fillStyle = marker.isQuery ? "rgba(180, 35, 24, 0.16)" : "rgba(183, 121, 31, 0.22)";
        // 绘制当前可视化元素。
        ctx.arc(x, y, radius + 7, 0, Math.PI * 2);
        ctx.fill();

        ctx.beginPath();
        ctx.lineWidth = marker.isQuery ? 3 : 2.4;
        // 绘制当前可视化元素。
        ctx.strokeStyle = marker.isQuery ? "#b42318" : "#111814";
        ctx.fillStyle = "#fffdf7";
        ctx.arc(x, y, radius, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();

        // 绘制当前可视化元素。
        ctx.fillStyle = marker.isQuery ? "#8f1d14" : "#111814";
        ctx.font = "700 11px Segoe UI, Microsoft YaHei, sans-serif";
        ctx.fillText(String(marker.rank), x, y + 0.5);
    }
    ctx.restore();
}

// 在画布上绘制对应图形。
function drawQueryTarget(ctx, width, height, markers) {
    if (!Number.isFinite(vizState.queryIndex)) {
        return;
    }
    const alreadyMarked = markers.some((marker) => Number(marker.cell_index) === vizState.queryIndex);
    // 根据当前状态执行对应处理。
    if (alreadyMarked) {
        return;
    }
    const point = indexPointsByCellIndex().get(vizState.queryIndex);
    if (!point) {
        // 返回当前函数的处理结果。
        return;
    }
    const pos = toCanvas(point, width, height);
    ctx.save();
    ctx.strokeStyle = "#b42318";
    // 绘制当前可视化元素。
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    ctx.arc(pos.x, pos.y, 12, 0, Math.PI * 2);
    ctx.stroke();
    ctx.beginPath();
    // 绘制当前可视化元素。
    ctx.moveTo(pos.x - 15, pos.y);
    ctx.lineTo(pos.x + 15, pos.y);
    ctx.moveTo(pos.x, pos.y - 15);
    ctx.lineTo(pos.x, pos.y + 15);
    ctx.stroke();
    // 绘制当前可视化元素。
    ctx.restore();
}

// 根据当前数据渲染页面内容。
function renderLegend(points) {
    const counts = new Map();
    for (const point of points) {
        counts.set(point.color, (counts.get(point.color) || 0) + 1);
    }
    // 保存当前步骤需要的数据。
    const entries = [...counts.entries()]
        .sort((a, b) => b[1] - a[1])
        .slice(0, 12);
    const highlightSummary = vizState.topResults.length ? `
        <div class="legend-highlight-summary">
            <strong>Top-${vizState.topResults.length}</strong>
            <span>${getHighlightMode() === "spread"
                ? `${vizState.topResults.length} 个编号已相对显示`
                : `${vizState.topResults.length} 个编号已按照真实坐标显示`}</span>
        </div>
    ` : "";
    viz.legend.innerHTML = `${highlightSummary}${entries.map(([name, count]) => `
        <div class="legend-item">
            <span class="legend-swatch" style="background:${colorFor(name)}"></span>
            <span>${escapeVizHtml(name)}</span>
            <small>${count}</small>
        </div>
    `).join("")}`;
}

// 查找鼠标附近的数据点。
function nearestHighlight(event) {
    if (!vizState.overlayMarkers.length) {
        return null;
    }
    const rect = viz.canvas.getBoundingClientRect();
    // 保存当前步骤需要的数据。
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    let best = null;
    let bestDistance = Infinity;
    for (const marker of vizState.overlayMarkers) {
        // 保存当前步骤需要的数据。
        const distance = Math.hypot(marker.display.x - x, marker.display.y - y);
        if (distance < bestDistance) {
            best = marker;
            bestDistance = distance;
        }
    }
    // 返回当前函数的处理结果。
    return best && bestDistance <= best.radius + 10 ? best : null;
}

// 查找鼠标附近的数据点。
function nearestPoint(event) {
    if (!vizState.points.length || !vizState.bounds) {
        return null;
    }
    const rect = viz.canvas.getBoundingClientRect();
    // 保存当前步骤需要的数据。
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    let best = null;
    let bestDistance = Infinity;
    for (const point of vizState.points) {
        // 保存当前步骤需要的数据。
        const pos = toCanvas(point, rect.width, rect.height);
        const distance = Math.hypot(pos.x - x, pos.y - y);
        if (distance < bestDistance) {
            best = { point, pos };
            bestDistance = distance;
        }
    }
    // 返回当前函数的处理结果。
    return bestDistance <= 8 ? best : null;
}

// 显示指定的界面内容。
function showTooltip(event) {
    const marker = nearestHighlight(event);
    if (marker) {
        showHighlightTooltip(event, marker);
        return;
    }

    // 保存当前步骤需要的数据。
    const nearest = nearestPoint(event);
    if (!nearest) {
        viz.tooltip.classList.add("hidden");
        return;
    }
    // 保存当前步骤需要的数据。
    const { point } = nearest;
    viz.tooltip.innerHTML = `
        <strong>${escapeVizHtml(point.cell_id)}</strong>
        <span>index: ${point.cell_index}</span>
        <span>${escapeVizHtml(viz.color.value)}: ${escapeVizHtml(point.color)}</span>
    `;
    positionTooltip(event);
}

// 显示指定的界面内容。
function showHighlightTooltip(event, marker) {
    const similarity = formatSimilarity(marker);
    viz.tooltip.innerHTML = `
        <strong>Top-${escapeVizHtml(marker.rank)} · ${escapeVizHtml(marker.cell_id)}</strong>
        <span>index: ${escapeVizHtml(marker.cell_index)}</span>
        <span>similarity: ${escapeVizHtml(similarity)}</span>
        <span>${escapeVizHtml(viz.color.value)}: ${escapeVizHtml(marker.point.color)}</span>
    `;
    positionTooltip(event);
}

// 调整提示框位置以便完整显示。
function positionTooltip(event) {
    viz.tooltip.style.left = `${event.offsetX + 14}px`;
    viz.tooltip.style.top = `${event.offsetY + 14}px`;
    viz.tooltip.classList.remove("hidden");
}

// 根据最新数据更新当前状态。
function updateHighlights(detail) {
    const response = detail.response || {};
    const payload = detail.payload || {};
    const results = Array.isArray(response.results) ? response.results : [];
    vizState.topResults = results
        .map((item, index) => ({
            ...item,
            rank: Number.isFinite(Number(item.rank)) ? Number(item.rank) : index + 1,
            cell_index: Number(item.cell_index)
        }))
        .filter((item) => Number.isFinite(item.cell_index));
    vizState.highlights = new Set(vizState.topResults.map((item) => item.cell_index));
    vizState.queryIndex = null;
    // 根据当前状态执行对应处理。
    if (payload.mode === "id" && Number.isFinite(Number(payload.cell_index))) {
        vizState.queryIndex = Number(payload.cell_index);
    } else if (payload.mode === "cell_id" && vizState.topResults.length) {
        const exact = vizState.topResults.find((item) => item.cell_id === payload.cell_id);
        vizState.queryIndex = exact ? exact.cell_index : vizState.topResults[0].cell_index;
    }
    renderLegend(vizState.points);
    drawEmbedding();
    updateVizStatus();
}

// 将数值整理为页面展示格式。
function formatSimilarity(marker) {
    const value = marker.similarity ?? marker.score ?? marker.distance;
    const number = Number(value);
    if (Number.isFinite(number)) {
        return number.toFixed(6);
    }
    // 返回当前函数的处理结果。
    return value ?? "-";
}

// 计算两个点之间的二维距离。
function distanceBetween(a, b) {
    return Math.hypot(a.x - b.x, a.y - b.y);
}

// 转义文本以避免 HTML 解析冲突。
function escapeVizHtml(value) {
    return String(value).replace(/[&<>"']/g, (char) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#039;"
    }[char]));
}

viz.button?.addEventListener("click", () => loadEmbedding(true));
viz.basis?.addEventListener("change", () => loadEmbedding(true));
viz.color?.addEventListener("change", () => loadEmbedding(true));
viz.highlightMode?.addEventListener("change", () => {
    renderLegend(vizState.points);
    drawEmbedding();
    updateVizStatus();
});
viz.canvas?.addEventListener("mousemove", showTooltip);
viz.canvas?.addEventListener("mouseleave", () => viz.tooltip.classList.add("hidden"));
window.addEventListener("resize", drawEmbedding);
window.addEventListener("nk:search-results", (event) => updateHighlights(event.detail));

window.NKVisualization = {
    ensureLoaded,
    loadEmbedding,
    drawEmbedding
};
