import threading

import numpy as np
import sounddevice as sd
import soundfile as sf

# Порядок предпочтения звуковых API: WASAPI даёт по одной записи на
# физическое устройство с полным именем; MME/DirectSound дублируют
# одни и те же устройства и обрезают имена.
_HOSTAPI_PRIORITY = ("Windows WASAPI", "Windows DirectSound", "MME")


def _devices(channel_key):
    """Список (index, name) устройств без дублей.

    Берёт устройства только самого предпочтительного доступного host API
    (WASAPI -> DirectSound -> MME), чтобы один микрофон/наушники не
    показывались в списке по 3 раза.
    """
    devs = sd.query_devices()
    apis = sd.query_hostapis()
    by_api = {}
    for i, dev in enumerate(devs):
        if dev[channel_key] > 0:
            api = apis[dev["hostapi"]]["name"]
            by_api.setdefault(api, []).append((i, dev["name"]))
    for api in _HOSTAPI_PRIORITY:
        if by_api.get(api):
            return by_api[api]
    # неизвестные API — отдаём всё как есть
    return [(i, d["name"]) for i, d in enumerate(devs) if d[channel_key] > 0]


def output_devices():
    """Список (index, name) устройств воспроизведения."""
    return _devices("max_output_channels")


def input_devices():
    """Список (index, name) устройств записи (микрофоны)."""
    return _devices("max_input_channels")


def find_input_device(name):
    """Индекс микрофона по имени или None (устройство отключено)."""
    if not name:
        return None
    for i, dev_name in input_devices():
        if dev_name == name:
            return i
    return None


def find_output_device(substr):
    if not substr:
        return None
    for i, name in output_devices():
        if substr.lower() in name.lower():
            return i
    return None


def default_output_device():
    """Индекс устройства вывода по умолчанию (наушники/динамики) или None."""
    try:
        idx = sd.default.device[1]
    except Exception:
        return None
    if idx is None or idx < 0:
        return None
    return idx


def _resample(data, src_sr, dst_sr):
    """Линейный ресемплинг numpy (речь переносит спокойно)."""
    if src_sr == dst_sr:
        return data
    n_src = len(data)
    n_dst = max(1, int(round(n_src * dst_sr / src_sr)))
    x_src = np.arange(n_src, dtype="float64")
    x_dst = np.linspace(0.0, n_src - 1, n_dst)
    if data.ndim == 1:
        return np.interp(x_dst, x_src, data).astype("float32")
    cols = [np.interp(x_dst, x_src, data[:, c]) for c in range(data.shape[1])]
    return np.stack(cols, axis=1).astype("float32")


class _Playback:
    """Один поток воспроизведения на конкретное устройство."""

    def __init__(self, data, samplerate, device, gain=1.0):
        self.done = threading.Event()
        self._pos = 0
        self._closed = False
        self._clock = threading.Lock()  # поток закрывается ровно один раз
        if gain != 1.0:
            data = np.clip(data * gain, -1.0, 1.0).astype("float32")
        self._data = data
        channels = 1 if data.ndim == 1 else data.shape[1]
        try:
            self.stream = sd.OutputStream(
                samplerate=samplerate, channels=channels, dtype="float32",
                device=device, callback=self._cb, finished_callback=self.done.set)
        except Exception:
            # WASAPI не умеет ресемплировать сам и отвергает чужую частоту
            # (piper 22050 / xtts 24000 на кабеле 48000) — приводим заранее
            # к родной частоте устройства и открываем поток ещё раз.
            if device is not None:
                dsr = int(sd.query_devices(device)["default_samplerate"])
            else:
                dsr = 44100
            self._data = _resample(data, samplerate, dsr)
            channels = 1 if self._data.ndim == 1 else self._data.shape[1]
            self.stream = sd.OutputStream(
                samplerate=dsr, channels=channels, dtype="float32",
                device=device, callback=self._cb, finished_callback=self.done.set)

    def _cb(self, outdata, frames, _time, _status):
        n = min(frames, len(self._data) - self._pos)
        if n > 0:
            chunk = self._data[self._pos:self._pos + n]
            outdata[:n] = chunk.reshape(n, -1)
            self._pos += n
        if n < frames:
            outdata[n:] = 0
            raise sd.CallbackStop

    def start(self):
        try:
            self.stream.start()
        except Exception:
            self.done.set()

    def _close_once(self):
        with self._clock:
            if self._closed:
                return
            self._closed = True
            try:
                self.stream.stop(ignore_errors=True)
            except Exception:
                pass
            try:
                self.stream.close(ignore_errors=True)
            except Exception:
                pass

    def wait(self):
        self.done.wait()
        self._close_once()

    def stop(self):
        # останавливаем и закрываем здесь же — wait() в рабочем потоке
        # потом просто выйдет по done и не будет закрывать второй раз
        self._close_once()
        self.done.set()


_active_lock = threading.Lock()
_active = []


def stop_playing():
    with _active_lock:
        targets = list(_active)
        _active.clear()
    for pb in targets:
        pb.stop()


def is_playing():
    """Сейчас что-то звучит?"""
    with _active_lock:
        return any(not pb.done.is_set() for pb in _active)


def play_wav(path, device_substr="", mirror_to_default=True, device_gain=1.0):
    """Воспроизводит wav на выбранном устройстве.

    device_substr='CABLE' -> звук пойдет в виртуальный микрофон.
    mirror_to_default=True -> одновременно дублирует звук на устройство
    вывода по умолчанию (наушники/динамики), чтобы было слышно самому.
    device_gain -> громкость именно для выбранного устройства (1.0 = 100%).

    Остановка предыдущего воспроизведения и регистрация нового происходят
    атомарно под одним замком: прерванный поток не сможет начать играть
    поверх нового, как бы ни переплелись потоки.
    """
    data, sr = sf.read(str(path), dtype="float32")

    devices = []  # (index, gain)
    idx = find_output_device(device_substr)
    if idx is not None:
        devices.append((idx, device_gain))
    if mirror_to_default:
        default_idx = default_output_device()
        if default_idx is not None and default_idx not in [d for d, _g in devices]:
            devices.append((default_idx, 1.0))
    if not devices:
        devices.append((None, 1.0))  # системный дефолт

    with _active_lock:
        for pb in _active:
            pb.stop()
        _active.clear()
        try:
            playbacks = [_Playback(data, sr, dev, gain) for dev, gain in devices]
        except Exception:
            # выбранное устройство отвалилось — играем через устройство по умолчанию
            playbacks = [_Playback(data, sr, None)]
        _active.extend(playbacks)
        for pb in playbacks:
            pb.start()
    for pb in playbacks:
        pb.wait()
