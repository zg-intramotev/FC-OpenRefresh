# Publishing OpenRefresh to the FreeCAD addon index

A checklist for getting OpenRefresh listed in FreeCAD's Addon Manager. It
follows FreeCAD's own process:

- Index for FreeCAD 1.0 and later: <https://github.com/FreeCAD/Addons>
  (the catalog is `Data/Index.json`).
- Guide: <https://freecad.github.io/Addon-Academy/Guides/Publishing/Indexed>

Re-read the guide before submitting; the process may have changed since this
checklist was written.

## Before tagging

Every placeholder below must be replaced. Re-check with
`git grep -n TODO` (or `grep -rn TODO --exclude-dir=.git .`) from the
repository root; this file is the only place `TODO` may remain.

| File | Placeholder | Replace with |
|---|---|---|
| `package.xml` | `<maintainer email="323311894+zg-intramotev@users.noreply.github.com">ZG</maintainer>` | Maintainer's public email (name set: ZG) |
| `package.xml` | `<author email="323311894+zg-intramotev@users.noreply.github.com">ZG</author>` | Author's public email (name set: ZG) |
| `package.xml` | `https://github.com/zg-intramotev/FC-OpenRefresh` (repository, readme and bugtracker URLs) | The real repository owner |
| `README.md` | `https://github.com/zg-intramotev/FC-OpenRefresh/issues` (status note and "Reporting problems") | The real issues URL |
| `README.md` | `https://github.com/zg-intramotev/FC-OpenRefresh.git` (manual install) | The real clone URL |
| `CHANGELOG.md` | `https://github.com/zg-intramotev/FC-OpenRefresh/...` (compare and release links) | The real repository owner |

Also before tagging:

- [ ] `package.xml` `<version>` and `<date>` match the release, and
      `CHANGELOG.md` has a matching section.
- [ ] `package.xml` parses (for example
      `python -c "import xml.etree.ElementTree as E; E.parse('package.xml')"`).
- [ ] Screenshots added under `docs/media/` and linked from `README.md`
      (optional, but listings with screenshots are easier to review).

## Checklist

1. [ ] **Fill in the placeholders** listed under *Before tagging*.
2. [ ] **Make the repository public** (GitHub, or another public git host the
       Addon Manager can clone from), with `package.xml` at the repository
       root and the default branch matching the `branch` attribute in
       `package.xml` (`main`).
3. [ ] **Add the GitHub topics** `freecad` and `addon` to the repository.
4. [ ] **Test with a small group of users first.** The official index is not
       meant for alpha testing (the guide calls it "not suitable for
       alpha-level testing"). Share the manual install instructions from
       `README.md` with a few testers and fix what they find before submitting.
5. [ ] **Run the GUI self-test on Windows and on Linux** against a clean
       FreeCAD 1.1 user profile:

       ```sh
       freecad <repo>/tests/gui_selftest.py
       ```

       It writes `report.json` and screenshots to
       `<user data dir>/openrefresh_selftest/`. Check that the report passes
       and the screenshots look right, then try the setup wizard's
       **Restore my previous settings** and the uninstall steps from
       `README.md`.
6. [ ] **Tag a release** `v0.1.0` (and create a release from the tag, with the
       `CHANGELOG.md` notes).
7. [ ] **Submit** by opening a GitHub issue on
       [FreeCAD/Addons](https://github.com/FreeCAD/Addons/issues) and choosing
       the **"Addon - Addition"** template. Alternatives if you do not use
       GitHub: open an issue on the index's Codeberg mirror, or post in the
       *Addons* subforum of the FreeCAD forum (<https://forum.freecad.org>).
8. [ ] **Wait for review and answer questions.** After the submission is
       approved, OpenRefresh appears in the Addon Manager roughly a day later.
       Install it from the Addon Manager on a clean profile to confirm.
9. [ ] **Keep it maintained.** Watch the issue tracker, test against new
       FreeCAD releases, and bump `<version>`/`<date>` in `package.xml` (plus
       `CHANGELOG.md`) for each release, since the Addon Manager uses the
       manifest to detect updates.
