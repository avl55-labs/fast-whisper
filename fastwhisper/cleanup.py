"""Removing the caption boilerplate Whisper invents when it has nothing to transcribe.

Whisper was trained partly on subtitle corpora, so when the decoder is handed a stretch of
audio with no speech in it, it falls back on the text most likely to appear in that
position of a subtitle file: a "to be continued", a credit line, a plea to subscribe. In
Russian the famous pair is «Продолжение следует...» followed by «Субтитры сделал
DimaTorzok»; in English it is "Thank you for watching" and "Subtitles by …".

The obvious defence - trusting the model's own confidence - does not work here, and it is
worth saying why. faster-whisper discards a window as silence only when `no_speech_prob`
is above its threshold **and** `avg_logprob` is below another. These phrases are memorised,
so the model emits them with high confidence: the second condition fails and they sail
through. Confidence filtering catches an empty result, not a fluent invented one.

So this module matches the text itself, under rules meant to keep it from ever touching
something a person actually said:

* Only the end of the result is examined. An invention in the middle is a different
  problem, and cutting there would maim real speech.
* Matching is on whole words, after case and punctuation are normalised, so
  «Продолжение следует...», «Продолжение следует…» and «продолжение следует.» are one
  entry rather than three.
* No preceding full stop is required. The model often runs straight on from the last real
  word into the boilerplate, with no punctuation between them.
* Several passes, because the phrases arrive in pairs.
* Every removal is logged, so that if this ever eats something real there is a record of
  it rather than a mystery.

The list holds only what no one would dictate into a working document. Ordinary sentences
that merely sound final - «конец», "the end", «всем пока» - are deliberately absent: the
cost of eating one of those is higher than the cost of leaving it.
"""
from __future__ import annotations

import logging
import re

log = logging.getLogger(__name__)

# Punctuation trimmed from the edge of a word before it is compared.
EDGE = " \t\r\n.,!?;:\"'«»„“”‘’()[]{}<>-–—…*"

# Whole phrases, compared word by word at the end of the result.
BOILERPLATE = [
    # Russian: subtitle furniture, and the one that started all this.
    "продолжение следует",
    "продолжение в следующей серии",
    "спасибо за просмотр",
    "подписывайтесь на канал",
    "подпишитесь на канал",
    "ставьте лайки и подписывайтесь на канал",
    "не забудьте подписаться на канал",
    # English.
    "thank you for watching",
    "thanks for watching",
    "please subscribe to my channel",
    "subscribe to my channel",
    "do not forget to subscribe",
    "don't forget to subscribe",
    "like and subscribe",
    "www.mooji.org",
]

# Credit lines and sound tags, which carry a name or a description that cannot be listed.
# Each is anchored to the end of the text, and a match longer than `MAX_PATTERN` is
# ignored so that a stray trigger word early on cannot swallow half a paragraph.
PATTERNS = [
    r"субтитры\s+(?:сделал|создавал|делал|подготовил|подготовлены|и\s+перевод)\b.*$",
    r"редактор\s+субтитров\b.*$",
    r"корректор\s+[А-ЯЁA-Z][\w.]*\b.*$",
    r"(?:subtitles|subtitling|subs|captions|transcription|transcribed)\s+by\b.*$",
    r"amara\.org\b.*$",
    # Sound and music tags, which belong to captions and never to dictation.
    r"[\[(]\s*(?:музыка|музыкa|аплодисменты|смех|звук\w*|тишина|играет[^\])]*|"
    r"music|applause|laughter|silence|inaudible|blank_audio)[^\])]*[\])]\s*$",
    r"[♪♫]+[^\n]*$",
]

MAX_PATTERN = 120  # characters; a credit line is never longer than this
MAX_PASSES = 6     # the phrases arrive in pairs, so one pass is not enough


def _fold(word: str) -> str:
    """Case, ё and edge punctuation removed, so one list entry covers every spelling."""
    return word.lower().replace("ё", "е").strip(EDGE)


def _words(text: str) -> list[tuple[str, int]]:
    """Each word of the text as (folded form, offset of the original)."""
    found = []
    for match in re.finditer(r"\S+", text):
        folded = _fold(match.group(0))
        if folded:
            found.append((folded, match.start()))
    return found


def _strip_phrase(text: str, phrases: list[str]) -> tuple[str, str]:
    words = _words(text)
    if not words:
        return text, ""
    tail = [word for word, _ in words]
    for phrase in phrases:
        wanted = [folded for folded in (_fold(part) for part in phrase.split()) if folded]
        if not wanted or len(wanted) > len(tail):
            continue
        if tail[-len(wanted):] == wanted:
            # Cutting from the first word of the match takes any trailing dots with it.
            return text[: words[-len(wanted)][1]].rstrip(), phrase
    return text, ""


def _strip_pattern(text: str) -> tuple[str, str]:
    for pattern in PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match and len(match.group(0)) <= MAX_PATTERN:
            return text[: match.start()].rstrip(), match.group(0).strip()
    return text, ""


def strip_boilerplate(text: str, extra: list[str] | None = None) -> tuple[str, list[str]]:
    """Returns the text without its invented tail, and whatever was taken off it."""
    if not text:
        return text, []

    phrases = BOILERPLATE + [phrase for phrase in (extra or []) if phrase.strip()]
    removed: list[str] = []
    for _ in range(MAX_PASSES):
        text, hit = _strip_phrase(text, phrases)
        if not hit:
            text, hit = _strip_pattern(text)
        if not hit:
            break
        removed.append(hit)

    if removed:
        log.info("removed invented tail: %s", " | ".join(removed))
    return text.strip(), removed
