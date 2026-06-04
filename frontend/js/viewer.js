/* 3DGS Viewer integration */
const params = new URLSearchParams(window.location.search);
const taskId = params.get("id");

const info = document.getElementById("viewer-info");
const frame = document.getElementById("viewer-frame");
const API_KEY = "3dgs-dev-2026";

if (!taskId) {
    info.innerHTML = `<p style="color:#ef4444;">请提供 task_id 参数</p>`;
} else {
    info.innerHTML = `<p>Task ID: <code>${taskId}</code></p>`;

    // Query task status on load
    fetch(`/tasks/${taskId}`, { headers: { "X-API-Key": API_KEY } })
        .then(r => r.json())
        .then(data => {
            info.innerHTML += `
                <p>状态: <span class="status-badge status-${data.status}">${data.status}</span></p>
                <div class="progress-bar">
                    <div class="progress-fill" style="width:${data.progress}%">${data.progress}%</div>
                </div>
            `;
        });

    // Connect to SSE for live status
    const evtSource = new EventSource(`/tasks/${taskId}/events?X-API-Key=${API_KEY}`);
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
            frame.src = `/viewer.html?model=${encodeURIComponent(`/tasks/${taskId}/model`)}`;
        }
    };
    evtSource.onerror = () => {
        info.innerHTML += `<p style="color:#ef4444;">SSE 连接断开</p>`;
    };
}
