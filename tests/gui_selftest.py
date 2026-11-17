# -*- coding: utf-8 -*-
"""GUI self-test for OpenRefresh. Run it from the GUI binary, with FreeCAD
otherwise closed:

    freecad.exe <path to>/tests/gui_selftest.py
    freecad.exe <path to>/tests/gui_selftest.py --keep-open

It waits for start-up, checks that the add-on loaded (commands, shortcuts,
menu, two-row toolbar), runs New Part and New Assembly, switches workbench
and back, then writes screenshots and ``report.json`` (top-level
``"passed": true/false``) to ``<user dir>/openrefresh_selftest/``. Documents
it created are closed without saving and FreeCAD quits, unless
``--keep-open`` is given.

It never opens the setup dialog; if the first-run dialog is showing it is
dismissed with reject(), which does not mark setup as done.
"""

import json
import os
import sys
import time

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets

OUT = os.path.join(App.getUserAppDataDir(), "openrefresh_selftest")
if not os.path.isdir(OUT):
    os.makedirs(OUT)

STARTUP_DELAY_MS = 16000
WATCHDOG_MS = 180000

COMMANDS = (
    "OpenRefresh_NewPart",
    "OpenRefresh_NewAssembly",
    "OpenRefresh_ShowGrid",
    "OpenRefresh_ToggleAutoBody",
    "OpenRefresh_ToggleBand",
    "OpenRefresh_Setup",
)

SHORTCUTS = (
    ("Ctrl+Alt+P", "OpenRefresh_NewPart"),
    ("Ctrl+Alt+A", "OpenRefresh_NewAssembly"),
    ("Ctrl+Alt+G", "OpenRefresh_ShowGrid"),
)

BAND_NAME = "OpenRefreshBand"
SETUP_DIALOG_NAME = "OpenRefreshSetupDialog"
SETUP_DIALOG_TITLE = "OpenRefresh setup"
ROW_TOLERANCE_PX = 6

report = {
    "passed": False,
    "started": time.strftime("%Y-%m-%d %H:%M:%S"),
    "freecad": ".".join(App.Version()[:3]),
    "steps": [],
    "checks": {},
    "info": {},
}
state = {"finished": False, "docs_before": [], "workbench_before": None}


# ------------------------------------------------------------- helpers --

def check(name, ok, detail=None, skipped=False):
    entry = {"ok": bool(ok), "detail": detail}
    if skipped:
        entry["skipped"] = True
    report["checks"][name] = entry
    App.Console.PrintMessage("SELFTEST {} {}: {}\n".format(
        "SKIP" if skipped else ("ok  " if ok else "FAIL"), name, detail))


def note(key, value):
    report["info"][key] = value
    App.Console.PrintMessage("SELFTEST {}: {}\n".format(key, value))


def grab(tag):
    try:
        path = os.path.join(OUT, tag + ".png")
        Gui.getMainWindow().grab().save(path)
        return path
    except Exception as exc:
        return "grab failed: {!r}".format(exc)


def open_dialogs():
    out = []
    try:
        for w in QtWidgets.QApplication.topLevelWidgets():
            if w.isVisible() and isinstance(w, QtWidgets.QDialog):
                out.append("{} | {}".format(w.objectName(), w.windowTitle()))
    except Exception as exc:
        out.append("scan failed: {!r}".format(exc))
    return out


def close_setup_dialog():
    """Dismiss the first-run dialog if it is up; return how many were closed."""
    closed = 0
    try:
        for w in QtWidgets.QApplication.topLevelWidgets():
            if not isinstance(w, QtWidgets.QDialog) or not w.isVisible():
                continue
            if w.objectName() == SETUP_DIALOG_NAME or w.windowTitle() == SETUP_DIALOG_TITLE:
                w.reject()
                closed += 1
    except Exception as exc:
        App.Console.PrintWarning("SELFTEST setup dialog scan failed: {!r}\n".format(exc))
    return closed


def action_class():
    cls = getattr(QtGui, "QAction", None)
    if cls is None:
        cls = getattr(QtWidgets, "QAction", None)
    return cls


def all_actions():
    cls = action_class()
    if cls is None:
        return []
    return list(Gui.getMainWindow().findChildren(cls))


def portable(seq):
    try:
        return seq.toString(QtGui.QKeySequence.PortableText)
    except Exception:
        return str(seq.toString())


def toolbar_rows():
    """Visible top-area toolbars as rows: [[(x, name), ...], ...] top to bottom."""
    mw = Gui.getMainWindow()
    items = []
    seen = set()
    for tb in mw.findChildren(QtWidgets.QToolBar):
        try:
            if tb.parent() is not mw or not tb.isVisible() or tb.isFloating():
                continue
            if mw.toolBarArea(tb) != QtCore.Qt.TopToolBarArea:
                continue
        except Exception:
            continue
        pos = tb.mapTo(mw, QtCore.QPoint(0, 0))
        name = tb.objectName() or tb.windowTitle() or "<unnamed>"
        items.append((pos.y(), pos.x(), name))
        seen.add(name)
    if BAND_NAME not in seen:
        # The band may be a plain widget rather than a QToolBar.
        band = mw.findChild(QtWidgets.QWidget, BAND_NAME)
        if band is not None and band.isVisible():
            pos = band.mapTo(mw, QtCore.QPoint(0, 0))
            items.append((pos.y(), pos.x(), BAND_NAME))
    items.sort()
    rows = []
    row_y = None
    for y, x, name in items:
        if row_y is None or y - row_y > ROW_TOLERANCE_PX:
            rows.append({"y": y, "bars": []})
            row_y = y
        rows[-1]["bars"].append((x, name))
    for row in rows:
        row["bars"].sort()
    return [{"y": r["y"], "bars": [name for _x, name in r["bars"]]} for r in rows]


def two_row_layout_expected():
    try:
        return bool(App.ParamGet(
            "User parameter:BaseApp/Preferences/Mod/OpenRefresh").GetBool("TwoRowLayout", True))
    except Exception:
        return True


def check_rows(tag):
    rows = toolbar_rows()
    note("toolbar_rows_" + tag, rows)
    if not two_row_layout_expected():
        check("two_rows_" + tag, True, "TwoRowLayout is off", skipped=True)
        return
    ok = len(rows) == 2 and BAND_NAME in rows[1]["bars"]
    check("two_rows_" + tag, ok,
          "{} row(s); band in row {}".format(
              len(rows),
              next((i + 1 for i, r in enumerate(rows) if BAND_NAME in r["bars"]), None)))


def new_documents():
    return [name for name in App.listDocuments() if name not in state["docs_before"]]


def type_ids(doc):
    return [o.TypeId for o in doc.Objects] if doc else []


def write_report():
    checks = report["checks"]
    report["passed"] = bool(checks) and all(c["ok"] for c in checks.values())
    report["failed"] = sorted(name for name, c in checks.items() if not c["ok"])
    report["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(os.path.join(OUT, "report.json"), "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
    except Exception as exc:
        App.Console.PrintError("SELFTEST report not written: {!r}\n".format(exc))
    App.Console.PrintMessage("SELFTEST {}: report in {}\n".format(
        "PASSED" if report["passed"] else "FAILED", OUT))


def guarded(step_name, func):
    """Run one step; an exception becomes a failed check, never a stopped chain."""
    report["steps"].append(step_name)
    try:
        func()
    except Exception as exc:
        check("step_" + step_name, False, "raised {!r}".format(exc))


# --------------------------------------------------------------- steps --

def step1_startup():
    guarded("startup", _startup)
    QtCore.QTimer.singleShot(1000, step2_new_part)


def _startup():
    mw = Gui.getMainWindow()
    note("setup_dialogs_closed", close_setup_dialog())
    note("dialogs_at_startup", open_dialogs())
    state["docs_before"] = list(App.listDocuments())
    wb = Gui.activeWorkbench()
    state["workbench_before"] = wb.name() if wb else None
    note("workbench_at_startup", state["workbench_before"])

    loaded = "freecad.openrefresh" in sys.modules
    check("package_imported", loaded,
          sorted(m for m in sys.modules if m.startswith("freecad.openrefresh")))

    known = set(Gui.listCommands())
    missing = [c for c in COMMANDS if c not in known]
    check("commands_registered", not missing, {"missing": missing})

    actions = all_actions()
    by_name = {}
    for act in actions:
        by_name.setdefault(act.objectName(), []).append(act)
    for keys, command in SHORTCUTS:
        wanted = portable(QtGui.QKeySequence(keys))
        owners = []
        for act in actions:
            try:
                seqs = [portable(s) for s in act.shortcuts()] or [portable(act.shortcut())]
            except Exception:
                seqs = [portable(act.shortcut())]
            if wanted in seqs:
                owners.append(act.objectName() or act.text())
        found = command in by_name
        ok = found and owners == [command]
        check("shortcut_" + keys, ok,
              {"command_action_found": found, "owners": owners})

    menus = [a.text().replace("&", "") for a in mw.menuBar().actions()]
    note("menus", menus)
    check("menu_present", "OpenRefresh" in menus, menus)

    check_rows("startup")
    note("shot_startup", grab("01_startup"))


def step2_new_part():
    guarded("new_part", _new_part)
    QtCore.QTimer.singleShot(3000, step3_check_part)


def _new_part():
    close_setup_dialog()
    Gui.runCommand("OpenRefresh_NewPart")


def step3_check_part():
    guarded("check_part", _check_part)
    QtCore.QTimer.singleShot(1500, step4_switch_away)


def _check_part():
    doc = App.ActiveDocument
    ids = type_ids(doc)
    note("part_objects", ids)
    check("new_part_body", doc is not None and doc.Name in new_documents()
          and "PartDesign::Body" in ids, doc.Name if doc else None)
    try:
        visible = bool(Gui.Snapper.grid.Visible)
        check("grid_visible", visible, visible)
    except Exception as exc:
        check("grid_visible", False, "no snapper grid {!r}".format(exc))
    wb = Gui.activeWorkbench()
    state["workbench_before"] = wb.name() if wb else state["workbench_before"]
    note("workbench_after_new_part", state["workbench_before"])
    note("shot_part", grab("02_new_part"))
    check_home_view()


def check_home_view():
    """A new part opens centred on the origin (regression: it used to land
    off-screen, after fitAll() on an empty part framed ~4 mm of nothing)."""
    try:
        view = Gui.ActiveDocument.ActiveView
        width, height = view.getSize()
        get = getattr(view, "getPointOnScreen", None) or view.getPointOnViewport
        ox, oy = get(App.Vector(0, 0, 0))
        off = max(abs(ox - width / 2.0) / width, abs(oy - height / 2.0) / height)
        check("home_view_centred", off < 0.05,
              "origin at ({}, {}) in {}x{}".format(ox, oy, width, height))
    except Exception as exc:
        check("home_view_centred", False, repr(exc))


def check_sketch_edit():
    """While a sketch is open: the top row holds only the fixed controls
    (regression: the Sketcher's edit toolbars landed there as duplicates),
    and the band keeps FreeCAD's variant menus (regression: the arc button
    lost its 3-point arc and the rest)."""
    try:
        from freecad.openrefresh import layout as or_layout
        allowed = set(or_layout.TOP_ROW)
    except Exception:
        allowed = set()
    rows = toolbar_rows()
    note("toolbar_rows_sketch_edit", rows)
    top = rows[0]["bars"] if rows else []
    extra = [n for n in top if n not in allowed]
    check("top_row_clean_in_sketch_edit", bool(rows) and not extra,
          "unexpected on row 1: {}".format(extra) if extra else "ok")
    mw = Gui.getMainWindow()
    band = mw.findChild(QtWidgets.QToolBar, BAND_NAME)
    variants = []
    if band is not None:
        for button in band.findChildren(QtWidgets.QToolButton):
            action = button.defaultAction()
            if action is None or button.menu() is None:
                continue
            names = [a.objectName() for a in button.menu().actions()]
            if "Sketcher_Create3PointArc" in names:
                variants = names
    check("arc_variants_in_band", "Sketcher_Create3PointArc" in variants,
          variants or "no button carrying the arc variants")
    note("shot_sketch_edit", grab("03b_sketch_edit"))


def step4_switch_away():
    guarded("switch_to_sketcher", _switch_away)
    QtCore.QTimer.singleShot(2500, step5_switch_back)


def _switch_away():
    Gui.activateWorkbench("SketcherWorkbench")
    # Open a sketch: entering edit mode is what makes the Sketcher show its
    # edit toolbars, which is where the duplicate-toolbar bug lived.
    import Part
    doc = App.ActiveDocument
    bodies = [o for o in doc.Objects if o.TypeId == "PartDesign::Body"]
    if not bodies:
        return
    sketch = bodies[0].newObject("Sketcher::SketchObject", "SelfTestSketch")
    sketch.AttachmentSupport = [(doc.getObject("XY_Plane"), "")]
    sketch.MapMode = "FlatFace"
    sketch.addGeometry(Part.Circle(App.Vector(0, 0, 0), App.Vector(0, 0, 1), 40), False)
    doc.recompute()
    Gui.ActiveDocument.setEdit(sketch.Name)
    state["sketch_open"] = True


def step5_switch_back():
    guarded("switch_back", _switch_back)
    QtCore.QTimer.singleShot(2500, step6_new_assembly)


def _switch_back():
    note("toolbar_rows_sketcher", toolbar_rows())
    note("shot_sketcher", grab("03_sketcher"))
    if state.get("sketch_open"):
        check_sketch_edit()
        try:
            Gui.ActiveDocument.resetEdit()
        except Exception:
            pass
    else:
        check("top_row_clean_in_sketch_edit", False, "could not open a sketch")
    back = state["workbench_before"] or "PartDesignWorkbench"
    if back == "SketcherWorkbench":
        back = "PartDesignWorkbench"
    Gui.activateWorkbench(back)


def step6_new_assembly():
    guarded("new_assembly", _new_assembly)
    QtCore.QTimer.singleShot(3500, step7_finish)


def _new_assembly():
    check_rows("after_switch")
    note("shot_switched_back", grab("04_switched_back"))
    close_setup_dialog()
    Gui.runCommand("OpenRefresh_NewAssembly")


def step7_finish():
    guarded("finish", _finish)
    state["finished"] = True
    write_report()
    shutdown()


def _finish():
    doc = App.ActiveDocument
    ids = type_ids(doc)
    note("assembly_objects", ids)
    check("new_assembly_object", "Assembly::AssemblyObject" in ids,
          doc.Name if doc else None)
    note("shot_assembly", grab("05_new_assembly"))
    note("dialogs_at_end", open_dialogs())
    still_open = close_setup_dialog()
    check("setup_dialog_not_left_open", still_open == 0,
          "{} setup dialog(s) were open at the end".format(still_open))


def watchdog():
    if state["finished"]:
        return
    check("finished_in_time", False, "watchdog fired after {} s".format(WATCHDOG_MS // 1000))
    state["finished"] = True
    write_report()
    shutdown()


def shutdown():
    if "--keep-open" in list(QtCore.QCoreApplication.arguments()):
        return
    for name in new_documents():
        try:
            App.closeDocument(name)
        except Exception:
            pass
    QtCore.QTimer.singleShot(500, QtWidgets.QApplication.quit)


QtCore.QTimer.singleShot(STARTUP_DELAY_MS, step1_startup)
QtCore.QTimer.singleShot(WATCHDOG_MS, watchdog)
App.Console.PrintMessage("SELFTEST: scheduled, output goes to {}\n".format(OUT))
