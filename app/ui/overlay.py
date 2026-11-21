from PySide6.QtWidgets import QDialog, QLabel, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout, QApplication, QFrame
from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QFont
import time as _time

from app.core.i18n import tr

# Палитра по умолчанию (тёмная), если тема ещё не применялась
_DEFAULT_PALETTE = dict(bg="#16171c", input="#1f2128", text="#e8e9ee",
                        dim="#8a8d98", border2="#32343d", accent="#3d6fd6",
                        nav_hover="#1e2027")


class Overlay(QDialog):
    """Оверлей по Alt+V: весь экран затемняется, по центру — непрозрачная
    панель в цветах текущей темы, поле ввода сразу в фокусе.
    Клик по затемнению скрывает оверлей. Панель можно таскать за верхнюю полосу."""

    PANEL_W, PANEL_H = 620, 170

    def __init__(self, on_submit):
        super().__init__()
        self.on_submit = on_submit
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        # полупрозрачность нужна самому диалогу, чтобы «затемнение» было видно
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.panel = QFrame(self)
        self.panel.setObjectName("panel")
        self.panel.setFixedSize(self.PANEL_W, self.PANEL_H)

        top = QHBoxLayout()
        self.hint = QLabel(tr("Enter — озвучить · Esc — скрыть"))
        self.hint.setObjectName("hint")
        f = QFont(); f.setPointSize(13); f.setBold(True); self.hint.setFont(f)
        top.addWidget(self.hint)
        top.addStretch(1)

        btn_min = QPushButton("—")
        btn_min.setObjectName("obtn")
        btn_min.setToolTip(tr("Скрыть"))
        btn_min.clicked.connect(self.hide)
        top.addWidget(btn_min)

        btn_close = QPushButton("✕")
        btn_close.setObjectName("obtn")
        btn_close.setToolTip(tr("Закрыть"))
        btn_close.clicked.connect(self._cancel)
        top.addWidget(btn_close)

        self.input = QLineEdit()
        self.input.setObjectName("oinput")
        self.input.setPlaceholderText(tr("Введите текст…"))
        self.input.returnPressed.connect(self._submit)
        self.input.installEventFilter(self)

        lay = QVBoxLayout(self.panel)
        lay.setContentsMargins(18, 10, 18, 16)
        lay.setSpacing(8)
        lay.addLayout(top)
        lay.addWidget(self.input)

        self._drag_pos = None
        self._opened_ts = 0.0
        self.set_theme(None)

    def eventFilter(self, obj, event):
        # Гасим клавиши с зажатым Alt в первые полсекунды после открытия:
        # автоповтор «V» из комбинации Alt+V иначе долетает в поле ввода.
        if obj is self.input and event.type() == QEvent.KeyPress:
            if (_time.time() - self._opened_ts) < 0.5 and (event.modifiers() & Qt.AltModifier):
                return True
        return super().eventFilter(obj, event)

    def set_theme(self, palette):
        p = dict(_DEFAULT_PALETTE)
        if palette:
            p.update(palette)
        self.setStyleSheet("""
            QDialog { background: rgba(0, 0, 0, 150); }
            #panel {
                background: %(bg)s; border: 2px solid %(accent)s; border-radius: 14px;
            }
            #hint { color: %(dim)s; background: transparent; }
            #oinput {
                background: %(input)s; color: %(text)s; border: 1px solid %(border2)s;
                border-radius: 8px; padding: 8px 12px; font-size: 18px; font-weight: 600;
                selection-background-color: %(accent)s; outline: none;
            }
            #oinput:focus { border: 1px solid %(accent)s; }
            #obtn {
                background: transparent; color: %(dim)s; border: none; border-radius: 6px;
                font-size: 14px; font-weight: 600; padding: 2px 10px; outline: none;
            }
            #obtn:hover { background: %(nav_hover)s; color: %(text)s; }
        """ % p)

    def resizeEvent(self, event):
        # панель вручную центрируем (без layout — иначе её нельзя таскать)
        if not self._drag_pos:
            self.panel.move((self.width() - self.panel.width()) // 2,
                            (self.height() - self.panel.height()) // 2)
        super().resizeEvent(event)

    def show_overlay(self):
        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(screen)
        self._drag_pos = None
        self._opened_ts = _time.time()
        self.show()
        self.raise_()
        self.activateWindow()
        self.input.setFocus(Qt.ActiveWindowFocusReason)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            pos = event.position().toPoint()
            if not self.panel.geometry().contains(pos):
                # клик по затемнению — скрыть
                self._cancel()
                return
            if pos.y() < self.panel.geometry().top() + 40:
                self._drag_pos = event.globalPosition().toPoint() - self.panel.geometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & Qt.LeftButton:
            self.panel.move(event.globalPosition().toPoint() - self._drag_pos)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self._cancel()
            return
        super().keyPressEvent(event)

    def _submit(self):
        text = self.input.text().strip()
        self.input.clear()
        self.hide()
        if text:
            self.on_submit(text)

    def _cancel(self):
        self.input.clear()
        self.hide()
