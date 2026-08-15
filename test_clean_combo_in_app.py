import os
import sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import attendance_tool as at
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QPixmap, QColor


def eprint(*args):
    sys.stderr.write(" ".join(str(a) for a in args) + "\n")
    sys.stderr.flush()


def count(pixmap):
    img = pixmap.toImage()
    w_, h_ = img.width(), img.height()
    gray = prim = 0
    for y in range(h_):
        for x in range(w_):
            c = QColor(img.pixel(x, y))
            if c.alpha() < 50:
                continue
            if abs(c.red() - 107) < 30 and abs(c.green() - 114) < 30 and abs(c.blue() - 128) < 30:
                gray += 1
            if abs(c.red() - 79) < 40 and abs(c.green() - 107) < 40 and abs(c.blue() - 246) < 40:
                prim += 1
    return gray, prim


try:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(at._inject_style_icons(at.STYLE_MODERN))
    eprint(f"QComboBox is _CleanComboBox: {at.QComboBox is at._CleanComboBox}")
    eprint(f"at.QComboBox class: {at.QComboBox.__name__}")

    w = QWidget()
    lay = QVBoxLayout(w)
    cb1 = at.QComboBox()
    cb1.addItems(["2026年8月15日", "其他选项"])
    cb1.setFixedSize(140, 34)
    cb2 = at.QComboBox()
    cb2.addItems(["1", "2", "3"])
    cb2.setFixedSize(60, 34)
    lay.addWidget(cb1)
    lay.addWidget(cb2)
    w.resize(200, 120)
    w.show()

    def go():
        eprint("go() called")
        pm = w.grab()
        eprint(f"grab size={pm.width()}x{pm.height()} null={pm.isNull()}")
        pm.save("E:/AI开发/考勤软件/_verify_clean_combo_in_app.png")
        g, pr = count(pm)
        eprint(f"整窗: 灰={g} 主={pr}")

        pm2 = cb1.grab()
        pm2.save("E:/AI开发/考勤软件/_verify_clean_cb1.png")
        g2, pr2 = count(pm2)
        eprint(f"日期下拉: 灰={g2} 主={pr2}")

        pm3 = cb2.grab()
        pm3.save("E:/AI开发/考勤软件/_verify_clean_cb2.png")
        g3, pr3 = count(pm3)
        eprint(f"加班下拉: 灰={g3} 主={pr3}")

        app.quit()

    QTimer.singleShot(0, go)
    QTimer.singleShot(500, app.quit)
    app.exec_()
except Exception as e:
    import traceback
    traceback.print_exc()
    sys.exit(1)
