@echo off
chcp 65001 >nul
cd /d "C:\Users\yq20772\WorkBuddy\20260330155247"
pyinstaller --clean --noconfirm "考勤管理工具.spec"
