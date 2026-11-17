# -*- coding: utf-8 -*-
"""Where the add-on's own files are. Paths are relative to this package only."""

from pathlib import Path

#: The package folder, ``.../freecad/openrefresh``.
ROOT = Path(__file__).resolve().parent
RESOURCES = ROOT / "resources"
#: Flat icon sources (SVG), copied into the user icon folder by icons.install().
FLAT_ICONS = RESOURCES / "flat-icons"
ADDON_ICON = RESOURCES / "icons" / "OpenRefresh.svg"
