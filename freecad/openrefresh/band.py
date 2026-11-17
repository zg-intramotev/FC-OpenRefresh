# -*- coding: utf-8 -*-
"""The bottom toolbar row as labelled panels.

FreeCAD's workbench toolbars already are the groups - "Part Design Modeling
Features", "Part Design Dress-Up Features" and so on - so each one becomes a
panel: its buttons in a row with the group's name centred underneath. The
panels live in one toolbar (objectName ``OpenRefreshBand``) and the original
toolbars are hidden while it is on.

FreeCAD saves each toolbar's visibility (``BaseApp/MainWindow/Toolbars``,
keyed by toolbar name) on every workbench switch and on close. Left alone, it
would save the toolbars the band hid as hidden, and anyone removing
OpenRefresh would be left without them. So the saved state is kept saying
"visible": after every band build, when the main window is asked to close
(before FreeCAD's own close handler saves state), and at quit. On the next
start the band simply hides them again.
"""

import traceback

import FreeCAD as App
import FreeCADGui as Gui

from . import prefs
from .log import log

BAND_NAME = "OpenRefreshBand"
BAND_TITLE = "Tools"
ENABLED_PREF = prefs.BAND_CAPTIONS
ICON_PX = 24

#: Toolbar name -> the caption under the panel. Anything not listed falls
#: back to _derive_caption().
CAPTIONS = {
    "Structure": "Structure",
    "Part Design Helper Features": "Helpers",
    "Part Design Modeling Features": "Create",
    "Part Design Dress-Up Features": "Modify",
    "Part Design Transformation Features": "Pattern",
    "Part Design Boolean": "Boolean",
    "NxtTesting": "Nxt",
    "View": "Inspect",
    "Individual Views": "Views",
    "Individual views": "Views",
    "Sketcher": "Sketch",
    "Sketcher geometries": "Create",
    "Sketcher constraints": "Constrain",
    "Sketcher tools": "Modify",
    "Sketcher B-spline tools": "B-spline",
    "Sketcher visual": "Visual",
    "Sketcher edit tools": "Edit",
    "Assembly": "Assemble",
    "Assembly Joints": "Joints",
    "Draft creation tools": "Create",
    "Draft modification tools": "Modify",
    "Draft annotation tools": "Annotate",
    "Draft snap": "Snap",
    "Surface": "Surface",
}

#: Words dropped when a caption has to be made up from the toolbar's name.
_NOISE = ("Part Design", "Sketcher", "Assembly", "Draft", "Surface", "FEM",
          "CAM", "Features", "tools", "Tools")

_harvested = []
#: Every toolbar name the band has hidden this session, across workbenches.
_ever_harvested = set()
_guards = []

TOOLBAR_STATE = "User parameter:BaseApp/MainWindow/Toolbars"


def enabled():
    return prefs.band_captions()


def _mark_visible_in_prefs(names):
    """Record the toolbars as visible in FreeCAD's saved state."""
    try:
        group = App.ParamGet(TOOLBAR_STATE)
        for name in names:
            group.SetBool(name, True)
    except Exception:
        log("could not mark toolbars visible:\n{}".format(traceback.format_exc()))


def _show_everything_we_hid():
    """Show every toolbar the band hid, in the widgets and in the prefs."""
    from PySide import QtWidgets
    mw = Gui.getMainWindow()
    if mw is None:
        return
    for toolbar in mw.findChildren(QtWidgets.QToolBar):
        name = toolbar.objectName() or toolbar.windowTitle()
        if name in _harvested:
            toolbar.show()
    _mark_visible_in_prefs(_ever_harvested)


#: True between the main window being asked to close and that close either
#: going through or being refused; the watcher stands down meanwhile.
_closing = []
_watched = set()


def _rehide(name):
    """Hide a toolbar the band owns that something has just shown again."""
    if _closing or not enabled() or name not in _harvested:
        return
    from PySide import QtWidgets
    mw = Gui.getMainWindow()
    if mw is None:
        return
    for toolbar in mw.findChildren(QtWidgets.QToolBar):
        if (toolbar.objectName() or toolbar.windowTitle()) == name:
            if toolbar.isVisible():
                toolbar.hide()
                # The toolbar area just changed height under the 3D view.
                try:
                    from . import layout
                    layout.schedule_resync()
                except Exception:
                    pass


def _on_visibility(name, visible):
    if visible and not _closing:
        import functools
        from PySide import QtCore
        QtCore.QTimer.singleShot(0, functools.partial(_rehide, name))


def _watch(toolbar):
    """Keep this toolbar hidden while the band holds its buttons.

    FreeCAD re-shows toolbars from its saved state on workbench switches, and
    the Sketcher shows its edit-mode toolbars when a sketch is opened. Both
    used to put a second copy of those tools on the top row.
    """
    key = id(toolbar)
    if key in _watched:
        return
    import functools
    name = toolbar.objectName() or toolbar.windowTitle()
    toolbar.visibilityChanged.connect(functools.partial(_on_visibility, name))
    _watched.add(key)


def _rehide_if_close_was_cancelled():
    """The close was refused (an unsaved document, say): put the band back."""
    del _closing[:]
    try:
        mw = Gui.getMainWindow()
        if mw is not None and mw.isVisible():
            from . import commands
            commands.relayout()
    except Exception:
        log("re-hide after cancelled close failed:\n{}".format(
            traceback.format_exc()))


def _on_about_to_quit():
    _mark_visible_in_prefs(_ever_harvested)


def _make_close_guard():
    from PySide import QtCore

    class _CloseGuard(QtCore.QObject):
        """Event filter: runs before the main window's own closeEvent."""

        def eventFilter(self, watched, event):  # noqa: N802 - Qt API
            try:
                if event.type() == QtCore.QEvent.Close:
                    _closing.append(True)
                    _show_everything_we_hid()
                    QtCore.QTimer.singleShot(500, _rehide_if_close_was_cancelled)
            except Exception:
                log("close guard failed:\n{}".format(traceback.format_exc()))
            return False

    return _CloseGuard()


def install_guards():
    """Keep FreeCAD's saved toolbar state safe; idempotent."""
    if _guards:
        return
    try:
        from PySide import QtCore
        mw = Gui.getMainWindow()
        guard = _make_close_guard()
        mw.installEventFilter(guard)
        _guards.append(guard)
        app = QtCore.QCoreApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(_on_about_to_quit)
        log("band: toolbar-state guards installed")
    except Exception:
        log("band guards not installed:\n{}".format(traceback.format_exc()))


def harvested():
    """Names of the toolbars currently folded into the band (and hidden)."""
    return tuple(_harvested)


def _derive_caption(name):
    text = name
    for noise in _NOISE:
        text = text.replace(noise, "")
    text = " ".join(text.split()).strip(" -")
    return text[:1].upper() + text[1:] if text else name


def caption_for(name):
    return CAPTIONS.get(name, _derive_caption(name))


#: Extra dropdowns, on top of the ones FreeCAD already defines (arcs, circles,
#: rectangles, polygons, slots, B-splines, dimensions, primitives, datums,
#: view directions, draw styles...). Leader command -> the commands folded
#: under it. The button shows the leader until a variant is used, then the
#: last one used, as FreeCAD's own groups do. Only commands on the same
#: toolbar are grouped; a command missing from the toolbar is skipped.
GROUPS = {
    # Part Design - Create
    "PartDesign_Pad": ("PartDesign_Pad", "PartDesign_Revolution",
                       "PartDesign_AdditiveLoft", "PartDesign_AdditivePipe",
                       "PartDesign_AdditiveHelix"),
    "PartDesign_Pocket": ("PartDesign_Pocket", "PartDesign_Groove",
                          "PartDesign_SubtractiveLoft",
                          "PartDesign_SubtractivePipe",
                          "PartDesign_SubtractiveHelix"),
    # Part Design - Modify / Pattern / Helpers
    "PartDesign_Draft": ("PartDesign_Draft", "PartDesign_Thickness"),
    "PartDesign_LinearPattern": ("PartDesign_LinearPattern",
                                 "PartDesign_PolarPattern",
                                 "PartDesign_MultiTransform"),
    "PartDesign_SubShapeBinder": ("PartDesign_SubShapeBinder",
                                  "PartDesign_Clone"),
    "Part_CheckGeometry": ("Part_CheckGeometry", "Sketcher_ValidateSketch"),
    # Structure
    "Std_Part": ("Std_Part", "Std_Group", "Std_VarSet"),
    # Inspect (the View toolbar)
    "Std_ViewFitAll": ("Std_ViewFitAll", "Std_ViewFitSelection",
                       "Std_AlignToSelection"),
    # Sketcher, outside edit mode
    "Sketcher_EditSketch": ("Sketcher_EditSketch", "Sketcher_MapSketch",
                            "Sketcher_ReorientSketch"),
    "Sketcher_ValidateSketch": ("Sketcher_ValidateSketch",
                                "Sketcher_MergeSketches",
                                "Sketcher_MirrorSketch"),
    # Sketcher, edit mode
    "Sketcher_CreateLine": ("Sketcher_CreateLine", "Sketcher_CreatePolyline"),
    "Sketcher_ViewSketch": ("Sketcher_ViewSketch", "Sketcher_ViewSection"),
    "Sketcher_Translate": ("Sketcher_Translate", "Sketcher_Rotate",
                           "Sketcher_Scale", "Sketcher_Symmetry",
                           "Sketcher_RemoveAxesAlignment"),
    "Sketcher_BSplineIncreaseDegree": ("Sketcher_BSplineIncreaseDegree",
                                       "Sketcher_BSplineDecreaseDegree",
                                       "Sketcher_BSplineInsertKnot",
                                       "Sketcher_BSplineConvertToNURBS",
                                       "Sketcher_JoinCurves"),
    "Sketcher_SelectConstraints": (
        "Sketcher_SelectConstraints",
        "Sketcher_SelectElementsAssociatedWithConstraints"),
    "Sketcher_ArcOverlay": ("Sketcher_ArcOverlay",
                            "Sketcher_RestoreInternalAlignmentGeometry",
                            "Sketcher_SwitchVirtualSpace"),
}

#: Toolbars left out of the band altogether (and still hidden). Individual
#: Views repeats the view-direction dropdown already in Inspect.
SKIP = ("Individual Views", "Individual views")


def _remember_variant(button, action):
    """A custom group's button shows the variant used last."""
    try:
        button.setDefaultAction(action)
    except Exception:
        pass


def _native_menu(toolbar, action):
    """The variants menu FreeCAD put on this action's button, if any.

    FreeCAD's grouped commands (Sketcher_CompCreateArc and the like) hang
    their menu on the toolbar's QToolButton, not on the QAction, so copying
    the action alone loses it.
    """
    from PySide import QtWidgets
    try:
        widget = toolbar.widgetForAction(action)
    except Exception:
        widget = None
    if isinstance(widget, QtWidgets.QToolButton) and widget.menu() is not None:
        return widget.menu()
    return action.menu()


#: The ▾ badge on buttons that open a variants menu. OpenTheme (like
#: FreeCAD's own stylesheets) draws the arrow transparent, in the button's
#: bottom-right corner, on top of the icon - so on any icon with artwork in
#: that corner the arrow disappears. An opaque badge with its own arrow image
#: reads the same on every icon and under any theme.
BADGE_PX = 11
BADGE_COLOUR = "#495057"        # open-color gray 7
BADGE_HOVER_COLOUR = "#339af0"  # open-color blue 5
_dropdown_qss_cache = []


def _dropdown_qss():
    if not _dropdown_qss_cache:
        from . import paths
        arrow = (paths.RESOURCES / "icons" / "dropdown-arrow.svg").as_posix()
        # The arrow is the badge's own `image`, which Qt draws centred in the
        # badge's content box. The separate ::menu-arrow sub-control is
        # switched off: Qt places that one using the theme's offsets, which
        # left it visibly off-centre inside the badge.
        _dropdown_qss_cache.append(
            "QToolButton { padding-right: 3px; }"
            "QToolButton::menu-button {"
            " subcontrol-origin: padding; subcontrol-position: right bottom;"
            " width: %dpx; height: %dpx; padding: 1px; margin: 0px;"
            " border: none; border-radius: 3px;"
            " background-color: %s;"
            " image: url(\"%s\"); image-position: center; }"
            "QToolButton::menu-button:hover { background-color: %s; }"
            "QToolButton::menu-arrow { image: none; width: 0px; height: 0px; }"
            % (BADGE_PX, BADGE_PX, BADGE_COLOUR, arrow, BADGE_HOVER_COLOUR))
    return _dropdown_qss_cache[0]


def _button(row, action, menu=None, group_actions=None):
    import functools
    from PySide import QtCore, QtWidgets
    button = QtWidgets.QToolButton(row)
    button.setDefaultAction(action)
    button.setIconSize(QtCore.QSize(ICON_PX, ICON_PX))
    button.setAutoRaise(True)
    if group_actions:
        menu = QtWidgets.QMenu(button)
        for member in group_actions:
            menu.addAction(member)
        menu.triggered.connect(functools.partial(_remember_variant, button))
    if menu is not None:
        button.setMenu(menu)
        button.setPopupMode(QtWidgets.QToolButton.MenuButtonPopup)
        button.setStyleSheet(_dropdown_qss())
    return button


def _panel(caption, toolbar, parent):
    """One group: a row of buttons with the group's name underneath."""
    from PySide import QtCore, QtWidgets

    box = QtWidgets.QWidget(parent)
    column = QtWidgets.QVBoxLayout(box)
    column.setContentsMargins(3, 0, 3, 0)
    column.setSpacing(0)

    row = QtWidgets.QWidget(box)
    line = QtWidgets.QHBoxLayout(row)
    line.setContentsMargins(0, 0, 0, 0)
    line.setSpacing(1)

    actions = toolbar.actions()
    by_name = {a.objectName(): a for a in actions if a.objectName()}
    # Commands folded into a custom group, other than each group's leader.
    folded = set()
    groups = {}
    for leader, members in GROUPS.items():
        present = [by_name[m] for m in members if m in by_name]
        if leader in by_name and len(present) > 1:
            groups[leader] = present
            folded.update(m for m in members if m != leader)

    buttons = 0
    for action in actions:
        if action.isSeparator():
            rule = QtWidgets.QFrame(row)
            rule.setFrameShape(QtWidgets.QFrame.VLine)
            rule.setFrameShadow(QtWidgets.QFrame.Plain)
            rule.setEnabled(False)
            line.addWidget(rule)
            continue
        name = action.objectName()
        if name in folded or not action.isVisible():
            continue
        if name in groups:
            button = _button(row, action, group_actions=groups[name])
        else:
            button = _button(row, action, menu=_native_menu(toolbar, action))
        line.addWidget(button)
        buttons += 1
    if not buttons:
        box.deleteLater()
        return None
    # No stretch: the panel must hug its buttons, or the row runs off the
    # right-hand edge and the last groups vanish into the overflow menu.
    column.addWidget(row)

    label = QtWidgets.QLabel(caption, box)
    label.setAlignment(QtCore.Qt.AlignHCenter | QtCore.Qt.AlignTop)
    font = label.font()
    font.setPointSizeF(max(6.5, font.pointSizeF() - 1.5))
    label.setFont(font)
    label.setEnabled(False)  # dimmed by the theme, whichever theme it is
    column.addWidget(label)
    return box


def _workbench_toolbars(mw):
    """The toolbars of the active workbench, in its own order."""
    from PySide import QtWidgets
    names = []
    try:
        names = list(Gui.activeWorkbench().listToolbars())
    except Exception:
        names = []
    found = {}
    for toolbar in mw.findChildren(QtWidgets.QToolBar):
        if toolbar.parent() is mw:
            found.setdefault(toolbar.objectName() or toolbar.windowTitle(),
                             toolbar)
    return names, found


def build(bottom_names):
    """(Re)fill the band from the named toolbars and hide those toolbars."""
    from PySide import QtCore, QtWidgets
    mw = Gui.getMainWindow()

    band = mw.findChild(QtWidgets.QToolBar, BAND_NAME)
    if band is None:
        band = mw.addToolBar(BAND_TITLE)
        band.setObjectName(BAND_NAME)
        band.setMovable(False)
    band.clear()
    band.setIconSize(QtCore.QSize(ICON_PX, ICON_PX))

    _, found = _workbench_toolbars(mw)
    del _harvested[:]
    panels = 0
    for name in bottom_names:
        toolbar = found.get(name)
        if toolbar is None or toolbar is band:
            continue
        if name not in SKIP:
            panel = _panel(caption_for(name), toolbar, band)
            if panel is None:
                continue
            if panels:
                band.addSeparator()
            band.addWidget(panel)
            panels += 1
        toolbar.hide()
        _watch(toolbar)
        _harvested.append(name)
        _ever_harvested.add(name)
    # FreeCAD saved toolbar visibility just before this workbench switch;
    # whatever it recorded for these, the saved state must say visible.
    _mark_visible_in_prefs(_ever_harvested)
    install_guards()
    log("band: {} panels from {}".format(panels, _harvested))
    return band if panels else None


def restore():
    """Show the original toolbars again and drop the band."""
    from PySide import QtWidgets
    mw = Gui.getMainWindow()
    _, found = _workbench_toolbars(mw)
    for name in _harvested:
        toolbar = found.get(name)
        if toolbar is not None:
            toolbar.show()
    band = mw.findChild(QtWidgets.QToolBar, BAND_NAME)
    if band is not None:
        band.clear()
        band.hide()
    log("band: restored {} toolbars".format(len(_harvested)))
    del _harvested[:]


def toggle():
    new = not prefs.band_captions()
    prefs.set_band_captions(new)
    App.Console.PrintMessage(
        "OpenRefresh: grouped toolbar captions {}. Switch workbench to "
        "redraw.\n".format("ON" if new else "OFF"))
    try:
        if new:
            from . import commands
            commands.relayout()
        else:
            restore()
    except Exception:
        log("toggle failed:\n{}".format(traceback.format_exc()))
    return new
