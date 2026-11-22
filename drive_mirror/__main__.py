"""drive-mirror command line."""
import argparse
import os
import sys

from . import __version__, find_drives, load, run, save, schedule, scheduled, target_root


def main(argv=None):
    ap = argparse.ArgumentParser(prog="drive-mirror", description="Back up folders into Google Drive, same layout. "
                                 "Copies new and changed files; never deletes.")
    ap.add_argument("--version", action="version", version="drive-mirror " + __version__)
    sub = ap.add_subparsers(dest="cmd")
    a = sub.add_parser("add", help="back up a folder")
    a.add_argument("folder")
    a.add_argument("--as", dest="name", help="its name on Drive (default: the folder's name)")
    a.add_argument("--no-schedule", action="store_true", help="do not turn on the hourly run")
    r = sub.add_parser("remove", help="stop backing up a folder (Drive keeps its copy)")
    r.add_argument("name")
    sub.add_parser("list", help="the folders, where they go, the schedule")
    ru = sub.add_parser("run", help="copy what changed, now")
    ru.add_argument("--dry", action="store_true", help="show what would be copied")
    ru.add_argument("-v", "--verbose", action="store_true", help="name every file copied")
    t = sub.add_parser("target", help="back up into this folder instead of the Google Drive found")
    t.add_argument("folder", nargs="?", default="")
    ac = sub.add_parser("account", help="with several Google accounts: which one (part of its email)")
    ac.add_argument("email")
    u = sub.add_parser("under", help="the folder on Drive that holds the backups (default: Backups; '' for none)")
    u.add_argument("name")
    ex = sub.add_parser("exclude", help="also skip files or folders with this exact name")
    ex.add_argument("name")
    s = sub.add_parser("schedule", help="turn the regular run on or off")
    s.add_argument("state", choices=["on", "off"])
    s.add_argument("--every", type=int, default=60, help="minutes between runs (default 60)")
    sub.add_parser("drives", help="the Google Drive folders found on this computer")
    o = ap.parse_args(argv)
    c = load()

    if o.cmd == "add":
        path = os.path.abspath(os.path.expanduser(o.folder))
        if not os.path.isdir(path):
            print("not a folder: " + path)
            return 1
        name = o.name or os.path.basename(path.rstrip("/\\")) or "root"
        c["folders"] = [f for f in c["folders"] if f["as"] != name] + [{"path": path, "as": name}]
        save(c)
        print("added %s -> %s" % (path, os.path.join(target_root(c) or "(no Drive found yet)", c["under"], name)))
        if not o.no_schedule and not scheduled():
            print("schedule: " + schedule(True))
        return 0
    if o.cmd == "remove":
        before = len(c["folders"])
        c["folders"] = [f for f in c["folders"] if o.name not in (f["as"], f["path"])]
        save(c)
        print(("removed %s (Drive keeps its copy)" % o.name) if len(c["folders"]) < before else "not in the list: " + o.name)
        if not c["folders"] and scheduled():
            print("schedule: " + schedule(False))
        return 0
    if o.cmd == "run":
        return run(o.dry, o.verbose)
    if o.cmd == "target":
        c["target"] = os.path.abspath(os.path.expanduser(o.folder)) if o.folder else ""
        save(c)
        print("target: " + (target_root(c) or "not found"))
        return 0
    if o.cmd == "account":
        c["account"] = o.email
        save(c)
        print("target: " + (target_root(c) or "no Drive folder for that account"))
        return 0
    if o.cmd == "under":
        c["under"] = o.name
        save(c)
        return 0
    if o.cmd == "exclude":
        c["exclude"] = sorted(set(c["exclude"]) | {o.name})
        save(c)
        return 0
    if o.cmd == "schedule":
        print("schedule: " + schedule(o.state == "on", o.every))
        return 0
    if o.cmd == "drives":
        for d in find_drives():
            print(d)
        return 0
    root = target_root(c)
    print("target: %s" % (os.path.join(root, c["under"]) if root else "(no Google Drive folder found)"))
    for f in c["folders"]:
        print("  %-20s <- %s" % (f["as"], f["path"]))
    if not c["folders"]:
        print("  no folders yet: drive-mirror add <folder>")
    sch = scheduled()
    print("schedule: " + ("on" if sch else "off" if sch is False else "see crontab -l"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
