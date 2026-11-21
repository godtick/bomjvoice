from pynput import keyboard as pkb

# Модификаторы: сводим левые/правые варианты к общему виду
_MOD_ALIASES = {
    pkb.Key.ctrl_l: pkb.Key.ctrl, pkb.Key.ctrl_r: pkb.Key.ctrl,
    pkb.Key.alt_l: pkb.Key.alt, pkb.Key.alt_r: pkb.Key.alt,
    pkb.Key.shift_l: pkb.Key.shift, pkb.Key.shift_r: pkb.Key.shift,
    pkb.Key.cmd_l: pkb.Key.cmd, pkb.Key.cmd_r: pkb.Key.cmd,
}

_SPECIAL = {
    "ctrl": pkb.Key.ctrl, "ctrl_l": pkb.Key.ctrl, "ctrl_r": pkb.Key.ctrl,
    "alt": pkb.Key.alt, "alt_l": pkb.Key.alt, "alt_r": pkb.Key.alt,
    "shift": pkb.Key.shift, "shift_l": pkb.Key.shift, "shift_r": pkb.Key.shift,
    "cmd": pkb.Key.cmd, "windows": pkb.Key.cmd, "win": pkb.Key.cmd,
}

# Множество значений-модификаторов (для проверки «в комбо есть обычная клавиша»)
_SPECIAL_VALUES = frozenset(_SPECIAL.values())


def norm_key(key):
    """Нормализует клавишу для сравнения.

    Буквы/цифры приводятся к виртуальному коду (VK) физической клавиши,
    поэтому комбинации работают в любой раскладке (RU/EN) одинаково:
    физическая клавиша V даёт VK 0x56 независимо от того, что на ней «м».
    """
    if isinstance(key, pkb.KeyCode):
        if key.vk is not None:
            return ("vk", key.vk)
        if key.char:
            return ("char", key.char.lower())
        return ("char", None)
    return _MOD_ALIASES.get(key, key)


def parse_combo(combo):
    """'<ctrl>+<alt>+r' -> frozenset нормализованных клавиш."""
    parts = [p.strip().strip("<>").lower()
             for p in combo.replace(" ", "").split("+") if p.strip("<> ")]
    result = set()
    for p in parts:
        if p in _SPECIAL:
            result.add(_SPECIAL[p])
        elif len(p) == 1 and p.isprintable():
            # Буква/цифра -> VK физической клавиши (совпадает с ASCII заглавной)
            result.add(("vk", ord(p.upper())))
        else:
            result.add(getattr(pkb.Key, p, p))
    return frozenset(result)


class GlobalHotkeys:
    """Глобальные горячие клавиши. Маппинг вида {'<alt>+v': callback}.

    Срабатывает один раз на нажатие комбинации (без повторов от автоповтора
    клавиши) и не зависит от текущей раскладки клавиатуры.
    """

    def __init__(self):
        self.listener = None

    def start(self, mapping):
        self.stop()
        combos = [(parse_combo(c), cb) for c, cb in mapping.items()]
        pressed = set()

        def on_press(key):
            # Фиксируем состояние ДО добавления клавиши: срабатываем только
            # когда комбинация стала выполненной именно этим нажатием.
            was = [combo <= pressed for combo, _cb in combos]
            pressed.add(norm_key(key))
            for i, (combo, cb) in enumerate(combos):
                if not was[i] and combo <= pressed:
                    try:
                        cb()
                    except Exception:
                        pass

        def on_release(key):
            pressed.discard(norm_key(key))

        self.listener = pkb.Listener(on_press=on_press, on_release=on_release)
        self.listener.daemon = True
        self.listener.start()

    def stop(self):
        if self.listener is not None:
            try:
                self.listener.stop()
            except Exception:
                pass
            self.listener = None
