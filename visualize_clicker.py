import sys
import threading
import warnings
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton
from PyQt5.QtGui import QPainter, QColor, QRegion, QPainterPath, QCursor
from PyQt5.QtCore import Qt, QTimer, QPoint, pyqtSignal, QObject, QRect, QSize
from PyQt5.QtGui import QTransform
from PyQt5.QtWidgets import QLabel
from PyQt5.QtGui import QMovie

from pynput import keyboard

warnings.filterwarnings("ignore", category=DeprecationWarning)

KEY_LAYOUT = [
    "1234567890",
    "qwertyuiop",
    "asdfghjkl",
    "zxcvbnm"
]

KEY_PIXEL_MAP = {}
PIXEL_STATE = {}

EDGE_MARGIN = 10  # dùng cho resize detection
SNAP_THRESHOLD = 40

class SignalHandler(QObject):
    key_pressed = pyqtSignal(str)

class CustomShapeWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.background_label = QLabel(self)
        self.background_label.setGeometry(self.rect())  # full size
        self.background_label.lower()  # send to back


        self.active_key = None
        self.line_timer = QTimer(self)
        self.line_timer.setSingleShot(True)
        self.line_timer.timeout.connect(self.clear_active_key)

        self.current_key = None
        self.key_display_timer = QTimer(self)
        self.key_display_timer.setSingleShot(True)
        self.key_display_timer.timeout.connect(self.clear_key_display)

        self.active_key = None
        self.line_timer = QTimer(self)
        self.line_timer.setSingleShot(True)
        self.line_timer.timeout.connect(self.clear_active_key)
        
    

        # Window config
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setGeometry(100, 100, 600, 300)
        self.setMinimumSize(300, 200)

        # Pixel logic
        self.build_pixel_map()

        # Exit button
        self.exit_btn = QPushButton("Exit", self)
        self.exit_btn.setGeometry(500, 250, 80, 30)
        self.exit_btn.clicked.connect(QApplication.instance().quit)
        self.exit_btn.setStyleSheet("""
            QPushButton {
                background-color: #d33;
                color: white;
                border-radius: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #a00;
            }
        """)

        # Signals
        self.signals = SignalHandler()
        self.signals.key_pressed.connect(self.handle_key)

        self.pixel_timers = {}
        self._drag_pos = None
        self._resizing = False
        self._resizing_direction = None

        self.show()


    def clear_active_key(self):
        self.active_key = None
        self.update()
    def resizeEvent(self, event):
        self.background_label.setGeometry(self.rect())
        return super().resizeEvent(event)

    def clear_key_display(self):
        self.current_key = None
        self.update()

    def build_pixel_map(self):
        spacing_x, spacing_y = 28, 28   # <— reduced spacing
        offset_x, offset_y = 140, 100   # <— tighter centering
        for row_idx, row in enumerate(KEY_LAYOUT):
            for col_idx, key in enumerate(row):
                pos = QPoint(offset_x + col_idx * spacing_x, offset_y + row_idx * spacing_y)
                KEY_PIXEL_MAP[key] = pos
                PIXEL_STATE[key] = False

    def handle_key(self, key: str):

        self.current_key = key.upper()  # lưu chữ cái in hoa
        self.key_display_timer.start(500)

        key = key.lower()
        if key not in KEY_PIXEL_MAP:
            return

        self.active_key = key
        self.update()

        self.line_timer.start(200)

        self.current_key = key.upper()
        self.key_display_timer.start(500)

        PIXEL_STATE[key] = True
        self.update()

        if key in self.pixel_timers:
            self.pixel_timers[key].stop()

        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda k=key: self.turn_off_pixel(k))
        timer.start(200)
        self.pixel_timers[key] = timer

    def turn_off_pixel(self, key):
        PIXEL_STATE[key] = False
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
    
        # Center of rotation
        center_x = self.width() // 2
        center_y = self.height() // 2
    
        # Transform: Rotate 45 deg, then shear (fall back)
        transform = QTransform()
        transform.translate(center_x, center_y)
        transform.rotate(30)           # Z axis (diamond)
        transform.shear(0.4, 0.3)      # X + Y tilt illusion
        transform.scale(0.8, 0.9)      # perspective compress
        transform.translate(-center_x, -center_y)
    
        painter.setTransform(transform)

        if self.active_key:
            pos = KEY_PIXEL_MAP[self.active_key]
            top_right = QPoint(self.width(), 0)
            painter.setPen(QColor(255, 0, 0, 180))  # Đỏ hơi mờ
            painter.drawLine(top_right, pos)
    
        for key, pos in KEY_PIXEL_MAP.items():
            color = QColor(255, 0, 0) if PIXEL_STATE[key] else QColor(70, 70, 70)
            painter.setBrush(color)
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(pos, 8, 8)
        
        if self.current_key:
            painter.resetTransform()  # bỏ các transform xoay/nghiêng
            painter.setPen(QColor(200, 200, 200, 160))  # ssxám nhạt, mờ
            font = painter.font()
            font.setPointSize(24)
            font.setBold(True)
            painter.setFont(font)

            key_text = f"[{self.current_key}]"
            text_rect = QRect(100, self.height() - 200, 200, 40)  # bottom-left
            painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter, key_text)

    # ===================== Move =====================
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self.is_in_resize_zone(event.pos()):
                self._resizing = True
                self._resizing_origin = event.globalPos()
                self._resizing_size = self.size()
            else:
                self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        pos = event.pos()
        if self._resizing:
            delta = event.globalPos() - self._resizing_origin
            new_width = max(self.minimumWidth(), self._resizing_size.width() + delta.x())
            new_height = max(self.minimumHeight(), self._resizing_size.height() + delta.y())
            self.resize(new_width, new_height)
        elif self._drag_pos:
            new_pos = event.globalPos() - self._drag_pos
            screen = QApplication.desktop().availableGeometry(self)
            if abs(new_pos.x()) < SNAP_THRESHOLD:
                new_pos.setX(0)
            if abs(new_pos.y()) < SNAP_THRESHOLD:
                new_pos.setY(0)
            if abs(new_pos.x() + self.width() - screen.width()) < SNAP_THRESHOLD:
                new_pos.setX(screen.width() - self.width())
            if abs(new_pos.y() + self.height() - screen.height()) < SNAP_THRESHOLD:
                new_pos.setY(screen.height() - self.height())
            self.move(new_pos)
        else:
            self.update_cursor_shape(pos)
        event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        self._resizing = False
        event.accept()

    # ===================== Resize support =====================
    def is_in_resize_zone(self, pos):
        rect = self.rect()
        return rect.right() - EDGE_MARGIN <= pos.x() <= rect.right() and \
               rect.bottom() - EDGE_MARGIN <= pos.y() <= rect.bottom()

    def update_cursor_shape(self, pos):
        if self.is_in_resize_zone(pos):
            self.setCursor(Qt.SizeFDiagCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

def start_key_listener(signal_handler: SignalHandler):
    def on_press(key):
        try:
            if hasattr(key, 'char') and key.char:
                signal_handler.key_pressed.emit(key.char)
        except:
            pass

    listener = keyboard.Listener(on_press=on_press)
    listener.daemon = True
    listener.start()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = CustomShapeWindow()
    threading.Thread(target=start_key_listener, args=(window.signals,), daemon=True).start()
    sys.exit(app.exec_())
