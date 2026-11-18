# -*- coding: utf-8 -*-
"""The new-file workflow.

Provides:
  * new_part()      -- new document with an active PartDesign Body + grid
  * new_assembly()  -- new document with an active Assembly + grid
  * show_grid()     -- turn the Draft working-plane grid on in the active view
  * auto-body on plain Ctrl+N (off by default, see prefs.AUTO_BODY)
  * the grid on the first time each 3D view appears (prefs.SHOW_GRID)

Everything here is defensive: a failure must never break FreeCAD start-up.
Every deferred callback is a module-level function, never a lambda or a
bound method handed to a timer.
"""

import FreeCAD as App

from . import prefs
from .log import log

# Set while we create a document ourselves, so the observer keeps its hands off.
_suppress_observer = False


def _warn(msg):
    log(msg)
    try:
        App.Console.PrintWarning("OpenRefresh: {}\n".format(msg))
    except Exception:
        pass


# ---------------------------------------------------------------- grid -----

def _ensure_snapper():
    """Make sure FreeCADGui.Snapper exists (it is created by Draft)."""
    import FreeCADGui as Gui
    if not hasattr(Gui, "Snapper"):
        try:
            import DraftTools  # noqa: F401  (creates Gui.Snapper + draftToolBar)
        except Exception as exc:
            _warn("could not load Draft for the grid: {}".format(exc))
            return None
    return getattr(Gui, "Snapper", None)


def show_grid(on=True):
    """Show (or hide) the Draft working-plane grid in the active 3D view.

    Mirrors what the Draft_ToggleGrid command does, but without toggling.
    """
    snapper = _ensure_snapper()
    if snapper is None:
        return False
    try:
        snapper.setTrackers(update_grid=False)
        grid = snapper.grid
        if not on:
            grid.off()
            grid.show_always = False
            return True
        import WorkingPlane
        grid.set()
        WorkingPlane.get_working_plane()
        grid.show_always = True
        grid.on()
        return True
    except Exception as exc:
        _warn("grid could not be shown: {}".format(exc))
        return False


def grid_visible():
    """True when the active 3D view shows the working-plane grid."""
    import FreeCADGui as Gui
    snapper = getattr(Gui, "Snapper", None)
    if snapper is None:
        return False
    try:
        import Draft
        view = Draft.get3DView()
        views, grids = snapper.trackers[0], snapper.trackers[1]
        if view in views:
            return bool(getattr(grids[views.index(view)], "Visible", False))
    except Exception as exc:
        log("grid state: {}".format(exc))
    return False


def toggle_grid():
    """Hide the grid in the active 3D view if it shows, else show it."""
    on = not grid_visible()
    show_grid(on)
    return on


# ------------------------------------------------------------ view helpers --

#: How much of the model space a new document shows, top to bottom, in mm.
HOME_HEIGHT_MM = 150.0
#: Camera distance from the origin; only matters for clipping and perspective.
HOME_DISTANCE = 1000.0
#: FreeCAD's isometric direction: the camera sits at +X, -Y, +Z and looks
#: back through the origin.
ISO_DIRECTION = (-1.0, 1.0, -1.0)


def _iso_rotation():
    """Camera orientation looking along ISO_DIRECTION with world Z up."""
    from pivy import coin
    import math

    def unit(v):
        n = math.sqrt(sum(c * c for c in v))
        return tuple(c / n for c in v)

    def cross(a, b):
        return (a[1] * b[2] - a[2] * b[1],
                a[2] * b[0] - a[0] * b[2],
                a[0] * b[1] - a[1] * b[0])

    d = unit(ISO_DIRECTION)
    z = tuple(-c for c in d)                 # camera looks down its own -Z
    up = (0.0, 0.0, 1.0)
    dot = sum(u * w for u, w in zip(up, z))
    y = unit(tuple(u - w * dot for u, w in zip(up, z)))
    x = unit(cross(y, z))
    # Coin matrices take row vectors: each row is where a camera axis goes.
    matrix = coin.SbMatrix(x[0], x[1], x[2], 0.0,
                           y[0], y[1], y[2], 0.0,
                           z[0], z[1], z[2], 0.0,
                           0.0, 0.0, 0.0, 1.0)
    return coin.SbRotation(matrix), d


def home_view(view=None):
    """Isometric, centred on the origin, a sensible working size.

    The old version ran fitAll() on an empty part. With nothing to fit,
    FreeCAD framed a few millimetres of nothing a little below the origin,
    so the origin landed off-screen and the zoom was absurd. This sets the
    camera directly instead - and does not call viewIsometric(), whose
    animation would land after these values and overwrite them.
    """
    import math
    import FreeCADGui as Gui
    try:
        view = view or Gui.ActiveDocument.ActiveView
        cam = view.getCameraNode()
        rotation, d = _iso_rotation()
        cam.orientation.setValue(rotation)
        cam.position.setValue(-d[0] * HOME_DISTANCE, -d[1] * HOME_DISTANCE,
                              -d[2] * HOME_DISTANCE)
        cam.focalDistance.setValue(HOME_DISTANCE)
        if hasattr(cam, "height"):           # orthographic
            cam.height.setValue(HOME_HEIGHT_MM)
        elif hasattr(cam, "heightAngle"):    # perspective: frame by distance
            half = math.tan(cam.heightAngle.getValue() / 2.0)
            dist = (HOME_HEIGHT_MM / 2.0) / max(half, 1e-6)
            cam.position.setValue(-d[0] * dist, -d[1] * dist, -d[2] * dist)
            cam.focalDistance.setValue(dist)
    except Exception as exc:
        _warn("home view failed, falling back: {}".format(exc))
        try:
            view.viewIsometric()
        except Exception:
            pass


def _home_view():
    home_view()


def _run_command(name):
    """Run a registered FreeCAD command, return True on success."""
    import FreeCADGui as Gui
    try:
        if name in Gui.listCommands():
            Gui.runCommand(name, 0)
            return True
    except Exception as exc:
        _warn("command {} failed: {}".format(name, exc))
    return False


# --------------------------------------------------------------- builders --

def add_body(doc=None, activate=True):
    """Add a PartDesign Body to doc and make it the active body."""
    import FreeCADGui as Gui
    doc = doc or App.ActiveDocument
    if doc is None:
        return None
    body = doc.addObject("PartDesign::Body", "Body")
    doc.recompute()
    if activate:
        try:
            Gui.ActiveDocument.ActiveView.setActiveObject("pdbody", body)
        except Exception as exc:
            log("could not activate body: {}".format(exc))
    return body


def add_assembly(doc=None):
    """Add an Assembly (with its Joints group) to doc and open it for editing."""
    import FreeCADGui as Gui
    doc = doc or App.ActiveDocument
    if doc is None:
        return None
    assembly = doc.addObject("Assembly::AssemblyObject", "Assembly")
    assembly.Type = "Assembly"
    assembly.newObject("Assembly::JointGroup", "Joints")
    doc.recompute()
    try:
        Gui.ActiveDocument.setEdit(assembly)
    except Exception as exc:
        log("could not activate assembly: {}".format(exc))
    return assembly


def new_part(name="Part"):
    """New document containing an active, empty PartDesign Body."""
    global _suppress_observer
    import FreeCADGui as Gui
    _suppress_observer = True
    try:
        doc = App.newDocument(name)
        Gui.activateWorkbench("PartDesignWorkbench")
        body = add_body(doc)
        show_grid(True)
        _home_view()
        App.Console.PrintMessage(
            "OpenRefresh: new part document ready (body: {}).\n".format(
                getattr(body, "Name", "?")))
        return doc
    finally:
        _suppress_observer = False


def new_assembly(name="Assembly"):
    """New document containing an active, empty Assembly."""
    global _suppress_observer
    import FreeCADGui as Gui
    _suppress_observer = True
    try:
        doc = App.newDocument(name)
        Gui.activateWorkbench("AssemblyWorkbench")
        assembly = add_assembly(doc)
        show_grid(True)
        _home_view()
        App.Console.PrintMessage(
            "OpenRefresh: new assembly document ready ({}).\n".format(
                getattr(assembly, "Name", "?")))
        return doc
    finally:
        _suppress_observer = False


# ------------------------------------------------- observer for plain Ctrl+N

#: Names of documents created since the last deferred pass.
_pending_docs = []


def _decorate_pending():
    """Deferred: give each just-created, still-empty document a body."""
    names = list(_pending_docs)
    del _pending_docs[:]
    for doc_name in names:
        _decorate(doc_name)


def _decorate(doc_name):
    try:
        doc = App.getDocument(doc_name)
    except Exception:
        return
    if doc is None or doc.Objects or doc.FileName:
        return
    try:
        add_body(doc)
        if prefs.show_grid_on_new():
            show_grid(True)
        _home_view()
    except Exception as exc:
        _warn("auto-body failed: {}".format(exc))


class _NewDocumentObserver:
    """Give documents created with File > New a Body and a grid.

    Only acts on a document that is genuinely new: no objects and no file
    name yet. Opening or restoring a file is therefore never touched.
    """

    def slotCreatedDocument(self, doc):
        if _suppress_observer:
            return
        if not prefs.auto_body():
            return
        try:
            from PySide import QtCore
            _pending_docs.append(doc.Name)
            QtCore.QTimer.singleShot(0, _decorate_pending)
        except Exception as exc:
            log("observer could not schedule: {}".format(exc))


_observer = None


def install_observer():
    global _observer
    if _observer is not None:
        return
    _observer = _NewDocumentObserver()
    App.addDocumentObserver(_observer)
    log("document observer installed")


def toggle_auto_body():
    new = not prefs.auto_body()
    prefs.set_auto_body(new)
    App.Console.PrintMessage(
        "OpenRefresh: auto-body on new document is now {}.\n".format(
            "ON" if new else "OFF"))
    return new


# ------------------------------------------------- grid on every 3D view ----
# The Draft grid only exists once Draft has built a tracker for a view, which
# never happens in a PartDesign-only session. This watches for a 3D view
# becoming active and turns the grid on there once - once only, so toggling it
# off with the Show Grid command stays off.

_seen_views = []
_watcher_installed = False


def _grid_for_active_view():
    if not prefs.show_grid_on_new():
        return
    try:
        import FreeCADGui as Gui
        view = Gui.ActiveDocument.ActiveView if Gui.ActiveDocument else None
        if view is None or not hasattr(view, "getCameraNode"):
            return  # not a 3D view (spreadsheet, TechDraw page, start page)
        key = id(view)
        if key in _seen_views:
            return
        _seen_views.append(key)
        del _seen_views[:-32]
        show_grid(True)
        # A brand-new, still-empty document - from Ctrl+Alt+P, Ctrl+N or the
        # Start page's Parametric Body tile - gets the same centred home view.
        # Later, so it lands after FreeCAD's own camera set-up for the view.
        doc = App.ActiveDocument
        if doc is not None and _is_new_and_empty(doc):
            import functools
            from PySide import QtCore
            QtCore.QTimer.singleShot(
                300, functools.partial(_home_if_still_new, doc.Name))
    except Exception as exc:
        log("grid watcher: {}".format(exc))


_DATUMS = ("App::Origin", "App::Line", "App::Plane", "App::Point")


def _is_new_and_empty(doc):
    """Unsaved, and nothing in it has any geometry yet."""
    if doc.FileName:
        return False
    for obj in doc.Objects:
        if obj.TypeId in _DATUMS:
            continue
        shape = getattr(obj, "Shape", None)
        try:
            if shape is not None and not shape.isNull():
                return False
        except Exception:
            return False
    return True


def _home_if_still_new(doc_name):
    try:
        import FreeCADGui as Gui
        doc = App.getDocument(doc_name)
        if doc is None or not _is_new_and_empty(doc):
            return
        gdoc = Gui.getDocument(doc_name)
        home_view(gdoc.ActiveView)
    except Exception as exc:
        log("home view for new document: {}".format(exc))


def _on_subwindow_activated(*_args):
    """MDI signal handler: look at the new view once the event loop is idle."""
    try:
        from PySide import QtCore
        QtCore.QTimer.singleShot(0, _grid_for_active_view)
    except Exception as exc:
        log("grid watcher could not schedule: {}".format(exc))


def install_view_watcher():
    """Turn the grid on the first time each 3D view becomes active."""
    global _watcher_installed
    if _watcher_installed:
        return
    try:
        import FreeCADGui as Gui
        from PySide import QtCore, QtWidgets
        mw = Gui.getMainWindow()
        mdi = mw.findChild(QtWidgets.QMdiArea)
        if mdi is None:
            _warn("no MDI area; grid watcher not installed")
            return
        mdi.subWindowActivated.connect(_on_subwindow_activated)
        _watcher_installed = True
        log("grid watcher installed")
        QtCore.QTimer.singleShot(0, _grid_for_active_view)
    except Exception as exc:
        _warn("grid watcher not installed: {}".format(exc))
