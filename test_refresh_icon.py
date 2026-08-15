import os
import sys

from PyQt5.QtWidgets import QApplication, QWidget, QHBoxLayout, QPushButton
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap, QPainter

STYLE = """
QPushButton#btnPrimary {
    background: #4F6BF6;
    color: #FFFFFF;
    border: none;
    border-radius: 8px;
    font-weight: 600;
    padding: 9px 20px;
    font-family: "Segoe UI Symbol", "Segoe UI Emoji", "Arial Unicode MS", sans-serif;
}
QPushButton#btnPrimary:hover { background: #4358E0; }
QPushButton#btnPrimary:pressed { background: #3B4FD8; }
"""

app = QApplication(sys.argv)

win = QWidget()
win.setWindowTitle("Refresh Button Icon Test")
win.setStyleSheet("background: #F4F6FA;")
lay = QHBoxLayout(win)
lay.setContentsMargins(20, 20, 20, 20)

btn = QPushButton("\u27F3 刷新")
btn.setObjectName("btnPrimary")
btn.setFixedHeight(34)
btn.setStyleSheet(STYLE)
lay.addWidget(btn)

win.adjustSize()
win.show()


def grab():
    pm = win.grab()
    pm.save("_shot_refresh_icon.png", "PNG")
    print("saved _shot_refresh_icon.png")
    app.quit()


QTimer.singleShot(300, grab)
sys.exit(app.exec_())
