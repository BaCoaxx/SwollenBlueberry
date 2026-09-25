"""Command-line entry points."""

from __future__ import annotations

import argparse
import sys

from gwmultilaunch import __version__


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="gwmultilaunch",
        description="Launch multiple Guild Wars clients on Linux via Wine.",
    )
    parser.add_argument("--version", action="version", version=f"gwmultilaunch {__version__}")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="If the vault is empty, add an account that launches the native stand-in.",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run headless checks (crypto, relaunch rules, stand-in) and exit.",
    )
    parser.add_argument(
        "--config-dir",
        default=None,
        help="Override the config directory (default: $XDG_CONFIG_HOME/gwmultilaunch or ~/.config/gwmultilaunch).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.self_test:
        from gwmultilaunch.selftest import run_self_test

        return run_self_test()
    from gwmultilaunch.app import run_app

    return run_app(args)


if __name__ == "__main__":
    raise SystemExit(main())
