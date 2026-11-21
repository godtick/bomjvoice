import json
import os
from pathlib import Path

APP_DIR = Path(os.environ.get("APPDATA", str(Path.home()))) / "bomjvoice"
APP_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR = APP_DIR / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

DEFAULTS = {
    "theme": "dark",            # dark | light
    "app_language": "ru",       # ru | en — язык интерфейса
    "device": "",               # имя устройства вывода (CABLE Input) — находится само
    "mirror_output": True,      # дублировать звук на устройство по умолчанию (наушники)
    "cable_volume": 100,        # громкость звука в виртуальный микрофон, % (0..200)
    "overlay_enabled": True,
    "length_scale": 1.0,        # скорость речи (0.5..2.0)
    "voice": "",                # SAPI5 token id выбранного голоса ("" = первый доступный)
    "binds": [],                # свои бинды: [{"text": "...", "combo": "ctrl+shift+1"}]
}


class Settings:
    def __init__(self):
        self.path = APP_DIR / "settings.json"
        self.data = dict(DEFAULTS)
        self.load()

    def load(self):
        if self.path.exists():
            try:
                self.data.update(json.loads(self.path.read_text(encoding="utf-8")))
            except Exception:
                pass

    def save(self):
        try:
            self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def get(self, key):
        return self.data.get(key, DEFAULTS.get(key))

    def set(self, key, value):
        self.data[key] = value
        self.save()
