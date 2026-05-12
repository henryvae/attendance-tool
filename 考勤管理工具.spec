# -*- mode: python ; coding: utf-8 -*-
import os
import sys

# Playwright headless shell 路径（打包时使用 ms-playwright 中的真实路径）
HEADLESS_SRC = os.path.join(
    os.environ.get('LOCALAPPDATA', ''),
    'ms-playwright', 'chromium_headless_shell-1208', 'chrome-headless-shell-win64'
)

# 打包目标路径：必须与 Playwright 期望的路径一致
# Playwright 在 _MEIPASS 下查找: playwright/driver/package/.local-browsers/chromium_headless_shell-1208/chrome-headless-shell-win64
HEADLESS_DST = 'playwright/driver/package/.local-browsers/chromium_headless_shell-1208/chrome-headless-shell-win64'

datas = []
if os.path.exists(HEADLESS_SRC):
    print(f"[spec] 找到 headless shell: {HEADLESS_SRC}")
    datas.append((HEADLESS_SRC, HEADLESS_DST))
else:
    print(f"[spec] 警告：未找到 headless shell: {HEADLESS_SRC}")

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
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
