"""Tests for versions and the updater (no network): python tests/test_version.py"""
import io
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import update as U  # noqa: E402
import version as V  # noqa: E402

fails = []


def check(ok, name):
    print(("PASS  " if ok else "FAIL  ") + name)
    if not ok:
        fails.append(name)


check(V.is_newer("v0.2.0", "0.1.9") and not V.is_newer("0.1.0", "0.1.0") and V.is_newer("1.0.0", "0.99.99"), "semver comparison")
check(subprocess.run([sys.executable, str(ROOT / "scripts" / "release.py"), "check"], capture_output=True).returncode == 0,
      "VERSION matches the CHANGELOG top entry")
cl = "# Changelog\n\n## v0.3.0 — c\n\n- three\n\n## v0.2.0 — b\n\n- two\n\n## 0.1.0 — a\n\n- one\n"
check([s[0] for s in V.changelog_between(cl, "0.1.0", "0.3.0")] == ["0.3.0", "0.2.0"], "changelog_between lists only newer entries")


def make_zip(files, top="owner-repo-abc123/"):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, data in files.items():
            z.writestr(top + name, data)
    return buf.getvalue()


with tempfile.TemporaryDirectory() as td:
    inst = Path(td) / "install"
    (inst / "scripts").mkdir(parents=True)
    (inst / "Projects" / "mymap").mkdir(parents=True)
    (inst / "Resources" / "brand").mkdir(parents=True)
    (inst / "VERSION").write_text("0.1.0\n")
    (inst / "scripts" / "old.py").write_text("old = 1\n")
    (inst / "Projects" / "mymap" / "config.json").write_text('{"keep": true}')
    (inst / "Resources" / "brand" / "brand.json").write_text('{"keep": true}')
    zdata = make_zip({"VERSION": "0.2.0\n", "scripts/old.py": "old = 2\n", "scripts/new.py": "new = 1\n",
                      "CHANGELOG.md": cl, "Projects/mymap/config.json": "OVERWRITTEN", "Resources/brand/brand.json": "OVERWRITTEN"})
    zf = Path(td) / "rel.zip"
    zf.write_bytes(zdata)
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "update.py"), "--zip", str(zf), "--root", str(inst)], capture_output=True, text=True)
    check(r.returncode == 0 and "UPDATED to v0.2.0" in r.stdout, "update.py applies a newer release zip")
    check((inst / "VERSION").read_text().strip() == "0.2.0" and (inst / "scripts" / "old.py").read_text() == "old = 2\n"
          and (inst / "scripts" / "new.py").exists(), "managed files replaced / added")
    check("keep" in (inst / "Projects" / "mymap" / "config.json").read_text() and "keep" in (inst / "Resources" / "brand" / "brand.json").read_text(),
          "maps and brand files are never touched")
    backups = list((inst / "_update_backup").rglob("old.py"))
    check(len(backups) == 1 and backups[0].read_text() == "old = 1\n", "replaced file saved in _update_backup")
    check("== v0.2.0" in r.stdout, "changelog of the new versions is shown")
    bad = Path(td) / "bad.zip"
    bad.write_bytes(make_zip({"VERSION": "0.9.0\n", "scripts/../../evil.py": "x"}))
    rb = subprocess.run([sys.executable, str(ROOT / "scripts" / "update.py"), "--zip", str(bad), "--root", str(inst)], capture_output=True, text=True)
    check(rb.returncode != 0 and not (Path(td) / "evil.py").exists(), "zip with ../ paths is rejected")
    nov = Path(td) / "nov.zip"
    nov.write_bytes(make_zip({"scripts/x.py": "x"}))
    rn = subprocess.run([sys.executable, str(ROOT / "scripts" / "update.py"), "--zip", str(nov), "--root", str(inst)], capture_output=True, text=True)
    check(rn.returncode != 0, "zip without VERSION is rejected")
    (inst / ".git").mkdir()
    r2 = subprocess.run([sys.executable, str(ROOT / "scripts" / "update.py"), "--zip", str(zf), "--root", str(inst)], capture_output=True, text=True)
    check("git clone" in r2.stdout, "a git clone is told to use git pull")

print("\n%d check(s) failed" % len(fails))
sys.exit(1 if fails else 0)
