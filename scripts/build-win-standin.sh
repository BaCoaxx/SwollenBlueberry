#!/bin/sh
# Build the Win32 stand-in with mingw-w64. Wine can run the resulting .exe.
set -eu
root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
out="$root/standin-win/gw-standin.exe"
x86_64-w64-mingw32-gcc -O2 -s -mwindows -o "$out" "$root/standin-win/standin.c"
echo "built $out"
