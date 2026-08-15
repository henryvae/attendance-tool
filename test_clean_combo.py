import sys
import os
from PyQt5.QtWidgets import (QApplication, QWidget, QComboBox, QStyle, QStyleOptionComboBox)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap, QPainter, QColor

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from attendance_tool import _arrow_icon_path

ARROW_DOWN = _arrow_icon_path("down", "#6B7280", 14).replace("\\", "/")
ARROW_DOWN_PRI = _arrow_icon_path("down", "#4F6BF6", 14).replace("\\", "/")


class CleanComboBox(QComboBox):
    """QComboBox 子类：paintEvent 末尾覆盖默认箭头，画 PNG 箭头。"""
    def paintEvent(self, event):
        super().paintEvent(event)
        opt = QStyleOptionComboBox()
        self.initStyleOption(opt)
        sc_rect = self.style().subControlRect(
            QStyle.CC_ComboBox, opt, QStyle.SC_ComboBoxArrow, self)
        print(f"  sc_rect={sc_rect.width()}x{sc_rect.height()} 组合框={self.width()}x{self.height()}")
        if not sc_rect.isValid():
            return
        painter = QPainter(self)
        # 仅覆盖下拉按钮子控件区域
        painter.fillRect(sc_rect, self.palette().base())
        pix = QPixmap(ARROW_DOWN_PRI if (self.hasFocus() or self.underMouse()) else ARROW_DOWN)
        if not pix.isNull():
            x = sc_rect.x() + (sc_rect.width() - pix.width()) // 2
            y = sc_rect.y() + (sc_rect.height() - pix.height()) // 2
            painter.drawPixmap(x, y, pix)
        painter.end()


def count(pixmap):
    img = pixmap.toImage()
    w, h = img.width(), img.height()
    gray = prim = 0
    for y in range(h):
        for x in range(w):
            c = QColor(img.pixel(x, y))
            if c.alpha() < 50:
                continue
            if abs(c.red() - 107) < 30 and abs(c.green() - 114) < 30 and abs(c.blue() - 128) < 30:
                gray += 1
            if abs(c.red() - 79) < 40 and abs(c.green() - 107) < 40 and abs(c.blue() - 246) < 40:
                prim += 1
    return gray, prim


def run():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # monkey patch: 用 CleanComboBox 替换全局 QComboBox
    import PyQt5.QtWidgets as qtw
    qtw.QComboBox = CleanComboBox

    w = QWidget()
    cb = qtw.QComboBox(w)  # 实际是 CleanComboBox
    cb.addItems(["1", "2", "3"])
    cb.setFixedSize(160, 34)
    w.resize(220, 60)
    w.show()

    def cap():
        pm = QPixmap(w.size())
        p = QPainter(pm); w.render(p); p.end()
        pm.save("E:/AI开发/考勤软件/_solution_J_wide.png")
        g, pr = count(pm)
        print(f"[J-CleanComboBox] 灰={g} 主={pr} -> {'双箭头' if g>10 and pr>20 else ('仅默认' if g>10 else ('仅图标' if pr>20 else '无'))}")
        app.quit()

    QTimer.singleShot(500, cap)
    app.exec_()


if __name__ == "__main__":
    run()
