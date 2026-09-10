# Changelog

What changed, newest first. Dates are the day the work landed on `main`.

## Unreleased

### 2026-09-10 - 0.1.1 - The keyboard, taken back from the library

**Ctrl no longer sticks**

- The application has its own low-level keyboard hook and no longer depends on the
  `keyboard` package. That package could not suppress a chord without first suppressing
  its modifiers: it swallowed every Ctrl press, waited to see whether the rest of the
  chord followed, and when it did not, put the key back with `keybd_event`. That call
  carries the scan code in a single byte and cannot set the extended flag, so a
  suppressed *right* Ctrl came back as a plain, non-extended one. The physical key-up a
  moment later did carry the flag, released the wrong key, and left Ctrl held down until
  some left Ctrl happened to cancel it.
- Switching keyboard layout with the right-hand `Ctrl+Shift` hit this every single time,
  and left the machine acting as though Ctrl were glued down: clicks became Ctrl-clicks,
  Space scrolled instead of typing. Any Ctrl chord could do it; the layout switcher was
  simply the one nobody could avoid.
- Now only the *last* key of a chord is taken from the window underneath, and only while
  the chord's modifiers are held. Modifiers are always passed through untouched, so
  there is nothing to put back and nothing that can be stranded.
- Left and right modifiers are told apart by virtual key code rather than by arithmetic
  on overlapping scan-code sets, which is both correct and considerably less clever.
- Text is delivered with `SendInput` instead of `keybd_event`, with the extended flag set
  where it belongs, and every injected event is stamped so the hook can recognise the
  app's own keystrokes and ignore them.
- Before each paste, any modifier Windows believes is held that was never physically
  pressed is released. Nothing here creates those any more, but other programs do, and a
  stray Shift turns `Ctrl+V` into a different command.

**The hotkey stops disappearing**

- Recording no longer starts inside the hook procedure. Windows silently unhooks a
  low-level keyboard hook whose callback overruns `LowLevelHooksTimeout`, 300 ms by
  default, and opening a microphone takes longer than that on its own - so the app went
  on looking healthy while its hotkey had quietly stopped working. The procedure now
  records the key and returns; everything else happens on a worker thread.
- Hold-to-talk ends on the real key-up rather than on a 20 ms poll, so the two polling
  threads per recording are gone.
- Whether a recording is open is asked of the recorder rather than remembered by the
  hotkey, so a recording that ended by itself - too short to keep, a microphone that
  failed - no longer leaves the toggle inverted for one press.

**Text**

- `output: type` sends characters rather than keystrokes, so what arrives no longer
  depends on the layout that happens to be active. Dictating Russian into a window while
  the layout was English produced nothing usable.

**The missing signature**

- The installer now says, on a page of its own before anything is written, that the
  package is unsigned and why: a certificate costs a few hundred dollars a year and this
  project charges nobody anything. Better read there than discovered afterwards.
- Both the installer page and the README name the exact folder to exclude for each way of
  installing, and link to Microsoft's false-positive form. Defender does flag unsigned
  PyInstaller builds — `Trojan:Win32/Wacatac` and `Trojan:Win32/Bearfoos` are the usual
  verdicts — and it will quarantine the program or stop it mid-run. Reporting a detection
  is what eventually clears it for everyone.

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
