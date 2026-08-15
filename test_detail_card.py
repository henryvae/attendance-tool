import os
import sys

from PyQt5.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QPixmap

# 导入主程序样式表
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from attendance_tool import STYLE_MODERN


class _SignalLabel(QLabel):
    """模拟主程序的 _SignalLabel，仅用于保持样式一致"""
    def __init__(self, text, parent=None):
        super().__init__(text, parent)


app = QApplication(sys.argv)
app.setStyle("Fusion")
app.setStyleSheet(STYLE_MODERN)

# 模拟一个 QWidget 窗口，只放今日考勤详情卡片
win = QWidget()
win.setWindowTitle("今日考勤详情 - 设计稿验证")
win.setStyleSheet("background: #F6F7FB;")
main_vb = QVBoxLayout(win)
main_vb.setContentsMargins(20, 20, 20, 20)

left = QFrame()
left.setObjectName("card")
lvb = QVBoxLayout(left)
lvb.setContentsMargins(16, 16, 16, 16)
lvb.setSpacing(4)

# card-head
head = QHBoxLayout()
head.setSpacing(0)
lbl_sec1 = QLabel("今日考勤详情")
lbl_sec1.setObjectName("sectionTitle")
head.addWidget(lbl_sec1)
head.addStretch()
late_badge = QLabel("迟到 ×2")
late_badge.setObjectName("badgeRed")
head.addWidget(late_badge)
early_badge = QLabel("早退 ×1")
early_badge.setObjectName("badgeOrange")
early_badge.setContentsMargins(6, 0, 0, 0)
head.addWidget(early_badge)
lvb.addLayout(head)


def _add_row(label, value, obj_name, signal=False):
    row = QHBoxLayout()
    row.setContentsMargins(0, 3, 0, 3)
    row.setSpacing(8)
    lbl_k = QLabel(label)
    lbl_k.setObjectName("detailKey")
    row.addWidget(lbl_k)
    row.addStretch()
    lbl_cls = _SignalLabel if signal else QLabel
    lbl_v = lbl_cls(value)
    lbl_v.setObjectName(obj_name)
    row.addWidget(lbl_v)
    lvb.addLayout(row)


_add_row("打卡记录", "07:46 · 17:15 · 17:56 · 20:01", "detailValMono", signal=True)
_add_row("应下班时间", "18:07", "valuePrimary")
_add_row("已工作时长", "08时48分", "valueSuccess")
_add_row("已加班时长", "02时15分", "valueWarning")
_add_row("平加 (工作日)", "20.0 h", "detailValMono")
_add_row("周加 (周末)", "8.0 h", "detailValMono")
_add_row("假加 (节假日)", "0.5 h", "detailValMono")
_add_row("合计加班", "28.5 h", "valuePrimary")

lvb.addStretch()
main_vb.addWidget(left)
win.resize(420, 360)
win.show()

# 等待布局完成后截图
QApplication.processEvents()
pixmap = win.grab()
pixmap.save("_shot_detail_card.png")
print("saved _shot_detail_card.png")

sys.exit(0)
