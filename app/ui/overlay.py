from PySide6.QtWidgets import QDialog, QLineEdit, QVBoxLayout, QApplication, QWidget
from PySide6.QtCore import Qt, QEvent
import time as _time

from app.core.i18n import tr

# Палитра по умолчанию (тёмная), если тема ещё не применялась
_DEFAULT_PALETTE = dict(bg="#16171c", input="#1f2128", text="#e8e9ee",
                        dim="#8a8d98", border2="#32343d", accent="#3d6fd6",
                        nav_hover="#1e2027")


class _Dimmer(QWidget):
    """Полноэкранное затемнение под оверлеем. Отдельное окно: рисуется один
    раз при открытии, а панель оверлея — маленькое окно, поэтому печать
    текста не перерисовывает весь экран и не подлагивает.
    Окно непрозрачное + setWindowOpacity: это заметно дешевле для
    видеоподсистемы, чем полноэкранное полупрозрачное окно.
    Клик по затемнению скрывает оверлей."""

    OPACITY = 0.6

    def __init__(self, on_click):
        super().__init__()
        self.on_click = on_click
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setStyleSheet("background: black;")
        self.setWindowOpacity(self.OPACITY)

    def mousePressEvent(self, event):
        self.on_click()


class Overlay(QDialog):
    """Оверлей по Alt+V: экран затемняется (отдельное окно _Dimmer), по центру —
    только поле ввода. Enter — озвучить, Esc — скрыть."""

    PANEL_W, PANEL_H = 620, 72

    def __init__(self, on_submit):
        super().__init__()
        self.on_submit = on_submit
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        # полупрозрачность нужна для скруглённых углов панели
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(self.PANEL_W, self.PANEL_H)

        self.dimmer = _Dimmer(self._cancel)

        self.input = QLineEdit()
        self.input.setObjectName("oinput")
        self.input.setPlaceholderText(tr("Введите текст…  (Enter — озвучить, Esc — скрыть)"))
        self.input.returnPressed.connect(self._submit)
        self.input.installEventFilter(self)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.addWidget(self.input)

        self._opened_ts = 0.0
        self.set_theme(None)

    def eventFilter(self, obj, event):
        # Гасим «эхо» клавиши вызова (V/М) в первые доли секунды после
        # открытия: автоповтор зажатой V, события с зажатым Alt и одиночное
        # нажатие той же физической клавиши (VK 0x56 — v/м в любой раскладке)
        # иначе долетают в поле ввода.
        if obj is self.input and event.type() == QEvent.KeyPress:
            dt = _time.time() - self._opened_ts
            if dt < 0.5:
                if event.modifiers() & Qt.AltModifier or event.isAutoRepeat():
                    return True
                if dt < 0.3 and (event.nativeVirtualKey() == 0x56
                                 or event.text().lower() in ("v", "м")):
                    return True
        return super().eventFilter(obj, event)

    def set_theme(self, palette, key=None):
        # применение стилей — дорогое, поэтому повторный вызов с той же
        # темой просто пропускаем
        if key is not None and key == getattr(self, "_theme_key", None):
            return
        self._theme_key = key
        p = dict(_DEFAULT_PALETTE)
        if palette:
            p.update(palette)
        self.setStyleSheet("""
            QDialog {
                background: %(bg)s; border: 2px solid %(accent)s; border-radius: 14px;
            }
            #oinput {
                background: %(input)s; color: %(text)s; border: none;
                border-radius: 8px; padding: 8px 12px; font-size: 18px; font-weight: 600;
                selection-background-color: %(accent)s; outline: none;
            }
        """ % p)

    def show_overlay(self):
        screen = QApplication.primaryScreen().geometry()
        self.dimmer.setGeometry(screen)
        self.dimmer.show()
        self.move(screen.x() + (screen.width() - self.width()) // 2,
                  screen.y() + (screen.height() - self.height()) // 2)
        self._opened_ts = _time.time()
        self.show()
        self.raise_()
        self.activateWindow()
        self.input.setFocus(Qt.ActiveWindowFocusReason)

    def hide(self):
        self.dimmer.hide()
        super().hide()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self._cancel()
            return
        super().keyPressEvent(event)

    def _submit(self):
        text = self.input.text().strip()
        self.input.clear()
        self.hide()
        # озвучку запускаем уже после того, как окно скрылось и событие
        # обработано — GUI-поток не ждёт speak()
        if text:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, lambda: self.on_submit(text))

    def _cancel(self):
        self.input.clear()
        self.hide()
