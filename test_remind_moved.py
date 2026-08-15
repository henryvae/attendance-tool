import os
import sys

from PyQt5.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QVBoxLayout,
    QWidget, QCheckBox, QComboBox, QPushButton
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QPixmap

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from attendance_tool import STYLE_MODERN


class _SignalLabel(QLabel):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)


app = QApplication(sys.argv)
app.setStyle("Fusion")
app.setStyleSheet(STYLE_MODERN)

win = QWidget()
win.setWindowTitle("下班提醒位置验证")
win.setStyleSheet("background: #F6F7FB;")
main_vb = QVBoxLayout(win)
main_vb.setContentsMargins(20, 20, 20, 20)

# 模拟主界面双栏
outer = QHBoxLayout()
outer.setSpacing(14)

# 左卡：今日考勤详情（包含下班提醒底部）
left = QFrame()
left.setObjectName("card")
lvb = QVBoxLayout(left)
lvb.setContentsMargins(16, 16, 16, 16)
lvb.setSpacing(4)

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

# 分隔线
sep_rmd = QFrame()
sep_rmd.setObjectName("hsep")
lvb.addWidget(sep_rmd)

# 下班提醒行（在今日考勤详情卡片底部）
row_rmd = QHBoxLayout()
row_rmd.setContentsMargins(0, 4, 0, 4)
row_rmd.setSpacing(8)

lbl_bell = QLabel("🔔 下班提醒")
lbl_bell.setStyleSheet("font-size: 13px; font-weight: 600; color: #3A4050;")
row_rmd.addWidget(lbl_bell)

cb = QCheckBox()
cb.setChecked(True)
cb.setStyleSheet("QCheckBox::indicator:checked { background: #4F6BF6; border: none; }")
row_rmd.addWidget(cb)

combo = QComboBox()
for v in (0, 5, 10, 15, 20, 30, 45, 60):
    combo.addItem(str(v), v)
combo.setFixedWidth(64)
combo.setStyleSheet(
    "QComboBox { border: 1px solid #D6DAE4; border-radius: 8px; padding: 0 8px; height: 30px; }"
)
row_rmd.addWidget(combo)

lbl_min = QLabel("分钟前")
lbl_min.setStyleSheet("font-size: 12px; font-weight: 600; color: #9CA3AF;")
row_rmd.addWidget(lbl_min)

row_rmd.addStretch()

btn = QPushButton(">")
btn.setFixedSize(34, 34)
btn.setStyleSheet(
    "QPushButton { border: 1px solid #E8EAF0; border-radius: 8px;"
    " background: #FFFFFF; color: #6B7280; font-size: 14px; }"
)
row_rmd.addWidget(btn)
lvb.addLayout(row_rmd)

lvb.addStretch()
outer.addWidget(left, stretch=3)

# 右卡：打卡时间线（不包含下班提醒）
right = QFrame()
right.setObjectName("card")
rvb = QVBoxLayout(right)
rvb.setContentsMargins(16, 16, 16, 16)
rvb.setSpacing(10)
lbl_tl = QLabel("打卡时间线")
lbl_tl.setObjectName("sectionTitle")
rvb.addWidget(lbl_tl)
for i in range(4):
    row = QHBoxLayout()
    row.setSpacing(10)
    dot = QFrame()
    dot.setFixedSize(8, 8)
    dot.setStyleSheet("background: #4F6BF6; border-radius: 4px;")
    row.addWidget(dot, 0, Qt.AlignVCenter)
    row.addWidget(QLabel("07:46"))
    row.addWidget(QLabel("上班打卡"))
    row.addStretch()
    rvb.addLayout(row)
rvb.addStretch()
outer.addWidget(right, stretch=2)

main_vb.addLayout(outer)
win.resize(720, 420)
win.show()

QApplication.processEvents()
pixmap = win.grab()
pixmap.save("_shot_remind_moved.png")
print("saved _shot_remind_moved.png")

sys.exit(0)
