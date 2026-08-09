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

echo "Handlers:"
for e in sh zsh command tool; do printf '  %-8s -> %s\n' "$e" "$(duti -x "$e" 2>/dev/null | head -1)"; done
echo
echo "Note: .bash stays with whatever else claims it — Terminal.app does not declare"
echo "public.bash-script, so LaunchServices will not accept it as the handler."
