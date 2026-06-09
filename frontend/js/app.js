/* 3DGS Platform frontend */
const API = APP_CONFIG.API_BASE;
const AUTH_TOKEN = APP_CONFIG.AUTH_TOKEN;

function apiHeaders(projectId) {
    return { "Authorization": AUTH_TOKEN, "projectId": projectId };
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

    uploadForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const btn = document.getElementById("submit-btn");
        const result = document.getElementById("result");
        btn.disabled = true;
        btn.textContent = "提交中...";

        const projectId = document.getElementById("project-id").value.trim();
        const externalCode = document.getElementById("external-code").value.trim();
        const scene = document.getElementById("scene").value;
        const fileType = document.getElementById("file-type").value;
        const fileInput = getActiveInput();

        if (!fileInput.files.length) {
            result.innerHTML = `<p style="color:#ef4444;">请选择文件</p>`;
            btn.disabled = false;
            btn.textContent = "创建任务";
            return;
        }

        const formData = new FormData();
        formData.append("externalCode", externalCode);
        formData.append("scene", scene);

        const metaList = [];
        for (const file of fileInput.files) {
            const buf = await file.arrayBuffer();
            const hash = await crypto.subtle.digest("SHA-256", buf);
            const sha256 = Array.from(new Uint8Array(hash)).map(b => b.toString(16).padStart(2, "0")).join("");
            metaList.push({
                fileName: file.name,
                sha256: sha256,
                contentLength: file.size,
                fileUrl: "",
                fileRole: fileType,
            });
            formData.append("files", file);
        }
        formData.append("filesMeta", JSON.stringify(metaList));

        try {
            const res = await fetch(API, {
                method: "POST",
                headers: { "Authorization": AUTH_TOKEN, "projectId": projectId },
                body: formData,
            });
            const data = await res.json();
            if (res.ok) {
                const taskId = data.taskId;
                result.innerHTML = `
                    <p style="color:#22c55e;">任务创建成功: <code>${taskId}</code></p>
                    <button onclick="startTask('${projectId}','${taskId}', this)">启动训练</button>
                    <span id="preview-status" style="margin-left:1rem;font-size:0.85rem;color:#64748b;"></span>
                `;
                // Start polling task status
                pollTask(projectId, taskId, "preview-status");
            } else {
                const msg = (data.detail?.ret?.msg) || data.detail || "创建失败";
                result.innerHTML = `<p style="color:#ef4444;">${msg}</p>`;
            }
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

    async function loadTasks() {
        try {
            const res = await fetch(API, { headers: apiHeaders(currentProjectId) });
            if (!res.ok) {
                taskList.innerHTML = `<li style="text-align:center;color:#64748b;">无任务 (${res.status})</li>`;
                return;
            }
            const data = await res.json();
            if (!data.items || data.items.length === 0) {
                taskList.innerHTML = `<li style="text-align:center;color:#64748b;">暂无任务 (项目: ${currentProjectId})</li>`;
                return;
            }
            taskList.innerHTML = data.items.map(t => `
                <li class="project-item">
                    <div>
                        <strong>${t.taskId}</strong>
                        <div style="font-size:0.8rem;color:#64748b;margin-top:0.25rem;">
                            ${t.currentStage} · ${t.scene} · 剩余 ${t.remainingTime}s
                        </div>
                    </div>
                    <div style="text-align:right;">
                        <span class="status-badge status-${t.status}">${t.status}</span>
                        <div class="progress-bar" style="width:120px;margin-top:0.5rem;">
                            <div class="progress-fill" style="width:${t.progress}%">${t.progress}%</div>
                        </div>
                        <a href="/viewer.html?id=${t.taskId}&projectId=${currentProjectId}">查看</a>
                    </div>
                </li>
            `).join("");
        } catch {
            taskList.innerHTML = `<li style="text-align:center;color:#ef4444;">加载失败</li>`;
        }
    }
    loadTasks();
    setInterval(loadTasks, 5000);
}
