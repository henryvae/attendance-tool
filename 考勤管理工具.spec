# -*- mode: python ; coding: utf-8 -*-
import os
import sys

# Playwright 完整 Chromium 路径（打包时使用 ms-playwright 中的真实路径）
# Playwright 1.58 对应 chromium-1208。运行时用 executable_path 直接指向 chrome.exe，
# 不依赖 headless-shell（headless-shell 在部分环境会 launch 卡死，已弃用）。
CHROME_SRC = os.path.join(
    os.environ.get('LOCALAPPDATA', ''),
    'ms-playwright', 'chromium-1208'
)

# 打包目标路径：运行时代码用 executable_path 指向该目录下的 chrome.exe
CHROME_DST = 'playwright/driver/package/.local-browsers/chromium-1208'

datas = []
if os.path.exists(CHROME_SRC):
    print(f"[spec] 找到完整 Chromium: {CHROME_SRC}")
    datas.append((CHROME_SRC, CHROME_DST))
else:
    print(f"[spec] 警告：未找到完整 Chromium: {CHROME_SRC}")

a = Analysis(
    ['attendance_tool.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=['PyQt5.sip', 'PyQt5.QtCore', 'PyQt5.QtGui', 'PyQt5.QtWidgets', 'requests', 'bs4', 'lxml', 'lxml.etree', 'urllib3', 'playwright', 'asyncio', 'json', 'glob'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='考勤管理工具',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
