"""Установка голосовых пакетов (русский / английский) по кнопке в приложении.

Русский пакет: голоса RHVoice (скачиваются установщики, ставятся тихо) +
IVONA 2 Maxim из комплекта ivona_setup рядом с программой (офлайн).
Английский пакет: голоса RHVoice Alan и Clb.

Официальный сайт RHVoice недоступен из РФ, поэтому установщики берутся
из архива web.archive.org (это те же оригинальные файлы rhvoice.org).
Установка требует прав администратора: все скачанные установщики
запускаются одним elevated bat-файлом — один запрос UAC на весь пакет.
"""
import ctypes
import os
import subprocess
import tempfile
import urllib.request

from .settings import APP_DIR

DL_DIR = APP_DIR / "voices"

_VOICE_URLS = {
    "ru": [
        ("RHVoice Aleksandr",
         "https://web.archive.org/web/20251120005219id_/"
         "https://rhvoice.eu-central-1.linodeobjects.com/"
         "RHVoice-voice-Russian-Aleksandr-v4.2.2010.15-setup.exe"),
        ("RHVoice Elena",
         "https://web.archive.org/web/20211109134202id_/"
         "https://rhvoice.eu-central-1.linodeobjects.com/"
         "RHVoice-voice-Russian-Elena-v4.2.2009.13-setup.exe"),
    ],
    "en": [
        ("RHVoice Alan",
         "https://web.archive.org/web/20251120005243id_/"
         "https://rhvoice.eu-central-1.linodeobjects.com/"
         "RHVoice-voice-English-Alan-v4.0.2008.15-setup.exe"),
        ("RHVoice Clb",
         "https://web.archive.org/web/20251120005308id_/"
         "https://rhvoice.eu-central-1.linodeobjects.com/"
         "RHVoice-voice-English-Clb-v4.0.2008.15-setup.exe"),
    ],
}


def _log(msg):
    try:
        import time
        APP_DIR.mkdir(parents=True, exist_ok=True)
        with open(APP_DIR / "voices_setup.log", "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (time.strftime("%H:%M:%S"), msg))
    except Exception:
        pass


def _download(url, dst, cb=None):
    req = urllib.request.Request(url, headers={"User-Agent": "bomjvoice"})
    with urllib.request.urlopen(req, timeout=300) as r, open(dst, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            if cb:
                cb(done, total)


def _run_silent_elevated(files):
    """Запускает все установщики тихо (/S) одним elevated bat — один UAC.
    Возвращает True, если bat отработал до конца (done-маркер)."""
    done = os.path.join(tempfile.gettempdir(), "bomjvoice_voices_done")
    bat = os.path.join(tempfile.gettempdir(), "bomjvoice_voices_setup.bat")
    lines = ["@echo off"]
    for f in files:
        # NSIS-установщики RHVoice: /S — тихая установка
        lines.append('start "" /wait "%s" /S' % f)
    lines.append('echo ok>"%s"' % done)
    with open(bat, "w", encoding="mbcs", errors="replace") as f:
        f.write("\r\n".join(lines) + "\r\n")
    try:
        os.remove(done)
    except OSError:
        pass
    r = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", "cmd.exe", '/c "%s"' % bat, None, 0)
    if r <= 32:
        _log("не удалось запустить установку с правами администратора (код %s)" % r)
        return False
    import time
    for _ in range(600):
        if os.path.exists(done):
            return True
        time.sleep(1)
    _log("истёк таймаут ожидания установщиков голосов")
    return False


def install_pack(lang, progress_cb=None):
    """Ставит голосовой пакет ('ru' или 'en'). Для 'ru' заодно ставит
    IVONA 2 Maxim из комплекта рядом с программой. Возвращает bool."""
    def progress(text):
        _log(text)
        if progress_cb:
            progress_cb(text)

    ok = True
    files = []
    DL_DIR.mkdir(parents=True, exist_ok=True)
    for name, url in _VOICE_URLS.get(lang, []):
        dst = DL_DIR / (name.replace(" ", "_") + "-setup.exe")
        if not dst.exists() or dst.stat().st_size < 100000:
            try:
                progress("Скачивание: %s…" % name)
                _download(url, str(dst),
                          lambda d, t, n=name: progress(
                              "Скачивание: %s — %d%%" % (n, d * 100 // t) if t else
                              "Скачивание: %s — %.1f МБ" % (n, d / 1048576)))
            except Exception as e:
                progress("Не удалось скачать %s: %s" % (name, e))
                ok = False
                continue
        files.append(str(dst))
    if files:
        progress("Установка голосов (нужны права администратора)…")
        if not _run_silent_elevated(files):
            ok = False
    if lang == "ru":
        # IVONA 2 Maxim ставится вместе с русским пакетом (из комплекта, офлайн)
        try:
            from . import ivona_setup
            if not ivona_setup.is_installed():
                progress("Установка голоса IVONA 2 Maxim…")
                if not ivona_setup.ensure_installed():
                    ok = False
        except Exception as e:
            _log("IVONA: %s" % e)
            ok = False
    progress("Готово." if ok else "Установка завершилась с ошибками.")
    return ok
