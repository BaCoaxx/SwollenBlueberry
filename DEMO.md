# Headless demo

From the repository root, with the dev extra installed (`pip install -e ".[dev]"`):

```bash
pytest -q
python -m gwmultilaunch --self-test
```

Both commands avoid Guild Wars. They do not print account passwords. `pytest` skips `test_two_wine_install_folders_stay_independent` when `wine` is not on `PATH`; with Wine installed, that test runs two copies of the Win32 stand-in from separate folders.

`pytest` covers the encrypted vault, a wrong master password, the launch argument list (the password is in argv and absent from the log helper), and the relaunch rules: 3 second delay, Stop suppresses relaunch, and five deaths within two minutes pause relaunch. A native stand-in process is started and then stopped so online/offline tracking is real.

`--self-test` runs a shorter version of those checks and exits 0.

To click through the window without a game install:

```bash
python -m gwmultilaunch --demo
```

Create a master password when asked. An empty vault gets one stand-in account. Launch opens a small window (or a headless process if there is no display). Close it and, with relaunch left on, it starts again after 3 seconds. Stop leaves it off.
