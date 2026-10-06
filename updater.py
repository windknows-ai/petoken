"""Update check and one-click update (V1.7 B).

Once a day (Settings > General > Check for updates, on by default) Petoken
asks GitHub for the latest release of windknows-ai/petoken. That is a
single read-only HTTPS request; nothing about this computer is sent. When
a newer version exists, the user sees what changed and can update now,
later, skip that version, or let Petoken update by itself from now on.

Updating downloads the release's installer and its SHA256SUMS.txt into
``%LOCALAPPDATA%\\CodexWisp\\updates``, refuses a file whose hash does not
match, then starts the installer silently with ``/RELAUNCH=1`` (the
installer reopens Petoken when done) and Petoken quits so its files can be
replaced. Settings and data are untouched by the installer.

``PETOKEN_UPDATE_FEED`` (a URL or a local JSON file in the GitHub release
format) replaces the GitHub address for QA, so the flow can be shown with
a test version without touching real releases.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import time
import urllib.request
from pathlib import Path

FEED = 'https://api.github.com/repos/windknows-ai/petoken/releases/latest'
CHECK_EVERY_S = 24 * 3600
TIMEOUT_S = 20
_VERSION = re.compile(r'^v?(\d+)\.(\d+)\.(\d+)$')
_INSTALLER = re.compile(r'^Petoken-Setup-v(\d+\.\d+\.\d+)\.exe$')


def parse_version(value):
    match = _VERSION.match(value.strip()) if isinstance(value, str) else None
    return tuple(int(part) for part in match.groups()) if match else None


def newer(candidate, current):
    a, b = parse_version(candidate), parse_version(current)
    return bool(a and b and a > b)


def _read(url, opener=None, limit=200 * 1024 * 1024):
    """Bytes from an https URL or, for QA feeds, a local file path."""
    if not re.match(r'^https://', url or ''):
        return Path(url).read_bytes()
    request = urllib.request.Request(url, headers={'User-Agent': 'Petoken-update-check',
                                                   'Accept': 'application/vnd.github+json'})
    with (opener or urllib.request.urlopen)(request, timeout=TIMEOUT_S) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError('Download larger than expected')
    return data


def latest(feed=None, opener=None):
    """dict(version, notes, url, installer, sums) of the latest release, or None."""
    feed = feed or os.environ.get('PETOKEN_UPDATE_FEED') or FEED
    try:
        release = json.loads(_read(feed, opener).decode('utf-8'))
    except (OSError, ValueError):
        return None
    if not isinstance(release, dict) or release.get('draft') or release.get('prerelease'):
        return None
    version = (release.get('tag_name') or '').lstrip('v')
    if not parse_version(version):
        return None
    assets = {a.get('name'): a.get('browser_download_url') for a in release.get('assets') or []
              if isinstance(a, dict)}
    installer = next((url for name, url in assets.items()
                      if isinstance(name, str) and _INSTALLER.match(name)
                      and _INSTALLER.match(name).group(1) == version), None)
    if not installer or not assets.get('SHA256SUMS.txt'):
        return None   # Never offer an update we cannot verify.
    notes = release.get('body') if isinstance(release.get('body'), str) else ''
    return dict(version=version, notes=notes[:20000], url=release.get('html_url') or '',
                installer=installer, sums=assets['SHA256SUMS.txt'])


def due(prefs, now=None):
    now = time.time() if now is None else now
    checked = prefs.get('update_checked_at')
    checked = checked if isinstance(checked, (int, float)) and not isinstance(checked, bool) else 0
    return bool(prefs.get('update_check', True)) and now - checked >= CHECK_EVERY_S


def offer(release, current, prefs):
    """The release if the user should hear about it: newer and not skipped."""
    if not release or not newer(release['version'], current):
        return None
    return None if prefs.get('update_skip') == release['version'] else release


def expected_hash(sums_text, name):
    for line in (sums_text or '').splitlines():
        parts = line.strip().split()
        if len(parts) == 2 and parts[1].lstrip('*') == name and re.match(r'^[0-9a-fA-F]{64}$', parts[0]):
            return parts[0].lower()
    return None


def download(release, folder, opener=None):
    """Verified installer path, or raise ValueError / OSError."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    name = f"Petoken-Setup-v{release['version']}.exe"
    wanted = expected_hash(_read(release['sums'], opener).decode('utf-8', 'replace'), name)
    if not wanted:
        raise ValueError('The release has no checksum for its installer')
    data = _read(release['installer'], opener)
    if hashlib.sha256(data).hexdigest() != wanted:
        raise ValueError('Checksum mismatch: the download was not used')
    target = folder / name
    temp = target.with_suffix('.part')
    temp.write_bytes(data)
    temp.replace(target)
    for old in folder.glob('Petoken-Setup-v*.exe'):
        if old != target:
            try:
                old.unlink()
            except OSError:
                pass
    return target


def install_command(installer):
    """Silent, per-user, closes Petoken and reopens it afterwards."""
    return [str(installer), '/SILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/CLOSEAPPLICATIONS',
            '/RELAUNCH=1']


def start_install(installer):
    flags = getattr(subprocess, 'DETACHED_PROCESS', 0) | getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)
    return subprocess.Popen(install_command(installer), shell=False, creationflags=flags, close_fds=True)
