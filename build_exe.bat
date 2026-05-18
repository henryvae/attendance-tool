@echo off
chcp 65001 > nul
echo ============================================
echo   考勤管理工具 - 打包为 EXE  (v3.0)
echo ============================================
echo.

cd /d "%~dp0"

echo [0/3] 清理旧文件...
if exist "dist\考勤管理工具.exe" (
    del /f /q "dist\考勤管理工具.exe" 2>nul
    echo 已清理旧版本
)
if exist "build" (
    rmdir /s /q build 2>nul
    echo 已清理 build 目录
)

echo [1/3] 检查依赖...
python -c "import PyQt5, requests, bs4, lxml, playwright" 2>nul
if errorlevel 1 (
    echo 安装缺少的依赖...
    pip install PyQt5 requests beautifulsoup4 lxml playwright ^
        -i https://pypi.tuna.tsinghua.edu.cn/simple
)

echo [2/3] 开始打包...
pyinstaller ^
    --onefile ^
    --windowed ^
    --name "考勤管理工具" ^
    --hidden-import PyQt5.sip ^
    --hidden-import PyQt5.QtCore ^
    --hidden-import PyQt5.QtGui ^
    --hidden-import PyQt5.QtWidgets ^
    --hidden-import requests ^
    --hidden-import bs4 ^
    --hidden-import lxml ^
    --hidden-import lxml.etree ^
    --hidden-import urllib3 ^
    --hidden-import playwright ^
    --hidden-import asyncio ^
    --hidden-import json ^
    --hidden-import glob ^
    --clean ^
    attendance_tool.py

echo.
if exist "dist\考勤管理工具.exe" (
    echo [3/3] 打包成功！
    echo.
    echo ✅ 输出文件：dist\考勤管理工具.exe
    echo.
    explorer dist
) else (
    echo [错误] 打包失败，请查看上方错误信息。
)

pause
