# drive-mirror

Back up the folders you choose into Google Drive, keeping the same folder layout. Set it once, and it runs every hour.

```
~/Documents/School/                    My Drive/Backups/School/
├── notes.md              ──────▶      ├── notes.md
└── term-2/                            └── term-2/
    └── essay.docx                         └── essay.docx
```

- **Copy only, never delete.** A file you delete or move on your computer stays on Drive. Nothing on your computer is ever changed.
- **Only what changed.** A file is copied when it is new, or when its size or modified time changed. The copy keeps the original's modified time.
- **No Google sign-in, no API keys.** It writes into the folder that [Google Drive for desktop](https://www.google.com/drive/download/) already shows on your computer, and Drive uploads it. It works the same with any synced folder: OneDrive, Dropbox, iCloud Drive, a NAS or a USB disk.
- **Safe defaults.** It skips `.git`, `node_modules`, `__pycache__`, `.DS_Store`, `Thumbs.db` and half-downloaded files. It stops before your disk drops under 10 GB free, because Drive for desktop keeps a local copy of each file until it is uploaded. A file appears on Drive only once it is fully written.
- **Python 3.8+, standard library only.** It runs on macOS, Windows and Linux.

## Install

```bash
git clone https://github.com/mateisuta/drive-mirror.git
cd drive-mirror
pip install .          # optional: gives you the `drive-mirror` command
```

Without `pip install`, use `python3 -m drive_mirror` from the cloned folder in place of `drive-mirror`.

## Use

```bash
drive-mirror add ~/Documents/School          # back up a folder (turns on the hourly run)
drive-mirror add ~/Desktop/Projects --as Code
drive-mirror list                            # what is backed up, where, and whether the schedule is on
drive-mirror run --dry                       # show what would be copied
drive-mirror run                             # copy now
drive-mirror remove Code                     # stop backing it up (Drive keeps its copy)
```

### Settings

| Command | What it does |
|---|---|
| `drive-mirror drives` | the Google Drive folders found on this computer |
| `drive-mirror account you@gmail.com` | with several Google accounts signed in: pick one |
| `drive-mirror target /Volumes/NAS/backup` | back up into any folder instead of Google Drive |
| `drive-mirror under "Laptop backup"` | the Drive folder that holds everything (default `Backups`) |
| `drive-mirror exclude build` | also skip files or folders with this exact name |
| `drive-mirror schedule on --every 30` / `off` | the regular run |

The schedule uses **launchd** on macOS, **Task Scheduler** on Windows, and on Linux it prints a `crontab` line for you to add. The settings live in `~/.config/drive-mirror/config.json` (on Windows, `%APPDATA%\drive-mirror`), and every run is logged in `log.jsonl` next to them.

## Why not just use Drive for desktop's "Back up folders"?

That works for a few folders on one computer, but you can't choose the layout on Drive, and a file you delete locally is removed from Drive too. drive-mirror is one-way and keeps everything, puts each computer's folders wherever you choose in My Drive, and works with any synced folder, not only Google's.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

## License

MIT
