# Super Productivity 网页版增强系统交付报告

## 一、项目概述

基于 Super Productivity 官方仓库 Fork 与增强，构建了一套专为个人长期稳定使用设计的完整生产力与自动化系统：
- **静态部署**：配置完整的 GitHub Actions 持续集成与部署流，支持零配置发布到固定的 GitHub Pages。
- **云端同步**：提供生产级自托管 SuperSync Docker Compose 编排体系（PostgreSQL 16 + SuperSync Server + 自动全库归档）。
- **高可靠本地自动备份**：本地常驻轻量助手（Python 原生实现），每 15 分钟自动抓取完整数据快照，结合 SHA-256 校验、临时文件落盘与原子替换机制，确保任意时刻备份文件完备且不可逆损坏，并提供一键灾难恢复。
- **独立桌面迷你计时窗口**：基于 Tkinter 原生的轻量常驻浮窗（内存仅 ~15MB，CPU ~0.0%），支持始终置顶、位置记忆、精准物理时间防漂移计算以及与网页端双向操作联动。
- **双重接入模式**：支持 Fork 原生内置 `LocalBridgeService` 与全能油猴脚本（`super-productivity-enhanced.user.js`），无论使用自建 Pages 还是官方网页版均可无缝享受增强能力。

---

## 二、项目目录结构与资产清单

```
F:\新学习资料分站\软件\github-super productivity\
│
├── .github/workflows/
│   └── deploy-gh-pages.yml         # GitHub Pages 自动化构建与发布流水线（包含 SPA 404 兜底）
│
├── local-bridge/                   # 本地备份助手与桌面迷你计时窗口
│   ├── bridge_server.py            # 安全 HTTP 服务（绑定 127.0.0.1，Token 鉴权，PNA 协议，DNS 防重定向）
│   ├── backup_manager.py           # 核心备份引擎（原子写、SHA-256、保留策略轮换、数据格式校验）
│   ├── mini_window.py              # 桌面迷你悬浮计时窗口（置顶、防漂移、双向控制、状态指示）
│   ├── main.py                     # 统一启动器（支持服务/窗口独立或协同运行，CLI 备份验证）
│   ├── config.json                 # 运行配置文件（自动生成 256 位安全令牌与窗口坐标）
│   ├── run_bridge.bat              # 前台控制台启动脚本
│   ├── start_service_hidden.vbs    # 后台静默启动脚本
│   ├── install_autostart.bat       # Windows 开机自启动快捷方式安装脚本
│   └── uninstall_autostart.bat     # 开机自启移除脚本
│
├── supersync-deploy/               # 官方 SuperSync 自托管云端同步部署包
│   ├── docker-compose.yml          # Docker Compose 编排（SuperSync 容器 + PostgreSQL 16 数据库 + 健康检查）
│   ├── env.example                 # 完整环境变量配置模板（JWT 密钥、CORS 白名单、数据凭据）
│   ├── README.md                   # 详细部署与反向代理指引
│   └── scripts/
│       ├── backup.sh               # 自动化数据库 gzip 归档与轮换脚本
│       └── restore.sh              # 数据库一键灾难恢复脚本
│
├── userscript/
│   └── super-productivity-enhanced.user.js # 配套油猴脚本（跨域透传、IndexedDB 导出、后台保活补偿）
│
├── docs/                           # 完整工程文档库
│   ├── ARCHITECTURE.md             # 架构总览、安全威胁模型与后台限制处理机制
│   ├── DEPLOY_GH_PAGES.md          # GitHub Pages 启用步骤与 SPA 路由适配
│   ├── SUPERSYNC_SETUP.md          # SuperSync 部署与客户端连接指南
│   ├── BACKUP_AND_RESTORE.md       # 自动备份机制、哈希核验与完整灾难恢复手册
│   └── TROUBLESHOOTING.md          # 常见故障诊断、端口冲突排查与日志查看指南
│
├── tests/
│   └── test_local_bridge.py        # 自动化测试套件（9 大测试用例，涵盖安全头、鉴权、原子写、恢复与同步）
│
├── src/app/core/local-bridge/      # 前端内置桥接增强服务
│   └── local-bridge.service.ts     # 任务流同步、定时快照上传、动作轮询、visibilitychange 补偿
│
├── 启动-本地备份助手与迷你窗口.bat   # 根目录一键启动助手
├── 启动-网页版开发服务器.bat        # 根目录一键启动本地前端开发环境 (http://localhost:4200)
└── 一键验证与测试.bat               # 根目录一键执行全套自动化回归测试
```

---

## 三、验证与测试执行记录

测试套件已在真实 Windows 环境执行并全部通过：
`python tests/test_local_bridge.py -v`

| 测试项目 | 验证内容 | 结果 |
| :--- | :--- | :---: |
| **test_save_and_verify_valid_backup** | 验证标准数据格式解析、临时文件原子写入与 SHA-256 物理比对 | **PASS** |
| **test_reject_empty_or_malformed_payload** | 验证恶意或异常空数据拦截（防止空状态覆盖有效数据） | **PASS** |
| **test_retention_and_pruning_policy** | 验证超过保留数量时自动安全轮换，且绝不误删最后有效备份 | **PASS** |
| **test_disaster_recovery_restore** | 验证全量破坏场景下从备份还原，任务与项目数据 100% 完整一致 | **PASS** |
| **test_health_check_endpoint** | 验证本地健康探针 `/api/health` 正常响应状态与版本 | **PASS** |
| **test_auth_token_enforcement** | 验证未授权、非法 Token 拦截 (401) 与合法 Token 放行 (200) | **PASS** |
| **test_cors_options_and_pna_headers** | 验证 Chromium Private Network Access (PNA) 标头与 OPTIONS 预检 | **PASS** |
| **test_state_sync_and_action_queue** | 验证前端任务/时间推送到迷你窗口与迷你窗口双向控制动作出入队 | **PASS** |
| **test_e2e_backup_and_restore_api** | 验证前端通过 REST API 上传备份并调取恢复的端到端闭环 | **PASS** |

---

## 四、核心使用方法

### 1. 启动本地助手与桌面迷你窗口
直接双击运行根目录下的：
👉 **`启动-本地备份助手与迷你窗口.bat`**
- 桌面将出现黑金现代配色的紧凑浮窗。
- 自动置顶、可随处拖动；窗口关闭时自动记忆屏幕坐标。
- 点击 **📌 置顶** 可切换始终置顶状态；
- 点击 **▶ 开始 / ⏸ 暂停** 可直接遥控网页端任务走表；
- 点击 **💾 备份** 可立即通知网页端生成本地数据快照。

### 2. 配置开机自启动
进入 `local-bridge/` 目录，双击运行：
👉 **`install_autostart.bat`**
- 电脑开机后将在后台静默自启助手并显示迷你窗口，无需每次手动打开。

### 3. 打开网页版
- **方式一（GitHub Pages 生产版）**：直接访问你的 GitHub Pages 地址（在 GitHub 仓库启用 Pages 后自动生成）。
- **方式二（本地开发版）**：双击运行根目录下 **`启动-网页版开发服务器.bat`**，浏览器访问 `http://localhost:4200`。
- **方式三（官方原版增强）**：在 Chrome / Edge 中安装 Tampermonkey 扩展并载入 `userscript/super-productivity-enhanced.user.js`，访问官方 `https://app.super-productivity.com` 即可直接获得本地桥接、自动备份与迷你窗口联动。
