"""Interface language.

The English string is the key. Anything missing from the dictionary simply stays English,
which is a readable failure rather than a blank label, and the source keeps saying what it
means without a layer of invented identifiers in between.

`ui_language` is about the interface. The language you dictate in is a separate setting -
a Russian interface is no reason to stop dictating in English.
"""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)

LANG_RUSSIAN = 0x19  # the primary language id Windows reports for Russian

_current = "en"


def system_language() -> str:
    """Russian if Windows itself is Russian, English for everything else."""
    try:
        import ctypes

        langid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        return "ru" if (langid & 0x3FF) == LANG_RUSSIAN else "en"
    except Exception:
        log.debug("could not read the system language", exc_info=True)
        return "en"


def resolve(setting: str) -> str:
    return system_language() if setting not in ("ru", "en") else setting


def set_language(setting: str) -> str:
    global _current
    _current = resolve(setting)
    return _current


def current() -> str:
    return _current


def _(text: str) -> str:
    """Translates one interface string."""
    if _current == "en":
        return text
    return RU.get(text, text)


RU = {
    # ---- tray ----
    "Starting...": "Запуск...",
    "Settings...": "Настройки...",
    "Copy last result": "Копировать последний результат",
    "Quit": "Выход",

    # ---- status line ----
    "Loading the model...": "Загрузка модели...",
    "Choose a model to begin": "Выберите модель, чтобы начать",
    "Hold {key} and speak": "Удерживайте {key} и говорите",
    "Press {key} and speak": "Нажмите {key} и говорите",
    "Recording...": "Идёт запись...",
    "Transcribing {seconds}s...": "Распознавание, {seconds} с...",
    "Cancelled.": "Отменено.",
    "Nothing recognized.": "Ничего не распознано.",
    "Microphone is silent - check the input device":
        "Микрофон молчит — проверьте устройство ввода",
    "Model error: {error}": "Ошибка модели: {error}",
    "Transcription failed: {error}": "Не удалось распознать: {error}",
    "Output failed: {error}": "Не удалось вставить текст: {error}",
    "Cannot open the microphone": "Не удалось открыть микрофон",

    # ---- settings: pages ----
    "General": "Основное",
    "Sound": "Звук",
    "Models": "Модели",
    "Vocabulary": "Словарь",
    "History": "История",
    "About": "О программе",
    "Offline. Free. No account.": "Локально. Бесплатно. Без аккаунта.",
    "Saved": "Сохранено",

    # ---- settings: general ----
    "DICTATION": "ДИКТОВКА",
    "TEXT": "ТЕКСТ",
    "FEEDBACK": "СИГНАЛЫ",
    "APPLICATION": "ПРИЛОЖЕНИЕ",
    "INTERFACE": "ИНТЕРФЕЙС",
    "Hotkey": "Горячая клавиша",
    "The key you hold, or press, to dictate": "Клавиша, которой начинается диктовка",
    "Change...": "Изменить...",
    "Cancel a recording": "Отмена записи",
    "Discards it without recognizing anything": "Стирает запись, ничего не распознавая",
    "Mode": "Режим",
    "Hold the key while speaking, or press once to start":
        "Удерживать клавишу во время речи или нажать один раз",
    "Hold to talk": "Удерживать клавишу",
    "Toggle on and off": "Нажатием включать и выключать",
    "Language": "Язык распознавания",
    "Recognition is more accurate with a fixed language":
        "С заданным языком распознавание точнее",
    "Russian": "Русский",
    "English": "Английский",
    "Detect automatically": "Определять автоматически",
    "Model": "Модель",
    "Change and download models on the Models page":
        "Скачивание и удаление моделей — на странице «Модели»",
    "Result": "Результат",
    "Where the recognized text goes": "Куда попадает распознанный текст",
    "Paste into the window": "Вставить в активное окно",
    "Type it out": "Напечатать посимвольно",
    "Copy to clipboard only": "Только в буфер обмена",
    "Leave it on the clipboard": "Оставлять в буфере обмена",
    "So a paste that missed the window can still be pasted by hand":
        "Если вставка промахнулась мимо окна, текст можно вставить вручную",
    "Keep a history": "Вести историю",
    "Every result is appended to {file}": "Каждый результат дописывается в {file}",
    "Floating panel": "Всплывающая панель",
    "Shows a live waveform while recording and while transcribing":
        "Показывает волну во время записи и работу во время распознавания",
    "Panel position": "Положение панели",
    "Top of the screen": "Сверху экрана",
    "Bottom": "Снизу",
    "Middle": "По центру",
    "Sound effects": "Звуковые сигналы",
    "Short beeps when recording starts and stops":
        "Короткие сигналы в начале и в конце записи",
    "Notifications": "Уведомления",
    "A tray balloon with the recognized text": "Всплывающее уведомление с распознанным текстом",
    "Launch at login": "Запускать при входе в систему",
    "Start FastWhisper when you sign in to Windows":
        "Запускать FastWhisper вместе с Windows",
    "Settings file": "Файл настроек",
    "Open": "Открыть",
    "Interface language": "Язык интерфейса",
    "Русский": "Русский",
    "Follow Windows": "Как в Windows",

    # ---- settings: sound ----
    "MICROPHONE": "МИКРОФОН",
    "LIMITS": "ОГРАНИЧЕНИЯ",
    "PERFORMANCE": "ПРОИЗВОДИТЕЛЬНОСТЬ",
    "Input device": "Устройство ввода",
    "System default": "Устройство по умолчанию",
    "Boost quiet recordings": "Усиливать тихие записи",
    "Lifts a low input to a usable level before recognition":
        "Поднимает слишком тихий сигнал до рабочего уровня перед распознаванием",
    "Silence removal": "Обрезка тишины",
    "Trims quiet parts before recognition, which is faster and cleaner":
        "Убирает тишину до распознавания — быстрее и чище",
    "Ignore recordings shorter than": "Игнорировать записи короче",
    "Guards against an accidental tap on the hotkey":
        "Защита от случайного нажатия клавиши",
    "Stop recording after": "Останавливать запись через",
    "A safety net for a stuck key": "Страховка на случай залипшей клавиши",
    "CPU threads": "Потоки процессора",
    "This machine has {count} logical cores": "В этой машине {count} логических ядер",
    "Half the cores (default)": "Половина ядер (по умолчанию)",
    "1 minute": "1 минута",
    "5 minutes": "5 минут",
    "15 minutes": "15 минут",

    # ---- settings: models ----
    "SPEECH MODELS": "МОДЕЛИ РАСПОЗНАВАНИЯ",
    "Every model here runs on this machine, with no account and no cloud. Larger ones are "
    "more accurate and slower; the speed and accuracy bars are relative to each other, and "
    "the wait is what you actually get on this CPU.":
        "Все модели работают на этой машине, без аккаунта и без облака. Крупные точнее и "
        "медленнее; шкалы скорости и точности сравнивают модели между собой, а время "
        "ожидания измерено на этом процессоре.",
    "Badges mark who trained each model, not a partnership: the weights are open and used "
    "under their own licences.":
        "Значки показывают, кто обучил модель, а не партнёрство: веса открыты и "
        "используются по их собственным лицензиям.",
    "Accuracy": "Точность",
    "Speed": "Скорость",
    "Download": "Скачать",
    "Delete": "Удалить",
    "Use": "Выбрать",
    "in use": "выбрана",
    "Downloading...": "Загрузка...",
    "Download failed": "Не удалось скачать",
    "Loading model...": "Загрузка модели...",
    "Model ready": "Модель готова",
    "Applies after the model reloads": "Применится после перезагрузки модели",

    # ---- settings: vocabulary ----
    "Names, jargon and spellings the model should prefer. They are passed to Whisper as "
    "context before each recording, which nudges it towards your wording. One entry per "
    "line; keep the list short, a long one dilutes the effect.":
        "Имена, термины и написания, которым модель должна отдавать предпочтение. Они "
        "передаются Whisper как контекст перед каждой записью и склоняют её к вашим "
        "формулировкам. По одной записи на строку; длинный список размывает эффект.",
    "Save": "Сохранить",
    "Applies to the next recording.": "Подействует со следующей записи.",

    # ---- settings: history ----
    "Refresh": "Обновить",
    "Nothing here yet.": "Пока пусто.",
    "No results.": "Ничего не найдено.",
    "Copied": "Скопировано",

    # ---- settings: about ----
    "ABOUT": "О ПРОГРАММЕ",
    "PRIVACY": "ПРИВАТНОСТЬ",
    "Version": "Версия",
    "Recognition": "Распознавание",
    "faster-whisper on the CTranslate2 runtime": "faster-whisper на движке CTranslate2",
    "Data folder": "Папка данных",
    "Log file": "Файл журнала",
    "Nothing leaves this machine": "Ничто не покидает эту машину",
    "Audio is held in memory and discarded after recognition. The only network request the "
    "app makes is downloading a model.":
        "Звук хранится в памяти и удаляется после распознавания. Единственный сетевой "
        "запрос приложения — загрузка модели.",

    # ---- hotkey capture ----
    "FastWhisper - set hotkey": "FastWhisper — выбор клавиши",
    "Press the key or combination you want to use":
        "Нажмите клавишу или сочетание, которое хотите использовать",
    "A single key such as Right Ctrl is the easiest to hold.\nA combination is swallowed "
    "while FastWhisper runs, a single key is not.\nEscape closes this window without "
    "changing anything.":
        "Одиночную клавишу вроде правого Ctrl удобнее удерживать.\nСочетание "
        "перехватывается целиком, одиночная клавиша — нет.\nEscape закрывает окно без "
        "изменений.",
    "Cancel": "Отмена",
    "{combo} cannot be used: {error}": "{combo} использовать нельзя: {error}",

    # ---- first run ----
    "Choose a speech model": "Выберите модель распознавания",
    "It runs on this computer - nothing is uploaded. Bigger models understand more and "
    "make you wait longer. This one is downloaded once.":
        "Она работает на этом компьютере, ничего никуда не отправляется. Крупные модели "
        "понимают лучше и заставляют дольше ждать. Загрузка — один раз.",
    "You can change this later in Settings, where five more models are waiting, including "
    "English-only ones that are faster at the same accuracy.":
        "Позже модель можно сменить в настройках — там ждут ещё пять, включая "
        "англоязычные, которые при той же точности работают быстрее.",
    "Use this model": "Использовать эту",
    "Decide later": "Решить позже",
    "{size} GB  -  {latency} per phrase": "{size} ГБ  -  {latency} на фразу",

    # ---- model tiers and purposes ----
    "Recommended": "Рекомендуем",
    "Accurate": "Точная",
    "Balanced": "Сбалансированная",
    "Quick": "Быстрая",
    "Instant": "Мгновенная",
    "The most accurate one that is still comfortable to wait for. Handles Russian names "
    "and endings the smaller ones mangle.":
        "Самая точная из тех, что комфортно ждать. Справляется с русскими именами и "
        "окончаниями, которые модели поменьше ломают.",
    "Everyday dictation when you would rather not reread every line.":
        "Повседневная диктовка, когда не хочется перечитывать каждую строку.",
    "Answers in a second and a half. Fine for English, rougher on Russian.":
        "Отвечает за полторы секунды. Для английского хорошо, для русского грубовато.",
    "Short notes and search boxes, where a wrong word costs nothing.":
        "Короткие заметки и строки поиска, где ошибка ничего не стоит.",
    "As fast as it gets. Expect to fix words afterwards.":
        "Быстрее некуда. Слова придётся править.",
    "99 languages": "99 языков",
    "~{value} s": "~{value} с",
    "{author} · {packager} · {languages} · {latency}":
        "{author} · {packager} · {languages} · {latency}",
}
