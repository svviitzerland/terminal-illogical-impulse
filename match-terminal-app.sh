#!/usr/bin/env bash
# Make macOS Terminal.app look like the Ghostty setup.
#
# Terminal.app keeps its own font and colours, so a shared ~/.zshrc is not enough:
# starship still runs and the OSC sequences still set the 256-colour palette, but the
# Nerd Font glyphs render as tofu because the profile font has no Private Use Area.
# Terminal.app has no config file for this, so drive it over AppleScript.
set -euo pipefail

PROFILE="${1:-$(defaults read com.apple.Terminal "Default Window Settings" 2>/dev/null || echo Basic)}"
COLORS="$HOME/.local/state/matyou/colors.json"
[ -f "$COLORS" ] || { echo "Run matcolor first."; exit 1; }

read -r BG FG <<<"$(python3 -c "
import json
d = json.load(open('$COLORS'))['terminal']
# AppleScript wants 16-bit channels
conv = lambda h: ' '.join(str(round(int(h[i:i+2],16) / 255 * 65535)) for i in (1,3,5))
print(conv(d['term0']), conv(d['term7']))
" | awk '{print $1","$2","$3, $4","$5","$6}')"

osascript <<APPLESCRIPT
tell application "Terminal"
  set p to "$PROFILE"
  set font name of settings set p to "JetBrainsMonoNFM-Regular"
  set font size of settings set p to 13
  set background color of settings set p to {$BG}
  set normal text color of settings set p to {$FG}
  set cursor color of settings set p to {$FG}
end tell
APPLESCRIPT

echo "Terminal.app profile \"$PROFILE\" now matches. Open a new Terminal window."
