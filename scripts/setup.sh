#!/bin/bash
# One-time setup: Python venv with dependencies (+ fonts if the skill doesn't ship them).
# Everything goes to $PDF_T2S_HOME (default ~/.cache/pdf-t2s), so the skill dir can be read-only.
# Prints the python interpreter to use. Safe to re-run.
set -e
SKILL="$(cd "$(dirname "$0")/.." && pwd)"
HOME_DIR="${PDF_T2S_HOME:-$HOME/.cache/pdf-t2s}"
mkdir -p "$HOME_DIR"
PY="$HOME_DIR/venv/bin/python"
if [ ! -x "$PY" ]; then
  python3 -m venv "$HOME_DIR/venv"
fi
"$PY" -c "import fitz, opencc, fontTools" 2>/dev/null || \
  "$HOME_DIR/venv/bin/pip" install -q pymupdf opencc-python-reimplemented fonttools >&2
for w in Regular Bold; do
  [ -s "$SKILL/fonts/NotoSansSC-$w.otf" ] && continue
  f="$HOME_DIR/fonts/NotoSansSC-$w.otf"
  mkdir -p "$HOME_DIR/fonts"
  [ -s "$f" ] || curl -sfL -o "$f" "https://github.com/notofonts/noto-cjk/raw/main/Sans/SubsetOTF/SC/NotoSansSC-$w.otf"
done
echo "$PY"
