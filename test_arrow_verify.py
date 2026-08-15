# -*- coding: utf-8 -*-
"""用真实的 STYLE_MODERN + _inject_style_icons 验证箭头渲染（像素级）。"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QComboBox, QSpinBox, QWidget, QVBoxLayout
from PyQt5.QtGui import QImage

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import attendance_tool as at

app = QApplication(sys.argv)
app.setStyle("Fusion")
app.setStyleSheet(at._inject_style_icons(at.STYLE_MODERN))  # 与 main() 完全一致

w = QWidget()
lay = QVBoxLayout(w)
combo = QComboBox(); combo.addItems(["2026年8月"])
spin_h = QSpinBox(); spin_h.setRange(0, 8)
spin_m = QSpinBox(); spin_m.setRange(0, 59)
lay.addWidget(combo); lay.addWidget(spin_h); lay.addWidget(spin_m)
w.resize(200, 160)
w.show()
app.processEvents()

def count_arrow_pixels(widget, name):
    pm = widget.grab()
    pm.save(f"_verify_{name}.png")
    img = pm.toImage()
    # 扫描整个控件右侧 26px 区域找灰色/主色箭头笔画
    region = img.copy(img.width() - 26, 0, 26, img.height())
    gray = primary = 0
    for y in range(region.height()):
        for x in range(region.width()):
            c = region.pixelColor(x, y)
            if c.alpha() > 30:
                if abs(c.red() - c.blue()) < 60 and c.red() < 200 and c.green() < 200:
                    gray += 1
                if c.blue() > 200 and c.red() < 150:  # #4F6BF6 主色系
                    primary += 1
    print(f"{name}: 灰色箭头像素={gray} 主色像素={primary} -> {'OK 渲染成功' if gray > 5 else 'FAIL 空白'}")
    return gray

ok1 = count_arrow_pixels(combo, "QComboBox")
ok2 = count_arrow_pixels(spin_h, "QSpinBox")

print("\n===== 最终结论 =====")
print("下拉框:", "渲染成功" if ok1 > 5 else "空白")
print("微调框:", "渲染成功" if ok2 > 5 else "空白")
assert ok1 > 5 and ok2 > 5, "仍有空白，禁止打包！"
print("全部通过，可以打包")
