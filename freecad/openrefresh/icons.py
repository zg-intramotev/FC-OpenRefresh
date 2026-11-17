# -*- coding: utf-8 -*-
"""Install or remove the flat icon set in FreeCAD's user icon folder.

FreeCAD looks in ``<user dir>/icons`` before its own compiled-in icons, so a
file there with a stock icon's name replaces that icon in toolbars, menus and
the tree. FreeCAD reads the folder at start-up: changes show after a restart.

The rules:

* Only files this add-on created are ever touched. Each one is listed in
  ``<user dir>/icons/.openrefresh-manifest.json``.
* A file that is already there and not in the manifest - the user's own, or
  another add-on's - is never overwritten and never deleted.
* ``restore()`` deletes exactly the files in the manifest, then the manifest.
"""

import json
import os
import shutil

import FreeCAD as App

from . import paths, prefs
from .log import log

MANIFEST_NAME = ".openrefresh-manifest.json"


def user_icon_dir():
    """``<user dir>/icons`` - from FreeCAD, never from a fixed path."""
    return os.path.join(App.getUserAppDataDir(), "icons")


def manifest_path():
    return os.path.join(user_icon_dir(), MANIFEST_NAME)


def _safe_name(name):
    """A bare file name, so a damaged manifest cannot reach outside the folder."""
    return (isinstance(name, str) and name
            and name == os.path.basename(name)
            and name not in (".", "..", MANIFEST_NAME))


def _read_manifest():
    try:
        with open(manifest_path(), "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError:
        return []
    except Exception as exc:
        log("icons: manifest unreadable ({}); treating it as empty".format(exc))
        return []
    files = data.get("files", []) if isinstance(data, dict) else data
    if not isinstance(files, list):
        return []
    return sorted({name for name in files if _safe_name(name)})


def _write_manifest(files):
    target = manifest_path()
    temp = target + ".tmp"
    data = {"addon": "OpenRefresh", "files": sorted(set(files))}
    with open(temp, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=1)
    os.replace(temp, target)


def _sources():
    folder = paths.FLAT_ICONS
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.iterdir()
                  if p.is_file() and p.suffix.lower() == ".svg")


def installed():
    """True when the manifest lists at least one icon that is still there."""
    try:
        folder = user_icon_dir()
        return any(os.path.isfile(os.path.join(folder, name))
                   for name in _read_manifest())
    except Exception:
        return False


def install():
    """Copy the flat SVGs into the user icon folder; return how many were copied.

    Existing files not created by this add-on are skipped. Re-running
    refreshes the files that are ours. Takes effect after a restart.
    """
    sources = _sources()
    if not sources:
        log("icons: no SVGs in {}".format(paths.FLAT_ICONS))
        return 0
    folder = user_icon_dir()
    os.makedirs(folder, exist_ok=True)
    ours = set(_read_manifest())
    copied = skipped = 0
    try:
        for source in sources:
            name = source.name
            if not _safe_name(name):
                continue
            target = os.path.join(folder, name)
            if os.path.lexists(target) and name not in ours:
                skipped += 1
                continue
            try:
                shutil.copyfile(str(source), target)
            except Exception as exc:
                log("icons: could not copy {}: {}".format(name, exc))
                continue
            ours.add(name)
            copied += 1
    finally:
        # Record what was copied even if something above failed part-way.
        if ours:
            _write_manifest(ours)
    try:
        prefs.set_flat_icons_installed(bool(ours))
    except Exception:
        pass
    log("icons: {} copied to {}, {} left alone (not ours)".format(
        copied, folder, skipped))
    return copied


def restore():
    """Delete the icons this add-on created, then the manifest; return the count."""
    folder = user_icon_dir()
    removed = 0
    remaining = []
    for name in _read_manifest():
        target = os.path.join(folder, name)
        try:
            if os.path.isfile(target) or os.path.islink(target):
                os.remove(target)
                removed += 1
        except Exception as exc:
            log("icons: could not remove {}: {}".format(name, exc))
            remaining.append(name)
    try:
        if remaining:
            _write_manifest(remaining)  # keep track of what is still ours
        elif os.path.exists(manifest_path()):
            os.remove(manifest_path())
    except Exception as exc:
        log("icons: manifest not updated: {}".format(exc))
    try:
        prefs.set_flat_icons_installed(bool(remaining))
    except Exception:
        pass
    log("icons: {} removed from {}".format(removed, folder))
    return removed
