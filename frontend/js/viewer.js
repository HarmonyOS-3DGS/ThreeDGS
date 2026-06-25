/* Task Detail Viewer */

function showLoginForm() {
    document.querySelectorAll(".auth-field").forEach(el => el.style.display = "");
    const authBtn = document.querySelector(".auth-area button");
    if (authBtn) authBtn.style.display = "";
    sessionStorage.removeItem("access_token");
    sessionStorage.removeItem("client_id");
}

const origFetch = window.fetch;
window.fetch = function(url, opts) {
    return origFetch(url, opts).then(r => {
        if (r.status === 401) {
            if (sessionStorage.getItem("access_token")) {
                showLoginForm();
                document.getElementById("auth-status").textContent = "登录已过期，请重新登录";
            }
            sessionStorage.removeItem("access_token");
            sessionStorage.removeItem("client_id");
        }
        return r;
    });
};

const token = sessionStorage.getItem("access_token");
if (token) {
    const cid = sessionStorage.getItem("client_id") || "";
    document.querySelectorAll(".auth-field").forEach(el => el.style.display = "none");
    document.querySelector(".auth-area button").style.display = "none";
    document.getElementById("auth-status").textContent = cid ? `已登录: ${cid}` : "已登录";
} else {
    document.getElementById("auth-status").textContent = "";
    document.getElementById("viewer-info").innerHTML = `<p class="empty-state">请先登录后查看任务详情</p>`;
}

const params = new URLSearchParams(window.location.search);
const taskId = params.get("id");
const projectId = params.get("projectId") || "default";

const info = document.getElementById("viewer-info");

function getToken() {
    return sessionStorage.getItem("access_token") || "";
}

async function login() {
    const cid = document.getElementById("auth-client-id")?.value;
    const secret = document.getElementById("auth-client-secret")?.value;
    if (!cid || !secret) return;
    const basic = btoa(`${cid}:${secret}`);
    const res = await fetch(APP_CONFIG.AUTH_URL, {
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
    document.querySelectorAll(".auth-field").forEach(el => el.style.display = "none");
    document.querySelector(".auth-area button").style.display = "none";
    const el = document.getElementById("auth-status");
    if (el) el.textContent = `已登录: ${cid}`;
    if (taskId) pollTask();
}

const stageMap = {
    initializing: "等待中", extracting: "帧提取", colmap: "稀疏重建",
    training: "3DGS训练", compressing: "压缩", completed: "完成", failed: "失败",
};
const sceneMap = { commodity: "商品", indoor: "室内", outdoor: "室外" };

function renderInfo(data) {
    const stage = stageMap[data.currentStage] || data.currentStage;
    const scene = sceneMap[data.scene] || data.scene;
    const progress = data.progress || 0;

    info.innerHTML = `
        <div class="detail-grid">
            <div><span class="field-label">任务 ID</span><div class="field-value">${data.taskId}</div></div>
            <div><span class="field-label">外部编码</span><div class="field-value">${data.externalCode || "-"}</div></div>
            <div><span class="field-label">场景</span><div class="field-value">${scene}</div></div>
            <div>
                <span class="field-label">状态</span>
                <div><span class="status-badge status-${data.status}">${data.status}</span>${data.status === "processing" ? ` / ${stage}` : ""}</div>
            </div>
            <div><span class="field-label">创建时间</span><div class="field-value">${toBeijingTime(data.createdAt)}</div></div>
            <div><span class="field-label">更新时间</span><div class="field-value">${toBeijingTime(data.updatedAt)}</div></div>
        </div>
        <div class="detail-progress">
            <span class="field-label">进度</span>
            <div class="progress-bar"><div class="progress-fill" style="width:${progress}%">${progress}%</div></div>
            ${data.status === "processing" ? `<p style="font-size:0.85rem;color:#64748b;margin-top:0.25rem;">预计剩余: ${data.remainingTime}s</p>` : ""}
            ${data.errorMessage ? `<p style="color:#dc2626;font-size:0.85rem;margin-top:0.5rem;">${data.errorMessage}</p>` : ""}
        </div>
        ${data.downloadInfos && data.downloadInfos.length > 0 ? `
        <div class="detail-downloads">
            <span class="field-label">下载文件</span><br>
            ${data.downloadInfos.map(f => `<a href="${f.url}" target="_blank">${f.fileName}</a>`).join("")}
        </div>` : ""}
    `;
}

async function pollTask() {
    const token = getToken();
    if (!token) return;
    try {
        const res = await fetch(`/tasks/${taskId}`, {
            headers: { "Authorization": `Bearer ${token}`, "projectId": projectId },
        });
        if (res.status === 401) {
            info.innerHTML = `<p class="empty-state">登录已过期，请重新登录后查看</p>`;
            return;
        }
        if (!res.ok) throw new Error("fetch failed");
        const data = await res.json();
        renderInfo(data);
        if (data.status === "processing") {
            setTimeout(pollTask, 2000);
        } else {
            setTimeout(pollTask, 5000);
        }
    } catch {
        info.innerHTML = `<p class="empty-state">加载失败，3秒后重试</p>`;
        setTimeout(pollTask, 3000);
    }
}

if (!taskId) {
    info.innerHTML = `<p class="empty-state">请提供 id 参数</p>`;
} else if (getToken()) {
    pollTask();
}
