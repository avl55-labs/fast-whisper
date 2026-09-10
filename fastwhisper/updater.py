"""Asking GitHub whether a newer version exists.

This is the only thing in the application that touches the network once the speech model
is on disk, and it is kept deliberately small. Once a day, if the setting is on, it asks
GitHub for the latest release and compares version numbers. Nothing is reported: the
request carries no identifier, no machine name and no statistics - only the application's
own version in the User-Agent, so that whoever maintains it can see which versions are
still out there.

Downloading and installing never happen by themselves. Someone has to press the button,
and what runs then is the ordinary installer with its ordinary window, so the moment code
is about to be executed is a moment somebody is looking at. A dictation tool that quietly
replaced itself in the background would be a strange thing to ask anyone to trust.

Verification is honest about what it is. The size and the checksum come from the same
release as the file, over the same connection, so they catch a truncated download and
nothing else. Only a signature would make them a security measure, and these packages are
not signed - the README says why.
"""
from __future__ import annotations

import hashlib
import logging
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import __version__

log = logging.getLogger(__name__)

REPO = "avl55-labs/fast-whisper"
API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{REPO}/releases/latest"
INTERVAL = 24 * 60 * 60
TIMEOUT = 12
MACHINE_KEY = r"Software\avl55-labs\FastWhisper"

# The release this run has found and not yet been told to forget, so the tray and the
# settings window can both show it without asking GitHub twice.
pending: "Release | None" = None


class UpdateError(RuntimeError):
    pass


@dataclass(frozen=True)
class Release:
    version: str
    page: str
    asset_name: str
    asset_url: str
    asset_size: int
    checksums_url: str = ""


# ---------------------------------------------------------------- versions


def parse_version(text: str) -> tuple[int, ...]:
    """`v0.1.2` and `0.1.2-rc1` both become (0, 1, 2)."""
    cleaned = text.strip().lstrip("vV").split("-")[0].split("+")[0]
    parts = []
    for piece in cleaned.split("."):
        digits = "".join(character for character in piece if character.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts) or (0,)


def is_newer(candidate: str, current: str = __version__) -> bool:
    left, right = parse_version(candidate), parse_version(current)
    width = max(len(left), len(right))
    left += (0,) * (width - len(left))
    right += (0,) * (width - len(right))
    return left > right


# ---------------------------------------------------------------- policy


def allowed_by_policy() -> bool:
    """A managed install can switch the check off for everyone on the machine.

    The MSI sets this, because on a network where software arrives through Group Policy
    an application that goes looking for its own updates is a nuisance rather than a
    feature: the administrator decides when versions change.
    """
    try:
        import winreg
    except ImportError:
        return True
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, MACHINE_KEY) as key:
            value, _kind = winreg.QueryValueEx(key, "UpdateCheck")
    except OSError:
        return True
    return str(value).strip().lower() not in ("0", "false", "no")


def _headers(accept: str = "application/vnd.github+json") -> dict[str, str]:
    return {
        "Accept": accept,
        "User-Agent": f"FastWhisper/{__version__}",
        "X-GitHub-Api-Version": "2022-11-28",
    }


# ---------------------------------------------------------------- checking


def latest() -> Release | None:
    """The newest published release, or None if it carries no installer."""
    import requests

    response = requests.get(API_URL, timeout=TIMEOUT, headers=_headers())
    response.raise_for_status()
    data = response.json()

    installer = None
    checksums = ""
    for asset in data.get("assets", []):
        name = str(asset.get("name", ""))
        lowered = name.lower()
        if lowered.endswith(".exe") and "setup" in lowered:
            # Prefer the one carrying a version; the unversioned copy is the same file
            # under a permanent name, kept so a plain link can point at "the latest".
            if installer is None or any(character.isdigit() for character in name):
                installer = asset
        elif lowered.startswith("sha256"):
            checksums = str(asset.get("browser_download_url", ""))

    if installer is None:
        log.info("the latest release has no installer to offer")
        return None

    return Release(
        version=str(data.get("tag_name") or "").lstrip("vV"),
        page=str(data.get("html_url") or RELEASES_PAGE),
        asset_name=str(installer.get("name")),
        asset_url=str(installer.get("browser_download_url")),
        asset_size=int(installer.get("size") or 0),
        checksums_url=checksums,
    )


def check(cfg, force: bool = False) -> Release | None:  # noqa: ANN001 - avoids a circular import
    """Returns a newer release, or None. Never raises: being offline is not an error."""
    global pending

    if not allowed_by_policy():
        return None
    if not force:
        if not cfg.update_check:
            return None
        if time.time() - cfg.update_last_check < INTERVAL:
            return pending

    try:
        release = latest()
    except Exception:
        log.info("the update check did not get through", exc_info=True)
        return None

    cfg.update_last_check = time.time()
    try:
        cfg.save()
    except OSError:
        log.debug("could not record the time of the update check", exc_info=True)

    if release is None or not is_newer(release.version):
        pending = None
        return None
    pending = release
    log.info("version %s is available (this is %s)", release.version, __version__)
    return release


# ---------------------------------------------------------------- downloading


def _published_checksum(release: Release) -> str:
    """The hash listed alongside the release, if it published one."""
    if not release.checksums_url:
        return ""
    import requests

    try:
        response = requests.get(
            release.checksums_url, timeout=TIMEOUT, headers=_headers("text/plain")
        )
        response.raise_for_status()
    except Exception:
        log.debug("could not read the published checksums", exc_info=True)
        return ""
    for line in response.text.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[-1].lstrip("*") == release.asset_name:
            return parts[0].strip().lower()
    return ""


def mark_downloaded(path: Path, url: str) -> None:
    """Marks the file as having come from the internet, the way a browser would.

    Without this SmartScreen says nothing, because as far as Windows knows the file was
    produced locally. That would be convenient and dishonest: the warning exists for
    precisely this case, and an unsigned installer is precisely what it should get to
    look at.
    """
    try:
        with open(f"{path}:Zone.Identifier", "w", encoding="ascii") as stream:
            stream.write(f"[ZoneTransfer]\nZoneId=3\nHostUrl={url}\n")
    except OSError:
        log.debug("could not mark the download as coming from the internet", exc_info=True)


def download(release: Release, on_progress: Callable[[float], None] | None = None) -> Path:
    """Fetches the installer into the temporary folder and returns where it landed."""
    import requests

    folder = Path(tempfile.gettempdir()) / "FastWhisper-update"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / release.asset_name

    digest = hashlib.sha256()
    written = 0
    with requests.get(
        release.asset_url,
        stream=True,
        timeout=TIMEOUT,
        headers=_headers("application/octet-stream"),
    ) as response:
        response.raise_for_status()
        total = int(response.headers.get("Content-Length") or release.asset_size or 0)
        with open(target, "wb") as handle:
            for chunk in response.iter_content(256 * 1024):
                if not chunk:
                    continue
                handle.write(chunk)
                digest.update(chunk)
                written += len(chunk)
                if on_progress is not None and total:
                    on_progress(min(1.0, written / total))

    if release.asset_size and written != release.asset_size:
        target.unlink(missing_ok=True)
        raise UpdateError(
            f"the download stopped early: {written} bytes of {release.asset_size}"
        )

    expected = _published_checksum(release)
    if expected and expected != digest.hexdigest():
        target.unlink(missing_ok=True)
        raise UpdateError("the downloaded file does not match the published checksum")

    mark_downloaded(target, release.asset_url)
    log.info("downloaded %s (%d bytes)", target.name, written)
    return target


def launch(path: Path) -> None:
    """Starts the installer and stays out of its way.

    The application does not close itself here. The installer asks Windows which programs
    are holding the files it needs, closes them at the point it actually replaces
    something and starts them again afterwards - so a cancelled install leaves everything
    exactly as it was.
    """
    subprocess.Popen([str(path)], close_fds=True)  # noqa: S603 - a file we just verified
