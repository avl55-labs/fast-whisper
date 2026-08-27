# FastWhisper

Hold a hotkey, speak, and the text appears in whatever window you were typing in.
Offline, free, no account, no ads, no telemetry. Windows 10/11.

It is a small, self-contained alternative to SuperWhisper and similar paid dictation
apps. Speech recognition runs locally through [faster-whisper][fw] (OpenAI's Whisper
models on the CTranslate2 runtime), so nothing leaves your machine.

> Not affiliated with the `faster-whisper` library. FastWhisper is an application that
> uses it.

## How it works

1. Hold `Ctrl+Alt+Space` (configurable) — the tray icon turns red and recording starts.
2. Speak.
3. Release the key — the icon turns amber while the model transcribes.
4. The text is pasted into the focused window.

`Esc` while recording cancels without transcribing. A `toggle` mode is available if you
prefer pressing once to start and once to stop.

## Install

Download `FastWhisper-x.y.z-setup.exe` from [Releases][rel] and run it. The installer is
per-user: it writes to `%LOCALAPPDATA%\Programs\FastWhisper`, needs no admin rights and
raises no UAC prompt. It can optionally add FastWhisper to startup.

On the first launch the app downloads the Whisper model (~0.5 GB for the default `small`)
into `%USERPROFILE%\.cache\huggingface`. The tray icon stays blue while that happens.
Everything after that is offline.

## Settings

Right-click the tray icon for the common options — mode, language, model, output method,
autostart. Everything else lives in `%APPDATA%\FastWhisper\config.json`:

| Key | Default | Meaning |
| --- | --- | --- |
| `hotkey` | `ctrl+alt+space` | Any combination in [`keyboard`][kb] syntax, e.g. `f9`, `right ctrl`. |
| `mode` | `hold` | `hold` (push-to-talk) or `toggle`. |
| `model` | `small` | `tiny`, `base`, `small`, `medium`, `large-v3`, `large-v3-turbo`. |
| `device` | `cpu` | `cuda` if you have an NVIDIA card and the CUDA libraries installed. |
| `compute_type` | `int8` | `int8` on CPU, `float16` on CUDA. |
| `language` | `ru` | Two-letter code, or `auto` to detect per recording. |
| `output` | `paste` | `paste`, `type` (key by key), or `clipboard` (no insertion). |
| `beep` | `true` | Short beeps on start and stop. |
| `vad` | `true` | Trim silence around speech before transcribing. |
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
