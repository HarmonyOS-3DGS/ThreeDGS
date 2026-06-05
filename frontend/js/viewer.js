/* 3DGS Viewer integration */
const params = new URLSearchParams(window.location.search);
const taskId = params.get("id");
const projectId = params.get("projectId") || "default";

const info = document.getElementById("viewer-info");
const AUTH_TOKEN = "3dgs-dev-2026";

if (!taskId) {
    info.innerHTML = `<p style="color:#ef4444;">请提供 id 参数</p>`;
} else {
    info.innerHTML = `<p>Task ID: <code>${taskId}</code></p>`;

    fetch(`/tasks/${taskId}`, {
        headers: { "Authorization": AUTH_TOKEN, "projectId": projectId },
    })
        .then(r => r.json())
        .then(data => {
            info.innerHTML += `
                <p>状态: <span class="status-badge status-${data.status}">${data.status}</span></p>
                <div class="progress-bar">
                    <div class="progress-fill" style="width:${data.progress}%">${data.progress}%</div>
                </div>
            `;
        });

    const evtSource = new EventSource(
        `/tasks/${taskId}/events?projectId=${projectId}&Authorization=${AUTH_TOKEN}`
    );
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
        }
    };
    evtSource.onerror = () => {
        info.innerHTML += `<p style="color:#ef4444;">SSE 连接断开</p>`;
    };
}
