import os
import sys
import time

from PyQt5.QtWidgets import (QApplication, QWidget, QFrame, QHBoxLayout, QLabel,
                             QCheckBox, QPushButton)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap, QColor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from attendance_tool import STYLE_MODERN, _StyledComboBox, _white_check_icon_path

GRAY = QColor(107, 114, 128)
PRIMARY = QColor(79, 107, 246)


def analyze(pm):
    img = pm.toImage()
    w, h = img.width(), img.height()
    gray = prim = 0
    for y in range(h):
        for x in range(w):
            c = QColor(img.pixel(x, y))
            if c.alpha() < 50:
                continue
            if abs(c.red() - GRAY.red()) < 30 and abs(c.green() - GRAY.green()) < 30 and abs(c.blue() - GRAY.blue()) < 30:
                gray += 1
            if abs(c.red() - PRIMARY.red()) < 40 and abs(c.green() - PRIMARY.green()) < 40 and abs(c.blue() - PRIMARY.blue()) < 40:
                prim += 1
    return gray, prim


def run():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # 用一个简单容器承载卡片，方便 grab
    win = QWidget()
    win.setStyleSheet("background: #F6F7FB;")
    win.resize(520, 120)
    base = QHBoxLayout(win)
    base.setContentsMargins(20, 20, 20, 20)

    card = QFrame()
    card.setObjectName("card")
    card.setStyleSheet(STYLE_MODERN)
    row = QHBoxLayout(card)
    row.setContentsMargins(16, 16, 16, 16)
    row.setSpacing(8)

    lbl_bell = QLabel("🔔 下班提醒")
    lbl_bell.setStyleSheet("font-size: 13px; font-weight: 600; color: #3A4050;")
    row.addWidget(lbl_bell)

    cb = QCheckBox()
    cb.setObjectName("cbRemind")
    chk_path = _white_check_icon_path().replace("\\", "/")
    cb.setStyleSheet(
        f"QCheckBox#cbRemind::indicator:checked {{ image: url(\"{chk_path}\"); }}")
    cb.setChecked(True)
    row.addWidget(cb)

    combo = _StyledComboBox()
    for v in (0, 5, 10, 15, 20, 30, 45, 60):
        combo.addItem(str(v), v)
    combo.setFixedWidth(64)
    combo.setCurrentIndex(1)  # 5
    row.addWidget(combo)

    lbl_min = QLabel("分钟前")
    lbl_min.setStyleSheet("font-size: 12px; font-weight: 600; color: #9CA3AF;")
    row.addWidget(lbl_min)

    row.addStretch()

    btn = QPushButton("▶")
    btn.setObjectName("btnTestRemind")
    btn.setFixedSize(34, 34)
    btn.setToolTip("测试提醒")
    btn.setStyleSheet(
        "QPushButton#btnTestRemind {"
        " border: 1px solid #E8EAF0; border-radius: 8px;"
        " background: #FFFFFF; color: #6B7280; font-size: 14px; padding: 0;"
        " font-family: \"Segoe UI Symbol\", \"Segoe UI Emoji\", \"Arial Unicode MS\", sans-serif; }"
        "QPushButton#btnTestRemind:hover { color: #4F6BF6; border-color: #4F6BF6; background: #F5F7FF; }"
        "QPushButton#btnTestRemind:pressed { background: #EDF0FE; }")
    row.addWidget(btn)

    base.addWidget(card)
    win.show()
    time.sleep(0.5)

    out = "E:/AI开发/考勤软件/_shot_remind_design.png"
    pm = win.grab()
    pm.save(out)

    g, pr = analyze(pm)
    print(f"输出: {out}")
    print(f"灰={g} 主={pr}")
    if g > 5 and pr == 0:
        print("OK: 仅检测到设计稿灰色下拉箭头，无蓝色/多余箭头")
    else:
        print(f"注意: 灰={g} 主={pr}")
    app.quit()


if __name__ == "__main__":
    run()
