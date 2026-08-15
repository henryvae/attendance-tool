import sys
import os
import traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PyQt5.QtWidgets import QApplication

try:
    from attendance_tool import LoginWindow
except Exception as e:
    print("IMPORT ERROR:")
    traceback.print_exc()
    sys.exit(1)

app = QApplication(sys.argv)
app.setStyle("Fusion")
try:
    w = LoginWindow()
except Exception as e:
    print("INIT ERROR:")
    traceback.print_exc()
    sys.exit(1)
print("flags:", hex(int(w.windowFlags())))
print("frameless:", bool(w.windowFlags() & 0x00000800))
w.show()
sys.exit(app.exec_())
