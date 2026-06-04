/* 3DGS Platform frontend app */
const TASKS_API = "/tasks";
const API_KEY = "3dgs-dev-2026";

function apiHeaders() {
    return { "X-API-Key": API_KEY };
}

// Upload form handler
const uploadForm = document.getElementById("upload-form");
if (uploadForm) {
    uploadForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const btn = document.getElementById("submit-btn");
        const result = document.getElementById("result");
        btn.disabled = true;
        btn.textContent = "上传中...";

        const formData = new FormData(uploadForm);
        const fileInput = document.getElementById("file-input");
        const externalCode = document.getElementById("external-code")?.value || "default";
        const metaList = [];
        for (const file of fileInput.files) {
            const buf = await file.arrayBuffer();
            const hash = await crypto.subtle.digest("SHA-256", buf);
            const sha256 = Array.from(new Uint8Array(hash)).map(b => b.toString(16).padStart(2, "0")).join("");
            metaList.push({
                original_filename: file.name,
                sha256: sha256,
                file_size: file.size,
            });
        }
        formData.set("external_code", externalCode);
        formData.set("files_meta", JSON.stringify(metaList));

        try {
            const res = await fetch(TASKS_API, { method: "POST", headers: apiHeaders(), body: formData });
            const data = await res.json();
            if (res.ok) {
                const taskId = data.task_id;
                result.innerHTML = `
                    <p style="color:#22c55e;">上传成功！</p>
                    <p>Task ID: <code>${taskId}</code></p>
                    <button onclick="startTask('${taskId}')" style="margin-top:0.5rem;">启动任务</button>
                    <p><a href="/viewer.html?id=${taskId}">查看进度</a></p>
                `;
            } else {
                result.innerHTML = `<p style="color:#ef4444;">${data.detail || "上传失败"}</p>`;
            }
        } catch (err) {
            result.innerHTML = `<p style="color:#ef4444;">网络错误</p>`;
        }
        btn.disabled = false;
        btn.textContent = "开始训练";
    });
}

async function startTask(taskId) {
    try {
        const res = await fetch(`${TASKS_API}/${taskId}/start`, { method: "POST", headers: apiHeaders() });
        const data = await res.json();
        alert(data.msg || "任务已启动");
        window.location.href = `/viewer.html?id=${taskId}`;
    } catch {
        alert("启动失败");
    }
}
