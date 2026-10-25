# GitHub Pages 部署与更新指南

本项目配置了完整的 GitHub Actions CI/CD 流水线，只需将仓库推送到你的 GitHub 账户，即可自动编译并发布到专属于你的固定 GitHub Pages 网页版。

---

## 一、一键启用 GitHub Pages 步骤

### 1. 创建你的 GitHub 仓库
1. 登录 GitHub，点击右上角 `+` -> `New repository`。
2. 建议仓库命名为 `super-productivity`。
3. 可选择 `Private`（私有）或 `Public`（公开）。
   - **注意**：由于个人任务数据仅保存在你的浏览器本地 IndexedDB 中，仓库代码即便公开也不会泄露你的日程和任务；但为了最大化安全性，建议使用个人 Private 仓库（GitHub 现已支持免费版 Private 仓库启用 GitHub Pages）。

### 2. 推送代码至 GitHub
在本地项目根目录 `F:\新学习资料分站\软件\github-super productivity` 下执行：
```bash
git remote set-url origin https://github.com/tokewer/super-productivity.git
git branch -M master
git add .
git commit -m "feat: complete enhanced super productivity system"
git push -u origin master
```

### 3. 配置仓库 GitHub Pages 权限
1. 打开 GitHub 仓库页面，点击顶部 `Settings`。
2. 在左侧菜单点击 `Pages`。
3. 在 **Build and deployment** 下的 **Source** 下拉菜单中，选择：
   👉 **`GitHub Actions`**（不要选择 Deploy from a branch）。
4. 保存即可。

### 4. 自动触发构建与发布
- 每次向 `master` 分支推送代码，`.github/workflows/deploy-gh-pages.yml` 会自动触发。
- 你也可以在仓库页面点击 `Actions` 标签 -> 选择 `Deploy Super Productivity Web to GitHub Pages` -> 点击 `Run workflow` 手动触发。
- 构建完成后，访问地址为：
  `https://tokewer.github.io/super-productivity/`

---

## 二、SPA 单页路由与防 404 处理

由于 GitHub Pages 默认仅服务静态静态文件，在子路由（例如 `/settings` 或刷新页面）时原生服务器会报 404。
我们在构建流水线中特别增加了：
```bash
cp dist/browser/index.html dist/browser/404.html
```
当浏览器刷新任何前端页面时，GitHub Pages 会回退至 `404.html`，由 Angular 内部路由接管，确保刷新和浏览器重启后状态正常保持。

---

## 三、版本更新与兼容性

1. **上游官方版本同步**：
   ```bash
   git remote add upstream https://github.com/super-productivity/super-productivity.git
   git fetch upstream
   git merge upstream/master
   git push origin master
   ```
2. **数据兼容性保障**：
   - Super Productivity 具备完善的内部数据迁移机制（Operation Log Schema Migrations），升级前端版本不会损坏已有的 IndexedDB 数据库。
   - 本地助手会持续在本地磁盘保留快照，更新前随时可导出或通过本地助手验证备份。
