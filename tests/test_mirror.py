import json
import os
import subprocess
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import drive_mirror as dm  # noqa: E402


def write(p, text):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as fh:
        fh.write(text)


class Mirror(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.mkdtemp()
        self.src, self.dst = os.path.join(self.t, "src"), os.path.join(self.t, "dst")
        write(os.path.join(self.src, "top.txt"), "hi")
        write(os.path.join(self.src, "a", "b", "deep.md"), "deep")
        write(os.path.join(self.src, ".git", "HEAD"), "x")
        write(os.path.join(self.src, "node_modules", "m.js"), "x")
        write(os.path.join(self.src, ".DS_Store"), "x")
        write(os.path.join(self.src, "half.part"), "x")

    def files(self):
        return sorted(os.path.relpath(os.path.join(d, f), self.dst) for d, _, fs in os.walk(self.dst) for f in fs)

    def test_same_layout_and_skips(self):
        st = dm.mirror(self.src, self.dst, min_free=0)
        self.assertEqual(st["copied"], 2)
        self.assertEqual(self.files(), [os.path.join("a", "b", "deep.md"), "top.txt"])

    def test_dry_copies_nothing(self):
        st = dm.mirror(self.src, self.dst, dry=True, min_free=0)
        self.assertEqual(st["copied"], 2)
        self.assertFalse(os.path.exists(self.dst))

    def test_only_changed_recopied(self):
        dm.mirror(self.src, self.dst, min_free=0)
        time.sleep(0.01)
        write(os.path.join(self.src, "top.txt"), "hi again")
        st = dm.mirror(self.src, self.dst, min_free=0)
        self.assertEqual((st["copied"], st["same"]), (1, 1))
        with open(os.path.join(self.dst, "top.txt")) as fh:
            self.assertEqual(fh.read(), "hi again")

    def test_never_deletes(self):
        dm.mirror(self.src, self.dst, min_free=0)
        os.remove(os.path.join(self.src, "a", "b", "deep.md"))
        dm.mirror(self.src, self.dst, min_free=0)
        self.assertIn(os.path.join("a", "b", "deep.md"), self.files())

    def test_keeps_modified_time(self):
        dm.mirror(self.src, self.dst, min_free=0)
        a, b = os.stat(os.path.join(self.src, "top.txt")), os.stat(os.path.join(self.dst, "top.txt"))
        self.assertLess(abs(a.st_mtime - b.st_mtime), 2)

    def test_disk_floor_stops(self):
        st = dm.mirror(self.src, self.dst, min_free=10 ** 18)
        self.assertTrue(st["stopped"])
        self.assertEqual(st["copied"], 0)

    def test_not_into_itself(self):
        inner = os.path.join(self.src, "backup")
        st = dm.mirror(self.src, inner, min_free=0)
        st2 = dm.mirror(self.src, inner, min_free=0)
        self.assertEqual(st2["copied"], 0, st)

    def test_cli_end_to_end(self):
        env = dict(os.environ, DRIVE_MIRROR_HOME=os.path.join(self.t, "conf"))
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        go = lambda *a: subprocess.run([sys.executable, "-m", "drive_mirror", *a], cwd=root, env=env,
                                       capture_output=True, text=True)
        go("target", self.dst)
        r = go("add", self.src, "--as", "School", "--no-schedule")
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(os.path.join(self.t, "conf", "config.json")) as fh:
            json.load(fh)
        r = go("run")
        self.assertIn("School: 2 copied", r.stdout)
        self.assertTrue(os.path.exists(os.path.join(self.dst, "Backups", "School", "a", "b", "deep.md")))


if __name__ == "__main__":
    unittest.main()
