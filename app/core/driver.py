"""Проверка и установка драйвера виртуального микрофона VB-CABLE.

Без него Windows физически не позволяет выводить звук «в микрофон» —
это ограничение ОС. Драйвер бесплатный (vb-audio.com), ставится один раз.

Важно: VBCABLE_Setup_x64.exe НЕ самодостаточен — рядом должны лежать
inf/sys/cat-файлы драйвера, поэтому всегда распаковываем весь Driver Pack.
После установки устройство появляется только после перезагрузки Windows.
"""
import ctypes
import urllib.request
import zipfile
from pathlib import Path

from .settings import APP_DIR
from . import audio_out

DRIVER_URLS = [
    "https://download.vb-audio.com/Download_CABLE/VBCABLE_Driver_Pack45.zip",
    "https://download.vb-audio.com/Download_CABLE/VBCABLE_Driver_Pack43.zip",
    # зеркало на случай, если сервер vb-audio недоступен/медленный
    "https://web.archive.org/web/2024id_/https://download.vb-audio.com/Download_CABLE/VBCABLE_Driver_Pack43.zip",
]
PACK_DIR = APP_DIR / "driver" / "pack"
SETUP_NAME = "VBCABLE_Setup_x64.exe"


def is_cable_installed():
    """True, если среди устройств вывода есть CABLE Input (виртуальный микрофон)."""
    return audio_out.find_output_device("CABLE") is not None


def _dir_has_full_pack(folder):
    folder = Path(folder)
    return (folder / SETUP_NAME).exists() and any(folder.glob("*.inf"))


def _find_pack_dir():
    candidates = [
        Path(__file__).resolve().parents[2] / "installer",  # рядом с проектом
        PACK_DIR,                                           # скачанный в %APPDATA%
    ]
    for d in candidates:
        if _dir_has_full_pack(d):
            return d
    return None


def _download(url, dst, cb=None):
    req = urllib.request.Request(url, headers={"User-Agent": "bomjvoice"})
    with urllib.request.urlopen(req, timeout=120) as r, open(dst, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            if cb:
                cb(done, total, dst.name)


def ensure_setup_exe(cb=None):
    """Возвращает путь к VBCABLE_Setup_x64.exe с полным набором файлов драйвера рядом."""
    found = _find_pack_dir()
    if found is not None:
        return found / SETUP_NAME
    PACK_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = PACK_DIR / "vbcable_pack.zip"
    last_err = None
    for url in DRIVER_URLS:
        try:
            _download(url, zip_path, cb)
            last_err = None
            break
        except Exception as e:
            last_err = e
    if last_err is not None:
        raise RuntimeError("Не удалось скачать драйвер: %s" % last_err)
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(PACK_DIR)
    zip_path.unlink(missing_ok=True)
    if not _dir_has_full_pack(PACK_DIR):
        raise RuntimeError("В скачанном пакете нет файлов драйвера (.inf)")
    return PACK_DIR / SETUP_NAME


def run_installer(exe_path):
    """Запускает установщик драйвера от администратора в тихом режиме (-i -h).

    Рабочая папка — папка с установщиком, там же лежат inf/sys-файлы.
    После установки требуется перезагрузка Windows.
    """
    exe_path = Path(exe_path)
    rc = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", str(exe_path), "-i -h", str(exe_path.parent), 0)
    if rc <= 32:
        raise RuntimeError("Установка отменена или нет прав администратора (код %s)" % rc)
