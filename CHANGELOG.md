# Changelog

All notable changes to OpenRefresh are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- The two-row toolbar is off until you choose it in the setup wizard, where
  it is now the first option. Turning it on takes effect at once, and
  **Restore my previous settings** turns it off and gives FreeCAD's own
  toolbars back at once. FreeCAD's interface is untouched until you opt in.
- Nxt is a recommended add-on instead of a required one. OpenRefresh works
  without it; with it, Nxt's tools get their own group on the bottom row.

## [0.1.0] - 2026-11-17

Initial release. Requires FreeCAD 1.1.0 or later.

### Added

- **New part** (`OpenRefresh_NewPart`, Ctrl+Alt+P) and **New assembly**
  (`OpenRefresh_NewAssembly`, Ctrl+Alt+A): open a new document straight into an
  active Body or Assembly, with the working-plane grid on.
- **Home view** for new documents: isometric, centred on the origin, 150 mm
  tall — for documents from these commands, Ctrl+N and the Start page alike.
- **Show grid** (`OpenRefresh_ShowGrid`, Ctrl+Alt+G), and the grid switched on
  automatically for every new 3D view, including documents created from the
  Start page's Parametric Body tile.
- Optional **auto-body on File → New** (`OpenRefresh_ToggleAutoBody`).
- **Two-row toolbar** (`OpenRefresh_ToggleBand`): a small (16 px) top row with
  file, edit and clipboard controls and the workbench tab bar, and a larger
  (24 px) bottom row with the active workbench's tools grouped into captioned
  panels (Structure, Helpers, Create, Modify, Pattern, Nxt, Inspect),
  re-applied on every workbench switch.
- **Variant dropdowns** in the bottom row: every one of FreeCAD's grouped
  commands keeps its menu (arcs, circles and conics, rectangles, polygons,
  slots, B-splines, dimensions, primitives, datums, view directions, draw
  styles…), plus extra groupings for related commands (Pad / Revolution /
  Loft / Pipe / Helix, Pocket / Groove / …, the patterns, the sketch
  transforms…). A grouped button shows the variant used last. Each one
  carries an opaque ▾ badge, so the arrow stays visible whatever the icon has
  in that corner and whichever theme is active.
- The bottom row keeps FreeCAD's own toolbars hidden even when FreeCAD or the
  Sketcher's edit mode tries to show them, so nothing appears twice; FreeCAD's
  saved toolbar state still says "visible", so removing OpenRefresh never
  leaves toolbars missing.
- **OpenRefresh menu**, placed after File.
- **First-run setup wizard** (`OpenRefresh_Setup`) with opt-in, journaled,
  reversible preference changes: workbench tabs, a trimmed workbench list
  (Part Design, Sketcher, Surface, Assembly, Draft, FEM, CAM), grid everywhere,
  the OpenDark theme (when OpenTheme is installed), the flat icon set and
  auto-body. **Restore my previous settings** undoes all of it.
- Flat icon set: about 380 unmodified CC0 icons from FreeCAD-Flat-Icons
  covering Part, Part Design, Sketcher and the view commands.
- GUI self-test (`tests/gui_selftest.py`) that writes `report.json` and
  screenshots to `<user data dir>/openrefresh_selftest/`.

[Unreleased]: https://github.com/zg-intramotev/FC-OpenRefresh/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/zg-intramotev/FC-OpenRefresh/releases/tag/v0.1.0
