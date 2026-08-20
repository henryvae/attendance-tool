import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

app = QApplication(sys.argv)
app.setStyle("Fusion")
from attendance_tool import LoginWindow
w = LoginWindow()
w.show()
app.processEvents()
# simulate login state
w.btn_login.setEnabled(False)
w._progress_track.setVisible(True)
w._progress_anim.start()
w.lbl_err.setText("正在登录，请稍候（首次启动较慢）…")
w.lbl_err.setVisible(True)
app.processEvents()
app.processEvents()
print("track visible:", w._progress_track.isVisible(), "geo:", w._progress_track.geometry())
print("thumb visible:", w._progress_thumb.isVisible(), "geo:", w._progress_thumb.geometry())
pix = w.grab()
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_shot_login_progress.png")
pix.save(out)
print("saved", out, pix.size().width(), pix.size().height())
import sys
sys.stdout.flush()
# force quit without event loop hanging
QApplication.instance().quit()
# give a moment then exit
from PyQt5.QtCore import QTimer
QTimer.singleShot(200, lambda: os._exit(0))
sys.exit(app.exec_())
