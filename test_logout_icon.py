import os
import sys

from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton
from PyQt5.QtCore import Qt, QTimer, QSize
from PyQt5.QtGui import QPixmap, QPainter, QIcon

STYLE = """
QWidget { background: #F4F6FA; }
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
"""

SVG_LOGOUT = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>"""


def _make_svg_icon(svg_template: str, size: int = 18, color: str = "#6B7280"):
    try:
        from PyQt5.QtSvg import QSvgRenderer
        from PyQt5.QtCore import QRect
        renderer = QSvgRenderer(svg_template.format(color=color).encode("utf-8"))
        pix = QPixmap(size, size)
        pix.fill(Qt.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing)
        renderer.setViewBox(QRect(0, 0, 24, 24))
        renderer.render(p)
        p.end()
        return QIcon(pix)
    except Exception:
        return None


app = QApplication(sys.argv)

win = QWidget()
win.setWindowTitle("Logout Button Icon Test")
win.setStyleSheet(STYLE)
lay = QVBoxLayout(win)
lay.setContentsMargins(20, 20, 20, 20)

icon = _make_svg_icon(SVG_LOGOUT, size=18, color="#DC2626")
btn = QPushButton("退出登录")
if icon is not None:
    btn.setIcon(icon)
    btn.setIconSize(QSize(18, 18))
btn.setObjectName("navLogout")
btn.setFixedWidth(160)
lay.addWidget(btn)

win.adjustSize()
win.show()


def grab():
    pm = win.grab()
    pm.save("_shot_logout_icon.png", "PNG")
    print("saved _shot_logout_icon.png")
    app.quit()


QTimer.singleShot(300, grab)
sys.exit(app.exec_())
