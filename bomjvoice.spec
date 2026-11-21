# -*- mode: python ; coding: utf-8 -*-
import os as _os
import sys as _sys
from PyInstaller.utils.hooks import collect_all, collect_submodules

# Git/mingw64 в PATH тащит СВОИ libssl/libcrypto, несовместимые с Python'овским
# _ssl.pyd («Не найдена указанная процедура»). Убираем их из PATH на время
# анализа и подкладываем правильные DLL из каталога Python.
_os.environ["PATH"] = _os.pathsep.join(
    p for p in _os.environ.get("PATH", "").split(_os.pathsep)
    if "mingw64" not in p.lower() and "\\git\\" not in p.lower())

_PY_DLLS = _os.path.join(_sys.base_prefix, "DLLs")

# Пакеты клонирования (torch/coqui) живут во внешнем pylibs и тянут за собой
# разные модули стандартной библиотеки (pickletools, unittest.mock и др.).
# PyInstaller про них не знает — поэтому вкладываем в exe всю stdlib,
# включая субмодули пакетов, кроме явно лишних.
_STDLIB_BLOCK = {"tkinter", "turtle", "turtledemo", "test", "idlelib",
                 "antigravity", "this", "tix"}

datas, binaries, hiddenimports = [
    ("app/ui/assets", "app/ui/assets"),
], [], []
# комплект голоса IVONA 2 Maxim для автоустановки — вкладываем в exe,
# если папка лежит рядом с проектом (её нет в репозитории: см. README)
if _os.path.isdir("ivona_setup"):
    datas.append(("ivona_setup", "ivona_setup"))
for _m in _sys.stdlib_module_names:
    if _m in _STDLIB_BLOCK:
        continue
    hiddenimports.append(_m)
    try:
        hiddenimports += collect_submodules(_m)
    except Exception:
        pass
for pkg in ("soundfile", "pynput", "PySide6", "comtypes"):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass

# выкидываем чужие OpenSSL DLL (если просочились) и кладём правильные из Python
binaries = [(s, d) for s, d in binaries
            if "mingw64" not in s.lower() and "mingw64" not in d.lower()]
for _dll in ("libssl-3-x64.dll", "libcrypto-3-x64.dll"):
    _src = _os.path.join(_PY_DLLS, _dll)
    if _os.path.exists(_src):
        binaries.append((_src, "."))

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    # Синтез — только SAPI5; нейросетевые движки (torch и ко) не нужны.
    excludes=[
        "piper",
        "huggingface_hub",
        "torch", "torchaudio", "torchgen",
        "transformers", "tokenizers", "safetensors", "sentencepiece",
        "pocket_tts", "xvibe_pocket_tts", "ruaccent",
        "einops", "sympy", "networkx", "mpmath",
        "regex", "yaml", "pyyaml",
        "pydantic", "pydantic_core", "annotated_types", "annotated_doc",
        "beartype", "typer", "rich", "click", "shellingham",
        "fastapi", "starlette", "uvicorn", "anyio", "h11",
        "razdel", "python_crfsuite", "coloredlogs", "humanfriendly",
        "pyreadline3", "typing_inspection", "opentelemetry_api",
        "protobuf", "flatbuffers",
        "requests", "urllib3", "certifi", "charset_normalizer", "idna",
        "tqdm", "filelock", "fsspec",
        "jinja2", "markupsafe",
        "mdurl", "pygments", "markdown_it", "python_multipart",
        "openvoice", "librosa", "numba", "llvmlite", "resampy",
        "wavmark", "pydub", "jieba", "mecab", "unidic_lite",
        "cn2an", "pypinyin", "eng_to_ipa", "unidecode", "inflect",
        "whisper", "whisper_timestamped", "faster_whisper", "ctranslate2",
        "av", "tiktoken", "chatterbox", "perth", "resemble_perth",
        "diffusers", "gradio", "gradio_client",
    ],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas,
    name="bomjvoice",
    debug=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,
    icon="app/ui/assets/icon.ico",
)
