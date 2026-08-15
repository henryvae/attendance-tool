import sys
import os
from PyQt5.QtWidgets import QApplication, QWidget, QHBoxLayout
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap, QPainter, QColor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from attendance_tool import STYLE_MODERN, _StyledComboBox

GRAY = QColor(107, 114, 128)
PRIMARY = QColor(79, 107, 246)


def count_arrow_pixels(pm):
    img = pm.toImage()
    w, h = img.width(), img.height()
    # 只看右半部分（下拉按钮区域）
    x0 = w // 2
    gray = prim = 0
    for y in range(h):
        for x in range(x0, w):
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

    w = QWidget()
    w.setStyleSheet(STYLE_MODERN)
    layout = QHBoxLayout(w)
    layout.setSpacing(12)

    cb1 = _StyledComboBox()
    cb1.addItems(["8/15 周六"])
    cb1.setMinimumWidth(100)

    cb2 = _StyledComboBox()
    cb2.addItems([str(i) for i in range(13)])
    cb2.setFixedWidth(60)

    cb3 = _StyledComboBox()
    cb3.addItems(["0", "15", "30", "45"])
    cb3.setFixedWidth(60)

    for cb in (cb1, cb2, cb3):
        layout.addWidget(cb)

    w.resize(360, 80)

    def capture():
        pm = QPixmap(w.size())
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        w.render(p)
        p.end()
        pm.save("E:/AI开发/考勤软件/_shot_combo_design.png")
        g, pr = count_arrow_pixels(pm)
        print(f"灰={g} 主={pr}")
        if g > 5 and pr == 0:
            print("OK: 仅显示设计稿灰色箭头")
        elif g == 0:
            print("WARN: 未检测到灰色箭头")
        else:
            print(f"异常: 灰={g} 主={pr}")
        app.quit()

    w.show()
    QTimer.singleShot(500, capture)
    app.exec_()


if __name__ == "__main__":
    run()
