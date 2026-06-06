@echo off
echo ========================================
echo 修复串口占用问题
echo ========================================
echo.

echo [1/3] 停止所有Python进程...
taskkill /F /IM python.exe 2>nul
timeout /t 2 /nobreak >nul

echo.
echo [2/3] 等待串口释放...
timeout /t 3 /nobreak >nul

echo.
echo [3/3] 重启后端服务...
start "Health Backend" cmd /c "cd /d %~dp0.. && python run.py"

echo.
echo ========================================
echo 完成！后端正在启动...
echo 请等待10秒后检查手机APP
echo ========================================
pause
