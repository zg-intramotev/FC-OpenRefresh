# -*- coding: utf-8 -*-
"""Two-row toolbar layout, re-applied on every workbench switch.

Row 1, small icons: the controls that never change - file, undo/redo, the
workbench tabs, macros, the OpenRefresh toolbar.
Row 2, large icons with captions underneath: the workbench's own tools plus
the view and inspection tools. These are the ones reached for while
modelling, so they are bigger (band.py draws the captions).

FreeCAD only inserts a toolbar break when it *creates* a toolbar, so coming
back to a workbench it has already built leaves everything on one row
(ToolBarManager::setup). Re-applying this on workbenchActivated is what keeps
the second row.

Set the TwoRowLayout preference to false and none of this runs: FreeCAD's
toolbars are left exactly where FreeCAD puts them.
"""

import traceback

import FreeCADGui as Gui

from . import band, prefs
from .log import log

#: Toolbars that stay on the top row, in this order.
TOP_ROW = (
    "File",
    "Edit",
    "Clipboard",
    "Workbench",
    "NxtMenuToolbar",
    "Macro",
    "OpenRefreshToolbar",
    "Help",
)

#: Bottom row: these lead, these trail, the workbench's own come between.
BOTTOM_FIRST = ("Structure",)
BOTTOM_LAST = ("NxtTesting", "View", "Individual Views", "Individual views")

TOP_ICON = 16
BOTTOM_ICON = 24


def _all_toolbars(mw):
    """Every toolbar the main window owns in the top area, by name."""
    from PySide import QtCore, QtWidgets
    found = {}
    for toolbar in mw.findChildren(QtWidgets.QToolBar):
        if toolbar.parent() is not mw:
            continue  # lives in the status bar or a menu-bar corner
        area = mw.toolBarArea(toolbar)
        if area not in (QtCore.Qt.TopToolBarArea, QtCore.Qt.NoToolBarArea):
            continue
        name = toolbar.objectName() or toolbar.windowTitle()
        if name:
            found.setdefault(name, toolbar)
    return found


#: Toolbars that belong to no workbench - another add-on's, such as Nxt's -
#: remembered by name because the band hides them and a hidden toolbar can no
#: longer be told apart from one belonging to a workbench that is not active.
_foreign = set()


def _classify(mw):
    """Which toolbar names belong on which row, in order."""
    by_name = _all_toolbars(mw)
    by_name.pop(band.BAND_NAME, None)

    try:
        workbench_order = list(Gui.activeWorkbench().listToolbars())
    except Exception:
        workbench_order = []
    owned = set(workbench_order)

    top = [n for n in TOP_ROW if n in by_name]
    bottom = [n for n in workbench_order
              if n in by_name and n not in TOP_ROW]

    # The active workbench's list is the authority on what belongs on the
    # bottom row: anything else visible is another add-on's and is kept from
    # then on. Without this, toolbars from the workbench visited before would
    # pile up in the band, since the band leaves them hidden.
    for name, toolbar in by_name.items():
        if name in TOP_ROW or name in owned:
            continue
        if not toolbar.isHidden():
            _foreign.add(name)
    for name in sorted(_foreign):
        if name in by_name and name not in bottom:
            bottom.append(name)

    lead = [n for n in BOTTOM_FIRST if n in bottom]
    trail = [n for n in BOTTOM_LAST if n in bottom]
    middle = [n for n in bottom if n not in lead and n not in trail]
    return by_name, top, lead + middle + trail


def arrange():
    """Put every toolbar back where it belongs, in two rows."""
    from PySide import QtCore
    mw = Gui.getMainWindow()
    by_name, top_names, bottom_names = _classify(mw)
    if not top_names or not bottom_names:
        log("layout: not enough toolbars yet; left alone")
        return

    top = [by_name[n] for n in top_names]

    if band.enabled():
        strip = band.build(bottom_names)
        bottom = [strip] if strip is not None else []
    else:
        band.restore()
        bottom = [by_name[n] for n in bottom_names]
    if not bottom:
        return

    # addToolBar() on a toolbar already in that area does not move it, so each
    # one is removed and added back: that appends it at the end, and doing it
    # in order lays the row out in order. removeToolBar() also hides it, hence
    # the setVisible() afterwards. Then one break, before the second row.
    for toolbar in top + bottom:
        mw.removeToolBarBreak(toolbar)
    for toolbar in top + bottom:
        mw.removeToolBar(toolbar)
        mw.addToolBar(QtCore.Qt.TopToolBarArea, toolbar)
        toolbar.setVisible(True)
    mw.insertToolBarBreak(bottom[0])

    size_top = QtCore.QSize(TOP_ICON, TOP_ICON)
    for toolbar in top:
        toolbar.setIconSize(size_top)
    size_bottom = QtCore.QSize(BOTTOM_ICON, BOTTOM_ICON)
    for toolbar in bottom:
        toolbar.setIconSize(size_bottom)

    log("layout: top {} / bottom {}".format(top_names, bottom_names))


def _gl_widget(subwindow):
    from PySide import QtWidgets
    for widget in subwindow.widget().findChildren(QtWidgets.QWidget):
        if "OpenGL" in widget.metaObject().className():
            return widget
    return None


def resync_active_view():
    """Make the 3D view's render size agree with its widget again.

    Reported symptom: sketches drawn ~4% wider than tall, circles as ovals.
    Coin's projection was measured undistorted in a clean window, so the
    suspect is the render viewport going stale when the toolbar area changes
    height under it (the band, or the Sketcher's edit-mode toolbars, adding or
    removing a row). Any mismatch is logged so the log shows when it occurs,
    and a resize event makes the view re-read its size.
    """
    try:
        from PySide import QtGui, QtWidgets
        if Gui.ActiveDocument is None:
            return
        view = Gui.ActiveDocument.ActiveView
        if not hasattr(view, "getSize"):
            return
        mdi = Gui.getMainWindow().findChild(QtWidgets.QMdiArea)
        sub = mdi.activeSubWindow() if mdi is not None else None
        gl = _gl_widget(sub) if sub is not None else None
        if gl is None:
            return
        vw, vh = view.getSize()
        dpr = gl.devicePixelRatioF()
        logical = (gl.width(), gl.height())
        device = (round(gl.width() * dpr), round(gl.height() * dpr))
        if (vw, vh) in (logical, device):
            return
        log("view resync: render {}x{}, widget {}x{} (x{} = {}x{})".format(
            vw, vh, logical[0], logical[1], dpr, device[0], device[1]))
        QtWidgets.QApplication.sendEvent(
            gl, QtGui.QResizeEvent(gl.size(), gl.size()))
        gl.update()
    except Exception:
        log("view resync failed:\n{}".format(traceback.format_exc()))


def schedule_resync():
    from PySide import QtCore
    QtCore.QTimer.singleShot(50, resync_active_view)
    QtCore.QTimer.singleShot(800, resync_active_view)


def apply():
    """Lay out the two rows, unless the TwoRowLayout preference is off."""
    try:
        if not prefs.two_row_layout():
            # Leave FreeCAD's layout alone - but if the band hid toolbars
            # earlier in this session, give them back.
            if band.harvested():
                band.restore()
            return
        arrange()
    except Exception:
        log("layout failed:\n{}".format(traceback.format_exc()))
    try:
        schedule_resync()
    except Exception:
        log("resync not scheduled:\n{}".format(traceback.format_exc()))
