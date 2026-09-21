"""What the boilerplate stripper must and must not do.

The three "real" cases below are taken verbatim from the tail of history.jsonl on the
machine where this was first noticed, which is the only reason we know the model runs
straight on from the last real word with no punctuation in between.

Run with:  .venv\\Scripts\\python -m pytest tests -q
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastwhisper.cleanup import strip_boilerplate  # noqa: E402


def stripped(text: str) -> str:
    return strip_boilerplate(text)[0]


# ---------------------------------------------------------------- the real cases


def test_whole_result_is_the_invention():
    assert stripped("Продолжение следует...") == ""


def test_runs_on_from_the_last_word_without_punctuation():
    text = "Ну в общем давай Варианты от тебя жду Продолжение следует..."
    assert stripped(text) == "Ну в общем давай Варианты от тебя жду"


def test_keeps_the_full_stop_that_belongs_to_the_sentence():
    text = "ну там небольшие изменения на графике. Продолжение следует..."
    assert stripped(text) == "ну там небольшие изменения на графике."


def test_the_famous_pair():
    text = "Всё понятно. Продолжение следует... Субтитры сделал DimaTorzok"
    assert stripped(text) == "Всё понятно."


# ---------------------------------------------------------------- spellings


def test_ellipsis_character_and_plain_dots_are_the_same_entry():
    assert stripped("Текст. Продолжение следует…") == "Текст."
    assert stripped("Текст. продолжение следует.") == "Текст."
    assert stripped("Текст. ПРОДОЛЖЕНИЕ СЛЕДУЕТ") == "Текст."


def test_yo_is_folded():
    assert stripped("Текст. Спасибо за просмотр!") == "Текст."


# ---------------------------------------------------------------- credits and tags


def test_credit_lines_with_any_name():
    assert stripped("Готово. Редактор субтитров А.Синецкая Корректор А.Егорова") == "Готово."
    assert stripped("Done. Subtitles by the Amara.org community") == "Done."
    assert stripped("Done. Transcription by CastingWords") == "Done."


def test_sound_tags():
    assert stripped("Раз два три [музыка]") == "Раз два три"
    assert stripped("One two three [Applause]") == "One two three"
    assert stripped("One two three ♪♪♪") == "One two three"


def test_english_subscribe_family():
    assert stripped("That is all. Thank you for watching!") == "That is all."
    assert stripped("That is all. Don't forget to subscribe") == "That is all."


# ---------------------------------------------------------------- must not touch


def test_leaves_ordinary_speech_alone():
    text = "Давай обсудим это завтра, а пока я подготовлю документы."
    assert stripped(text) == text


def test_does_not_strip_a_bare_ellipsis():
    text = "Ну не знаю..."
    assert stripped(text) == text


def test_does_not_cut_mid_text():
    text = "Продолжение следует только в кино, а у нас всё заканчивается сразу."
    assert stripped(text) == text


def test_a_long_tail_after_a_trigger_word_is_left_alone():
    text = ("Субтитры сделал наш подрядчик, но потом выяснилось, что тайминги поехали, "
            "и пришлось всё переделывать заново силами редакции.")
    assert stripped(text) == text


def test_reports_what_it_removed():
    text, removed = strip_boilerplate("Текст. Продолжение следует...")
    assert text == "Текст."
    assert removed == ["продолжение следует"]


def test_empty_input():
    assert strip_boilerplate("") == ("", [])


def test_user_supplied_phrase():
    text, removed = strip_boilerplate("Текст. Всем пока", extra=["всем пока"])
    assert text == "Текст."
    assert removed == ["всем пока"]
