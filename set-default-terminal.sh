#!/usr/bin/env bash
# Point macOS at Ghostty wherever a "default terminal" actually exists.
# macOS has no single setting for this, so each surface is handled separately.
set -euo pipefail

BUNDLE="com.mitchellh.ghostty"
command -v duti >/dev/null || brew install --quiet duti

# Double-clicking a script in Finder, and the app that runs unix executables
duti -s "$BUNDLE" public.shell-script all
duti -s "$BUNDLE" com.apple.terminal.shell-script all
duti -s "$BUNDLE" public.unix-executable shell

# A `ghostty` on PATH, so $TERMINAL resolves for tools that spawn a terminal
mkdir -p "$HOME/.local/bin"
ln -sfn /Applications/Ghostty.app/Contents/MacOS/ghostty "$HOME/.local/bin/ghostty"

# VS Code's "Open in External Terminal"
CODE="$HOME/Library/Application Support/Code/User/settings.json"
if [ -f "$CODE" ]; then
  python3 - "$CODE" <<'PY'
import json, io, shutil, sys
p = sys.argv[1]
shutil.copy(p, p + '.bak-ghostty')
d = json.load(open(p))
d["terminal.external.osxExec"] = "Ghostty.app"
d["terminal.explorerKind"] = "external"
with io.open(p, 'w', encoding='utf-8') as f:
    json.dump(d, f, indent=4, ensure_ascii=False); f.write('\n')
PY
fi

echo "Done. Verify with: duti -x sh"
