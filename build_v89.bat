@echo off
cd /d "C:\Users\yq20772\WorkBuddy\20260330155247"
python -m PyInstaller --clean --noconfirm "考勤管理工具.spec" > build_log_v89.txt 2>&1
echo Build exit: %ERRORLEVEL% >> build_log_v89.txt
