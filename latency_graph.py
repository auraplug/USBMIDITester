
from collections import deque

from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QPen, QColor, QFont
from PySide6.QtCore import Qt


class LatencyGraph(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.values = deque(maxlen=180)
        self.setMinimumHeight(180)

        self.setStyleSheet(
            "background-color: #171d28;"
        )

    def add_value(self, value):

        if value is None:
            return

        self.values.append(float(value))
        self.update()

    def clear(self):
        self.values.clear()
        self.update()

    def paintEvent(self, event):

        painter = QPainter(self)

        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing
        )

        rect = self.rect()
        painter.fillRect(rect, QColor("#171d28"))

        left = 48
        right = 12
        top = 20
        bottom = 28

        width = rect.width() - left - right
        height = rect.height() - top - bottom

        if width <= 0 or height <= 0:
            return

        painter.setFont(QFont("Arial", 8))

        # Automatikus skála
        maximum = max(
            max(self.values, default=1),
            1
        ) * 1.2

        # Segédvonalak
        for i in range(5):

            y = top + height * i / 4
            value = maximum * (4 - i) / 4

            painter.setPen(QPen(
                QColor("#354253"), 1
            ))

            painter.drawLine(
                left, int(y),
                left + width, int(y)
            )

            painter.setPen(QColor("#aab6c5"))

            painter.drawText(
                2, int(y) + 4,
                f"{value:.1f}"
            )

        painter.setPen(QColor("#aab6c5"))
        painter.drawText(4, 12, "ms")

        if len(self.values) < 2:
            painter.end()
            return

        points = []

        for i, value in enumerate(self.values):

            x = left + width * (
                i / (len(self.values) - 1)
            )

            y = top + height * (
                1 - value / maximum
            )

            points.append((int(x), int(y)))

        pen = QPen(QColor("#22c985"), 2)
        painter.setPen(pen)

        for i in range(1, len(points)):

            painter.drawLine(
                points[i-1][0],
                points[i-1][1],
                points[i][0],
                points[i][1]
            )

        painter.end()
