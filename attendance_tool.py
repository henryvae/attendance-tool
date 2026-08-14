"""
考勤管理工具 - intretech UMS 系统
https://ums.intretech.com/ums/AtteUserReportManage.aspx

v96 - 修复应下班时间：加班=0不加晚休；加班>0超过晚休开始才加晚休（用实际打卡替代配置rest2_end）

v90 - 修复下班提醒弹窗：已到下班时间时显示"已到下班时间"（蓝色标题），未到时显示"还有X分钟"；_check_remind 下班后1小时内均可触发

v73 - 新增下班弹窗提醒功能（托盘气泡）；设置弹窗新增"下班提醒提前量"配置

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

APP_VERSION = "v107"
import json
import asyncio
import threading

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QDateEdit, QGroupBox, QMessageBox, QStatusBar, QFrame,
    QHeaderView, QComboBox, QProgressBar,
    QAbstractItemView, QFileDialog, QCheckBox, QStackedWidget,
    QSystemTrayIcon, QMenu, QAction, QTimeEdit,
    QStyle, QDialog, QSpinBox, QSizePolicy,
)
from PyQt5.QtCore import Qt, QDate, QThread, pyqtSignal, QTimer, QTime, QSize
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
    "primary":    "#4F6BF6",
    "primary_dk": "#4358E0",
    "accent":     "#6E85FF",
    "bg":         "#F6F7FB",
    "card":       "#FFFFFF",
    "text":       "#1A1D26",
    "text_sec":   "#6B7280",
    "border":     "#E8EAF0",
    "success":    "#16A34A",
    "warning":    "#D97706",
    "danger":     "#DC2626",
    "header_bg":  "#4F6BF6",
    "row_alt":    "#F6F7FB",
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

# ─────────────────────────────────────────────
#  现代简约主题（全局 QSS，与 UI设计方案.html / theme_modern.qss 一致）
# ─────────────────────────────────────────────
STYLE_MODERN = """
/* ═══════════════════════════════════════════
   考勤管理工具 · 现代简约主题
   主色 #4F6BF6   背景 #F6F7FB   卡片 #FFFFFF
   ═══════════════════════════════════════════ */
QWidget {
    font-family: "Microsoft YaHei UI", "Segoe UI", "PingFang SC", sans-serif;
    font-size: 13px;
    color: #1A1D26;
}
QMainWindow, QDialog { background: #F6F7FB; }
#centralRoot { background: #F6F7FB; }

/* ── 卡片容器 ── */
QFrame#card, QGroupBox {
    background: #FFFFFF;
    border: 1px solid #E8EAF0;
    border-radius: 12px;
}
QFrame#card:hover { border-color: #D6DAE4; }

/* ── 顶栏 ── */
#topBar {
    background: #FFFFFF;
    border: none;
    border-bottom: 1px solid #E8EAF0;
}
#topBar QLabel { color: #1A1D26; background: transparent; }
#appLogo { font-size: 20px; font-weight: 700; color: #4F6BF6; }
#appLogoBox {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #6E85FF, stop:0.7 #4F6BF6, stop:1 #3B4FD8);
    border-radius: 9px;
}
#appLogoBox QLabel { color: #FFFFFF; font-size: 16px; background: transparent; }
#appTitle { font-size: 14px; font-weight: 700; }
#versionBadge {
    color: #4F6BF6;
    background: #EDF0FE;
    border-radius: 9px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 600;
}
#userName { font-size: 13px; font-weight: 600; color: #3A4050; }

/* ── 头像 ── */
#avatar {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #6E85FF, stop:1 #4F6BF6);
    border-radius: 20px;
    color: #FFFFFF;
    font-size: 13px;
    font-weight: 700;
}

/* ── 侧边导航 ── */
#sideBar {
    background: #FFFFFF;
    border: none;
    border-right: 1px solid #E8EAF0;
}
QPushButton#navItem {
    background: transparent;
    border: none;
    border-radius: 9px;
    color: #6B7280;
    font-size: 13px;
    font-weight: 600;
    padding: 8px 12px;
    text-align: left;
}
QPushButton#navItem:hover { background: #F6F7FB; color: #1A1D26; }
QPushButton#navItem:checked {
    background: #EDF0FE;
    color: #4F6BF6;
}
#navGroupLabel {
    color: #9CA3AF;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1px;
    padding: 12px 12px 4px;
    background: transparent;
}

/* ── 分段控件（本月/上月）── */
#segControl {
    background: #F6F7FB;
    border: 1px solid #E8EAF0;
    border-radius: 9px;
    padding: 3px;
}
#segControl QPushButton {
    background: transparent;
    border: none;
    border-radius: 7px;
    color: #6B7280;
    font-size: 12px;
    font-weight: 600;
    padding: 6px 16px;
}
#segControl QPushButton:hover { color: #1A1D26; }
#segControl QPushButton:checked {
    background: #FFFFFF;
    color: #4F6BF6;
    border: 1px solid #E8EAF0;
}

/* ── 页面标题 / 打卡时间线 ── */
#pageTitle { font-size: 17px; font-weight: 800; color: #1A1D26; }
#timelineDotIn {
    background: #16A34A;
    border-radius: 4px;
}
#timelineDotOut {
    background: #4F6BF6;
    border-radius: 4px;
}
#tlTime {
    font-family: "JetBrains Mono", "Consolas", monospace;
    font-size: 15px;
    font-weight: 700;
    color: #1A1D26;
    min-width: 56px;
}
#tlLabel { font-size: 13px; color: #3A4050; }
#countdownBox {
    background: #FBFBFE;
    border: 1.5px solid #D6DAE4;
    border-radius: 8px;
    color: #1A1D26;
    font-family: "JetBrains Mono", "Consolas", monospace;
    font-size: 13px;
    font-weight: 700;
}

/* ── 分组标题 / 详情行 ── */
#sectionTitle { font-size: 13px; font-weight: 700; color: #1A1D26; }
#detailKey { font-size: 13px; color: #6B7280; }
#detailVal { font-size: 13px; font-weight: 700; color: #1A1D26; }
#detailValMono {
    font-family: "JetBrains Mono", "Consolas", monospace;
    font-size: 13px; font-weight: 700; color: #1A1D26;
}

/* ── 指标卡 ── */
#metricCard {
    background: #FFFFFF;
    border: 1px solid #E8EAF0;
    border-radius: 12px;
}
#metricCard:hover { border-color: #D6DAE4; }
#metricTitle { font-size: 12px; color: #6B7280; font-weight: 600; }
#metricValue {
    font-family: "JetBrains Mono", "Consolas", monospace;
    font-size: 26px; font-weight: 800; color: #1A1D26;
}
#metricValuePrimary {
    font-family: "JetBrains Mono", "Consolas", monospace;
    font-size: 26px; font-weight: 800; color: #4F6BF6;
}
#metricValueWarning {
    font-family: "JetBrains Mono", "Consolas", monospace;
    font-size: 26px; font-weight: 800; color: #D97706;
}
#metricValueSuccess {
    font-family: "JetBrains Mono", "Consolas", monospace;
    font-size: 26px; font-weight: 800; color: #16A34A;
}
#metricValueDanger {
    font-family: "JetBrains Mono", "Consolas", monospace;
    font-size: 26px; font-weight: 800; color: #DC2626;
}

/* 强调卡（应下班时间：渐变主色底） */
#metricCardAccent {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #4F6BF6, stop:1 #6E85FF);
    border: none;
    border-radius: 12px;
}
#metricCardAccent #metricTitle { color: rgba(255,255,255,0.82); }
#metricCardAccent #metricValue,
#metricCardAccent #metricValuePrimary,
#metricCardAccent #metricValueWarning,
#metricCardAccent #metricValueSuccess {
    color: #FFFFFF;
}

/* ── 输入框 ── */
QLineEdit, QSpinBox, QComboBox, QDateEdit, QTimeEdit {
    background: #FBFBFE;
    border: 1.5px solid #D6DAE4;
    border-radius: 8px;
    padding: 4px 10px;
    font-size: 13px;
    color: #1A1D26;
    selection-background-color: #4F6BF6;
    selection-color: #FFFFFF;
}
QLineEdit:hover, QSpinBox:hover, QComboBox:hover, QDateEdit:hover, QTimeEdit:hover {
    border-color: #9CA3AF;
}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus, QDateEdit:focus, QTimeEdit:focus {
    border-color: #4F6BF6;
    background: #FFFFFF;
}
QLineEdit:disabled { background: #F6F7FB; color: #9CA3AF; }

/* ── 下拉列表 ── */
QComboBox::drop-down { width: 24px; border: none; }
QComboBox::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #6B7280;
    margin-right: 8px;
}
QComboBox QAbstractItemView {
    background: #FFFFFF;
    border: 1px solid #E8EAF0;
    border-radius: 8px;
    outline: none;
    selection-background-color: #EDF0FE;
    selection-color: #4F6BF6;
    padding: 4px;
}
QComboBox QAbstractItemView::item {
    min-height: 28px;
    padding: 4px 10px;
    border-radius: 6px;
}
QComboBox QAbstractItemView::item:hover {
    background: #EDF0FE;
    color: #4F6BF6;
}

/* ── 按钮 ── */
QPushButton {
    background: #FFFFFF;
    color: #3A4050;
    border: 1.5px solid #D6DAE4;
    border-radius: 8px;
    padding: 7px 16px;
    font-size: 13px;
    font-weight: 600;
}
QPushButton:hover { border-color: #4F6BF6; color: #4F6BF6; background: #F5F7FF; }
QPushButton:pressed { background: #EDF0FE; }
QPushButton:disabled { color: #9CA3AF; border-color: #E8EAF0; background: #F6F7FB; }

/* 主按钮 */
QPushButton#btnPrimary {
    background: #4F6BF6;
    color: #FFFFFF;
    border: none;
    border-radius: 8px;
    font-weight: 600;
    padding: 9px 20px;
}
QPushButton#btnPrimary:hover { background: #4358E0; }
QPushButton#btnPrimary:pressed { background: #3B4FD8; }
QPushButton#btnPrimary:disabled { background: #A5B4FB; color: #FFFFFF; }

/* 危险按钮 */
QPushButton#btnDanger { color: #DC2626; border-color: #F3C1C1; background: #FFFFFF; }
QPushButton#btnDanger:hover { background: #FDEBEB; border-color: #DC2626; }

/* 图标按钮 */
QPushButton#iconBtn {
    background: #FFFFFF;
    border: 1px solid #E8EAF0;
    border-radius: 8px;
    padding: 0;
    min-width: 32px; max-width: 32px;
    min-height: 32px; max-height: 32px;
    font-size: 16px;
    color: #6B7280;
    text-align: center;
}
QPushButton#iconBtn:hover { color: #4F6BF6; border-color: #4F6BF6; background: #F5F7FF; }

/* ── 进度条 ── */
QProgressBar {
    background: #EDF0FE;
    border: none;
    border-radius: 4px;
    text-align: center;
    color: transparent;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #6E85FF, stop:1 #4F6BF6);
    border-radius: 4px;
}

/* ── 复选框 / 单选 ── */
QCheckBox { spacing: 8px; color: #3A4050; font-size: 13px; }
QCheckBox::indicator {
    width: 18px; height: 18px; border-radius: 5px;
    border: 1.5px solid #D6DAE4; background: #FFFFFF;
}
QCheckBox::indicator:hover { border-color: #4F6BF6; }
QCheckBox::indicator:checked { background: #4F6BF6; border-color: #4F6BF6; }
QRadioButton { spacing: 8px; color: #3A4050; font-size: 13px; }
QRadioButton::indicator {
    width: 16px; height: 16px; border-radius: 9px;
    border: 1.5px solid #D6DAE4; background: #FFFFFF;
}
QRadioButton::indicator:hover { border-color: #4F6BF6; }
QRadioButton::indicator:checked { background: #4F6BF6; border-color: #4F6BF6; }

/* ── 标签 ── */
QLabel { background: transparent; color: #3A4050; }
QLabel#h1 { font-size: 26px; font-weight: 800; color: #1A1D26; }
QLabel#h3 { font-size: 14px; font-weight: 700; color: #1A1D26; }
QLabel#caption { font-size: 12px; color: #9CA3AF; }
QLabel#valueMono {
    font-family: "JetBrains Mono", "Consolas", monospace;
    font-weight: 700; color: #1A1D26;
}
QLabel#valuePrimary {
    font-family: "JetBrains Mono", "Consolas", monospace;
    font-weight: 700; color: #4F6BF6;
}
QLabel#valueSuccess { color: #16A34A; font-weight: 700; }
QLabel#valueWarning { color: #D97706; font-weight: 700; }
QLabel#valueDanger { color: #DC2626; font-weight: 700; }

/* ── 分割线 ── */
QFrame#hsep { background: #E8EAF0; max-height: 1px; border: none; }

/* ── 状态栏 ── */
#statusBar {
    background: #F6F7FB;
    border-top: 1px solid #E8EAF0;
    color: #6B7280;
    font-size: 12px;
    padding: 6px 10px;
}

/* ── 表格 ── */
QTableWidget {
    background: #FFFFFF;
    border: 1px solid #E8EAF0;
    border-radius: 10px;
    gridline-color: #F0F1F5;
    alternate-background-color: #FAFAFD;
    selection-background-color: #EDF0FE;
    selection-color: #1A1D26;
    font-size: 13px;
}
QTableWidget::item { padding: 6px 10px; border: none; }
QTableWidget::item:hover { background: #F5F7FF; }
QHeaderView::section {
    background: #FBFBFE;
    color: #6B7280;
    font-weight: 700;
    font-size: 12px;
    padding: 9px 10px;
    border: none;
    border-bottom: 1px solid #E8EAF0;
}
QTableCornerButton::section { background: #FBFBFE; border: none; border-bottom: 1px solid #E8EAF0; }

/* ── 滚动条 ── */
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #D6DAE4; border-radius: 5px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #9CA3AF; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: #D6DAE4; border-radius: 5px; min-width: 30px; }
QScrollBar::handle:horizontal:hover { background: #9CA3AF; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

/* ── 弹窗 / 提示 ── */
QMessageBox { background: #FFFFFF; }
QMessageBox QLabel { font-size: 13px; color: #1A1D26; }
QMessageBox QPushButton { min-width: 76px; min-height: 32px; }
QToolTip {
    background: #1A1D26;
    color: #FFFFFF;
    border: none;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 12px;
}
QMenu {
    background: #FFFFFF;
    border: 1px solid #E8EAF0;
    border-radius: 10px;
    padding: 6px;
}
QMenu::item { padding: 7px 26px 7px 14px; border-radius: 6px; color: #3A4050; font-size: 13px; }
QMenu::item:selected { background: #EDF0FE; color: #4F6BF6; }
QMenu::separator { height: 1px; background: #E8EAF0; margin: 4px 8px; }

/* ── 下班提醒弹窗 ── */
#remindDialog { background: #FFFFFF; border-radius: 14px; }
#remindIcon { font-size: 30px; }
#remindTitle { font-size: 17px; font-weight: 800; color: #1A1D26; }
#remindSub { font-size: 13px; color: #6B7280; }
#remindOut {
    font-size: 13px;
    color: #4F6BF6;
    font-weight: 700;
    font-family: "JetBrains Mono", "Consolas", monospace;
}
#remindAuto { font-size: 11px; color: #9CA3AF; }

/* ── 页面布局补充（三段式内容页）── */
#pageRoot { background: #F6F7FB; }
#overviewControl {
    background: #FFFFFF;
    border: 1px solid #E8EAF0;
    border-radius: 12px;
}
#topBarHint { font-size: 12px; color: #6B7280; font-weight: 600; }
#timelineDotMuted { background: #E8EAF0; border-radius: 4px; }
#sideBrand { font-size: 14px; font-weight: 700; color: #1A1D26; }
#navLogout {
    background: transparent;
    border: none;
    border-radius: 9px;
    color: #DC2626;
    font-size: 13px;
    font-weight: 600;
    padding: 8px 12px;
    text-align: left;
}
#navLogout:hover { background: #FDEBEB; color: #DC2626; }
#navLogout:pressed { background: #F9D2D2; }
#settingsCard { background: #FFFFFF; border: 1px solid #E8EAF0; border-radius: 12px; }
#otCard { background: #FFFFFF; border: 1px solid #E8EAF0; border-radius: 12px; }
"""

STYLE_LOGIN = f"""
QWidget {{
    background-color: {THEME['bg']};
    font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
}}
"""

# 登录窗背景：柔和渐变 + 右上角光斑（通过代码设置，不使用 STYLE_LOGIN）
LOGIN_BG_QSS = """
QWidget#loginRoot {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #EEF1FF, stop:0.4 #F6F7FB, stop:1 #F0F4FF);
}
QWidget#glowBox {
    background: qradialgradient(cx:0.5, cy:0.5, radius:1.0, fx:0.5, fy:0.5,
        stop:0 rgba(79,107,246,0.15), stop:1 rgba(79,107,246,0));
    border: none;
}
"""


class _SignalLabel(QLabel):
    """在 setText 时发出 textSet 信号的 QLabel。
    用于在不改动核心逻辑的前提下，把某个数据标签的更新同步到另一处展示。"""

    textSet = pyqtSignal(str)

    def setText(self, text):
        super().setText(text)
        self.textSet.emit(str(text))


# ─────────────────────────────────────────────
#  登录窗口
# ─────────────────────────────────────────────
class LoginWindow(QWidget):
    login_success = pyqtSignal(list, str)  # cookies, username

    def __init__(self):
        super().__init__()
        self.setWindowTitle("考勤管理系统 · 登录")
        self.setFixedSize(460, 560)
        self.setStyleSheet(LOGIN_BG_QSS)  # 代码内渐变背景，不使用空的 STYLE_LOGIN
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
        # ── 根容器：柔和渐变背景 ──
        root = QWidget(self)
        root.setObjectName("loginRoot")
        root_lay = QVBoxLayout(root)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(0)

        # 让渐变背景 root 填满整个登录窗口，避免右侧/底部出现空白
        main_lay = QVBoxLayout(self)
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.setSpacing(0)
        main_lay.addWidget(root)

        # ── 右上角淡蓝色光斑装饰 ──
        glow = QFrame(root)
        glow.setObjectName("glowBox")
        glow.setFixedSize(280, 280)
        glow.move(200, -90)
        glow.raise_()

        # ── 水平居中白色圆角卡片 ──
        center_vb = QVBoxLayout()
        center_vb.setContentsMargins(0, 0, 0, 0)
        center_vb.setSpacing(0)

        self._card = QFrame()
        self._card.setObjectName("loginCard")
        self._card.setFixedWidth(380)
        self._card.setStyleSheet(
            "QFrame#loginCard { background: #FFFFFF; border: 1px solid #E8EAF0;"
            " border-radius: 16px; }")

        # 卡片大阴影（近似设计稿 box-shadow: lg）
        try:
            from PyQt5.QtWidgets import QGraphicsDropShadowEffect
            _sh = QGraphicsDropShadowEffect(self._card)
            _sh.setBlurRadius(48)
            _sh.setOffset(0, 10)
            _sh.setColor(QColor(26, 29, 38, 55))
            self._card.setGraphicsEffect(_sh)
        except Exception:
            pass

        cl = QVBoxLayout(self._card)
        cl.setContentsMargins(36, 32, 36, 26)
        cl.setSpacing(0)

        # ── 48px 渐变 Logo ──
        logo_box = QFrame()
        logo_box.setObjectName("loginLogoBox")
        logo_box.setFixedSize(48, 48)
        logo_box.setStyleSheet(
            "QFrame#loginLogoBox { background: qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            " stop:0 #6E85FF, stop:0.7 #4F6BF6, stop:1 #3B4FD8);"
            " border-radius: 14px; }")
        logo_lay = QVBoxLayout(logo_box)
        logo_lay.setContentsMargins(0, 0, 0, 0)
        logo_lbl = QLabel("\U0001F4C5")
        logo_lbl.setAlignment(Qt.AlignCenter)
        logo_lbl.setStyleSheet("font-size: 24px; background: transparent;")
        logo_lay.addWidget(logo_lbl)
        cl.addWidget(logo_box)

        # ── 标题 / 副标题 ──
        lbl_welcome = QLabel("欢迎回来")
        lbl_welcome.setStyleSheet(
            "font-size: 20px; font-weight: 800; color: #1A1D26;"
            " background: transparent; margin-top: 18px;")
        cl.addWidget(lbl_welcome)

        lbl_sub = QLabel("登录 UMS 系统查看你的考勤")
        lbl_sub.setStyleSheet(
            "font-size: 13px; color: #6B7280; background: transparent;"
            " margin-top: 4px; margin-bottom: 26px;")
        cl.addWidget(lbl_sub)

        # ── 工号 ──
        lbl_u = QLabel("工号")
        lbl_u.setStyleSheet(
            "font-size: 12px; font-weight: 600; color: #3A4050;"
            " background: transparent; margin-bottom: 6px;")
        cl.addWidget(lbl_u)

        self.input_user = QLineEdit()
        self.input_user.setPlaceholderText("请输入工号")
        self.input_user.setClearButtonEnabled(True)
        self.input_user.setFixedHeight(44)
        self.input_user.setStyleSheet(
            "QLineEdit { border: 1.5px solid #D6DAE4; border-radius: 10px;"
            " padding: 0 14px; font-size: 14px; background: #FBFBFE; }"
            "QLineEdit:focus { border-color: #4F6BF6; background: #FFFFFF; }")
        cl.addWidget(self.input_user)
        cl.addSpacing(16)

        # ── 密码 ──
        lbl_p = QLabel("密码")
        lbl_p.setStyleSheet(
            "font-size: 12px; font-weight: 600; color: #3A4050;"
            " background: transparent; margin-bottom: 6px;")
        cl.addWidget(lbl_p)

        pwd_row = QHBoxLayout()
        pwd_row.setContentsMargins(0, 0, 0, 0)
        pwd_row.setSpacing(8)
        self.input_pwd = QLineEdit()
        self.input_pwd.setPlaceholderText("请输入密码")
        self.input_pwd.setEchoMode(QLineEdit.Password)
        self.input_pwd.setFixedHeight(44)
        self.input_pwd.setStyleSheet(
            "QLineEdit { border: 1.5px solid #D6DAE4; border-radius: 10px;"
            " padding: 0 14px; font-size: 14px; background: #FBFBFE; }"
            "QLineEdit:focus { border-color: #4F6BF6; background: #FFFFFF; }")
        pwd_row.addWidget(self.input_pwd, stretch=1)

        self.btn_eye = QPushButton("\U0001F441")
        self.btn_eye.setFixedSize(44, 44)
        self.btn_eye.setCursor(Qt.PointingHandCursor)
        self.btn_eye.setStyleSheet(
            "QPushButton { background: #F0F0F0;"
            " border: 1.5px solid #E8EAF0; border-radius: 10px; font-size: 17px; }"
            "QPushButton:hover { background: #E0E0E0; border-color: #4F6BF6; }")
        self.btn_eye.clicked.connect(self._toggle_pwd_visibility)
        pwd_row.addWidget(self.btn_eye)
        cl.addLayout(pwd_row)
        cl.addSpacing(14)

        # ── 记住账号 / 记住密码 ──
        remember_row = QHBoxLayout()
        remember_row.setContentsMargins(0, 0, 0, 0)
        remember_row.setSpacing(18)
        self.chk_remember = QCheckBox("记住账号")
        self.chk_remember_pwd = QCheckBox("记住密码")
        remember_row.addWidget(self.chk_remember)
        remember_row.addWidget(self.chk_remember_pwd)
        remember_row.addStretch()
        cl.addLayout(remember_row)
        cl.addSpacing(22)

        # ── 主按钮「登 录」 ──
        self.btn_login = QPushButton("登 录")
        self.btn_login.setObjectName("btnLogin")
        self.btn_login.setFixedHeight(44)
        self.btn_login.setCursor(Qt.PointingHandCursor)
        self.btn_login.setStyleSheet(
            "QPushButton { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            " stop:0 #4F6BF6, stop:1 #6E85FF); color: white; border: none;"
            " border-radius: 10px; font-size: 15px; font-weight: 600;"
            " letter-spacing: 6px; }"
            "QPushButton:hover { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            " stop:0 #4358E0, stop:1 #4F6BF6); margin-top: -2px; margin-bottom: 2px; }"
            "QPushButton:pressed { margin-top: 0px; margin-bottom: 0px; }"
            "QPushButton:disabled { background: #BDBDBD; }")
        self.btn_login.clicked.connect(self._do_login)
        cl.addWidget(self.btn_login)

        # ── 底部细进度条 ──
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        self.progress.setFixedHeight(4)
        self.progress.setStyleSheet(
            "QProgressBar{border:none;background:#EDF0FE;border-radius:2px;margin-top:14px;}"
            "QProgressBar::chunk{background:#4F6BF6;border-radius:2px;}")
        cl.addWidget(self.progress)

        # ── 红色错误提示条 ──
        self.lbl_err = QLabel("")
        self.lbl_err.setAlignment(Qt.AlignCenter)
        self.lbl_err.setWordWrap(True)
        self.lbl_err.setMinimumHeight(20)
        self.lbl_err.setStyleSheet(
            "color: #DC2626; font-size: 13px; background: transparent; margin-top: 12px;")
        cl.addWidget(self.lbl_err)

        center_vb.addStretch()
        center_vb.addWidget(self._card, alignment=Qt.AlignHCenter)
        center_vb.addStretch()
        root_lay.addLayout(center_vb, 1)

        # 回车快捷登录
        self.input_user.returnPressed.connect(self._do_login)
        self.input_pwd.returnPressed.connect(self._do_login)


    def _do_login(self):
        # 使用标志位防止重复登录
        if self._is_logging_in:
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

        self._worker = LoginWorker(username, password)
        # 连接安装进度信号
        self._worker.install_progress.connect(self._on_install_progress)
        self._worker.success.connect(lambda c: self._on_success(c, username))
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

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
        self.progress.setVisible(False)
        self.btn_login.setEnabled(True)
        self._is_logging_in = False  # 重置登录标志
        self.login_success.emit(cookies, username)

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
        self.setFixedSize(380, 370)
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
        btn_cancel.clicked.connect(self.close)
        btn_row.addWidget(btn_cancel)

        btn_save = QPushButton("保存配置")
        btn_save.setObjectName("btnPrimary")
        btn_save.setFixedHeight(40)
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
#  下班提醒弹窗
# ─────────────────────────────────────────────
class OffWorkRemindDialog(QDialog):
    """下班提醒弹窗：360×240，居中，30秒自动关闭"""

    def __init__(self, remain_txt: str, should_out_str: str, is_arrived: bool = False, parent=None):
        super().__init__(parent)
        self.setWindowTitle("下班提醒")
        self.setObjectName("remindDialog")
        self.setFixedSize(360, 240)
        self.setWindowFlags(Qt.Dialog | Qt.WindowStaysOnTopHint)
        self._auto_close_remain = 30  # 自动关闭倒计时（秒）

        # 屏幕居中
        screen = QApplication.primaryScreen().geometry()
        self.move(
            (screen.width() - self.width()) // 2,
            (screen.height() - self.height()) // 2,
        )

        vb = QVBoxLayout(self)
        vb.setContentsMargins(24, 20, 24, 20)
        vb.setSpacing(12)
        vb.setAlignment(Qt.AlignCenter)

        # 图标
        lbl_icon = QLabel("🏠")
        lbl_icon.setObjectName("remindIcon")
        lbl_icon.setAlignment(Qt.AlignCenter)
        vb.addWidget(lbl_icon)

        # 标题：区分"已到下班时间"和"下班提醒"
        lbl_title = QLabel("已到下班时间" if is_arrived else "下班提醒")
        lbl_title.setObjectName("remindTitle")
        if is_arrived:
            lbl_title.setStyleSheet("color: #4F6BF6;")  # 已到时高亮主色
        lbl_title.setAlignment(Qt.AlignCenter)
        vb.addWidget(lbl_title)

        # 还有多久（已到时不显示）
        if not is_arrived:
            lbl_remain = QLabel(f"还有 {remain_txt} 就要下班啦！")
            lbl_remain.setObjectName("remindSub")
            lbl_remain.setAlignment(Qt.AlignCenter)
            vb.addWidget(lbl_remain)

        # 应下班时间
        lbl_out = QLabel(f"预计下班 {should_out_str}")
        lbl_out.setObjectName("remindOut")
        lbl_out.setAlignment(Qt.AlignCenter)
        vb.addWidget(lbl_out)

        # 自动关闭倒计时
        self._lbl_auto = QLabel(f"{self._auto_close_remain} 秒后自动关闭")
        self._lbl_auto.setObjectName("remindAuto")
        self._lbl_auto.setAlignment(Qt.AlignCenter)
        vb.addWidget(self._lbl_auto)

        # 知道了按钮
        btn_ok = QPushButton("知道了")
        btn_ok.setObjectName("btnPrimary")
        btn_ok.setFixedHeight(36)
        btn_ok.clicked.connect(self.close)
        vb.addWidget(btn_ok)

        # 自动关闭定时器
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_tick)
        self._timer.start(1000)

    def _on_tick(self):
        self._auto_close_remain -= 1
        if self._auto_close_remain <= 0:
            self.close()
        else:
            self._lbl_auto.setText(f"{self._auto_close_remain} 秒后自动关闭")


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

        # 获取失败后自动重试倒计时
        self._retry_remain = 0       # >0 时每秒 -1，归零自动重试

        # 下班提醒：每天只弹一次，跨天重置
        self._reminded_today = False
        self._remind_date    = None   # 记录当天日期，用于判断是否跨天
        self._remind_check_interval = 30  # 每 30 秒检查一次下班提醒
        self._remind_check_remain   = 0
        self._today_should_out_min = None  # 今日应下班时间（分钟），_update_stats 计算后写入

        self.setWindowTitle(f"考勤管理  ·  {username}")
        self.resize(960, 640)
        self.setMinimumSize(840, 480)

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
        central.setObjectName("centralRoot")
        self.setCentralWidget(central)

        root_vb = QVBoxLayout(central)
        root_vb.setContentsMargins(0, 0, 0, 0)
        root_vb.setSpacing(0)

        # ── 顶栏 54px ──
        root_vb.addWidget(self._build_top_bar())

        # ── 主体：200px 侧边导航 + 内容区 ──
        body = QWidget()
        body_hb = QHBoxLayout(body)
        body_hb.setContentsMargins(0, 0, 0, 0)
        body_hb.setSpacing(0)

        body_hb.addWidget(self._build_side_bar())

        content = QWidget()
        content_vb = QVBoxLayout(content)
        content_vb.setContentsMargins(0, 0, 0, 0)
        content_vb.setSpacing(0)

        # 4 页切换
        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_overview_page())    # 0 今日概览
        self.stack.addWidget(self._build_records_page())     # 1 考勤记录
        self.stack.addWidget(self._build_overtime_page())    # 2 加班统计
        self.stack.addWidget(self._build_settings_page())    # 3 系统设置
        content_vb.addWidget(self.stack)

        body_hb.addWidget(content, stretch=1)
        root_vb.addWidget(body, stretch=1)

        # 兼容旧逻辑：隐藏的统计 dummy（_update_stats 引用 card_total 等）
        self._build_stats_cards()

        # 数据标签 → 页面外的同步（时间线 / 顶栏 / 加班小卡）
        self._connect_sync_signals()

        # 初始页：今日概览
        self._switch_page(0)

    # ═══════════════════════════════════════
    #  顶栏：Logo + 标题 + 版本 | 预计下班 + 倒计时 + 头像 + 操作
    # ═══════════════════════════════════════
    def _build_top_bar(self):
        top_bar = QFrame()
        top_bar.setObjectName("topBar")
        top_bar.setFixedHeight(54)

        tb = QHBoxLayout(top_bar)
        tb.setContentsMargins(16, 0, 16, 0)
        tb.setSpacing(10)

        # Logo（渐变方块）
        logo_box = QFrame()
        logo_box.setObjectName("appLogoBox")
        logo_box.setFixedSize(32, 32)
        logo_lay = QVBoxLayout(logo_box)
        logo_lay.setContentsMargins(0, 0, 0, 0)
        lbl_logo = QLabel("\U0001F4C5")
        lbl_logo.setAlignment(Qt.AlignCenter)
        logo_lay.addWidget(lbl_logo)
        tb.addWidget(logo_box)

        lbl_app = QLabel("考勤管理")
        lbl_app.setObjectName("appTitle")
        tb.addWidget(lbl_app)

        lbl_ver = QLabel(APP_VERSION)
        lbl_ver.setObjectName("versionBadge")
        tb.addWidget(lbl_ver)

        tb.addStretch()

        # 预计下班 / 刷新倒计时（由数据标签同步）
        self._lbl_should_out_top = QLabel("预计下班 --:--")
        self._lbl_should_out_top.setObjectName("topBarHint")
        tb.addWidget(self._lbl_should_out_top)

        self._lbl_countdown_top = QLabel("刷新 --:--")
        self._lbl_countdown_top.setObjectName("topBarHint")
        tb.addWidget(self._lbl_countdown_top)

        # 头像（初始显示工号首字符占位）
        self._lbl_avatar = QLabel()
        self._lbl_avatar.setObjectName("avatar")
        self._lbl_avatar.setFixedSize(40, 40)
        self._lbl_avatar.setAlignment(Qt.AlignCenter)
        placeholder = self.username[0].upper() if self.username else "?"
        self._lbl_avatar.setText(placeholder)
        tb.addWidget(self._lbl_avatar)

        self._lbl_username = QLabel(self.username or "你好")
        self._lbl_username.setObjectName("userName")
        tb.addWidget(self._lbl_username)

        # 设置 / 导出 / 退出登录 图标按钮组
        btn_group = QFrame()
        btn_group_lay = QHBoxLayout(btn_group)
        btn_group_lay.setContentsMargins(0, 0, 0, 0)
        btn_group_lay.setSpacing(8)

        btn_cfg = QPushButton("\u2699")
        btn_cfg.setObjectName("iconBtn")
        btn_cfg.setToolTip("系统设置")
        btn_cfg.setFixedSize(32, 32)
        btn_cfg.clicked.connect(lambda: self._switch_page(3))
        btn_group_lay.addWidget(btn_cfg)

        btn_exp = QPushButton("\u21E9")
        btn_exp.setObjectName("iconBtn")
        btn_exp.setToolTip("导出考勤记录 CSV")
        btn_exp.setFixedSize(32, 32)
        btn_exp.clicked.connect(self._export_csv)
        btn_group_lay.addWidget(btn_exp)

        btn_lo = QPushButton("\u23FB")
        btn_lo.setObjectName("iconBtn")
        btn_lo.setToolTip("退出登录")
        btn_lo.setFixedSize(32, 32)
        btn_lo.clicked.connect(self._logout)
        btn_group_lay.addWidget(btn_lo)

        tb.addWidget(btn_group)

        return top_bar

    # ═══════════════════════════════════════
    #  左侧导航（200px）
    # ═══════════════════════════════════════
    def _build_side_bar(self):
        side = QFrame()
        side.setObjectName("sideBar")
        side.setFixedWidth(200)

        vb = QVBoxLayout(side)
        vb.setContentsMargins(12, 14, 12, 14)
        vb.setSpacing(4)

        # 品牌区
        brand = QHBoxLayout()
        brand.setSpacing(8)
        bbox = QFrame()
        bbox.setObjectName("appLogoBox")
        bbox.setFixedSize(28, 28)
        blay = QVBoxLayout(bbox)
        blay.setContentsMargins(0, 0, 0, 0)
        blogo = QLabel("\U0001F4C5")
        blogo.setAlignment(Qt.AlignCenter)
        blay.addWidget(blogo)
        brand.addWidget(bbox)
        btitle = QLabel("考勤管理")
        btitle.setObjectName("sideBrand")
        brand.addWidget(btitle)
        brand.addStretch()
        vb.addLayout(brand)
        vb.addSpacing(12)

        glb = QLabel("主导航")
        glb.setObjectName("navGroupLabel")
        vb.addWidget(glb)

        self._nav_btns = []
        nav_items = [
            ("\U0001F4CA 今日概览", 0),
            ("\U0001F4CB 考勤记录", 1),
            ("\u23F0 加班统计", 2),
            ("\u2699 系统设置", 3),
        ]
        for text, idx in nav_items:
            btn = QPushButton(text)
            btn.setObjectName("navItem")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _=False, i=idx: self._switch_page(i))
            vb.addWidget(btn)
            self._nav_btns.append(btn)

        vb.addStretch()

        # 分隔线
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: #E8EAF0; border: none;")
        vb.addWidget(sep)
        vb.addSpacing(10)

        # 退出登录（独立按钮）
        btn_logout = QPushButton("\u23FB 退出登录")
        btn_logout.setObjectName("navLogout")
        btn_logout.setCursor(Qt.PointingHandCursor)
        btn_logout.clicked.connect(self._logout)
        vb.addWidget(btn_logout)

        return side

    def _switch_page(self, idx):
        self.stack.setCurrentIndex(idx)
        for i, btn in enumerate(self._nav_btns):
            btn.setChecked(i == idx)

    # ═══════════════════════════════════════
    #  第 0 页：今日概览
    # ═══════════════════════════════════════
    def _build_overview_page(self):
        page = QWidget()
        page.setObjectName("pageRoot")
        vb = QVBoxLayout(page)
        vb.setContentsMargins(16, 16, 16, 16)
        vb.setSpacing(14)

        # ── 控制行 ──
        ctrl = QFrame()
        ctrl.setObjectName("overviewControl")
        ctrl.setFixedHeight(54)
        ctrl_hb = QHBoxLayout(ctrl)
        ctrl_hb.setContentsMargins(10, 8, 10, 8)
        ctrl_hb.setSpacing(6)

        # 分段控件 本月/上月（代理隐藏的 combo_range）
        self.combo_range = QComboBox()
        self.combo_range.addItem("本月", "current")
        self.combo_range.addItem("上月", "prev")
        self.combo_range.currentIndexChanged.connect(self._on_range_combo_changed)
        self.combo_range.setVisible(False)  # 隐藏，由分段按钮控制

        seg = QFrame()
        seg.setObjectName("segControl")
        seg_hb = QHBoxLayout(seg)
        seg_hb.setContentsMargins(0, 0, 0, 0)
        seg_hb.setSpacing(0)
        self._seg_cur = QPushButton("本月")
        self._seg_cur.setObjectName("segBtn")
        self._seg_cur.setCheckable(True)
        self._seg_cur.setChecked(True)
        self._seg_cur.clicked.connect(lambda: self._on_seg_range(0))
        self._seg_prev = QPushButton("上月")
        self._seg_prev.setObjectName("segBtn")
        self._seg_prev.setCheckable(True)
        self._seg_prev.clicked.connect(lambda: self._on_seg_range(1))
        seg_hb.addWidget(self._seg_cur)
        seg_hb.addWidget(self._seg_prev)
        ctrl_hb.addWidget(seg)

        # 日期下拉
        self.combo_date = QComboBox()
        self.combo_date.setMinimumWidth(100)
        self._fill_date_combo()
        self.combo_date.currentIndexChanged.connect(self._on_date_combo_changed)
        ctrl_hb.addWidget(self.combo_date)

        # 加班设置 时/分
        lbl_ot = QLabel("加班")
        lbl_ot.setObjectName("detailKey")
        ctrl_hb.addWidget(lbl_ot)
        self.combo_ot_h = QComboBox()
        self.combo_ot_h.addItems([str(i) for i in range(13)])
        self.combo_ot_h.setFixedWidth(44)
        ctrl_hb.addWidget(self.combo_ot_h)
        lbl_h = QLabel("时")
        lbl_h.setObjectName("detailKey")
        ctrl_hb.addWidget(lbl_h)
        self.combo_ot_m = QComboBox()
        self.combo_ot_m.addItems(["0", "15", "30", "45"])
        self.combo_ot_m.setFixedWidth(44)
        ctrl_hb.addWidget(self.combo_ot_m)
        lbl_m = QLabel("分")
        lbl_m.setObjectName("detailKey")
        ctrl_hb.addWidget(lbl_m)
        self.combo_ot_h.currentIndexChanged.connect(self._refresh_detail_panel)
        self.combo_ot_m.currentIndexChanged.connect(self._refresh_detail_panel)

        # 立即刷新
        btn_refresh = QPushButton("\u21BB 刷新")
        btn_refresh.setObjectName("btnPrimary")
        btn_refresh.setFixedHeight(34)
        btn_refresh.clicked.connect(self._fetch_data)
        ctrl_hb.addWidget(btn_refresh)

        # 获取进度条 + 状态文本（_fetch_data / _on_data_ready 等引用）
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("fetchProgress")
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setFixedWidth(50)
        ctrl_hb.addWidget(self.progress_bar)

        vb.addWidget(ctrl)

        # ── 状态行（位于控制栏下方，避免控制栏过宽被截断）──
        status_row = QHBoxLayout()
        status_row.setContentsMargins(10, 2, 10, 0)
        status_row.setSpacing(0)
        self._lbl_status = QLabel("就绪")
        self._lbl_status.setObjectName("topBarHint")
        self._lbl_status.setFixedHeight(18)
        self._lbl_status.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        status_row.addWidget(self._lbl_status)
        status_row.addStretch()
        vb.addLayout(status_row)

        # ── 4 个指标卡 ──
        self._detail_lines = {}
        cards = QHBoxLayout()
        cards.setSpacing(14)
        cards.addWidget(self._make_metric_card("应下班时间", "should_out", "metricValuePrimary", accent=True), stretch=1)
        cards.addWidget(self._make_metric_card("已工作时长", "worked", "metricValue"), stretch=1)
        cards.addWidget(self._make_metric_card("已加班时长", "overtime", "metricValueWarning"), stretch=1)
        cards.addWidget(self._make_metric_card("合计加班", "ot_cycle_sum", "metricValueSuccess"), stretch=1)
        vb.addLayout(cards)

        # ── 双栏：左今日详情 / 右时间线+提醒 ──
        dual = QHBoxLayout()
        dual.setSpacing(14)

        # 左卡：今日考勤详情
        left = QFrame()
        left.setObjectName("card")
        lvb = QVBoxLayout(left)
        lvb.setContentsMargins(18, 14, 18, 14)
        lvb.setSpacing(10)

        lbl_sec1 = QLabel("今日考勤详情")
        lbl_sec1.setObjectName("sectionTitle")
        lvb.addWidget(lbl_sec1)

        row_rec = QHBoxLayout()
        row_rec.setSpacing(8)
        lbl_k = QLabel("打卡记录")
        lbl_k.setObjectName("detailKey")
        row_rec.addWidget(lbl_k)
        self._detail_lines["clock_records"] = _SignalLabel("--")
        self._detail_lines["clock_records"].setObjectName("detailValMono")
        row_rec.addWidget(self._detail_lines["clock_records"], stretch=1)
        lvb.addLayout(row_rec)

        row_ot = QHBoxLayout()
        row_ot.setSpacing(16)
        for key, label in [("ot_weekday", "平加(h)"), ("ot_weekend", "周加(h)"), ("ot_holiday", "假加(h)")]:
            sub = QHBoxLayout()
            sub.setSpacing(6)
            lb = QLabel(label)
            lb.setObjectName("detailKey")
            sub.addWidget(lb)
            self._detail_lines[key] = _SignalLabel("0")
            self._detail_lines[key].setObjectName("detailValMono")
            sub.addWidget(self._detail_lines[key])
            row_ot.addLayout(sub)
        row_ot.addStretch()
        lvb.addLayout(row_ot)

        lvb.addWidget(self._make_hsep())

        row_counts = QHBoxLayout()
        row_counts.setSpacing(8)
        lbl_lk = QLabel("迟到次数")
        lbl_lk.setObjectName("detailKey")
        row_counts.addWidget(lbl_lk)
        self._lbl_late = QLabel("0")
        self._lbl_late.setObjectName("valueDanger")
        row_counts.addWidget(self._lbl_late)
        row_counts.addStretch()
        lbl_ek = QLabel("早退次数")
        lbl_ek.setObjectName("detailKey")
        row_counts.addWidget(lbl_ek)
        self._lbl_early = QLabel("0")
        self._lbl_early.setObjectName("valueDanger")
        row_counts.addWidget(self._lbl_early)
        row_counts.addStretch()
        lvb.addLayout(row_counts)

        row_timer = QHBoxLayout()
        row_timer.setSpacing(8)
        lbl_tk = QLabel("刷新倒计时")
        lbl_tk.setObjectName("detailKey")
        row_timer.addWidget(lbl_tk)
        self._lbl_countdown = _SignalLabel("--")
        self._lbl_countdown.setObjectName("countdownBox")
        self._lbl_countdown.setFixedWidth(64)
        self._lbl_countdown.setAlignment(Qt.AlignCenter)
        row_timer.addWidget(self._lbl_countdown)
        row_timer.addStretch()
        lvb.addLayout(row_timer)

        # 失败重试提示
        self._lbl_retry = QLabel("")
        self._lbl_retry.setAlignment(Qt.AlignCenter)
        self._lbl_retry.setWordWrap(True)
        self._lbl_retry.setObjectName("valueDanger")
        self._lbl_retry.setVisible(False)
        lvb.addWidget(self._lbl_retry)

        lvb.addStretch()
        dual.addWidget(left, stretch=3)

        # 右栏
        right = QVBoxLayout()
        right.setSpacing(14)

        # 打卡时间线
        tl_card = QFrame()
        tl_card.setObjectName("card")
        tvb = QVBoxLayout(tl_card)
        tvb.setContentsMargins(18, 14, 18, 14)
        tvb.setSpacing(10)
        lbl_tl = QLabel("打卡时间线")
        lbl_tl.setObjectName("sectionTitle")
        tvb.addWidget(lbl_tl)
        self._timeline_rows = []
        for i in range(4):
            row = QHBoxLayout()
            row.setSpacing(10)
            dot = QFrame()
            dot.setObjectName("timelineDotMuted")
            dot.setFixedSize(8, 8)
            row.addWidget(dot, 0, Qt.AlignVCenter)
            tl_time = QLabel("--")
            tl_time.setObjectName("tlTime")
            row.addWidget(tl_time)
            tl_lbl = QLabel("")
            tl_lbl.setObjectName("tlLabel")
            row.addWidget(tl_lbl)
            row.addStretch()
            tvb.addLayout(row)
            self._timeline_rows.append((dot, tl_time, tl_lbl))
        right.addWidget(tl_card)

        # 下班提醒设置
        rmd_card = QFrame()
        rmd_card.setObjectName("card")
        rvb = QVBoxLayout(rmd_card)
        rvb.setContentsMargins(18, 14, 18, 14)
        rvb.setSpacing(10)
        lbl_rmd = QLabel("下班提醒设置")
        lbl_rmd.setObjectName("sectionTitle")
        rvb.addWidget(lbl_rmd)

        row_rmd = QHBoxLayout()
        row_rmd.setContentsMargins(4, 4, 4, 4)
        row_rmd.setSpacing(10)
        lbl_r = QLabel("提前")
        lbl_r.setObjectName("detailKey")
        row_rmd.addWidget(lbl_r)
        self.spin_remind = QSpinBox()
        self.spin_remind.setRange(0, 60)
        self.spin_remind.setSingleStep(5)
        self.spin_remind.setFixedWidth(60)
        self.spin_remind.setAlignment(Qt.AlignCenter)
        row_rmd.addWidget(self.spin_remind)
        lbl_min = QLabel("分钟")
        lbl_min.setObjectName("detailKey")
        row_rmd.addWidget(lbl_min)
        self.cb_remind = QCheckBox("启用")
        row_rmd.addWidget(self.cb_remind)
        self.btn_test_remind = QPushButton("测试")
        self.btn_test_remind.setObjectName("btnPrimary")
        self.btn_test_remind.setFixedHeight(28)
        self.btn_test_remind.setFixedWidth(52)
        self.btn_test_remind.clicked.connect(self._manual_show_remind)
        row_rmd.addWidget(self.btn_test_remind)
        row_rmd.addStretch()
        rvb.addLayout(row_rmd)

        # 从配置加载提醒设置
        cfg = self._load_work_config()
        self.cb_remind.setChecked(cfg.get("remind_enabled", True))
        self.spin_remind.setValue(cfg.get("remind_offset", 5))
        self.cb_remind.stateChanged.connect(self._save_remind_cfg)
        self.spin_remind.valueChanged.connect(self._save_remind_cfg)

        rvb.addStretch()
        right.addWidget(rmd_card)

        dual.addLayout(right, stretch=2)
        vb.addLayout(dual, stretch=1)

        return page

    def _on_seg_range(self, idx):
        """分段控件点击 → 驱动隐藏的 combo_range"""
        self._seg_cur.setChecked(idx == 0)
        self._seg_prev.setChecked(idx == 1)
        self.combo_range.setCurrentIndex(idx)  # 触发 _on_range_combo_changed

    def _save_remind_cfg(self):
        """提醒配置写入 ~/.attendance_tool_cfg.json"""
        cfg_path = os.path.join(os.path.expanduser("~"), ".attendance_tool_cfg.json")
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
        if "work_config" not in data:
            data["work_config"] = {}
        data["work_config"]["remind_enabled"] = self.cb_remind.isChecked()
        data["work_config"]["remind_offset"] = self.spin_remind.value()
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _connect_sync_signals(self):
        """把核心数据标签的更新同步到时间线 / 顶栏 / 加班小卡"""
        # 打卡记录 → 时间线
        self._detail_lines["clock_records"].textSet.connect(self._update_timeline)
        self._update_timeline(self._detail_lines["clock_records"].text())
        # 应下班时间 → 顶栏
        self._detail_lines["should_out"].textSet.connect(self._on_should_out_changed)
        self._on_should_out_changed(self._detail_lines["should_out"].text())
        # 刷新倒计时 → 顶栏
        self._lbl_countdown.textSet.connect(self._on_countdown_changed)
        self._on_countdown_changed(self._lbl_countdown.text())
        # 加班 4 项 → 加班统计小卡
        ot_map = {"ot_weekday": "weekday", "ot_weekend": "weekend",
                  "ot_holiday": "holiday", "ot_cycle_sum": "cycle_sum"}
        for src_key, card_key in ot_map.items():
            if src_key in self._detail_lines and card_key in self._ot_cards:
                self._detail_lines[src_key].textSet.connect(self._ot_cards[card_key].setText)
                self._ot_cards[card_key].setText(self._detail_lines[src_key].text())

    def _on_should_out_changed(self, text):
        self._lbl_should_out_top.setText(f"预计下班 {text}")

    def _on_countdown_changed(self, text):
        self._lbl_countdown_top.setText(f"刷新 {text}")

    def _update_timeline(self, text):
        """根据打卡记录文本更新时间线"""
        parts = []
        if text and str(text) != "--":
            parts = [p.strip() for p in str(text).replace("，", ",").split(",") if p.strip()]
        labels = ["上班打卡", "午休下班", "午休上班", "下班打卡"]
        for i, (dot, tl_time, tl_lbl) in enumerate(self._timeline_rows):
            if i < len(parts):
                tl_time.setText(parts[i])
                dot.setObjectName("timelineDotIn" if i % 2 == 0 else "timelineDotOut")
            else:
                tl_time.setText("--")
                dot.setObjectName("timelineDotMuted")
            tl_lbl.setText(labels[i] if i < len(labels) else "")
            dot.style().unpolish(dot)
            dot.style().polish(dot)

    # ═══════════════════════════════════════
    #  第 1 页：考勤记录
    # ═══════════════════════════════════════
    def _build_records_page(self):
        page = QWidget()
        page.setObjectName("pageRoot")
        vb = QVBoxLayout(page)
        vb.setContentsMargins(16, 16, 16, 16)
        vb.setSpacing(12)

        head = QHBoxLayout()
        lbl_title = QLabel("考勤记录")
        lbl_title.setObjectName("pageTitle")
        head.addWidget(lbl_title)
        head.addStretch()
        btn_export = QPushButton("\u21E9 导出 CSV")
        btn_export.setFixedHeight(32)
        btn_export.clicked.connect(self._export_csv)
        head.addWidget(btn_export)
        vb.addLayout(head)

        # 完整考勤表格（_populate_table 写入 self.table）
        self.table = QTableWidget()
        self.table.setObjectName("recordsTable")
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.verticalHeader().setDefaultSectionSize(28)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        vb.addWidget(self.table, stretch=1)

        # 底部计数（setText 触发加班表同步）
        self.lbl_count = _SignalLabel("共 0 条记录")
        self.lbl_count.setObjectName("caption")
        self.lbl_count.textSet.connect(self._sync_overtime_table)
        vb.addWidget(self.lbl_count, 0, Qt.AlignRight)

        return page

    # ═══════════════════════════════════════
    #  第 2 页：加班统计
    # ═══════════════════════════════════════
    def _build_overtime_page(self):
        page = QWidget()
        page.setObjectName("pageRoot")
        vb = QVBoxLayout(page)
        vb.setContentsMargins(16, 16, 16, 16)
        vb.setSpacing(14)

        lbl_title = QLabel("加班统计")
        lbl_title.setObjectName("pageTitle")
        vb.addWidget(lbl_title)

        # 4 张小卡
        cards = QHBoxLayout()
        cards.setSpacing(12)
        self._ot_cards = {}
        for key, label, obj in [
            ("weekday", "平加", "metricValuePrimary"),
            ("weekend", "周加", "metricValueWarning"),
            ("holiday", "假加", "metricValueSuccess"),
            ("cycle_sum", "合计", "metricValue"),
        ]:
            c = QFrame()
            c.setObjectName("otCard")
            cvb = QVBoxLayout(c)
            cvb.setContentsMargins(14, 10, 14, 10)
            cvb.setSpacing(4)
            lt = QLabel(label)
            lt.setObjectName("metricTitle")
            lv = QLabel("--")
            lv.setObjectName(obj)
            cvb.addWidget(lt)
            cvb.addWidget(lv)
            cards.addWidget(c, stretch=1)
            self._ot_cards[key] = lv
        vb.addLayout(cards)

        lbl_sec = QLabel("加班明细")
        lbl_sec.setObjectName("sectionTitle")
        vb.addWidget(lbl_sec)

        # 加班明细表格（由 _sync_overtime_table 从 self.table 同步填充）
        self.overtime_table = QTableWidget()
        self.overtime_table.setObjectName("overtimeTable")
        self.overtime_table.setAlternatingRowColors(True)
        self.overtime_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.overtime_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.overtime_table.horizontalHeader().setStretchLastSection(True)
        self.overtime_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.overtime_table.verticalHeader().setDefaultSectionSize(28)
        self.overtime_table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        vb.addWidget(self.overtime_table, stretch=1)

        return page

    def _sync_overtime_table(self, *args):
        """从 self.table 同步加班明细（过滤加班>0 的行，跳过汇总行）"""
        try:
            headers = getattr(self, "_headers", []) or []
            rows = getattr(self, "_all_data", []) or []
            if not headers:
                self.overtime_table.clear()
                self.overtime_table.setRowCount(0)
                return

            def col_idx(kws):
                for i, h in enumerate(headers):
                    if any(k in h for k in kws):
                        return i
                return -1

            date_i = col_idx(["考勤日期", "日期"])
            wd_i = col_idx(["平加"])
            we_i = col_idx(["周加"])
            hd_i = col_idx(["假加"])
            tot_i = col_idx(["合计加班", "合计"])

            def cell(row, i):
                return str(row[i]).strip() if 0 <= i < len(row) else ""

            def to_h(v):
                try:
                    if not v or v in ("0", "--", ""):
                        return 0.0
                    if ":" in v:
                        h, m = v.split(":")
                        return float(h) + float(m) / 60.0
                    return float(v)
                except Exception:
                    return 0.0

            keep = []
            for row in rows:
                if not row:
                    continue
                date_val = cell(row, date_i)
                if "至" in date_val:  # 跳过汇总行
                    continue
                vals = [cell(row, i) for i in (wd_i, we_i, hd_i, tot_i)]
                if any(to_h(v) > 0 for v in vals):
                    keep.append([date_val] + vals)

            self.overtime_table.clear()
            self.overtime_table.setColumnCount(5)
            self.overtime_table.setHorizontalHeaderLabels(
                ["日期", "平加(h)", "周加(h)", "假加(h)", "合计(h)"])
            self.overtime_table.setRowCount(len(keep))
            for r, row in enumerate(keep):
                for c, v in enumerate(row):
                    it = QTableWidgetItem(v)
                    it.setTextAlignment(Qt.AlignCenter)
                    self.overtime_table.setItem(r, c, it)
            self.overtime_table.resizeColumnsToContents()
        except Exception:
            pass

    # ═══════════════════════════════════════
    #  第 3 页：系统设置（上下班 6 项时间表单）
    # ═══════════════════════════════════════
    def _build_settings_page(self):
        page = QWidget()
        page.setObjectName("pageRoot")
        vb = QVBoxLayout(page)
        vb.setContentsMargins(16, 16, 16, 16)
        vb.setSpacing(14)

        lbl_title = QLabel("系统设置")
        lbl_title.setObjectName("pageTitle")
        vb.addWidget(lbl_title)

        card = QFrame()
        card.setObjectName("settingsCard")
        cvb = QVBoxLayout(card)
        cvb.setContentsMargins(20, 18, 20, 18)
        cvb.setSpacing(10)

        lbl_sec = QLabel("上下班时间")
        lbl_sec.setObjectName("sectionTitle")
        cvb.addWidget(lbl_sec)

        cfg = self._load_work_config()
        self._settings_edits = {}
        time_rows = [
            ("最早上班", "work_start"),
            ("最晚上班", "work_start_late"),
            ("标准下班", "work_end"),
            ("午休开始", "rest_start"),
            ("午休结束", "rest_end"),
            ("晚休开始", "dinner_start"),
            ("晚休结束", "dinner_end"),
        ]
        defaults = {
            "work_start": "07:00", "work_start_late": "09:00", "work_end": "17:00",
            "rest_start": "12:00", "rest_end": "13:00",
            "dinner_start": "17:00", "dinner_end": "17:45",
        }
        for label, key in time_rows:
            row = QHBoxLayout()
            row.setSpacing(10)
            lb = QLabel(label)
            lb.setObjectName("detailKey")
            lb.setFixedWidth(80)
            row.addWidget(lb)
            edit = QLineEdit()
            edit.setText(str(cfg.get(key, defaults.get(key, "09:00"))))
            edit.setFixedWidth(120)
            edit.setAlignment(Qt.AlignCenter)
            edit.setPlaceholderText("HH:MM")
            row.addWidget(edit)
            row.addStretch()
            cvb.addLayout(row)
            self._settings_edits[key] = edit

        vb.addWidget(card)
        vb.addStretch()

        btn_row = QHBoxLayout()
        btn_save = QPushButton("保存配置")
        btn_save.setObjectName("btnPrimary")
        btn_save.setFixedHeight(40)
        btn_save.clicked.connect(self._save_work_settings)
        btn_row.addStretch()
        btn_row.addWidget(btn_save)
        vb.addLayout(btn_row)

        return page

    def _save_work_settings(self):
        """保存上下班时间配置并立即刷新详情（与 ConfigWindow 相同写盘逻辑）"""
        cfg_path = os.path.join(os.path.expanduser("~"), ".attendance_tool_cfg.json")
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
        cfg = data.get("work_config", {})
        for key, edit in self._settings_edits.items():
            cfg[key] = edit.text().strip()
        data["work_config"] = cfg
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        try:
            self._refresh_detail_panel()
        except Exception:
            pass
        QMessageBox.information(self, "保存成功", "上下班配置已保存！")


    def _make_hsep(self):
        """细分割线（QSS #hsep）"""
        sep = QFrame()
        sep.setObjectName("hsep")
        return sep

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
    def _make_metric_card(self, title, key, value_obj_name, accent=False):
        """构建指标卡并登记到 _detail_lines（accent=True 用强调渐变主色底）"""
        card = QFrame()
        card.setObjectName("metricCardAccent" if accent else "metricCard")
        vbl = QVBoxLayout(card)
        vbl.setContentsMargins(16, 12, 16, 12)
        vbl.setSpacing(4)
        lbl_t = QLabel(title)
        lbl_t.setObjectName("metricTitle")
        lbl_v = _SignalLabel("--")
        lbl_v.setObjectName(value_obj_name)
        vbl.addWidget(lbl_t)
        vbl.addWidget(lbl_v)
        self._detail_lines[key] = lbl_v
        return card


    def _make_detail_val(self, text, obj_name):
        """构建详情值标签"""
        lbl = QLabel(text)
        lbl.setObjectName(obj_name)
        return lbl

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

    # ── 下班提醒辅助方法 ──

    def _find_first_clock_in(self, row):
        """
        从一行数据中找到第一次上班打卡时间（分钟数）。
        打卡格式: "[08:48]，[17:19]，[17:48]，[20:06]"
        返回 None 表示无打卡。
        """
        headers = self._headers
        clock_col = -1
        for i, h in enumerate(headers):
            if any(k in h for k in ["打卡", "时间", "考勤时间"]):
                clock_col = i
                break
        if clock_col < 0 or clock_col >= len(row):
            return None
        clock_str = str(row[clock_col]).strip()
        if not clock_str or clock_str in ("--", ""):
            return None
        # 解析: 去掉方括号和中文逗号
        cleaned = clock_str.replace("，", ",").replace("[", "").replace("]", "")
        parts = cleaned.split(",")
        for t in parts:
            t = t.strip()
            if t and ":" in t:
                return self._parse_time_to_min(t)
        return None

    def _get_ot_str_from_row(self, row):
        """从一行数据中获取加班时长字符串（合计加班列）"""
        headers = self._headers
        for i, h in enumerate(headers):
            if any(k in h for k in ["合计加班", "合计"]):
                if i < len(row):
                    val = str(row[i]).strip()
                    if val and val not in ("--", "0"):
                        return val
                break
        return "0时0分"

    def _on_tick(self):
        """每秒定时回调：倒计时刷新 + 下班提醒"""
        # ── 跨天重置提醒标志 ──
        today = datetime.date.today()
        if self._remind_date != today:
            self._reminded_today       = False
            self._today_should_out_min = None  # 跨天清空缓存的应下班时间
            self._remind_date          = today

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

        # ── 失败重试倒计时 ──
        if self._retry_remain > 0:
            self._retry_remain -= 1
            if self._retry_remain <= 0:
                self._lbl_retry.setVisible(False)
                self._fetch_data()
            else:
                self._lbl_retry.setText(f"⚠ 数据获取失败\n{self._retry_remain} 秒后自动重试...")

        # ── 下班提醒检查（每 30 秒一次）──
        self._remind_check_remain -= 1
        if self._remind_check_remain <= 0:
            self._remind_check_remain = self._remind_check_interval
            self._check_remind()

    def _calc_today_should_out_min(self):
        """计算今日应下班时间（分钟），无数据则返回 None"""
        # 优先复用主界面已计算好的应下班时间（与右侧详情面板一致）
        if self._today_should_out_min is not None:
            return self._today_should_out_min

        if not self._has_data or not self._all_data:
            return None

        today = datetime.date.today()
        row = None
        date_fmts = ["%Y/%m/%d", "%Y-%m-%d", "%Y%m%d", "%Y.%m.%d"]
        for r in self._all_data:
            if len(r) == 0:
                continue
            date_str = str(r[0]).strip()
            dt = None
            for fmt in date_fmts:
                try:
                    dt = datetime.datetime.strptime(date_str, fmt).date()
                    break
                except Exception:
                    continue
            match = (dt == today) if dt else False
            if not match and dt:
                match = (dt.month == today.month and dt.day == today.day
                         and abs(dt.year - today.year) <= 1)
            if match:
                row = r
                break
        if not row:
            return None

        config = self._load_work_config()
        first_clock_in = self._find_first_clock_in(row)
        if first_clock_in is None:
            return None

        standed_up  = self._parse_time_to_min(config.get("work_start", "07:00"))
        rest1_begin = self._parse_time_to_min(config.get("rest_start", "12:00"))
        rest1_end   = self._parse_time_to_min(config.get("rest_end",   "13:00"))
        rest2_begin = self._parse_time_to_min(config.get("dinner_start","17:00"))
        rest2_end   = self._parse_time_to_min(config.get("dinner_end", "17:45"))

        eff_start = standed_up if first_clock_in < standed_up else first_clock_in

        # 解析完整打卡记录 → up_list（用于实际晚休结束判断）
        up_list = []
        headers = self._headers
        clock_col = -1
        for i, h in enumerate(headers):
            if any(k in h for k in ["打卡", "时间", "考勤时间"]):
                clock_col = i
                break
        if 0 <= clock_col < len(row):
            clock_str = str(row[clock_col]).strip()
            if clock_str and clock_str not in ("--", ""):
                cleaned = clock_str.replace("，", ",").replace("[", "").replace("]", "")
                cnt = 0
                for t in cleaned.split(","):
                    t = t.strip()
                    if t and ":" in t:
                        if cnt % 2 == 0:
                            up_list.append(self._parse_time_to_min(t))
                        cnt += 1

        # 大小周判断：根据日历周数奇偶性，奇数=小周，偶数=大周
        # 小周周六工作7h；大周周六与周日一律不工作
        wd = today.weekday() + 1   # 1=周一 ... 7=周日
        if wd == 7:                # 周日
            work_hours = 0
        elif wd == 6:              # 周六
            week_num = today.isocalendar()[1]
            work_hours = 7 * 60 if week_num % 2 != 0 else 0  # 小周7h，大周0
        else:                      # 周一~周五
            work_hours = 8 * 60
        if work_hours == 0:        # 休息日无需计算应下班
            return None
        base = eff_start + work_hours + (rest1_end - rest1_begin)

        ot_str = self._get_ot_str_from_row(row)
        ot_parts = ot_str.replace("时", ":").replace("分", "").split(":")
        ot_h = int(ot_parts[0]) if len(ot_parts) > 0 and ot_parts[0].isdigit() else 0
        ot_m = int(ot_parts[1]) if len(ot_parts) > 1 and ot_parts[1].isdigit() else 0
        ot_total = ot_h * 60 + ot_m

        rest2_len = rest2_end - rest2_begin

        # 加班=0：不加晚休时长（用实际晚休结束打卡替代配置）
        if ot_total == 0:
            if base <= rest2_begin:
                return base
            else:
                # 实际晚休结束 = up_list 中首个 ≥ rest2_begin 的打卡（晚休后再上班打卡）
                actual_dinner_end = rest2_end
                for u in up_list:
                    if u >= rest2_begin:
                        actual_dinner_end = max(actual_dinner_end, u)
                        break
                return base + (actual_dinner_end - rest2_begin)

        # 加班>0：超过晚休开始才加晚休
        work_done_time = base + ot_total
        if work_done_time <= rest2_begin:
            return work_done_time
        else:
            return work_done_time + rest2_len

    def _show_remind_dialog(self, should_out_min):
        """显示下班提醒弹窗（should_out_min: 应下班分钟数）"""
        now = datetime.datetime.now()
        now_min = now.hour * 60 + now.minute
        remain_min = should_out_min - now_min
        should_out_str = self._min_to_time_str(should_out_min)

        if remain_min <= 0:
            # 已到或已过应下班时间
            dlg = OffWorkRemindDialog(None, should_out_str, is_arrived=True, parent=self)
        else:
            remain_h = remain_min // 60
            remain_m = remain_min % 60
            if remain_h > 0:
                remain_txt = f"{remain_h}小时{remain_m}分钟"
            else:
                remain_txt = f"{remain_m}分钟"
            dlg = OffWorkRemindDialog(remain_txt, should_out_str, is_arrived=False, parent=self)
        dlg.show()  # 非模态，最小化时也能显示

    def _check_remind(self):
        """检查是否需要弹出下班提醒（定时调用）"""
        if self._reminded_today:
            return  # 今天已提醒过，跳过

        if hasattr(self, "cb_remind") and not self.cb_remind.isChecked():
            return  # 提醒未启用

        should_out_min = self._calc_today_should_out_min()
        if should_out_min is None:
            return

        now = datetime.datetime.now()
        now_min = now.hour * 60 + now.minute

        # 获取提前提醒分钟数（SpinBox 设置值）
        remind_offset = self.spin_remind.value() if hasattr(self, "spin_remind") else 5

        # 触发条件：当前时间 >= 应下班时间 - 提前分钟数（已到下班时间同样触发）
        trigger_min = should_out_min - remind_offset
        if now_min < trigger_min:
            return  # 还没到提醒时间
        if now_min > should_out_min + 60:
            return  # 超过下班时间1小时以上，说明是新的一天或异常，不弹

        self._reminded_today = True
        self._show_remind_dialog(should_out_min)

    def _manual_show_remind(self):
        """手动触发下班提醒弹窗"""
        should_out_min = self._calc_today_should_out_min()
        if should_out_min is not None:
            self._show_remind_dialog(should_out_min)
            return

        # 降级：无今日打卡数据时，基于配置估算应下班时间
        config = self._load_work_config()
        standed_up  = self._parse_time_to_min(config.get("work_start", "07:00"))
        rest1_end   = self._parse_time_to_min(config.get("rest_end",   "13:00"))
        rest1_begin = self._parse_time_to_min(config.get("rest_start", "12:00"))
        rest2_begin = self._parse_time_to_min(config.get("dinner_start","17:00"))
        rest2_end   = self._parse_time_to_min(config.get("dinner_end", "17:45"))
        base = standed_up + 8 * 60 + (rest1_end - rest1_begin)
        should_out_min = base + (rest2_end - rest2_begin)  # 含晚休
        self._show_remind_dialog(should_out_min)

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
            # 数据成功获取，取消失败重试倒计时
            self._retry_remain = 0
            self._lbl_retry.setVisible(False)

            if not rows:
                self._lbl_status.setText("该时间段内无考勤记录")
            else:
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
        # 不弹窗，直接在左侧面板显示失败提示并开始 30 秒重试倒计时
        self._retry_remain = 30
        self._lbl_retry.setVisible(True)
        self._lbl_retry.setText("⚠ 数据获取失败\n30 秒后自动重试...")

    def _load_demo_data(self):
        headers = ["工号", "姓名", "部门", "考勤日期", "考勤周数", "班次",
                   "有效打卡时间", "出勤", "在家办公", "平加", "周加", "假加", "合计加班",
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
                "3.0" if d == 7 else "", "2.0" if d == 13 else "", "",
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
                return 0, []  # 缺列时返回空元组，避免解包崩溃
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

        # 计算 [up, dowm) 区间内应扣除的休息时间（分钟）
        def check_time_is_include_rest_time(up, dowm,
                                            standed_up, rest1_begin, rest1_end,
                                            rest2_begin, rest2_end):
            total_time = 0
            # 提前打卡：早于标准上班时间的部分不算工作时间，补回来
            if up < standed_up and up != 0:
                total_time += standed_up - up
            # 区间重叠计算休息时间（半开区间 [begin, end)）
            total_time += max(0, min(dowm, rest1_end) - max(up, rest1_begin))
            total_time += max(0, min(dowm, rest2_end) - max(up, rest2_begin))
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
              工时：小周周六7h，其余工作日8h（按日历周数奇偶判断，奇数=小周）
              加班=0：base ≤ 晚休开始 → 返回 base；base > 晚休开始 → 加晚休
              加班>0：work_done = base + 加班；≤ 晚休开始 → 不加晚休；> 晚休开始 → 加晚休
              晚休时长：用 up_list 中首个 ≥ rest2_begin 的打卡作为实际晚休结束（替代配置rest2_end）
            """
            # 步骤1：有效上班时间
            if first_clock_in < standed_up:
                eff_start = standed_up
            else:
                eff_start = first_clock_in

            # 步骤2：base = 有效上班 + 工时 + 午休时长（不含晚休）
            rest1_len = rest1_end - rest1_begin
            # 大小周判断：根据日历周数奇偶性，奇数=小周，偶数=大周
            # 小周周六工作7h；大周周六与周日一律不工作
            wd = target_date.weekday() + 1   # 1=周一 ... 7=周日
            if wd == 7:                      # 周日
                work_hours = 0
            elif wd == 6:                    # 周六
                week_num = target_date.isocalendar()[1]
                work_hours = 7 * 60 if week_num % 2 != 0 else 0  # 小周7h，大周0
            else:                            # 周一~周五
                work_hours = 8 * 60
            if work_hours == 0:              # 休息日无需计算应下班
                return 0
            base = eff_start + work_hours + rest1_len

            # 步骤3：加班设置
            ot_h = int(self.combo_ot_h.currentText()) if hasattr(self, 'combo_ot_h') else 0
            ot_m = int(self.combo_ot_m.currentText()) if hasattr(self, 'combo_ot_m') else 0
            ot_total = ot_h * 60 + ot_m

            # 实际晚休结束 = up_list 中首个 ≥ rest2_begin 的打卡（晚休后再上班打卡）
            actual_dinner_end = rest2_end
            for u in up_list:
                if u >= rest2_begin:
                    actual_dinner_end = max(actual_dinner_end, u)
                    break

            # 加班=0：不加晚休时长（用实际晚休结束替代配置）
            if ot_total == 0:
                if base <= rest2_begin:
                    return base          # 8h完成在晚休之前，直接走
                else:
                    return base + (actual_dinner_end - rest2_begin)  # 8h跨越晚休，加实际晚休

            # 加班>0：work_done_time = base + 加班
            work_done_time = base + ot_total

            if work_done_time <= rest2_begin:
                return work_done_time    # 加班后仍在晚休之前，不加晚休

            # 加班后超过晚休开始 → 加晚休（用实际打卡替代配置）
            dinner_len = actual_dinner_end - rest2_begin
            return work_done_time + dinner_len

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
        _odd_last_dup = False  # 奇数打卡最后一个为重复/误打卡（<15min内）

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
                        temp_times = []
                        for t in parts:
                            t = t.strip()
                            if t and ":" in t:
                                t_min = self._parse_time_to_min(t)
                                temp_times.append(t_min)
                                if cnt % 2 == 0:
                                    up_list.append(t_min)
                                else:
                                    dowm_list.append(t_min)
                                cnt += 1
                        # 打卡数为奇数时，最后一个未配对打卡的处理：
                        # 若与最后一个下班打卡间隔很短（<15min），视为重复/误打卡
                        # 上班列表中不移除，但后续"打卡对等"判断会跳过（走已下班分支）
                        if len(temp_times) % 2 != 0 and len(dowm_list) > 0:
                            last_up = temp_times[-1]
                            last_dowm = dowm_list[-1]
                            if last_up - last_dowm < 15:
                                _odd_last_dup = True
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

            if up_times != dowm_times and not _odd_last_dup:
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
        # 如果是今日，保存应下班分钟数供弹窗使用
        if target_date == datetime.date.today():
            self._today_should_out_min = title_dowm_time

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
        act_quit.triggered.connect(self._quit_app)
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
        """窗口关闭事件，直接最小化到托盘而不是退出"""
        # 退出登录时直接关闭，不弹对话框
        if self._is_logging_out:
            self.tray_icon.hide()
            event.accept()
            return

        # 直接最小化到托盘
        self.hide()
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

    def _quit_app(self):
        """直接从托盘或底部按钮退出程序（关闭进程）"""
        self._is_logging_out = True  # 绕过closeEvent对话框
        self.tray_icon.hide()
        QApplication.instance().quit()

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
        app.setStyleSheet(STYLE_MODERN)  # 现代简约主题（v107：修复登录窗居中、主窗口控制栏截断与控件拥挤）
        app.setFont(QFont("Microsoft YaHei", 10))
        # 防止关闭所有窗口时自动退出（程序生命周期由托盘图标控制）
        app.setQuitOnLastWindowClosed(False)

        login_win = LoginWindow()
        main_win_holder = [None]

        def on_login_success(cookies, username):
            try:
                if main_win_holder[0] is not None:
                    main_win_holder[0].close()
                login_win.hide()
                mw = MainWindow(cookies, username, login_window=login_win)
                main_win_holder[0] = mw
                mw.show()
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
