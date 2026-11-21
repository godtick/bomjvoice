import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _selftest():
    """Скрытая самопроверка: BOMJVOICE_SELFTEST=1 — синтезирует фразу
    первым доступным SAPI5-голосом и пишет результат в
    %APPDATA%\\bomjvoice\\selftest.log.
    Нужна для проверки работы внутри собранного exe (без консоли)."""
    import time
    import traceback
    log_path = os.path.join(os.environ.get("APPDATA", "."), "bomjvoice", "selftest.log")

    def log(msg):
        with open(log_path, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (time.strftime("%H:%M:%S"), msg))

    try:
        from app.core.settings import Settings, APP_DIR
        from app.core.tts_engine import TTSEngine
        settings = Settings()
        eng = TTSEngine(settings)
        voices = eng.voices()
        log("voices: %d" % len(voices))
        if not voices:
            log("FAIL: нет ни одного SAPI5-голоса")
            return
        out = str(APP_DIR / "cache" / "_selftest.wav")
        t0 = time.time()
        # можно проверить конкретный голос: BOMJVOICE_SELFTEST_VOICE=<tokenId>
        vid = os.environ.get("BOMJVOICE_SELFTEST_VOICE") or eng._default_voice_id()
        eng.synthesize("Самопроверка синтеза речи.", out, vid)
        size = os.path.getsize(out)
        if size < 1000:
            log("FAIL: пустой звук (%d bytes)" % size)
            return
        log("OK in %.1fs voice=%s -> %s (%d bytes)"
            % (time.time() - t0, vid, out, size))
    except Exception:
        log("FAIL:\n" + traceback.format_exc())


if os.environ.get("BOMJVOICE_SELFTEST"):
    _selftest()
    sys.exit(0)

# --- голос IVONA 2 Maxim: проверяем и при необходимости восстанавливаем ---
def _ensure_ivona():
    """Фоновая автоустановка голоса IVONA Maxim (если вдруг не установлен)."""
    try:
        import threading
        from app.core.settings import Settings
        from app.core import ivona_setup
        settings = Settings()
        if ivona_setup.is_installed():
            ivona_setup.migrate_settings(settings)
            return
        # установка может занять время (копирование 200+ МБ) — в фоне
        def work():
            ivona_setup.ensure_installed()
            ivona_setup.migrate_settings(Settings())
        threading.Thread(target=work, daemon=True).start()
    except Exception:
        pass

_ensure_ivona()

from app.ui.main_window import main

if __name__ == "__main__":
    main()
