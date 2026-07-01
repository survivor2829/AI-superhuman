@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 正在启动 AI 客户触达助手...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Start-Agent.ps1"
echo.
echo 如果桌面软件没有自动弹出，请打开 http://127.0.0.1:5173
pause
