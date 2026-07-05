@echo off
cd /d "%~dp0"
chcp 65001>nul
title 鲍鱼数据分析系统
color 0A

echo ===== 鲍鱼数据分析系统 一键启动 =====
echo.

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未检测到Python，请先安装Python 3
    pause
    exit /b 1
)

echo [1/3] Python 环境检查通过
echo [2/3] 启动后端服务...

netstat -ano | findstr ":5000 " >nul 2>&1
if %errorlevel% equ 0 (
    echo [提示] 端口 5000 已被占用，跳过启动
    goto OPEN_BROWSER
)

start "鲍鱼数据系统" cmd /c python server.py

echo 等待服务器启动...
for /l %%i in (1,1,10) do (
    >nul 2>&1 timeout /t 1
    >nul 2>&1 netstat -ano | findstr ":5000 " && goto OPEN_BROWSER
)

:OPEN_BROWSER
echo [3/3] 打开浏览器...
start http://localhost:5000

echo.
echo 服务已启动！浏览器将自动打开 http://localhost:5000
echo 关闭服务端窗口即可停止服务器
echo.
pause