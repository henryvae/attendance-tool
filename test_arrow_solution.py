import sys
import os
from PyQt5.QtWidgets import QApplication, QWidget, QComboBox, QVBoxLayout
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap, QPainter, QColor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from attendance_tool import _arrow_icon_path

GRAY = QColor(107, 114, 128)
PRIMARY = QColor(79, 107, 246)
ARROW_DOWN = _arrow_icon_path("down", "#6B7280", 14).replace("\\", "/")
ARROW_DOWN_PRI = _arrow_icon_path("down", "#4F6BF6", 14).replace("\\", "/")


def count_pixels(pm, x0_pct=0.5, x1_pct=1.0):
    img = pm.toImage()
    w, h = img.width(), img.height()
    x0, x1 = int(w * x0_pct), int(w * x1_pct)
    gray = prim = 0
    for y in range(h):
        for x in range(x0, x1):
            c = QColor(img.pixel(x, y))
            if c.alpha() < 50:
                continue
            if abs(c.red() - GRAY.red()) < 30 and abs(c.green() - GRAY.green()) < 30 and abs(c.blue() - GRAY.blue()) < 30:
                gray += 1
            if abs(c.red() - PRIMARY.red()) < 40 and abs(c.green() - PRIMARY.green()) < 40 and abs(c.blue() - PRIMARY.blue()) < 40:
                prim += 1
    return gray, prim


def make_widget(qss_extra, name):
    w = QWidget()
    base = """
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
    """
    w.setStyleSheet(base + qss_extra)
    cb = QComboBox(w)
    cb.addItems(["1", "2", "3"])
    cb.setGeometry(10, 10, 80, 34)
    w.resize(120, 60)
    w.setObjectName(name)
    return w


def run():
    app = QApplication(sys.argv)

    variants = [
        ("E-bg no-repeat center", f"""
            QComboBox::drop-down {{
                background-image: url({ARROW_DOWN});
                background-repeat: no-repeat;
                background-position: center;
                background-origin: content;
            }}
            QComboBox:hover::drop-down, QComboBox:focus::drop-down {{
                background-image: url({ARROW_DOWN_PRI});
            }}
        """),
        ("F-subclass 重写 paintEvent", f"""
        """),
    ]    ]

    widgets = []
    for name, qss in variants:
        w = make_widget(qss, name)
        widgets.append((name, w))
        w.show()

    def capture():
        for name, w in widgets:
            pm = QPixmap(w.size())
            p = QPainter(pm)
            w.render(p)
            p.end()
            pm.save(f"E:/AI开发/考勤软件/_solution_{name.replace(' ', '_').replace(':', '')}.png")
            g, pr = count_pixels(pm)
            print(f"[{name}] 灰={g} 主={pr} -> {'双箭头' if g>10 and pr>20 else ('仅默认箭头' if g>10 else ('仅图标' if pr>20 else '无'))}")
        app.quit()

    QTimer.singleShot(500, capture)
    app.exec_()


if __name__ == "__main__":
    run()
