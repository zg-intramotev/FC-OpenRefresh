# -*- coding: utf-8 -*-
"""A working-plane grid that follows the zoom and reaches past the view.

Draft's grid (``gui_trackers.gridTracker``) has a fixed spacing and a fixed
number of lines, both from its preferences. Zoom out and it shrinks to a
small square under the model; zoom in and the lines merge into a smear.

With the AutoScaleGrid preference on, this module sets each visible grid's
spacing and size from its view's camera:

* Spacing steps through 1, 2, 5, 10, 20, 50 ... mm so that minor lines stay
  between MIN_PX and 2.5 x MIN_PX pixels apart.
* The line count is large enough to reach well past the edges of the view,
  measured from the origin, so the grid looks endless. It is rounded up to a
  power of two so panning does not rebuild it every frame.

Draft snaps to the same spacing (``gridTracker.getClosestNode`` reads
``grid.space``), so grid snapping follows the zoom too.

Draft resets the grid from its preferences whenever a command or a working
plane change calls ``grid.set()``. Each grid's ``reset`` is wrapped so the
scaled values come straight back, with no flash of the old size. Turning
the preference off unwraps the grids and resets them.

Every deferred callback is a module-level function.
"""

import functools
import math

import FreeCAD as App

from . import prefs
from .log import log

#: How often the cameras are checked, in milliseconds.
TICK_MS = 120
#: Minor lines are never closer together than this, in pixels.
MIN_PX = 10.0
#: How far past the view the grid reaches, in view diagonals.
REACH = 1.5
#: Upper limit on lines in each direction, so a far pan cannot stall FreeCAD.
MAX_LINES = 2000
#: The spacing steps inside each power of ten.
STEPS = (1.0, 2.0, 5.0)

_timer = []
_logged = set()


def _log_once(msg):
    if msg not in _logged:
        _logged.add(msg)
        log("grid scale: " + msg)


# ------------------------------------------------------------- the maths ---

def spacing_for(world_per_px):
    """Smallest 1/2/5 x 10^n spacing that puts lines MIN_PX pixels apart."""
    target = max(world_per_px * MIN_PX, 1e-9)
    exponent = math.floor(math.log10(target))
    for step in STEPS + (10.0,):
        value = step * 10.0 ** exponent
        if value >= target * (1 - 1e-9):
            return value
    return 10.0 ** (exponent + 1)


def lines_for(needed, mainlines):
    """Round a line count up to 2 x mainlines x 2^k, capped at MAX_LINES."""
    unit = 2 * max(int(mainlines), 1)
    count = unit
    while count < needed and count < MAX_LINES:
        count *= 2
    return min(count, max(unit, MAX_LINES // unit * unit))


def camera_scale(view):
    """(world units per pixel, focal point, view diagonal in pixels)."""
    from pivy import coin
    cam = view.getCameraNode()
    width, height = view.getSize()
    short_side = max(min(width, height), 1)
    if hasattr(cam, "heightAngle"):          # perspective
        visible = 2.0 * cam.focalDistance.getValue() * math.tan(
            cam.heightAngle.getValue() / 2.0)
    else:                                    # orthographic
        visible = cam.height.getValue()
    # Coin fits the camera height to the shorter side of the window.
    world_per_px = visible / short_side
    direction = cam.orientation.getValue().multVec(coin.SbVec3f(0, 0, -1))
    pos = cam.position.getValue()
    dist = cam.focalDistance.getValue()
    focal = App.Vector(pos[0] + direction[0] * dist,
                       pos[1] + direction[1] * dist,
                       pos[2] + direction[2] * dist)
    return world_per_px, focal, math.hypot(width, height)


def target_for(grid, view):
    """(spacing, line count) this grid should have in this view."""
    world_per_px, focal, diagonal = camera_scale(view)
    space = spacing_for(world_per_px)
    local = grid._get_wp().get_local_coords(focal)
    offset = max(abs(local.x), abs(local.y))
    half = offset + REACH * diagonal * world_per_px
    return space, lines_for(2.0 * half / space, grid.mainlines)


# ----------------------------------------------------------- the grids ---

def _apply(grid, space, count):
    if grid.space == space and grid.numlines == count:
        return False
    grid.space = space
    grid.numlines = count
    grid.update()
    try:
        grid.displayHumanFigure(grid._get_wp())   # it sits at the grid corner
    except Exception:
        pass
    return True


def scale(grid, view):
    """Fit one grid to one view now. True when something changed."""
    space, count = target_for(grid, view)
    return _apply(grid, space, count)


def _view_of(grid):
    try:
        import FreeCADGui as Gui
        trackers = Gui.Snapper.trackers
        for view, other in zip(trackers[0], trackers[1]):
            if other is grid:
                return view
    except Exception:
        pass
    return None


def _reset_and_scale(grid, original):
    """Stands in for ``grid.reset``: Draft's reset, then our size."""
    original(grid)
    if not prefs.auto_scale_grid():
        return
    view = _view_of(grid)
    if view is None:
        return
    try:
        scale(grid, view)
    except Exception as exc:
        _log_once("reset: {}".format(exc))


def _wrap(grid):
    if "reset" in grid.__dict__:
        return
    grid.reset = functools.partial(_reset_and_scale, grid, type(grid).reset)


def _unwrap(grid):
    if "reset" not in grid.__dict__:
        return
    del grid.reset
    try:
        grid.reset()                      # back to Draft's own preferences
    except Exception as exc:
        _log_once("unwrap: {}".format(exc))


def _pairs():
    import FreeCADGui as Gui
    snapper = getattr(Gui, "Snapper", None)
    if snapper is None:
        return []
    try:
        return list(zip(snapper.trackers[0], snapper.trackers[1]))
    except Exception:
        return []


def tick():
    """Timer slot: fit every visible grid to its view."""
    try:
        enabled = prefs.auto_scale_grid()
        for view, grid in _pairs():
            if not enabled:
                _unwrap(grid)
                continue
            _wrap(grid)
            if not getattr(grid, "Visible", False):
                continue
            try:
                scale(grid, view)
            except Exception as exc:      # closed view, odd camera
                _log_once("view: {}".format(exc))
    except Exception as exc:
        _log_once("tick: {}".format(exc))


def install():
    """Start the timer once. Cheap when the preference is off."""
    if _timer:
        return
    try:
        import FreeCADGui as Gui
        from PySide import QtCore
        timer = QtCore.QTimer(Gui.getMainWindow())
        timer.setInterval(TICK_MS)
        timer.timeout.connect(tick)
        timer.start()
        _timer.append(timer)
        log("grid scale installed")
    except Exception as exc:
        _log_once("not installed: {}".format(exc))


def toggle():
    new = prefs.toggle_bool(prefs.AUTO_SCALE_GRID)
    tick()
    App.Console.PrintMessage(
        "OpenRefresh: auto-scaling grid is now {}.\n".format("ON" if new else "OFF"))
    return new
