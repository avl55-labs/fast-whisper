# PyInstaller spec for FastWhisper.
# Build with:  .venv\Scripts\pyinstaller.exe packaging\FastWhisper.spec --noconfirm
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

ROOT = Path(SPECPATH).parent

# These ship native DLLs that PyInstaller does not discover on its own.
binaries = (
    collect_dynamic_libs("ctranslate2")
    + collect_dynamic_libs("onnxruntime")
    + collect_dynamic_libs("av")
)

# faster_whisper carries the Silero VAD models as package data.
datas = collect_data_files("faster_whisper")

hidden = [
    "faster_whisper",
    "ctranslate2",
    "onnxruntime",
    "av",
    "sounddevice",
    "_sounddevice_data",
    "pystray._win32",
    "PIL._tkinter_finder",
]

a = Analysis(
    [str(ROOT / "packaging" / "entry.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    excludes=["tkinter", "matplotlib", "pytest", "torch"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="FastWhisper",
    icon=str(ROOT / "packaging" / "app.ico"),
    debug=False,
    strip=False,
    upx=False,
    console=False,  # tray application: no console window
    version=str(ROOT / "packaging" / "version_info.txt"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="FastWhisper",
)
