import os
import sys
import datetime

from PyQt5.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QVBoxLayout,
    QWidget, QCheckBox, QComboBox, QPushButton
)
from PyQt5.QtCore import Qt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from attendance_tool import STYLE_MODERN


def _week_hint_text(target_date):
    """与 attendance_tool.py 中 _update_week_hint 保持一致（奇数周=小周上班，偶数周=大周休息）"""
    week_num = target_date.isocalendar()[1]
    is_odd = (week_num % 2 != 0)
    if is_odd:
        return "本周 · 小周（上班）", "false"
    else:
        return "本周 · 大周（休息）", "true"


app = QApplication(sys.argv)
app.setStyle("Fusion")
app.setStyleSheet(STYLE_MODERN)

win = QWidget()
win.setWindowTitle("大小周提示验证")
win.setStyleSheet("background: #F6F7FB;")
main_vb = QVBoxLayout(win)
main_vb.setContentsMargins(20, 20, 20, 20)

# 右栏：打卡时间线
right = QFrame()
right.setObjectName("card")
rvb = QVBoxLayout(right)
rvb.setContentsMargins(16, 16, 16, 16)
rvb.setSpacing(10)

# 标题行：打卡时间线 + 大小周提示
tl_head = QHBoxLayout()
tl_head.setSpacing(8)
lbl_tl = QLabel("打卡时间线")
lbl_tl.setObjectName("sectionTitle")
tl_head.addWidget(lbl_tl)
tl_head.addStretch()
lbl_week_hint = QLabel("")
lbl_week_hint.setObjectName("weekHint")
lbl_week_hint.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
tl_head.addWidget(lbl_week_hint)
rvb.addLayout(tl_head)

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

main_vb.addWidget(right)
win.resize(320, 320)
win.show()

# 测试多个日期（周一到周日都显示，只看 ISO 周奇偶）
test_cases = [
    (datetime.date(2026, 8, 10), "周一 第33周"),   # 奇数周
    (datetime.date(2026, 8, 11), "周二 第33周"),   # 奇数周
    (datetime.date(2026, 8, 15), "周六 第33周"),   # 奇数周
    (datetime.date(2026, 8, 16), "周日 第33周"),   # 奇数周
    (datetime.date(2026, 8, 17), "周一 第34周"),   # 偶数周
    (datetime.date(2026, 8, 22), "周六 第34周"),   # 偶数周
]

for idx, (d, desc) in enumerate(test_cases):
    text, rest = _week_hint_text(d)
    print(f"[{idx}] {d} ({desc}) -> {text!r} rest={rest}")
    lbl_week_hint.setText(text)
    lbl_week_hint.setProperty("rest", rest)
    lbl_week_hint.style().unpolish(lbl_week_hint)
    lbl_week_hint.style().polish(lbl_week_hint)
    lbl_week_hint.setVisible(True)

    QApplication.processEvents()
    pixmap = win.grab()
    out = f"_shot_week_hint_{idx}_{d.strftime('%m%d')}.png"
    pixmap.save(out)
    print(f"    saved {out}")

sys.exit(0)
