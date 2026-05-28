@echo off
chcp 65001 > nul
echo ============================================
echo   考勤管理工具 - 打包为 EXE
echo ============================================
echo.

cd /d "%~dp0"

echo [0/4] 自动递增版本号...
for /f "delims=" %%i in ('python increment_version.py') do echo        %%i

echo [1/4] 清理旧文件...
if exist "dist\考勤管理工具.exe" (
    del /f /q "dist\考勤管理工具.exe" 2>nul
    echo 已清理旧版本
)
if exist "build" (
    rmdir /s /q build 2>nul
    echo 已清理 build 目录
)

echo [2/4] 检查依赖...
python -c "import PyQt5, requests, bs4, lxml, playwright" 2>nul
if errorlevel 1 (
    echo 安装缺少的依赖...
    pip install PyQt5 requests beautifulsoup4 lxml playwright ^
        -i https://pypi.tuna.tsinghua.edu.cn/simple
)

echo [3/4] 开始打包（使用 spec 文件）...
pyinstaller --clean --noconfirm "考勤管理工具.spec"

echo.
if exist "dist\考勤管理工具.exe" (
    echo [4/4] 打包成功！
    echo.
    echo ✅ 输出文件：dist\考勤管理工具.exe
    echo.
    explorer dist
) else (
    echo [错误] 打包失败，请查看上方错误信息。
)

pause
