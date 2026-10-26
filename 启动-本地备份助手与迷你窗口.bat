@echo off
setlocal
title Super Productivity 本地备份助手与迷你窗口

pushd "%~dp0local-bridge"

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] 系统未找到 Python。
    echo 请安装 Python 3 并确保在安装时勾选了 "Add python.exe to PATH"。
    pause
    popd
    exit /b 1
)

echo ========================================================
echo  Super Productivity 增强系统 - 本地助手与迷你窗口
echo  - 监听地址: http://127.0.0.1:4567
echo  - 备份目录: %~dp0local-bridge\backups
echo ========================================================
echo.

python main.py %*
if errorlevel 1 (
    echo.
    echo [ERROR] 本地助手已退出。
    pause
)

popd
