@echo off
setlocal
title Super Productivity - 配置开机自启动

echo =======================================================
echo  Super Productivity 本地桥接 - 配置开机自启动
echo =======================================================
echo.

set "SCRIPT_DIR=%~dp0"
set "TARGET=%SCRIPT_DIR%start_service_hidden.vbs"
set "STARTUP_FOLDER=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "SHORTCUT=%STARTUP_FOLDER%\SuperProductivityBridge.lnk"

powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%SHORTCUT%'); $s.TargetPath = '%TARGET%'; $s.WorkingDirectory = '%SCRIPT_DIR%'; $s.Save()"

if exist "%SHORTCUT%" (
    echo [OK] 已成功在 Windows 开机自启文件夹创建快捷方式:
    echo      %SHORTCUT%
    echo 电脑重启后将自动在后台启动桥接助手与迷你窗口。
) else (
    echo [ERROR] 创建开机自启快捷方式失败。
)

echo.
pause
