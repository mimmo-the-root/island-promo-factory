import sys as _sys; from pathlib import Path as _P; _sys.path.insert(0, str(_P(__file__).resolve().parent))  # embedded python ignores script dir
"""Maintainer helper for versions (not needed to USE the tool).

  release.py check [--tag vX.Y.Z]   VERSION is semver, CHANGELOG's top entry matches it, optional tag matches (used by CI)
  release.py bump patch|minor|major  raise VERSION and add an empty CHANGELOG entry to fill in
  release.py notes [X.Y.Z]           print that version's CHANGELOG section (default: current); CI uses it for the release text
  release.py ship                    print the exact git commands for the current version
Scheme: VERSION "X.Y.Z" -> commit "vX.Y.Z: summary" -> tag "vX.Y.Z" -> GitHub Release (built by CI from the tag).
"""
import re
import sys
from pathlib import Path

import version as V

ROOT = V.ROOT


def top_entry():
    secs = V.changelog_sections((ROOT / "CHANGELOG.md").read_text(encoding="utf-8"))
    return secs[0] if secs else None


def cmd_check(args):
    ver = V.read_version()
    problems = []
    if not V.SEMVER.match((ROOT / "VERSION").read_text(encoding="utf-8").strip() if (ROOT / "VERSION").exists() else ""):
        problems.append("VERSION is missing or not X.Y.Z")
    top = top_entry()
    if top is None:
        problems.append("CHANGELOG.md has no '## vX.Y.Z - title' entry")
    elif top[0] != ver:
        problems.append("CHANGELOG top entry is v%s but VERSION is %s" % (top[0], ver))
    elif not top[2].strip():
        problems.append("CHANGELOG entry v%s is empty" % ver)
    if "--tag" in args:
        tag = args[args.index("--tag") + 1]
        if tag != "v" + ver:
            problems.append("tag %s does not match VERSION %s" % (tag, ver))
    if problems:
        print("VERSION CHECK FAILED:")
        for p in problems:
            print(" - " + p)
        sys.exit(1)
    print("version check OK: v%s" % ver)


def cmd_bump(args):
    kind = args[0] if args else ""
    if kind not in ("patch", "minor", "major"):
        sys.exit("usage: release.py bump patch|minor|major")
    a, b, c = V.parse(V.read_version())
    new = {"patch": (a, b, c + 1), "minor": (a, b + 1, 0), "major": (a + 1, 0, 0)}[kind]
    ver = "%d.%d.%d" % new
    (ROOT / "VERSION").write_text(ver + "\n", encoding="utf-8")
    cl = ROOT / "CHANGELOG.md"
    text = cl.read_text(encoding="utf-8")
    entry = "## v%s — TODO short title\n\n- TODO what changed, in one line per change\n\n" % ver
    text = text.replace("# Changelog\n\n", "# Changelog\n\n" + entry, 1) if "# Changelog" in text else entry + text
    cl.write_text(text, encoding="utf-8")
    print("VERSION -> %s. Fill in the CHANGELOG entry, then: python scripts/release.py check" % ver)


def cmd_notes(args):
    ver = args[0].lstrip("v") if args else V.read_version()
    for v, title, body in V.changelog_sections((ROOT / "CHANGELOG.md").read_text(encoding="utf-8")):
        if v == ver:
            print("%s\n" % title if title else "", end="")
            print(body)
            return
    sys.exit("no CHANGELOG entry for v%s" % ver)


def cmd_ship(args):
    ver = V.read_version()
    top = top_entry()
    title = top[1] if top else "release"
    print("git add -A")
    print('git commit -m "v%s: %s"' % (ver, title))
    print("git push")
    print("git tag v%s && git push origin v%s    # CI runs the tests, then publishes the GitHub Release" % (ver, ver))


if __name__ == "__main__":
    cmds = {"check": cmd_check, "bump": cmd_bump, "notes": cmd_notes, "ship": cmd_ship}
    if len(sys.argv) < 2 or sys.argv[1] not in cmds:
        sys.exit(__doc__)
    cmds[sys.argv[1]](sys.argv[2:])
