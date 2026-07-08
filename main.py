import sys
import os

# Set matplotlib backend before any Qt imports
import matplotlib
matplotlib.use("QtAgg")

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from windows.main_window import MainWindow


def main():
    # HiDPI support
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("LocalOps AI")
    app.setOrganizationName("LocalOps")

    icon_path = os.path.join(os.path.dirname(__file__), "assets", "icons", "localops-ai.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    # Load stylesheet
    qss_path = os.path.join(os.path.dirname(__file__), "style", "dark.qss")
    if os.path.exists(qss_path):
        with open(qss_path, "r") as f:
            app.setStyleSheet(f.read())

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
