# -*- coding: utf-8 -*-
"""自动化测试：验证 QSS image: url() 箭头图标是否真的渲染出来。

分别测试 3 种 URL 写法（file:/// 前缀 / 正斜杠绝对路径 / 反斜杠路径），
渲染 QComboBox 下拉箭头区域，分析像素判断箭头是否可见。
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QComboBox, QSpinBox, QWidget, QVBoxLayout
from PyQt5.QtGui import QImage, QColor
from PyQt5.QtCore import Qt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import attendance_tool as at

app = QApplication(sys.argv)
app.setStyle("Fusion")

# 1) 生成箭头 PNG（与程序一致的路径）
png = at._arrow_icon_path("down", "#6B7280", 14)
print("[1] PNG 路径:", png)
print("    存在:", os.path.exists(png), "大小:", os.path.getsize(png) if os.path.exists(png) else -1)

img = QImage(png)
print("    QImage 尺寸:", img.width(), "x", img.height())
# 检查 PNG 里是否真的有非透明像素（箭头笔画）
non_transparent = 0
for y in range(img.height()):
    for x in range(img.width()):
        if img.pixelColor(x, y).alpha() > 30:
            non_transparent += 1
print("    非透明像素数:", non_transparent)

# 2) 三种 URL 写法
png_fwd = png.replace(os.sep, "/")
variants = {
    "A_file_url":   "file:///" + png_fwd,
    "B_fwd_path":   png_fwd,
    "C_back_path":  png,
}

QSS_TMPL = """
QComboBox {{ border: 1px solid #E8EAF0; border-radius: 8px; background: #FFFFFF; padding: 4px 28px 4px 10px; }}
QComboBox::drop-down {{ width: 24px; border: none; border-left: 1px solid #E8EAF0; subcontrol-origin: padding;
    subcontrol-position: top right; }}
QComboBox::down-arrow {{ width: 14px; height: 14px; image: url("{url}"); }}
"""

results = {}
for name, url in variants.items():
    w = QWidget()
    w.setStyleSheet(QSS_TMPL.format(url=url))
    lay = QVBoxLayout(w)
    combo = QComboBox()
    combo.addItems(["测试项"])
    spin = QSpinBox()
    lay.addWidget(combo)
    lay.addWidget(spin)
    w.resize(160, 90)
    w.show()
    app.processEvents()

    pm = combo.grab()
    pm.save(f"_arrow_test_{name}.png")

    # 分析下拉箭头区域：drop-down 宽 24px，箭头 14x14 居中
    region = pm.copy(pm.width() - 26, 0, 26, pm.height()).toImage()
    colored = 0
    for y in range(region.height()):
        for x in range(region.width()):
            c = region.pixelColor(x, y)
            # 找"灰色箭头"像素：不是纯白、不是透明、偏灰暗（RGB 都 < 200 且差异小）
            if c.alpha() > 30 and c.red() < 200 and c.green() < 200 and abs(c.red() - c.blue()) < 60:
                colored += 1
    results[name] = colored
    print(f"[2] {name}: 箭头区域灰色像素数 = {colored}  -> {'渲染成功' if colored > 5 else '空白/未渲染'}")
    w.hide()

# 3) 对照：完全不写 image（纯 Fusion 默认箭头）
w2 = QWidget(); w2.resize(160, 50)
lay2 = QVBoxLayout(w2)
combo2 = QComboBox(); combo2.addItems(["对照"])
lay2.addWidget(combo2)
w2.show(); app.processEvents()
pm2 = combo2.grab()
region2 = pm2.copy(pm2.width() - 26, 0, 26, pm2.height()).toImage()
colored2 = 0
for y in range(region2.height()):
    for x in range(region2.width()):
        c = region2.pixelColor(x, y)
        if c.alpha() > 30 and c.red() < 200 and c.green() < 200 and abs(c.red() - c.blue()) < 60:
            colored2 += 1
print(f"[3] 对照组(默认样式): 箭头区域灰色像素数 = {colored2}")

print("\n===== 结论 =====")
ok = [k for k, v in results.items() if v > 5]
print("渲染成功的 URL 写法:", ok if ok else "无（全部空白！）")
