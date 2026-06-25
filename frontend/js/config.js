/* 全局配置 — 集中管理 API 地址、鉴权 Token 等常量。
 * 生产环境可通过后端在 index.html 中注入 <script>window.APP_CONFIG = {...}</script>
 * 覆盖默认值。
 */
const APP_CONFIG = window.APP_CONFIG || {
    API_BASE: "/tasks",
    AUTH_URL: "/auth/token",
    DEFAULT_PROJECT_ID: "default",
};

function toBeijingTime(utcStr) {
    if (!utcStr) return "-";
    const d = new Date(utcStr.replace(" ", "T") + "Z");
    const bj = new Date(d.getTime() + 8 * 3600000);
    const pad = n => String(n).padStart(2, "0");
    return `${bj.getUTCFullYear()}-${pad(bj.getUTCMonth() + 1)}-${pad(bj.getUTCDate())} ${pad(bj.getUTCHours())}:${pad(bj.getUTCMinutes())}:${pad(bj.getUTCSeconds())}`;
}
