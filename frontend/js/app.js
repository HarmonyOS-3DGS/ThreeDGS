/* 3DGS Platform frontend */
const API = APP_CONFIG.API_BASE;
let ACCESS_TOKEN = sessionStorage.getItem("access_token");

function showLoginForm() {
    document.querySelectorAll(".auth-field").forEach(el => el.style.display = "");
    const authBtn = document.querySelector(".auth-area button");
    if (authBtn) authBtn.style.display = "";
    ACCESS_TOKEN = null;
    sessionStorage.removeItem("access_token");
    sessionStorage.removeItem("client_id");
}

const origFetch = window.fetch;
window.fetch = function(url, opts) {
    return origFetch(url, opts).then(r => {
        if (r.status === 401) {
            if (ACCESS_TOKEN) {
                showLoginForm();
                document.getElementById("auth-status").textContent = "登录已过期，请重新登录";
            }
            ACCESS_TOKEN = null;
            sessionStorage.removeItem("access_token");
            sessionStorage.removeItem("client_id");
        }
        return r;
    });
};

if (ACCESS_TOKEN) {
    const cid = sessionStorage.getItem("client_id") || "";
    document.querySelectorAll(".auth-field").forEach(el => el.style.display = "none");
    const authBtn2 = document.querySelector(".auth-area button");
    if (authBtn2) authBtn2.style.display = "none";
    document.getElementById("auth-status").textContent = cid ? `已登录: ${cid}` : "已登录";
} else {
    document.getElementById("auth-status").textContent = "";
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
    ACCESS_TOKEN = data.access_token;
    sessionStorage.setItem("access_token", ACCESS_TOKEN);
    sessionStorage.setItem("client_id", cid);
    document.getElementById("auth-client-id").value = "";
    document.getElementById("auth-client-secret").value = "";
    document.querySelectorAll(".auth-field").forEach(el => el.style.display = "none");
    const authBtn2 = document.querySelector(".auth-area button");
    if (authBtn2) authBtn2.style.display = "none";
    const el = document.getElementById("auth-status");
    if (el) el.textContent = `已登录: ${cid}`;
    setTimeout(login, Math.max(60000, (data.expires_in - 300)) * 1000);
}

function apiHeaders(projectId) {
    return { "Authorization": `Bearer ${ACCESS_TOKEN}`, "projectId": projectId };
}

// ====== Upload page ======
const uploadForm = document.getElementById("upload-form");
if (uploadForm) {
    const inputVideo = document.getElementById("file-input-video");
    const inputImages = document.getElementById("file-input-images");

    function getActiveInput() {
        return document.getElementById("file-type").value === "source_images" ? inputImages : inputVideo;
    }

    document.getElementById("file-type").onchange = function () {
        if (this.value === "source_images") {
            inputVideo.style.display = "none";
            inputVideo.value = "";
            inputImages.style.display = "";
        } else {
            inputImages.style.display = "none";
            inputImages.value = "";
            inputVideo.style.display = "";
        }
    };

    window.toggleUploadMode = function () {
        const mode = document.querySelector('input[name="uploadMode"]:checked').value;
        document.getElementById("local-upload-section").style.display = mode === "local" ? "" : "none";
        document.getElementById("server-upload-section").style.display = mode === "server" ? "" : "none";
        if (mode === "server") {
            document.getElementById("file-input-video").value = "";
            document.getElementById("file-input-images").value = "";
        } else {
            document.getElementById("server-file-path").value = "";
        }
        document.getElementById("file-type").value = "source_video";
        document.getElementById("file-type").dispatchEvent(new Event("change"));
    };

    async function handleServerUpload(projectId, externalCode, scene, btn, result) {
        const serverPath = document.getElementById("server-file-path").value.trim();
        const fileType = document.getElementById("file-type").value;
        if (!serverPath) {
            result.innerHTML = `<p style="color:#ef4444;">请输入服务器文件路径</p>`;
            btn.disabled = false;
            btn.textContent = "创建任务";
            return;
        }
        const fileName = serverPath.split(/[\\/]/).pop();
        const fileInfos = [{
            fileName: fileName,
            sha256: "",
            contentLength: 0,
            fileUrl: "",
            fileRole: fileType,
            mimeType: "video/mp4",
        }];
        const res1 = await fetch(API, {
            method: "POST",
            headers: { ...apiHeaders(projectId), "Content-Type": "application/json" },
            body: JSON.stringify({ externalCode, scene, fileInfos }),
        });
        const data = await res1.json();
        if (!res1.ok) {
            const msg = (data.detail?.ret?.msg) || data.detail || "创建失败";
            result.innerHTML = `<p style="color:#ef4444;">${msg}</p>`;
            btn.disabled = false;
            btn.textContent = "创建任务";
            return;
        }
        const taskId = data.taskId;
        if (!data.uploadInfos || data.uploadInfos.length === 0) {
            result.innerHTML = `<p style="color:#ef4444;">后端未返回上传 URL，请联系管理员</p>`;
            btn.disabled = false;
            btn.textContent = "创建任务";
            return;
        }
        result.innerHTML = `
            <p style="color:#22c55e;">任务已创建: <span style="font-family:inherit">${taskId}</span></p>
            <p style="margin-top:1rem;font-weight:bold;">在 M1 服务器上执行以下命令上传文件：</p>
            <pre style="background:#1e293b;color:#e2e8f0;padding:1rem;border-radius:6px;overflow-x:auto;font-size:0.85rem;">
curl -X PUT --data-binary @${serverPath} -H "Content-Type: video/mp4" -w "\\nHTTP %{http_code}\\n" "${data.uploadInfos[0].url}"
            </pre>
            <p style="color:#ef4444;font-size:0.85rem;">⚠️ 预签名 URL 有效期为 1 小时，超时需重新创建任务</p>
            <p style="color:#64748b;font-size:0.85rem;">执行完毕后点击下方按钮启动任务</p>
            <button onclick="startTask('${projectId}','${taskId}', this)">启动训练</button>
            <span id="preview-status" style="margin-left:1rem;font-size:0.85rem;color:#64748b;"></span>
        `;
        pollTask(projectId, taskId, "preview-status");
        btn.disabled = false;
        btn.textContent = "创建任务";
    }

    uploadForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const btn = document.getElementById("submit-btn");
        const result = document.getElementById("result");

        if (!ACCESS_TOKEN) {
            result.innerHTML = `<p style="color:#dc2626;">请先登录后再创建任务</p>`;
            return;
        }

        btn.disabled = true;
        btn.textContent = "提交中...";

        const projectId = document.getElementById("project-id").value.trim();
        const externalCode = document.getElementById("external-code").value.trim();
        const scene = document.getElementById("scene").value;
        const uploadMode = document.querySelector('input[name="uploadMode"]:checked').value;

        if (uploadMode === "server") {
            return handleServerUpload(projectId, externalCode, scene, btn, result);
        }

        const fileType = document.getElementById("file-type").value;
        const fileInput = getActiveInput();
        if (!fileInput.files.length) {
            result.innerHTML = `<p style="color:#ef4444;">请选择文件</p>`;
            btn.disabled = false;
            btn.textContent = "创建任务";
            return;
        }

        const fileInfos = [];
        for (const file of fileInput.files) {
            let sha256 = "";
            if (window.crypto && window.crypto.subtle) {
                const buf = await file.arrayBuffer();
                const hash = await crypto.subtle.digest("SHA-256", buf);
                sha256 = Array.from(new Uint8Array(hash)).map(b => b.toString(16).padStart(2, "0")).join("");
            }
            fileInfos.push({
                fileName: file.name,
                sha256: sha256,
                contentLength: file.size,
                fileUrl: "",
                fileRole: fileType,
                mimeType: file.type || "",
            });
        }

        try {
            const res1 = await fetch(API, {
                method: "POST",
                headers: { ...apiHeaders(projectId), "Content-Type": "application/json" },
                body: JSON.stringify({ externalCode, scene, fileInfos }),
            });
            const data = await res1.json();
            if (!res1.ok) {
                const msg = (data.detail?.ret?.msg) || data.detail || "创建失败";
                result.innerHTML = `<p style="color:#ef4444;">${msg}</p>`;
                btn.disabled = false;
                btn.textContent = "创建任务";
                return;
            }

            const taskId = data.taskId;
            result.innerHTML = `<p style="color:#22c55e;">创建成功: <span style="font-family:inherit">${taskId}</span>，正在上传文件...</p>`;

            const files = fileInput.files;
            let totalLoaded = 0;
            const totalSize = files.length > 1 ? Array.from(files).reduce((s, f) => s + f.size, 0) : 0;

            for (let i = 0; i < files.length; i++) {
                const file = files[i];
                const urlInfo = data.uploadInfos[i];

                try {
                    await new Promise((resolve, reject) => {
                        const xhr = new XMLHttpRequest();
                        let lastUpdate = 0;
                        xhr.upload.onprogress = (e) => {
                            if (!e.lengthComputable) {
                                result.innerHTML = `<p>正在上传 ${file.name}...</p>`;
                                return;
                            }
                            const now = Date.now();
                            if (now - lastUpdate < 100) return;
                            lastUpdate = now;
                            const filePct = Math.round((e.loaded / e.total) * 100);
                            if (files.length === 1) {
                                result.innerHTML = `<p>正在上传 ${file.name}... ${filePct}%</p>`;
                            } else {
                                const partial = totalLoaded + e.loaded;
                                const totalPct = Math.round((partial / totalSize) * 100);
                                result.innerHTML = `<p>总进度 ${totalPct}% (文件 ${i + 1}/${files.length})<br><small>${file.name}: ${filePct}%</small></p>`;
                            }
                        };
                        xhr.onload = () => {
                            if (xhr.status >= 200 && xhr.status < 300) {
                                totalLoaded += file.size;
                                resolve();
                            } else {
                                reject(new Error(`upload failed: ${xhr.status}`));
                            }
                        };
                        xhr.onerror = () => reject(new Error("network error"));
                        xhr.open(urlInfo.method, urlInfo.url);
                        for (const [k, v] of Object.entries(urlInfo.headers || {})) {
                            xhr.setRequestHeader(k, v);
                        }
                        xhr.send(file);
                    });
                } catch (uploadErr) {
                    result.innerHTML = `<p style="color:#ef4444;">文件 ${file.name} 上传失败</p>
                        <button onclick="startTask('${projectId}','${taskId}', this)">跳过上传/启动训练</button>`;
                    btn.disabled = false;
                    btn.textContent = "创建任务";
                    return;
                }
            }

            result.innerHTML = `
                <p style="color:#22c55e;">任务创建成功: <span style="font-family:inherit">${taskId}</span></p>
                <button onclick="startTask('${projectId}','${taskId}', this)">启动训练</button>
                <span id="preview-status" style="margin-left:1rem;font-size:0.85rem;color:#64748b;"></span>
            `;
            pollTask(projectId, taskId, "preview-status");
        } catch (err) {
            result.innerHTML = `<p style="color:#ef4444;">网络错误</p>`;
        }
        btn.disabled = false;
        btn.textContent = "创建任务";
    });
}

function pollTask(projectId, taskId, elId) {
    const el = document.getElementById(elId);
    const timer = setInterval(async () => {
        try {
            const res = await fetch(`${API}/${taskId}`, { headers: apiHeaders(projectId) });
            if (!res.ok) return;
            const data = await res.json();
            if (el) el.textContent = `状态: ${data.status} | 进度: ${data.progress}%`;
            if (data.status === "completed" || data.status === "failed") {
                clearInterval(timer);
            }
        } catch {}
    }, 2000);
    // 页面卸载时清理定时器
    window.addEventListener("beforeunload", () => clearInterval(timer), { once: true });
}

async function startTask(projectId, taskId, btn) {
    btn.disabled = true;
    btn.textContent = "启动中...";
    try {
        const res = await fetch(`${API}/${taskId}/start`, {
            method: "POST",
            headers: apiHeaders(projectId),
        });
        const data = await res.json();
        if (res.ok) {
            btn.textContent = "已启动";
            setTimeout(() => { window.location.href = `/viewer.html?id=${taskId}&projectId=${projectId}`; }, 1000);
        } else {
            const msg = (data.detail?.ret?.msg) || "启动失败";
            btn.textContent = msg;
            btn.disabled = false;
        }
    } catch {
        btn.textContent = "启动失败";
        btn.disabled = false;
    }
}

// ====== Status list page ======
const taskList = document.getElementById("project-list");
if (taskList) {
    let currentProjectId = new URLSearchParams(window.location.search).get("projectId")
        || sessionStorage.getItem("projectId")
        || "default";

    const inputEl = document.getElementById("project-id-input");
    if (inputEl) inputEl.value = currentProjectId;

    window.switchProject = function () {
        const val = document.getElementById("project-id-input").value.trim();
        if (val) {
            currentProjectId = val;
            sessionStorage.setItem("projectId", val);
            loadTasks();
        }
    };

    function stageLabel(t) {
        if (t.status === "processing") return ` / ${t.currentStage}`;
        return "";
    }

    async function loadTasks() {
        try {
            const res = await fetch(API, { headers: apiHeaders(currentProjectId) });
            if (res.status === 401) {
                taskList.innerHTML = `<tr><td colspan="8" class="empty-state">请先登录后再查看任务列表</td></tr>`;
                return;
            }
            if (!res.ok) {
                taskList.innerHTML = `<tr><td colspan="8" class="empty-state">无任务 (${res.status})</td></tr>`;
                return;
            }
            const data = await res.json();
            if (!data.items || data.items.length === 0) {
                taskList.innerHTML = `<tr><td colspan="8" class="empty-state">暂无任务 (项目: ${currentProjectId})</td></tr>`;
                return;
            }
            taskList.innerHTML = data.items.map(t => `
                <tr>
                    <td>${t.taskId}</td>
                    <td>${t.externalCode || "-"}</td>
                    <td>${t.scene}</td>
                    <td><span class="status-badge status-${t.status}">${t.status}</span>${stageLabel(t)}</td>
                    <td>
                        <div class="progress-mini"><div class="progress-mini-fill" style="width:${t.progress}%"></div></div>
                        ${t.progress}%
                    </td>
                    <td style="white-space:nowrap;">${toBeijingTime(t.createdAt)}</td>
                    <td style="white-space:nowrap;">${toBeijingTime(t.updatedAt)}</td>
                    <td><a href="/viewer.html?id=${t.taskId}&projectId=${currentProjectId}">查看</a></td>
                </tr>
            `).join("");
        } catch {
            taskList.innerHTML = `<tr><td colspan="8" class="empty-state">加载失败</td></tr>`;
        }
    }
    loadTasks();
    setInterval(loadTasks, 5000);
}
