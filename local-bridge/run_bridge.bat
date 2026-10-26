@echo off
setlocal
title Super Productivity 本地桥接助手与迷你窗口

pushd "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] 系统未找到 Python。请确保 Python 3 已安装并添加到 PATH。
    pause
    popd
    exit /b 1
)

echo [INFO] 正在启动 Super Productivity 本地助手...
echo [INFO] 桥接接口监听地址: http://127.0.0.1:4567
echo.

python main.py %*
if errorlevel 1 (
    echo.
    echo [ERROR] 程序异常退出。
    pause
)

popd
