# -*- coding: utf-8 -*-
"""GUI entry point: FreeCAD imports ``freecad.openrefresh.init_gui`` at start-up.

Kept to a few guarded calls. All real code, and every deferred callback,
lives in ordinary modules (commands, workflow, layout, band). Nothing here may
stop FreeCAD from starting, so each step catches everything and reports it.
"""


def _report(what):
    """Log a failure to OpenRefresh.log and the Report view; never raise."""
    import traceback
    text = "OpenRefresh: {}:\n{}".format(what, traceback.format_exc())
    try:
        from .log import log
        log(text)
    except Exception:
        pass
    try:
        import FreeCAD
        FreeCAD.Console.PrintError(text + "\n")
    except Exception:
        pass


try:
    import FreeCADGui as _Gui
    from . import paths as _paths
    if _paths.ADDON_ICON.parent.is_dir():
        _Gui.addIconPath(str(_paths.ADDON_ICON.parent))
except Exception:
    _report("could not add the icon path")

try:
    from . import commands as _commands
    _commands.install()
except Exception:
    _report("failed to load")
