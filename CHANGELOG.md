# Changelog

What changed, newest first. Dates are the day the work landed on `main`.

## Unreleased

### 2026-08-27 - Defaults, models and the panel

**Dictation**

- `Ctrl+Space` in toggle mode is the default: press once to start, once to stop.
  `Esc` cancels a recording without transcribing it, and now says so in the settings.
- Hotkeys can be recorded in a capture window instead of only picked from a list. Single
  keys such as `Right Ctrl` are watched through a raw keyboard hook, which keeps the left
  and right modifiers apart and leaves the key working as itself; combinations are
  registered as suppressed hotkeys so the keystroke never reaches the window underneath.

**Language**

- The interface speaks Russian as well as English, and picks one from Windows: Russian if
  Windows itself is Russian, English otherwise. *General → Interface language* overrides
  it, and the windows rebuild in place rather than asking for a restart.
- Recognition language stays a separate setting. A Russian interface is no reason to stop
  dictating in English.

**First run**

- A one-time picker asks which speech model to use, showing what each is good for, how
  accurate it is and how long it makes you wait. Choosing a model is the one decision a
  new user cannot avoid - it costs a download of between 80 MB and 1.6 GB - so it is put
  in front of them once instead of being made silently.

**Text**

- The dictated text stays on the clipboard after being pasted. A paste can miss, and then
  the only copy of what was just said would be gone.

**The floating panel**

- Gold for recording, its opposite blue for transcribing, in the panel and in the tray
  icon. The tray icon and the window icon are the logo's grain now, and the two states
  differ in shape as well as in colour - a colour-blind reader gets the same signal. Resting grains keep a bronze tint instead of fading to grey, and speaking louder
  adds rows to the lattice rather than only brightening the ones already there.

- A lattice of gold grains at the top of the screen, rippling with your voice while
  recording and carrying a travelling wave while the model works.
- No panel behind it. The window is layered and its bitmap is pushed with
  `UpdateLayeredWindow`, because Tk can only key out a single flat colour and that leaves
  a coloured fringe around anything antialiased.
- Resting grains fade out rather than turning dark, so the field does not read as dirt on
  a light desktop.

**Settings window**

- Six pages - General, Sound, Models, Vocabulary, History, About - replacing a tray menu
  that had grown into a worse version of the same thing. The tray now keeps the status,
  the settings window, copy-last-result and quit.
- Vocabulary entries are passed to Whisper as context before each recording, which is the
  supported way to bias it towards particular names and jargon.
- History is searchable, and clicking an entry copies it.

**Models**

- Whisper Large v3 Turbo is the default. Small is what comparable apps ship, and it is
  what English needs; Russian gets noticeably more wrong out of it, and Turbo costs the
  same disk as Medium for better accuracy.
- Listed under their real names with who trained them, who converted them to the runtime
  this app uses, an accuracy gauge and the measured wait per phrase.
- Download and delete from the page. The active model cannot be deleted.
- Sizes are summed over the whole repository directory and deduplicated by inode: the
  newer Xet cache backend leaves `blobs` empty and keeps the files under `snapshots`, so
  a blobs-only measurement reported zero.
- Badges are monograms drawn by the app, not company marks. The weights are open and used
  under their own licences.

**Audio**

- Recording happens at the device's own sample rate and is resampled to 16 kHz with
  libswresample. Requesting 16 kHz directly fails on the MME host API unless the hardware
  offers that rate, which is why every attempt on a 44.1 kHz microphone errored out.
- Quiet input is lifted before recognition. Whisper's voice activity detector judges
  absolute loudness, so a microphone running at a low system level had its speech
  discarded as silence.
- Audio that comes back at digital silence reports the microphone instead of quietly
  recognizing nothing.

**Deployment**

- The README and the release notes now say plainly what the MSI is for: a managed network
  where software arrives through Group Policy or an MDM rather than by hand, with no
  licences to count and no data leaving the machines. Both also state that the packages
  are unsigned, why, and what is offered instead - full source, reproducible builds and
  published SHA-256 checksums.
- An MSI for Group Policy and Intune, next to the per-user installer. It installs for the
  whole machine, needs no interface and takes two properties: `AUTOSTART=1` to start for
  every user who signs in, and `MODELDIR` to point them all at one model directory rather
  than a copy per profile, which is half a gigabyte each.

**Application**

- A second launch exits quietly instead of stacking a modal dialog on top of a tray app.
- Installer and per-user install with no admin rights; optional launch at login.

### 2026-08-26 - First working version

- Push-to-talk dictation with faster-whisper running locally on the CPU, a tray icon, and
  the text pasted into the focused window.
- Settings in `%APPDATA%\FastWhisper\config.json`, history in `history.jsonl`.
