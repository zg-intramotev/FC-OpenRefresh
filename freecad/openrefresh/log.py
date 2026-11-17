# -*- coding: utf-8 -*-
"""The add-on's own log: ``<user dir>/OpenRefresh.log`` plus the Report view.

Start-up errors only reach FreeCAD's Report view, which is easy to miss, so
everything worth knowing is also appended to a plain file. Nothing in here may
raise: a logging failure must never take FreeCAD (or the caller) down.
"""

import os

import FreeCAD as App

FILE_NAME = "OpenRefresh.log"
#: Past this size the old log is moved aside once, at the first write.
MAX_BYTES = 512 * 1024

_checked = []


def path():
    """Full path of the log file, or None if FreeCAD cannot say where."""
    try:
        return os.path.join(App.getUserAppDataDir(), FILE_NAME)
    except Exception:
        return None


def _rotate_once(target):
    if _checked:
        return
    _checked.append(True)
    try:
        if os.path.getsize(target) > MAX_BYTES:
            os.replace(target, target + ".old")
    except Exception:
        pass


def log(msg):
    """Append one line to the log file and to FreeCAD's Report view (log level)."""
    try:
        text = str(msg).rstrip()
    except Exception:
        text = repr(msg)
    try:
        target = path()
        if target:
            _rotate_once(target)
            with open(target, "a", encoding="utf-8") as handle:
                handle.write(text + "\n")
    except Exception:
        pass
    try:
        App.Console.PrintLog("OpenRefresh: {}\n".format(text))
    except Exception:
        pass
