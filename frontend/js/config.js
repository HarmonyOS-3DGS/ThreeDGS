/* 全局配置 — 集中管理 API 地址、鉴权 Token 等常量。
 * 生产环境可通过后端在 index.html 中注入 <script>window.APP_CONFIG = {...}</script>
 * 覆盖默认值。
 */
const APP_CONFIG = window.APP_CONFIG || {
    API_BASE: "/tasks",
    DEFAULT_PROJECT_ID: "default",
};
