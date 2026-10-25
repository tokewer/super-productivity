# 数据自动备份与灾难恢复手册

数据安全是个人长期使用生产力系统的生命线。本文档详细说明本地自动备份机制、备份文件结构与灾难恢复实操流程。

---

## 一、自动备份系统的工作原理

1. **自动生成机制**：
   - 网页端开启时，后台调度器默认每 15 分钟检查一次是否有变动，并生成一份带时间戳的完整快照。
   - 网页关闭前（`beforeunload` 事件触发），通过 `sendBeacon` 发送当前最终状态。
   - 随时可通过桌面迷你窗口上的 **💾 备份** 按钮或网页端右下角角标执行即时备份。
2. **安全写入流程**：
   - 数据先写入临时文件 `.tmp_backup_*.json`。
   - 经系统调用 `fsync` 确保数据完全落盘。
   - 计算 SHA-256 哈希值并反向比对，确保无字节损坏。
   - 调用操作系统原子重命名（`os.replace`）正式归档。
3. **备份存储路径**：
   - 默认存放在：`F:\新学习资料分站\软件\github-super productivity\local-bridge\backups\`
   - 文件名格式：`backup_YYYY-MM-DD_HH-MM-SS_<hash8>.json`
   - 索引清单：`backup_index.json`（记录每份备份的哈希、任务数、项目数、时间戳与数据量）。

---

## 二、备份文件有效性检验

本地助手提供了内建的自动校验机制。

### 命令行一键验证全部历史备份：
打开命令行，执行：
```powershell
cd "F:\新学习资料分站\软件\github-super productivity\local-bridge"
python main.py --verify
```
输出示例：
```
Checking 12 backups in F:\新学习资料分站\软件\github-super productivity\local-bridge\backups...
[PASS] backup_2026-10-25_22-15-00_bc2715b9.json -> Verified OK (SHA-256: bc2715b9...)
[PASS] backup_2026-10-25_22-30-00_a81f33e1.json -> Verified OK (SHA-256: a81f33e1...)
Summary: 12/12 valid.
```

---

## 三、灾难恢复实战流程

当遇到换电脑、清空浏览器缓存、误删项目或云端冲突时，按以下步骤恢复数据：

### 场景 A：网页端重新打开时的自动检测恢复（最简方式）
1. 启动本地助手（`run_bridge.bat`）。
2. 在浏览器中打开你的 GitHub Pages 地址（或本地开发网页）。
3. 如果浏览器数据库为空（如新设备或被清理），前端启动程序会自动向本地助手探测最新可用备份，并弹出提示框：
   > `是否从本地备份恢复数据？（生成于：2026/10/25 22:30:00）`
4. 点击 **“确定”**，系统即刻拉取备份数据，并在浏览器中无缝重建所有任务、时间统计、标签、项目与设置。

### 场景 B：日常使用中的手动回滚恢复
1. 在网页版中点击左上角菜单 -> **设置** -> **导入/导出**。
2. 点击 **“从文件导入”**。
3. 在文件选择框中，选择 `local-bridge/backups/` 目录下你需要回滚的特定时间点的 `backup_*.json` 文件。
4. 确认导入，页面将自动刷新并载入所选时间点的完整状态。

### 场景 C：脱机恢复与数据导出
备份文件为标准 JSON 格式，完全遵从 Super Productivity 开放规范。你可以使用任何文本编辑器查看或通过 Python 脚本提取特定的任务和笔记：
```python
import json

with open("backup_2026-10-25_22-30-00_a81f33e1.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# 打印所有任务标题
tasks = data.get("task", {}).get("entities", {})
for task_id, task in tasks.items():
    print(f"[{task.get('timeSpent', 0)//60000} 分钟] {task.get('title')}")
```

---

## 四、安全与保留红线

- **防误清空**：当传入的新备份数据任务数为 0 且项目数为 0 时，系统会判定为“空数据异常”，拒绝生成写入，防止空状态覆盖有效历史数据。
- **保留底线**：即使超过配置的最大保留天数，系统也绝不自动删除最后 1 份有效备份。
- **多副本建议**：你可以随时将 `local-bridge/backups/` 目录复制到移动硬盘、U盘，或配合网盘同步软件进行二次异地备份。
