#!/usr/bin/env bash
# Point macOS at Terminal.app for shell scripts and unix executables.
# macOS has no single "default terminal" setting, so each surface is set separately.
set -euo pipefail

BUNDLE="com.apple.Terminal"
command -v duti >/dev/null || brew install --quiet duti

for uti in public.shell-script public.zsh-script com.apple.terminal.shell-script; do
  duti -s "$BUNDLE" "$uti" all
done
duti -s "$BUNDLE" public.unix-executable shell

# Terminal.app auto-marks every prompt line and draws the mark as a bracket pair at the
# far left and far right of that line. With a two-line prompt this reads as a stray "["
# and "]" wrapping the command you just ran. The brackets are drawn decoration, not text,
# which is why they never show up in the scrollback buffer.
#
# There is no key to keep the marks but hide the indicator, so this turns auto-marking
# off entirely. Cost: Cmd-Up / Cmd-Down prompt navigation and Cmd-L "clear to previous
# mark" lose their automatic anchors. Mark manually from Edit > Marks if you want them.
defaults write com.apple.Terminal AutoMarkPromptLines -bool false
python3 - <<'PY'
import subprocess, plistlib
raw = subprocess.run(["defaults","export","com.apple.Terminal","-"],capture_output=True).stdout
d = plistlib.loads(raw)
for prof in d.get("Window Settings", {}).values():
    prof["AutoMarkPromptLines"] = False
subprocess.run(["defaults","import","com.apple.Terminal","-"], input=plistlib.dumps(d))
PY
echo "Auto-marking disabled. Quit Terminal.app completely (Cmd-Q) and reopen."

echo "Handlers:"
for e in sh zsh command tool; do printf '  %-8s -> %s\n' "$e" "$(duti -x "$e" 2>/dev/null | head -1)"; done
echo
echo "Note: .bash stays with whatever else claims it — Terminal.app does not declare"
echo "public.bash-script, so LaunchServices will not accept it as the handler."
