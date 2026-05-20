const statusBox = document.getElementById("status");
const errorBox = document.getElementById("error-message");
const resultsBody = document.getElementById("results-body");

function showError(message) {
    errorBox.textContent = message || "";
}

async function loadStatus() {
    const response = await fetch("/api/status");
    const data = await response.json();
    statusBox.textContent = JSON.stringify(data, null, 2);
}

function updateModeInputs() {
    const mode = document.getElementById("mode").value;

    document.getElementById("cell-index-row").classList.toggle("hidden", mode !== "id");
    document.getElementById("cell-id-row").classList.toggle("hidden", mode !== "cell_id");
    document.getElementById("vector-row").classList.toggle("hidden", mode !== "vector");
}

function collectPayload() {
    const mode = document.getElementById("mode").value;
    const payload = {
        mode,
        k: Number(document.getElementById("k").value),
        index_type: document.getElementById("index-type").value
    };

    if (mode === "id") {
        payload.cell_index = Number(document.getElementById("cell-index").value);
    }

    if (mode === "cell_id") {
        payload.cell_id = document.getElementById("cell-id").value.trim();
    }

    if (mode === "vector") {
        payload.vector = document.getElementById("vector").value
            .split(",")
            .map(x => Number(x.trim()))
            .filter(x => !Number.isNaN(x));
    }

    return payload;
}

function renderResults(results) {
    if (!results || results.length === 0) {
        resultsBody.innerHTML = `<tr><td colspan="5" class="empty">暂无结果</td></tr>`;
        return;
    }

    resultsBody.innerHTML = results.map(item => {
        const metadata = item.metadata || {};
        const metadataText = Object.entries(metadata)
            .slice(0, 8)
            .map(([key, value]) => `${key}: ${value}`)
            .join("<br>");

        return `
            <tr>
                <td>${item.rank}</td>
                <td>${item.index}</td>
                <td>${item.cell_id}</td>
                <td>${Number(item.similarity).toFixed(6)}</td>
                <td>${metadataText}</td>
            </tr>
        `;
    }).join("");
}

async function doSearch() {
    showError("");

    const payload = collectPayload();

    const response = await fetch("/api/search", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload)
    });

    const data = await response.json();

    if (!response.ok) {
        showError(data.error || "检索失败");
        renderResults([]);
        return;
    }

    renderResults(data.results);
    await loadStatus();
}

document.getElementById("mode").addEventListener("change", updateModeInputs);
document.getElementById("refresh-status").addEventListener("click", loadStatus);
document.getElementById("search-button").addEventListener("click", doSearch);

updateModeInputs();
loadStatus();
