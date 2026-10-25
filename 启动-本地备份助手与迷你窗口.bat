@echo off
setlocal
title Super Productivity 本地备份助手与迷你窗口

cd /d "%~dp0local-bridge"

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] 未找到 Python。请确保 Python 3 已安装。
    pause
    exit /b 1
)

echo ========================================================
echo  Super Productivity 增强系统 - 本地助手与迷你窗口
echo  - 监听地址: http://127.0.0.1:4567
echo  - 备份目录: %~dp0local-bridge\backups
echo ========================================================
echo.
python main.py
if errorlevel 1 (
    echo.
    echo [ERROR] 本地助手异常退出。
    pause
)
