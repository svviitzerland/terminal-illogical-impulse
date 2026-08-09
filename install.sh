#!/usr/bin/env bash
# Install the illogical-impulse Ghostty port. Idempotent; backs up anything it replaces.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG="${XDG_CONFIG_HOME:-$HOME/.config}"
SHARE="$HOME/.local/share/matyou"
BIN="$HOME/.local/bin"
STAMP="$(date +%Y%m%d-%H%M%S)"

say() { printf '\033[1m==>\033[0m %s\n' "$1"; }

[[ "$(uname)" == "Darwin" ]] || { echo "This port targets macOS."; exit 1; }
command -v brew >/dev/null || { echo "Homebrew is required: https://brew.sh"; exit 1; }

say "Installing starship, eza and JetBrains Mono Nerd Font"
brew install --quiet starship eza
brew install --quiet --cask font-jetbrains-mono-nerd-font
if ! [ -d "/Applications/Ghostty.app" ]; then
  say "Ghostty not found — installing"
  brew install --quiet --cask ghostty
fi

say "Creating the colour-generator venv"
mkdir -p "$SHARE" "$BIN" "$HOME/.local/state/matyou" "$CONFIG/ghostty/themes"
[ -d "$SHARE/venv" ] || python3 -m venv "$SHARE/venv"
"$SHARE/venv/bin/pip" install --quiet --upgrade pip materialyoucolor pillow numpy

# back up then link, so the repo stays the single source of truth
link() {
  local src="$1" dst="$2"
  if [ -e "$dst" ] && [ ! -L "$dst" ]; then
    cp "$dst" "$dst.bak-$STAMP"
    say "Backed up $dst -> $dst.bak-$STAMP"
  fi
  ln -sfn "$src" "$dst"
}

say "Linking configs"
link "$REPO/ghostty/config"            "$CONFIG/ghostty/config"
link "$REPO/starship/starship.toml"    "$CONFIG/starship.toml"
link "$REPO/matyou/generate.py"        "$SHARE/generate.py"
link "$REPO/matyou/scheme-base.json"   "$SHARE/scheme-base.json"
link "$REPO/matyou/matcolor"           "$BIN/matcolor"
chmod +x "$REPO/matyou/matcolor"

say "Wiring ~/.zshrc"
MARK='# --- illogical-impulse look'
if grep -qF "$MARK" "$HOME/.zshrc" 2>/dev/null; then
  say "Already present in ~/.zshrc, leaving it alone"
else
  cp "$HOME/.zshrc" "$HOME/.zshrc.bak-$STAMP" 2>/dev/null || true
  printf '\n' >>"$HOME/.zshrc"
  cat "$REPO/zsh/illogical-impulse.zsh" >>"$HOME/.zshrc"
fi
case ":$PATH:" in
  *":$HOME/.local/bin:"*) ;;
  *) say "Add \$HOME/.local/bin to your PATH to use \`matcolor\` directly" ;;
esac

say "Generating a first theme"
"$BIN/matcolor" --scheme scheme-neutral --color '#8A8F98' --mode dark || \
  say "Theme generation skipped — run \`matcolor <image>\` yourself"

say "Done. Open a new Ghostty window."
