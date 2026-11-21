"""Движок синтеза речи — обычный (не нейронный) TTS через Windows SAPI5.

Работает полностью локально и офлайн. Программа видит все SAPI5-голоса,
установленные в системе (RHVoice, IVONA, Microsoft и любые другие):
если пользователь поставит ещё голоса — они сами появятся в списке.
"""
import re
import threading
from xml.sax.saxutils import escape as _xml_escape

import comtypes.client

from .settings import APP_DIR

MODELS_DIR = APP_DIR / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

SVSF_IS_XML = 8  # флаг SAPI: текст содержит XML-разметку

# Голоса, которые приложение скрывает из списка (системные/лишние).
# Совпадение — по подстроке в имени голоса или token id, без учёта регистра.
HIDDEN_VOICES = (
    "zira",         # Microsoft Zira (встроенный английский голос Windows)
    "evgeniy-eng",  # RHVoice Evgeniy-Eng (английский)
    "lyubov",       # RHVoice Lyubov
    "magda",        # RHVoice Magda
    "slt",          # RHVoice Slt (английский)
    "vitaliy-ng",   # RHVoice Vitaliy-ng
    "vitaly-ng",
)


def is_hidden_voice(label, token_id=""):
    """True, если голос в списке скрытых — его не показываем и не выбираем."""
    text = "%s %s" % (label or "", token_id or "")
    text = text.lower()
    return any(mark in text for mark in HIDDEN_VOICES)


def _text_with_pauses(text):
    """Вставляет SAPI-паузы после знаков препинания:
    точка/!/?/… — длинная пауза, запятая/;/:/тире — короткая.
    Числа вида 3,14 и 3.14 пауз не получают (рядом цифры, не пробел)."""
    esc = _xml_escape(text)
    esc = re.sub(r'([.!?…]+)(\s+|$)', r'\1<silence msec="450"/>\2', esc)
    esc = re.sub(r'([,;:—–-])(\s+)', r'\1<silence msec="200"/>\2', esc)
    return esc


class TTSEngine:
    def __init__(self, settings):
        self.settings = settings
        self._lock = threading.Lock()

    # ---------- список голосов ----------
    def voices(self):
        """Все SAPI5-голоса системы: [{"id": token_id, "type": "sapi",
        "label": имя}]. Список перечитывается каждый раз — свежие голоса
        появляются сразу после установки."""
        result = []
        try:
            sp = comtypes.client.CreateObject("SAPI.SpVoice")
            tokens = sp.GetVoices()
            for i in range(tokens.Count):
                tok = tokens.Item(i)
                label = tok.GetDescription()
                if is_hidden_voice(label, tok.Id):
                    continue  # скрытые голоса приложение не показывает
                lang = ""
                try:
                    lang = tok.GetAttribute("Language") or ""
                except Exception:
                    pass
                result.append({"id": tok.Id, "type": "sapi",
                               "label": label, "lang": lang})
        except Exception:
            pass
        return result

    def _default_voice_id(self):
        """Голос по умолчанию: первый русский, иначе первый доступный."""
        vs = self.voices()
        for v in vs:
            # 419 = ru-RU в hex-коде языка SAPI
            if (v.get("lang") or "").lower() == "419":
                return v["id"]
        return vs[0]["id"] if vs else ""

    # ---------- синтез ----------
    def synthesize(self, text, out_wav, voice_id=None):
        """Синтезирует text в wav-файл выбранным SAPI5-голосом."""
        # вызывается из фонового потока — COM нужно инициализировать в нём
        comtypes.CoInitialize()
        try:
            with self._lock:
                self._synthesize_inner(text, out_wav, voice_id)
        finally:
            comtypes.CoUninitialize()

    def _synthesize_inner(self, text, out_wav, voice_id):
        voice_id = voice_id or self.settings.get("voice")
        sp = comtypes.client.CreateObject("SAPI.SpVoice")
        tokens = sp.GetVoices()
        token = None
        if not is_hidden_voice("", voice_id or ""):
            for i in range(tokens.Count):
                tok = tokens.Item(i)
                if (tok.Id == voice_id or tok.GetDescription() == voice_id) \
                        and not is_hidden_voice(tok.GetDescription(), tok.Id):
                    token = tok
                    break
        if token is None and tokens.Count:
            # сохранённый голос пропал — молча берём голос по умолчанию
            # (первый русский, иначе просто первый)
            want = self._default_voice_id()
            for i in range(tokens.Count):
                if tokens.Item(i).Id == want:
                    token = tokens.Item(i)
                    break
            if token is None:
                # берём первый не скрытый голос
                for i in range(tokens.Count):
                    tok = tokens.Item(i)
                    if not is_hidden_voice(tok.GetDescription(), tok.Id):
                        token = tok
                        break
                if token is None:
                    token = tokens.Item(0)
            self.settings.set("voice", token.Id)
        if token is None:
            raise RuntimeError("В системе нет ни одного SAPI5-голоса.")
        sp.Voice = token
        # скорость речи: length_scale 0.5..2.0 (больше = медленнее)
        # -> SAPI rate -10..+10 (больше = быстрее)
        ls = self.settings.get("length_scale") or 1.0
        try:
            ls = float(ls)
        except Exception:
            ls = 1.0
        ls = max(0.5, min(2.0, ls))
        sp.Rate = max(-10, min(10, int(round((1.0 / ls - 1.0) * 10))))
        stream = comtypes.client.CreateObject("SAPI.SpFileStream")
        stream.Open(str(out_wav), 3)  # SSFMCreateForWrite
        try:
            sp.AudioOutputStream = stream
            try:
                # с паузами на знаках препинания (SAPI XML)
                sp.Speak(_text_with_pauses(text), SVSF_IS_XML)
            except Exception:
                # голос не понял разметку — читаем как обычный текст
                sp.Speak(text, 0)  # SVSFDefault — ждём окончания
        finally:
            stream.Close()
