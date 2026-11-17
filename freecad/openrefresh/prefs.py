# -*- coding: utf-8 -*-
"""OpenRefresh's preferences, under BaseApp/Preferences/Mod/OpenRefresh.

Every key has one default, kept in DEFAULTS, so callers never pass their own
and two modules can never disagree about what an unset key means.
"""

import FreeCAD as App

GROUP = "User parameter:BaseApp/Preferences/Mod/OpenRefresh"

SETUP_DONE = "SetupDone"
AUTO_BODY = "AutoBodyOnNewDocument"
SHOW_GRID = "ShowGridOnNewDocument"
BAND_CAPTIONS = "BandCaptions"
TWO_ROW_LAYOUT = "TwoRowLayout"
FLAT_ICONS_INSTALLED = "FlatIconsInstalled"

DEFAULTS = {
    SETUP_DONE: False,
    AUTO_BODY: False,
    SHOW_GRID: True,
    BAND_CAPTIONS: True,
    TWO_ROW_LAYOUT: True,
    FLAT_ICONS_INSTALLED: False,
}


def group():
    """The parameter group itself (created on first use)."""
    return App.ParamGet(GROUP)


def get_bool(key, default=None):
    """Read a boolean; an unset key gives DEFAULTS[key] (or ``default``)."""
    if default is None:
        default = DEFAULTS.get(key, False)
    try:
        return bool(group().GetBool(key, bool(default)))
    except Exception:
        return bool(default)


def set_bool(key, value):
    group().SetBool(key, bool(value))


def toggle_bool(key):
    """Flip a boolean and return the new value."""
    new = not get_bool(key)
    set_bool(key, new)
    return new


# ------------------------------------------------------- typed shorthands ---

def setup_done():
    return get_bool(SETUP_DONE)


def set_setup_done(value=True):
    set_bool(SETUP_DONE, value)


def auto_body():
    return get_bool(AUTO_BODY)


def set_auto_body(value):
    set_bool(AUTO_BODY, value)


def show_grid_on_new():
    return get_bool(SHOW_GRID)


def set_show_grid_on_new(value):
    set_bool(SHOW_GRID, value)


def band_captions():
    return get_bool(BAND_CAPTIONS)


def set_band_captions(value):
    set_bool(BAND_CAPTIONS, value)


def two_row_layout():
    return get_bool(TWO_ROW_LAYOUT)


def set_two_row_layout(value):
    set_bool(TWO_ROW_LAYOUT, value)


def flat_icons_installed():
    return get_bool(FLAT_ICONS_INSTALLED)


def set_flat_icons_installed(value):
    set_bool(FLAT_ICONS_INSTALLED, value)
