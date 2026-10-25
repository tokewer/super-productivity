# SuperSync 自托管云端同步部署说明

本项目基于 Super Productivity 官方 SuperSync 服务构建，提供生产可用的 Docker Compose 编排体系。

## 一、架构组成

- **数据库**：PostgreSQL 16（存储操作事件流 Operation Log 与账号元数据）
- **同步服务**：SuperSync Server（基于 Event Sourcing 架构的高性能增量同步）
- **持久化卷**：`supersync_postgres_data`（数据文件持久化）
- **备份系统**：自动化带校验与轮换的 SQL 备份脚本

## 二、部署步骤

### 1. 配置环境变量

复制模板并生成安全凭据：
```bash
cp env.example .env
```
用编辑器修改 `.env`：
- `JWT_SECRET`：必须是高强度随机字符串（可使用 `openssl rand -hex 32`）
- `POSTGRES_PASSWORD`：数据库安全密码
- `CORS_ORIGINS`：必须包含你的前端部署网址（例如 `https://tokewer.github.io`）

### 2. 启动服务

```bash
docker compose up -d
```

### 3. 健康检查

```bash
docker compose ps
curl http://localhost:3000/health
```
输出 `{"status":"ok"}` 即表示启动成功。

### 4. 反向代理与 HTTPS（推荐生产环境使用 Caddy 或 Nginx）

如果部署到公网服务器，建议通过 Caddy 自动申请 Let's Encrypt 证书：
```caddy
sync.yourdomain.com {
    reverse_proxy 127.0.0.1:3000
}
```

## 三、客户端连接配置

1. 打开部署好的 Super Productivity 网页版。
2. 进入 `设置` -> `同步` -> 选择 `SuperSync`。
3. 输入 Base URL：`https://sync.yourdomain.com`（若本地测试填 `http://127.0.0.1:3000`）。
4. 注册/登录账号，获取 Access Token 并启用端到端加密（E2E）。

## 四、自动备份与灾难恢复

- **执行手动备份**：`./scripts/backup.sh`
- **配置定时备份（每日凌晨 3 点）**：
  ```bash
  (crontab -l 2>/dev/null; echo "0 3 * * * /path/to/supersync-deploy/scripts/backup.sh >> /var/log/supersync-backup.log 2>&1") | crontab -
  ```
- **数据恢复**：`./scripts/restore.sh backups/supersync_YYYYMMDD_HHMMSS.sql.gz`
