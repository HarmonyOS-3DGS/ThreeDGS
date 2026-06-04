/* 3DGS Platform frontend app */
const API_BASE = "/upload";
const PROJECTS_API = "/projects";
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
        try {
            const res = await fetch(API_BASE, { method: "POST", headers: apiHeaders(), body: formData });
            const data = await res.json();
            if (res.ok) {
                result.innerHTML = `
                    <p style="color:#22c55e;">✅ 上传成功！</p>
                    <p>Project ID: <code>${data.id}</code></p>
                    <p><a href="/viewer.html?id=${data.id}">查看 3D 场景</a></p>
                `;
            } else {
                result.innerHTML = `<p style="color:#ef4444;">❌ ${data.detail || "上传失败"}</p>`;
            }
        } catch (err) {
            result.innerHTML = `<p style="color:#ef4444;">❌ 网络错误</p>`;
        }
        btn.disabled = false;
        btn.textContent = "开始训练";
    });
}

// Project list on status page
const projectList = document.getElementById("project-list");
if (projectList) {
    async function loadProjects() {
        try {
            const res = await fetch(PROJECTS_API, { headers: apiHeaders() });
            const data = await res.json();
            if (!data.items || data.items.length === 0) {
                projectList.innerHTML = `<li style="text-align:center;color:#64748b;">暂无任务</li>`;
                return;
            }
            projectList.innerHTML = data.items.map(p => `
                <li class="project-item">
                    <div>
                        <strong>${p.name}</strong>
                        <div style="font-size:0.8rem;color:#64748b;margin-top:0.25rem;">
                            ${new Date(p.created_at).toLocaleString()}
                        </div>
                    </div>
                    <div style="text-align:right;">
                        <span class="status-badge status-${p.status}">${p.status}</span>
                        <div class="progress-bar" style="width:120px;margin-top:0.5rem;">
                            <div class="progress-fill" style="width:${p.progress}%">${p.progress}%</div>
                        </div>
                        ${p.status === "completed" ? `<a href="/viewer.html?id=${p.id}">查看</a>` : ""}
                    </div>
                </li>
            `).join("");
        } catch {
            projectList.innerHTML = `<li style="text-align:center;color:#ef4444;">加载失败</li>`;
        }
    }
    loadProjects();
    setInterval(loadProjects, 3000);
}
