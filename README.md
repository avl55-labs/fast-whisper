# FastWhisper

Hold a hotkey, speak, and the text appears in whatever window you were typing in.
Offline, free, no account, no ads, no telemetry. Windows 10/11.

It is a small, self-contained alternative to SuperWhisper and similar paid dictation
apps. Speech recognition runs locally through [faster-whisper][fw] (OpenAI's Whisper
models on the CTranslate2 runtime), so nothing leaves your machine.

> Not affiliated with the `faster-whisper` library. FastWhisper is an application that
> uses it.

## How it works

1. Press `Ctrl+Space` — a panel of gold grains fades in at the top of the screen and
   ripples with your voice.
2. Speak.
3. Press `Ctrl+Space` again — the pattern changes while the model transcribes.
4. The text is pasted into the focused window.

`Esc` while recording cancels without transcribing. Hold-to-talk is available too: set
*Mode* to *Hold to talk* and the recording runs only while the key is down.

## Install

Download `FastWhisper-x.y.z-setup.exe` from [Releases][rel] and run it. The installer is
per-user: it writes to `%LOCALAPPDATA%\Programs\FastWhisper`, needs no admin rights and
raises no UAC prompt. It can optionally add FastWhisper to startup.

On the first launch the app downloads the Whisper model (~0.5 GB for the default `small`)
into `%USERPROFILE%\.cache\huggingface`. The tray icon stays blue while that happens.
Everything after that is offline.

## The floating panel

While you speak, a panel fades in at the top of the screen: a lattice of small gold grains
that ripples with your voice, so you can see the app is listening. When you let the hotkey
go the pattern changes to a wave travelling through the lattice and keeps moving until the
text lands in your window - transcription takes a few seconds, and without it nothing on
screen would tell you the app was still working.

The panel never takes focus and clicks pass straight through it, so it cannot interfere
with the window you are dictating into. Turn it off or move it in *Settings -> General*.

## Settings

The tray icon carries only what you need mid-dictation — settings, copy the last result,
quit. Everything else is in the settings window, which opens on *Settings* or a double
click on the icon. Six pages:

- **General** - hotkey, hold or toggle, language, model, where the text goes, the panel,
  sounds, launch at login.
- **Sound** - microphone, boosting quiet input, silence trimming, the minimum and maximum
  length of a recording, CPU threads.
- **Models** - every model with who trained it, its accuracy, its measured latency and
  its size on disk. Download and delete them here; the active one cannot be deleted.
- **Vocabulary** - names and jargon the model should prefer. They are passed to Whisper as
  context before each recording.
- **History** - everything recognized so far, searchable. Click an entry to copy it.
- **About** - version and the paths to the log and data folders.

Anything set here is written to `%APPDATA%\FastWhisper\config.json` immediately.

## Choosing a hotkey

*Hotkey -> Set a custom key...* in the tray menu opens a window that records whatever you
press next; the current hotkey stays disarmed while it is open. There are presets in the
same menu, and `hotkey` in the settings file accepts any [`keyboard`][kb] combination. What matters is how the key behaves the rest of the time:

- **A single key** — `right ctrl`, `right alt`, `f9` — is the most comfortable to hold and
  is *not* swallowed by FastWhisper, so it keeps working as itself. The trade-off is that
  every ordinary use of the key starts a recording: with `right ctrl` a slow `Ctrl+C`
  or a `Ctrl`-drag opens the microphone. Anything shorter than `min_seconds` is thrown
  away, so short shortcuts are harmless — long ones are not. `right alt` is the safer of
  the two, unless your layout uses AltGr to type characters.
- **A combination** — `ctrl+alt+space` (the default), `ctrl+shift+space` — is suppressed
  while FastWhisper runs, so the keystroke never reaches the app underneath. Pick one
  nothing else wants.
- **`ctrl+space`** works, but editors use it for autocomplete and Asian input methods use
  it to switch; suppression makes it stop doing that everywhere.
- **`win+space`** works too, and takes over the Windows keyboard-layout switcher. Avoid it
  if you type in more than one language.

## Settings

Right-click the tray icon for the common options — hotkey, mode, language, model, output
method, autostart. Everything else lives in `%APPDATA%\FastWhisper\config.json`:

| Key | Default | Meaning |
| --- | --- | --- |
| `hotkey` | `ctrl+space` | Any combination in [`keyboard`][kb] syntax, e.g. `f9`, `right ctrl`. |
| `mode` | `toggle` | `hold` (push-to-talk) or `toggle`. |
| `model` | `small` | `tiny`, `base`, `small`, `medium`, `large-v3`, `large-v3-turbo`. |
| `device` | `cpu` | `cuda` if you have an NVIDIA card and the CUDA libraries installed. |
| `compute_type` | `int8` | `int8` on CPU, `float16` on CUDA. |
| `language` | `ru` | Two-letter code, or `auto` to detect per recording. |
| `output` | `paste` | `paste`, `type` (key by key), or `clipboard` (no insertion). |
| `beep` | `true` | Short beeps on start and stop. |
| `vad` | `true` | Trim silence around speech before transcribing. |
| `auto_gain` | `true` | Lift a quiet recording before recognition. |
| `min_seconds` | `0.4` | Shorter recordings are discarded as accidental presses. |
| `input_device` | `null` | Microphone index; `null` is the system default. |
| `cpu_threads` | `0` | `0` means half of the logical cores. |
| `prompt` | `""` | Optional bias text: names, jargon, spelling you want kept. |

Edit the file and restart the app to apply.

## Choosing a model

Whisper runs its encoder over a fixed 30-second window, so the wait after you release the
hotkey barely depends on how long you spoke — a three-second phrase costs about as much as
a nine-second one. Measured on an 8-core Ryzen 9 8945HS, `int8`, 16 threads:

| Model | Size on disk | Latency per phrase | Quality |
| --- | --- | --- | --- |
| `base` | ~0.15 GB | ~0.6 s | rough, fine for short English notes |
| `small` | ~0.5 GB | ~1.6 s | decent — the default |
| `medium` | ~1.5 GB | ~4.3 s | good, but `large-v3-turbo` beats it at a similar cost |
| `large-v3-turbo` | ~1.6 GB | ~5.5 s | best quality on CPU |
| `large-v3` | ~3 GB | slower still | only worth it on a CUDA GPU |

Switch models from the tray menu; the new one loads in the background. On an NVIDIA GPU
set `device` to `cuda` and `compute_type` to `float16` — `large-v3-turbo` then answers in
well under a second and there is no reason to use anything smaller.

## Build from source

Requires Python 3.11+ and, for the installer, [Inno Setup 6][inno].

```powershell
git clone https://github.com/avl55-labs/fast-whisper
cd fast-whisper
powershell -ExecutionPolicy Bypass -File packaging\build.ps1
```

The result is `dist\FastWhisper\FastWhisper.exe` and `dist\FastWhisper-0.1.0-setup.exe`.

To run without building:

```powershell
py -3 -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\pythonw -m fastwhisper
```

## Troubleshooting

- **The hotkey does nothing in one particular app.** Windows blocks keyboard hooks from
  processes at a lower integrity level. If the target app runs as administrator,
  FastWhisper has to as well.
- **Text is not pasted.** Some apps ignore synthetic `Ctrl+V`. Switch `output` to `type`.
- **Nothing is recognized.** Check the microphone under `input_device`; the log at
  `%APPDATA%\FastWhisper\fastwhisper.log` records every recording and its length.
- **Antivirus flags the exe.** Unsigned PyInstaller builds are a common false positive.
  Build from source if you would rather not trust the release binary.

## Privacy

Audio is recorded to memory and discarded after transcription. Recognized text is
appended to `%APPDATA%\FastWhisper\history.jsonl` — set `save_history` to `false` to
turn that off. The only network request the app ever makes is the one-time model
download from Hugging Face.

## License

MIT. See [LICENSE](LICENSE).

[fw]: https://github.com/SYSTRAN/faster-whisper
[kb]: https://github.com/boppreh/keyboard#api
[inno]: https://jrsoftware.org/isinfo.php
[rel]: https://github.com/avl55-labs/fast-whisper/releases
