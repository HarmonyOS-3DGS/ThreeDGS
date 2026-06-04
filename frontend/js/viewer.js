/* 3DGS Viewer integration */
const params = new URLSearchParams(window.location.search);
const projectId = params.get("id");

const info = document.getElementById("viewer-info");
const frame = document.getElementById("viewer-frame");
const API_KEY = "3dgs-dev-2026";

if (!projectId) {
    info.innerHTML = `<p style="color:#ef4444;">请提供 project_id 参数</p>`;
} else {
    info.innerHTML = `<p>Project ID: <code>${projectId}</code></p>`;

    // Connect to SSE for live status
    const evtSource = new EventSource(`/projects/${projectId}/events?X-API-Key=${API_KEY}`);
    evtSource.onmessage = (e) => {
        const data = JSON.parse(e.data);
        info.innerHTML = `
            <p>状态: <span class="status-badge status-${data.status}">${data.status}</span></p>
            <div class="progress-bar">
                <div class="progress-fill" style="width:${data.progress}%">${data.progress}%</div>
            </div>
        `;
        if (data.status === "completed") {
            evtSource.close();
            // Load the 3D model viewer (placeholder - integrate Spark/SuperSplat)
            frame.src = `https://playcanvas.com/viewer?model=${encodeURIComponent(`/api/projects/${projectId}/model`)}`;
        }
    };
    evtSource.onerror = () => {
        info.innerHTML += `<p style="color:#ef4444;">SSE 连接断开</p>`;
    };
}
