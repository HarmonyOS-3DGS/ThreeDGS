/* 3DGS Viewer */

function showLoginForm() {
    document.getElementById("auth-client-id").style.display = "";
    document.getElementById("auth-client-secret").style.display = "";
    document.querySelector("#auth-bar button").style.display = "";
    sessionStorage.removeItem("access_token");
    sessionStorage.removeItem("client_id");
}

const origFetch = window.fetch;
window.fetch = function(url, opts) {
    return origFetch(url, opts).then(r => {
        if (r.status === 401 && sessionStorage.getItem("access_token")) {
            showLoginForm();
            document.getElementById("auth-status").textContent = "登录已过期，请重新登录";
        }
        return r;
    });
};

const token = sessionStorage.getItem("access_token");
if (token) {
    const cid = sessionStorage.getItem("client_id") || "";
    document.getElementById("auth-client-id").style.display = "none";
    document.getElementById("auth-client-secret").style.display = "none";
    document.querySelector("#auth-bar button").style.display = "none";
    document.getElementById("auth-status").textContent = cid ? `已登录: ${cid}` : "已登录";
}

const params = new URLSearchParams(window.location.search);
const taskId = params.get("id");
const projectId = params.get("projectId") || "default";

const info = document.getElementById("viewer-info");
const frame = document.getElementById("viewer-frame");

function getToken() {
    return sessionStorage.getItem("access_token") || "";
}

async function login() {
    const cid = document.getElementById("auth-client-id")?.value;
    const secret = document.getElementById("auth-client-secret")?.value;
    if (!cid || !secret) return;
    const basic = btoa(`${cid}:${secret}`);
    const res = await fetch(`/auth/token`, {
        method: "POST",
        headers: { "Authorization": `Basic ${basic}` },
    });
    if (!res.ok) {
        const el = document.getElementById("auth-status");
        if (el) el.textContent = "登录失败";
        return;
    }
    const data = await res.json();
    sessionStorage.setItem("access_token", data.access_token);
    sessionStorage.setItem("client_id", cid);
    document.getElementById("auth-client-id").style.display = "none";
    document.getElementById("auth-client-secret").style.display = "none";
    document.querySelector("#auth-bar button").style.display = "none";
    const el = document.getElementById("auth-status");
    if (el) el.textContent = `已登录: ${cid}`;
    if (taskId) setupSSE();
}

if (!taskId) {
    info.innerHTML = `<p style="color:#ef4444;">请提供 id 参数</p>`;
} else {
    info.innerHTML = `<p>Task: <code>${taskId}</code> | 连接中...</p>`;

    function setupSSE() {
        const token = getToken();
        if (!token) return;
        const url = `/tasks/${taskId}/events?projectId=${projectId}&Authorization=Bearer ${token}`;
        const es = new EventSource(url);
        let errorShown = false;

        es.addEventListener("status", (e) => {
            const data = JSON.parse(e.data);
            info.innerHTML = `
                <p>Task: <code>${taskId}</code></p>
                <p>状态: <span class="status-badge status-${data.status}">${data.status}</span></p>
                <p>阶段: ${data.stage}</p>
                <div class="progress-bar">
                    <div class="progress-fill" style="width:${data.progress}%">${data.progress}%</div>
                </div>
                <p style="font-size:0.85rem;color:#64748b;">预计剩余: ${data.remainingTime}s</p>
            `;
        });

        es.addEventListener("done", (e) => {
            const data = JSON.parse(e.data);
            es.close();
            if (data.finalStatus === "completed") {
                loadDownloadLinks();
            } else if (data.finalStatus === "failed") {
                loadTaskInfo(true);
            }
        });

        es.addEventListener("error", () => {
            if (!errorShown) {
                errorShown = true;
                info.innerHTML += `<p style="color:#ef4444;">任务不存在或连接失败</p>`;
            }
            es.close();
        });
    }

    async function loadTaskInfo(failed = false) {
        const token = getToken();
        if (!token) return;
        try {
            const res = await fetch(`/tasks/${taskId}`, {
                headers: { "Authorization": `Bearer ${token}`, "projectId": projectId },
            });
            const data = await res.json();
            const failedMsg = failed ? `<p style="color:#ef4444;">任务执行失败: ${data.errorMessage || "未知错误"}</p>` : "";
            info.innerHTML = `
                <p>Task: <code>${taskId}</code></p>
                <p>状态: <span class="status-badge status-${data.status}">${data.status}</span></p>
                <div class="progress-bar">
                    <div class="progress-fill" style="width:${data.progress}%">${data.progress}%</div>
                </div>
                ${failedMsg}
                ${data.downloadInfos && data.downloadInfos.length > 0 ? `
                    <p style="margin-top:1rem;">下载文件:</p>
                    ${data.downloadInfos.map(f =>
                        `<p><a href="${f.url}" target="_blank">${f.fileName}</a></p>`
                    ).join("")}
                ` : `<p style="color:#64748b;">暂无输出文件</p>`}
            `;
        } catch (err) {
            info.innerHTML += `<p style="color:#ef4444;">加载任务信息失败</p>`;
        }
    }

    async function loadDownloadLinks() {
        await loadTaskInfo(false);
    }

    if (getToken()) setupSSE();
}
