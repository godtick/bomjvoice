"""Автоустановка и самовосстановление голоса IVONA 2 Maxim (SAPI5).

При запуске программы проверяет, доступен ли голос в системе. Если нет —
восстанавливает всё сам и без интернета:
1. Файлы движка берутся из папки ivona_setup рядом с программой
   (полный комплект оригинального установщика).
2. Файлы копируются в «C:\\Program Files\\NextUp-Ivona».
3. Голос регистрируется через rundll32 -> InstallVoice — ровно та команда,
   которую выполняет оригинальный установщик MSI.
4. Результат проверяется повторным запросом списка голосов SAPI.

Для записи в Program Files и HKLM нужны права администратора: если
программа запущена без них, один раз появится стандартный запрос UAC —
всё остальное происходит автоматически.
"""
import ctypes
import os
import shutil
import subprocess
import sys
import tempfile

IVONA_MARK = "IVONA 2 Maxim"          # подстрока имени голоса в SAPI
PRODUCT_CODE = "{61DBC758-EBE5-4586-B3B9-80E970A90476}"
PRODUCT_NAME = "NextUp-Ivona Maxim Russian Voice"
DLL64 = "ivona_sapi5_oem_v1_6_72_x64.dll"
DLL32 = "ivona_sapi5_oem_v1_6_72.dll"


def _log(msg):
    try:
        from .settings import APP_DIR
        import time
        APP_DIR.mkdir(parents=True, exist_ok=True)
        with open(APP_DIR / "ivona_setup.log", "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (time.strftime("%H:%M:%S"), msg))
    except Exception:
        pass


def ivona_dir():
    pf = os.environ.get("ProgramFiles", r"C:\Program Files")
    return os.path.join(pf, "NextUp-Ivona", "ivona_voices")


def _bundle_dir():
    """Где лежит комплект ivona_setup: внутри exe (релиз одним файлом),
    рядом с exe (в т.ч. dist/ivona_setup) или в корне проекта (dev-режим)."""
    if getattr(sys, "frozen", False):
        emb = os.path.join(getattr(sys, "_MEIPASS", ""), "ivona_setup")
        if os.path.isdir(emb):
            return emb
        base = os.path.dirname(sys.executable)
        candidates = [os.path.join(base, "ivona_setup")]
    else:
        base = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))))
        candidates = [os.path.join(base, "ivona_setup"),
                      os.path.join(base, "dist", "ivona_setup")]
    for p in candidates:
        if os.path.isdir(p):
            return p
    return None


def _stable_bundle(bundle):
    """Возвращает путь к комплекту в СТАБИЛЬНОМ месте.

    Если комплект лежит во временной _MEI-распаковке exe, сначала копирует
    его в %APPDATA%\\bomjvoice\\ivona_setup: _MEI-директория удаляется при
    выходе программы, и установка, запущенная в фоне, не должна от неё
    зависеть. Копирование инкрементальное (по размеру файлов) и
    возобновляемое: оборвётся — докопируется при следующем запуске."""
    mei = getattr(sys, "_MEIPASS", "") if getattr(sys, "frozen", False) else ""
    if not bundle or not mei or not os.path.abspath(
            bundle).startswith(os.path.abspath(mei)):
        return bundle
    from .settings import APP_DIR
    dst_root = APP_DIR / "ivona_setup"
    marker = dst_root / ".complete"
    if marker.is_file() and (dst_root / "ivona_voices").is_dir():
        return str(dst_root)
    src = os.path.join(bundle, "ivona_voices")
    dst = dst_root / "ivona_voices"
    _log("копирую комплект IVONA в постоянное хранилище…")
    try:
        for root, _dirs, files in os.walk(src):
            rel = os.path.relpath(root, src)
            d = str(dst) if rel == "." else os.path.join(str(dst), rel)
            os.makedirs(d, exist_ok=True)
            for name in files:
                s = os.path.join(root, name)
                t = os.path.join(d, name)
                try:
                    if (not os.path.isfile(t)
                            or os.path.getsize(t) != os.path.getsize(s)):
                        shutil.copy2(s, t)
                except OSError:
                    pass
        marker.write_text("ok", encoding="ascii")
    except OSError as e:
        _log("не удалось скопировать комплект: %s" % e)
        return None
    return str(dst_root)


def find_ivona_token():
    """TokenId голоса IVONA Maxim в SAPI или None."""
    try:
        import comtypes.client
        sp = comtypes.client.CreateObject("SAPI.SpVoice")
        tokens = sp.GetVoices()
        for i in range(tokens.Count):
            tok = tokens.Item(i)
            try:
                if IVONA_MARK.lower() in (tok.GetDescription() or "").lower():
                    return tok.Id
            except Exception:
                pass
    except Exception:
        pass
    return None


def is_installed():
    return find_ivona_token() is not None


def _reg_installed():
    """Проверка напрямую через реестр, без SAPI: SAPI кэширует список
    токенов внутри процесса и может «не видеть» свежеустановленный голос."""
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"SOFTWARE\Microsoft\Speech\Voices\Tokens") as k:
            i = 0
            while True:
                try:
                    name = winreg.EnumKey(k, i)
                except OSError:
                    break
                i += 1
                if "ivona" in name.lower():
                    return True
    except OSError:
        pass
    return False


def _register_bat(target, src_voices=None):
    """Пишет .bat, который выполняет всю установку штатным способом:
    гасит зависшие копии регистратора, копирует файлы (если задан источник)
    и регистрирует голос через rundll32 -> InstallVoice (та же команда,
    что выполняет оригинальный установщик, — видно в NextUpIvonaInstall.log).

    32-битный RegisterIvonaVoice.exe НЕ используем: 32-битные дочерние
    процессы подвисают на этой машине при запуске из нашего приложения.
    Регистрируем только x64 — программе и всем 64-битным приложениям
    (Discord и т.п.) этого достаточно."""
    done = os.path.join(tempfile.gettempdir(), "bomjvoice_ivona_done")
    ivlog = os.path.join(tempfile.gettempdir(), "NextUpIvonaInstall.log")
    dll64_path = os.path.join(target, "x64", DLL64)
    lines = [
        "@echo off",
        "taskkill /F /IM RegisterIvonaVoice.exe >nul 2>&1",
    ]
    if src_voices:
        lines.append('robocopy "%s" "%s" /E /R:1 /W:1 /NFL /NDL /NJH /NJS >nul'
                     % (src_voices, target))
    # если файлов нет — не запускаем rundll32 (он показал бы скрытый
    # диалог об ошибке и завис бы навсегда в фоновой сессии)
    lines += [
        'if not exist "%s" echo fail>"%s" & goto :eof' % (dll64_path, done),
        'cd /d "%s"' % os.path.join(target, "x64"),
        ('C:\\Windows\\System32\\rundll32.exe "%s",InstallVoice '
         '-installdir "%s" -libvoice voice_ru_maxim_x64.dll '
         '-vox vox_ru_maxim22i -lex russian.lex '
         '-mode WSAPI -vendor NextUp -vendor-desc "NextUp.com" '
         '-integration OpenSAPI -logfile "%s"') % (dll64_path, target, ivlog),
        'echo ok>"%s"' % done,
    ]
    bat = os.path.join(tempfile.gettempdir(), "bomjvoice_ivona_setup.bat")
    with open(bat, "w", encoding="mbcs", errors="replace") as f:
        f.write("\r\n".join(lines) + "\r\n")
    return bat, done


def _elevated_install(src_voices):
    """Установка через elevated cmd (один запрос UAC). Возвращает done-файл."""
    bat, done = _register_bat(ivona_dir(), src_voices)
    try:
        os.remove(done)
    except OSError:
        pass
    r = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", "cmd.exe", '/c "%s"' % bat, None, 0)
    _log("elevated ShellExecute -> %s" % r)
    return done if r > 32 else None


def _spawn_detached(bat):
    """Запускает bat через WMI Win32_Process.Create: процесс создаётся
    службой WMI, а не нами, — у него своё окружение и он не наследует
    наши описатели (иначе RegisterIvonaVoice.exe подвисает, будучи
    запущенным напрямую из нашего GUI-процесса)."""
    ps = ("Invoke-CimMethod -ClassName Win32_Process -MethodName Create "
          "-Arguments @{ CommandLine = 'cmd /c \"%s\"' } "
          "| Select-Object -ExpandProperty ReturnValue" % bat)
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                       timeout=60, stdin=subprocess.DEVNULL,
                       capture_output=True)
    out = (r.stdout or b"").decode("mbcs", "replace").strip()
    _log("WMI spawn -> %s" % out)
    return out == "0"


def _wait_done(done, seconds=300):
    import time
    for _ in range(seconds):
        if os.path.exists(done) or is_installed():
            return True
        time.sleep(1)
    return False


def ensure_installed():
    """Проверяет голос и при необходимости ставит его сам. Возвращает bool."""
    if is_installed():
        return True
    _log("голос IVONA не найден — начинаю восстановление")
    bundle = _bundle_dir()
    if not bundle:
        _log("папка ivona_setup рядом с программой не найдена")
        return False
    # комплект из временной распаковки exe перекладываем в стабильное место
    bundle = _stable_bundle(bundle)
    if not bundle:
        return False
    src_voices = os.path.join(bundle, "ivona_voices")
    if not os.path.isdir(src_voices):
        _log("в ivona_setup нет файлов голоса")
        return False

    target = ivona_dir()
    need_copy = not os.path.isfile(os.path.join(target, "x64", DLL64))
    bat, done = _register_bat(target, src_voices if need_copy else None)
    try:
        os.remove(done)
    except OSError:
        pass

    is_admin = False
    try:
        is_admin = bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        pass

    if is_admin:
        # отцеплённый запуск через WMI — безопасно и без запросов
        try:
            _spawn_detached(bat)
            # ждём появления голоса в реестре (без SAPI-кэша), до 5 минут
            import time
            for _ in range(300):
                if os.path.exists(done) or _reg_installed():
                    break
                time.sleep(1)
        except Exception as e:
            _log("WMI-установка не удалась: %s" % e)

    if not _reg_installed():
        # нет прав админа или WMI не сработал: один UAC-запрос через shell
        done2 = _elevated_install(src_voices)
        if not done2:
            _log("не удалось запустить установку с правами администратора")
            return False
        _wait_done(done2)

    ok = _reg_installed() or is_installed()
    _log("итог восстановления: %s" % ("OK" if ok else "НЕ УДАЛОСЬ"))
    return ok


def migrate_settings(settings):
    """Если в настройках остался старый голос «Максим (RVC)» (id ivona-maxim),
    переключает на настоящий голос IVONA."""
    try:
        if settings.get("voice") != "ivona-maxim":
            return
        token = find_ivona_token()
        if token:
            settings.set("voice", token)
            _log("настройка голоса переключена на настоящий IVONA Maxim")
    except Exception:
        pass
