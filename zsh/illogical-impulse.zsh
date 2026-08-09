# Tools that spawn a terminal (lazygit, ranger, some git helpers) read $TERMINAL.
# ~/.local/bin/ghostty is a symlink to the binary inside Ghostty.app.
export TERMINAL=ghostty

# --- illogical-impulse look (ported from end-4/dots-hyprland) ---
# Material You palette. Ghostty reads themes/material-you at launch, but this also
# repaints terminals that were already open when `matcolor` last ran.
if [[ -f ~/.local/state/matyou/sequences.txt && "$TERM" != "linux" && -z "$SSH_TTY" ]]; then
  cat ~/.local/state/matyou/sequences.txt
fi

# Prompt
eval "$(starship init zsh)"

# eza with icons, as in the upstream fish config
if [[ "$TERM" != "linux" ]]; then
  alias ls='eza --icons=auto'
  alias ll='eza --icons=auto -l --git'
  alias la='eza --icons=auto -la --git'
  alias lt='eza --icons=auto --tree --level=2'
fi

# Upstream clears scrollback too, not just the screen
alias clear="printf '\033[2J\033[3J\033[1;1H'"
alias celar="printf '\033[2J\033[3J\033[1;1H'"
alias claer="printf '\033[2J\033[3J\033[1;1H'"
# --- end illogical-impulse look ---
