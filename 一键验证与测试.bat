@echo off
setlocal
title Super Productivity 系统验证与自动化测试

cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] 未找到 Python。
    pause
    exit /b 1
)

echo ========================================================
echo  正在运行 Super Productivity 增强系统自动化测试套件...
echo ========================================================
echo.
python tests/test_local_bridge.py -v
set "TEST_CODE=%ERRORLEVEL%"

echo.
if "%TEST_CODE%"=="0" (
    echo ========================================================
    echo  [PASS] 全部测试通过！系统处于高可用与数据安全就绪状态。
    echo ========================================================
) else (
    echo ========================================================
    echo  [FAIL] 测试发现异常，退出码: %TEST_CODE%
    echo ========================================================
)

echo.
pause
exit /b %TEST_CODE%
