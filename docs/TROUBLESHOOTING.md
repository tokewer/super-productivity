# 故障排查与运维诊断指南

本文档汇总了在长期使用过程中的常见问题定位与修复方案。

---

## 一、迷你计时窗口与本地助手问题

### 1. 迷你窗口提示“⚠ 网页未连接”
- **原因**：网页端尚未打开，或本地助手与网页端未建立通信。
- **排查步骤**：
  1. 确认浏览器中已打开 Super Productivity 网页版。
  2. 检查网页端与本地助手是否使用了相同的 `auth_token`：
     - 本地助手 Token 位于：`local-bridge/config.json` 中的 `auth_token` 字段。
     - 网页端若安装了油猴脚本，点击右下角 `[Super Productivity 助手]` 胶囊，确认输入的 Token 与 `config.json` 一致。
  3. 检查浏览器 Console（控制台 F12）是否有网络拦截报错：
     - 若出现 `Private Network Access` 警告，请确保本地助手已启动并正常返回 `Access-Control-Allow-Private-Network: true`。

### 2. 本地服务端口 4567 冲突
- **现象**：`run_bridge.bat` 启动时报错 `OSError: [Errno 10048] 通常每个套接字地址只允许使用一次`。
- **解决方法**：
  1. 打开 `local-bridge/config.json`，修改 `"port": 4568`（或其他空闲端口）。
  2. 重新双击运行 `run_bridge.bat` 即可。

### 3. 开机自启未生效
- **排查步骤**：
  1. 按 `Win + R` 键，输入 `shell:startup` 并回车，检查是否存在 `SuperProductivityBridge.lnk`。
  2. 若不存在，在 `local-bridge` 目录下右键以管理员身份运行 `install_autostart.bat`。

---

## 二、浏览器后台运行与计时精度

### 1. 网页最小化后，计时会不会停止？
- **机制说明**：现代浏览器（Chromium / Edge / Chrome）在页面置于后台一段时间后会降低 `setInterval` 频率以节省资源。
- **解决方案**：
  - 系统使用 **真实墙钟物理时间戳（Wall-clock time delta）**。当切换到后台时，时间以开始时间为基准向前推移；
  - 无论何时切换回前台或刷新，系统瞬间基于毫秒时间戳校准，**绝不遗失任何时长**；
  - 本地迷你浮窗运行在 Python 独立进程中，即便浏览器被最小化，浮窗依然可以实时刷新。

### 2. 浏览器完全关闭时为什么不继续走表？
- 这是出于严肃的学习与工作统计原则。若浏览器关闭后依然盲目累加时间，可能在用户忘记关机或已离开电脑时记录数小时的虚假工作时间。
- 当网页关闭时，系统会诚实显示“网页离线”，并将关闭前的最后状态安全存档。

---

## 三、GitHub Pages 与网络限制

### 1. 打开 GitHub Pages 显示空白或 404
- **排查步骤**：
  1. 确认仓库 `Settings` -> `Pages` 中 Build and deployment Source 设置为 **`GitHub Actions`**。
  2. 确认流水线部署分支与路径正确。
  3. 检查浏览器地址栏路径是否包含仓库名（例如 `https://tokewer.github.io/super-productivity/`）。

### 2. Mixed Content（HTTPS 网页请求 HTTP 本地接口）
- **Chromium / Edge 规范**：Chrome 遵循 Private Network Access (PNA) 规范，允许由受信任的公网 HTTPS 页面调用受限的 `http://127.0.0.1`，前提是本地服务端响应带有 `Access-Control-Allow-Private-Network: true` 的 OPTIONS 预检请求。本项目本地助手已全面支持该规范。
- **油猴脚本双保险**：若使用其他浏览器或特殊安全策略环境，配套油猴脚本使用 `GM_xmlhttpRequest`，该接口在浏览器拓展沙盒中执行，不受同源策略与 Mixed Content 限制。

---

## 四、SuperSync 云端同步排查

### 1. 同步报错：`Sync failed` 或 `Network Error`
- **排查步骤**：
  1. 检查 Docker 容器运行状态：`docker compose ps`。
  2. 检查日志：`docker compose logs supersync --tail=100`。
  3. 确认 `.env` 中 `CORS_ORIGINS` 包含了当前访问的前端完整域名（包含 `https://`）。
  4. 确认反向代理已配置 WebSocket 支持（若启用了 Presence 特性）。
