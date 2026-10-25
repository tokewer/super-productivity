@echo off
setlocal
echo =======================================================
echo  Super Productivity 本地桥接 - 移除开机自启动
echo =======================================================
echo.

set "SHORTCUT=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\SuperProductivityBridge.lnk"

if exist "%SHORTCUT%" (
    del "%SHORTCUT%"
    echo [OK] 已移除开机自启快捷方式。
) else (
    echo [INFO] 未检测到开机自启快捷方式，无需处理。
)

echo.
pause
