# OpenRefresh

A FreeCAD 1.1 add-on built on [OpenTheme](#built-on) and [Nxt](#built-on):
workbench tabs, a captioned two-row toolbar, and one-key new parts and
assemblies. It sits on top of stock FreeCAD, and every preference it changes is
opt-in and can be undone with one click.

> **Status: experimental (0.x).** Expect rough edges, and please
> [report problems](https://github.com/zg-intramotev/FC-OpenRefresh/issues).

<!-- Screenshots: add images under docs/media/ (for example docs/media/overview.png)
     and link them here once they exist. No images are linked yet on purpose. -->
*Screenshots coming soon (they will live in `docs/media/`).*

## Features

- **New part / New assembly.** Opens a new document straight into an active
  Body or Assembly, with the working-plane grid switched on.
- **A proper home view.** Every new document opens isometric, centred on the
  origin, at a working size of about 150 mm — however it was created.
- **Grid everywhere.** The grid comes on automatically for every new 3D view,
  including documents created from the Start page's *Parametric Body* tile.
  *Show grid* toggles it for the current view.
- **Auto-body on File → New** (optional). A plain new document also gets an
  active Body, ready to sketch.
- **Two-row toolbar.**
  - Top row (small, 16 px): file, edit and clipboard controls, plus the
    workbench **tab bar**.
  - Bottom row (larger, 24 px): the active workbench's tools grouped into
    captioned panels, Fusion-style: *Structure · Helpers · Create · Modify ·
    Pattern · Nxt · Inspect*. The panels are rebuilt every time you switch
    workbench.
  - **Variant dropdowns.** Related commands share a button with a small ▾
    menu: the arc button opens center arc, 3-point arc and the conic arcs;
    Pad opens Revolution, Loft, Pipe and Helix; and so on. The button shows
    whichever variant you used last.
- **OpenRefresh menu** (just after *File*) with all of the commands below.
- **Setup wizard** on first run. Each change is opt-in, recorded in a journal,
  and reversible:
  - workbench tabs;
  - a trimmed workbench list: Part Design, Sketcher, Surface, Assembly, Draft,
    FEM and CAM (every other workbench is one click away through the **+** on
    the tab bar);
  - grid everywhere;
  - the OpenDark theme (only offered if OpenTheme is installed);
  - the flat icon set;
  - auto-body on File → New.

  **Restore my previous settings** in the wizard undoes all of it.

## Commands and shortcuts

| Command | What it does | Shortcut |
|---|---|---|
| New part (`OpenRefresh_NewPart`) | New document with an active Body, isometric, grid on | Ctrl+Alt+P |
| New assembly (`OpenRefresh_NewAssembly`) | New document with an active Assembly, isometric, grid on | Ctrl+Alt+A |
| Show grid (`OpenRefresh_ShowGrid`) | Toggle the working-plane grid in the current view | Ctrl+Alt+G |
| Auto-body on New (`OpenRefresh_ToggleAutoBody`) | Toggle adding a Body to every File → New document | none |
| Two-row toolbar (`OpenRefresh_ToggleBand`) | Turn the two-row toolbar on or off | none |
| Setup (`OpenRefresh_Setup`) | Open the setup wizard (apply or restore settings) | none |

All commands are in the **OpenRefresh** menu. You can change the shortcuts in
*Tools → Customize → Keyboard*.

## Requirements

- FreeCAD **1.1.0 or later** (earlier versions are not supported).
- Python 3.11 or later (bundled with FreeCAD 1.1).
- [Nxt](https://github.com/obelisk79/FreeCAD-Nxt) and
  [OpenTheme](https://github.com/obelisk79/OpenTheme). Both are required; the
  Addon Manager installs them with OpenRefresh. If you install manually,
  install them too (see [Built on](#built-on)).

## Install

### With the Addon Manager (recommended)

Once OpenRefresh is listed in FreeCAD's official addon index:

1. Open *Tools → Addon manager*.
2. Search for **OpenRefresh** and click *Install*.
3. Restart FreeCAD.

### Manually

1. Find your FreeCAD user `Mod` folder. FreeCAD 1.1 keeps add-ons in a
   *versioned* user data folder, for example `%APPDATA%\FreeCAD\v1-1\Mod` on
   Windows, but the exact location differs between systems and installs, so
   check yours rather than assuming: either look at where the Addon Manager
   installs add-ons, or type this in FreeCAD's Python console
   (*View → Panels → Python console*):

   ```python
   FreeCAD.getUserAppDataDir()
   ```

   Your `Mod` folder is the `Mod` subfolder of the path it prints (create it if
   it does not exist).
2. Clone the repository into it:

   ```sh
   cd "<your Mod folder>"
   git clone https://github.com/zg-intramotev/FC-OpenRefresh.git
   ```

3. Restart FreeCAD.

## First run

The first time FreeCAD starts with OpenRefresh installed, the **setup wizard**
opens. Tick the changes you want and apply them; nothing is changed unless you
choose it. You can open the wizard again at any time from the
**OpenRefresh** menu (the Setup command) to apply more changes or restore your
previous settings.

## Uninstall

Do these steps in order so FreeCAD is left exactly as you had it:

1. Open the setup wizard from the **OpenRefresh** menu and choose
   **Restore my previous settings**.
2. Turn the two-row toolbar **off** (its toggle is in the **OpenRefresh** menu).
   While it is on, it hides FreeCAD's own toolbars.
3. Remove OpenRefresh with the Addon Manager (or delete its folder from your
   `Mod` folder if you installed it manually), then restart FreeCAD.

If you removed the add-on without turning the toolbar off first and some
toolbars are missing, switch them back on from *View → Toolbars*.

## Built on

OpenRefresh requires both of these add-ons, by Obelisk79:

- **[OpenTheme](https://github.com/obelisk79/OpenTheme)**: accessible light
  and dark themes based on the open-color palette. The setup wizard switches
  you to OpenDark, which the flat icons are drawn for.
- **[Nxt](https://github.com/obelisk79/FreeCAD-Nxt)**: a model panel, rollback
  history, its own fillet and chamfer, and section views. Its tools get their
  own *Nxt* panel on OpenRefresh's bottom row.

The Addon Manager installs both when you install OpenRefresh.

## Known limitations

- Requires FreeCAD 1.1.0 or later.
- While the two-row toolbar is on, FreeCAD's own toolbars are hidden. Turn it
  off before uninstalling, or restore toolbars from *View → Toolbars*.
- The flat icon set covers about 380 icons (Part, Part Design, Sketcher and the
  view commands). Other workbenches keep their usual icons, and the flat icons
  are drawn for dark themes, so they can look low-contrast on light themes.
- Nxt itself is experimental, and so is OpenRefresh (version 0.x).

## Reporting problems

Please open an issue at <https://github.com/zg-intramotev/FC-OpenRefresh/issues> and
include your FreeCAD version (*Help → About FreeCAD → Copy to clipboard*).

If you can, also run the GUI self-test and attach its results. Start FreeCAD
with the test script from the OpenRefresh folder, for example on Windows:

```sh
freecad.exe "<OpenRefresh folder>\tests\gui_selftest.py"
```

It writes `report.json` and screenshots to an `openrefresh_selftest` folder
inside your FreeCAD user data folder (the path `FreeCAD.getUserAppDataDir()`
prints).

## Licence

- OpenRefresh is licensed under the **GNU Lesser General Public License v2.1 or
  later** (LGPL-2.1-or-later); see [LICENSE](LICENSE).
- The flat icons in `freecad/openrefresh/resources/flat-icons/` are
  **CC0 1.0** (public domain); see that folder's `LICENSE` and `NOTICE.md`.

## Credits

- Flat icons: [FreeCAD-Flat-Icons](https://github.com/obelisk79/FreeCAD-Flat-Icons)
  (CC0 1.0), included unmodified.
- Colours: the [open-color](https://github.com/yeun/open-color) palette.
- Companion projects: [Nxt](https://github.com/obelisk79/FreeCAD-Nxt) and
  [OpenTheme](https://github.com/obelisk79/OpenTheme).
- The FreeCAD project and community: <https://www.freecad.org>.
