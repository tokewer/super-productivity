@echo off
setlocal
title Super Productivity - 取消开机自启动

set "STARTUP_FOLDER=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "SHORTCUT=%STARTUP_FOLDER%\SuperProductivityBridge.lnk"

if exist "%SHORTCUT%" (
    del /f /q "%SHORTCUT%"
    echo [OK] 已删除开机自启快捷方式:
    echo      %SHORTCUT%
) else (
    echo [INFO] 未检测到已配置的自启快捷方式，无需操作。
)

echo.
pause
