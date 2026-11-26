"""Перевод интерфейса. Русские строки — ключи, переводы — в EN."""

LANG = {"current": "ru"}

EN = {
    # --- общее окно ---
    "Свернуть": "Minimize",
    "Развернуть / восстановить": "Maximize / restore",
    "Закрыть": "Close",
    "Скрыть": "Hide",
    "Готово. Alt+V — оверлей.": "Ready. Alt+V — overlay.",
    "Готово.": "Done.",
    "Ошибка: ": "Error: ",

    # --- навигация ---
    "Главный": "Main",
    "История": "History",
    "Голос": "Voice",
    "Настройки": "Settings",

    # --- главная страница ---
    "Что сказать?": "What to say?",
    "Текст прозвучит в выбранное устройство — например, в виртуальный микрофон.":
        "The text will play through the selected device — e.g. a virtual microphone.",
    "Озвучить  (Enter)": "Speak  (Enter)",
    "Введите текст…": "Type text…",

    # --- история ---
    "Очистить историю": "Clear history",
    "Повторить": "Repeat",

    # --- голоса ---
    "Включите голос кнопкой справа — активен только один. "
    "Новые SAPI-голоса, установленные в Windows, появляются здесь сами.":
        "Enable a voice with the button on the right — only one is active. "
        "New SAPI voices installed in Windows appear here automatically.",
    "Включён ✓": "Enabled ✓",
    "Включить": "Enable",
    "Голос включён": "Voice enabled",
    "Сейчас выбран: %s": "Currently selected: %s",
    "Голоса не найдены": "No voices found",
    "Установить голоса (русские / английские)": "Install voices (Russian / English)",
    "Установка голосов": "Voice installation",
    "Какие голоса установить?": "Which voices to install?",
    "Русские": "Russian",
    "Отмена": "Cancel",
    "Голоса установлены.": "Voices installed.",
    "Установка голосов завершилась с ошибками.": "Voice installation finished with errors.",

    # --- настройки ---
    "Язык интерфейса:": "Interface language:",
    "Тема приложения:": "App theme:",
    "Виртуальный микрофон:": "Virtual microphone:",
    "Дублировать звук в наушники (слышно и вам, и собеседнику)":
        "Mirror audio to headphones (heard by you and the other person)",
    "Громкость в микрофон (VB-CABLE): %d%%": "Microphone volume (VB-CABLE): %d%%",
    "Оверлей по Alt+V": "Overlay on Alt+V",
    "Свои горячие клавиши — по нажатию бинда текст озвучится:":
        "Custom hotkeys — pressing the bind speaks the text:",
    "Текст, который озвучить…": "Text to speak…",
    "Кликните и нажмите комбинацию клавиш": "Click and press a key combination",
    "Добавить": "Add",
    "Применить": "Apply",
    "Скорость речи: %.2f  (0.5 — быстро, 2.0 — медленно)":
        "Speech rate: %.2f  (0.5 — fast, 2.0 — slow)",
    "Настройки голоса применены.": "Voice settings applied.",
    "Версия: v%s": "Version: v%s",

    # --- бинды ---
    "Удалить бинд": "Remove bind",
    "Введите текст для бинда.": "Enter text for the bind.",
    "Нажмите комбинацию клавиш в поле бинда.": "Press a key combination in the bind field.",
    "В комбинации должна быть обычная клавиша, не только Ctrl/Alt/Shift.":
        "The combination must include a regular key, not only Ctrl/Alt/Shift.",
    "Эта комбинация занята оверлеем.": "This combination is taken by the overlay.",
    "Такой бинд уже существует.": "This bind already exists.",
    "Бинд добавлен: %s": "Bind added: %s",

    # --- VB-CABLE / драйвер ---
    "VB-CABLE: найден ✔ — звук сам идёт в виртуальный микрофон.":
        "VB-CABLE: found ✔ — audio goes to the virtual microphone automatically.",
    "VB-CABLE: не найден ⚠ — звук пойдёт в динамики. "
    "Нажмите кнопку ниже, чтобы установить драйвер.":
        "VB-CABLE: not found ⚠ — audio will go to the speakers. "
        "Click the button below to install the driver.",
    "Установить виртуальный микрофон (VB-CABLE)": "Install virtual microphone (VB-CABLE)",
    "Виртуальный микрофон": "Virtual microphone",
    "Проверка зависимостей: не найден VB-CABLE, устанавливаю…":
        "Checking dependencies: VB-CABLE not found, installing…",
    "Подготовка установщика драйвера…": "Preparing the driver installer…",
    "Не удалось подготовить драйвер: ": "Failed to prepare the driver: ",
    "Драйвер установлен. Если виртуальный микрофон не появился в списке — "
    "перезагрузите компьютер (требуется один раз).":
        "Driver installed. If the virtual microphone did not appear in the list — "
        "restart your computer (required once).",
    "Установка не завершена: ": "Installation did not complete: ",

    # --- статусы синтеза ---
    "Синтез речи…": "Synthesizing speech…",
    "Воспроизведение…": "Playing…",

    # --- оверлей ---
    "Введите текст…  (Enter — озвучить, Esc — скрыть)":
        "Type text…  (Enter — speak, Esc — hide)",
    "Введите текст и нажмите Enter…": "Type text and press Enter…",

    # --- темы ---
    "Тёмная": "Dark",
    "Белая": "Light",
    "Чёрная": "Black",
    "Зелёная": "Green",
    "Красная": "Red",
    "Фиолетовая": "Purple",
    "Голубая": "Blue",
    "Оранжевая": "Orange",
}


def set_lang(code):
    LANG["current"] = code if code in ("ru", "en") else "ru"


def tr(text):
    if LANG["current"] == "en":
        return EN.get(text, text)
    return text
