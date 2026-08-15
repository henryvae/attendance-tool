import sys
import os
from PyQt5.QtWidgets import QApplication, QWidget, QComboBox, QProxyStyle, QStyle
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap, QPainter, QColor

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from attendance_tool import _arrow_icon_path

GRAY = QColor(107, 114, 128)
PRIMARY = QColor(79, 107, 246)
ARROW_DOWN = _arrow_icon_path("down", "#6B7280", 14).replace("\\", "/")
ARROW_DOWN_PRI = _arrow_icon_path("down", "#4F6BF6", 14).replace("\\", "/")


class NoArrowStyle(QProxyStyle):
    """拦截默认下拉箭头绘制，让 QSS image 自己显示。"""
    def drawPrimitive(self, element, option, painter, widget=None):
        if element in (QStyle.PE_IndicatorArrowDown, QStyle.PE_IndicatorArrowUp):
            return
        super().drawPrimitive(element, option, painter, widget)


def count(pixmap):
    img = pixmap.toImage()
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
    app.setStyle(NoArrowStyle("Fusion"))

    qss = """
        QComboBox {
            border: 1.5px solid #E8EAF0;
            border-radius: 8px;
            padding: 6px 10px;
            background: white;
            font-size: 13px;
            min-height: 32px;
        }
        QComboBox::drop-down {
            width: 24px;
            border: none;
            border-left: 1px solid #E8EAF0;
            border-top-right-radius: 8px;
            border-bottom-right-radius: 8px;
            background: transparent;
        }
        QComboBox::down-arrow {
            image: url(%s);
        }
        QComboBox:hover::down-arrow, QComboBox:focus::down-arrow {
            image: url(%s);
        }
    """ % (ARROW_DOWN, ARROW_DOWN_PRI)

    w = QWidget()
    w.setStyleSheet(qss)
    cb = QComboBox(w)
    cb.addItems(["1", "2", "3"])
    cb.setGeometry(10, 10, 80, 34)
    w.resize(150, 60)
    w.show()

    def cap():
        pm = QPixmap(w.size())
        p = QPainter(pm)
        w.render(p)
        p.end()
        pm.save("E:/AI开发/考勤软件/_solution_G-ProxyStyle.png")
        g, pr = count(pm)
        print(f"[G-ProxyStyle] 灰={g} 主={pr} -> {'双箭头' if g>10 and pr>20 else ('仅默认' if g>10 else ('仅图标' if pr>20 else '无'))}")
        app.quit()

    QTimer.singleShot(500, cap)
    app.exec_()


if __name__ == "__main__":
    run()
