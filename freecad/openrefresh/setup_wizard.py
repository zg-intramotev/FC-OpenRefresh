# -*- coding: utf-8 -*-
"""First-run setup: every change to FreeCAD's own preferences is opt-in.

OpenRefresh never rewrites FreeCAD's preferences on its own. This dialog lists
each change with a one-line explanation; nothing happens until the user
presses Apply, and everything applied can be undone with
"Restore my previous settings".

The undo journal
----------------
Before any value is written, its previous state is recorded in
``<user dir>/OpenRefresh-undo.json``::

    {
      "version": 1,
      "addon": "OpenRefresh",
      "records": [
        {"path": "User parameter:BaseApp/Preferences/Workbenches",
         "key": "Ordered", "type": "str", "existed": true, "old": "..."},
        ...
      ]
    }

``type`` is one of ``bool``, ``int``, ``uint``, ``float``, ``str`` (FreeCAD
keeps each type in its own namespace, so path + key + type identify a value).
Records accumulate across runs and the first record for a value wins, so a
restore always returns to the value from before OpenRefresh first touched it.
``restore_backup()`` replays the records newest first: the old value is set
back, or the key is removed if it did not exist before.

A full copy of the parameters is also exported once, before the first apply,
to ``<user dir>/user.cfg.before-openrefresh`` as a last resort.

Public API: ``maybe_show_first_run()``, ``show(parent=None)``,
``apply(choices) -> list[str]``, ``restore_backup() -> bool``,
``has_backup() -> bool``, ``OPTIONS``.
"""

import datetime
import importlib.util
import json
import os
import xml.etree.ElementTree as ET

import FreeCAD as App

from . import icons, prefs
from .log import log

try:
    from PySide import QtCore, QtGui, QtWidgets  # noqa: F401  (QtGui kept for parity)
except Exception:  # console mode: apply()/restore_backup() still work
    QtCore = QtGui = QtWidgets = None

PREFS = "User parameter:BaseApp/Preferences/"
JOURNAL_NAME = "OpenRefresh-undo.json"
SAFETY_COPY_NAME = "user.cfg.before-openrefresh"
DIALOG_NAME = "OpenRefreshSetupDialog"
DIALOG_TITLE = "OpenRefresh setup"

# ------------------------------------------------------------- the options --

#: Kept as tabs, in tab order.
ENABLED_WORKBENCHES = (
    "PartDesignWorkbench",
    "SketcherWorkbench",
    "SurfaceWorkbench",
    "AssemblyWorkbench",
    "DraftWorkbench",
    "FemWorkbench",
    "CAMWorkbench",
)

#: Hidden from the tab bar; its "+" button still lists every one of them.
DISABLED_WORKBENCHES = (
    "TechDrawWorkbench",
    "SpreadsheetWorkbench",
    "BIMWorkbench",
    "MeshWorkbench",
    "PartWorkbench",
    "InspectionWorkbench",
    "MaterialWorkbench",
    "OpenSCADWorkbench",
    "PointsWorkbench",
    "ReverseEngineeringWorkbench",
    "RobotWorkbench",
    "TestWorkbench",
    "NoneWorkbench",
)

# (path under BaseApp/Preferences, key, type, value)
TABS_VALUES = (
    ("Workbenches", "WorkbenchSelectorType", "int", 1),   # 0 ComboBox, 1 TabBar
    ("Workbenches", "WorkbenchSelectorItem", "int", 0),   # 0 icon+text
)

TRIM_VALUES = (
    ("Workbenches", "Ordered", "str", ",".join(ENABLED_WORKBENCHES)),
    ("Workbenches", "Disabled", "str", ",".join(DISABLED_WORKBENCHES)),
)

GRID_VALUES = (
    ("Mod/Draft", "alwaysShowGrid", "bool", True),
    ("Mod/Draft", "GridHideInOtherWorkbenches", "bool", False),
    ("Mod/Draft", "gridEvery", "int", 10),
    ("Mod/Draft", "gridShowHuman", "bool", False),
    ("Mod/Draft", "coloredGridAxes", "bool", True),
    ("Mod/Draft", "gridBorder", "bool", False),
)

#: id, checkbox label, one-line explanation, default.
#: ``apply()`` takes a dict keyed by these ids.
OPTIONS = (
    ("tabs", "Workbench tabs",
     "Show the workbenches as a row of tabs (icon and text) instead of a "
     "drop-down list. Needs a restart.", True),
    ("trim_workbenches", "Trim the workbench list",
     "Keep Part Design, Sketcher, Surface, Assembly, Draft, FEM and CAM as "
     "tabs. The others stay one click away under the tab bar's “+” "
     "button.", True),
    ("grid", "Grid everywhere",
     "Show the working-plane grid in every workbench, with a heavier line "
     "every 10 squares and coloured origin axes.", True),
    ("theme", "OpenDark theme",
     "Dark colours and stylesheet from the OpenTheme add-on. Needs a "
     "restart.", True),
    ("icons", "Flat icon set",
     "Replace stock toolbar icons with a flat set drawn for dark themes. "
     "Your own icon files are never overwritten. Needs a restart.", True),
    ("autobody", "Auto-body on File → New",
     "Every new document starts with a Part Design Body, ready to sketch "
     "in.", False),
)

#: Options whose effect only shows after FreeCAD restarts.
RESTART_OPTIONS = ("tabs", "trim_workbenches", "theme", "icons")


# --------------------------------------------------------- parameter types --

_GETTERS = {
    "bool": "GetBool", "int": "GetInt", "uint": "GetUnsigned",
    "float": "GetFloat", "str": "GetString",
}
_SETTERS = {
    "bool": "SetBool", "int": "SetInt", "uint": "SetUnsigned",
    "float": "SetFloat", "str": "SetString",
}
_REMOVERS = {
    "bool": "RemBool", "int": "RemInt", "uint": "RemUnsigned",
    "float": "RemFloat", "str": "RemString",
}
_LISTERS = {
    "bool": "GetBools", "int": "GetInts", "uint": "GetUnsigneds",
    "float": "GetFloats", "str": "GetStrings",
}
_CONTENT_TYPES = {
    "bool": "Boolean", "int": "Integer", "uint": "Unsigned",
    "float": "Float", "str": "String",
}
_CFG_TAGS = {
    "FCBool": "bool", "FCInt": "int", "FCUInt": "uint",
    "FCFloat": "float", "FCText": "str",
}


def _coerce(typ, value):
    if typ == "bool":
        return bool(value)
    if typ in ("int", "uint"):
        return int(value)
    if typ == "float":
        return float(value)
    return "" if value is None else str(value)


def _exists(group, key, typ):
    """Whether ``key`` is set in ``group`` as type ``typ``."""
    try:
        return key in list(getattr(group, _LISTERS[typ])())
    except Exception:
        pass
    try:
        for entry in group.GetContents() or ():
            if entry[0] == _CONTENT_TYPES[typ] and entry[1] == key:
                return True
    except Exception:
        pass
    return False


def _get(group, key, typ):
    """(existed, value) for one parameter."""
    if not _exists(group, key, typ):
        return False, None
    try:
        return True, getattr(group, _GETTERS[typ])(key)
    except Exception:
        return True, None


def _set(group, key, typ, value):
    getattr(group, _SETTERS[typ])(key, _coerce(typ, value))


def _remove(group, key, typ):
    getattr(group, _REMOVERS[typ])(key)


# ---------------------------------------------------------- undo journal --

def journal_path():
    return os.path.join(App.getUserAppDataDir(), JOURNAL_NAME)


def _read_journal():
    try:
        with open(journal_path(), "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError:
        return []
    except Exception as exc:
        log("setup: undo journal unreadable ({})".format(exc))
        return []
    records = data.get("records", []) if isinstance(data, dict) else data
    if not isinstance(records, list):
        return []
    good = []
    for rec in records:
        if (isinstance(rec, dict) and isinstance(rec.get("path"), str)
                and rec["path"].startswith("User parameter:")
                and rec["path"] != "User parameter:"
                and isinstance(rec.get("key"), str) and rec["key"]
                and rec.get("type") in _SETTERS):
            good.append(rec)
    return good


def _write_journal(records):
    target = journal_path()
    if not records:
        if os.path.exists(target):
            os.remove(target)
        return
    temp = target + ".tmp"
    data = {
        "version": 1,
        "addon": "OpenRefresh",
        "updated": datetime.datetime.now().isoformat(timespec="seconds"),
        "records": records,
    }
    with open(temp, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=1)
    os.replace(temp, target)


def _record_key(rec):
    return (rec["path"], rec["key"], rec["type"])


def _journal_and_set(changes):
    """Record, then write, a batch of ``(full path, key, type, value)``.

    Only values that actually differ are touched. The journal is on disk
    before the first value is set; if it cannot be written nothing is set.
    Returns the number of values changed.
    """
    groups = {}
    pending = []
    for path, key, typ, value in changes:
        if not key or path == "User parameter:" or typ not in _SETTERS:
            continue
        try:
            value = _coerce(typ, value)
            group = groups.get(path)
            if group is None:
                group = groups[path] = App.ParamGet(path)
            existed, old = _get(group, key, typ)
        except Exception as exc:
            log("setup: skipped {}/{}: {}".format(path, key, exc))
            continue
        if existed and old == value:
            continue
        pending.append((group, path, key, typ, value, existed, old))
    if not pending:
        return 0

    records = _read_journal()
    seen = {_record_key(rec) for rec in records}
    for _group, path, key, typ, _value, existed, old in pending:
        rec = {"path": path, "key": key, "type": typ,
               "existed": bool(existed), "old": old if existed else None}
        if _record_key(rec) not in seen:
            seen.add(_record_key(rec))
            records.append(rec)
    _write_journal(records)  # raises -> nothing below runs

    count = 0
    for group, path, key, typ, value, _existed, _old in pending:
        try:
            _set(group, key, typ, value)
            count += 1
        except Exception as exc:
            log("setup: could not set {}/{}: {}".format(path, key, exc))
    return count


def _apply_values(values):
    """Apply ``(path under BaseApp/Preferences, key, type, value)`` tuples."""
    return _journal_and_set(
        [(PREFS + path, key, typ, value) for path, key, typ, value in values])


def _safety_copy():
    """Export the whole parameter tree once, before OpenRefresh changes it."""
    try:
        target = os.path.join(App.getUserAppDataDir(), SAFETY_COPY_NAME)
        if not os.path.exists(target):
            App.ParamGet("User parameter:BaseApp").Export(target)
            log("setup: safety copy written to {}".format(target))
    except Exception as exc:
        log("setup: safety copy not written ({})".format(exc))


def has_backup():
    """True when there is something for restore_backup() to undo."""
    try:
        if _read_journal():
            return True
    except Exception:
        pass
    try:
        return bool(icons.installed())
    except Exception:
        return False


def restore_backup():
    """Undo everything OpenRefresh applied; True if it all went back.

    Replays the journal newest first, removes the flat icons, clears
    SetupDone (so the dialog is offered again) and deletes the journal.
    Records that could not be restored stay in the journal for a retry.
    """
    ok = True
    records = _read_journal()
    failed = []
    for rec in reversed(records):
        try:
            group = App.ParamGet(rec["path"])
            if rec.get("existed"):
                _set(group, rec["key"], rec["type"], rec.get("old"))
            else:
                _remove(group, rec["key"], rec["type"])
        except Exception as exc:
            ok = False
            failed.insert(0, rec)
            log("setup: could not restore {}/{}: {}".format(
                rec.get("path"), rec.get("key"), exc))
    try:
        _write_journal(failed)
    except Exception as exc:
        ok = False
        log("setup: undo journal not updated ({})".format(exc))

    removed = 0
    try:
        removed = icons.restore()
    except Exception as exc:
        ok = False
        log("setup: icons not restored ({})".format(exc))

    try:
        prefs.group().RemBool(prefs.SETUP_DONE)
    except Exception:
        pass
    _save_parameters()
    log("setup: restored {} preference(s), removed {} icon(s){}".format(
        len(records) - len(failed), removed, "" if ok else " (with errors)"))
    return ok


def _save_parameters():
    try:
        App.saveParameter()
    except Exception as exc:
        log("setup: parameters not saved yet ({})".format(exc))


# ------------------------------------------------------------- cfg merge --

def _set_leaf(path, el, out):
    """Collect one cfg leaf as (path, key, type, value); 1 if usable."""
    name = el.get("Name")
    if not name:
        # Some packs contain a nameless entry; FreeCAD rejects those.
        return 0
    typ = _CFG_TAGS.get(el.tag)
    if typ is None:
        log("setup: unknown cfg element {}".format(el.tag))
        return 0
    if path == "User parameter:":
        # The bare root is not a group; never ParamGet() it.
        return 0
    try:
        if typ == "str":
            value = el.text or ""
        elif typ == "bool":
            value = str(el.get("Value")) in ("1", "true", "True")
        else:
            value = _coerce(typ, el.get("Value"))
    except Exception as exc:
        log("setup: skipped {}/{}: {}".format(path, name, exc))
        return 0
    out.append((path, name, typ, value))
    return 1


def _walk(node, path, out):
    count = 0
    for el in node:
        if el.tag == "FCParamGroup":
            name = el.get("Name")
            if not name:
                continue
            sep = "" if path.endswith(":") else "/"
            count += _walk(el, path + sep + name, out)
        else:
            count += _set_leaf(path, el, out)
    return count


def merge_cfg(cfg_path):
    """Merge a parameter .cfg (a preference pack) into the user parameters.

    Every value is journaled first. Returns the number of values changed.
    """
    root = ET.parse(cfg_path).getroot()
    leaves = []
    for top in root:  # <FCParamGroup Name="Root">
        if top.tag == "FCParamGroup":
            _walk(top, "User parameter:", leaves)
    return _journal_and_set(leaves)


# ------------------------------------------------------- add-on discovery --

def _mod_dirs():
    dirs = []
    try:
        dirs.append(os.path.join(App.getUserAppDataDir(), "Mod"))
    except Exception:
        pass
    try:
        from addonmanager_freecad_interface import DataPaths
        mod_dir = DataPaths().mod_dir
        if mod_dir:
            dirs.append(str(mod_dir))
    except Exception:
        pass
    unique = []
    for d in dirs:
        norm = os.path.normcase(os.path.abspath(d))
        if norm not in [os.path.normcase(os.path.abspath(u)) for u in unique]:
            unique.append(d)
    return unique


def opentheme_cfg():
    """Path of OpenTheme's OpenDark.cfg, or None if OpenTheme is missing."""
    for mod in _mod_dirs():
        cfg = os.path.join(mod, "OpenTheme", "OpenDark", "OpenDark.cfg")
        if os.path.isfile(cfg):
            return cfg
    return None


def nxt_installed():
    try:
        if importlib.util.find_spec("freecad.nxt") is not None:
            return True
    except Exception:
        pass
    return any(os.path.isdir(os.path.join(mod, "FreeCAD-Nxt"))
               for mod in _mod_dirs())


# -------------------------------------------------------------- apply() --

def _report(lines, label, count, note=""):
    if count:
        lines.append("{}: {} preference(s) changed{}".format(label, count, note))
    else:
        lines.append("{}: already set".format(label))


def apply(choices):
    """Apply the chosen options; return a human-readable line per option.

    ``choices`` maps option ids (see OPTIONS) to bools. For every option but
    ``autobody``, False means "leave it alone". ``autobody`` is a plain
    on/off setting and is written either way when given.
    Sets SetupDone. Values that are already right are not touched.
    """
    choices = dict(choices or {})
    lines = []
    _safety_copy()

    restart = " (after a restart)"
    if choices.get("tabs"):
        try:
            _report(lines, "Workbench tabs", _apply_values(TABS_VALUES), restart)
        except Exception as exc:
            lines.append("Workbench tabs: FAILED ({})".format(exc))
    if choices.get("trim_workbenches"):
        try:
            _report(lines, "Workbench list", _apply_values(TRIM_VALUES), restart)
        except Exception as exc:
            lines.append("Workbench list: FAILED ({})".format(exc))
    if choices.get("grid"):
        try:
            _report(lines, "Grid everywhere", _apply_values(GRID_VALUES))
        except Exception as exc:
            lines.append("Grid everywhere: FAILED ({})".format(exc))
    if choices.get("theme"):
        cfg = opentheme_cfg()
        if not cfg:
            lines.append("OpenDark theme: skipped, OpenTheme is not installed")
        else:
            try:
                _report(lines, "OpenDark theme", merge_cfg(cfg), restart)
            except Exception as exc:
                lines.append("OpenDark theme: FAILED ({})".format(exc))
    if choices.get("icons"):
        try:
            count = icons.install()
            if count:
                lines.append("Flat icons: {} icon(s) installed{}".format(count, restart))
            elif icons.installed():
                lines.append("Flat icons: already installed")
            else:
                lines.append("Flat icons: nothing installed (see OpenRefresh.log)")
        except Exception as exc:
            lines.append("Flat icons: FAILED ({})".format(exc))
    if "autobody" in choices:
        try:
            on = bool(choices["autobody"])
            count = _journal_and_set([(prefs.GROUP, prefs.AUTO_BODY, "bool", on)])
            if count:
                lines.append("Auto-body on File → New: {}".format("on" if on else "off"))
        except Exception as exc:
            lines.append("Auto-body: FAILED ({})".format(exc))

    try:
        prefs.set_setup_done(True)
    except Exception as exc:
        log("setup: SetupDone not set ({})".format(exc))
    _save_parameters()
    for line in lines:
        log("setup: " + line)
    return lines


# --------------------------------------------------------------- dialog --

#: Live widgets, so callbacks stay plain module-level functions.
_STATE = {"dialog": None, "boxes": {}}


def _main_window():
    try:
        import FreeCADGui
        return FreeCADGui.getMainWindow()
    except Exception:
        return None


def maybe_show_first_run():
    """Show the setup dialog only if it has not been completed or skipped."""
    try:
        if prefs.setup_done():
            return None
        return show()
    except Exception as exc:
        log("setup: first-run dialog failed ({})".format(exc))
        return None


def show(parent=None):
    """Show the setup dialog (non-modal) and return it."""
    if QtWidgets is None:
        log("setup: no Qt, dialog not shown")
        return None
    dlg = _STATE.get("dialog")
    if dlg is not None:
        try:
            dlg.show()
            dlg.raise_()
            dlg.activateWindow()
            return dlg
        except RuntimeError:  # the C++ side is gone
            _STATE["dialog"] = None
    dlg = _build_dialog(parent if parent is not None else _main_window())
    _STATE["dialog"] = dlg
    dlg.show()
    dlg.raise_()
    return dlg


def _explanation(text):
    label = QtWidgets.QLabel(text)
    label.setWordWrap(True)
    label.setContentsMargins(24, 0, 0, 6)
    font = label.font()
    if font.pointSizeF() > 0:
        font.setPointSizeF(font.pointSizeF() * 0.92)
    label.setFont(font)
    return label


def _get_button(text, name):
    button = QtWidgets.QPushButton(text)
    button.setObjectName(name)
    button.setAutoDefault(False)
    button.clicked.connect(_on_get_addon)
    return button


def _build_dialog(parent):
    dlg = QtWidgets.QDialog(parent)
    dlg.setObjectName(DIALOG_NAME)
    dlg.setWindowTitle(DIALOG_TITLE)
    dlg.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
    dlg.setMinimumWidth(520)

    layout = QtWidgets.QVBoxLayout(dlg)
    intro = QtWidgets.QLabel(
        "Choose what OpenRefresh may change in your FreeCAD preferences. "
        "Nothing changes until you press Apply, and everything can be undone "
        "later with “Restore my previous settings” "
        "(OpenRefresh menu → OpenRefresh setup…).")
    intro.setWordWrap(True)
    layout.addWidget(intro)
    layout.addSpacing(8)

    theme_cfg = opentheme_cfg()
    boxes = {}
    for opt_id, label, text, default in OPTIONS:
        box = QtWidgets.QCheckBox(label)
        box.setObjectName("OpenRefreshSetup_" + opt_id)
        checked = default
        if opt_id == "autobody":
            checked = prefs.auto_body()
        if opt_id == "theme" and not theme_cfg:
            checked = False
            box.setEnabled(False)
        box.setChecked(bool(checked))
        boxes[opt_id] = box
        if opt_id == "theme" and not theme_cfg:
            row = QtWidgets.QHBoxLayout()
            row.addWidget(box)
            row.addStretch(1)
            row.addWidget(_get_button("Get OpenTheme…", "OpenRefreshSetup_GetOpenTheme"))
            layout.addLayout(row)
            layout.addWidget(_explanation(
                text + " OpenTheme is not installed; install it from the "
                "Addon Manager, then open this dialog again."))
        else:
            layout.addWidget(box)
            layout.addWidget(_explanation(text))

    if not nxt_installed():
        layout.addSpacing(4)
        row = QtWidgets.QHBoxLayout()
        info = QtWidgets.QLabel(
            "Tip: OpenRefresh pairs well with the Nxt add-on, which is not "
            "installed.")
        info.setWordWrap(True)
        row.addWidget(info, 1)
        row.addWidget(_get_button("Get Nxt…", "OpenRefreshSetup_GetNxt"))
        layout.addLayout(row)

    layout.addSpacing(8)
    buttons = QtWidgets.QHBoxLayout()
    restore = QtWidgets.QPushButton("Restore my previous settings")
    restore.setObjectName("OpenRefreshSetup_Restore")
    restore.setAutoDefault(False)
    restore.setEnabled(has_backup())
    restore.clicked.connect(_on_restore)
    buttons.addWidget(restore)
    buttons.addStretch(1)
    skip = QtWidgets.QPushButton("Skip")
    skip.setObjectName("OpenRefreshSetup_Skip")
    skip.setAutoDefault(False)
    skip.clicked.connect(_on_skip)
    buttons.addWidget(skip)
    apply_button = QtWidgets.QPushButton("Apply")
    apply_button.setObjectName("OpenRefreshSetup_Apply")
    apply_button.setDefault(True)
    apply_button.clicked.connect(_on_apply)
    buttons.addWidget(apply_button)
    layout.addLayout(buttons)

    _STATE["boxes"] = boxes
    dlg.finished.connect(_on_finished)
    return dlg


def _collect_choices():
    choices = {}
    for opt_id, box in _STATE.get("boxes", {}).items():
        try:
            choices[opt_id] = bool(box.isEnabled() and box.isChecked())
        except RuntimeError:
            pass
    return choices


# ------------------------------------------------- callbacks (module-level) --

def _on_apply(*_args):
    dlg = _STATE.get("dialog")
    choices = _collect_choices()
    try:
        lines = apply(choices)
    except Exception as exc:
        log("setup: apply failed ({})".format(exc))
        QtWidgets.QMessageBox.warning(dlg, DIALOG_TITLE, "Apply failed:\n{}".format(exc))
        return
    text = "\n".join(lines) if lines else "Nothing was selected, so nothing changed."
    if any(choices.get(opt) for opt in RESTART_OPTIONS):
        text += ("\n\nRestart FreeCAD for the workbench tabs, theme and icons "
                 "to take effect.")
    text += ("\n\nTo undo, open OpenRefresh → OpenRefresh setup… and "
             "press “Restore my previous settings”.")
    QtWidgets.QMessageBox.information(dlg, DIALOG_TITLE, text)
    if dlg is not None:
        dlg.accept()


def _on_skip(*_args):
    try:
        prefs.set_setup_done(True)
        _save_parameters()
    except Exception as exc:
        log("setup: SetupDone not set ({})".format(exc))
    log("setup: skipped by the user")
    dlg = _STATE.get("dialog")
    if dlg is not None:
        dlg.reject()


def _on_restore(*_args):
    dlg = _STATE.get("dialog")
    answer = QtWidgets.QMessageBox.question(
        dlg, DIALOG_TITLE,
        "Put back every FreeCAD preference OpenRefresh changed, and remove "
        "its flat icons?",
        QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
        QtWidgets.QMessageBox.No)
    if answer != QtWidgets.QMessageBox.Yes:
        return
    ok = restore_backup()
    if ok:
        text = ("Your previous settings are back. Restart FreeCAD to see the "
                "original workbench selector, theme and icons.")
    else:
        text = ("Most settings were restored, but some could not be. "
                "Details are in OpenRefresh.log in your FreeCAD user folder.")
    QtWidgets.QMessageBox.information(dlg, DIALOG_TITLE, text)
    if dlg is not None:
        dlg.reject()


def _on_get_addon(*_args):
    try:
        import FreeCADGui
        FreeCADGui.runCommand("Std_AddonMgr")
    except Exception as exc:
        log("setup: could not open the Addon Manager ({})".format(exc))


def _on_finished(*_args):
    _STATE["dialog"] = None
    _STATE["boxes"] = {}
