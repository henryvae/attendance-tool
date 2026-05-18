"""
考勤管理工具 - intretech UMS 系统
https://ums.intretech.com/ums/AtteUserReportManage.aspx

v72 - 应下班时间计算修复；加班时间显示格式改为时.分；周加/假加统一逐行累加

v3.0 - 使用 Playwright (Edge) 实现登录和数据抓取，确保 JS 渲染数据完整获取。
字段名已通过真实抓包确认:
- 登录: txtUserName / txtPWD / Button1
- 考勤: setMonthInput / setMonthEndInput / ShowRangeList / ShowTypeList / btn1
"""

import sys
import os
import csv
import datetime

APP_VERSION = "v72"
import json
import asyncio
import threading

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QDateEdit, QGroupBox, QMessageBox, QStatusBar, QFrame,
    QHeaderView, QComboBox, QProgressBar,
    QAbstractItemView, QFileDialog, QCheckBox,
    QSystemTrayIcon, QMenu, QAction, QTimeEdit,
    QStyle,
)
from PyQt5.QtCore import Qt, QDate, QThread, pyqtSignal, QTimer, QTime
from PyQt5.QtNetwork import QLocalServer, QLocalSocket
from PyQt5.QtGui import QFont, QColor, QIcon

# ─────────────────────────────────────────────
#  常量
# ─────────────────────────────────────────────
BASE_URL   = "https://ums.intretech.com/ums"
LOGIN_URL  = f"{BASE_URL}/login.aspx"
ATTEND_URL = f"{BASE_URL}/AtteUserReportManage.aspx"

# Edge 浏览器路径（自动探测）
def _find_edge():
    candidates = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None

EDGE_PATH = _find_edge()

THEME = {
    "primary":    "#1976D2",
    "primary_dk": "#1565C0",
    "accent":     "#42A5F5",
    "bg":         "#F5F7FA",
    "card":       "#FFFFFF",
    "text":       "#212121",
    "text_sec":   "#757575",
    "border":     "#E0E0E0",
    "success":    "#4CAF50",
    "warning":    "#FF9800",
    "danger":     "#F44336",
    "header_bg":  "#1976D2",
    "row_alt":    "#EEF2F8",
}


# ─────────────────────────────────────────────
#  Playwright 核心操作（同步包装）
# ─────────────────────────────────────────────
def _run_async(coro):
    """在新事件循环中同步运行异步函数"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _setup_bundled_browser_env():
    """
    如果是打包后的 exe，把 PLAYWRIGHT_BROWSERS_PATH 指向 _MEIPASS 内的浏览器目录。
    这样 Playwright 会直接从 exe 解压的临时目录找到内置的 chromium_headless_shell。
    返回 True 表示找到内置浏览器，False 表示没有。
    """
    import os
    import sys

    if not getattr(sys, 'frozen', False):
        # 开发环境，不设置环境变量
        return False

    # _MEIPASS 是 PyInstaller 解压的临时目录
    # 我们把浏览器打包在：playwright/driver/package/.local-browsers/
    browsers_path = os.path.join(
        sys._MEIPASS,
        'playwright', 'driver', 'package', '.local-browsers'
    )

    # 验证 headless shell 是否存在
    headless_exe = os.path.join(
        browsers_path,
        'chromium_headless_shell-1208',
        'chrome-headless-shell-win64',
        'chrome-headless-shell.exe'
    )

    if os.path.exists(headless_exe):
        # 设置环境变量，让 Playwright 在这里找浏览器
        os.environ['PLAYWRIGHT_BROWSERS_PATH'] = browsers_path
        print(f"[浏览器] 使用内置 headless shell: {headless_exe}")
        print(f"[浏览器] PLAYWRIGHT_BROWSERS_PATH = {browsers_path}")
        return True
    else:
        print(f"[浏览器] 内置 headless shell 不存在: {headless_exe}")
        return False


def _ensure_playwright_browsers(progress_callback=None):
    """
    确保 Playwright 浏览器已安装。如果未安装，自动安装。
    打包后优先使用内置的 chromium headless shell（通过环境变量指向 _MEIPASS）。

    progress_callback: 进度回调函数，接收字符串消息
    返回 (True, None) 成功，或 (False, error_msg) 失败。
    """
    import subprocess
    import sys
    import os

    # 先检查 playwright 是否已安装
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False, "未安装 Playwright，请先运行：\npip install playwright"

    # 尝试使用内置浏览器（打包后）
    if _setup_bundled_browser_env():
        return True, None

    # 尝试用同步 API 检测已安装的浏览器（开发环境 / 外部浏览器）
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, timeout=8000)
            browser.close()
            print("[浏览器] 使用系统已安装的 Chromium")
            return True, None
    except Exception as e:
        print(f"[浏览器] 系统 Chromium 不可用: {e}")

    # 未安装，尝试下载
    if progress_callback:
        progress_callback("正在下载安装 Chromium 浏览器（首次需几分钟）...")

    # 使用 python -m playwright install
    cmd = [sys.executable, "-m", "playwright", "install", "chromium"]

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        for line in process.stdout:
            line = line.strip()
            if progress_callback and line:
                if "downloading" in line.lower() or "%" in line:
                    progress_callback(line[:100])
            print(f"[Playwright] {line}")

        process.wait()
        if process.returncode == 0:
            print("[浏览器] Chromium 安装成功")
            return True, None
        else:
            return False, "自动安装浏览器失败，请手动运行：\npython -m playwright install chromium"
    except subprocess.TimeoutExpired:
        return False, "安装浏览器超时，请手动运行：\npython -m playwright install chromium"
    except Exception as e:
        return False, f"安装浏览器失败：{e}\n\n请手动运行命令安装：\npython -m playwright install chromium"


async def _async_login(username: str, password: str, install_progress_callback=None):
    """
    用 Playwright 登录，成功返回 cookies 列表；失败返回 (None, error_msg)
    install_progress_callback: 安装浏览器时的进度回调
    """
    from playwright.async_api import async_playwright

    # 确保浏览器已安装
    ok, err = _ensure_playwright_browsers(progress_callback=install_progress_callback)
    if not ok:
        return None, err

    launch_kwargs = dict(
        headless=True,
        args=["--ignore-certificate-errors", "--no-sandbox",
              "--disable-dev-shm-usage"]
    )
    # 使用系统 Edge（如果配置）
    if EDGE_PATH:
        launch_kwargs["executable_path"] = EDGE_PATH

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(**launch_kwargs)
            context = await browser.new_context(ignore_https_errors=True)
            page    = await context.new_page()

            await page.goto(LOGIN_URL, timeout=25000, wait_until="domcontentloaded")
            await page.fill("input[name='txtUserName']", username)
            await page.fill("input[name='txtPWD']",      password)
            await page.click("input[name='Button1']")
            await page.wait_for_load_state("domcontentloaded", timeout=20000)

            cur_url = page.url
            if "login" in cur_url.lower():
                # 检查错误信息
                err_text = ""
                for sel in ["#lblMsg", ".error", ".alert", "span[style*='red']"]:
                    el = await page.query_selector(sel)
                    if el:
                        t = (await el.text_content() or "").strip()
                        if t:
                            err_text = t
                            break
                await browser.close()
                return None, err_text or "用户名或密码错误，请重试。"

            # 保存 cookies
            cookies = await context.cookies()
            await browser.close()
            return cookies, None

    except Exception as e:
        msg = str(e)
        if "Timeout" in msg or "timeout" in msg:
            return None, "连接超时，请确保在公司内网或 VPN 环境下使用。"
        if "Executable" in msg or "executable" in msg:
            return None, "未找到浏览器，正在尝试自动安装..."
        return None, f"登录异常：{e}"


async def _async_fetch(cookies, start_date: str, end_date: str):
    """
    用 Playwright 抓取考勤数据，返回 (headers, rows)
    """
    from playwright.async_api import async_playwright

    # 确保浏览器已安装
    ok, err = _ensure_playwright_browsers()
    if not ok:
        return None, None, err

    launch_kwargs = dict(
        headless=True,
        args=["--ignore-certificate-errors", "--no-sandbox",
              "--disable-dev-shm-usage"]
    )
    if EDGE_PATH:
        launch_kwargs["executable_path"] = EDGE_PATH

    async with async_playwright() as p:
        browser = await p.chromium.launch(**launch_kwargs)
        context = await browser.new_context(ignore_https_errors=True)

        # 恢复 cookies（免登录）
        await context.add_cookies(cookies)

        page = await context.new_page()
        await page.goto(ATTEND_URL, timeout=30000, wait_until="networkidle")

        # 检查是否被重定向到登录页
        if "login" in page.url.lower():
            await browser.close()
            raise Exception("会话已过期，请重新登录。")

        # 设置日期范围（3=自定义）和显示模式（1=列表）
        await page.evaluate("""
            () => {
                var s1 = document.querySelector(
                    "select[name='ctl00$ContentPlaceHolder1$ShowRangeList']");
                if (s1) {
                    s1.value = '3';
                    s1.dispatchEvent(new Event('change', {bubbles: true}));
                }
                var s2 = document.querySelector(
                    "select[name='ctl00$ContentPlaceHolder1$ShowTypeList']");
                if (s2) {
                    s2.value = '1';
                    s2.dispatchEvent(new Event('change', {bubbles: true}));
                }
            }
        """)
        await page.wait_for_timeout(400)

        # 填写日期
        await page.evaluate(f"""
            () => {{
                var d1 = document.querySelector(
                    "input[name='ctl00$ContentPlaceHolder1$setMonthInput']");
                if (d1) d1.value = '{start_date}';
                var d2 = document.querySelector(
                    "input[name='ctl00$ContentPlaceHolder1$setMonthEndInput']");
                if (d2) d2.value = '{end_date}';
            }}
        """)
        await page.wait_for_timeout(300)

        # 点击查询
        await page.click("input[name='ctl00$ContentPlaceHolder1$btn1']")
        await page.wait_for_load_state("domcontentloaded", timeout=30000)
        await page.wait_for_timeout(1000)

        # 解析表格
        headers, rows = await _extract_table(page)
        await browser.close()
        return headers, rows


async def _extract_table(page):
    """从页面中提取考勤数据表格（正确处理跨列单元格）"""
    tables = await page.query_selector_all("table")
    for tbl in tables:
        trs = await tbl.query_selector_all("tr")
        if len(trs) < 2:
            continue
        # 检查表头
        first_cells = await trs[0].query_selector_all("td, th")
        header_texts = [(await c.text_content() or "").strip() for c in first_cells]
        if "工号" in header_texts and "姓名" in header_texts:
            headers = header_texts
            rows = []
            for tr in trs[1:]:
                cells = await tr.query_selector_all("td, th")
                # 获取每个单元格的 colspan 值，并展开跨列单元格
                expanded = []
                for cell in cells:
                    text = (await cell.text_content() or "").strip()
                    # 获取 colspan 属性，默认为 1
                    col_span = await cell.get_attribute("colspan")
                    span = int(col_span) if col_span and col_span.isdigit() else 1
                    # 将跨列单元格展开为多个单元格（内容相同）
                    expanded.extend([text] * span)
                if any(expanded):
                    # 对齐列数
                    while len(expanded) < len(headers):
                        expanded.append("")
                    rows.append(expanded[:len(headers)])
            return headers, rows
    return [], []


# ─────────────────────────────────────────────
#  后台线程
# ─────────────────────────────────────────────
class LoginWorker(QThread):
    success = pyqtSignal(list)    # cookies
    failed  = pyqtSignal(str)
    install_progress = pyqtSignal(str)  # 浏览器安装进度

    def __init__(self, username, password):
        super().__init__()
        self.username = username
        self.password = password

    def run(self):
        try:
            def progress_callback(msg):
                # 在主线程发出进度信号
                self.install_progress.emit(msg)

            cookies, err = _run_async(_async_login(self.username, self.password, progress_callback))
            if cookies:
                self.success.emit(cookies)
            else:
                self.failed.emit(err or "登录失败")
        except Exception as e:
            # 捕获所有异常，确保错误信息传递给用户
            self.failed.emit(f"登录异常：{e}")


class FetchWorker(QThread):
    success  = pyqtSignal(list, list)
    failed   = pyqtSignal(str)
    progress = pyqtSignal(int)

    def __init__(self, cookies, start_date, end_date):
        super().__init__()
        self.cookies    = cookies
        self.start_date = start_date
        self.end_date   = end_date

    def run(self):
        try:
            self.progress.emit(20)
            result = _run_async(
                _async_fetch(self.cookies, self.start_date, self.end_date)
            )
            # 处理浏览器未安装等错误（返回3元素元组）
            if len(result) == 3:
                _, _, err = result
                self.failed.emit(err)
                return
            headers, rows = result
            self.progress.emit(100)
            self.success.emit(headers, rows)
        except Exception as e:
            self.failed.emit(str(e))


def _debug_path():
    """返回调试文件保存路径（桌面或源目录）"""
    import os, sys
    if getattr(sys, '_MEIPASS', None):
        return os.path.join(os.path.expanduser("~"), "Desktop")
    return os.path.dirname(os.path.abspath(__file__))


async def _save_avatar_debug(page, reason: str):
    """保存页面截图和 img 列表到桌面"""
    import os, re
    out_dir = _debug_path()
    os.makedirs(out_dir, exist_ok=True)
    sc_path = os.path.join(out_dir, "avatar_debug.png")
    txt_path = os.path.join(out_dir, "avatar_debug.txt")
    try:
        await page.screenshot(path=sc_path, full_page=False)
        imgs = await page.query_selector_all("img")
        lines = [f"=== 头像抓取调试报告（{reason}）===", f"URL: {page.url}", f"img 数量: {len(imgs)}\n"]
        for i, img in enumerate(imgs):
            src  = await img.get_attribute("src")  or ""
            id_  = await img.get_attribute("id")   or ""
            cls  = await img.get_attribute("class") or ""
            alt  = await img.get_attribute("alt")   or ""
            w    = await img.get_attribute("width")  or ""
            h    = await img.get_attribute("height") or ""
            lines.append(f"[{i}] src={src[:150]!r} | id={id_!r} | class={cls!r} | alt={alt!r} | {w}x{h}")
        content = await page.content()
        body = re.search(r'<body[^>]*>(.*?)</body>', content, re.DOTALL | re.IGNORECASE)
        body_html = body.group(1)[:8000] if body else content[:8000]
        lines.append(f"\n=== body 片段 ===\n{body_html}")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print(f"[头像调试] 截图: {sc_path}\n[头像调试] 报告: {txt_path}")
    except Exception as e:
        print(f"[头像调试] 保存失败: {e}")


async def _async_fetch_avatar(cookies):
    """
    用 Playwright 访问考勤数据页面，抓取用户头像图片。
    返回 bytes（图片字节流），失败返回 None。
    """
    import urllib.request
    from playwright.async_api import async_playwright

    ok, err = _ensure_playwright_browsers()
    if not ok:
        return None

    launch_kwargs = dict(
        headless=True,
        args=["--ignore-certificate-errors", "--no-sandbox", "--disable-dev-shm-usage"]
    )
    if EDGE_PATH:
        launch_kwargs["executable_path"] = EDGE_PATH

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(**launch_kwargs)
            context = await browser.new_context(ignore_https_errors=True)
            await context.add_cookies(cookies)
            page = await context.new_page()

            # 头像在考勤数据页面里
            await page.goto(ATTEND_URL, timeout=30000, wait_until="domcontentloaded")
            await page.wait_for_timeout(2000)

            # Cookie 过期 → 跳转登录页
            if "login" in page.url.lower():
                await _save_avatar_debug(page, "Cookie 过期，跳转登录页")
                await browser.close()
                return None

            # ── 策略1：特定选择器 ──
            avatar_url = None
            selectors = [
                # 侧边栏（攸信）专用选择器
                "#sidebar img",
                ".sidebar img",
                ".leftsidebar img",
                ".nav-sidebar img",
                ".sidebar-user img",
                ".user-panel img",
                "aside img",
                # 通用企业 UMS 选择器
                "img.avatar",
                "img#imgPhoto",
                "img[id*='photo']", "img[id*='Photo']",
                "img[id*='avatar']", "img[id*='Avatar']",
                "img[id*='user']", "img[id*='User']",
                "img[class*='avatar']", "img[class*='photo']",
                "img[class*='user']",
                "img[src*='photo']", "img[src*='Photo']",
                "img[src*='avatar']", "img[src*='UserPhoto']",
                "img[src*='user']",
                ".user-avatar img", ".userphoto img",
                "img.user-photo",
                "img[alt*='头像']", "img[alt*='photo']",
                "img[title*='头像']", "img[title*='photo']",
            ]
            for sel in selectors:
                try:
                    el = await page.query_selector(sel)
                    if el:
                        src = await el.get_attribute("src")
                        if src and src.strip() and not src.strip().startswith("data:image/gif"):
                            avatar_url = src.strip()
                            print(f"[头像] 选择器命中: {sel} → {src[:80]}")
                            break
                except Exception:
                    continue

            # ── 策略2：扫描所有 img，按关键字过滤 ──
            if not avatar_url:
                imgs = await page.query_selector_all("img")
                print(f"[头像] 扫描 {len(imgs)} 个 img 标签...")
                for img in imgs:
                    try:
                        src = await img.get_attribute("src") or ""
                        if not src:
                            continue
                        src_lower = src.lower()
                        # 过滤明显非头像
                        if any(x in src_lower for x in ["logo", "icon", "banner", "bg", "background", ".gif", "sp_", "sprite"]):
                            continue
                        # 关键字匹配
                        if any(x in src_lower for x in ["photo", "user", "avatar", "face", "portrait", "head", "头像", "个人", "person"]):
                            avatar_url = src.strip()
                            print(f"[头像] 扫描命中 → {src[:80]}")
                            break
                        # 额外启发：侧边栏小正方形图片（攸信侧边栏风格）
                        w = await img.get_attribute("width") or ""
                        h = await img.get_attribute("height") or ""
                        try:
                            if w and h and 30 <= int(w) <= 120 and 30 <= int(h) <= 120 and abs(int(w) - int(h)) <= 15:
                                avatar_url = src.strip()
                                print(f"[头像] 尺寸启发 → {src[:80]} ({w}x{h})")
                                break
                        except Exception:
                            pass
                    except Exception:
                        continue

            # 无论是否找到，都保存调试截图（帮助下次调试）
            await _save_avatar_debug(page, f"头像{'已找到' if avatar_url else '未找到'}，调试截图")
            await browser.close()

            if not avatar_url:
                return None

            # 补全相对路径
            if avatar_url.startswith("//"):
                avatar_url = "https:" + avatar_url
            elif avatar_url.startswith("/"):
                avatar_url = BASE_URL.rstrip("/") + "/" + avatar_url.lstrip("/")
            elif not avatar_url.startswith("http"):
                avatar_url = BASE_URL.rstrip("/") + "/" + avatar_url.lstrip("/")

            # 下载（注入 cookie）
            cookie_str = "; ".join(f"{c['name']}={c['value']}" for c in cookies)
            req = urllib.request.Request(
                avatar_url,
                headers={
                    "Cookie": cookie_str,
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Referer": ATTEND_URL,
                }
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                img_bytes = resp.read()
            return img_bytes if img_bytes else None

    except Exception as e:
        print(f"[头像] 抓取失败: {e}")
        return None


class AvatarWorker(QThread):
    """后台抓取 UMS 头像"""
    success = pyqtSignal(bytes)   # 图片字节流
    failed  = pyqtSignal(str)

    def __init__(self, cookies):
        super().__init__()
        self.cookies = cookies

    def run(self):
        try:
            img_bytes = _run_async(_async_fetch_avatar(self.cookies))
            if img_bytes:
                self.success.emit(img_bytes)
            else:
                self.failed.emit("未找到头像")
        except Exception as e:
            self.failed.emit(str(e))


# ─────────────────────────────────────────────
#  样式表
# ─────────────────────────────────────────────
STYLE_MAIN = f"""
QMainWindow, QWidget {{
    background-color: {THEME['bg']};
    color: {THEME['text']};
    font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
}}
QPushButton {{
    background-color: {THEME['primary']};
    color: white;
    border: none;
    border-radius: 4px;
    padding: 8px 18px;
    font-size: 13px;
    font-weight: bold;
}}
QPushButton:hover {{ background-color: {THEME['accent']}; }}
QPushButton:pressed {{ background-color: {THEME['primary_dk']}; }}
QPushButton:disabled {{ background-color: #BDBDBD; color: #757575; }}
QPushButton#btnSecondary {{
    background-color: white;
    color: {THEME['primary']};
    border: 1.5px solid {THEME['primary']};
}}
QPushButton#btnSecondary:hover {{ background-color: #E3F2FD; }}
QLineEdit, QDateEdit, QComboBox {{
    border: 1.5px solid {THEME['border']};
    border-radius: 5px;
    padding: 6px 10px;
    background: white;
    font-size: 13px;
    min-height: 32px;
}}
QLineEdit:focus, QDateEdit:focus, QComboBox:focus {{ border-color: {THEME['primary']}; }}
QComboBox::drop-down {{
    width: 28px;
    border: none;
    border-left: 1px solid {THEME['border']};
    border-top-right-radius: 5px;
    border-bottom-right-radius: 5px;
}}
QComboBox QAbstractItemView {{
    background: white;
    border: 1.5px solid {THEME['border']};
    border-radius: 4px;
    outline: none;
    selection-background-color: {THEME['primary']};
    selection-color: black;
}}
QComboBox QAbstractItemView::item {{
    min-height: 28px;
    padding: 4px 10px;
    color: {THEME['text']};
}}
QComboBox QAbstractItemView::item:hover {{
    background-color: {THEME['accent']};
    color: black;
}}
QDateEdit::drop-down {{
    width: 28px;
    border: none;
    border-left: 1px solid {THEME['border']};
    border-top-right-radius: 5px;
    border-bottom-right-radius: 5px;
}}
QGroupBox {{
    border: 1.5px solid {THEME['border']};
    border-radius: 6px;
    margin-top: 8px;
    padding-top: 8px;
    background: {THEME['card']};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
    color: {THEME['primary']};
    font-weight: bold;
    font-size: 13px;
}}
QTableWidget {{
    border: 1px solid {THEME['border']};
    gridline-color: {THEME['border']};
    background: white;
    alternate-background-color: {THEME['row_alt']};
    selection-background-color: {THEME['accent']};
    selection-color: white;
    font-size: 12px;
}}
QHeaderView::section {{
    background-color: {THEME['header_bg']};
    color: white;
    padding: 6px 4px;
    border: none;
    font-weight: bold;
    font-size: 12px;
}}
QScrollBar:vertical {{ width: 8px; background: #F5F5F5; }}
QScrollBar::handle:vertical {{ background: #BDBDBD; border-radius: 4px; }}
QStatusBar {{ background: {THEME['primary']}; color: white; font-size: 12px; }}
QProgressBar {{
    border: 1px solid {THEME['border']};
    border-radius: 4px;
    text-align: center;
    background: #E0E0E0;
    height: 12px;
}}
QProgressBar::chunk {{ background: {THEME['primary']}; border-radius: 4px; }}
"""

STYLE_LOGIN = f"""
QWidget {{
    background-color: {THEME['bg']};
    font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
}}
"""


# ─────────────────────────────────────────────
#  登录窗口
# ─────────────────────────────────────────────
class LoginWindow(QWidget):
    login_success = pyqtSignal(list, str)  # cookies, username

    def __init__(self):
        super().__init__()
        self.setWindowTitle("考勤管理系统 · 登录")
        self.setFixedSize(460, 560)
        self.setStyleSheet(STYLE_LOGIN)
        self._worker = None
        self._is_logging_in = False  # 登录中标志，防止重复登录
        self._saved_user = ""
        self._saved_pwd = ""
        self._save_remember_pwd = False
        self._load_saved_user()
        self._setup_ui()
        if self._saved_user:
            self.input_user.setText(self._saved_user)
            self.chk_remember.setChecked(True)
        if self._saved_pwd and self._save_remember_pwd:
            self.input_pwd.setText(self._saved_pwd)
            self.chk_remember_pwd.setChecked(True)

    def _get_config_path(self):
        cfg = os.path.join(os.path.expanduser("~"), ".attendance_tool_cfg.json")
        return cfg

    def _load_saved_user(self):
        cfg_path = self._get_config_path()
        if os.path.exists(cfg_path):
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._saved_user = data.get("saved_user", "")
                    self._saved_pwd = data.get("saved_pwd", "")
                    self._save_remember_pwd = data.get("save_remember_pwd", False)
            except Exception:
                self._saved_user = ""
                self._saved_pwd = ""
                self._save_remember_pwd = False

    def _save_user(self, user, pwd=""):
        cfg_path = self._get_config_path()
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
        
        data["saved_user"] = user
        if self.chk_remember_pwd.isChecked() and pwd:
            data["saved_pwd"] = pwd
            data["save_remember_pwd"] = True
        else:
            data["saved_pwd"] = ""
            data["save_remember_pwd"] = False
        
        try:
            with open(cfg_path, "w", encoding="utf-8") as f:
                json.dump(data, f)
        except Exception:
            pass

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # ── Banner ──
        banner = QFrame()
        banner.setFixedHeight(170)
        banner.setStyleSheet(f"""
            background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                stop:0 {THEME['primary']}, stop:1 {THEME['accent']});
        """)
        bl = QVBoxLayout(banner)
        bl.setAlignment(Qt.AlignCenter)
        bl.setContentsMargins(20, 20, 20, 16)

        # Logo area
        logo_lbl = QLabel()
        logo_lbl.setText('<span style="font-size:56px;">&#128197;</span>')
        logo_lbl.setAlignment(Qt.AlignCenter)
        logo_lbl.setStyleSheet("background:transparent;")

        title_lbl = QLabel("考勤管理系统")
        title_lbl.setStyleSheet(
            "font-size: 26px; font-weight: bold; color: white; background: transparent;")
        title_lbl.setAlignment(Qt.AlignCenter)

        sub_lbl = QLabel("intretech UMS  ·  登录")
        sub_lbl.setStyleSheet(
            "font-size: 13px; color: rgba(255,255,255,0.82); background: transparent;")
        sub_lbl.setAlignment(Qt.AlignCenter)

        bl.addWidget(logo_lbl)
        bl.addWidget(title_lbl)
        bl.addWidget(sub_lbl)
        layout.addWidget(banner)

        # ── 表单卡片（白底） ──
        self._card = QFrame()   # 存为实例变量，防止被GC导致body被连带删除
        card = self._card
        card.setStyleSheet("background: white;")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)

        # ── 表单主体：固定宽度300px，水平居中 ──
        self.body = QFrame()
        self.body.setFixedWidth(300)
        self.body.setStyleSheet("background: transparent;")
        body_layout = QVBoxLayout(self.body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        # 每个行容器都塞进水平居中 wrapper，再加入 body
        def add_row(body_l, row_w):
            """把 row_w 水平居中地加入 body_l"""
            row_w.setFixedWidth(300)  # 确保行框架宽度与 body 一致
            hb = QHBoxLayout()
            hb.setContentsMargins(0, 0, 0, 0)
            hb.setSpacing(0)
            hb.addStretch()
            hb.addWidget(row_w)
            hb.addStretch()
            body_l.addLayout(hb)

        # ── 欢迎语 ──
        r_welcome = QFrame()
        r_welcome.setStyleSheet("background: transparent;")
        rw = QVBoxLayout(r_welcome)
        rw.setContentsMargins(0, 28, 0, 0)
        rw.setSpacing(4)
        lbl_welcome = QLabel("欢迎回来")
        lbl_welcome.setStyleSheet(
            f"font-size: 20px; font-weight: bold; color: {THEME['text']}; "
            f"background: transparent;")
        lbl_sub = QLabel("请输入您的工号和密码登录")
        lbl_sub.setStyleSheet(
            f"font-size: 13px; color: {THEME['text_sec']}; background: transparent;")
        rw.addWidget(lbl_welcome)
        rw.addWidget(lbl_sub)
        add_row(body_layout, r_welcome)

        # ── 工号标签 ──
        r_ulbl = QFrame()
        r_ulbl.setStyleSheet("background: transparent;")
        rul = QVBoxLayout(r_ulbl)
        rul.setContentsMargins(0, 14, 0, 6)
        rul.setSpacing(0)
        lbl_u = QLabel("工号")
        lbl_u.setStyleSheet(
            f"font-size: 13px; font-weight: bold; color: {THEME['text_sec']}; "
            f"background: transparent;")
        rul.addWidget(lbl_u)
        add_row(body_layout, r_ulbl)

        # ── 工号输入框 ──
        r_uin = QFrame()
        r_uin.setStyleSheet("background: transparent;")
        rui = QVBoxLayout(r_uin)
        rui.setContentsMargins(0, 0, 0, 10)
        rui.setSpacing(0)
        self.input_user = QLineEdit()
        self.input_user.setPlaceholderText("请输入工号（如：20772）")
        self.input_user.setClearButtonEnabled(True)
        self.input_user.setFixedHeight(44)
        self.input_user.setStyleSheet(f"""
            QLineEdit {{
                border: 1.5px solid {THEME['border']};
                border-radius: 8px;
                padding: 0 14px;
                font-size: 15px;
                background: #FAFBFC;
            }}
            QLineEdit:focus {{
                border-color: {THEME['primary']};
                background: white;
            }}
        """)
        rui.addWidget(self.input_user)
        add_row(body_layout, r_uin)

        # ── 密码标签 ──
        r_plbl = QFrame()
        r_plbl.setStyleSheet("background: transparent;")
        rpl = QVBoxLayout(r_plbl)
        rpl.setContentsMargins(0, 0, 0, 6)
        rpl.setSpacing(0)
        lbl_p = QLabel("密码")
        lbl_p.setStyleSheet(
            f"font-size: 13px; font-weight: bold; color: {THEME['text_sec']}; "
            f"background: transparent;")
        rpl.addWidget(lbl_p)
        add_row(body_layout, r_plbl)

        # ── 密码输入框 + 眼睛按钮 ──
        r_pwd = QFrame()
        r_pwd.setStyleSheet("background: transparent;")
        rp = QHBoxLayout(r_pwd)
        rp.setContentsMargins(0, 0, 0, 10)
        rp.setSpacing(8)

        self.input_pwd = QLineEdit()
        self.input_pwd.setPlaceholderText("请输入密码")
        self.input_pwd.setEchoMode(QLineEdit.Password)
        self.input_pwd.setFixedHeight(44)
        self.input_pwd.setStyleSheet(f"""
            QLineEdit {{
                border: 1.5px solid {THEME['border']};
                border-radius: 8px;
                padding: 0 14px;
                font-size: 15px;
                background: #FAFBFC;
            }}
            QLineEdit:focus {{
                border-color: {THEME['primary']};
                background: white;
            }}
        """)
        rp.addWidget(self.input_pwd, stretch=1)

        self.btn_eye = QPushButton("👁")
        self.btn_eye.setFixedSize(44, 44)
        self.btn_eye.setCursor(Qt.PointingHandCursor)
        self.btn_eye.setStyleSheet(f"""
            QPushButton {{
                background: #F0F0F0;
                border: 1.5px solid {THEME['border']};
                border-radius: 8px;
                font-size: 17px;
            }}
            QPushButton:hover {{
                background: #E0E0E0;
                border-color: {THEME['primary']};
            }}
        """)
        self.btn_eye.clicked.connect(self._toggle_pwd_visibility)
        rp.addWidget(self.btn_eye)
        add_row(body_layout, r_pwd)

        # ── 记住工号 ──
        r_remember = QFrame()
        r_remember.setStyleSheet("background: transparent;")
        rr = QHBoxLayout(r_remember)
        rr.setContentsMargins(0, 0, 0, 10)
        rr.setSpacing(20)
        
        self.chk_remember = QCheckBox("记住工号")
        self.chk_remember.setStyleSheet(f"""
            QCheckBox {{ font-size: 14px; color: {THEME['text_sec']}; spacing: 6px; }}
            QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 4px; border: 2px solid {THEME['border']}; background: white; }}
            QCheckBox::indicator:checked {{ background: {THEME['primary']}; border-color: {THEME['primary']}; }}
        """)
        rr.addWidget(self.chk_remember)
        
        self.chk_remember_pwd = QCheckBox("记住密码")
        self.chk_remember_pwd.setStyleSheet(f"""
            QCheckBox {{ font-size: 14px; color: {THEME['text_sec']}; spacing: 6px; }}
            QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 4px; border: 2px solid {THEME['border']}; background: white; }}
            QCheckBox::indicator:checked {{ background: {THEME['primary']}; border-color: {THEME['primary']}; }}
        """)
        rr.addWidget(self.chk_remember_pwd)
        
        rr.addStretch()
        add_row(body_layout, r_remember)

        # ── 登录按钮 ──
        r_login = QFrame()
        r_login.setStyleSheet("background: transparent;")
        rlk = QVBoxLayout(r_login)
        rlk.setContentsMargins(0, 0, 0, 14)
        rlk.setSpacing(0)
        self.btn_login = QPushButton("登 录")
        self.btn_login.setObjectName("btnLogin")
        self.btn_login.setFixedHeight(48)
        self.btn_login.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {THEME['primary']}, stop:1 {THEME['accent']});
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 16px;
                font-weight: bold;
                letter-spacing: 4px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {THEME['accent']}, stop:1 {THEME['primary']});
            }}
            QPushButton:disabled {{
                background: #BDBDBD;
            }}
        """)
        self.btn_login.clicked.connect(self._do_login)
        rlk.addWidget(self.btn_login)
        add_row(body_layout, r_login)

        # ── 进度条 ──
        r_prog = QFrame()
        r_prog.setStyleSheet("background: transparent;")
        rpr = QVBoxLayout(r_prog)
        rpr.setContentsMargins(0, 0, 0, 4)
        rpr.setSpacing(0)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        self.progress.setFixedHeight(4)
        self.progress.setFixedWidth(300)
        self.progress.setStyleSheet(
            "QProgressBar{border:none;background:#E3F2FD;border-radius:2px;}"
            "QProgressBar::chunk{background:#1976D2;border-radius:2px;}"
        )
        rpr.addWidget(self.progress)
        add_row(body_layout, r_prog)

        # ── 错误提示 ──
        r_err = QFrame()
        r_err.setStyleSheet("background: transparent;")
        rer = QVBoxLayout(r_err)
        rer.setContentsMargins(0, 0, 0, 0)
        rer.setSpacing(0)
        self.lbl_err = QLabel("")
        self.lbl_err.setStyleSheet(
            f"color: {THEME['danger']}; font-size: 13px; background: transparent;")
        self.lbl_err.setAlignment(Qt.AlignCenter)
        self.lbl_err.setWordWrap(True)
        self.lbl_err.setMinimumHeight(20)
        rer.addWidget(self.lbl_err)
        add_row(body_layout, r_err)

        # body 放入 card
        cl.addWidget(self.body)

        # card 水平居中放入 window
        hcenter = QHBoxLayout()
        hcenter.setContentsMargins(0, 0, 0, 0)
        hcenter.setSpacing(0)
        hcenter.addStretch()
        hcenter.addWidget(self._card)
        hcenter.addStretch()
        layout.addLayout(hcenter)

        # 回车快捷登录
        self.input_user.returnPressed.connect(self._do_login)
        self.input_pwd.returnPressed.connect(self._do_login)

    def _do_login(self):
        import traceback
        print(f"[DEBUG] _do_login called, stack:\n{traceback.format_stack()}")
        
        # 使用标志位防止重复登录
        if self._is_logging_in:
            print("[DEBUG] 正在登录中，跳过重复调用")
            return
        self._is_logging_in = True
        self.btn_login.setEnabled(False)
        self.progress.setVisible(True)
        
        username = self.input_user.text().strip()
        password = self.input_pwd.text().strip()
        if not username or not password:
            self.lbl_err.setText("工号和密码不能为空")
            self.btn_login.setEnabled(True)
            self.progress.setVisible(False)
            self._is_logging_in = False
            return
        # 保存工号和密码
        if self.chk_remember.isChecked():
            self._save_user(username, password if self.chk_remember_pwd.isChecked() else "")
        else:
            self._save_user("")
        self.lbl_err.setText("")
        self.lbl_err.setText("正在登录，请稍候（首次启动较慢）…")
        self.lbl_err.setStyleSheet(f"color: {THEME['text_sec']}; font-size: 12px;")

        # 断开旧的 worker 信号
        if self._worker and self._worker.isRunning():
            try:
                self._worker.success.disconnect()
                self._worker.failed.disconnect()
            except Exception:
                pass
            print("[DEBUG] 已断开旧 worker 信号")

        self._worker = LoginWorker(username, password)
        # 连接安装进度信号
        self._worker.install_progress.connect(self._on_install_progress)
        self._worker.success.connect(lambda c: self._on_success(c, username))
        self._worker.failed.connect(self._on_failed)
        self._worker.start()
        print(f"[DEBUG] 新 worker 已启动: {id(self._worker)}")

    def _on_install_progress(self, msg):
        """显示浏览器安装进度"""
        # 简化进度信息显示
        if "downloading" in msg.lower():
            # 提取关键信息
            import re
            match = re.search(r'(\d+\.?\d*)%', msg)
            if match:
                pct = float(match.group(1))
                self.lbl_err.setText(f"正在下载安装浏览器… {pct:.0f}%")
            else:
                self.lbl_err.setText("正在下载安装浏览器…")
            self.lbl_err.setStyleSheet(f"color: {THEME['text_sec']}; font-size: 12px;")

    def _on_success(self, cookies, username):
        print(f"[DEBUG] _on_success called, cookies count: {len(cookies) if cookies else 0}")
        self.progress.setVisible(False)
        self.btn_login.setEnabled(True)
        self._is_logging_in = False  # 重置登录标志
        self.login_success.emit(cookies, username)
        print("[DEBUG] login_success signal emitted")

    def _on_failed(self, msg):
        self.progress.setVisible(False)
        self.btn_login.setEnabled(True)
        self._is_logging_in = False  # 重置登录标志
        self.lbl_err.setStyleSheet(f"color: {THEME['danger']}; font-size: 12px;")
        self.lbl_err.setText(f"登录失败：{msg}")

    def _toggle_pwd_visibility(self):
        if self.input_pwd.echoMode() == QLineEdit.Password:
            self.input_pwd.setEchoMode(QLineEdit.Normal)
            self.btn_eye.setText("🙈")
            self.btn_eye.setStyleSheet(f"""
                QPushButton {{
                    background: {THEME['primary']};
                    border: none;
                    border-radius: 8px;
                    font-size: 17px;
                    color: white;
                }}
                QPushButton:hover {{
                    background: {THEME['accent']};
                }}
            """)
        else:
            self.input_pwd.setEchoMode(QLineEdit.Password)
            self.btn_eye.setText("👁")
            self.btn_eye.setStyleSheet(f"""
                QPushButton {{
                    background: #F0F0F0;
                    border: 1.5px solid {THEME['border']};
                    border-radius: 8px;
                    font-size: 17px;
                }}
                QPushButton:hover {{
                    background: #E0E0E0;
                    border-color: {THEME['primary']};
                }}
            """)


# ─────────────────────────────────────────────
#  配置弹窗窗口
# ─────────────────────────────────────────────
class ConfigWindow(QWidget):
    """上下班配置弹窗"""
    config_saved = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("上下班时间配置")
        self.setFixedSize(380, 320)
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {THEME['bg']};
                font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
            }}
        """)
        self._load_config()
        self._setup_ui()

    def _get_config_path(self):
        cfg = os.path.join(os.path.expanduser("~"), ".attendance_tool_cfg.json")
        return cfg

    def _load_config(self):
        cfg_path = self._get_config_path()
        self._config = {
            "work_start": "09:00",
            "work_end": "18:00",
            "rest_start": "12:00",
            "rest_end": "13:00",
            "flex_enabled": False,
            "remind_enabled": True,
            "late_threshold": 0,
        }
        if os.path.exists(cfg_path):
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    saved = json.load(f).get("work_config", {})
                    self._config.update(saved)
            except Exception:
                pass

    def _save_config(self):
        cfg_path = self._get_config_path()
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
        data["work_config"] = self._config
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        # 上班时间
        layout.addLayout(self._create_time_row("最早上班", "work_start", ""))
        # 最晚上班
        layout.addLayout(self._create_time_row("最晚上班", "work_start_late", ""))
        # 午休开始
        layout.addLayout(self._create_time_row("午休开始", "rest_start", ""))
        # 午休结束
        layout.addLayout(self._create_time_row("午休结束", "rest_end", ""))
        # 晚休开始
        layout.addLayout(self._create_time_row("晚休开始", "dinner_start", ""))
        # 晚休结束
        layout.addLayout(self._create_time_row("晚休结束", "dinner_end", ""))

        layout.addStretch()

        # 按钮行
        btn_row = QHBoxLayout()
        btn_cancel = QPushButton("取消")
        btn_cancel.setFixedHeight(40)
        btn_cancel.setStyleSheet(f"QPushButton {{ background: white; color: {THEME['text']}; border: 1.5px solid {THEME['border']}; border-radius: 6px; font-size: 14px; padding: 0 20px; }} QPushButton:hover {{ background: #F5F5F5; }}")
        btn_cancel.clicked.connect(self.close)
        btn_row.addWidget(btn_cancel)

        btn_save = QPushButton("保存配置")
        btn_save.setFixedHeight(40)
        btn_save.setStyleSheet(f"QPushButton {{ background: {THEME['primary']}; color: white; border: none; border-radius: 6px; font-size: 14px; font-weight: bold; padding: 0 20px; }} QPushButton:hover {{ background: {THEME['accent']}; }}")
        btn_save.clicked.connect(self._on_save)
        btn_row.addWidget(btn_save)

        layout.addLayout(btn_row)

    def _create_time_row(self, label, key, hint):
        row = QHBoxLayout()
        lbl = QLabel(label)
        lbl.setStyleSheet(f"font-size: 14px; color: {THEME['text']}; min-width: 70px;")
        row.addWidget(lbl)

        time_edit = QLineEdit()
        time_edit.setText(self._config.get(key, "09:00"))
        time_edit.setFixedWidth(80)
        time_edit.setAlignment(Qt.AlignCenter)
        time_edit.setStyleSheet(f"QLineEdit {{ border: 1.5px solid {THEME['border']}; border-radius: 5px; padding: 4px 8px; background: white; font-size: 13px; min-height: 28px; }} QLineEdit:focus {{ border-color: {THEME['primary']}; }}")
        time_edit.editingFinished.connect(lambda: self._config.__setitem__(key, time_edit.text()))
        row.addWidget(time_edit)

        hint_lbl = QLabel(hint)
        hint_lbl.setStyleSheet(f"font-size: 12px; color: {THEME['text_sec']};")
        row.addWidget(hint_lbl)
        row.addStretch()
        return row

    def _on_save(self):
        self._save_config()
        self.config_saved.emit(self._config)
        self.close()
        QMessageBox.information(self, "保存成功", "上下班配置已保存！")


# ─────────────────────────────────────────────
#  主界面
# ─────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self, cookies, username: str, login_window=None):
        super().__init__()
        self.cookies      = cookies
        self.username     = username
        self.login_window = login_window  # 保存登录窗口引用，退出时返回
        self._worker      = None
        self._avatar_worker = None
        self._is_logging_out = False  # 退出登录标志，绕过closeEvent对话框
        self._all_data = []
        self._headers  = []
        self._has_data = False

        # 刷新倒计时（秒）
        self._refresh_interval = 0   # 0 = 未启用
        self._refresh_remain   = 0

        self.setWindowTitle(f"考勤管理  ·  {username}")
        self.resize(780, 420)
        self.setMinimumSize(680, 380)

        self._init_tray()
        self.setWindowIcon(self._make_letter_icon(64))  # 任务栏窗口图标（初始字母占位）
        self._setup_ui()

        # 1秒定时器：倒计时 + 右侧实时时间
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_tick)
        self._timer.start(1000)

        # 启动时自动查询本月考勤
        QTimer.singleShot(800, self._fetch_data)
        # 启动时后台抓取头像
        QTimer.singleShot(1200, self._fetch_avatar)

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        # ── 背景渐变（绿色自然风格，模仿截图）
        central.setStyleSheet("""
            QWidget#bg {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 #5a8a4a, stop:0.4 #6fa055, stop:0.7 #4e7a3e, stop:1 #3d6030);
            }
        """)
        central.setObjectName("bg")

        root = QHBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        root.addWidget(self._build_left_panel(), stretch=0)
        root.addWidget(self._build_right_panel(), stretch=1)

        # 初始化 stub 控件（供 _update_stats / _populate_table 写入，不显示）
        self._build_stats_cards()
        self._build_table()

    # ═══════════════════════════════════════
    #  左侧控制面板
    # ═══════════════════════════════════════
    def _build_left_panel(self):
        frame = QFrame()
        frame.setFixedWidth(330)
        frame.setStyleSheet("""
            QFrame {
                background: rgba(240,255,240,0.88);
                border: 2px solid #7ab07a;
                border-radius: 4px;
            }
            QLabel { background: transparent; }
            QComboBox, QLineEdit {
                background: white;
                border: 1px solid #aaa;
                padding: 1px 4px;
                font-size: 12px;
            }
            QComboBox QAbstractItemView {
                background: white;
                border: 1px solid #aaa;
                selection-background-color: #1976D2;
                selection-color: black;
            }
            QComboBox QAbstractItemView::item:hover {
                background-color: #42A5F5;
                color: black;
            }
            QPushButton {
                font-size: 12px;
                padding: 2px 10px;
                background: #e8e8e8;
                border: 1px solid #999;
                border-radius: 2px;
            }
            QPushButton:hover { background: #d0d0d0; }
        """)

        vb = QVBoxLayout(frame)
        vb.setContentsMargins(8, 8, 8, 8)
        vb.setSpacing(6)

        # ── 顶部标题（头像 + 用户名）
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        # 头像标签（初始显示首字符占位）
        self._lbl_avatar = QLabel()
        self._lbl_avatar.setFixedSize(40, 40)
        self._lbl_avatar.setAlignment(Qt.AlignCenter)
        self._lbl_avatar.setStyleSheet("""
            QLabel {
                background: #1976D2;
                border-radius: 20px;
                font-size: 16px;
                font-weight: bold;
                color: white;
            }
        """)
        # 显示工号首字符作为占位
        placeholder = self.username[0].upper() if self.username else "?"
        self._lbl_avatar.setText(placeholder)
        top_bar.addWidget(self._lbl_avatar)

        self._lbl_username = QLabel(self.username or "你好")
        self._lbl_username.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        self._lbl_username.setStyleSheet("""
            QLabel {
                background: transparent;
                border: none;
                font-size: 14px;
                font-weight: bold;
                padding: 4px;
                color: #2d5a1e;
            }
        """)
        top_bar.addWidget(self._lbl_username, stretch=1)
        vb.addLayout(top_bar)

        # ── 显示范围（本月/上月考勤周期）
        row_range = QHBoxLayout()
        row_range.addWidget(QLabel("显示范围："))
        self.combo_range = QComboBox()
        self.combo_range.addItem("本月", "current")
        self.combo_range.addItem("上月", "prev")
        self.combo_range.setFixedWidth(160)
        self.combo_range.currentIndexChanged.connect(self._on_range_combo_changed)
        row_range.addWidget(self.combo_range)
        row_range.addStretch()
        vb.addLayout(row_range)

        # ── 日期选择
        row_date = QHBoxLayout()
        row_date.addWidget(QLabel("日期选择："))
        self.combo_date = QComboBox()
        self._fill_date_combo()
        self.combo_date.setFixedWidth(160)
        self.combo_date.currentIndexChanged.connect(self._on_date_combo_changed)
        row_date.addWidget(self.combo_date)
        row_date.addStretch()
        vb.addLayout(row_date)

        # ── 下班提醒
        row_remind = QHBoxLayout()
        row_remind.addWidget(QLabel("下班提醒："))
        self.combo_remind_h = QComboBox()
        self.combo_remind_h.addItems([str(i) for i in range(24)])
        self.combo_remind_h.setFixedWidth(48)
        row_remind.addWidget(self.combo_remind_h)
        row_remind.addWidget(QLabel("时"))
        self.combo_remind_m = QComboBox()
        self.combo_remind_m.addItems(["0", "15", "30", "45"])
        self.combo_remind_m.setFixedWidth(48)
        row_remind.addWidget(self.combo_remind_m)
        row_remind.addWidget(QLabel("分"))
        row_remind.addStretch()
        vb.addLayout(row_remind)

        # ── 加班设置
        row_ot = QHBoxLayout()
        row_ot.addWidget(QLabel("加班设置："))
        self.combo_ot_h = QComboBox()
        self.combo_ot_h.addItems([str(i) for i in range(13)])
        self.combo_ot_h.setFixedWidth(48)
        row_ot.addWidget(self.combo_ot_h)
        row_ot.addWidget(QLabel("时"))
        self.combo_ot_m = QComboBox()
        self.combo_ot_m.addItems(["0", "15", "30", "45"])
        self.combo_ot_m.setFixedWidth(48)
        row_ot.addWidget(self.combo_ot_m)
        row_ot.addWidget(QLabel("分"))
        row_ot.addStretch()
        vb.addLayout(row_ot)

        # 加班设置变化时刷新详情面板
        self.combo_ot_h.currentIndexChanged.connect(self._refresh_detail_panel)
        self.combo_ot_m.currentIndexChanged.connect(self._refresh_detail_panel)

        # ── 分隔线
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("border: 1px solid #adc8ad;")
        vb.addWidget(sep)

        # ── 迟到次数 + 早退次数
        row_counts = QHBoxLayout()
        row_counts.addWidget(QLabel("迟到次数："))
        self._lbl_late = QLabel("0")
        self._lbl_late.setStyleSheet("font-weight:bold; color:#c0392b;")
        row_counts.addWidget(self._lbl_late)
        row_counts.addSpacing(16)
        row_counts.addWidget(QLabel("早退次数："))
        self._lbl_early = QLabel("0")
        self._lbl_early.setStyleSheet("font-weight:bold; color:#c0392b;")
        row_counts.addWidget(self._lbl_early)
        row_counts.addStretch()
        vb.addLayout(row_counts)

        # ── 考勤刷新倒计时
        row_timer = QHBoxLayout()
        row_timer.addWidget(QLabel("考勤刷新倒计时："))
        self._lbl_countdown = QLineEdit("--")
        self._lbl_countdown.setReadOnly(True)
        self._lbl_countdown.setFixedWidth(60)
        self._lbl_countdown.setAlignment(Qt.AlignCenter)
        row_timer.addWidget(self._lbl_countdown)
        btn_refresh = QPushButton("刷新")
        btn_refresh.clicked.connect(self._fetch_data)
        row_timer.addWidget(btn_refresh)
        row_timer.addStretch()
        vb.addLayout(row_timer)

        # ── 底部按钮行：设置 + 导出 + 退出
        row_btns = QHBoxLayout()
        btn_cfg = QPushButton("⚙ 设置")
        btn_cfg.clicked.connect(self._open_config)
        row_btns.addWidget(btn_cfg)

        btn_exp = QPushButton("📥 导出")
        btn_exp.clicked.connect(self._export_csv)
        row_btns.addWidget(btn_exp)

        btn_lo = QPushButton("退出")
        btn_lo.clicked.connect(self._logout)
        row_btns.addWidget(btn_lo)
        vb.addLayout(row_btns)

        vb.addStretch()
        return frame

    def _calc_cycle_range(self, offset=0):
        """计算考勤周期起止日期。
        offset=0 → 当前周期（今天所在）；offset=-1 → 上一个周期。
        返回 (start: date, end: date)。
        """
        today = datetime.date.today()
        year  = today.year
        month = today.month
        # 先确定"当前周期"的起月
        if today.day >= 26:
            cur_start_year, cur_start_month = year, month
        else:
            cur_start_month = month - 1 if month > 1 else 12
            cur_start_year  = year if month > 1 else year - 1
        # 按 offset 偏移
        sm = cur_start_month + offset
        sy = cur_start_year
        while sm <= 0:
            sm += 12; sy -= 1
        while sm > 12:
            sm -= 12; sy += 1
        em = sm + 1; ey = sy
        if em > 12:
            em = 1; ey += 1
        return datetime.date(sy, sm, 26), datetime.date(ey, em, 25)

    def _fill_date_combo(self):
        """填充日期选择下拉：根据显示范围下拉决定考勤周期"""
        self.combo_date.blockSignals(True)
        self.combo_date.clear()
        today = datetime.date.today()

        # 读取显示范围选项（首次调用时 combo_range 可能还未创建，默认当前周期）
        offset = 0
        if hasattr(self, "combo_range"):
            raw = self.combo_range.currentData()
            if raw == "prev":
                offset = -1

        start, end = self._calc_cycle_range(offset)

        weekdays_cn = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        idx_today = 0
        i = 0
        d = start
        while d <= end:
            self.combo_date.addItem(f"{d.month}/{d.day} {weekdays_cn[d.weekday()]}", d)
            if d == today:
                idx_today = i
            d += datetime.timedelta(days=1)
            i += 1
        # 若今天不在该区间内（查看上月时），默认选最后一天
        self.combo_date.setCurrentIndex(idx_today)
        self.combo_date.blockSignals(False)

    def _on_range_combo_changed(self, idx):
        """显示范围改变：重填日期下拉并重新拉取考勤数据"""
        self._fill_date_combo()
        self._fetch_data()

    def _on_date_combo_changed(self, idx):
        """日期下拉改变：右侧刷新当日数据"""
        self._refresh_detail_panel()

    # ═══════════════════════════════════════
    #  右侧详情面板
    # ═══════════════════════════════════════
    def _build_right_panel(self):
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background: rgba(240,255,240,0.88);
                border: 2px solid #7ab07a;
                border-radius: 4px;
            }
            QLabel { background: transparent; }
        """)

        vb = QVBoxLayout(frame)
        vb.setContentsMargins(0, 0, 0, 0)
        vb.setSpacing(0)

        # ── 标题栏
        title_bar = QFrame()
        title_bar.setFixedHeight(32)
        title_bar.setStyleSheet("""
            QFrame {
                background: rgba(220,240,220,0.9);
                border: none;
                border-bottom: 1px solid #7ab07a;
            }
        """)
        tb_layout = QHBoxLayout(title_bar)
        tb_layout.setContentsMargins(8, 0, 8, 0)
        lbl_title = QLabel(f"考勤管理  ·  {self.username}")
        lbl_title.setStyleSheet("font-size:13px;font-weight:bold;color:#2d5a1e;")
        tb_layout.addWidget(lbl_title)
        # 版本号标签
        lbl_ver = QLabel(APP_VERSION)
        lbl_ver.setStyleSheet("""
            font-size:11px; color:#2d5a1e;
            background: rgba(255,255,255,0.55);
            border: 1px solid #7ab07a;
            border-radius: 6px;
            padding: 1px 7px;
        """)
        tb_layout.addWidget(lbl_ver)
        tb_layout.addStretch()

        # 进度条（查询时显示）
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setStyleSheet("""
            QProgressBar { border: none; background: #ddd; }
            QProgressBar::chunk { background: #1976D2; }
        """)
        tb_layout.addWidget(self.progress_bar)

        vb.addWidget(title_bar)

        # ── "详情信息" 副标题
        lbl_sub = QLabel("详情信息")
        lbl_sub.setAlignment(Qt.AlignCenter)
        lbl_sub.setFixedHeight(28)
        lbl_sub.setStyleSheet("""
            QLabel {
                background: rgba(210,235,210,0.8);
                border: none;
                border-bottom: 1px solid #7ab07a;
                font-size: 12px;
                color: #3a6030;
            }
        """)
        vb.addWidget(lbl_sub)

        # ── 内容区（今日考勤详情）
        content = QWidget()
        content.setStyleSheet("background: transparent;")
        content_vb = QVBoxLayout(content)
        content_vb.setContentsMargins(12, 10, 12, 10)
        content_vb.setSpacing(6)

        # 今日打卡信息
        self._detail_lines = {}
        detail_items = [
            ("clock_records", "打卡记录",  "--"),
            ("should_out",   "应下班时间", "--:--"),
            ("worked",       "已工作时长", "00时00分"),
            ("overtime",     "已加班时长", "00时00分"),
            ("ot_weekday",   "平加(h)",    "0"),
            ("ot_weekend",   "周加(h)",    "0"),
            ("ot_holiday",   "假加(h)",    "0"),
            ("ot_cycle_sum", "合计加班(h)","0"),
        ]
        for key, label, default in detail_items:
            row = QHBoxLayout()
            lbl_k = QLabel(f"{label}：")
            lbl_k.setFixedWidth(90)
            lbl_k.setStyleSheet("font-size:12px; color:#3a6030;")
            lbl_v = QLabel(default)
            lbl_v.setStyleSheet("font-size:13px; font-weight:bold; color:#1a3a10;")
            row.addWidget(lbl_k)
            row.addWidget(lbl_v)
            row.addStretch()
            content_vb.addLayout(row)
            self._detail_lines[key] = lbl_v

        content_vb.addStretch()

        # 底部状态栏
        self._lbl_status = QLabel("就绪")
        self._lbl_status.setFixedHeight(22)
        self._lbl_status.setStyleSheet("""
            QLabel {
                background: rgba(200,230,200,0.8);
                border: none;
                border-top: 1px solid #7ab07a;
                font-size: 11px;
                color: #4a6a3a;
                padding-left: 6px;
            }
        """)

        vb.addWidget(content, stretch=1)
        vb.addWidget(self._lbl_status)

        return frame

    def _build_stats_cards(self):
        """兼容旧代码调用（不再显示卡片，改由右侧详情面板展示）

        所有 card_* 元组统一用 self 做父窗口，防止 Qt 提前析构。
        """
        # 用一个隐藏容器确保所有子控件生命周期与 self 绑定
        _container = QFrame(self)
        _container.setVisible(False)

        def _make_dummy():
            lbl = QLabel(_container)
            return _container, lbl

        self.card_clock_in   = _make_dummy()
        self.card_clock_out  = _make_dummy()
        self.card_should_out = _make_dummy()
        self.card_worked     = _make_dummy()
        self.card_overtime   = _make_dummy()
        self.card_total      = _make_dummy()
        self.card_days       = _make_dummy()
        self.card_late       = _make_dummy()
        self.card_absent     = _make_dummy()
        self.card_ot         = _make_dummy()
        self.card_ot_today   = _make_dummy()
        return _container

    def _make_card(self, title, value, color):
        """兼容旧代码"""
        card = QFrame()
        lv = QLabel(value)
        return card, lv

    def _build_table(self):
        """兼容旧代码（详情面板在右侧，表格不再主显示）

        self.table 和 self.lbl_count 直接挂 self 为父，不放进任何 layout，
        这样 Qt 不会在父控件析构前把它们也析构掉。
        """
        self.table = QTableWidget(self)
        self.table.setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.verticalHeader().setDefaultSectionSize(28)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.lbl_count = QLabel("共 0 条记录", self)
        self.lbl_count.setVisible(False)
        return None  # 不再返回任何 widget

    def _on_tick(self):
        """每秒定时回调：倒计时刷新"""
        if self._refresh_interval > 0:
            self._refresh_remain -= 1
            if self._refresh_remain <= 0:
                self._refresh_remain = self._refresh_interval
                self._fetch_data()
            m = self._refresh_remain // 60
            s = self._refresh_remain % 60
            self._lbl_countdown.setText(f"{m:02d}:{s:02d}")
        else:
            self._lbl_countdown.setText("--")


    # ─── 逻辑 ───

    def _make_letter_icon(self, size: int = 32) -> "QIcon":
        """
        用工号首字母生成一个蓝色圆形图标，用于托盘/任务栏占位。
        size: 像素尺寸（建议 32 或 64）
        """
        from PyQt5.QtGui import QPixmap, QPainter, QBrush, QColor, QFont, QIcon
        pix = QPixmap(size, size)
        pix.fill(Qt.transparent)
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.Antialiasing)
        # 蓝色圆形背景
        painter.setBrush(QBrush(QColor("#1976D2")))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(0, 0, size, size)
        # 白色字母
        letter = (self.username[0].upper() if self.username else "?")
        painter.setPen(QColor("white"))
        font = QFont()
        font.setPixelSize(int(size * 0.5))
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(pix.rect(), Qt.AlignCenter, letter)
        painter.end()
        return QIcon(pix)

    def _fetch_avatar(self):
        """后台抓取 UMS 头像"""
        if self._avatar_worker and self._avatar_worker.isRunning():
            return
        self._avatar_worker = AvatarWorker(self.cookies)
        self._avatar_worker.success.connect(self._apply_avatar)
        self._avatar_worker.failed.connect(lambda msg: print(f"[头像] {msg}"))
        self._avatar_worker.start()

    def _apply_avatar(self, img_bytes: bytes):
        """将头像图片字节流处理为圆形，应用到左侧头像标签和系统托盘"""
        try:
            from PyQt5.QtGui import QPixmap, QBitmap, QPainter, QBrush, QPainterPath, QColor
            from PyQt5.QtCore import QByteArray, QBuffer, QIODevice

            # 从字节流创建 QPixmap
            ba = QByteArray(img_bytes)
            pixmap = QPixmap()
            if not pixmap.loadFromData(ba):
                print("[头像] 图片数据无法解析")
                return

            # ── 1. 左侧头像标签：40×40 圆形 ──
            size = 40
            scaled = pixmap.scaled(size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            # 居中裁切为正方形
            x_off = (scaled.width()  - size) // 2
            y_off = (scaled.height() - size) // 2
            scaled = scaled.copy(x_off, y_off, size, size)

            # 圆形遮罩
            rounded = QPixmap(size, size)
            rounded.fill(Qt.transparent)
            painter = QPainter(rounded)
            painter.setRenderHint(QPainter.Antialiasing)
            path = QPainterPath()
            path.addEllipse(0, 0, size, size)
            painter.setClipPath(path)
            painter.drawPixmap(0, 0, scaled)
            painter.end()

            self._lbl_avatar.setPixmap(rounded)
            self._lbl_avatar.setText("")  # 清除占位文字

            # ── 2. 系统托盘图标 & 任务栏图标：32×32，带白色圆形背景（Windows 不支持纯透明）──
            tray_size = 32
            tray_scaled = pixmap.scaled(tray_size, tray_size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            tx = (tray_scaled.width()  - tray_size) // 2
            ty = (tray_scaled.height() - tray_size) // 2
            tray_scaled = tray_scaled.copy(tx, ty, tray_size, tray_size)

            # 用白色不透明背景，再绘制圆形裁切的头像（Windows 托盘需要不透明图标）
            tray_rounded = QPixmap(tray_size, tray_size)
            tray_rounded.fill(QColor("white"))          # ← 不透明白底
            tp = QPainter(tray_rounded)
            tp.setRenderHint(QPainter.Antialiasing)
            tpath = QPainterPath()
            tpath.addEllipse(0, 0, tray_size, tray_size)
            tp.setClipPath(tpath)
            tp.drawPixmap(0, 0, tray_scaled)
            tp.end()

            tray_icon = QIcon(tray_rounded)
            self.tray_icon.setIcon(tray_icon)
            self.setWindowIcon(QIcon(tray_rounded))

            print("[头像] 头像已成功应用")
        except Exception as e:
            print(f"[头像] 应用失败: {e}")

    def _fetch_data(self):
        """查询考勤数据（范围与显示范围下拉一致：当前/上一个考勤周期）"""
        offset = 0
        if hasattr(self, "combo_range"):
            raw = self.combo_range.currentData()
            if raw == "prev":
                offset = -1
        start_d, end_d = self._calc_cycle_range(offset)
        start = start_d.strftime("%Y-%m-%d")
        end   = end_d.strftime("%Y-%m-%d")

        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(True)
        self._lbl_status.setText(f"正在获取考勤数据 {start} ~ {end}，请稍候…")

        self._worker = FetchWorker(self.cookies, start, end)
        self._worker.success.connect(self._on_data_ready)
        self._worker.failed.connect(self._on_fetch_failed)
        self._worker.progress.connect(self._on_progress)
        self._worker.start()

    def _on_progress(self, v):
        if v >= 100:
            self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(v)

    def _on_data_ready(self, headers, rows):
        import traceback
        try:
            self.progress_bar.setVisible(False)
            self._headers  = headers
            self._all_data = rows
            self._has_data = True

            if not rows:
                self._lbl_status.setText("该时间段内无考勤记录")
            else:
                # 写调试日志：记录列名和数据样本
                _debug_log = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "debug.log")
                try:
                    with open(_debug_log, "w", encoding="utf-8") as _f:
                        _f.write(f"调试时间: {datetime.datetime.now()}\n")
                        _f.write(f"表头: {headers}\n")
                        _f.write(f"行数: {len(rows)}\n")
                        if rows:
                            _f.write(f"第一行数据: {rows[0]}\n")
                            # 找关键列
                            for i, h in enumerate(headers):
                                if any(k in h for k in ["考勤日期", "有效打卡时间", "打卡时间", "出勤", "平加", "周加", "假加"]):
                                    _f.write(f"  [{i}] {h} = {rows[0][i] if i < len(rows[0]) else 'N/A'}\n")
                except Exception:
                    pass

                self._populate_table(headers, rows)
                self._update_stats(headers, rows)
                self._refresh_detail_panel()
                self._lbl_status.setText(f"已登录：{self.username}  |  共 {len(rows)} 条记录")

            # 启动自动刷新（每30分钟）
            if self._refresh_interval == 0:
                self._refresh_interval = 30 * 60
                self._refresh_remain   = self._refresh_interval
        except Exception:
            _tb = traceback.format_exc()
            _crash_log = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "crash.log")
            try:
                with open(_crash_log, "a", encoding="utf-8") as _f:
                    _f.write(f"\n{'='*60}\n崩溃时间: {datetime.datetime.now()}\n{_tb}")
            except Exception:
                pass
            self._lbl_status.setText("数据处理异常，详见 crash.log")
            QMessageBox.critical(self, "数据处理异常",
                f"处理考勤数据时出错，已记录到 crash.log：\n\n{_tb[:800]}")

    def _on_fetch_failed(self, msg):
        self.progress_bar.setVisible(False)
        self._lbl_status.setText(f"获取失败：{msg}")
        reply = QMessageBox.question(
            self, "获取失败",
            f"数据获取失败：{msg}\n\n是否加载演示数据预览界面？",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self._load_demo_data()

    def _load_demo_data(self):
        headers = ["工号", "姓名", "部门", "考勤日期", "考勤周数", "班次",
                   "有效打卡时间", "出勤", "在家办公", "平加",
                   "迟到", "早退", "旷工", "漏打卡", "异常说明"]
        rows = []
        names = ["演示用户"]
        today = datetime.date.today()
        for d in range(30):
            date = today - datetime.timedelta(days=d)
            if date.weekday() >= 5:
                continue
            late   = (d % 5 == 1)
            absent = (d % 10 == 3)
            rows.append([
                "YQ10001", names[0], "研发部",
                date.strftime("%Y/%m/%d"),
                ["星期一","星期二","星期三","星期四","星期五"][date.weekday() % 5],
                "弹性班",
                "--" if absent else ("09:25，18:00" if late else "07:45，18:00"),
                "0" if absent else "08:00",
                "", "2.5" if d == 2 else "",
                "1" if late else "", "", "1" if absent else "", "", ""
            ])
        self._headers  = headers
        self._all_data = rows
        self._has_data = True
        self._populate_table(headers, rows)
        self._update_stats(headers, rows)
        self._refresh_detail_panel()
        self._lbl_status.setText(f"演示模式  |  共 {len(rows)} 条模拟记录")

    def _populate_table(self, headers, rows):
        self.table.clear()
        if not headers:
            self.table.setColumnCount(1)
            self.table.setHorizontalHeaderLabels(["暂无数据"])
            self.lbl_count.setText("共 0 条记录")
            return

        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setRowCount(len(rows))

        def col_idx(kws):
            for i, h in enumerate(headers):
                if any(k in h for k in kws):
                    return i
            return -1

        late_col   = col_idx(["迟到"])
        absent_col = col_idx(["旷工"])
        miss_col   = col_idx(["漏打卡"])

        for r, row in enumerate(rows):
            for c, cell in enumerate(row):
                if c >= len(headers):
                    break
                item = QTableWidgetItem(str(cell))
                item.setTextAlignment(Qt.AlignCenter)
                val = str(cell).strip()
                if c == late_col and val not in ("", "0"):
                    item.setBackground(QColor("#FFF3E0"))
                    item.setForeground(QColor(THEME["warning"]))
                elif c == absent_col and val not in ("", "0"):
                    item.setBackground(QColor("#FFEBEE"))
                    item.setForeground(QColor(THEME["danger"]))
                elif c == miss_col and val not in ("", "0"):
                    item.setBackground(QColor("#FFEBEE"))
                    item.setForeground(QColor(THEME["danger"]))
                self.table.setItem(r, c, item)

        self.table.resizeColumnsToContents()
        for c in range(self.table.columnCount()):
            if self.table.columnWidth(c) > 180:
                self.table.setColumnWidth(c, 180)

        self.lbl_count.setText(f"共 {len(rows)} 条记录")

    def _update_stats(self, headers, rows, target_date=None):
        """
        target_date: 要显示详情的目标日期（默认为今日）。
        """
        def col_idx(kws):
            for i, h in enumerate(headers):
                if any(k in h for k in kws):
                    return i
            return -1

        # 先获取日期列索引（用于过滤汇总行）
        date_col = col_idx(["考勤日期", "日期"])

        def sum_col(idx):
            if idx < 0:
                return 0
            total = 0.0
            debug_details = []
            for i, row in enumerate(rows):
                # 跳过汇总行（日期列包含"至"表示日期范围，是汇总行）
                date_val = row[date_col].strip() if date_col >= 0 and date_col < len(row) else ""
                if "至" in date_val:
                    debug_details.append(f"[{i}] SKIP(汇总行): 日期={date_val}")
                    continue
                try:
                    v = row[idx].strip() if idx < len(row) else ""
                    if v and v not in ("", "0"):
                        if ":" in v:
                            # HH:MM 格式转换为小时
                            parts = v.split(":")
                            val = float(parts[0]) + (float(parts[1]) / 60.0 if len(parts) > 1 else 0)
                            total += val
                            debug_details.append(f"[{i}] ADD: {v} -> {val:.2f}, 累计={total:.2f}")
                        else:
                            val = float(v)
                            total += val
                            debug_details.append(f"[{i}] ADD: {v} -> {val:.2f}, 累计={total:.2f}")
                except Exception as e:
                    debug_details.append(f"[{i}] ERROR: {v}, {e}")
            return total, debug_details

        def _get_col_sum(idx):
            """辅助函数：提取 sum_col 的数值部分"""
            result, _ = sum_col(idx)
            return result

        # 今日加班计算（从平加列读取）
        def sum_today_ot(date_col_idx, ot_col_idx):
            if date_col_idx < 0 or ot_col_idx < 0:
                return 0
            s = 0.0
            date_fmts = ["%Y/%m/%d", "%Y-%m-%d", "%Y%m%d", "%Y.%m.%d"]
            for row in rows:
                # 跳过汇总行
                if "至" in row[date_col_idx].strip():
                    continue
                try:
                    date_str = row[date_col_idx].strip()
                    dt = None
                    for fmt in date_fmts:
                        try:
                            dt = datetime.datetime.strptime(date_str, fmt).date()
                            break
                        except:
                            continue
                    match = (dt == target_date) if dt else False
                    if not match and dt:
                        match = (dt.month == target_date.month and dt.day == target_date.day
                                 and abs(dt.year - target_date.year) <= 1)
                    if match:
                        ot_val = row[ot_col_idx].strip()
                        if ot_val and ot_val not in ("0", ""):
                            s += float(ot_val)
                except:
                    pass
            return s

        # 分钟数转 HH时MM分 字符串（与ku.py min2hm一致）
        def min2hm(minutes):
            a = int(minutes)
            return str(int(a / 60)).zfill(2) + "时" + str(int(a % 60)).zfill(2) + "分"

        # ===== 完全对齐ku.py的 check_time_is_include_rest_time =====
        # 计算 [up, dowm) 区间内应扣除的休息时间（分钟）
        def check_time_is_include_rest_time(up, dowm,
                                            standed_up, rest1_begin, rest1_end,
                                            rest2_begin, rest2_end):
            total_time = 0
            # 提前打卡：早于标准上班时间的部分不算工作时间，补回来
            if up < standed_up and up != 0:
                total_time += standed_up - up
            # 逐分钟统计休息时间（午饭 + 晚饭）
            for i in range(up, dowm):
                if rest1_begin < i <= rest1_end:
                    total_time += 1
                if rest2_begin < i <= rest2_end:
                    total_time += 1
            return total_time

        attend_col   = col_idx(["出勤"])
        late_col     = col_idx(["迟到"])
        absent_col   = col_idx(["旷工"])
        ot_col       = col_idx(["平加"])
        ot_weekend_col = col_idx(["周加"])
        ot_holiday_col = col_idx(["假加"])
        ot_sum_col   = col_idx(["合计加班", "合计"])
        date_col     = col_idx(["考勤日期", "日期"])
        clock_col    = col_idx(["打卡时间", "有效打卡时间"])

        def get_summary_val(idx):
            """直接从汇总行（日期含"至"的行）读取指定列的数值"""
            if idx < 0:
                return 0.0
            for row in rows:
                date_val = row[date_col].strip() if date_col >= 0 else ""
                if "至" in date_val:
                    try:
                        v = row[idx].strip()
                        if v and v not in ("0", ""):
                            if ":" in v:
                                parts = v.split(":")
                                return float(parts[0]) + (float(parts[1]) / 60.0 if len(parts) > 1 else 0)
                            else:
                                return float(v)
                    except:
                        pass
                    return 0.0
            # 汇总行不存在时降级为逐行累加
            return _get_col_sum(idx)

        days         = _get_col_sum(attend_col)
        late         = _get_col_sum(late_col)
        absent       = _get_col_sum(absent_col)
        # 平加：考勤记录表中"平加"列逐行相加后，减去汇总行（最后一行的"平加"）
        # sum_col 已自动跳过汇总行，故此处直接取 sum_col 结果即可
        ot_weekday, ot_debug = sum_col(ot_col)
        ot_weekend, _   = sum_col(ot_weekend_col)
        ot_holiday, _   = sum_col(ot_holiday_col)
        # 合计加班优先从汇总行取，否则三项相加
        _ot_sum_raw  = get_summary_val(ot_sum_col)
        ot_cycle_sum = _ot_sum_raw if _ot_sum_raw else (ot_weekday + ot_weekend + ot_holiday)
        # 目标日期默认为今天
        target_date = target_date or datetime.date.today()

        ot_today = sum_today_ot(date_col, ot_col)

        self.card_total[1].setText(str(len(rows)))
        self.card_days[1].setText(f"{days:.0f}" if days == int(days) else f"{days:.1f}")
        self.card_late[1].setText(str(int(late)))
        self.card_absent[1].setText(str(int(absent)))
        self.card_ot[1].setText(self._format_ot_hours(ot_weekday))

        # 读取配置
        config = self._load_work_config()
        week_mode = config.get("week_mode", "standard")  # standard / big / small

        # 弹性上下班时间（分钟），与ku.py成员变量对应
        standed_up        = self._parse_time_to_min(config.get("work_start",      "07:00"))  # 最早上班
        standed_up_late   = self._parse_time_to_min(config.get("work_start_late", "09:00"))  # 最晚上班
        standed_dowm      = self._parse_time_to_min(config.get("work_end",        "17:00"))  # 标准下班
        rest1_begin       = self._parse_time_to_min(config.get("rest_start",      "12:00"))  # 午饭开始
        rest1_end         = self._parse_time_to_min(config.get("rest_end",        "13:00"))  # 午饭结束
        rest2_begin       = self._parse_time_to_min(config.get("dinner_start",    "17:00"))  # 晚饭开始
        rest2_end         = self._parse_time_to_min(config.get("dinner_end",      "17:45"))  # 晚饭结束

        # 历史日期：current_min 用标准下班时间；今日：用实际当前时间
        is_today = (target_date == datetime.date.today())
        if is_today:
            current_min = datetime.datetime.now().hour * 60 + datetime.datetime.now().minute
        else:
            current_min = standed_dowm  # 历史日期按标准下班计算已工作时长

        # 初始化卡片显示
        should_out_time = "--:--"
        worked_time_str = "00时00分"
        overtime_str    = "00时00分"

        def calc_should_out(first_clock_in, actual_dowm=None):
            """
            计算应下班时间（分钟数）。
            规则：
              1. 确定有效上班时间：
                 - 打卡 < 最早上班  → 用最早上班
                 - 最早上班 ≤ 打卡 < 最晚上班  → 用打卡时间
                 - 打卡 ≥ 最晚上班  → 用打卡时间（迟到但照实）
              2. base = 有效上班时间 + 8H + 午休时长
              3. 若 base < 晚休开始：
                 - 加班设置 = 0 → 直接返回 base
                 - 加班设置 > 0 → 返回 base + 晚休时长 + 加班设置时长
              4. 若 base >= 晚休开始（下班时间本就在晚休之后）：
                 - 加班设置 = 0 → 返回 base（不重复加晚休）
                 - 加班设置 > 0 → 视情况补加晚休 + 加班
            """
            debug_lines = []
            debug_lines.append(f"[calc_should_out] first_clock_in={first_clock_in}({self._min_to_time_str(first_clock_in)}), standed_up={standed_up}({self._min_to_time_str(standed_up)})")
            
            # 步骤1：有效上班时间
            if first_clock_in < standed_up:
                eff_start = standed_up
            else:
                eff_start = first_clock_in
            debug_lines.append(f"[calc_should_out] eff_start={eff_start}({self._min_to_time_str(eff_start)})")

            # 步骤2：base = 有效上班 + 8H + 午休时长
            rest1_len = rest1_end - rest1_begin   # 午休时长（分钟）
            rest2_len = rest2_end - rest2_begin   # 晚休时长（分钟）
            base = eff_start + 8 * 60 + rest1_len
            debug_lines.append(f"[calc_should_out] rest1_len={rest1_len}, rest2_len={rest2_len}, base={base}({self._min_to_time_str(base)})")

            # 加班设置
            ot_h = int(self.combo_ot_h.currentText()) if hasattr(self, 'combo_ot_h') else 0
            ot_m = int(self.combo_ot_m.currentText()) if hasattr(self, 'combo_ot_m') else 0
            ot_total = ot_h * 60 + ot_m
            debug_lines.append(f"[calc_should_out] ot_total={ot_total}({ot_h}h{ot_m}m)")

            # 步骤3/4：根据 (base + ot_total) 与晚休开始时间的关系决定是否加晚休
            result = None
            work_done_time = base + ot_total  # 8小时工作完成后加上加班的时间点
            debug_lines.append(f"[calc_should_out] base({base})={self._min_to_time_str(base)}, ot_total={ot_total}, work_done_time={work_done_time}({self._min_to_time_str(work_done_time)})")
            
            if work_done_time < rest2_begin:
                # 加班后时间仍在晚休开始之前，不加晚休
                debug_lines.append(f"[calc_should_out] work_done_time({work_done_time}) < rest2_begin({rest2_begin}), 不加晚休")
                result = work_done_time
                debug_lines.append(f"[calc_should_out] result=work_done_time={result}({self._min_to_time_str(result)})")
            else:
                # 加班后时间超过晚休开始，需要等晚休
                debug_lines.append(f"[calc_should_out] work_done_time({work_done_time}) >= rest2_begin({rest2_begin}), 加晚休{rest2_len}分钟")
                result = work_done_time + rest2_len
                debug_lines.append(f"[calc_should_out] result=work_done_time+rest2_len={result}({self._min_to_time_str(result)})")
            
            # 写日志
            try:
                with open("debug_should_out.log", "a", encoding="utf-8") as f:
                    for line in debug_lines:
                        f.write(line + "\n")
                    f.write(f"[calc_should_out] FINAL RESULT: {result}({self._min_to_time_str(result)})\n\n")
            except:
                pass
            
            return result

        # 大小周 + 周几 → 今日应工作分钟数（与ku.py work_time_check一致）
        weekday      = target_date.weekday() + 1   # ku.py 用 isocalendar weekday：1=周一, 7=周日
        week_of_year = target_date.isocalendar()[1]

        # zhouliu_week_chek: 1=小周模式(奇数周周六上班), 2=大周模式(偶数周周六上班)
        zhouliu = 1 if week_mode == "small" else (2 if week_mode == "big" else 0)

        def work_time_check():
            if weekday == 6:  # 周六
                if zhouliu == 1:
                    return 7 * 60 if week_of_year % 2 != 0 else 0
                elif zhouliu == 2:
                    return 7 * 60 if week_of_year % 2 == 0 else 0
                else:
                    return 0  # 标准周周六休息
            elif weekday == 7:  # 周日
                return 0
            else:
                return 8 * 60

        total_work_time = work_time_check()  # 今日应工作分钟数

        # 解析今日打卡记录 → up_list / dowm_list（与ku.py up_checkTime_List一致）
        up_list   = []
        dowm_list = []

        for row in rows:
            if date_col < 0:
                continue
            date_str = row[date_col].strip()
            dt = None
            for fmt in ["%Y/%m/%d", "%Y-%m-%d", "%Y%m%d", "%Y.%m.%d"]:
                try:
                    dt = datetime.datetime.strptime(date_str, fmt).date()
                    break
                except:
                    continue
            # 先精确匹配，兜底：仅比较月/日（允许数据年份与目标年份差1年内）
            match = (dt == target_date) if dt else False
            if not match and dt:
                match = (dt.month == target_date.month and dt.day == target_date.day
                         and abs(dt.year - target_date.year) <= 1)
            if match:
                if clock_col >= 0:
                    clock_str = row[clock_col].strip()
                    if clock_str and clock_str not in ("--", ""):
                        # UMS真实格式: "[08:48]，[17:19]，[17:48]，[20:06]"
                        # 先去掉所有方括号，再把中文逗号换英文逗号，最后分割
                        cleaned = clock_str.replace("，", ",").replace("[", "").replace("]", "")
                        parts = cleaned.split(",")
                        cnt = 0
                        for t in parts:
                            t = t.strip()
                            if t and ":" in t:
                                t_min = self._parse_time_to_min(t)
                                if cnt % 2 == 0:
                                    up_list.append(t_min)
                                else:
                                    dowm_list.append(t_min)
                                cnt += 1
                break

        # 与ku.py逻辑一致：up/dowm列表中[0]=0 表示无记录
        up_times   = len(up_list)
        dowm_times = len(dowm_list)
        if up_times == 1 and up_list[0] == 0:
            up_times = 0
        if dowm_times == 1 and dowm_list[0] == 0:
            dowm_times = 0

        # 构建合并打卡记录字符串（按时间顺序显示所有打卡）
        all_times = sorted(up_list + dowm_list)
        clock_records_str = ", ".join(self._min_to_time_str(t) for t in all_times) if all_times else "--"

        if up_times > 0:

            if up_times != dowm_times:
                # ---- 打卡不对等：在上班中，计算应下班时间 ----

                # 应下班时间：用公共计算函数
                title_dowm_time = calc_should_out(up_list[0])
                should_out_time = self._min_to_time_str(title_dowm_time)

                # 求晚饭后上了多少班（reset_time），用于已工作时长修正
                def worktime_after_dinner():
                    reset_time = 0
                    for idx_i, up_t in enumerate(up_list):
                        if up_t > rest2_end:
                            if idx_i - 1 >= 0 and idx_i - 1 < len(dowm_list):
                                prev_dowm = dowm_list[idx_i - 1]
                                if prev_dowm < rest2_end:
                                    reset_time += up_t - rest2_end
                                else:
                                    reset_time += up_t - prev_dowm
                    return reset_time

                reset_time = worktime_after_dinner()

                # 已工作时间
                rest_excluded = check_time_is_include_rest_time(
                    up_list[0], current_min,
                    standed_up, rest1_begin, rest1_end, rest2_begin, rest2_end
                )
                worked_minutes = current_min - up_list[0] - rest_excluded - reset_time

                if worked_minutes > 0:
                    worked_time_str = min2hm(worked_minutes)

                # 已加班
                added_work_time = current_min - total_work_time - up_list[0] - rest_excluded - reset_time
                if added_work_time > 0:
                    overtime_str = min2hm(added_work_time)

                # 还没到上班时间
                if worked_minutes < 0 and current_min < up_list[0]:
                    worked_time_str = f"还可睡{min2hm(up_list[0] - current_min)}"

            else:
                # ---- 打卡对等：今日已下班，计算应下班时间与工作时长 ----
                if dowm_times > 0:
                    # 应下班：用公共计算函数
                    title_dowm_time = calc_should_out(up_list[0], dowm_list[0])
                    should_out_time = self._min_to_time_str(title_dowm_time)

                    total_time = 0
                    for i, up_t in enumerate(up_list):
                        try:
                            seg_rest = check_time_is_include_rest_time(
                                up_t, dowm_list[i],
                                standed_up, rest1_begin, rest1_end, rest2_begin, rest2_end
                            )
                            total_time += dowm_list[i] - up_t - seg_rest
                        except:
                            pass

                    if total_time > 0:
                        worked_time_str = min2hm(total_time)

                    # 今日加班 = 实际工作时长 - 8小时标准工作时长（不受加班设置影响）
                    overtime_minutes = total_time - total_work_time
                    if overtime_minutes > 0:
                        overtime_str = min2hm(overtime_minutes)

        else:
            # ---- 今日还没打卡 ----
            # 未打卡时以最早上班时间作为参考
            title_dowm_time = calc_should_out(standed_up)
            should_out_time = self._min_to_time_str(title_dowm_time)

            if current_min < standed_up:
                worked_time_str = f"还可睡{min2hm(standed_up - current_min)}"

        # 更新考勤周期加班汇总
        # 更新右侧详情面板
        if hasattr(self, '_detail_lines'):
            self._detail_lines["clock_records"].setText(clock_records_str)
            self._detail_lines["should_out"].setText(should_out_time)
            self._detail_lines["worked"].setText(worked_time_str)
            self._detail_lines["overtime"].setText(overtime_str)
            self._detail_lines["ot_weekday"].setText(self._format_ot_hours(ot_weekday))
            self._detail_lines["ot_weekend"].setText(self._format_ot_hours(ot_weekend))
            self._detail_lines["ot_holiday"].setText(self._format_ot_hours(ot_holiday))
            self._detail_lines["ot_cycle_sum"].setText(self._format_ot_hours(ot_cycle_sum))

        # 更新左侧迟到/早退次数
        if hasattr(self, '_lbl_late'):
            self._lbl_late.setText(str(int(late)))
        # 早退次数
        early_col = col_idx(["早退"])
        early, _ = sum_col(early_col)
        if hasattr(self, '_lbl_early'):
            self._lbl_early.setText(str(int(early)))

    def _parse_time_to_min(self, time_str):
        """将时间字符串转换为分钟数"""
        try:
            if isinstance(time_str, str):
                parts = time_str.strip().split(":")
                if len(parts) == 2:
                    h, m = int(parts[0]), int(parts[1])
                    return h * 60 + m
            return 0
        except:
            return 0

    def _min_to_time_str(self, minutes):
        """将分钟数转换为时间字符串 HH:MM"""
        h = int(minutes) // 60
        m = int(minutes) % 60
        return f"{h}:{m:02d}"

    def _format_ot_hours(self, hours):
        """将小数小时转换为 时.分 格式显示 (例: 17.25 -> 17.15 表示17小时15分钟)"""
        if not hours or hours <= 0:
            return "0"
        h = int(hours)
        m = round((hours - h) * 60)
        # 防止进位问题 (如 17.9999 应该显示为 18.00)
        if m >= 60:
            h += 1
            m = 0
        return f"{h}.{m:02d}"
        m = int(minutes) % 60
        return f"{h:02d}:{m:02d}"

    def _refresh_detail_panel(self):
        """根据当前日期下拉选择，刷新右侧详情面板"""
        if not self._has_data:
            return
        # 从下拉框取选中的日期（itemData 返回 QVariant，需 toPython 还原）
        idx = self.combo_date.currentIndex()
        if idx >= 0:
            raw = self.combo_date.itemData(idx)
            if hasattr(raw, 'toPython'):
                target_date = raw.toPython()
            else:
                target_date = raw  # fallback
        else:
            target_date = datetime.date.today()
        self._update_stats(self._headers, self._all_data, target_date)

    def _quick_select(self, idx):
        """兼容旧代码（快捷日期选择），新UI不需要此控件但保留接口"""
        pass

    def _filter_table(self, keyword):
        """兼容旧代码（搜索框），新UI保留功能"""
        kw = keyword.lower()
        if not kw:
            self._populate_table(self._headers, self._all_data)
            return
        filtered = [r for r in self._all_data if any(kw in str(c).lower() for c in r)]
        self._populate_table(self._headers, filtered)

    def _export_csv(self):
        if not self._all_data:
            QMessageBox.information(self, "提示", "暂无数据可导出。")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "导出考勤数据",
            f"考勤记录_{datetime.date.today()}.csv",
            "CSV Files (*.csv);;All Files (*)"
        )
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(self._headers)
                writer.writerows(self._all_data)
            QMessageBox.information(self, "导出成功", f"数据已保存到：\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", str(e))

    def _init_tray(self):
        """初始化系统托盘"""
        from PyQt5.QtWidgets import QSystemTrayIcon, QMenu, QAction
        
        # 创建托盘图标
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setToolTip(f"考勤管理系统 - {self.username}")
        
        # 初始使用工号首字母蓝色圆形图标，头像加载成功后会被替换
        self.tray_icon.setIcon(self._make_letter_icon(32))
        
        # 创建托盘菜单
        tray_menu = QMenu()
        
        # 显示主窗口
        act_show = QAction("显示主窗口", self)
        act_show.triggered.connect(self.showNormal)
        act_show.setIcon(self.style().standardIcon(QStyle.SP_TitleBarMaxButton))
        tray_menu.addAction(act_show)
        
        tray_menu.addSeparator()
        
        # 刷新考勤
        act_refresh = QAction("刷新考勤数据", self)
        act_refresh.triggered.connect(self._fetch_data)
        act_refresh.setIcon(self.style().standardIcon(QStyle.SP_BrowserReload))
        tray_menu.addAction(act_refresh)
        
        tray_menu.addSeparator()
        
        # 退出
        act_quit = QAction("退出", self)
        act_quit.triggered.connect(self._logout)
        act_quit.setIcon(self.style().standardIcon(QStyle.SP_TitleBarCloseButton))
        tray_menu.addAction(act_quit)
        
        self.tray_icon.setContextMenu(tray_menu)
        
        # 双击托盘图标显示主窗口
        self.tray_icon.activated.connect(self._on_tray_activated)
        
        # 显示托盘图标
        self.tray_icon.show()
    
    def _on_tray_activated(self, reason):
        """托盘图标被点击"""
        if reason == QSystemTrayIcon.DoubleClick or reason == QSystemTrayIcon.Trigger:
            self.showNormal()
            self.activateWindow()
    
    def closeEvent(self, event):
        """窗口关闭事件，最小化到托盘而不是退出"""
        # 退出登录时直接关闭，不弹对话框
        if self._is_logging_out:
            self.tray_icon.hide()
            event.accept()
            return

        reply = QMessageBox.question(
            self, "关闭确认", "是否最小化到系统托盘？（在托盘双击可恢复）",
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
        )
        if reply == QMessageBox.Yes:
            # 最小化到托盘
            self.hide()
            event.ignore()
        elif reply == QMessageBox.No:
            # 真正退出
            self.tray_icon.hide()
            event.accept()
        else:
            # 取消
            event.ignore()
    
    def hideEvent(self, event):
        """窗口隐藏时最小化到托盘"""
        if self.isMinimized():
            self.tray_icon.showMessage(
                "考勤管理系统",
                "程序已最小化到系统托盘，双击图标可恢复",
                QSystemTrayIcon.Information,
                2000
            )

    def _logout(self):
        reply = QMessageBox.question(
            self, "退出确认", "确认退出登录？",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self._is_logging_out = True  # 设置标志，绕过closeEvent对话框
            # 返回登录界面而不是关闭程序
            if self.login_window:
                self.login_window.show()
            self.close()

    def _open_config(self):
        """打开上下班配置弹窗"""
        self._config_win = ConfigWindow()
        self._config_win.setWindowModality(Qt.ApplicationModal)
        self._config_win.show()

    def _load_work_config(self):
        """加载上下班配置（默认值与ku.py对齐）"""
        cfg_path = os.path.join(os.path.expanduser("~"), ".attendance_tool_cfg.json")
        config = {
            "work_start":      "07:00",   # 最早上班时间
            "work_start_late": "09:00",   # 最晚上班时间
            "work_end":        "17:00",   # 标准下班时间
            "rest_start":      "12:00",   # 午饭开始
            "rest_end":        "13:00",   # 午饭结束
            "dinner_start":    "17:00",   # 晚饭开始
            "dinner_end":      "17:45",   # 晚饭结束
            "flex_enabled":    False,
            "remind_enabled":  True,
            "remind_time":     "18:00",
            "week_mode":       "standard",
            "late_threshold":  0,
        }
        if os.path.exists(cfg_path):
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    saved = json.load(f).get("work_config", {})
                    config.update(saved)
            except Exception:
                pass
        return config


# ─────────────────────────────────────────────
#  应用入口
# ─────────────────────────────────────────────
def main():
    import traceback

    # ── 崩溃日志路径（exe 同目录）
    _crash_log = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "crash.log")

    def _write_crash(exc_type, exc_val, exc_tb):
        try:
            with open(_crash_log, "a", encoding="utf-8") as f:
                f.write(f"\n{'='*60}\n")
                f.write(f"崩溃时间: {datetime.datetime.now()}\n")
                f.writelines(traceback.format_exception(exc_type, exc_val, exc_tb))
        except Exception:
            pass
        sys.__excepthook__(exc_type, exc_val, exc_tb)

    sys.excepthook = _write_crash

    # ─────────────────────────────────────────────
    #  单实例检查
    # ─────────────────────────────────────────────
    app_id = "AttendanceTool_SingleInstance"
    server = None
    socket = QLocalSocket()
    socket.connectToServer(app_id)
    if socket.waitForConnected(500):
        # 已有实例在运行，发送激活信号后退出
        socket.close()
        print("程序已在运行中，正在激活...")
        sys.exit(0)
    else:
        # 没有实例在运行，创建服务器
        server = QLocalServer()
        server.listen(app_id)

    try:
        app = QApplication(sys.argv)
        app.setApplicationName("考勤管理系统")
        app.setStyle("Fusion")
        app.setFont(QFont("Microsoft YaHei", 10))

        login_win = LoginWindow()
        main_win_holder = [None]

        def on_login_success(cookies, username):
            print(f"[DEBUG] on_login_success called, existing main_win: {main_win_holder[0]}")
            try:
                if main_win_holder[0] is not None:
                    print("[DEBUG] 主窗口已存在，关闭旧窗口")
                    main_win_holder[0].close()
                login_win.hide()
                mw = MainWindow(cookies, username, login_window=login_win)
                main_win_holder[0] = mw
                mw.show()
                print(f"[DEBUG] 新主窗口已创建并显示: {id(mw)}")
            except Exception:
                _write_crash(*sys.exc_info())
                QMessageBox.critical(None, "启动失败",
                    f"主窗口启动异常，详见 crash.log:\n{traceback.format_exc()}")

        login_win.login_success.connect(on_login_success)
        login_win.show()
        exit_code = app.exec_()
        # 清理服务器
        if server:
            server.close()
        sys.exit(exit_code)
    except Exception:
        _write_crash(*sys.exc_info())
        raise
    finally:
        # 确保服务器被关闭
        if server:
            server.close()


if __name__ == "__main__":
    main()
