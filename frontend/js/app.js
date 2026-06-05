/* 3DGS Platform frontend app */
const TASKS_API = "/tasks";
const AUTH_TOKEN = "3dgs-dev-2026";

function apiHeaders() {
    return { "Authorization": AUTH_TOKEN };
}

// Upload form handler
const uploadForm = document.getElementById("upload-form");
if (uploadForm) {
    uploadForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const btn = document.getElementById("submit-btn");
        const result = document.getElementById("result");
        btn.disabled = true;
        btn.textContent = "提交中...";

        const projectId = document.getElementById("project-id").value.trim();
        const externalCode = document.getElementById("external-code").value.trim();
        const scene = document.getElementById("scene").value;
        const fileInput = document.getElementById("file-input");
        const file = fileInput.files[0];

        if (!file) {
            result.innerHTML = `<p style="color:#ef4444;">请选择文件</p>`;
            btn.disabled = false;
            btn.textContent = "创建任务";
            return;
        }

        const buf = await file.arrayBuffer();
        const hash = await crypto.subtle.digest("SHA-256", buf);
        const sha256 = Array.from(new Uint8Array(hash)).map(b => b.toString(16).padStart(2, "0")).join("");

        const body = {
            externalCode: externalCode,
            fileInfos: [{
                fileName: file.name,
                sha256: sha256,
                contentLength: file.size,
                fileUrl: "",
            }],
            scene: scene,
        };

        try {
            const res = await fetch(TASKS_API, {
                method: "POST",
                headers: { ...apiHeaders(), "Content-Type": "application/json", "projectId": projectId },
                body: JSON.stringify(body),
            });
            const data = await res.json();
            if (res.ok) {
                const taskId = data.taskId;
                result.innerHTML = `
                    <p style="color:#22c55e;">创建成功！</p>
                    <p>Task ID: <code>${taskId}</code></p>
                    <button onclick="startTask('${projectId}','${taskId}')" style="margin-top:0.5rem;">启动任务</button>
                    <p><a href="/viewer.html?id=${taskId}&projectId=${projectId}">查看进度</a></p>
                `;
            } else {
                const msg = data.detail?.ret?.msg || data.detail || "创建失败";
                result.innerHTML = `<p style="color:#ef4444;">${msg}</p>`;
            }
        } catch (err) {
            result.innerHTML = `<p style="color:#ef4444;">网络错误</p>`;
        }
        btn.disabled = false;
        btn.textContent = "创建任务";
    });
}

async function startTask(projectId, taskId) {
    try {
        const res = await fetch(`${TASKS_API}/${taskId}/start`, {
            method: "POST",
            headers: { "Authorization": AUTH_TOKEN, "projectId": projectId },
        });
        const data = await res.json();
        alert(data.ret?.msg || "任务已启动");
        window.location.href = `/viewer.html?id=${taskId}&projectId=${projectId}`;
    } catch {
        alert("启动失败");
    }
}
