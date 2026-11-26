import sys
import threading
import time
from pathlib import Path
from PySide6.QtWidgets import (
    QAbstractButton, QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QLabel, QListWidget, QListWidgetItem,
    QComboBox, QCheckBox, QSlider, QMessageBox, QAbstractItemView,
    QStackedWidget, QButtonGroup, QFrame, QSizeGrip, QLineEdit, QKeySequenceEdit,
    QScrollArea, QToolButton, QSizePolicy,
)
from PySide6.QtCore import Qt, QTimer, QObject, Signal, QEvent, QSize, QByteArray, QRect, QCoreApplication
from PySide6.QtGui import QIcon, QPixmap, QFont, QFontDatabase, QPainter
from PySide6.QtSvg import QSvgRenderer

from app import __version__
from app.core.settings import Settings, APP_DIR, CACHE_DIR
from app.core.history import History
from app.core.tts_engine import TTSEngine
from app.core import audio_out, driver, voices_setup
from app.core.hotkeys import GlobalHotkeys, parse_combo, _SPECIAL_VALUES
from app.core.i18n import tr, set_lang
from app.ui.overlay import Overlay


def _assets_dir():
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "app" / "ui" / "assets"
    return Path(__file__).resolve().parent / "assets"


ASSETS_DIR = _assets_dir()
ICON_PATH = ASSETS_DIR / "icon.png"
FONT_PATH = ASSETS_DIR / "fonts" / "Inter.ttf"

FONT_STACK = '"Inter", "Segoe UI Variable Text", "Segoe UI", sans-serif'
CHECK_SVG = (ASSETS_DIR / "check.svg").as_posix()

# --- палитры тем -----------------------------------------------------------
_BASE_DARK = dict(
    bg="#16171c", panel="#101116", border="#26272e", border2="#32343d",
    text="#e8e9ee", dim="#8a8d98", input="#1f2128", nav_hover="#1e2027",
    secondary="#2a2c34", secondary_hover="#34363f",
)
_BASE_LIGHT = dict(
    bg="#f5f6f9", panel="#ffffff", border="#e2e4ea", border2="#d4d7df",
    text="#22252c", dim="#8a8f9c", input="#ffffff", nav_hover="#eef0f5",
    secondary="#e4e6ec", secondary_hover="#d7dae2",
)


def _dark_variant(accent, hover, pressed, **over):
    p = dict(_BASE_DARK, accent=accent, accent_hover=hover, accent_pressed=pressed)
    p.update(over)
    return p


THEME_PALETTES = {
    "dark": _dark_variant("#3d6fd6", "#4a7de4", "#2f5cb8"),
    "light": dict(_BASE_LIGHT, accent="#3d6fd6", accent_hover="#4a7de4",
                  accent_pressed="#2f5cb8"),
    "black": _dark_variant("#3d6fd6", "#4a7de4", "#2f5cb8",
                           bg="#000000", panel="#0a0a0c", border="#1b1b20",
                           border2="#26262c", input="#101013", nav_hover="#16161a",
                           dim="#7a7d88", secondary="#1a1a1e", secondary_hover="#222228"),
    "green": _dark_variant("#35a05a", "#41b868", "#2b8249",
                           bg="#0f1a12", panel="#0b130d", border="#1d2e21",
                           border2="#28402e", input="#14231a", nav_hover="#16281c",
                           dim="#87a08c", secondary="#1c2e22", secondary_hover="#243a2c"),
    "red": _dark_variant("#d64550", "#e4555f", "#b83742",
                         bg="#1a1113", panel="#130c0d", border="#2e1d1f",
                         border2="#402827", input="#231416", nav_hover="#281618",
                         dim="#a08a8c", secondary="#2e1c1e", secondary_hover="#3a2326"),
    "purple": _dark_variant("#8b5cf6", "#9d72f8", "#7449d6",
                            bg="#151222", panel="#0f0d19", border="#241e3a",
                            border2="#2f2850", input="#1a1730", nav_hover="#1c1832",
                            dim="#948fb0", secondary="#221d3a", secondary_hover="#2a2450"),
    "blue": _dark_variant("#2ea6e8", "#4cb6ef", "#2589c2",
                          bg="#0e1a24", panel="#0a121a", border="#1a2c3c",
                          border2="#22405a", input="#12222e", nav_hover="#14283a",
                          dim="#829cb0", secondary="#16283a", secondary_hover="#1c3448"),
    "orange": _dark_variant("#e8823d", "#f5914a", "#c96f32",
                            bg="#1c1410", panel="#130e0a", border="#30221a",
                            border2="#423026", input="#241a12", nav_hover="#2a1e14",
                            dim="#b09482", secondary="#2e221a", secondary_hover="#3a2a20"),
}

# (ключ, название) — порядок в списке настроек; тема по умолчанию: dark
THEMES = [
    ("dark", "Тёмная"), ("light", "Белая"), ("black", "Чёрная"),
    ("green", "Зелёная"), ("red", "Красная"), ("purple", "Фиолетовая"),
    ("blue", "Голубая"), ("orange", "Оранжевая"),
]

_THEME_QSS = """
QMainWindow, QDialog, QMessageBox, QInputDialog { background: %(bg)s; }
QWidget { color: %(text)s; font-family: %(font)s; font-size: 14px; outline: none; }
#titlebar { background: %(panel)s; border-bottom: 1px solid %(border)s; }
#titleName { font-weight: 600; font-size: 13px; color: %(dim)s; }
QPushButton[titleBtn="true"] {
    background: transparent; border: none; border-radius: 6px;
    color: %(dim)s; font-size: 14px; padding: 4px 12px; outline: none;
}
QPushButton[titleBtn="true"]:hover { background: %(nav_hover)s; color: %(text)s; }
QPushButton[closeBtn="true"] {
    background: transparent; border: none; border-radius: 6px;
    color: %(dim)s; font-size: 14px; padding: 4px 12px; outline: none;
}
QPushButton[closeBtn="true"]:hover { background: #e81123; color: white; }
#sidebar { background: %(panel)s; border-right: 1px solid %(border)s; }
#appName { font-size: 16px; font-weight: 600; letter-spacing: 0.5px; }
#appTagline { color: %(dim)s; font-size: 11px; }
QToolButton[nav="true"] {
    background: transparent; border: none; border-radius: 10px; outline: none;
    padding: 10px 6px; font-size: 12px; color: %(dim)s;
}
QToolButton[nav="true"]:hover { background: %(nav_hover)s; color: %(text)s; }
QToolButton[nav="true"]:checked { background: %(accent)s; color: white; font-weight: 600; }
QToolButton[nav="true"]:focus { outline: none; }
#content { background: %(bg)s; }
QTextEdit, QLineEdit, QListWidget, QComboBox, QKeySequenceEdit {
    background: %(input)s; border: 1px solid %(border2)s; border-radius: 10px; padding: 8px;
    selection-background-color: %(accent)s; outline: none;
}
QTextEdit:focus, QLineEdit:focus, QListWidget:focus, QComboBox:focus, QKeySequenceEdit:focus {
    border: 1px solid %(accent)s; outline: none;
}
QComboBox::drop-down { border: none; width: 28px; }
QComboBox::down-arrow { image: none; border-left: 5px solid transparent;
    border-right: 5px solid transparent; border-top: 6px solid %(dim)s; margin-right: 10px; }
QComboBox QAbstractItemView {
    background: %(input)s; color: %(text)s; border: 1px solid %(border2)s;
    selection-background-color: %(accent)s; selection-color: white; outline: none;
}
QPushButton {
    background: %(accent)s; color: white; border: none; border-radius: 10px;
    padding: 10px 20px; font-weight: 600; outline: none;
}
QPushButton:hover { background: %(accent_hover)s; }
QPushButton:pressed { background: %(accent_pressed)s; }
QPushButton[secondary="true"] { background: %(secondary)s; color: %(text)s; font-weight: 400; }
QPushButton[secondary="true"]:hover { background: %(secondary_hover)s; }
QPushButton[compact="true"] { padding: 6px 10px; }
QCheckBox { spacing: 10px; outline: none; }
QCheckBox::indicator {
    width: 20px; height: 20px; border-radius: 6px;
    border: 2px solid %(border2)s; background: %(input)s;
}
QCheckBox::indicator:hover { border-color: %(accent)s; }
QCheckBox::indicator:checked {
    background: %(accent)s; border-color: %(accent)s;
    image: url(%(check)s);
}
QSlider::groove:horizontal { height: 6px; background: %(border2)s; border-radius: 3px; }
QSlider::handle:horizontal { width: 16px; margin: -6px 0; border-radius: 8px; background: %(accent)s; }
QStatusBar { background: %(panel)s; color: %(dim)s; }
QToolTip { background: %(input)s; color: %(text)s; border: 1px solid %(border2)s; padding: 6px; }
QLabel[dim="true"] { color: %(dim)s; }
QScrollArea { background: transparent; border: none; }
QScrollArea > QWidget > QWidget { background: transparent; }
QScrollBar:vertical {
    background: transparent; width: 10px; margin: 2px;
}
QScrollBar::handle:vertical {
    background: %(border2)s; border-radius: 5px; min-height: 30px;
}
QScrollBar::handle:vertical:hover { background: %(accent)s; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal {
    background: %(border2)s; border-radius: 5px; min-width: 30px;
}
QScrollBar::handle:horizontal:hover { background: %(accent)s; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QSizeGrip { background: transparent; width: 14px; height: 14px; }
"""


def build_stylesheet(theme_key):
    palette = THEME_PALETTES.get(theme_key) or THEME_PALETTES["dark"]
    return _THEME_QSS % dict(font=FONT_STACK, check=CHECK_SVG, **palette)


# --- иконки навигации (стиль: тонкие линии, цвет берётся из темы) ----------
NAV_ICONS = {
    0: ('<rect x="9" y="2" width="6" height="12" rx="3"/>'
        '<path d="M5 10a7 7 0 0 0 14 0"/>'
        '<line x1="12" y1="17" x2="12" y2="22"/><line x1="8" y1="22" x2="16" y2="22"/>'),
    1: ('<circle cx="12" cy="12" r="9"/>'
        '<polyline points="12 7 12 12 15.5 14"/>'),
    2: ('<line x1="4" y1="10" x2="4" y2="14"/><line x1="8" y1="7" x2="8" y2="17"/>'
        '<line x1="12" y1="4" x2="12" y2="20"/><line x1="16" y1="7" x2="16" y2="17"/>'
        '<line x1="20" y1="10" x2="20" y2="14"/>'),
    3: ('<line x1="4" y1="7" x2="20" y2="7"/><circle cx="9" cy="7" r="2.2"/>'
        '<line x1="4" y1="17" x2="20" y2="17"/><circle cx="15" cy="17" r="2.2"/>'),
}


def render_icon(svg_body, color, size=24):
    """Рисует SVG-иконку заданным цветом -> QPixmap (перекраска под тему)."""
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
           'stroke="%s" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
           '%s</svg>') % (color, svg_body)
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    painter = QPainter(pm)
    renderer.render(painter)
    painter.end()
    return pm


class Bus(QObject):
    refresh_history = Signal()
    refresh_voices = Signal()
    status = Signal(str)
    speak_text = Signal(str)
    speak_bind = Signal(str)   # бинд: озвучить с кэшированием wav
    toggle_overlay = Signal()
    driver_exe_ready = Signal(object)


class SpeakInput(QTextEdit):
    def __init__(self, on_enter):
        super().__init__()
        self.on_enter = on_enter
        self.setPlaceholderText(tr("Введите текст и нажмите Enter…"))

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and not (event.modifiers() & Qt.ShiftModifier):
            self.on_enter()
            return
        super().keyPressEvent(event)


class _HandCursor(QObject):
    """Курсор «рука» над любой кнопкой приложения (и над будущими,
    созданными после построения окна — Polish срабатывает у каждого)."""

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Polish and isinstance(obj, QAbstractButton):
            try:
                obj.setCursor(Qt.PointingHandCursor)
            except Exception:
                pass
        return False


class _WheelToScroll(QObject):
    """Колесо мыши над выпадающими списками и ползунками в настройках не
    меняет их значения, а прокручивает саму страницу настроек."""

    def __init__(self, viewport):
        super().__init__()
        self._viewport = viewport

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Wheel:
            QCoreApplication.sendEvent(self._viewport, event)
            return True
        return False


class TitleBar(QFrame):
    """Свой заголовок окна: иконка, название, свернуть/развернуть/закрыть."""

    def __init__(self, win):
        super().__init__(win)
        self.win = win
        self.setObjectName("titlebar")
        self.setFixedHeight(38)
        self._drag_pos = None

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 0, 6, 0)
        lay.setSpacing(8)

        if ICON_PATH.exists():
            icon = QLabel()
            icon.setPixmap(QPixmap(str(ICON_PATH)).scaled(
                20, 20, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            lay.addWidget(icon)

        name = QLabel("bomjvoice")
        name.setObjectName("titleName")
        lay.addWidget(name)
        lay.addStretch(1)

        btn_min = QPushButton("—")
        btn_min.setProperty("titleBtn", True)
        btn_min.setToolTip(tr("Свернуть"))
        btn_min.clicked.connect(win.showMinimized)
        lay.addWidget(btn_min)

        btn_max = QPushButton("▢")
        btn_max.setProperty("titleBtn", True)
        btn_max.setToolTip(tr("Развернуть / восстановить"))
        btn_max.clicked.connect(win.toggle_maximized)
        lay.addWidget(btn_max)

        btn_close = QPushButton("✕")
        btn_close.setProperty("closeBtn", True)
        btn_close.setToolTip(tr("Закрыть"))
        btn_close.clicked.connect(win.close)
        lay.addWidget(btn_close)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.win.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & Qt.LeftButton:
            if self.win.is_maximized:
                self.win.toggle_maximized()
            self.win.move(event.globalPosition().toPoint() - self._drag_pos)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.win.toggle_maximized()
        super().mouseDoubleClickEvent(event)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("bomjvoice")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.resize(880, 600)
        self.setMinimumSize(760, 560)
        self.is_maximized = False
        self._normal_geo = None
        self._resizing = False
        self._resize_edges = frozenset()
        self._resize_start_geo = None
        self._resize_start_pos = None
        self._resize_cursor = False
        QApplication.instance().installEventFilter(self)
        if ICON_PATH.exists():
            self.setWindowIcon(QIcon(str(ICON_PATH)))

        self.settings = Settings()
        set_lang(self.settings.get("app_language"))
        self.history = History()
        self.tts = TTSEngine(self.settings)
        self.hotkeys = GlobalHotkeys()
        self.overlay = None
        self._speak_gen = 0   # поколение озвучки: новое сообщение прерывает старое
        self._last_speak = ("", 0.0)
        self._speak_active = {}  # текст -> поколение: что сейчас синтезируется/играет

        self.bus = Bus()
        self.bus.refresh_history.connect(self._on_history_dirty)
        self.bus.refresh_voices.connect(self._fill_voices)
        self.bus.status.connect(lambda m: self.statusBar().showMessage(m, 6000))
        self.bus.speak_text.connect(self.speak)
        self.bus.speak_bind.connect(lambda t: self.speak(t, use_cache=True))
        self.bus.toggle_overlay.connect(self.toggle_overlay)
        self.bus.driver_exe_ready.connect(self._run_driver_installer)

        # ВАЖНО: стили применяем ДО построения интерфейса. Иначе строки
        # списков (голоса/история) считают свои размеры без стилей и
        # кнопки на них выглядят маленькими до первого клика.
        self._apply_theme()
        self._build_ui()
        self._restart_hotkeys()
        self._check_environment()
        grip = QSizeGrip(self)
        self.statusBar().addPermanentWidget(grip)
        QTimer.singleShot(300, self._check_driver_on_start)
        QTimer.singleShot(600, self._warm_up_overlay)

    def _warm_up_overlay(self):
        """Создаёт нативное окно оверлея заранее (невидимый показ/скрытие) —
        тогда первый вызов по Alt+V открывается мгновенно, без лага."""
        import os
        if not self.settings.get("overlay_enabled"):
            return
        if QApplication.platformName() == "offscreen" or os.environ.get("BOMJVOICE_NO_DIALOGS"):
            return
        if self.overlay is None:
            self.overlay = Overlay(on_submit=self.speak)
            theme = self.settings.get("theme")
            self.overlay.set_theme(THEME_PALETTES.get(theme, THEME_PALETTES["dark"]), key=theme)
        self.overlay.setWindowOpacity(0.0)
        self.overlay.dimmer.setWindowOpacity(0.0)
        self.overlay.show_overlay()
        self.overlay.hide()
        self.overlay.setWindowOpacity(1.0)
        self.overlay.dimmer.setWindowOpacity(type(self.overlay.dimmer).OPACITY)
        self.activateWindow()  # вернуть фокус главному окну

    # ---------- свой заголовок ----------
    def toggle_maximized(self):
        if self.is_maximized:
            if self._normal_geo is not None:
                self.setGeometry(self._normal_geo)
            self.is_maximized = False
        else:
            self._normal_geo = self.geometry()
            self.setGeometry(QApplication.primaryScreen().availableGeometry())
            self.is_maximized = True

    # ---------- растягивание окна за края/углы ----------
    _RESIZE_MARGIN = 6

    def _resize_edges_at(self, pos):
        m = self._RESIZE_MARGIN
        r = self.rect()
        edges = set()
        if pos.x() <= m:
            edges.add("l")
        if pos.x() >= r.width() - m:
            edges.add("r")
        if pos.y() <= m:
            edges.add("t")
        if pos.y() >= r.height() - m:
            edges.add("b")
        return frozenset(edges)

    @staticmethod
    def _cursor_for(edges):
        if edges in (frozenset({"t", "l"}), frozenset({"b", "r"})):
            return Qt.SizeFDiagCursor
        if edges in (frozenset({"t", "r"}), frozenset({"b", "l"})):
            return Qt.SizeBDiagCursor
        if edges & {"l", "r"}:
            return Qt.SizeHorCursor
        if edges & {"t", "b"}:
            return Qt.SizeVerCursor
        return None

    def _set_resize_cursor(self, shape):
        app = QApplication.instance()
        if shape is None:
            if self._resize_cursor:
                app.restoreOverrideCursor()
                self._resize_cursor = False
        elif self._resize_cursor:
            app.changeOverrideCursor(shape)
        else:
            app.setOverrideCursor(shape)
            self._resize_cursor = True

    def _apply_resize(self, gpos):
        d = gpos - self._resize_start_pos
        g = QRect(self._resize_start_geo)
        e = self._resize_edges
        if "l" in e:
            g.setLeft(g.left() + d.x())
        if "r" in e:
            g.setRight(g.right() + d.x())
        if "t" in e:
            g.setTop(g.top() + d.y())
        if "b" in e:
            g.setBottom(g.bottom() + d.y())
        min_w, min_h = self.minimumWidth(), self.minimumHeight()
        if g.width() < min_w:
            if "l" in e:
                g.setLeft(g.right() - min_w + 1)
            else:
                g.setWidth(min_w)
        if g.height() < min_h:
            if "t" in e:
                g.setTop(g.bottom() - min_h + 1)
            else:
                g.setHeight(min_h)
        self.setGeometry(g)

    def eventFilter(self, obj, event):
        t = event.type()
        for lst, key in ((getattr(self, "history_list", None), "_hist_w"),
                         (getattr(self, "voices_list", None), "_voices_w")):
            if lst is not None and obj is lst.viewport() and t == QEvent.Resize:
                w = obj.width()
                if w and w != getattr(self, key, 0):
                    setattr(self, key, w)
                    (self._fill_history if lst is self.history_list else self._fill_voices)()
        if obj.isWidgetType() and obj.window() is self and not self.is_maximized:
            if t == QEvent.MouseMove:
                gpos = event.globalPosition().toPoint()
                if self._resizing:
                    self._apply_resize(gpos)
                    return True
                self._set_resize_cursor(
                    self._cursor_for(self._resize_edges_at(self.mapFromGlobal(gpos))))
            elif t == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                edges = self._resize_edges_at(self.mapFromGlobal(event.globalPosition().toPoint()))
                if edges:
                    self._resizing = True
                    self._resize_edges = edges
                    self._resize_start_geo = QRect(self.geometry())
                    self._resize_start_pos = event.globalPosition().toPoint()
                    return True
            elif t == QEvent.MouseButtonRelease and self._resizing:
                self._resizing = False
                self._set_resize_cursor(None)
                return True
            elif t == QEvent.Leave and obj is self:
                self._set_resize_cursor(None)
        return super().eventFilter(obj, event)

    # ---------- UI ----------
    def _build_ui(self):
        central = QWidget()
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.titlebar = TitleBar(self)
        outer.addWidget(self.titlebar)

        body = QWidget()
        root = QHBoxLayout(body)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # --- боковая панель ---
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(120)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(10, 16, 10, 12)
        side.setSpacing(5)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_buttons = []
        for i, title in enumerate([tr("Главный"), tr("История"), tr("Голос"), tr("Настройки")]):
            btn = QToolButton()
            btn.setText(title)
            btn.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            btn.setIconSize(QSize(22, 22))
            btn.setProperty("nav", True)
            btn.setCheckable(True)
            btn.setFixedHeight(58)
            btn.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed))
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _c=False, idx=i: self.stack.setCurrentIndex(idx))
            btn.toggled.connect(lambda _c: self._refresh_nav_icons())
            self.nav_group.addButton(btn, i)
            side.addWidget(btn)
            self.nav_buttons.append(btn)
        side.addStretch(1)

        # --- страницы ---
        self.stack = QStackedWidget()
        self.stack.setObjectName("content")
        self._build_main_page()
        self._build_history_page()
        self._build_voices_page()
        self._build_settings_page()

        root.addWidget(sidebar)
        root.addWidget(self.stack, 1)
        outer.addWidget(body, 1)
        self.setCentralWidget(central)

        # чтобы курсор менялся у краёв окна ещё до нажатия
        self.setMouseTracking(True)
        for _w in (central, body, sidebar, self.stack):
            _w.setMouseTracking(True)

        self.nav_buttons[0].setChecked(True)
        self.stack.setCurrentIndex(0)
        self.stack.currentChanged.connect(self._on_page_changed)
        self.statusBar().showMessage(tr("Готово. Alt+V — оверлей."))

    @staticmethod
    def _page():
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(24, 22, 24, 20)
        lay.setSpacing(10)
        return w, lay

    @staticmethod
    def _title(text):
        t = QLabel(text)
        f = t.font()
        f.setPointSize(16)
        f.setBold(True)
        t.setFont(f)
        return t

    def _build_main_page(self):
        w, lay = self._page()
        lay.addWidget(self._title(tr("Что сказать?")))
        hint = QLabel(tr("Текст прозвучит в выбранное устройство — например, в виртуальный микрофон."))
        hint.setProperty("dim", True)
        lay.addWidget(hint)
        self.input = SpeakInput(self._speak_from_input)
        lay.addWidget(self.input, 1)
        btn = QPushButton(tr("Озвучить  (Enter)"))
        btn.clicked.connect(self._speak_from_input)
        lay.addWidget(btn)
        self.stack.addWidget(w)

    def _build_history_page(self):
        w, lay = self._page()
        lay.addWidget(self._title(tr("История")))
        self.history_list = QListWidget()
        self.history_list.setSelectionMode(QAbstractItemView.NoSelection)
        self.history_list.viewport().installEventFilter(self)
        clear_btn = QPushButton(tr("Очистить историю"))
        clear_btn.setProperty("secondary", True)
        clear_btn.clicked.connect(self._clear_history)
        lay.addWidget(self.history_list, 1)
        lay.addWidget(clear_btn)
        self.stack.addWidget(w)
        self._fill_history()

    def _build_voices_page(self):
        w, lay = self._page()
        lay.addWidget(self._title(tr("Голос")))
        # крупная строка с текущим выбранным голосом
        self.current_voice_label = QLabel("")
        f = self.current_voice_label.font()
        f.setPointSize(15)
        f.setBold(True)
        self.current_voice_label.setFont(f)
        lay.addWidget(self.current_voice_label)
        hint = QLabel(tr("Включите голос кнопкой справа — активен только один. "
                         "Новые SAPI-голоса, установленные в Windows, появляются здесь сами."))
        hint.setProperty("dim", True)
        hint.setWordWrap(True)
        lay.addWidget(hint)
        self.voices_list = QListWidget()
        self.voices_list.setSelectionMode(QAbstractItemView.NoSelection)
        self.voices_list.viewport().installEventFilter(self)
        lay.addWidget(self.voices_list, 1)
        # кнопка видна, только если подходящих голосов в системе нет
        self.install_voices_btn = QPushButton(tr("Установить голоса (русские / английские)"))
        self.install_voices_btn.clicked.connect(self._install_voices_dialog)
        self.install_voices_btn.setVisible(False)
        lay.addWidget(self.install_voices_btn)
        self.stack.addWidget(w)
        self._fill_voices()

    def _build_settings_page(self):
        outer = QWidget()
        outer_lay = QVBoxLayout(outer)
        outer_lay.setContentsMargins(0, 0, 0, 0)
        outer_lay.setSpacing(0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        w, lay = self._page()
        scroll.setWidget(w)
        outer_lay.addWidget(scroll)
        lay.addWidget(self._title(tr("Настройки")))

        lay.addWidget(QLabel(tr("Язык интерфейса:")))
        self.lang_combo = QComboBox()
        self.lang_combo.addItem("Русский", "ru")
        self.lang_combo.addItem("English", "en")
        cur = self.lang_combo.findData(self.settings.get("app_language"))
        self.lang_combo.setCurrentIndex(max(0, cur))
        self.lang_combo.currentIndexChanged.connect(self._language_changed)
        lay.addWidget(self.lang_combo)

        lay.addWidget(QLabel(tr("Тема приложения:")))
        self.theme_combo = QComboBox()
        for key, label in THEMES:
            self.theme_combo.addItem(tr(label), key)
        cur = self.theme_combo.findData(self.settings.get("theme"))
        self.theme_combo.setCurrentIndex(max(0, cur))
        self.theme_combo.currentIndexChanged.connect(self._theme_changed)
        lay.addWidget(self.theme_combo)

        lay.addWidget(QLabel(tr("Виртуальный микрофон:")))
        self.cable_label = QLabel("")
        lay.addWidget(self.cable_label)

        self.mirror_check = QCheckBox(tr("Дублировать звук в наушники (слышно и вам, и собеседнику)"))
        self.mirror_check.setChecked(self.settings.get("mirror_output"))
        self.mirror_check.toggled.connect(lambda v: self.settings.set("mirror_output", v))
        lay.addWidget(self.mirror_check)

        self.volume_label = QLabel()
        lay.addWidget(self.volume_label)
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 200)
        self.volume_slider.setValue(int(self.settings.get("cable_volume")))
        self.volume_slider.valueChanged.connect(self._volume_changed)
        lay.addWidget(self.volume_slider)
        self._update_volume_label()

        self.overlay_check = QCheckBox(tr("Оверлей по Alt+V"))
        self.overlay_check.setChecked(self.settings.get("overlay_enabled"))
        self.overlay_check.toggled.connect(lambda v: (self.settings.set("overlay_enabled", v), self._restart_hotkeys()))
        lay.addWidget(self.overlay_check)

        lay.addSpacing(8)
        binds_title = QLabel(tr("Свои горячие клавиши — по нажатию бинда текст озвучится:"))
        binds_title.setProperty("dim", True)
        lay.addWidget(binds_title)
        self.binds_list = QListWidget()
        self.binds_list.setFixedHeight(120)
        lay.addWidget(self.binds_list)
        bind_row = QHBoxLayout()
        bind_row.setSpacing(8)
        self.bind_text = QLineEdit()
        self.bind_text.setPlaceholderText(tr("Текст, который озвучить…"))
        self.bind_key = QKeySequenceEdit()
        self.bind_key.setFixedWidth(180)
        self.bind_key.setToolTip(tr("Кликните и нажмите комбинацию клавиш"))
        bind_add = QPushButton(tr("Добавить"))
        bind_add.clicked.connect(self._add_bind)
        bind_row.addWidget(self.bind_text, 1)
        bind_row.addWidget(self.bind_key)
        bind_row.addWidget(bind_add)
        lay.addLayout(bind_row)
        self._fill_binds()

        self.speed_label = QLabel()
        lay.addWidget(self.speed_label)
        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setRange(50, 200)
        self.speed_slider.setValue(int(self.settings.get("length_scale") * 100))
        self.speed_slider.valueChanged.connect(self._update_sound_labels)
        lay.addWidget(self.speed_slider)

        apply_btn = QPushButton(tr("Применить"))
        apply_btn.clicked.connect(self._apply_sound_settings)
        lay.addWidget(apply_btn)
        self._update_sound_labels()
        lay.addStretch(1)

        version_label = QLabel(
            tr("Версия: v%s") % __version__ + ' · <a href="https://github.com/godtick/bomjvoice" '
            'style="color: #3d6fd6;">github.com/godtick/bomjvoice</a>')
        version_label.setOpenExternalLinks(True)
        version_label.setProperty("dim", True)
        lay.addWidget(version_label)

        # колесо мыши над комбо/ползунками прокручивает страницу,
        # а не меняет их значения
        self._wheel_guard = _WheelToScroll(scroll.viewport())
        for cls in (QComboBox, QSlider, QKeySequenceEdit):
            for wdg in w.findChildren(cls):
                wdg.installEventFilter(self._wheel_guard)

        self.stack.addWidget(outer)

    def _apply_theme(self):
        palette = THEME_PALETTES.get(self.settings.get("theme"), THEME_PALETTES["dark"])
        QApplication.instance().setStyleSheet(build_stylesheet(self.settings.get("theme")))
        self._refresh_nav_icons()
        if self.overlay is not None:
            try:
                self.overlay.set_theme(palette, key=self.settings.get("theme"))
            except RuntimeError:
                self.overlay = None

    def _refresh_nav_icons(self):
        """Перекрашивает иконки меню: активная — белая, остальные — цветом темы."""
        if not getattr(self, "nav_buttons", None):
            return  # тема применяется до построения интерфейса
        palette = THEME_PALETTES.get(self.settings.get("theme"), THEME_PALETTES["dark"])
        for i, btn in enumerate(self.nav_buttons):
            color = "#ffffff" if btn.isChecked() else palette["dim"]
            btn.setIcon(QIcon(render_icon(NAV_ICONS[i], color)))

    # ---------- действия ----------
    def _speak_from_input(self):
        text = self.input.toPlainText().strip()
        if not text:
            return
        self.input.clear()
        self.speak(text)

    def speak(self, text, voice_id=None, record=True, use_cache=False):
        """Озвучивает текст. Новое сообщение прерывает предыдущее.
        record=False — не добавлять в историю (кнопка «Повторить»).
        use_cache=True — кэшировать wav (бинды: один и тот же текст
        тем же голосом синтезируется один раз)."""
        if not text:
            return
        # защита от двойного срабатывания (дубль сигнала/хоткея): тот же
        # текст не озвучиваем, пока предыдущий такой же ещё играет/синтезируется.
        # Важно: если прошлое воспроизведение уже прервано или закончено,
        # повторная отправка ТОГО ЖЕ текста обязана сработать.
        # Бинды — исключение: повторное нажатие бинда (даже того же самого)
        # прерывает звук и запускает его заново.
        if text in self._speak_active and not use_cache:
            return
        self._speak_active[text] = self._speak_gen + 1
        self._last_speak = (text, time.time())
        # новая озвучка прерывает предыдущую: старый поток по поколению
        # поймёт, что его отменили, и не станет играть поверх нового
        self._speak_gen += 1
        gen = self._speak_gen
        voice_id = voice_id or self.settings.get("voice")
        device = self.settings.get("device")
        engine = self.tts
        bus = self.bus

        def work():
            try:
                # остановка прежнего звука — в рабочем потоке: PortAudio
                # может блокироваться на stop/close, а GUI не должен ждать
                audio_out.stop_playing()
                if use_cache:
                    cache_dir = CACHE_DIR / "binds"
                    cache_dir.mkdir(parents=True, exist_ok=True)
                    import hashlib
                    key_src = "%s|%s|%s" % (voice_id,
                                            self.settings.get("length_scale"), text)
                    wav_path = cache_dir / (hashlib.md5(
                        key_src.encode("utf-8")).hexdigest() + ".wav")
                    if not wav_path.exists():
                        bus.status.emit(tr("Синтез речи…"))
                        engine.synthesize(text, wav_path, voice_id)
                else:
                    wav_path = CACHE_DIR / ("say_%d.wav" % int(time.time() * 1000))
                    bus.status.emit(tr("Синтез речи…"))
                    engine.synthesize(text, wav_path, voice_id)
                if gen != self._speak_gen:
                    return  # прервано более новым сообщением
                bus.status.emit(tr("Воспроизведение…"))
                audio_out.play_wav(wav_path, device,
                                   mirror_to_default=self.settings.get("mirror_output"),
                                   device_gain=self.settings.get("cable_volume") / 100.0)
                if gen != self._speak_gen:
                    return  # прервано во время воспроизведения
                if record:
                    self.history.add(text, voice_id)
                    bus.refresh_history.emit()
                bus.status.emit(tr("Готово."))
            except Exception as e:
                if gen == self._speak_gen:
                    bus.status.emit(tr("Ошибка: ") + str(e))
            finally:
                # снимаем пометку, только если это наше поколение —
                # перезапущенный бинд не должен гасить сам себя
                if self._speak_active.get(text) == gen:
                    self._speak_active.pop(text, None)

        threading.Thread(target=work, daemon=True).start()

    def _on_history_dirty(self):
        """История поменялась. Перестройка списка — дорогая (сотни виджетов),
        поэтому делаем её только когда вкладка «История» открыта."""
        self._history_dirty = True
        if getattr(self, "stack", None) is not None and self.stack.currentIndex() == 1:
            self._fill_history()
            self._history_dirty = False

    def _on_page_changed(self, idx):
        if idx == 1 and getattr(self, "_history_dirty", False):
            self._fill_history()
            self._history_dirty = False

    def _fill_history(self):
        # защита от вложенного вызова (см. _fill_voices)
        if getattr(self, "_filling_history", False):
            return
        self._filling_history = True
        try:
            self._fill_history_inner()
        finally:
            self._filling_history = False

    def _fill_history_inner(self):
        self.history_list.clear()
        now = time.localtime()
        for _id, text, voice, ts in self.history.all():
            lt = time.localtime(ts)
            same_day = (lt.tm_year, lt.tm_yday) == (now.tm_year, now.tm_yday)
            item = QListWidgetItem()
            row = QWidget()
            h = QHBoxLayout(row)
            h.setContentsMargins(6, 2, 6, 2)
            time_label = QLabel(time.strftime("%H:%M" if same_day else "%d.%m %H:%M", lt))
            time_label.setProperty("dim", True)
            time_label.setFixedWidth(82 if not same_day else 46)
            time_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            label = QLabel(text[:120] + ("…" if len(text) > 120 else ""))
            label.setWordWrap(True)
            btn = QPushButton(tr("Повторить"))
            # повторяем текущим выбранным голосом, а не тем, которым озвучивали раньше
            btn.clicked.connect(lambda _c=False, t=text: self.speak(t, None, record=False))
            h.addWidget(time_label)
            h.addWidget(label, 1)
            h.addWidget(btn)
            hint = row.sizeHint()
            vw = self.history_list.viewport().width() - 8
            if vw > 50:
                hint.setWidth(vw)
            item.setSizeHint(hint)
            self.history_list.addItem(item)
            self.history_list.setItemWidget(item, row)

    def _clear_history(self):
        self.history.clear()
        self._fill_history()

    def _fill_voices(self):
        # защита от вложенного вызова: добавление строк может вызвать
        # Resize viewport -> eventFilter -> _fill_voices повторно, и тогда
        # clear() внутри удалит items, с которыми работает внешний вызов
        if getattr(self, "_filling_voices", False):
            return
        self._filling_voices = True
        try:
            self._fill_voices_inner()
        finally:
            self._filling_voices = False

    def _fill_voices_inner(self):
        self.voices_list.clear()
        current = self.settings.get("voice")
        voices = self.tts.voices()
        for v in voices:
            active = v["id"] == current
            item = QListWidgetItem()
            row = QWidget()
            h = QHBoxLayout(row)
            h.setContentsMargins(6, 2, 6, 2)
            label = QLabel(v["label"])
            label.setWordWrap(False)
            btn = QPushButton(tr("Включён ✓") if active else tr("Включить"))
            btn.setProperty("secondary", not active)
            btn.setEnabled(not active)
            btn.clicked.connect(lambda _c=False, vid=v["id"]: self._enable_voice(vid))
            h.addWidget(label, 1)
            h.addWidget(btn)
            hint = row.sizeHint()
            vw = self.voices_list.viewport().width() - 8
            if vw > 50:
                hint.setWidth(vw)
            item.setSizeHint(hint)
            self.voices_list.addItem(item)
            self.voices_list.setItemWidget(item, row)
        # крупная надпись сверху: какой голос сейчас выбран
        name = next((v["label"] for v in voices if v["id"] == current), None)
        if name is None and voices:
            name = next((v["label"] for v in voices
                         if v["id"] == self.tts._default_voice_id()), voices[0]["label"])
        self.current_voice_label.setText(
            tr("Сейчас выбран: %s") % name if name else tr("Голоса не найдены"))
        # кнопка установки появляется, только если голосов совсем нет
        btn = getattr(self, "install_voices_btn", None)
        if btn is not None:
            btn.setEnabled(True)
            btn.setVisible(not voices)

    def _install_voices_dialog(self):
        """Выбор пакета голосов: русские или английские."""
        box = QMessageBox(self)
        box.setWindowTitle(tr("Установка голосов"))
        box.setText(tr("Какие голоса установить?"))
        btn_ru = box.addButton(tr("Русские"), QMessageBox.AcceptRole)
        btn_en = box.addButton("English", QMessageBox.AcceptRole)
        box.addButton(tr("Отмена"), QMessageBox.RejectRole)
        box.exec()
        clicked = box.clickedButton()
        if clicked is btn_ru:
            self._install_voice_pack("ru")
        elif clicked is btn_en:
            self._install_voice_pack("en")

    def _install_voice_pack(self, lang):
        """Фоновая установка голосового пакета с прогрессом в статус-баре."""
        self.install_voices_btn.setEnabled(False)
        bus = self.bus

        def work():
            try:
                ok = voices_setup.install_pack(
                    lang, progress_cb=lambda t: bus.status.emit(t))
                if ok:
                    bus.status.emit(tr("Голоса установлены."))
                else:
                    bus.status.emit(tr("Установка голосов завершилась с ошибками."))
            except Exception as e:
                bus.status.emit(tr("Ошибка: ") + str(e))
            finally:
                bus.refresh_voices.emit()

        threading.Thread(target=work, daemon=True).start()

    def _enable_voice(self, voice_id):
        """Делает голос активным; остальные кнопки снова становятся «Включить».
        Перезаполнение списка отложено: clear() удаляет саму нажатую кнопку,
        а мы ещё внутри её сигнала — синхронный вызов ронял приложение."""
        self.settings.set("voice", voice_id)
        QTimer.singleShot(0, self._fill_voices)
        self.statusBar().showMessage(tr("Голос включён"), 4000)

    def _theme_changed(self, idx):
        self.settings.set("theme", self.theme_combo.itemData(idx) or "dark")
        self._apply_theme()

    def _language_changed(self, idx):
        code = self.lang_combo.itemData(idx) or "ru"
        self.settings.set("app_language", code)
        set_lang(code)
        if self.overlay is not None:
            try:
                self.overlay.close()
            except RuntimeError:
                pass
            self.overlay = None
        self._rebuild_ui()

    def _rebuild_ui(self):
        """Пересоздаёт весь интерфейс (применение языка) с сохранением страницы."""
        page = self.stack.currentIndex()
        old = self.takeCentralWidget()
        if old is not None:
            old.deleteLater()
        self._install_btn = None
        self._build_ui()
        self._check_environment()
        self._apply_theme()
        page = min(page, self.stack.count() - 1)
        self.stack.setCurrentIndex(page)
        self.nav_buttons[page].setChecked(True)

    def _update_volume_label(self):
        self.volume_label.setText(
            tr("Громкость в микрофон (VB-CABLE): %d%%") % self.volume_slider.value())

    def _volume_changed(self, value):
        self._update_volume_label()
        self.settings.set("cable_volume", value)

    def _update_sound_labels(self):
        self.speed_label.setText(
            tr("Скорость речи: %.2f  (0.5 — быстро, 2.0 — медленно)")
            % (self.speed_slider.value() / 100.0))

    def _apply_sound_settings(self):
        self.settings.set("length_scale", self.speed_slider.value() / 100.0)
        self.bus.status.emit(tr("Настройки голоса применены."))

    # ---------- свои горячие клавиши (текст -> озвучка) ----------
    @staticmethod
    def _combo_label(combo):
        return " + ".join(p.capitalize() for p in combo.split("+") if p)

    def _fill_binds(self):
        self.binds_list.clear()
        for i, b in enumerate(self.settings.get("binds") or []):
            item = QListWidgetItem()
            row = QWidget()
            h = QHBoxLayout(row)
            h.setContentsMargins(6, 2, 6, 2)
            label = QLabel("%s  →  %s" % (self._combo_label(b.get("combo", "")),
                                          b.get("text", "")[:80]))
            label.setWordWrap(False)
            btn = QPushButton("✕")
            btn.setProperty("secondary", True)
            btn.setProperty("compact", True)
            btn.setToolTip(tr("Удалить бинд"))
            btn.clicked.connect(lambda _c=False, idx=i: self._remove_bind(idx))
            h.addWidget(label, 1)
            h.addWidget(btn)
            item.setSizeHint(row.sizeHint())
            self.binds_list.addItem(item)
            self.binds_list.setItemWidget(item, row)

    def _add_bind(self):
        text = self.bind_text.text().strip()
        combo = self.bind_key.keySequence().toString().strip().strip("+").lower()
        if not text:
            self.bus.status.emit(tr("Введите текст для бинда."))
            return
        if not combo:
            self.bus.status.emit(tr("Нажмите комбинацию клавиш в поле бинда."))
            return
        keys = parse_combo(combo)
        if not any(k not in _SPECIAL_VALUES for k in keys):
            self.bus.status.emit(tr("В комбинации должна быть обычная клавиша, не только Ctrl/Alt/Shift."))
            return
        if combo == "<alt>+v":
            self.bus.status.emit(tr("Эта комбинация занята оверлеем."))
            return
        binds = list(self.settings.get("binds") or [])
        if any(b.get("combo") == combo for b in binds):
            self.bus.status.emit(tr("Такой бинд уже существует."))
            return
        binds.append({"text": text, "combo": combo})
        self.settings.set("binds", binds)
        self.bind_text.clear()
        self.bind_key.clear()
        self._fill_binds()
        self._restart_hotkeys()
        self.bus.status.emit(tr("Бинд добавлен: %s") % self._combo_label(combo))

    def _remove_bind(self, idx):
        binds = list(self.settings.get("binds") or [])
        if 0 <= idx < len(binds):
            binds.pop(idx)
            self.settings.set("binds", binds)
            # отложено: кнопка «✕», которую нажали, удаляется в _fill_binds
            QTimer.singleShot(0, self._fill_binds)
            self._restart_hotkeys()

    # ---------- VB-CABLE ----------
    def _auto_select_cable(self):
        """Сам перехватывает виртуальный микрофон: звук всегда направляется
        в «CABLE Input» (конец кабеля, куда играют программы; дальше Windows
        сама отдаёт его как микрофон «CABLE Output» в Discord и т.п.).
        Выбора устройства нет — программа находит кабель сама."""
        idx = audio_out.find_output_device("CABLE Input")
        if idx is None:
            idx = audio_out.find_output_device("CABLE")
        if idx is not None:
            name = dict(audio_out.output_devices())[idx]
            self.settings.set("device", name)
        else:
            self.settings.set("device", "")

    def _cable_status_text(self):
        if driver.is_cable_installed():
            return tr("VB-CABLE: найден ✔ — звук сам идёт в виртуальный микрофон.")
        return tr("VB-CABLE: не найден ⚠ — звук пойдёт в динамики. "
                  "Нажмите кнопку ниже, чтобы установить драйвер.")

    def _check_environment(self):
        self._auto_select_cable()
        self.cable_label.setText(self._cable_status_text())
        if not driver.is_cable_installed() and getattr(self, "_install_btn", None) is None:
            install_btn = QPushButton(tr("Установить виртуальный микрофон (VB-CABLE)"))
            install_btn.clicked.connect(self._install_driver)
            self.cable_label.parentWidget().layout().insertWidget(
                self.cable_label.parentWidget().layout().indexOf(self.cable_label) + 1, install_btn)
            self._install_btn = install_btn

    def _check_driver_on_start(self):
        """Проверка зависимостей при запуске (как в Discord): если чего-то
        не хватает — ставим сами, без вопросов. Голоса сюда не входят:
        их пользователь ставит кнопкой на вкладке «Голос»."""
        import os
        if QApplication.platformName() == "offscreen" or os.environ.get("BOMJVOICE_NO_DIALOGS"):
            return
        if driver.is_cable_installed():
            return
        # VB-CABLE не найден — тихо скачиваем и устанавливаем
        self.bus.status.emit(tr("Проверка зависимостей: не найден VB-CABLE, устанавливаю…"))
        self._install_driver()

    def _install_driver(self):
        self.bus.status.emit(tr("Подготовка установщика драйвера…"))

        def work():
            try:
                exe = driver.ensure_setup_exe()
                self.bus.driver_exe_ready.emit(exe)
            except Exception as e:
                self.bus.status.emit(tr("Не удалось подготовить драйвер: ") + str(e))

        threading.Thread(target=work, daemon=True).start()

    def _run_driver_installer(self, exe):
        try:
            driver.run_installer(exe)
            QMessageBox.information(
                self, "VB-CABLE",
                tr("Драйвер установлен. Если виртуальный микрофон не появился в списке — "
                   "перезагрузите компьютер (требуется один раз)."))
        except Exception as e:
            QMessageBox.warning(self, "VB-CABLE", tr("Установка не завершена: ") + str(e))
        finally:
            self._check_environment_refresh()

    def _check_environment_refresh(self):
        self.cable_label.setText(self._cable_status_text())
        if driver.is_cable_installed() and getattr(self, "_install_btn", None) is not None:
            self._install_btn.setVisible(False)

    # ---------- горячие клавиши / оверлей ----------
    def _restart_hotkeys(self):
        mapping = {}
        if self.settings.get("overlay_enabled"):
            mapping["<alt>+v"] = self.bus.toggle_overlay.emit
        for b in (self.settings.get("binds") or []):
            text = (b.get("text") or "").strip()
            combo = (b.get("combo") or "").strip()
            if text and combo:
                mapping[combo] = (lambda t=text: self.bus.speak_bind.emit(t))
        self.hotkeys.stop()
        if mapping:
            self.hotkeys.start(mapping)

    def toggle_overlay(self):
        if self.overlay is not None:
            try:
                # обращение к уже удалённому C++-объекту кидает RuntimeError
                self.overlay.isVisible()
            except RuntimeError:
                self.overlay = None
        if self.overlay is None:
            self.overlay = Overlay(on_submit=self.speak)
        theme = self.settings.get("theme")
        self.overlay.set_theme(THEME_PALETTES.get(theme, THEME_PALETTES["dark"]), key=theme)
        if self.overlay.isVisible():
            self.overlay.hide()
        else:
            self.overlay.show_overlay()

    def closeEvent(self, event):
        self.hotkeys.stop()
        if self.overlay is not None:
            try:
                self.overlay.close()
            except RuntimeError:
                pass  # C++-объект оверлея уже удалён
        audio_out.stop_playing()
        event.accept()


def _acquire_single_instance():
    """Разрешает только одну копию программы.

    Если запущена вторая копия, у неё свои глобальные горячие клавиши —
    из-за этого озвучка и оверлей срабатывали бы дважды. Вторая копия
    молча завершается. Возвращает handle мьютекса (держать всё время жизни).
    """
    if sys.platform != "win32":
        return None
    import ctypes
    kernel32 = ctypes.windll.kernel32
    mutex = kernel32.CreateMutexW(None, False, "Local\\bomjvoice_single_instance")
    if not mutex:
        return None
    ERROR_ALREADY_EXISTS = 183
    if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
        sys.exit(0)
    return mutex


def main():
    _single_instance_mutex = _acquire_single_instance()
    app = QApplication(sys.argv)
    app.setApplicationName("bomjvoice")
    family = None
    if FONT_PATH.exists():
        fid = QFontDatabase.addApplicationFont(str(FONT_PATH))
        fams = QFontDatabase.applicationFontFamilies(fid)
        if fams:
            family = fams[0]
    font = QFont(family or "Segoe UI Variable Text", 10)
    font.setFamilies([family or "Segoe UI Variable Text", "Segoe UI", "Inter"])
    app.setFont(font)
    if ICON_PATH.exists():
        app.setWindowIcon(QIcon(str(ICON_PATH)))
    app.installEventFilter(_HandCursor(app))
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
