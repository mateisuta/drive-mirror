"""drive-mirror: back up chosen folders into Google Drive (or any synced folder), keeping the same layout.

Copy only, never delete. Standard library only.
"""
import glob
import json
import os
import shutil
import subprocess
import sys
import time

__version__ = "0.1.0"

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".Trash", ".Spotlight-V100", ".fseventsd", "$RECYCLE.BIN",
             "System Volume Information"}
SKIP_FILES = {".DS_Store", "Thumbs.db", "desktop.ini", "Icon\r"}
SKIP_ENDS = (".tmp", ".part", ".crdownload", ".download", ".dmpart")
PART = ".dmpart"
LABEL = "io.github.drive-mirror"


def config_dir():
    if os.environ.get("DRIVE_MIRROR_HOME"):
        return os.environ["DRIVE_MIRROR_HOME"]
    if sys.platform.startswith("win"):
        return os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "drive-mirror")
    return os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "drive-mirror")


def conf_path():
    return os.path.join(config_dir(), "config.json")


def load():
    try:
        with open(conf_path(), encoding="utf-8") as fh:
            c = json.load(fh)
    except (OSError, ValueError):
        c = {}
    c.setdefault("target", "")
    c.setdefault("account", "")
    c.setdefault("under", "Backups")
    c.setdefault("min_free_gb", 10)
    c.setdefault("folders", [])
    c.setdefault("exclude", [])
    return c


def save(c):
    os.makedirs(config_dir(), exist_ok=True)
    p = conf_path()
    with open(p + ".tmp", "w", encoding="utf-8") as fh:
        json.dump(c, fh, ensure_ascii=False, indent=2)
    os.replace(p + ".tmp", p)


def find_drives():
    """The Google Drive for desktop folders on this computer."""
    home = os.path.expanduser("~")
    found = glob.glob(os.path.join(home, "Library", "CloudStorage", "GoogleDrive-*", "My Drive"))   # macOS
    found += glob.glob(os.path.join(home, "Google Drive", "My Drive")) + glob.glob(os.path.join(home, "Google Drive"))
    if sys.platform.startswith("win"):                                                            # Windows: G:\My Drive
        for letter in "GHIJKLMNOPQRSTUVWXYZ":
            p = letter + ":\\My Drive"
            if os.path.isdir(p):
                found.append(p)
    seen, out = set(), []
    for p in found:
        if os.path.isdir(p) and p not in seen and not os.path.isdir(os.path.join(p, "My Drive")):
            seen.add(p)
            out.append(p)
    return sorted(out)


def target_root(c):
    """Where the backups go: the configured target, else the Google Drive folder (of the chosen account)."""
    if c.get("target"):
        return os.path.expanduser(c["target"])
    drives = find_drives()
    if c.get("account"):
        drives = [d for d in drives if c["account"] in d]
    return drives[0] if drives else ""


def _skipped(name, is_dir, excl):
    if is_dir:
        return name in SKIP_DIRS or name in excl
    return name in SKIP_FILES or name.endswith(SKIP_ENDS) or name in excl


def mirror(src, dest, dry=False, min_free=10 * 1024 ** 3, exclude=(), log=None):
    """Copy every new or changed file of src into dest with the same layout. Never deletes. Returns the counts."""
    st = {"copied": 0, "same": 0, "bytes": 0, "failed": [], "stopped": ""}
    excl = set(exclude or ())
    dest_abs = os.path.abspath(dest)
    for dp, dirs, files in os.walk(src):
        dirs[:] = sorted(d for d in dirs if not _skipped(d, True, excl)
                         and os.path.abspath(os.path.join(dp, d)) != dest_abs)        # never copy into itself
        rel = os.path.relpath(dp, src)
        tdir = dest if rel == "." else os.path.join(dest, rel)
        for f in sorted(files):
            if _skipped(f, False, excl):
                continue
            s, t = os.path.join(dp, f), os.path.join(tdir, f)
            try:
                ss = os.stat(s)
            except OSError:
                continue
            try:
                ts = os.stat(t)
                if ts.st_size == ss.st_size and abs(ts.st_mtime - ss.st_mtime) < 2:
                    st["same"] += 1
                    continue
            except OSError:
                pass
            if min_free and shutil.disk_usage(os.path.expanduser("~")).free - ss.st_size < min_free:
                st["stopped"] = "the disk would go under %d GB free" % (min_free // 1024 ** 3)
                return st
            if not dry:
                try:
                    os.makedirs(tdir, exist_ok=True)
                    shutil.copy2(s, t + PART)
                    os.replace(t + PART, t)
                except OSError as e:
                    st["failed"].append("%s: %s" % (os.path.relpath(s, src), str(e)[:100]))
                    continue
            st["copied"] += 1
            st["bytes"] += ss.st_size
            if log:
                log(os.path.relpath(s, src))
    return st


def run(dry=False, verbose=False, out=print):
    c = load()
    root = target_root(c)
    if not root:
        out("No Google Drive folder found. Install Google Drive for desktop, or set one: drive-mirror target <folder>")
        return 1
    if not c["folders"]:
        out("No folders yet: drive-mirror add <folder>")
        return 0
    tot = {"copied": 0, "same": 0, "bytes": 0, "failed": [], "stopped": ""}
    for f in c["folders"]:
        src = os.path.expanduser(f["path"])
        if not os.path.isdir(src):
            out("%s: not found (%s), skipped" % (f["as"], src))
            continue
        dest = os.path.join(root, c["under"], f["as"]) if c["under"] else os.path.join(root, f["as"])
        st = mirror(src, dest, dry, int(c["min_free_gb"] * 1024 ** 3), c["exclude"],
                    log=(lambda p: out("  + " + p)) if verbose else None)
        out("%s: %d %s (%.1f MB), %d unchanged%s%s" % (
            f["as"], st["copied"], "to copy" if dry else "copied", st["bytes"] / 1e6, st["same"],
            ", %d failed" % len(st["failed"]) if st["failed"] else "", " - stopped: " + st["stopped"] if st["stopped"] else ""))
        for x in st["failed"][:10]:
            out("  ! " + x)
        for k in ("copied", "same", "bytes"):
            tot[k] += st[k]
        tot["failed"] += st["failed"]
        if st["stopped"]:
            tot["stopped"] = st["stopped"]
            break
    if not dry:
        os.makedirs(config_dir(), exist_ok=True)
        with open(os.path.join(config_dir(), "log.jsonl"), "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"at": time.time(), "target": root, **tot, "failed": tot["failed"][:50]}) + "\n")
    return 0


# ---- the schedule -------------------------------------------------------------------------------------------------

def _cmd():
    return [sys.executable, "-m", "drive_mirror", "run"]


def schedule(on, every_min=60):
    """Turn the regular run on or off: launchd on macOS, Task Scheduler on Windows, a crontab line on Linux."""
    pkg_parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if sys.platform == "darwin":
        plist = os.path.expanduser("~/Library/LaunchAgents/%s.plist" % LABEL)
        if os.path.exists(plist):
            subprocess.run(["launchctl", "unload", "-w", plist], capture_output=True)
            os.remove(plist)
        if not on:
            return "off"
        args = "".join("<string>%s</string>" % a for a in _cmd())
        logf = os.path.join(config_dir(), "last-run.txt")
        os.makedirs(os.path.dirname(plist), exist_ok=True)
        os.makedirs(config_dir(), exist_ok=True)
        with open(plist, "w") as fh:
            fh.write('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
                     '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n<plist version="1.0"><dict>'
                     '<key>Label</key><string>%s</string><key>ProgramArguments</key><array>%s</array>'
                     '<key>WorkingDirectory</key><string>%s</string>'
                     '<key>EnvironmentVariables</key><dict><key>PYTHONPATH</key><string>%s</string></dict>'
                     '<key>StartInterval</key><integer>%d</integer><key>RunAtLoad</key><true/>'
                     '<key>LowPriorityIO</key><true/><key>Nice</key><integer>10</integer>'
                     '<key>StandardOutPath</key><string>%s</string><key>StandardErrorPath</key><string>%s</string>'
                     '</dict></plist>\n' % (LABEL, args, pkg_parent, pkg_parent, every_min * 60, logf, logf))
        subprocess.run(["launchctl", "load", "-w", plist], capture_output=True)
        return "on (launchd, every %d min)" % every_min
    if sys.platform.startswith("win"):
        subprocess.run(["schtasks", "/Delete", "/TN", "drive-mirror", "/F"], capture_output=True)
        if not on:
            return "off"
        tr = 'cmd /c "cd /d %s && %s"' % (pkg_parent, subprocess.list2cmdline(_cmd()))
        r = subprocess.run(["schtasks", "/Create", "/TN", "drive-mirror", "/SC", "MINUTE", "/MO", str(every_min),
                            "/TR", tr, "/F"], capture_output=True, text=True)
        return "on (Task Scheduler, every %d min)" % every_min if r.returncode == 0 else "not set: " + r.stderr.strip()
    line = "*/%d * * * * cd %s && %s" % (min(every_min, 59), pkg_parent, " ".join(_cmd()))
    return "add this line with `crontab -e`:\n  " + line if on else "remove the drive-mirror line with `crontab -e`"


def scheduled():
    if sys.platform == "darwin":
        return os.path.exists(os.path.expanduser("~/Library/LaunchAgents/%s.plist" % LABEL))
    if sys.platform.startswith("win"):
        return subprocess.run(["schtasks", "/Query", "/TN", "drive-mirror"], capture_output=True).returncode == 0
    return None
