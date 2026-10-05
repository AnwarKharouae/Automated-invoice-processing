import os
import sys

# When frozen, ensure the internal bundle folder is on sys.path
if getattr(sys, "frozen", False):
    _base = getattr(sys, "_MEIPASS", None)
    if _base and _base not in sys.path:
        sys.path.insert(0, _base)
    _exe_dir = os.path.dirname(sys.executable)
    if _exe_dir not in sys.path:
        sys.path.insert(0, _exe_dir)

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Invoice Reviewer")

    # ---- window / taskbar icon ----
    if getattr(sys, "frozen", False):
        icon_path = os.path.join(os.path.dirname(sys.executable), "icon.ico")
    else:
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    # -------------------------------

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()