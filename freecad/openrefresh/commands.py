# -*- coding: utf-8 -*-
"""Commands, menu, toolbar and shortcuts for OpenRefresh.

Things learned the hard way, kept on purpose:

* FreeCAD builds a command's own QAction only when a workbench lists the
  command, so an add-on with no workbench gets no action - and with no action
  there is no keyboard shortcut. The actions here are built directly, owned
  by the main window with an application-wide shortcut context, and carry
  the shortcuts themselves.
* Ctrl+Shift+P and G,G are already taken by Std_SendToPythonConsole and
  Std_ClarifySelection. Two actions sharing a key means neither fires, hence
  Ctrl+Alt+P / Ctrl+Alt+A / Ctrl+Alt+G.
* FreeCAD rebuilds menus and toolbars after workbenchActivated fires, and
  Nxt re-adds its own button after that, so the menu, toolbar and rows are
  re-applied at 0 ms and the rows once more at 700 ms.
* Every deferred callback is a module-level function in this module.
"""

import functools
import traceback

import FreeCAD as App
import FreeCADGui as Gui

from .log import log

MENU_NAME = "OpenRefreshMenu"
MENU_TITLE = "OpenRefresh"
TOOLBAR_NAME = "OpenRefreshToolbar"
TOOLBAR_TITLE = "OpenRefresh"

#: How many of the commands go on the toolbar (the first ones, in order).
TOOLBAR_COUNT = 3
#: Delay before the first-run check, after the first workbench activation.
FIRST_RUN_DELAY_MS = 1500


# -------------------------------------------------------------- commands ---

class _CmdNewPart:
    def GetResources(self):
        return {
            "Pixmap": "PartDesign_Body",
            "MenuText": "New part",
            "Accel": "Ctrl+Alt+P",
            "ToolTip": "New document with an active, empty PartDesign body and the grid shown",
        }

    def Activated(self):
        from . import workflow
        workflow.new_part()

    def IsActive(self):
        return True


class _CmdNewAssembly:
    def GetResources(self):
        return {
            "Pixmap": "Assembly_CreateAssembly",
            "MenuText": "New assembly",
            "Accel": "Ctrl+Alt+A",
            "ToolTip": "New document with an active, empty assembly and the grid shown",
        }

    def Activated(self):
        from . import workflow
        workflow.new_assembly()

    def IsActive(self):
        return True


class _CmdShowGrid:
    def GetResources(self):
        return {
            "Pixmap": "Draft_Grid",
            "MenuText": "Show grid",
            "Accel": "Ctrl+Alt+G",
            "ToolTip": "Show the working-plane grid in the active 3D view",
        }

    def Activated(self):
        from . import workflow
        workflow.show_grid(True)

    def IsActive(self):
        return True


class _CmdToggleAutoBody:
    def GetResources(self):
        return {
            "Pixmap": "PartDesign_AdditiveBox",
            "MenuText": "Auto-body on new document",
            "ToolTip": "Toggle: give every document created with File > New a body",
        }

    def Activated(self):
        from . import workflow
        workflow.toggle_auto_body()

    def IsActive(self):
        return True


class _CmdToggleBand:
    def GetResources(self):
        return {
            "Pixmap": "preferences-general",
            "MenuText": "Grouped toolbar with captions",
            "ToolTip": "Toggle: show the bottom row as labelled groups, or as "
                       "FreeCAD's own separate toolbars",
        }

    def Activated(self):
        from . import band
        band.toggle()

    def IsActive(self):
        return True


class _CmdSetup:
    def GetResources(self):
        return {
            "Pixmap": "preferences-general",
            "MenuText": "OpenRefresh setup…",
            "ToolTip": "Choose which OpenRefresh features are on: layout, "
                       "captions, icons, grid and auto-body",
        }

    def Activated(self):
        try:
            from . import setup_wizard
            setup_wizard.show()
        except Exception:
            log("setup wizard failed:\n{}".format(traceback.format_exc()))
            try:
                App.Console.PrintError(
                    "OpenRefresh: the setup wizard could not open; see "
                    "OpenRefresh.log in the user data folder.\n")
            except Exception:
                pass

    def IsActive(self):
        return True


COMMANDS = (
    ("OpenRefresh_NewPart", _CmdNewPart()),
    ("OpenRefresh_NewAssembly", _CmdNewAssembly()),
    ("OpenRefresh_ShowGrid", _CmdShowGrid()),
    ("OpenRefresh_ToggleAutoBody", _CmdToggleAutoBody()),
    ("OpenRefresh_ToggleBand", _CmdToggleBand()),
    ("OpenRefresh_Setup", _CmdSetup()),
)

_actions = []
_started = []


# -------------------------------------------------------------------- ui ---

def _run_named(name, *_args):
    """Slot for every action: run the FreeCAD command of that name."""
    try:
        Gui.runCommand(name, 0)
    except Exception:
        log("{} failed:\n{}".format(name, traceback.format_exc()))


def _qaction_class():
    from PySide import QtGui
    cls = getattr(QtGui, "QAction", None)
    if cls is None:  # Qt5 bindings keep QAction in QtWidgets
        from PySide import QtWidgets
        cls = QtWidgets.QAction
    return cls


def _build_actions():
    """One QAction per command, owned by the main window, holding the key."""
    from PySide import QtCore, QtGui
    if _actions:
        return _actions
    mw = Gui.getMainWindow()
    action_class = _qaction_class()
    for name, cmd in COMMANDS:
        res = cmd.GetResources()
        try:
            icon = Gui.getIcon(res["Pixmap"])
        except Exception:
            icon = QtGui.QIcon()
        action = action_class(icon, res["MenuText"], mw)
        action.setObjectName(name)
        action.setToolTip(res.get("ToolTip", ""))
        accel = res.get("Accel")
        if accel:
            action.setShortcut(QtGui.QKeySequence(accel))
            action.setShortcutContext(QtCore.Qt.ApplicationShortcut)
        action.triggered.connect(functools.partial(_run_named, name))
        mw.addAction(action)  # keeps the shortcut live even with no menu
        _actions.append(action)
    log("built {} actions".format(len(_actions)))
    return _actions


def _is_file_menu(action):
    """True for the File menu - by object name first, so translations work."""
    menu = action.menu()
    if menu is not None and menu.objectName() in ("&File", "File"):
        return True
    return (action.text() or "").replace("&", "") == "File"


def _install_menu():
    """Put the OpenRefresh menu back, just after File."""
    from PySide import QtWidgets
    bar = Gui.getMainWindow().menuBar()
    for action in bar.actions():
        menu = action.menu()
        if menu is not None and menu.objectName() == MENU_NAME:
            return  # still there
    menu = QtWidgets.QMenu(MENU_TITLE, bar)
    menu.setObjectName(MENU_NAME)
    actions = _build_actions()
    for index, action in enumerate(actions):
        if action.objectName() == "OpenRefresh_Setup" and index:
            menu.addSeparator()
        menu.addAction(action)
    items = bar.actions()
    after = None
    for index, action in enumerate(items):
        if _is_file_menu(action):
            after = items[index + 1] if index + 1 < len(items) else None
            break
    if after is not None:
        bar.insertMenu(after, menu)
    else:
        bar.addMenu(menu)


def _install_toolbar():
    from PySide import QtWidgets
    mw = Gui.getMainWindow()
    if mw.findChild(QtWidgets.QToolBar, TOOLBAR_NAME) is not None:
        return
    bar = mw.addToolBar(TOOLBAR_TITLE)
    bar.setObjectName(TOOLBAR_NAME)
    for action in _build_actions()[:TOOLBAR_COUNT]:
        bar.addAction(action)


def refresh():
    """Re-add the menu and toolbar; FreeCAD rebuilds both per workbench."""
    try:
        _install_menu()
    except Exception:
        log("menu failed:\n{}".format(traceback.format_exc()))
    try:
        _install_toolbar()
    except Exception:
        log("toolbar failed:\n{}".format(traceback.format_exc()))
    relayout()


def relayout():
    """Just the toolbar rows; cheap enough to run again after everything."""
    try:
        from . import layout
        layout.apply()
    except Exception:
        log("relayout failed:\n{}".format(traceback.format_exc()))


def _later(*_args):
    # FreeCAD rebuilds menus and toolbars after the signal fires, and Nxt
    # re-adds its own button after that, so the rows are laid out twice.
    from PySide import QtCore
    QtCore.QTimer.singleShot(0, refresh)
    QtCore.QTimer.singleShot(700, relayout)


def _maybe_first_run():
    """Deferred: let the setup wizard decide whether to greet a new user."""
    try:
        from . import setup_wizard
        setup_wizard.maybe_show_first_run()
    except Exception:  # ImportError included: the wizard is optional here
        log("first-run check failed:\n{}".format(traceback.format_exc()))


def _first_time():
    try:
        from . import workflow
        workflow.install_observer()
        workflow.install_view_watcher()
    except Exception:
        log("background setup failed:\n{}".format(traceback.format_exc()))
    refresh()
    from PySide import QtCore
    QtCore.QTimer.singleShot(1200, relayout)
    QtCore.QTimer.singleShot(FIRST_RUN_DELAY_MS, _maybe_first_run)
    log("started; shortcuts: " + ", ".join(
        "{}={}".format(a.objectName(), a.shortcut().toString())
        for a in _actions))


def on_workbench(*_args):
    """First workbench activation does the setup; later ones just refresh."""
    if _started:
        try:
            _later()
        except Exception:
            log("refresh not scheduled:\n{}".format(traceback.format_exc()))
        return
    _started.append(True)
    try:
        _first_time()
    except Exception:
        log("start failed:\n{}".format(traceback.format_exc()))


def install():
    """Called from init_gui at start-up."""
    try:
        from . import __version__
    except Exception:
        __version__ = "?"
    log("--- install() {} ---".format(__version__))
    for name, cmd in COMMANDS:
        try:
            Gui.addCommand(name, cmd)
        except Exception:
            log("could not register {}:\n{}".format(name, traceback.format_exc()))
    try:
        mw = Gui.getMainWindow()
        if mw is None:
            log("no main window at load time")
        else:
            mw.workbenchActivated.connect(on_workbench)
            log("connected to workbenchActivated")
    except Exception:
        log("could not connect workbenchActivated:\n{}".format(traceback.format_exc()))
    try:
        from PySide import QtCore
        QtCore.QTimer.singleShot(3000, on_workbench)  # belt and braces
    except Exception:
        log("timer not scheduled:\n{}".format(traceback.format_exc()))
