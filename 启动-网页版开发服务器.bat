@echo off
setlocal
title Super Productivity 网页版开发服务器

pushd "%~dp0"

where node >nul 2>nul
if errorlevel 1 (
    echo [ERROR] 系统未找到 Node.js。
    echo 请安装 Node.js 并确保已加入 PATH。
    pause
    popd
    exit /b 1
)

echo ========================================================
echo  Super Productivity 网页开发服务器正在启动...
echo  - 访问地址: http://localhost:4200
echo ========================================================
echo.

call npm run serve
if errorlevel 1 (
    echo.
    echo [ERROR] 开发服务器启动失败。
    pause
)

popd
