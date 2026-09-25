# GWMultiLaunch

Minimalist Linux launcher for running more than one Guild Wars client. Each account starts `Gw.exe` under Wine with the game's own login arguments. The launcher does not inject DLLs, load GWToolbox or texmod/gMod, or patch process memory.

## Install

Python 3.11 or newer:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Runtime libraries are pinned in `pyproject.toml` and `requirements.txt` (PySide6, cryptography, psutil). Pytest is the `dev` extra.

Guild Wars itself is a Windows program. Install Wine so the `wine` binary is on `PATH`, or set another binary in Settings or on the account.

Optional: `wmctrl` (package `wmctrl`) so a dead X11 window can be tied to a zombie process. Without it, online/offline uses the process tree only. Zombies are always treated as offline.

## Run

```bash
gwmultilaunch
# or
python -m gwmultilaunch
```

On first launch, choose a master password (at least 8 characters). It encrypts the account vault at:

```text
${XDG_CONFIG_HOME:-~/.config}/gwmultilaunch/accounts.enc
```

Non-secret settings (default Wine binary, poll interval) live in `settings.json` beside that file. `examples/settings.example.json` matches the shape. `examples/accounts.example.json` shows the decrypted account list with `REPLACE_ME` passwords — it is not something you copy over the vault.

`--config-dir PATH` points at a different folder. `--demo` adds one account that runs the native stand-in when the vault is empty, so you can try the window without Guild Wars or Wine.

Closing the launcher does not stop clients that are already running. Relaunch intent lasts only for this session: press Launch again after you reopen the app.

## Accounts

| Field | Meaning |
| --- | --- |
| Title | Optional name in the list. Otherwise the character, otherwise the email. |
| Email, password, character | Passed to Gw.exe. Character is omitted when blank. |
| Gw.exe | Absolute path to **that copy** of `Gw.exe`. |
| Extra args | Appended as extra arguments (quotes are honored; nothing is run through a shell). |
| Wine prefix | Empty uses Wine's default prefix (`~/.wine`). |
| Wine binary | Empty uses the Settings value, which defaults to `wine`. |
| Relaunch | When on, a client you started that then exits is started again after 3 seconds. |

The list dot is green when that account's client is running and red when it is not. Double-click a row to launch it. **Stop** marks the account as intentionally stopped so it will not relaunch until you press Launch.

If the same account dies 5 times within 2 minutes, relaunch pauses and the row says **relaunch paused**. The failure count clears after the client stays online for more than 30 seconds, or when you press Stop or Launch.

## Multi-box and Wine

Guild Wars locks its data file and, on Windows, gwlauncher avoids the single-instance mutex by patching memory. This program does not do that.

Use one copied Guild Wars folder per account. Each copy needs its own `Gw.exe` and `Gw.dat`. Point that account's path at that copy. Two rows must not share a path; the launcher refuses to save a duplicate because status and Stop would target the same process. Multi-box means those separate install folders (a copy of the exe in each): `tests/test_multibox.py` launches the same `Gw.exe` filename from two directories and checks that stopping one leaves the other online.

If a second client exits immediately, give that account its own Wine prefix (a separate directory). Wine's mutex and session state are per prefix. That is configuration only — still no memory patch.

The working directory of each launch is the folder that contains that `Gw.exe`. When a prefix is set, the child gets `WINEPREFIX`. An empty prefix clears any `WINEPREFIX` inherited from the shell so Wine uses its default.

Launch shape (argument list, never `shell=True`):

```text
wine /path/to/copy/Gw.exe -email EMAIL -password PASSWORD -character NAME extra args
```

`-character` is left off when the character field is empty. A path that is not a Windows `.exe` is executed directly (or with this Python, for the stand-in script). That is how `--demo` and the tests run without Wine.

## Security

- The vault is Fernet ciphertext. The key is PBKDF2-HMAC-SHA256, 600,000 iterations, with a random salt stored in the file. A wrong master password fails authentication and does not return accounts.
- File mode is `0600`. The config directory is `0700`.
- Passwords are masked in the editor and are not written to the log or the status line. `repr(account)` redacts the password.
- **Guild Wars reads `-password` from its command line.** That value is visible in the process list (`ps`, `/proc/<pid>/cmdline`) for as long as the client is running. gwlauncher has the same property. GWMultiLaunch does not print it, but it cannot hide an argument the game requires.
- Do not commit `accounts.enc` or a filled-in account export. `.gitignore` ignores `*.enc`.

Change the master password from the File menu. Account passwords are re-encrypted; they are not shown.

## Stand-in client

`gwmultilaunch/assets/gw-standin` is a small native client that stays open until it is closed or signaled. It accepts `-email`, `-password`, and `-character` and does not print them. Use it as an account's client path, or run:

```bash
python -m gwmultilaunch --demo
python -m gwmultilaunch.standin --headless
```

A Win32 window with the same role is `standin-win/standin.c`. Build it when `x86_64-w64-mingw32-gcc` is installed:

```bash
scripts/build-win-standin.sh
wine standin-win/gw-standin.exe
```

Point an account at `standin-win/gw-standin.exe` to exercise the Wine path. The prebuilt `standin-win/gw-standin.exe` in this tree is that program.

## Tests

```bash
pytest
python -m gwmultilaunch --self-test
```

`--self-test` is headless: it checks encryption, the log redaction helper, the relaunch rules, and the native stand-in. See `DEMO.md`.

## Out of scope

Texmod, DLL plugins, GWToolbox, Steam accounts, auto-update, and a Windows build of this launcher.
