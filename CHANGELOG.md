# Changelog

What changed, newest first.

## 0.1.2 - 2026-09-10

- FastWhisper can tell you when a newer version is released. It asks GitHub once a day,
  sends nothing about you or your machine, and installs nothing by itself: you press a
  button and the ordinary installer opens. The choice is offered on the first run and
  lives in *Settings → About*.
- The MSI turns the check off for the whole machine, since a managed network updates on
  the administrator's schedule. `UPDATECHECK=1` gives it back.
- You can tell it to skip a version and stop offering that one.
- **No MSI is attached to this release** - the last published one is in 0.1.0. Build it
  from source in the meantime; see the README.
- Downloads are checked against the size and, where a release publishes one, the SHA-256,
  and are marked as coming from the internet so SmartScreen sees them as it would any
  other download.

## 0.1.1 - 2026-09-10

- **Ctrl no longer gets stuck.** Switching the keyboard layout with the right-hand
  `Ctrl+Shift` used to leave Ctrl held down until you pressed and released the *left*
  Ctrl - and until then clicks became Ctrl-clicks and Space scrolled instead of typing.
  Any Ctrl combination could trigger it. The application now handles the keyboard itself
  rather than through a library, swallows only the last key of a hotkey and never touches
  the modifiers, so there is nothing left to get stuck.
- **The hotkey no longer stops working by itself.** Windows quietly disconnects a
  keyboard hook that takes too long to answer, and opening a microphone took too long.
  The app went on looking healthy while its hotkey had gone dead. It now answers
  immediately and does the work elsewhere.
- Hold-to-talk stops the instant you let go, rather than up to a moment later.
- `output: type` writes characters rather than keystrokes, so dictating Russian into a
  window while the keyboard layout was English now produces the right text.
- A modifier left held down by some other program is released before each paste.
- The installer says, before it writes anything, that the package is unsigned and why,
  which folder to exclude from Defender, and where to report a false positive. The README
  says the same.

## 0.1.0 - 2026-08-27

First release.

- Dictation with faster-whisper running locally on the CPU: press the hotkey, speak, and
  the text is pasted into the window you were typing in. It stays on the clipboard too.
- A one-time picker on the first launch asks which of ten speech models to use, showing
  what each is good for and what it costs in disk and in waiting. Whisper Large v3 Turbo
  is the default.
- A floating panel of gold grains that ripples with your voice while recording and
  carries a travelling wave while the model works. It never takes focus and clicks pass
  through it.
- A settings window with six pages, replacing a tray menu that had outgrown itself:
  hotkey and output, microphone and silence trimming, model management, a vocabulary of
  names and jargon fed to the model as context, a searchable history, and About.
- English and Russian interface, following Windows by default. Separate from the language
  you dictate in.
- Hotkeys can be recorded rather than picked from a list, and single keys such as
  `Right Ctrl` keep working as themselves.
- Recording happens at the microphone's own sample rate and is resampled, which fixes
  every 44.1 kHz device. Quiet input is lifted before recognition, and a microphone that
  returns silence says so instead of recognizing nothing.
- A per-user installer that needs no administrator rights, and an MSI for Group Policy
  and Intune with `AUTOSTART` and `MODELDIR` properties.
